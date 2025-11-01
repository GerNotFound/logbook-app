# routes/gym.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from datetime import date, datetime, timedelta
from collections import defaultdict
from .auth import login_required
from utils import execute_query
from sqlalchemy.exc import IntegrityError
from extensions import db
from services.workout_service import get_templates_with_history, get_session_log_data
from services.suggestion_service import get_catalog_suggestions, resolve_catalog_item

gym_bp = Blueprint('gym', __name__)

# --- ENDPOINT API PER AJAX ---

@gym_bp.route('/api/suggest/exercises')
@login_required
def suggest_exercises():
    user_id = session['user_id']
    search_term = (request.args.get('q') or '').strip()
    suggestions = get_catalog_suggestions('exercises', user_id, search_term)
    return jsonify({'results': suggestions})

# --- ROTTE TRADIZIONALI ---

@gym_bp.route('/palestra')
@login_required
def palestra():
    return render_template('palestra.html', title='Palestra')

@gym_bp.route('/esercizi', methods=['GET', 'POST'])
@login_required
def esercizi():
    user_id = session['user_id']
    is_superuser = bool(session.get('is_superuser'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_exercise':
            name = (request.form.get('name') or '').strip()
            notes = request.form.get('notes')
            if name:
                try:
                    make_global = request.form.get('make_global') == '1' and is_superuser
                    owner_id = None if make_global else user_id
                    if make_global and execute_query('SELECT 1 FROM exercises WHERE user_id IS NULL AND LOWER(name) = LOWER(:name)', {'name': name}, fetchone=True):
                        flash(f"Errore: esiste già un esercizio globale chiamato '{name}'.", 'danger')
                        return redirect(url_for('gym.esercizi'))
                    
                    new_exercise_query = 'INSERT INTO exercises (name, user_id) VALUES (:name, :user_id) RETURNING id'
                    result = execute_query(new_exercise_query, {'name': name, 'user_id': owner_id}, fetchone=True, commit=True)
                    new_exercise_id = result['id']
                    
                    if new_exercise_id and notes:
                        notes_query = "INSERT INTO user_exercise_notes (user_id, exercise_id, notes) VALUES (:user_id, :eid, :notes)"
                        execute_query(notes_query, {'user_id': user_id, 'eid': new_exercise_id, 'notes': notes}, commit=True)
                    
                    flash(('Esercizio globale aggiunto.' if make_global else 'Esercizio personale aggiunto.'), 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: L'esercizio '{name}' esiste già.", 'danger')
            else:
                flash("Inserisci un nome valido per l'esercizio.", 'danger')
        elif action == 'update_notes':
            exercise_id = request.form.get('exercise_id')
            notes = request.form.get('notes')
            query = "INSERT INTO user_exercise_notes (user_id, exercise_id, notes) VALUES (:uid, :eid, :notes) ON CONFLICT(user_id, exercise_id) DO UPDATE SET notes = EXCLUDED.notes"
            execute_query(query, {'uid': user_id, 'eid': exercise_id, 'notes': notes}, commit=True)
            flash('Nota aggiornata.', 'success')
        elif action == 'delete_exercise':
            exercise_id = request.form.get('exercise_id')
            is_global = request.form.get('is_global') == '1'
            if is_global and not is_superuser:
                flash('Non sei autorizzato a eliminare questo esercizio.', 'danger')
            else:
                params = {'id': exercise_id}
                condition = 'user_id IS NULL' if is_global else 'user_id = :uid'
                if not is_global: params['uid'] = user_id
                execute_query(f'DELETE FROM exercises WHERE id = :id AND {condition}', params, commit=True)
                flash('Esercizio eliminato.', 'success')
        elif action == 'rename_exercise':
            exercise_id = request.form.get('exercise_id')
            new_name = (request.form.get('new_exercise_name') or '').strip()
            is_global = request.form.get('is_global') == '1'
            if new_name:
                if is_global and not is_superuser:
                    flash('Non autorizzato.', 'danger')
                else:
                    try:
                        params = {'name': new_name, 'id': exercise_id}
                        if is_global:
                            query = "UPDATE exercises SET name = :name WHERE id = :id AND user_id IS NULL"
                        else:
                            params['uid'] = user_id
                            query = "UPDATE exercises SET name = :name WHERE id = :id AND user_id = :uid"
                        execute_query(query, params, commit=True)
                        flash('Esercizio rinominato.', 'success')
                    except IntegrityError:
                        db.session.rollback()
                        flash(f"Errore: Esiste già un esercizio con il nome '{new_name}'.", 'danger')
        return redirect(url_for('gym.esercizi'))

    query = "SELECT e.id, e.name, e.user_id, uen.notes FROM exercises e LEFT JOIN user_exercise_notes uen ON e.id = uen.exercise_id AND uen.user_id = :user_id WHERE e.user_id IS NULL OR e.user_id = :user_id ORDER BY e.name"
    exercises = execute_query(query, {'user_id': user_id}, fetchall=True)
    return render_template('esercizi.html', title='Esercizi', exercises=exercises, is_superuser=is_superuser)

@gym_bp.route('/scheda', methods=['GET', 'POST'])
@login_required
def scheda():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_template':
            name = request.form.get('template_name')
            if name:
                try:
                    execute_query('INSERT INTO workout_templates (user_id, name) VALUES (:uid, :name)', {'uid': user_id, 'name': name}, commit=True)
                    flash('Scheda creata con successo.', 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: Una scheda con il nome '{name}' esiste già.", 'danger')
        elif action == 'delete_template':
            template_id = request.form.get('template_id')
            execute_query('DELETE FROM workout_templates WHERE id = :id AND user_id = :uid', {'id': template_id, 'uid': user_id}, commit=True)
            flash('Scheda eliminata con successo.', 'success')
        return redirect(url_for('gym.scheda'))

    templates_raw = execute_query('SELECT * FROM workout_templates WHERE user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    templates = [dict(t) for t in templates_raw]
    template_ids = [t['id'] for t in templates]

    if template_ids:
        exercises_query = """
            SELECT te.id, te.template_id, e.name, e.user_id, te.sets 
            FROM template_exercises te 
            JOIN exercises e ON te.exercise_id = e.id 
            WHERE te.template_id = ANY(:tids) 
            ORDER BY te.display_order, te.id
        """
        all_exercises = execute_query(exercises_query, {'tids': template_ids}, fetchall=True)
        
        exercises_by_template = defaultdict(list)
        for ex in all_exercises:
            exercises_by_template[ex['template_id']].append(dict(ex))
        
        for t in templates:
            t['exercises'] = exercises_by_template[t['id']]
    
    return render_template('scheda.html', title='Scheda Allenamento', templates=templates)

@gym_bp.route('/scheda/<int:template_id>/modifica_scheda', methods=['GET', 'POST'])
@login_required
def modifica_scheda_dettaglio(template_id):
    user_id = session['user_id']
    
    template = execute_query('SELECT * FROM workout_templates WHERE id = :id AND user_id = :uid', {'id': template_id, 'uid': user_id}, fetchone=True)
    if not template:
        flash('Scheda non trovata o non autorizzata.', 'danger')
        return redirect(url_for('gym.scheda'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save_all':
            # Salva il nuovo nome della scheda
            new_template_name = (request.form.get('new_template_name') or '').strip()
            if new_template_name and new_template_name != template['name']:
                try:
                    execute_query('UPDATE workout_templates SET name = :name WHERE id = :id AND user_id = :uid', {'name': new_template_name, 'id': template_id, 'uid': user_id}, commit=True)
                    flash('Scheda rinominata.', 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: Esiste già una scheda con il nome '{new_template_name}'.", 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_id=template_id))

            # Aggiorna serie e ordine degli esercizi
            exercise_ids_order = request.form.getlist('exercise_order')
            for index, exercise_id in enumerate(exercise_ids_order):
                sets = request.form.get(f'sets_{exercise_id}', '1')
                execute_query(
                    'UPDATE template_exercises SET sets = :sets, display_order = :order WHERE id = :id AND template_id = :tid',
                    {'sets': sets, 'order': index, 'id': exercise_id, 'tid': template_id},
                    commit=True
                )
            flash('Modifiche alla scheda salvate con successo.', 'success')

        elif action == 'add_exercise_to_template':
            exercise_id = request.form.get('exercise_id')
            if exercise_id:
                max_order = execute_query('SELECT MAX(display_order) as max_o FROM template_exercises WHERE template_id = :tid', {'tid': template_id}, fetchone=True)
                new_order = (max_order['max_o'] or -1) + 1
                execute_query('INSERT INTO template_exercises (template_id, exercise_id, sets, display_order) VALUES (:tid, :eid, :sets, :order)',
                              {'tid': template_id, 'eid': exercise_id, 'sets': '1', 'order': new_order}, commit=True)
                flash('Esercizio aggiunto.', 'success')
            else:
                flash('Nessun esercizio selezionato.', 'danger')

        elif action == 'delete_template_exercise':
            template_exercise_id = request.form.get('template_exercise_id')
            execute_query('DELETE FROM template_exercises WHERE id = :id AND template_id = :tid', {'id': template_exercise_id, 'tid': template_id}, commit=True)
            flash('Esercizio rimosso dalla scheda.', 'success')
            
        return redirect(url_for('gym.modifica_scheda_dettaglio', template_id=template_id))

    current_exercises = execute_query('SELECT te.id, e.name, te.sets FROM template_exercises te JOIN exercises e ON te.exercise_id = e.id WHERE te.template_id = :tid ORDER BY te.display_order, te.id', {'tid': template_id}, fetchall=True)
    all_exercises = execute_query('SELECT id, name, user_id FROM exercises WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)

    return render_template('modifica_scheda.html', 
                           title=f'Modifica {template["name"]}', 
                           template=template, 
                           current_exercises=current_exercises, 
                           all_exercises=all_exercises)

@gym_bp.route('/esercizio/<int:exercise_id>/info')
@login_required
def esercizio_info(exercise_id):
    user_id = session['user_id']
    exercise = execute_query(
        'SELECT * FROM exercises WHERE id = :id AND (user_id IS NULL OR user_id = :uid)', 
        {'id': exercise_id, 'uid': user_id}, 
        fetchone=True
    )
    if not exercise:
        flash('Esercizio non trovato.', 'danger')
        return redirect(url_for('gym.esercizi'))
    
    return render_template('esercizio_info.html', title=exercise['name'], exercise=exercise)


@gym_bp.route('/esercizio/<int:exercise_id>')
@login_required
def esercizio_dettaglio(exercise_id):
    user_id = session['user_id']
    exercise = execute_query('SELECT * FROM exercises WHERE id = :id', {'id': exercise_id}, fetchone=True)
    if not exercise:
        return redirect(url_for('gym.esercizi'))

    query = "SELECT wl.record_date, wl.session_timestamp, wl.set_number, wl.reps, wl.weight FROM workout_log wl WHERE wl.user_id = :user_id AND wl.exercise_id = :eid ORDER BY wl.record_date DESC, wl.session_timestamp DESC, wl.id ASC"
    history_raw = execute_query(query, {'user_id': user_id, 'eid': exercise_id}, fetchall=True)

    sessions = defaultdict(lambda: {'date_formatted': '', 'sets': []})
    for row in history_raw:
        ts = row['session_timestamp']
        if not sessions[ts]['date_formatted']:
            sessions[ts]['date_formatted'] = row['record_date'].strftime('%d %b %y')
        sessions[ts]['sets'].append(dict(row))

    return render_template('esercizio_dettaglio.html', title=f"Progressione - {exercise['name']}", exercise=exercise, sessions=sessions)

@gym_bp.route('/sessione_palestra', defaults={'date_param': None}, methods=['GET', 'POST'])
@gym_bp.route('/sessione_palestra/<date_param>', methods=['GET', 'POST'])
@gym_bp.route('/sessione_palestra/<date_param>/<session_ts>', methods=['GET', 'POST'])
@login_required
def sessione_palestra(date_param, session_ts=None):
    user_id = session['user_id']
    if date_param:
        try: current_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError: current_date = date.today()
    else: current_date = date.today()

    record_date = current_date.strftime('%Y-%m-%d'); date_formatted = current_date.strftime('%d %b %y')
    prev_day = (current_date - timedelta(days=1)).strftime('%Y-%m-%d'); next_day = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    is_today = (current_date == date.today())

    if request.method == 'POST':
        session_timestamp = session_ts if session_ts else datetime.now().strftime('%Y%m%d%H%M%S')
        template_name = request.form.get('template_name', 'Allenamento Libero')
        start_timestamp_ms = request.form.get('start_timestamp')
        manual_duration_value = (request.form.get('duration_minutes_manual') or '').strip()
        duration_minutes = None
        if manual_duration_value:
            try:
                manual_duration = int(manual_duration_value)
                if manual_duration >= 0: duration_minutes = manual_duration
            except (ValueError, TypeError):
                manual_duration = None
        if duration_minutes is None:
            duration_minutes = 0
            if start_timestamp_ms:
                try:
                    start_time = datetime.fromtimestamp(int(start_timestamp_ms) / 1000)
                    duration_minutes = max(0, int((datetime.now() - start_time).total_seconds() / 60))
                except (ValueError, TypeError): pass
        session_note = (request.form.get('session_note') or '').strip()
        session_rating_value = (request.form.get('session_rating') or '').strip()
        session_rating = None
        if session_rating_value:
            try:
                parsed_rating = int(session_rating_value)
                if 1 <= parsed_rating <= 10: session_rating = parsed_rating
            except (ValueError, TypeError):
                parsed_rating = None
        session_query = "INSERT INTO workout_sessions (user_id, session_timestamp, record_date, template_name, duration_minutes, session_note, session_rating) VALUES (:uid, :ts, :rd, :tn, :dur, :note, :rating) ON CONFLICT(session_timestamp) DO UPDATE SET template_name = EXCLUDED.template_name, duration_minutes = EXCLUDED.duration_minutes, session_note = EXCLUDED.session_note, session_rating = EXCLUDED.session_rating"
        execute_query(session_query, {'uid': user_id, 'ts': session_timestamp, 'rd': record_date, 'tn': template_name, 'dur': duration_minutes, 'note': session_note or None, 'rating': session_rating}, commit=True)
        if session_ts:
            execute_query('DELETE FROM workout_log WHERE user_id = :user_id AND session_timestamp = :ts', {'user_id': user_id, 'ts': session_ts}, commit=True)
            execute_query('DELETE FROM workout_session_comments WHERE user_id = :user_id AND session_timestamp = :ts', {'user_id': user_id, 'ts': session_ts}, commit=True)
        latest_weight_data = execute_query('SELECT weight FROM daily_data WHERE user_id = :user_id AND weight IS NOT NULL ORDER BY record_date DESC LIMIT 1', {'user_id': user_id}, fetchone=True)
        latest_weight = latest_weight_data['weight'] if latest_weight_data else 0
        has_data = False
        for key, reps_str in request.form.items():
            if key.startswith('reps_'):
                if not reps_str: continue
                parts = key.split('_'); exercise_id = int(parts[1]); set_number = int(parts[2])
                weight_str = request.form.get(f'weight_{exercise_id}_{set_number}', '').lower()
                final_weight = latest_weight if weight_str in ['io', 'me'] and latest_weight > 0 else 0
                if weight_str not in ['io', 'me']:
                    try: final_weight = float(weight_str)
                    except (ValueError, TypeError): final_weight = 0
                try: final_reps = int(reps_str)
                except (ValueError, TypeError): final_reps = 0
                if final_reps > 0 and final_weight >= 0:
                    has_data = True
                    execute_query('INSERT INTO workout_log (user_id, exercise_id, record_date, session_timestamp, set_number, reps, weight) VALUES (:uid, :eid, :rd, :ts, :set, :reps, :w)', {'uid': user_id, 'eid': exercise_id, 'rd': record_date, 'ts': session_timestamp, 'set': set_number, 'reps': final_reps, 'w': final_weight}, commit=True)
        if not has_data:
            flash('Nessun dato valido inserito. Allenamento non salvato.', 'warning')
            execute_query('DELETE FROM workout_sessions WHERE session_timestamp = :ts', {'ts': session_timestamp}, commit=True)
            return redirect(url_for('gym.sessione_palestra', date_param=record_date))
        for key, comment in request.form.items():
            if key.startswith('comment_'):
                exercise_id = int(key.split('_')[1])
                if comment:
                    comment_query = "INSERT INTO workout_session_comments (user_id, session_timestamp, exercise_id, comment) VALUES (:uid, :ts, :eid, :comm) ON CONFLICT(user_id, session_timestamp, exercise_id) DO UPDATE SET comment=EXCLUDED.comment"
                    execute_query(comment_query, {'uid': user_id, 'ts': session_timestamp, 'eid': exercise_id, 'comm': comment}, commit=True)
        flash('Allenamento salvato con successo!', 'success')
        return redirect(url_for('gym.diario_palestra'))

    stored_session = execute_query('SELECT template_name, duration_minutes FROM workout_sessions WHERE user_id = :uid AND session_timestamp = :ts', {'uid': user_id, 'ts': session_ts}, fetchone=True) if session_ts else None
    selected_template_name = stored_session['template_name'] if stored_session else None
    stored_duration_minutes = stored_session['duration_minutes'] if stored_session else None
    templates = get_templates_with_history(user_id, current_date)
    selected_template_id = None
    if session_ts and selected_template_name:
        for template in templates or []:
            if template['name'] == selected_template_name:
                selected_template_id = template['id']
                break
    requested_template_id = request.args.get('template_id', type=int)
    if not session_ts and requested_template_id is not None:
        selected_template_id = requested_template_id
    elif selected_template_id is None and requested_template_id is not None:
        selected_template_id = requested_template_id
    log_data = get_session_log_data(user_id, session_ts) if session_ts else {}
    cancel_url = url_for('gym.diario_palestra') if session_ts else url_for('gym.palestra')

    return render_template('sessione_palestra.html', title='Sessione Palestra', templates=templates, log_data=log_data, record_date=record_date, date_formatted=date_formatted, prev_day=prev_day, next_day=next_day, is_today=is_today, is_editing=(session_ts is not None), session_timestamp=session_ts if session_ts else datetime.now().strftime('%Y%m%d%H%M%S'), selected_template_id=selected_template_id, selected_template_name=selected_template_name, session_duration_minutes=stored_duration_minutes, cancel_url=cancel_url)

@gym_bp.route('/diario_palestra', methods=['GET', 'POST'])
@login_required
def diario_palestra():
    user_id = session['user_id']
    if request.method == 'POST':
        session_to_delete = request.form.get('session_to_delete')
        execute_query('DELETE FROM workout_sessions WHERE user_id = :uid AND session_timestamp = :ts', {'uid': user_id, 'ts': session_to_delete}, commit=True)
        flash('Allenamento eliminato con successo.', 'success')
        return redirect(url_for('gym.diario_palestra'))

    logs_raw = execute_query('SELECT wl.record_date, wl.session_timestamp, e.name as exercise_name, wl.set_number, wl.reps, wl.weight FROM workout_log wl JOIN exercises e ON wl.exercise_id = e.id WHERE wl.user_id = :uid ORDER BY wl.record_date DESC, wl.session_timestamp DESC, wl.id ASC', {'uid': user_id}, fetchall=True)
    sessions_raw = execute_query('SELECT session_timestamp, duration_minutes, template_name, session_note, session_rating FROM workout_sessions WHERE user_id = :uid', {'uid': user_id}, fetchall=True)
    sessions_info = {s['session_timestamp']: dict(s) for s in sessions_raw}

    workouts_by_day = defaultdict(lambda: {'date_formatted': '', 'template_names': [], 'sessions': defaultdict(lambda: {'time_formatted': '', 'duration': None, 'template_name': 'Allenamento Libero', 'session_note': None, 'session_rating': None, 'exercises': defaultdict(list)})})
    for row in logs_raw:
        day, ts, ex_name = row['record_date'], row['session_timestamp'], row['exercise_name']
        workouts_by_day[day]['date_formatted'] = day.strftime('%d %b %y')
        session_details = sessions_info.get(ts, {})
        s_data = workouts_by_day[day]['sessions'][ts]
        s_data['time_formatted'] = datetime.strptime(ts, '%Y%m%d%H%M%S').strftime('%H:%M')
        s_data['duration'] = session_details.get('duration_minutes')
        template_name = session_details.get('template_name') or 'Allenamento Libero'
        s_data['template_name'] = template_name
        s_data['session_note'] = session_details.get('session_note')
        s_data['session_rating'] = session_details.get('session_rating')
        if template_name not in workouts_by_day[day]['template_names']:
            workouts_by_day[day]['template_names'].append(template_name)
        s_data['exercises'][ex_name].append({'set': row['set_number'], 'reps': row['reps'], 'weight': row['weight']})
    
    final_workouts = {}
    for day, data in workouts_by_day.items():
        sessions_payload = {}
        for ts, s_data in data['sessions'].items():
            session_dict = dict(s_data)
            session_dict['exercises'] = {name: sets for name, sets in s_data['exercises'].items()}
            sessions_payload[ts] = session_dict
        final_workouts[day] = {'date_formatted': data['date_formatted'], 'template_names': data['template_names'], 'sessions': sessions_payload}
        
    return render_template('diario_palestra.html', title='Diario Palestra', workouts_by_day=final_workouts)