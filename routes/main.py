# routes/main.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, date, timedelta
import math
from collections import defaultdict
from .auth import login_required
from utils import execute_query, is_valid_time_format
from services import user_service, data_service # NUOVE IMPORTAZIONI

main_bp = Blueprint('main', __name__)

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
    
    entries_raw = execute_query('SELECT * FROM daily_data WHERE user_id = :user_id ORDER BY record_date DESC', {'user_id': user_id}, fetchall=True)
    all_workouts = execute_query('SELECT DISTINCT record_date, template_name FROM workout_sessions WHERE user_id = :user_id', {'user_id': user_id}, fetchall=True)
    all_cardio = execute_query('SELECT DISTINCT record_date, activity_type FROM cardio_log WHERE user_id = :user_id', {'user_id': user_id}, fetchall=True)

    activities_by_date = defaultdict(set)
    for workout in all_workouts:
        if workout.get('template_name'): activities_by_date[workout['record_date']].add(workout['template_name'])
    for cardio in all_cardio:
        activities_by_date[cardio['record_date']].add(cardio['activity_type'])

    entries = []
    for entry in entries_raw:
        entry_dict = dict(entry)
        record_date = entry['record_date']
        activities = activities_by_date.get(record_date, set())
        entry_dict['workout_info'] = ", ".join(sorted(list(activities)))
        
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
        
    return render_template('generale.html', title='Generale', entries=entries)

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