# routes/nutrition.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from .auth import login_required
from extensions import db
from services.suggestion_service import get_catalog_suggestions, resolve_catalog_item
from utils import execute_query

nutrition_bp = Blueprint('nutrition', __name__)


@nutrition_bp.get('/api/suggest/foods')
@login_required
def suggest_foods():
    user_id = session['user_id']
    search_term = (request.args.get('q') or '').strip()

    suggestions = get_catalog_suggestions('foods', user_id, search_term)
    return jsonify({'results': suggestions})


TRACKER_DEFINITIONS = [
    {
        'key': 'water',
        'label': 'Acqua',
        'unit': 'ml',
        'unit_singular': 'ml',
        'unit_plural': 'ml',
        'icon': 'bi-droplet',
        'description': 'Monitora rapidamente quanta acqua bevi durante la giornata.',
        'quick_add': [250, 500, 750],
        'input_step': 50,
        'placeholder': 'Quantità in ml',
        'goal_hint': 'Suggerimento: punta a 2-3 litri al giorno.'
    },
    {
        'key': 'coffee',
        'label': 'Caffè',
        'unit': 'tazze',
        'unit_singular': 'tazza',
        'unit_plural': 'tazze',
        'icon': 'bi-cup-hot',
        'description': 'Tieni sotto controllo il numero di caffè che assumi.',
        'quick_add': [1, 2],
        'input_step': 1,
        'placeholder': 'Numero di tazze',
        'goal_hint': 'Suggerimento: limita il consumo serale.'
    },
    {
        'key': 'supplements',
        'label': 'Integratori',
        'unit': 'dosi',
        'unit_singular': 'dose',
        'unit_plural': 'dosi',
        'icon': 'bi-capsule',
        'description': 'Segna se hai assunto i tuoi integratori quotidiani.',
        'quick_add': [1],
        'input_step': 1,
        'placeholder': 'Numero di dosi',
        'goal_hint': 'Aggiungi una nota per ricordare quali integratori hai preso.'
    },
]

TRACKER_LOOKUP = {tracker['key']: tracker for tracker in TRACKER_DEFINITIONS}

DEFAULT_TARGETS = {
    'days_on': 3,
    'days_off': 4,
    'p_on': 1.8,
    'c_on': 5.0,
    'f_on': 0.55,
    'p_off': 1.8,
    'c_off': 3.0,
    'f_off': 0.70,
}


_INTAKE_LOG_READY = False


def ensure_intake_log_table() -> None:
    """Guarantee the intake_log table exists before interacting with it."""

    global _INTAKE_LOG_READY

    if _INTAKE_LOG_READY:
        return

    inspector = inspect(db.engine)

    if inspector.has_table('intake_log'):
        _INTAKE_LOG_READY = True
        return

    statements = (
        """
        CREATE TABLE IF NOT EXISTS intake_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            record_date DATE NOT NULL,
            tracker_type TEXT NOT NULL,
            amount REAL NOT NULL,
            unit TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_intake_log_user_date ON intake_log (user_id, record_date)",
    )

    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

    _INTAKE_LOG_READY = True


def _format_number(value: Optional[float]):
    if value is None:
        return '0'
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _unit_label(tracker: dict, amount: float) -> str:
    singular = tracker.get('unit_singular', tracker['unit'])
    plural = tracker.get('unit_plural', tracker['unit'])
    return singular if float(amount) == 1 else plural


def _format_total(tracker: dict, amount: Optional[float]):
    amount = amount or 0
    if tracker['key'] == 'water':
        if amount <= 0:
            return '0 ml'
        liters = amount / 1000
        liters_label = f" ({liters:.2f} L)" if amount >= 1000 else ''
        return f"{int(round(amount))} ml{liters_label}"

    label = _unit_label(tracker, amount)
    return f"{_format_number(amount)} {label}"


def _format_entry_amount(tracker: dict, amount: Optional[float]):
    amount = amount or 0
    if tracker['key'] == 'water':
        return f"{int(round(amount))} ml"
    return f"{_format_number(amount)} {_unit_label(tracker, amount)}"


def _format_quick_label(value, singular, plural):
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = 0
    label = singular if abs(numeric_value) == 1 else plural
    display_value = _format_number(numeric_value)
    return f"+{display_value} {label}"


def _parse_date_or_today(date_str: Optional[str]) -> tuple[date, str, str, str, bool]:
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return _parse_date_or_today(None)
    else:
        current_date = date.today()

    current_date_str = current_date.strftime('%Y-%m-%d')
    prev_day = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    return current_date, current_date_str, prev_day, next_day, current_date == date.today()


def _build_quick_buttons(tracker: dict) -> list[dict[str, str]]:
    unit_singular = tracker.get('unit_singular', tracker['unit'])
    unit_plural = tracker.get('unit_plural', tracker['unit'])
    return [
        {
            'value': quick,
            'label': _format_quick_label(quick, unit_singular, unit_plural),
        }
        for quick in tracker.get('quick_add', [])
    ]


def _build_tracker_cards(entries: Iterable[dict], totals: dict[str, float]) -> list[dict]:
    grouped_entries = {tracker['key']: [] for tracker in TRACKER_DEFINITIONS}
    for row in entries:
        tracker = TRACKER_LOOKUP.get(row['tracker_type'])
        if not tracker:
            continue
        grouped_entries[row['tracker_type']].append({
            'id': row['id'],
            'amount_label': _format_entry_amount(tracker, row['amount']),
            'note': row['note'],
            'time_label': row['created_at'].strftime('%H:%M') if row['created_at'] else '',
        })

    tracker_cards = []
    for tracker in TRACKER_DEFINITIONS:
        tracker_cards.append({
            **tracker,
            'unit_singular': tracker.get('unit_singular', tracker['unit']),
            'unit_plural': tracker.get('unit_plural', tracker['unit']),
            'quick_buttons': _build_quick_buttons(tracker),
            'entries': grouped_entries.get(tracker['key'], []),
            'total_label': _format_total(tracker, totals.get(tracker['key'])),
        })
    return tracker_cards


def _fetch_intake_entries(user_id: int, date_str: str) -> list[dict]:
    rows = execute_query(
        'SELECT id, tracker_type, amount, unit, note, created_at '
        'FROM intake_log WHERE user_id = :uid AND record_date = :rd ORDER BY created_at DESC',
        {'uid': user_id, 'rd': date_str},
        fetchall=True,
    )
    return rows or []


def _calculate_tracker_totals(entries: Iterable[dict]) -> dict[str, float]:
    totals = {tracker['key']: 0.0 for tracker in TRACKER_DEFINITIONS}
    for row in entries:
        tracker_key = row.get('tracker_type')
        if tracker_key in totals:
            totals[tracker_key] += row.get('amount') or 0
    return totals


def _parse_amount(quick_amount: Optional[str], amount_value: Optional[str]) -> float:
    try:
        return float(quick_amount or amount_value or 0)
    except (TypeError, ValueError):
        return 0.0


def _handle_tracker_post(user_id: int, current_date: str) -> Optional[str]:
    action = request.form.get('action', 'add_entry')
    if action == 'delete_entry':
        entry_id = request.form.get('entry_id')
        if entry_id:
            execute_query(
                'DELETE FROM intake_log WHERE id = :id AND user_id = :uid',
                {'id': entry_id, 'uid': user_id},
                commit=True,
            )
        return None

    tracker_key = request.form.get('tracker_type')
    tracker = TRACKER_LOOKUP.get(tracker_key)
    if not tracker:
        return 'Tracker non valido.'

    amount = _parse_amount(request.form.get('quick_amount'), request.form.get('amount'))
    if amount <= 0:
        return 'Inserisci una quantità valida.'

    note = (request.form.get('note') or '').strip()
    execute_query(
        'INSERT INTO intake_log (user_id, record_date, tracker_type, amount, unit, note) '
        'VALUES (:uid, :rd, :tt, :amt, :unit, :note)',
        {
            'uid': user_id,
            'rd': current_date,
            'tt': tracker_key,
            'amt': amount,
            'unit': tracker['unit'],
            'note': note or None,
        },
        commit=True,
    )
    return None


def _fetch_diet_log(user_id: int, date_str: str) -> list[dict]:
    return execute_query(
        'SELECT dl.id, f.name as food_name, f.user_id, dl.weight, dl.protein, dl.carbs, dl.fat, dl.calories '
        'FROM diet_log dl JOIN foods f ON dl.food_id = f.id '
        'WHERE dl.user_id = :uid AND dl.log_date = :ld',
        {'uid': user_id, 'ld': date_str},
        fetchall=True,
    ) or []


def _fetch_food_options(user_id: int) -> list[dict]:
    raw_food_options = execute_query(
        """
        SELECT id, name, user_id IS NULL AS is_global
        FROM foods
        WHERE user_id IS NULL OR user_id = :uid
        ORDER BY CASE WHEN user_id IS NULL THEN 0 ELSE 1 END,
                 LOWER(name) ASC,
                 name ASC
        """,
        {'uid': user_id},
        fetchall=True,
    ) or []
    return [
        {
            'id': row['id'],
            'name': row['name'],
            'is_global': bool(row['is_global']),
        }
        for row in raw_food_options
    ]


def _calculate_diet_totals(entries: Iterable[dict]) -> dict[str, float]:
    totals = {'protein': 0.0, 'carbs': 0.0, 'fat': 0.0, 'calories': 0.0}
    for item in entries:
        totals['protein'] += item.get('protein') or 0
        totals['carbs'] += item.get('carbs') or 0
        totals['fat'] += item.get('fat') or 0
        totals['calories'] += item.get('calories') or 0
    return totals


def _latest_weight(user_id: int) -> float:
    weight_row = execute_query(
        'SELECT weight FROM daily_data WHERE user_id = :uid AND weight IS NOT NULL '
        'ORDER BY record_date DESC LIMIT 1',
        {'uid': user_id},
        fetchone=True,
    )
    return weight_row['weight'] if weight_row else 0.0


def _fetch_macro_targets(user_id: int) -> dict:
    targets_row = execute_query(
        'SELECT * FROM user_macro_targets WHERE user_id = :uid',
        {'uid': user_id},
        fetchone=True,
    )
    return dict(targets_row) if targets_row else DEFAULT_TARGETS.copy()


def _calculate_target_macros(weight: float, targets_config: dict) -> dict[str, dict[str, float]]:
    target_macros = {'on': {'p': 0.0, 'c': 0.0, 'f': 0.0}, 'off': {'p': 0.0, 'c': 0.0, 'f': 0.0}}
    if weight <= 0:
        return target_macros

    for phase in ('on', 'off'):
        target_macros[phase]['p'] = targets_config[f'p_{phase}'] * weight
        target_macros[phase]['c'] = targets_config[f'c_{phase}'] * weight
        target_macros[phase]['f'] = targets_config[f'f_{phase}'] * weight
    return target_macros


def _calculate_macro_overview(latest_weight: float, targets: dict) -> dict[str, float]:
    calcs = {
        'p_on_g': 0.0,
        'c_on_g': 0.0,
        'f_on_g': 0.0,
        'cal_on': 0.0,
        'p_off_g': 0.0,
        'c_off_g': 0.0,
        'f_off_g': 0.0,
        'cal_off': 0.0,
        'weekly_cal': 0.0,
        'avg_daily_cal': 0.0,
        'cg_ratio': 0.0,
    }

    if latest_weight <= 0:
        return calcs

    calcs['p_on_g'] = targets['p_on'] * latest_weight
    calcs['c_on_g'] = targets['c_on'] * latest_weight
    calcs['f_on_g'] = targets['f_on'] * latest_weight
    calcs['cal_on'] = (calcs['p_on_g'] * 4) + (calcs['c_on_g'] * 4) + (calcs['f_on_g'] * 9)

    calcs['p_off_g'] = targets['p_off'] * latest_weight
    calcs['c_off_g'] = targets['c_off'] * latest_weight
    calcs['f_off_g'] = targets['f_off'] * latest_weight
    calcs['cal_off'] = (calcs['p_off_g'] * 4) + (calcs['c_off_g'] * 4) + (calcs['f_off_g'] * 9)

    calcs['weekly_cal'] = (calcs['cal_on'] * targets['days_on']) + (calcs['cal_off'] * targets['days_off'])
    if targets['days_on'] + targets['days_off'] > 0:
        calcs['avg_daily_cal'] = calcs['weekly_cal'] / 7

    weekly_carbs = (calcs['c_on_g'] * targets['days_on']) + (calcs['c_off_g'] * targets['days_off'])
    weekly_fat = (calcs['f_on_g'] * targets['days_on']) + (calcs['f_off_g'] * targets['days_off'])
    if weekly_fat > 0:
        calcs['cg_ratio'] = weekly_carbs / weekly_fat

    return calcs

def update_daily_totals(user_id, date_str):
    totals_query = """
        SELECT SUM(protein) as p, SUM(carbs) as c, SUM(fat) as f, SUM(calories) as cal
        FROM diet_log WHERE user_id = :user_id AND log_date = :date_str
    """
    totals = execute_query(totals_query, {'user_id': user_id, 'date_str': date_str}, fetchone=True)
    
    total_protein = totals.get('p') or 0
    total_carbs = totals.get('c') or 0
    total_fat = totals.get('f') or 0
    total_calories = totals.get('cal') or 0
    
    upsert_query = """
        INSERT INTO daily_data (user_id, record_date, total_protein, total_carbs, total_fat, calories) 
        VALUES (:user_id, :date_str, :tp, :tc, :tf, :cal)
        ON CONFLICT(user_id, record_date) DO UPDATE SET 
        total_protein = EXCLUDED.total_protein, total_carbs = EXCLUDED.total_carbs, 
        total_fat = EXCLUDED.total_fat, calories = EXCLUDED.calories
    """
    execute_query(upsert_query, {'user_id': user_id, 'date_str': date_str, 'tp': total_protein, 'tc': total_carbs, 'tf': total_fat, 'cal': total_calories}, commit=True)


def _handle_dieta_post(user_id: int, current_date_str: str) -> tuple[Optional[str], Optional[str]]:
    action = request.form.get('action')

    if action == 'add_food':
        food_data = resolve_catalog_item(
            'foods',
            user_id,
            entry_id=request.form.get('food_id'),
            name=request.form.get('food_name'),
        )
        try:
            weight = float(request.form.get('weight', 0))
        except (ValueError, TypeError):
            weight = 0

        if not (food_data and weight > 0):
            return 'danger', "Seleziona un alimento valido dall'archivio e inserisci un peso maggiore di zero."

        factor = weight / food_data['ref_weight']
        protein = food_data['protein'] * factor
        carbs = food_data['carbs'] * factor
        fat = food_data['fat'] * factor
        calories = (protein * 4) + (carbs * 4) + (fat * 9)
        execute_query(
            'INSERT INTO diet_log (user_id, food_id, weight, protein, carbs, fat, calories, log_date) '
            'VALUES (:uid, :fid, :w, :p, :c, :f, :cal, :ld)',
            {
                'uid': user_id,
                'fid': food_data['id'],
                'w': weight,
                'p': protein,
                'c': carbs,
                'f': fat,
                'cal': calories,
                'ld': current_date_str,
            },
            commit=True,
        )
        update_daily_totals(user_id, current_date_str)
        return None, None

    if action == 'delete_entry':
        entry_id = request.form.get('entry_id')
        execute_query(
            'DELETE FROM diet_log WHERE id = :id AND user_id = :uid',
            {'id': entry_id, 'uid': user_id},
            commit=True,
        )
        update_daily_totals(user_id, current_date_str)
        return None, None

    if action == 'set_day_type':
        day_type = request.form.get('day_type')
        query = """
            INSERT INTO daily_data (user_id, record_date, day_type) VALUES (:uid, :rd, :dt)
            ON CONFLICT(user_id, record_date) DO UPDATE SET day_type = EXCLUDED.day_type
        """
        execute_query(query, {'uid': user_id, 'rd': current_date_str, 'dt': day_type}, commit=True)
        return None, None

    return None, None

@nutrition_bp.route('/alimentazione')
@login_required
def alimentazione():
    return render_template('alimentazione.html', title='Alimentazione')


@nutrition_bp.route('/tracking', defaults={'date_str': None}, methods=['GET', 'POST'])
@nutrition_bp.route('/tracking/<date_str>', methods=['GET', 'POST'])
@login_required
def tracking(date_str):
    user_id = session['user_id']
    ensure_intake_log_table()
    current_date, current_date_str, prev_day, next_day, is_today = _parse_date_or_today(date_str)

    if request.method == 'POST':
        error = _handle_tracker_post(user_id, current_date_str)
        if error:
            flash(error, 'danger')
        return redirect(url_for('nutrition.tracking', date_str=current_date_str))

    rows = _fetch_intake_entries(user_id, current_date_str)
    totals = _calculate_tracker_totals(rows)
    tracker_cards = _build_tracker_cards(rows, totals)

    return render_template(
        'tracking.html',
        title='Tracking',
        tracker_cards=tracker_cards,
        date_formatted=current_date.strftime('%d %b %y'),
        current_date_str=current_date_str,
        prev_day=prev_day,
        next_day=next_day,
        is_today=is_today,
    )

@nutrition_bp.route('/diario_alimentare')
@login_required
def diario_alimentare():
    user_id = session['user_id']
    query = """
        SELECT record_date, total_protein, total_carbs, total_fat, calories, day_type 
        FROM daily_data WHERE user_id = :user_id AND (total_protein > 0 OR total_carbs > 0 OR total_fat > 0 OR calories > 0) 
        ORDER BY record_date DESC
    """
    daily_summary = execute_query(query, {'user_id': user_id}, fetchall=True)
    
    entries = [{'date_formatted': row['record_date'].strftime('%d %b %y'), **row} for row in daily_summary]
    return render_template('diario_alimentare.html', title='Diario Alimentare', entries=entries)
    
@nutrition_bp.route('/dieta', defaults={'date_str': None}, methods=['GET', 'POST'])
@nutrition_bp.route('/dieta/<date_str>', methods=['GET', 'POST'])
@login_required
def dieta(date_str):
    user_id = session['user_id']
    current_date, current_date_str, prev_day, next_day, is_today = _parse_date_or_today(date_str)

    if request.method == 'POST':
        category, message = _handle_dieta_post(user_id, current_date_str)
        if message:
            flash(message, category or 'info')
        return redirect(url_for('nutrition.dieta', date_str=current_date_str))

    diet_log = _fetch_diet_log(user_id, current_date_str)
    food_options = _fetch_food_options(user_id)
    totals = _calculate_diet_totals(diet_log)
    targets_config = _fetch_macro_targets(user_id)
    latest_weight = _latest_weight(user_id)
    target_macros = _calculate_target_macros(latest_weight, targets_config)

    today_data = execute_query('SELECT day_type FROM daily_data WHERE user_id = :uid AND record_date = :rd', {'uid': user_id, 'rd': current_date_str}, fetchone=True)
    current_day_type = today_data['day_type'] if today_data and today_data.get('day_type') else 'ON'

    return render_template(
        'dieta.html',
        title='Dieta',
        diet_log=diet_log,
        totals=totals,
        date_formatted=current_date.strftime('%d %b %y'),
        target_macros=target_macros,
        current_day_type=current_day_type,
        current_date_str=current_date_str,
        prev_day=prev_day,
        next_day=next_day,
        is_today=is_today,
        food_options=food_options,
    )

@nutrition_bp.route('/alimenti', methods=['GET', 'POST'])
@login_required
def alimenti():
    user_id = session['user_id']
    is_superuser = bool(session.get('is_superuser'))
    if request.method == 'POST':
        action = request.form.get('action')
        food_id = request.form.get('food_id')

        if action == 'add':
            name = (request.form.get('name') or '').strip()
            if not name:
                flash('Inserisci un nome valido per l\'alimento.', 'danger')
                return redirect(url_for('nutrition.alimenti'))
            protein = float(request.form.get('protein', 0)); carbs = float(request.form.get('carbs', 0)); fat = float(request.form.get('fat', 0))
            calories = (protein * 4) + (carbs * 4) + (fat * 9)
            try:
                make_global = request.form.get('make_global') == '1' and is_superuser
                owner_id = None if make_global else user_id
                if make_global:
                    duplicate = execute_query('SELECT 1 FROM foods WHERE user_id IS NULL AND LOWER(name) = LOWER(:name)', {'name': name}, fetchone=True)
                    if duplicate:
                        flash(f"Errore: esiste già un alimento globale chiamato '{name}'.", 'danger')
                        return redirect(url_for('nutrition.alimenti'))
                execute_query('INSERT INTO foods (name, protein, carbs, fat, calories, user_id) VALUES (:name, :p, :c, :f, :cal, :uid)',
                              {'name': name, 'p': protein, 'c': carbs, 'f': fat, 'cal': calories, 'uid': owner_id}, commit=True)
                flash(('Alimento globale aggiunto.' if make_global else 'Alimento personale aggiunto.'), 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f"Errore: L'alimento '{name}' esiste già.", 'danger')

        elif action == 'delete':
            is_global = request.form.get('is_global') == '1'
            if is_global and not is_superuser:
                flash('Non sei autorizzato a eliminare questo alimento.', 'danger')
            else:
                params = {'id': food_id}
                condition = 'user_id IS NULL' if is_global else 'user_id = :uid'
                if not is_global:
                    params['uid'] = user_id
                execute_query(f'DELETE FROM foods WHERE id = :id AND {condition}', params, commit=True)
                flash(('Alimento globale eliminato.' if is_global else 'Alimento personale eliminato.'), 'success')

        elif action == 'rename_food':
            new_name = (request.form.get('new_food_name') or '').strip()
            is_global = request.form.get('is_global') == '1'
            if new_name and food_id:
                if is_global and not is_superuser:
                    flash('Non sei autorizzato a rinominare questo alimento.', 'danger')
                    return redirect(url_for('nutrition.alimenti'))
                try:
                    params = {'name': new_name, 'id': food_id}
                    if is_global:
                        duplicate = execute_query('SELECT 1 FROM foods WHERE user_id IS NULL AND LOWER(name) = LOWER(:name) AND id <> :id', {'name': new_name, 'id': food_id}, fetchone=True)
                        if duplicate:
                            flash(f"Errore: esiste già un alimento globale con il nome '{new_name}'.", 'danger')
                            return redirect(url_for('nutrition.alimenti'))
                        query = "UPDATE foods SET name = :name WHERE id = :id AND user_id IS NULL"
                    else:
                        params['uid'] = user_id
                        query = "UPDATE foods SET name = :name WHERE id = :id AND user_id = :uid"
                    execute_query(query, params, commit=True)
                    flash('Alimento rinominato con successo.', 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: Esiste già un alimento con il nome '{new_name}'.", 'danger')
            else:
                flash('Inserisci un nome valido per rinominare l\'alimento.', 'danger')

        if food_id:
            return redirect(url_for('nutrition.alimenti', _anchor=f"food-{food_id}"))
        return redirect(url_for('nutrition.alimenti'))

    foods = execute_query('SELECT * FROM foods WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    return render_template('alimenti.html', title='Database Alimenti', foods=foods, is_superuser=is_superuser)

@nutrition_bp.route('/macros', methods=['GET', 'POST'])
@login_required
def macros():
    user_id = session['user_id']
    latest_weight = _latest_weight(user_id)
    if request.method == 'POST':
        try:
            days_on = int(request.form.get('days_on') or 0)
            days_off = int(request.form.get('days_off') or 0)
            if days_on + days_off > 7:
                flash('La somma dei giorni ON e OFF non può superare 7.', 'danger')
                return redirect(url_for('nutrition.macros'))

            query = """
                INSERT INTO user_macro_targets (user_id, days_on, days_off, p_on, c_on, f_on, p_off, c_off, f_off) 
                VALUES (:uid, :d_on, :d_off, :p_on, :c_on, :f_on, :p_off, :c_off, :f_off) 
                ON CONFLICT(user_id) DO UPDATE SET 
                days_on=excluded.days_on, days_off=excluded.days_off, p_on=excluded.p_on, c_on=excluded.c_on, 
                f_on=excluded.f_on, p_off=excluded.p_off, c_off=excluded.c_off, f_off=excluded.f_off
            """
            params = {
                'uid': user_id,
                'd_on': days_on,
                'd_off': days_off,
                'p_on': float(request.form.get('p_on') or DEFAULT_TARGETS['p_on']),
                'c_on': float(request.form.get('c_on') or DEFAULT_TARGETS['c_on']),
                'f_on': float(request.form.get('f_on') or DEFAULT_TARGETS['f_on']),
                'p_off': float(request.form.get('p_off') or DEFAULT_TARGETS['p_off']),
                'c_off': float(request.form.get('c_off') or DEFAULT_TARGETS['c_off']),
                'f_off': float(request.form.get('f_off') or DEFAULT_TARGETS['f_off']),
            }
            execute_query(query, params, commit=True)
            flash('Obiettivi macro salvati con successo.', 'success')
            return redirect(url_for('nutrition.macros'))
        except (ValueError, TypeError):
            flash('Assicurati di inserire valori numerici validi.', 'danger')
            return redirect(url_for('nutrition.macros'))

    targets = _fetch_macro_targets(user_id)
    calcs = _calculate_macro_overview(latest_weight, targets)

    return render_template('macros.html', title='Macros', targets=targets, latest_weight=latest_weight, calcs=calcs)