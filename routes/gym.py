# routes/gym.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import date, datetime, timedelta
from collections import defaultdict
from .auth import login_required
from utils import execute_query

gym_bp = Blueprint('gym', __name__)

@gym_bp.route('/palestra')
@login_required
def palestra():
    return render_template('palestra.html', title='Palestra')

@gym_bp.route('/esercizi', methods=['GET', 'POST'])
@login_required
def esercizi():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_exercise':
            name = request.form.get('name')
            if name:
                execute_query('INSERT INTO exercises (name, user_id) VALUES (:name, :user_id)', {'name': name, 'user_id': user_id}, commit=True)
                flash('Esercizio personale aggiunto.', 'success')
        elif action == 'delete_exercise':
            exercise_id = request.form.get('exercise_id')
            execute_query('DELETE FROM exercises WHERE id = :id AND user_id = :user_id', {'id': exercise_id, 'user_id': user_id}, commit=True)
            flash('Esercizio personale eliminato.', 'success')
        elif action == 'update_notes':
            exercise_id = request.form.get('exercise_id')
            notes = request.form.get('notes')
            query = """
                INSERT INTO user_exercise_notes (user_id, exercise_id, notes) VALUES (:user_id, :eid, :notes) 
                ON CONFLICT(user_id, exercise_id) DO UPDATE SET notes = EXCLUDED.notes
            """
            execute_query(query, {'user_id': user_id, 'eid': exercise_id, 'notes': notes}, commit=True)
            flash('Note personali aggiornate.', 'success')
        return redirect(url_for('gym.esercizi'))
    
    query = """
        SELECT e.id, e.name, e.user_id, uen.notes 
        FROM exercises e
        LEFT JOIN user_exercise_notes uen ON e.id = uen.exercise_id AND uen.user_id = :user_id
        WHERE e.user_id IS NULL OR e.user_id = :user_id
        ORDER BY e.name
    """
    exercises = execute_query(query, {'user_id': user_id}, fetchall=True)
    return render_template('esercizi.html', title='Esercizi', exercises=exercises)

@gym_bp.route('/esercizio/<int:exercise_id>')
@login_required
def esercizio_dettaglio(exercise_id):
    user_id = session['user_id']
    exercise = execute_query('SELECT * FROM exercises WHERE id = :id', {'id': exercise_id}, fetchone=True)
    if not exercise:
        return redirect(url_for('gym.esercizi'))
    
    query = """
        SELECT wl.record_date, wl.session_timestamp, wl.set_number, wl.reps, wl.weight, wsc.comment
        FROM workout_log wl
        LEFT JOIN workout_session_comments wsc ON wl.session_timestamp = wsc.session_timestamp AND wl.exercise_id = wsc.exercise_id AND wl.user_id = wsc.user_id
        WHERE wl.user_id = :user_id AND wl.exercise_id = :eid
        ORDER BY wl.record_date DESC, wl.session_timestamp DESC, wl.id ASC
    """
    history_raw = execute_query(query, {'user_id': user_id, 'eid': exercise_id}, fetchall=True)

    sessions = {}
    for row in history_raw:
        ts = row['session_timestamp']
        if ts not in sessions:
            sessions[ts] = {
                'date_formatted': datetime.strptime(row['record_date'], '%Y-%m-%d').strftime('%d %b %y'),
                'comment': row['comment'],
                'sets': []
            }
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
        duration_minutes = 0
        if start_timestamp_ms:
            try:
                start_time = datetime.fromtimestamp(int(start_timestamp_ms) / 1000)
                duration = datetime.now() - start_time
                duration_minutes = max(0, int(duration.total_seconds() / 60))
            except (ValueError, TypeError): pass
        
        session_query = """
            INSERT INTO workout_sessions (user_id, session_timestamp, record_date, template_name, duration_minutes) 
            VALUES (:uid, :ts, :rd, :tn, :dur)
            ON CONFLICT(session_timestamp) DO UPDATE SET
            template_name = EXCLUDED.template_name, duration_minutes = EXCLUDED.duration_minutes
        """
        execute_query(session_query, {'uid': user_id, 'ts': session_timestamp, 'rd': record_date, 'tn': template_name, 'dur': duration_minutes}, commit=True)

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
                    execute_query('INSERT INTO workout_log (user_id, exercise_id, record_date, session_timestamp, set_number, reps, weight) VALUES (:uid, :eid, :rd, :ts, :set, :reps, :w)',
                                  {'uid': user_id, 'eid': exercise_id, 'rd': record_date, 'ts': session_timestamp, 'set': set_number, 'reps': final_reps, 'w': final_weight}, commit=True)
        
        if not has_data:
            flash('Nessun dato valido inserito. Allenamento non salvato.', 'warning')
            execute_query('DELETE FROM workout_sessions WHERE session_timestamp = :ts', {'ts': session_timestamp}, commit=True)
            return redirect(url_for('gym.sessione_palestra', date_param=record_date))
            
        for key, comment in request.form.items():
            if key.startswith('comment_'):
                exercise_id = int(key.split('_')[1])
                if comment:
                    comment_query = """
                        INSERT INTO workout_session_comments (user_id, session_timestamp, exercise_id, comment) VALUES (:uid, :ts, :eid, :comm) 
                        ON CONFLICT(user_id, session_timestamp, exercise_id) DO UPDATE SET comment=EXCLUDED.comment
                    """
                    execute_query(comment_query, {'uid': user_id, 'ts': session_timestamp, 'eid': exercise_id, 'comm': comment}, commit=True)
        
        flash('Allenamento salvato con successo!', 'success')
        return redirect(url_for('gym.diario_palestra'))
            
    templates_raw = execute_query('SELECT * FROM workout_templates WHERE user_id = :user_id ORDER BY name', {'user_id': user_id}, fetchall=True)
    templates_dict = {t['id']: {**dict(t), 'exercises': []} for t in templates_raw}
    template_ids = list(templates_dict.keys())

    if template_ids:
        all_template_exercises_raw = execute_query(f'''
            SELECT te.id, te.template_id, e.id as exercise_id, e.name, uen.notes, te.sets
            FROM template_exercises te JOIN exercises e ON te.exercise_id = e.id
            LEFT JOIN user_exercise_notes uen ON e.id = uen.exercise_id AND uen.user_id = :user_id
            WHERE te.template_id = ANY(:template_ids) ORDER BY te.id
        ''', {'user_id': user_id, 'template_ids': template_ids}, fetchall=True)
        
        exercise_ids = list(set(ex['exercise_id'] for ex in all_template_exercises_raw))
        if exercise_ids:
            history_raw = execute_query(f'SELECT record_date, session_timestamp, exercise_id, set_number, reps, weight FROM workout_log WHERE user_id = :user_id AND exercise_id = ANY(:eids) AND record_date < :rd ORDER BY record_date DESC, session_timestamp DESC, id ASC', 
                                        {'user_id': user_id, 'eids': exercise_ids, 'rd': record_date}, fetchall=True)
            comments_raw = execute_query(f'''
                SELECT wsc.comment, wl.record_date, wsc.exercise_id FROM workout_session_comments wsc 
                JOIN workout_log wl ON wsc.session_timestamp = wl.session_timestamp 
                WHERE wsc.user_id = :user_id AND wsc.exercise_id = ANY(:eids) AND wl.record_date < :rd 
                ORDER BY wl.record_date DESC, wsc.id DESC
                ''', {'user_id': user_id, 'eids': exercise_ids, 'rd': record_date}, fetchall=True)

            history_by_exercise = defaultdict(list); last_comment_by_exercise = {}
            for row in history_raw: history_by_exercise[row['exercise_id']].append(row)
            for row in comments_raw:
                if row['exercise_id'] not in last_comment_by_exercise: last_comment_by_exercise[row['exercise_id']] = row

            for ex in all_template_exercises_raw:
                ex_dict = dict(ex); history_grouped = {}
                for row in history_by_exercise.get(ex['exercise_id'], []):
                    ts = row['session_timestamp']
                    if ts not in history_grouped:
                        if len(history_grouped) >= 2: break
                        history_grouped[ts] = {'date_formatted': datetime.strptime(row['record_date'], '%Y-%m-%d').strftime('%d %b'), 'sets': []}
                    history_grouped[ts]['sets'].append(f"{row['weight']}kg x {row['reps']}")
                ex_dict['history'] = history_grouped

                last_comment = last_comment_by_exercise.get(ex['exercise_id'])
                ex_dict['last_comment'] = last_comment['comment'] if last_comment else None
                ex_dict['last_comment_date'] = datetime.strptime(last_comment['record_date'], '%Y-%m-%d').strftime('%d %b') if last_comment else None
                templates_dict[ex['template_id']]['exercises'].append(ex_dict)

    templates = list(templates_dict.values())
    log_data = {}
    if session_ts:
        log_rows = execute_query('SELECT * FROM workout_log WHERE user_id = :uid AND session_timestamp = :ts', {'uid': user_id, 'ts': session_ts}, fetchall=True)
        for row in log_rows: log_data[f"{row['exercise_id']}_{row['set_number']}"] = {'reps': row['reps'], 'weight': row['weight']}
        comment_rows = execute_query('SELECT exercise_id, comment FROM workout_session_comments WHERE user_id = :uid AND session_timestamp = :ts', {'uid': user_id, 'ts': session_ts}, fetchall=True)
        for row in comment_rows: log_data[f"comment_{row['exercise_id']}"] = row['comment']
    
    return render_template('sessione_palestra.html', title='Sessione Palestra', templates=templates, log_data=log_data, record_date=record_date, date_formatted=date_formatted, prev_day=prev_day, next_day=next_day, is_today=is_today, is_editing=(session_ts is not None), session_timestamp=session_ts if session_ts else datetime.now().strftime('%Y%m%d%H%M%S'))

@gym_bp.route('/scheda', methods=['GET', 'POST'])
@login_required
def scheda():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_template':
            name = request.form.get('template_name')
            if name:
                execute_query('INSERT INTO workout_templates (user_id, name) VALUES (:uid, :name)', {'uid': user_id, 'name': name}, commit=True)
                flash('Scheda creata con successo.', 'success')
        elif action == 'delete_template':
            template_id = request.form.get('template_id')
            execute_query('DELETE FROM workout_templates WHERE id = :id AND user_id = :uid', {'id': template_id, 'uid': user_id}, commit=True)
            flash('Scheda eliminata con successo.', 'success')
        elif action == 'add_exercise':
            template_id = request.form.get('template_id'); exercise_id = request.form.get('exercise_id'); sets = request.form.get('sets')
            if template_id and exercise_id and sets:
                execute_query('INSERT INTO template_exercises (template_id, exercise_id, sets) VALUES (:tid, :eid, :sets)', 
                              {'tid': template_id, 'eid': exercise_id, 'sets': sets}, commit=True)
                flash('Esercizio aggiunto alla scheda.', 'success')
        elif action == 'delete_template_exercise':
            template_exercise_id = request.form.get('template_exercise_id')
            execute_query('DELETE FROM template_exercises WHERE id = :id', {'id': template_exercise_id}, commit=True)
            flash('Esercizio rimosso dalla scheda.', 'success')
        return redirect(url_for('gym.scheda'))
        
    templates_raw = execute_query('SELECT * FROM workout_templates WHERE user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    templates = []
    for t in templates_raw:
        template_dict = dict(t)
        exercises = execute_query('SELECT te.id, e.name, te.sets FROM template_exercises te JOIN exercises e ON te.exercise_id = e.id WHERE te.template_id = :tid ORDER BY te.id', {'tid': t['id']}, fetchall=True)
        template_dict['exercises'] = exercises
        templates.append(template_dict)
    all_exercises = execute_query('SELECT * FROM exercises WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    return render_template('scheda.html', title='Scheda Allenamento', templates=templates, all_exercises=all_exercises)

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
    sessions_raw = execute_query('SELECT session_timestamp, duration_minutes, template_name FROM workout_sessions WHERE user_id = :uid', {'uid': user_id}, fetchall=True)
    sessions_info = {s['session_timestamp']: dict(s) for s in sessions_raw}
    
    workouts_by_day = defaultdict(lambda: {'date_formatted': '', 'sessions': defaultdict(lambda: {'time_formatted': '', 'duration': None, 'template_name': 'N/D', 'exercises': defaultdict(list)})})
    for row in logs_raw:
        day, ts, ex_name = row['record_date'], row['session_timestamp'], row['exercise_name']
        workouts_by_day[day]['date_formatted'] = datetime.strptime(day, '%Y-%m-%d').strftime('%d %b %y')
        session_details = sessions_info.get(ts, {})
        s_data = workouts_by_day[day]['sessions'][ts]
        s_data['time_formatted'] = datetime.strptime(ts, '%Y%m%d%H%M%S').strftime('%H:%M')
        s_data['duration'] = session_details.get('duration_minutes')
        s_data['template_name'] = session_details.get('template_name', 'N/D')
        s_data['exercises'][ex_name].append({'set': row['set_number'], 'reps': row['reps'], 'weight': row['weight']})
    final_workouts = {day: {'date_formatted': data['date_formatted'], 'sessions': {ts: dict(s_data) for ts, s_data in data['sessions'].items()}} for day, data in workouts_by_day.items()}
    return render_template('diario_palestra.html', title='Diario Palestra', workouts_by_day=final_workouts)