# routes/nutrition.py
from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash, jsonify
from datetime import date, datetime, timedelta
from .auth import login_required
from utils import execute_query
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from extensions import db
from services.suggestion_service import get_catalog_suggestions, resolve_catalog_item

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


def _format_number(value):
    if value is None:
        return '0'
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _format_total(tracker, amount):
    amount = amount or 0
    if tracker['key'] == 'water':
        if amount <= 0:
            return '0 ml'
        liters = amount / 1000
        liters_label = f" ({liters:.2f} L)" if amount >= 1000 else ''
        return f"{int(round(amount))} ml{liters_label}"
    if tracker['key'] == 'coffee':
        cups = _format_number(amount)
        label = tracker.get('unit_singular', 'tazza') if float(amount) == 1 else tracker.get('unit_plural', 'tazze')
        return f"{cups} {label}"
    if tracker['key'] == 'supplements':
        doses = _format_number(amount)
        label = tracker.get('unit_singular', 'dose') if float(amount) == 1 else tracker.get('unit_plural', 'dosi')
        return f"{doses} {label}"
    return f"{_format_number(amount)} {tracker['unit']}"


def _format_entry_amount(tracker, amount):
    amount = amount or 0
    if tracker['key'] == 'water':
        return f"{int(round(amount))} ml"
    if tracker['key'] == 'coffee':
        cups = _format_number(amount)
        label = tracker.get('unit_singular', 'tazza') if float(amount) == 1 else tracker.get('unit_plural', 'tazze')
        return f"{cups} {label}"
    if tracker['key'] == 'supplements':
        doses = _format_number(amount)
        label = tracker.get('unit_singular', 'dose') if float(amount) == 1 else tracker.get('unit_plural', 'dosi')
        return f"{doses} {label}"
    return f"{_format_number(amount)} {tracker['unit']}"


def _format_quick_label(value, singular, plural):
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = 0
    label = singular if abs(numeric_value) == 1 else plural
    display_value = _format_number(numeric_value)
    return f"+{display_value} {label}"

def update_daily_totals(user_id, date_str):
    totals_query = """
        SELECT SUM(protein) as p, SUM(carbs) as c, SUM(fat) as f, SUM(calories) as cal 
        FROM diet_log WHERE user_id = :user_id AND log_date = :date_str
    """
    totals = execute_query(totals_query, {'user_id': user_id, 'date_str': date_str}, fetchone=True)
    
    total_protein = totals['p'] or 0; total_carbs = totals['c'] or 0
    total_fat = totals['f'] or 0; total_calories = totals['cal'] or 0
    
    upsert_query = """
        INSERT INTO daily_data (user_id, record_date, total_protein, total_carbs, total_fat, calories) 
        VALUES (:user_id, :date_str, :tp, :tc, :tf, :cal)
        ON CONFLICT(user_id, record_date) DO UPDATE SET 
        total_protein = EXCLUDED.total_protein, total_carbs = EXCLUDED.total_carbs, 
        total_fat = EXCLUDED.total_fat, calories = EXCLUDED.calories
    """
    execute_query(upsert_query, {'user_id': user_id, 'date_str': date_str, 'tp': total_protein, 'tc': total_carbs, 'tf': total_fat, 'cal': total_calories}, commit=True)

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
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return redirect(url_for('nutrition.tracking'))
    else:
        current_date = date.today()

    current_date_str = current_date.strftime('%Y-%m-%d')
    prev_day = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    is_today = current_date == date.today()

    if request.method == 'POST':
        action = request.form.get('action', 'add_entry')
        if action == 'delete_entry':
            entry_id = request.form.get('entry_id')
            if entry_id:
                execute_query(
                    'DELETE FROM intake_log WHERE id = :id AND user_id = :uid',
                    {'id': entry_id, 'uid': user_id},
                    commit=True,
                )
        else:
            tracker_key = request.form.get('tracker_type')
            tracker = TRACKER_LOOKUP.get(tracker_key)
            if not tracker:
                flash('Tracker non valido.', 'danger')
                return redirect(url_for('nutrition.tracking', date_str=current_date_str))

            quick_amount = request.form.get('quick_amount')
            amount_value = request.form.get('amount')
            try:
                amount = float(quick_amount or amount_value or 0)
            except (ValueError, TypeError):
                amount = 0

            if amount <= 0:
                flash('Inserisci una quantità valida.', 'danger')
                return redirect(url_for('nutrition.tracking', date_str=current_date_str))

            note = (request.form.get('note') or '').strip()
            execute_query(
                'INSERT INTO intake_log (user_id, record_date, tracker_type, amount, unit, note) VALUES (:uid, :rd, :tt, :amt, :unit, :note)',
                {
                    'uid': user_id,
                    'rd': current_date_str,
                    'tt': tracker_key,
                    'amt': amount,
                    'unit': tracker['unit'],
                    'note': note or None,
                },
                commit=True,
            )

        return redirect(url_for('nutrition.tracking', date_str=current_date_str))

    rows = execute_query(
        'SELECT id, tracker_type, amount, unit, note, created_at FROM intake_log WHERE user_id = :uid AND record_date = :rd ORDER BY created_at DESC',
        {'uid': user_id, 'rd': current_date_str},
        fetchall=True,
    ) or []

    totals = {tracker['key']: 0 for tracker in TRACKER_DEFINITIONS}
    grouped_entries = {tracker['key']: [] for tracker in TRACKER_DEFINITIONS}

    for row in rows:
        tracker = TRACKER_LOOKUP.get(row['tracker_type'])
        if not tracker:
            continue
        totals[row['tracker_type']] += row['amount']
        created_at = row['created_at']
        time_label = created_at.strftime('%H:%M') if created_at else ''
        grouped_entries[row['tracker_type']].append(
            {
                'id': row['id'],
                'amount_label': _format_entry_amount(tracker, row['amount']),
                'note': row['note'],
                'time_label': time_label,
            }
        )

    tracker_cards = []
    for tracker in TRACKER_DEFINITIONS:
        unit_singular = tracker.get('unit_singular', tracker['unit'])
        unit_plural = tracker.get('unit_plural', tracker['unit'])
        quick_buttons = [
            {
                'value': quick,
                'label': _format_quick_label(quick, unit_singular, unit_plural),
            }
            for quick in tracker.get('quick_add', [])
        ]

        tracker_cards.append(
            {
                **tracker,
                'unit_singular': unit_singular,
                'unit_plural': unit_plural,
                'quick_buttons': quick_buttons,
                'entries': grouped_entries.get(tracker['key'], []),
                'total_label': _format_total(tracker, totals.get(tracker['key'])),
            }
        )

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
    if date_str:
        try: current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError: return redirect(url_for('nutrition.dieta'))
    else: current_date = date.today()
        
    current_date_str = current_date.strftime('%Y-%m-%d'); prev_day = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (current_date + timedelta(days=1)).strftime('%Y-%m-%d'); is_today = (current_date == date.today())
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_food':
            food_data = resolve_catalog_item(
                'foods',
                user_id,
                entry_id=request.form.get('food_id'),
                name=request.form.get('food_name'),
            )
            try: weight = float(request.form.get('weight', 0))
            except (ValueError, TypeError): weight = 0

            if food_data and weight > 0:
                factor = weight / food_data['ref_weight']
                protein = food_data['protein'] * factor; carbs = food_data['carbs'] * factor; fat = food_data['fat'] * factor
                calories = (protein * 4) + (carbs * 4) + (fat * 9)
                execute_query('INSERT INTO diet_log (user_id, food_id, weight, protein, carbs, fat, calories, log_date) VALUES (:uid, :fid, :w, :p, :c, :f, :cal, :ld)',
                              {'uid': user_id, 'fid': food_data['id'], 'w': weight, 'p': protein, 'c': carbs, 'f': fat, 'cal': calories, 'ld': current_date_str}, commit=True)
                update_daily_totals(user_id, current_date_str)
            else:
                flash('Seleziona un alimento valido dall\'archivio e inserisci un peso maggiore di zero.', 'danger')

        elif action == 'delete_entry':
            entry_id = request.form.get('entry_id')
            execute_query('DELETE FROM diet_log WHERE id = :id AND user_id = :uid', {'id': entry_id, 'uid': user_id}, commit=True)
            update_daily_totals(user_id, current_date_str)
        
        elif action == 'set_day_type':
            day_type = request.form.get('day_type')
            query = """
                INSERT INTO daily_data (user_id, record_date, day_type) VALUES (:uid, :rd, :dt)
                ON CONFLICT(user_id, record_date) DO UPDATE SET day_type = EXCLUDED.day_type
            """
            execute_query(query, {'uid': user_id, 'rd': current_date_str, 'dt': day_type}, commit=True)
        
        return redirect(url_for('nutrition.dieta', date_str=current_date_str))

    diet_log = execute_query('SELECT dl.id, f.name as food_name, f.user_id, dl.weight, dl.protein, dl.carbs, dl.fat, dl.calories FROM diet_log dl JOIN foods f ON dl.food_id = f.id WHERE dl.user_id = :uid AND dl.log_date = :ld',
                             {'uid': user_id, 'ld': current_date_str}, fetchall=True)
    
    totals = {'protein': sum(item['protein'] for item in diet_log), 'carbs': sum(item['carbs'] for item in diet_log), 'fat': sum(item['fat'] for item in diet_log), 'calories': sum(item['calories'] for item in diet_log)}
    targets_row = execute_query('SELECT * FROM user_macro_targets WHERE user_id = :uid', {'uid': user_id}, fetchone=True)
    targets_config = dict(targets_row) if targets_row else {'p_on': 1.8, 'c_on': 5.0, 'f_on': 0.55, 'p_off': 1.8, 'c_off': 3.0, 'f_off': 0.70}
    latest_weight_data = execute_query('SELECT weight FROM daily_data WHERE user_id = :uid AND weight IS NOT NULL ORDER BY record_date DESC LIMIT 1', {'uid': user_id}, fetchone=True)
    latest_weight = latest_weight_data['weight'] if latest_weight_data else 0
    target_macros = {'on': {'p': 0, 'c': 0, 'f': 0}, 'off': {'p': 0, 'c': 0, 'f': 0}}
    if latest_weight > 0:
        target_macros['on']['p'] = targets_config['p_on'] * latest_weight; target_macros['on']['c'] = targets_config['c_on'] * latest_weight; target_macros['on']['f'] = targets_config['f_on'] * latest_weight
        target_macros['off']['p'] = targets_config['p_off'] * latest_weight; target_macros['off']['c'] = targets_config['c_off'] * latest_weight; target_macros['off']['f'] = targets_config['f_off'] * latest_weight
    
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

        # NUOVA LOGICA: Rinomina Alimento
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
    latest_weight_data = execute_query('SELECT weight FROM daily_data WHERE user_id = :uid AND weight IS NOT NULL ORDER BY record_date DESC LIMIT 1', {'uid': user_id}, fetchone=True)
    latest_weight = latest_weight_data['weight'] if latest_weight_data else 0
    if request.method == 'POST':
        try:
            days_on = int(request.form.get('days_on') or 0); days_off = int(request.form.get('days_off') or 0)
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
                'uid': user_id, 'd_on': days_on, 'd_off': days_off,
                'p_on': float(request.form.get('p_on') or 1.8), 'c_on': float(request.form.get('c_on') or 5.0), 'f_on': float(request.form.get('f_on') or 0.55),
                'p_off': float(request.form.get('p_off') or 1.8), 'c_off': float(request.form.get('c_off') or 3.0), 'f_off': float(request.form.get('f_off') or 0.70)
            }
            execute_query(query, params, commit=True)
            flash('Obiettivi macro salvati con successo.', 'success')
            return redirect(url_for('nutrition.macros'))
        except (ValueError, TypeError):
            flash('Assicurati di inserire valori numerici validi.', 'danger')
            return redirect(url_for('nutrition.macros'))
            
    targets_row = execute_query('SELECT * FROM user_macro_targets WHERE user_id = :uid', {'uid': user_id}, fetchone=True)
    targets = dict(targets_row) if targets_row else {'days_on': 3, 'days_off': 4, 'p_on': 1.8, 'c_on': 5.0, 'f_on': 0.55, 'p_off': 1.8, 'c_off': 3.0, 'f_off': 0.70}
    
    calcs = {
        'p_on_g': 0, 'c_on_g': 0, 'f_on_g': 0, 'cal_on': 0,
        'p_off_g': 0, 'c_off_g': 0, 'f_off_g': 0, 'cal_off': 0,
        'weekly_cal': 0, 'avg_daily_cal': 0, 'cg_ratio': 0
    }

    if latest_weight > 0:
        calcs['p_on_g'] = targets['p_on'] * latest_weight
        calcs['c_on_g'] = targets['c_on'] * latest_weight
        calcs['f_on_g'] = targets['f_on'] * latest_weight
        calcs['cal_on'] = (calcs['p_on_g'] * 4) + (calcs['c_on_g'] * 4) + (calcs['f_on_g'] * 9)
        calcs['p_off_g'] = targets['p_off'] * latest_weight
        calcs['c_off_g'] = targets['c_off'] * latest_weight
        calcs['f_off_g'] = targets['f_off'] * latest_weight
        calcs['cal_off'] = (calcs['p_off_g'] * 4) + (calcs['c_off_g'] * 4) + (calcs['f_off_g'] * 9)
        calcs['weekly_cal'] = (calcs['cal_on'] * targets['days_on']) + (calcs['cal_off'] * targets['days_off'])
        total_days = targets['days_on'] + targets['days_off']
        if total_days > 0:
            calcs['avg_daily_cal'] = calcs['weekly_cal'] / 7
        weekly_carbs = (calcs['c_on_g'] * targets['days_on']) + (calcs['c_off_g'] * targets['days_off'])
        weekly_fat = (calcs['f_on_g'] * targets['days_on']) + (calcs['f_off_g'] * targets['days_off'])
        if weekly_fat > 0:
            calcs['cg_ratio'] = weekly_carbs / weekly_fat
    
    return render_template('macros.html', title='Macros', targets=targets, latest_weight=latest_weight, calcs=calcs)