# routes/main.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_from_directory, current_app
from datetime import datetime, date, timedelta
import math
import re
import statistics
from collections import defaultdict, OrderedDict
from .auth import login_required
from utils import execute_query, is_valid_time_format
from services import user_service, data_service  # NUOVE IMPORTAZIONI
from services import privacy_service

main_bp = Blueprint('main', __name__)


def _prepare_daily_entries(user_id, height_cm, gender, limit):
    entries_raw = execute_query(
        'SELECT * FROM daily_data WHERE user_id = :user_id ORDER BY record_date DESC LIMIT :limit',
        {'user_id': user_id, 'limit': limit},
        fetchall=True,
    ) or []

    date_range = None
    activities_by_date = defaultdict(set)
    if entries_raw:
        date_min = min(entry['record_date'] for entry in entries_raw)
        date_max = max(entry['record_date'] for entry in entries_raw)
        date_range = (date_min, date_max)
        activity_rows = execute_query(
            """
            WITH combined AS (
                SELECT record_date, template_name AS label
                FROM workout_sessions
                WHERE user_id = :user_id
                  AND template_name IS NOT NULL AND template_name <> ''
                  AND record_date BETWEEN :start_date AND :end_date
                UNION ALL
                SELECT record_date, activity_type AS label
                FROM cardio_log
                WHERE user_id = :user_id
                  AND activity_type IS NOT NULL AND activity_type <> ''
                  AND record_date BETWEEN :start_date AND :end_date
            )
            SELECT record_date, label FROM combined
            """,
            {
                'user_id': user_id,
                'start_date': date_min,
                'end_date': date_max,
            },
            fetchall=True,
        ) or []

        for row in activity_rows:
            activities_by_date[row['record_date']].add(row['label'])

    entries = []
    entries_by_date = {}
    for entry in entries_raw:
        entry_dict = dict(entry)
        record_date = entry['record_date']
        activities = activities_by_date.get(record_date, set())
        entry_dict['workout_info'] = ", ".join(sorted(activities))

        if entry.get('bfp_manual') is not None:
            entry_dict['bfp'] = entry['bfp_manual']
        else:
            try:
                entry_dict['bfp'] = None
                if height_cm > 0 and entry.get('waist') and entry.get('neck'):
                    if gender == 'F' and entry.get('hip'):
                        entry_dict['bfp'] = 495 / (1.29579 - 0.35004 * math.log10(entry['waist'] + entry['hip'] - entry['neck']) + 0.22100 * math.log10(height_cm)) - 450
                    elif gender == 'M':
                        entry_dict['bfp'] = 495 / (1.0324 - 0.19077 * math.log10(entry['waist'] - entry['neck']) + 0.15456 * math.log10(height_cm)) - 450
            except (ValueError, TypeError, KeyError):
                entry_dict['bfp'] = None

        try:
            if entry.get('weight') and height_cm > 0:
                height_m = height_cm / 100
                entry_dict['bmi'] = entry['weight'] / (height_m ** 2)
            else:
                entry_dict['bmi'] = None
        except (ValueError, TypeError, KeyError):
            entry_dict['bmi'] = None

        entry_dict['date_formatted'] = record_date.strftime('%d %b %y')
        entries.append(entry_dict)
        entries_by_date[record_date] = entry_dict

    return entries, entries_by_date, date_range

@main_bp.route('/service-worker.js')
def service_worker():
    response = send_from_directory('static', 'service-worker.js', max_age=0)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@main_bp.route('/offline')
def offline():
    return render_template('offline.html', title="Sei Offline")

@main_bp.route('/app-shell')
def app_shell():
    return render_template('app_shell.html', title='Logbook')

@main_bp.route('/home')
@login_required
def home():
    if session.get('is_admin'): return redirect(url_for('admin.admin_generale'))
    return render_template('home.html', title='Home')

@main_bp.route('/impostazioni', methods=['GET', 'POST'])
@login_required
def impostazioni():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'change_password':
            user_service.handle_password_change(user_id, request.form.get('current_password'), request.form.get('new_password'))
            return redirect(url_for('main.impostazioni'))
        
        elif action == 'export_data':
            return data_service.export_user_data(user_id)
        
        elif action == 'delete_account':
            return user_service.handle_account_deletion(user_id, request.form.get('password_confirm'))
        
    return render_template('impostazioni.html', title='Impostazioni')


@main_bp.route('/privacy')
@login_required
def privacy():
    privacy_text = privacy_service.get_privacy_text()
    return render_template('privacy.html', title='Privacy', privacy_text=privacy_text)

@main_bp.route('/utente', methods=['GET', 'POST'])
@login_required
def utente():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_data':
            birth_date = request.form.get("birth_date") or None
            height_str = request.form.get("height")
            
            try:
                height = float(height_str) if height_str else None
            except (ValueError, TypeError):
                flash("Il valore per l'altezza non è un numero valido.", 'danger')
                return redirect(url_for('main.utente'))

            gender = request.form.get("gender")
            
            query = "INSERT INTO user_profile (user_id, birth_date, height, gender) VALUES (:user_id, :birth_date, :height, :gender) ON CONFLICT(user_id) DO UPDATE SET birth_date = EXCLUDED.birth_date, height = EXCLUDED.height, gender = EXCLUDED.gender"
            params = {"user_id": user_id, "birth_date": birth_date, "height": height, "gender": gender}
            execute_query(query, params, commit=True)
            flash("Dati anagrafici aggiornati.", "success")
        return redirect(url_for('main.utente'))

    profile = execute_query('SELECT * FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    return render_template('utente.html', title='Dati Personali', profile=profile or {})

@main_bp.route('/generale')
@login_required
def generale():
    user_id = session['user_id']
    profile = execute_query('SELECT height, gender FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    height_cm = (profile['height'] * 100) if profile and profile.get('height') else 0
    gender = profile['gender'] if profile and profile.get('gender') else 'M'

    limit = current_app.config.get('GENERAL_METRICS_ENTRY_LIMIT', 90)
    entries, entries_by_date, date_range = _prepare_daily_entries(user_id, height_cm, gender, limit)

    analytics_context = {
        'chart_labels': [],
        'chart_datasets': [],
        'metric_summary': [],
        'insights': [],
        'consistency': {
            'labels': [],
            'datasets': [],
        },
        'has_data': bool(entries_by_date),
    }

    if entries_by_date:
        sorted_dates = sorted(entries_by_date.keys())

        def safe_number(value, allow_zero=False):
            try:
                number = float(value)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(number):
                return None
            if not allow_zero and number == 0:
                return None
            return number

        def parse_sleep_value(raw_value):
            if raw_value is None:
                return None
            text = str(raw_value).strip().lower()
            if not text:
                return None
            text = text.replace('ore', 'h').replace(' ', '')
            text = text.replace(',', '.')
            if ':' in text:
                hours_str, minutes_str = text.split(':', 1)
                try:
                    hours = float(hours_str)
                    minutes = float(re.sub(r'[^0-9.]', '', minutes_str) or 0)
                except ValueError:
                    return None
                return round(hours + (minutes / 60.0), 2)

            match = re.findall(r'\d+(?:\.\d+)?', text)
            if not match:
                return None
            hours = float(match[0])
            minutes = 0.0
            if len(match) > 1 and 'm' in text:
                minutes = float(match[1])
            return round(hours + (minutes / 60.0), 2)

        def normalize_series(values):
            cleaned = [v for v in values if v is not None]
            if not cleaned:
                return [None for _ in values], {'mean': None, 'stdev': None}
            if len(cleaned) == 1:
                baseline = cleaned[0]
                return [50 if v is not None else None for v in values], {'mean': baseline, 'stdev': 0.0}
            mean_val = statistics.mean(cleaned)
            stdev_val = statistics.pstdev(cleaned)
            if stdev_val == 0:
                return [50 if v is not None else None for v in values], {'mean': mean_val, 'stdev': 0.0}

            normalized = []
            for value in values:
                if value is None:
                    normalized.append(None)
                    continue
                z_score = (value - mean_val) / stdev_val
                percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
                normalized.append(round(max(0, min(100, percentile * 100)), 1))
            return normalized, {'mean': mean_val, 'stdev': stdev_val}

        def collect_summary(label, values, unit, rounding=1):
            valid = [v for v in values if v is not None]
            if not valid:
                return None
            return {
                'metric': label,
                'avg': round(statistics.mean(valid), rounding),
                'min': round(min(valid), rounding),
                'max': round(max(valid), rounding),
                'unit': unit,
            }

        def pearson(x_values, y_values):
            paired = [(x, y) for x, y in zip(x_values, y_values) if x is not None and y is not None]
            if len(paired) < 2:
                return None
            xs, ys = zip(*paired)
            mean_x = statistics.mean(xs)
            mean_y = statistics.mean(ys)
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in paired)
            denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
            if denominator == 0:
                return None
            return numerator / denominator

        def describe_correlation(metric_label, value):
            if value is None:
                return f"Dati insufficienti per valutare l'impatto di {metric_label}."
            intensity = abs(value)
            if intensity >= 0.7:
                strength = 'forte'
            elif intensity >= 0.4:
                strength = 'moderata'
            elif intensity >= 0.2:
                strength = 'leggera'
            else:
                strength = 'quasi assente'
            trend = 'direttamente proporzionale' if value > 0 else 'inversamente proporzionale'
            return f"{metric_label}: correlazione {strength} {trend} (r = {value:.2f})."

        chart_labels = [date_obj.strftime('%d %b') for date_obj in sorted_dates]

        volume_rows = execute_query(
            """
            SELECT record_date, SUM(weight * reps) AS total_volume
            FROM workout_log
            WHERE user_id = :user_id
              AND record_date BETWEEN :start_date AND :end_date
            GROUP BY record_date
            """,
            {
                'user_id': user_id,
                'start_date': sorted_dates[0],
                'end_date': sorted_dates[-1],
            },
            fetchall=True,
        ) or []
        volume_by_date = {row['record_date']: safe_number(row['total_volume'], allow_zero=True) or 0 for row in volume_rows}

        weight_values = []
        calories_values = []
        protein_values = []
        carbs_values = []
        fat_values = []
        sleep_values = []
        progress_values = []

        for date_obj in sorted_dates:
            entry = entries_by_date.get(date_obj, {})
            weight_values.append(safe_number(entry.get('weight')))
            calories_values.append(safe_number(entry.get('calories')))
            protein_values.append(safe_number(entry.get('total_protein')))
            carbs_values.append(safe_number(entry.get('total_carbs')))
            fat_values.append(safe_number(entry.get('total_fat')))
            sleep_values.append(parse_sleep_value(entry.get('sleep')))
            progress_values.append(volume_by_date.get(date_obj, 0.0))

        datasets = []

        def add_dataset(key, label, values, unit, color, rounding=1):
            normalized, stats = normalize_series(values)
            if all(v is None for v in normalized):
                return
            datasets.append({
                'key': key,
                'label': label,
                'data': normalized,
                'raw': [None if v is None else round(v, rounding) for v in values],
                'unit': unit,
                'color': color,
            })
            summary = collect_summary(label, values, unit, rounding)
            if summary:
                analytics_context['metric_summary'].append(summary)

        add_dataset('progress', 'Progressi Palestra (volume)', progress_values, 'kg × ripetizioni', '#0d6efd', rounding=0)
        add_dataset('peso', 'Peso corporeo', weight_values, 'kg', '#6610f2', rounding=1)
        add_dataset('calorie', 'Calorie totali', calories_values, 'kcal', '#d63384', rounding=0)
        add_dataset('proteine', 'Proteine', protein_values, 'g', '#198754', rounding=1)
        add_dataset('carboidrati', 'Carboidrati', carbs_values, 'g', '#fd7e14', rounding=1)
        add_dataset('grassi', 'Grassi', fat_values, 'g', '#20c997', rounding=1)
        add_dataset('sonno', 'Ore di sonno', sleep_values, 'ore', '#6c757d', rounding=2)

        analytics_context['chart_labels'] = chart_labels
        analytics_context['chart_datasets'] = datasets

        progress_for_corr = [value if value and value > 0 else None for value in progress_values]
        analytics_context['insights'] = [
            describe_correlation('Ore di sonno', pearson(progress_for_corr, sleep_values)),
            describe_correlation('Calorie totali', pearson(progress_for_corr, calories_values)),
            describe_correlation('Peso corporeo', pearson(progress_for_corr, weight_values)),
            describe_correlation('Proteine', pearson(progress_for_corr, protein_values)),
        ]

        measure_dates = set(sorted_dates)
        workout_days_rows = execute_query(
            'SELECT record_date FROM workout_sessions WHERE user_id = :user_id AND record_date BETWEEN :start_date AND :end_date',
            {
                'user_id': user_id,
                'start_date': sorted_dates[0],
                'end_date': sorted_dates[-1],
            },
            fetchall=True,
        ) or []
        workout_dates = {row['record_date'] for row in workout_days_rows}

        cardio_rows = execute_query(
            'SELECT record_date FROM cardio_log WHERE user_id = :user_id AND record_date BETWEEN :start_date AND :end_date',
            {
                'user_id': user_id,
                'start_date': sorted_dates[0],
                'end_date': sorted_dates[-1],
            },
            fetchall=True,
        ) or []
        cardio_dates = {row['record_date'] for row in cardio_rows}

        diet_rows = execute_query(
            'SELECT log_date FROM diet_log WHERE user_id = :user_id AND log_date BETWEEN :start_date AND :end_date',
            {
                'user_id': user_id,
                'start_date': sorted_dates[0],
                'end_date': sorted_dates[-1],
            },
            fetchall=True,
        ) or []
        diet_dates = {row['log_date'] for row in diet_rows}

        full_date_range = [sorted_dates[0] + timedelta(days=offset) for offset in range((sorted_dates[-1] - sorted_dates[0]).days + 1)]
        weekly_data = OrderedDict()

        for current_date in full_date_range:
            week_start = current_date - timedelta(days=current_date.weekday())
            week_bucket = weekly_data.setdefault(
                week_start,
                {'total_days': 0, 'misure': 0, 'palestra': 0, 'corsa': 0, 'dieta': 0},
            )
            week_bucket['total_days'] += 1
            if current_date in measure_dates:
                week_bucket['misure'] += 1
            if current_date in workout_dates:
                week_bucket['palestra'] += 1
            if current_date in cardio_dates:
                week_bucket['corsa'] += 1
            if current_date in diet_dates:
                week_bucket['dieta'] += 1

        consistency_labels = []
        misure_pct = []
        palestra_pct = []
        corsa_pct = []
        dieta_pct = []

        for week_start, data in weekly_data.items():
            week_end = week_start + timedelta(days=6)
            label = f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b')}"
            total_days = data['total_days'] or 1
            consistency_labels.append(label)
            misure_pct.append(round((data['misure'] / total_days) * 100, 1))
            palestra_pct.append(round((data['palestra'] / total_days) * 100, 1))
            corsa_pct.append(round((data['corsa'] / total_days) * 100, 1))
            dieta_pct.append(round((data['dieta'] / total_days) * 100, 1))

        analytics_context['consistency'] = {
            'labels': consistency_labels,
            'datasets': [
                {'label': 'Misure', 'data': misure_pct, 'color': '#0d6efd'},
                {'label': 'Palestra', 'data': palestra_pct, 'color': '#dc3545'},
                {'label': 'Corsa', 'data': corsa_pct, 'color': '#198754'},
                {'label': 'Diario Alimentare', 'data': dieta_pct, 'color': '#fd7e14'},
            ],
        }

    return render_template('generale.html', title='Logbook - Analytics', entries=entries, analytics=analytics_context)


@main_bp.route('/generale/tabella')
@login_required
def generale_tabella():
    user_id = session['user_id']
    profile = execute_query('SELECT height, gender FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    height_cm = (profile['height'] * 100) if profile and profile.get('height') else 0
    gender = profile['gender'] if profile and profile.get('gender') else 'M'

    limit = current_app.config.get('GENERAL_METRICS_ENTRY_LIMIT', 90)
    entries, _, _ = _prepare_daily_entries(user_id, height_cm, gender, limit)

    return render_template('generale_tabella.html', title='Logbook - Generale', entries=entries)

@main_bp.route('/misure', defaults={'date_str': None}, methods=['GET', 'POST'])
@main_bp.route('/misure/<date_str>', methods=['GET', 'POST'])
@login_required
def misure(date_str):
    user_id = session['user_id']
    if date_str:
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        current_date = date.today()

    current_date_str = current_date.strftime('%Y-%m-%d')
    prev_day = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    is_today = (current_date == date.today())
    
    profile = execute_query('SELECT gender FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    gender = profile['gender'] if profile and profile.get('gender') else 'M'

    if request.method == 'POST':
        weight_time = request.form.get('weight_time'); measure_time = request.form.get('measure_time')
        if not is_valid_time_format(weight_time) or not is_valid_time_format(measure_time):
            flash('Formato orario non valido. Usa HH:MM.', 'danger')
            return redirect(url_for('main.misure', date_str=current_date_str))
        
        bfp_mode = request.form.get('bfp-mode-selector')
        try:
            form_data = {
                'weight': float(request.form.get('weight')) if request.form.get('weight') else None,
                'sleep_quality': int(request.form.get('sleep_quality')) if request.form.get('sleep_quality') else None,
                'neck': float(request.form.get('neck')) if bfp_mode == 'formula' and request.form.get('neck') else None,
                'waist': float(request.form.get('waist')) if bfp_mode == 'formula' and request.form.get('waist') else None,
                'hip': float(request.form.get('hip')) if bfp_mode == 'formula' and request.form.get('hip') else None,
                'bfp_manual': float(request.form.get('bfp_manual')) if bfp_mode == 'manual' and request.form.get('bfp_manual') else None,
                'weight_time': weight_time or None,
                'sleep': request.form.get('sleep') or None,
                'measure_time': measure_time if bfp_mode == 'formula' else None
            }
        except (ValueError, TypeError):
             flash('Inserisci solo valori numerici validi.', 'danger')
             return redirect(url_for('main.misure', date_str=current_date_str))

        query = "INSERT INTO daily_data (user_id, record_date, weight, weight_time, sleep, sleep_quality, neck, waist, hip, measure_time, bfp_manual) VALUES (:user_id, :record_date, :weight, :weight_time, :sleep, :sleep_quality, :neck, :waist, :hip, :measure_time, :bfp_manual) ON CONFLICT(user_id, record_date) DO UPDATE SET weight=excluded.weight, weight_time=excluded.weight_time, sleep=excluded.sleep, sleep_quality=excluded.sleep_quality, neck=excluded.neck, waist=excluded.waist, hip=excluded.hip, measure_time=excluded.measure_time, bfp_manual=excluded.bfp_manual"
        params = {'user_id': user_id, 'record_date': current_date_str, **form_data}
        execute_query(query, params, commit=True)
        flash('Misure salvate con successo.', 'success')
        return redirect(url_for('main.generale'))
    
    misure_giorno = execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date', {'user_id': user_id, 'date': current_date_str}, fetchone=True)
    return render_template('misure.html', title='Misure', date_formatted=current_date.strftime('%d %b %y'), misure=misure_giorno or {}, prev_day=prev_day, next_day=next_day, is_today=is_today, current_date_str=current_date_str, gender=gender)

@main_bp.route('/note', methods=['GET', 'POST'])
@login_required
def note():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_personal':
            content = request.form.get('personal_note')
            query = "INSERT INTO user_notes (user_id, content) VALUES (:user_id, :content) ON CONFLICT(user_id) DO UPDATE SET content = EXCLUDED.content"
            execute_query(query, {'user_id': user_id, 'content': content}, commit=True)
            flash('Nota personale salvata.', 'success')
        elif action == 'save_shared':
            content = request.form.get('shared_note')
            query = "INSERT INTO user_notes (user_id, content_shared) VALUES (:user_id, :content) ON CONFLICT(user_id) DO UPDATE SET content_shared = EXCLUDED.content_shared"
            execute_query(query, {'user_id': user_id, 'content': content}, commit=True)
            flash('Nota per l\'admin salvata.', 'success')
        return redirect(url_for('main.note'))
    
    note_data = execute_query('SELECT content, content_shared FROM user_notes WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    return render_template('note.html', title='Note', note=note_data or {})

@main_bp.route('/modifica_misure/<record_date>', methods=['GET', 'POST'])
@login_required
def modifica_misure(record_date):
    user_id = session['user_id']
    misure = execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date', {'user_id': user_id, 'date': record_date}, fetchone=True)
    if not misure:
        flash("Nessuna misurazione trovata per questa data.", "warning")
        return redirect(url_for('main.generale'))

    profile = execute_query('SELECT gender FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    gender = profile['gender'] if profile and profile.get('gender') else 'M'
    date_obj = datetime.strptime(record_date, '%Y-%m-%d').date()
    date_formatted = date_obj.strftime('%d %b %y')

    if request.method == 'POST':
        # Logica di salvataggio identica alla rotta 'misure'
        weight_time = request.form.get('weight_time'); measure_time = request.form.get('measure_time')
        if not is_valid_time_format(weight_time) or not is_valid_time_format(measure_time):
            flash('Formato orario non valido. Usa HH:MM.', 'danger')
            return render_template('modifica_misure.html', title=f'Modifica {date_formatted}', misure=misure, date_formatted=date_formatted, gender=gender)
        
        bfp_mode = request.form.get('bfp-mode-selector')
        try:
            form_data = {
                'weight': float(request.form.get('weight')) if request.form.get('weight') else None,
                'sleep_quality': int(request.form.get('sleep_quality')) if request.form.get('sleep_quality') else None,
                'neck': float(request.form.get('neck')) if bfp_mode == 'formula' and request.form.get('neck') else None,
                'waist': float(request.form.get('waist')) if bfp_mode == 'formula' and request.form.get('waist') else None,
                'hip': float(request.form.get('hip')) if bfp_mode == 'formula' and request.form.get('hip') else None,
                'bfp_manual': float(request.form.get('bfp_manual')) if bfp_mode == 'manual' and request.form.get('bfp_manual') else None,
                'weight_time': weight_time or None,
                'sleep': request.form.get('sleep') or None,
                'measure_time': measure_time if bfp_mode == 'formula' else None
            }
        except (ValueError, TypeError):
             flash('Inserisci solo valori numerici validi.', 'danger')
             return redirect(url_for('main.modifica_misure', record_date=record_date))

        query = "UPDATE daily_data SET weight=:weight, weight_time=:weight_time, sleep=:sleep, sleep_quality=:sleep_quality, neck=:neck, waist=:waist, hip=:hip, measure_time=:measure_time, bfp_manual=:bfp_manual WHERE user_id=:user_id AND record_date=:record_date"
        params = {'user_id': user_id, 'record_date': record_date, **form_data}
        execute_query(query, params, commit=True)
        flash('Misure aggiornate con successo.', 'success')
        return redirect(url_for('main.generale'))
    
    return render_template('modifica_misure.html', title=f'Modifica {date_formatted}', misure=misure, date_formatted=date_formatted, gender=gender)

@main_bp.route('/elimina_giorno', methods=['POST'])
@login_required
def elimina_giorno():
    date_to_delete = request.form.get('date')
    user_id = session['user_id']
    success, message = data_service.delete_all_day_data(user_id, date_to_delete)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('main.generale'))

@main_bp.route('/allenamento')
@login_required
def allenamento():
    return render_template('allenamento.html', title='Allenamento')