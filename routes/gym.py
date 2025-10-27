# routes/gym.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from datetime import date, datetime, timedelta
from collections import defaultdict
from .auth import login_required
from utils import execute_query
from sqlalchemy.exc import IntegrityError
from extensions import db
from services.workout_service import get_templates_with_history, get_session_log_data

gym_bp = Blueprint('gym', __name__)

# --- ENDPOINT API PER AJAX ---

@gym_bp.route('/scheda/rinomina', methods=['POST'])
@login_required
def rinomina_scheda_ajax():
    user_id = session['user_id']
    template_id = request.form.get('template_id')
    new_name = (request.form.get('new_template_name') or '').strip()

    if not new_name or not template_id:
        return jsonify({'success': False, 'error': 'Dati mancanti.'}), 400

    try:
        template_id_int = int(template_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Identificativo scheda non valido.'}), 400

    if len(new_name) > 120:
        return jsonify({'success': False, 'error': 'Il nome è troppo lungo (max 120 caratteri).'}), 400

    template = execute_query(
        'SELECT id, name FROM workout_templates WHERE id = :id AND user_id = :user_id',
        {'id': template_id_int, 'user_id': user_id},
        fetchone=True,
    )

    if not template:
        return jsonify({'success': False, 'error': 'Scheda non trovata o non autorizzata.'}), 404

    if template['name'] == new_name:
        return jsonify({'success': True, 'newName': new_name, 'templateId': template_id_int})

    try:
        execute_query(
            'UPDATE workout_templates SET name = :name WHERE id = :id AND user_id = :user_id',
            {'name': new_name, 'id': template_id_int, 'user_id': user_id},
            commit=True,
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"Esiste già una scheda con il nome '{new_name}'."}), 409
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Si è verificato un errore interno.'}), 500

    return jsonify({'success': True, 'newName': new_name, 'templateId': template_id_int})

@gym_bp.route('/scheda/aggiungi-esercizio', methods=['POST'])
@login_required
def aggiungi_esercizio_ajax():
    user_id = session['user_id']
    template_id = request.form.get('template_id')
    exercise_id = request.form.get('exercise_id')
    sets = (request.form.get('sets') or '').strip()
    csrf_token = request.form.get('csrf_token')
    if not all([template_id, exercise_id, sets]):
        return jsonify({'success': False, 'error': 'Dati mancanti.'}), 400

    try:
        template_id_int = int(template_id)
        exercise_id_int = int(exercise_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Parametri non validi.'}), 400

    template = execute_query(
        'SELECT id FROM workout_templates WHERE id = :id AND user_id = :user_id',
        {'id': template_id_int, 'user_id': user_id},
        fetchone=True,
    )
    if not template:
        return jsonify({'success': False, 'error': 'Scheda non trovata o non autorizzata.'}), 404

    exercise = execute_query(
        'SELECT id, name FROM exercises WHERE id = :id AND (user_id IS NULL OR user_id = :user_id)',
        {'id': exercise_id_int, 'user_id': user_id},
        fetchone=True,
    )
    if not exercise:
        return jsonify({'success': False, 'error': 'Esercizio non disponibile.'}), 404

    try:
        query = "INSERT INTO template_exercises (template_id, exercise_id, sets) VALUES (:tid, :eid, :sets) RETURNING id"
        result = execute_query(
            query,
            {'tid': template_id_int, 'eid': exercise_id_int, 'sets': sets},
            fetchone=True,
            commit=True,
        )
        new_id = result['id'] if result else None
        return jsonify({
            'success': True,
            'exercise': {'id': new_id, 'name': exercise['name'], 'sets': sets},
            'csrf_token': csrf_token
        })
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Errore durante il salvataggio.'}), 500

@gym_bp.route('/scheda/elimina-esercizio', methods=['POST'])
@login_required
def elimina_esercizio_ajax():
    user_id = session['user_id']
    template_exercise_id = request.form.get('template_exercise_id')
    if not template_exercise_id:
        return jsonify({'success': False, 'error': 'ID Esercizio mancante.'}), 400
    try:
        query = "DELETE FROM template_exercises te WHERE te.id = :teid AND EXISTS (SELECT 1 FROM workout_templates wt WHERE wt.id = te.template_id AND wt.user_id = :uid)"
        execute_query(query, {'teid': template_exercise_id, 'uid': user_id}, commit=True)
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Errore durante l\'eliminazione.'}), 500

@gym_bp.route('/esercizi/rinomina', methods=['POST'])
@login_required
def rinomina_esercizio_ajax():
    user_id = session['user_id']
    exercise_id = request.form.get('exercise_id')
    new_name = (request.form.get('new_exercise_name') or '').strip()

    if not new_name or not exercise_id:
        return jsonify({'success': False, 'error': 'Dati mancanti.'}), 400

    try:
        exercise_id_int = int(exercise_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Identificativo esercizio non valido.'}), 400

    if len(new_name) > 120:
        return jsonify({'success': False, 'error': 'Il nome è troppo lungo (max 120 caratteri).'}), 400

    exercise = execute_query(
        'SELECT id, name FROM exercises WHERE id = :id AND user_id = :user_id',
        {'id': exercise_id_int, 'user_id': user_id},
        fetchone=True,
    )

    if not exercise:
        return jsonify({'success': False, 'error': 'Esercizio non trovato o non autorizzato.'}), 404

    if exercise['name'] == new_name:
        return jsonify({'success': True, 'newName': new_name, 'exerciseId': exercise_id_int})

    try:
        execute_query(
            'UPDATE exercises SET name = :name WHERE id = :id AND user_id = :user_id',
            {'name': new_name, 'id': exercise_id_int, 'user_id': user_id},
            commit=True,
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"Esiste già un esercizio con il nome '{new_name}'."}), 409
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Errore del server.'}), 500

    return jsonify({'success': True, 'newName': new_name, 'exerciseId': exercise_id_int})

@gym_bp.route('/esercizi/aggiorna-note', methods=['POST'])
@login_required
def aggiorna_note_ajax():
    user_id = session['user_id']
    exercise_id = request.form.get('exercise_id')
    notes = request.form.get('notes')
    if exercise_id is None:
        return jsonify({'success': False, 'error': 'ID Esercizio mancante.'}), 400
    try:
        query = "INSERT INTO user_exercise_notes (user_id, exercise_id, notes) VALUES (:user_id, :eid, :notes) ON CONFLICT(user_id, exercise_id) DO UPDATE SET notes = EXCLUDED.notes"
        execute_query(query, {'user_id': user_id, 'eid': exercise_id, 'notes': notes}, commit=True)
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Errore del server.'}), 500

@gym_bp.route('/esercizi/elimina', methods=['POST'])
@login_required
def elimina_esercizio_personale_ajax():
    user_id = session['user_id']
    exercise_id = request.form.get('exercise_id')
    if not exercise_id:
        return jsonify({'success': False, 'error': 'ID Esercizio mancante.'}), 400
    try:
        execute_query('DELETE FROM exercises WHERE id = :id AND user_id = :user_id', {'id': exercise_id, 'user_id': user_id}, commit=True)
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Errore del server.'}), 500

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
                    if make_global:
                        duplicate = execute_query('SELECT 1 FROM exercises WHERE user_id IS NULL AND LOWER(name) = LOWER(:name)', {'name': name}, fetchone=True)
                        if duplicate:
                            flash(f"Errore: esiste già un esercizio globale chiamato '{name}'.", 'danger')
                            return redirect(url_for('gym.esercizi'))
                    new_exercise_query = 'INSERT INTO exercises (name, user_id) VALUES (:name, :user_id) RETURNING id'
                    result = execute_query(new_exercise_query, {'name': name, 'user_id': owner_id}, fetchone=True)
                    db.session.commit()
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
        elif action == 'rename_exercise':
            exercise_id = request.form.get('exercise_id')
            new_name = (request.form.get('new_exercise_name') or '').strip()

            if not exercise_id or not new_name:
                flash('Completa tutti i campi per rinominare l\'esercizio.', 'danger')
                return redirect(url_for('gym.esercizi'))

            if len(new_name) > 120:
                flash('Il nome è troppo lungo (massimo 120 caratteri).', 'danger')
                return redirect(url_for('gym.esercizi'))

            try:
                exercise_id_int = int(exercise_id)
            except (TypeError, ValueError):
                flash('Identificativo esercizio non valido.', 'danger')
                return redirect(url_for('gym.esercizi'))

            exercise = execute_query('SELECT id, user_id FROM exercises WHERE id = :id', {'id': exercise_id_int}, fetchone=True)

            if not exercise or (exercise['user_id'] != user_id and exercise['user_id'] is not None):
                flash('Esercizio non trovato o non autorizzato.', 'danger')
                return redirect(url_for('gym.esercizi'))

            if exercise['user_id'] is None and not is_superuser:
                flash('Non sei autorizzato a modificare questo esercizio.', 'danger')
                return redirect(url_for('gym.esercizi'))

            try:
                params = {'name': new_name, 'id': exercise_id_int}
                if exercise['user_id'] is None:
                    duplicate = execute_query('SELECT 1 FROM exercises WHERE user_id IS NULL AND LOWER(name) = LOWER(:name) AND id <> :id', {'name': new_name, 'id': exercise_id_int}, fetchone=True)
                    if duplicate:
                        flash(f"Errore: esiste già un esercizio globale chiamato '{new_name}'.", 'danger')
                        return redirect(url_for('gym.esercizi'))
                    query = 'UPDATE exercises SET name = :name WHERE id = :id AND user_id IS NULL'
                else:
                    params['user_id'] = user_id
                    query = 'UPDATE exercises SET name = :name WHERE id = :id AND user_id = :user_id'
                execute_query(query, params, commit=True)
                flash('Esercizio rinominato con successo.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f"Errore: esiste già un esercizio chiamato '{new_name}'.", 'danger')
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception('Errore durante la rinomina esercizio %s', exercise_id_int)
                flash('Si è verificato un errore durante il salvataggio.', 'danger')
        elif action == 'delete_exercise':
            exercise_id = request.form.get('exercise_id')
            if not exercise_id:
                flash('Identificativo esercizio non valido.', 'danger')
                return redirect(url_for('gym.esercizi'))
            try:
                exercise_id_int = int(exercise_id)
            except (TypeError, ValueError):
                flash('Identificativo esercizio non valido.', 'danger')
                return redirect(url_for('gym.esercizi'))

            is_global = request.form.get('is_global') == '1'
            if is_global and not is_superuser:
                flash('Non sei autorizzato a eliminare questo esercizio.', 'danger')
                return redirect(url_for('gym.esercizi'))
            params = {'id': exercise_id_int}
            condition = 'user_id IS NULL' if is_global else 'user_id = :uid'
            if not is_global:
                params['uid'] = user_id
            execute_query(f'DELETE FROM exercises WHERE id = :id AND {condition}', params, commit=True)
            flash(('Esercizio globale eliminato.' if is_global else 'Esercizio personale eliminato.'), 'success')
        return redirect(url_for('gym.esercizi'))

    query = "SELECT e.id, e.name, e.user_id, uen.notes FROM exercises e LEFT JOIN user_exercise_notes uen ON e.id = uen.exercise_id AND uen.user_id = :user_id WHERE e.user_id IS NULL OR e.user_id = :user_id ORDER BY e.name"
    exercises = execute_query(query, {'user_id': user_id}, fetchall=True)
    return render_template('esercizi.html', title='Esercizi', exercises=exercises, is_superuser=is_superuser)

@gym_bp.route('/scheda', methods=['GET', 'POST'])
@login_required
def scheda():
    user_id = session['user_id']
    is_superuser = bool(session.get('is_superuser'))
    if request.method == 'POST':
        action = request.form.get('action')
        template_id = request.form.get('template_id')
        if action == 'add_template':
            name = request.form.get('template_name')
            if name:
                try:
                    execute_query('INSERT INTO workout_templates (user_id, name) VALUES (:uid, :name)', {'uid': user_id, 'name': name}, commit=True)
                    flash('Scheda creata con successo.', 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: Una scheda con il nome '{name}' esiste già.", 'danger')
        elif action == 'rename_template':
            template_id = request.form.get('template_id')
            new_name = (request.form.get('new_template_name') or '').strip()

            if not template_id or not new_name:
                flash('Completa tutti i campi per rinominare la scheda.', 'danger')
                return redirect(url_for('gym.scheda'))

            if len(new_name) > 120:
                flash('Il nome è troppo lungo (massimo 120 caratteri).', 'danger')
                return redirect(url_for('gym.scheda'))

            try:
                template_id_int = int(template_id)
            except (TypeError, ValueError):
                flash('Identificativo scheda non valido.', 'danger')
                return redirect(url_for('gym.scheda'))

            template = execute_query(
                'SELECT id FROM workout_templates WHERE id = :id AND user_id = :user_id',
                {'id': template_id_int, 'user_id': user_id},
                fetchone=True,
            )

            if not template:
                flash('Scheda non trovata o non autorizzata.', 'danger')
                return redirect(url_for('gym.scheda'))

            try:
                execute_query(
                    'UPDATE workout_templates SET name = :name WHERE id = :id AND user_id = :user_id',
                    {'name': new_name, 'id': template_id_int, 'user_id': user_id},
                    commit=True,
                )
                flash('Scheda rinominata con successo.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f"Errore: esiste già una scheda chiamata '{new_name}'.", 'danger')
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception('Errore durante la rinomina scheda %s', template_id_int)
                flash('Si è verificato un errore durante il salvataggio.', 'danger')
        elif action == 'add_exercise':
            exercise_id = request.form.get('exercise_id')
            sets = (request.form.get('sets') or '').strip()
            if not template_id or not exercise_id or not sets:
                flash('Compila tutti i campi per aggiungere un esercizio.', 'danger')
                return redirect(url_for('gym.scheda'))

            try:
                template_id_int = int(template_id)
                exercise_id_int = int(exercise_id)
            except (TypeError, ValueError):
                flash('Dati esercizio non validi.', 'danger')
                return redirect(url_for('gym.scheda'))

            template = execute_query('SELECT id FROM workout_templates WHERE id = :id AND user_id = :uid', {'id': template_id_int, 'uid': user_id}, fetchone=True)
            if not template:
                flash('Scheda non trovata.', 'danger')
                return redirect(url_for('gym.scheda'))

            exercise = execute_query('SELECT id, user_id FROM exercises WHERE id = :id', {'id': exercise_id_int}, fetchone=True)
            if not exercise or (exercise['user_id'] not in (user_id, None)):
                flash('Esercizio non disponibile.', 'danger')
                return redirect(url_for('gym.scheda'))
            execute_query('INSERT INTO template_exercises (template_id, exercise_id, sets) VALUES (:tid, :eid, :sets)',
                          {'tid': template_id_int, 'eid': exercise_id_int, 'sets': sets}, commit=True)
            flash('Esercizio aggiunto alla scheda.', 'success')
        elif action == 'delete_template_exercise':
            template_exercise_id = request.form.get('template_exercise_id')
            execute_query(
                'DELETE FROM template_exercises te WHERE te.id = :id AND EXISTS (SELECT 1 FROM workout_templates wt WHERE wt.id = te.template_id AND wt.user_id = :uid)',
                {'id': template_exercise_id, 'uid': user_id},
                commit=True,
            )
            flash('Esercizio rimosso dalla scheda.', 'success')
        elif action == 'delete_template':
            execute_query('DELETE FROM workout_templates WHERE id = :id AND user_id = :uid', {'id': template_id, 'uid': user_id}, commit=True)
            flash('Scheda eliminata con successo.', 'success')
        return redirect(url_for('gym.scheda'))

    templates_raw = execute_query('SELECT * FROM workout_templates WHERE user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    templates = []
    for t in templates_raw:
        template_dict = dict(t)
        exercises = execute_query('SELECT te.id, e.name, e.user_id, te.sets FROM template_exercises te JOIN exercises e ON te.exercise_id = e.id WHERE te.template_id = :tid ORDER BY te.id', {'tid': t['id']}, fetchall=True)
        template_dict['exercises'] = exercises
        templates.append(template_dict)
    all_exercises = execute_query('SELECT id, name, user_id FROM exercises WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    return render_template('scheda.html', title='Scheda Allenamento', templates=templates, all_exercises=all_exercises, is_superuser=is_superuser)

@gym_bp.route('/esercizio/<int:exercise_id>')
@login_required
def esercizio_dettaglio(exercise_id):
    user_id = session['user_id']
    exercise = execute_query('SELECT * FROM exercises WHERE id = :id', {'id': exercise_id}, fetchone=True)
    if not exercise:
        return redirect(url_for('gym.esercizi'))

    query = "SELECT wl.record_date, wl.session_timestamp, wl.set_number, wl.reps, wl.weight, wsc.comment FROM workout_log wl LEFT JOIN workout_session_comments wsc ON wl.session_timestamp = wsc.session_timestamp AND wl.exercise_id = wsc.exercise_id AND wl.user_id = wsc.user_id WHERE wl.user_id = :user_id AND wl.exercise_id = :eid ORDER BY wl.record_date DESC, wl.session_timestamp DESC, wl.id ASC"
    history_raw = execute_query(query, {'user_id': user_id, 'eid': exercise_id}, fetchall=True)

    sessions = {}
    for row in history_raw:
        ts = row['session_timestamp']
        if ts not in sessions:
            sessions[ts] = { 'date_formatted': row['record_date'].strftime('%d %b %y'), 'comment': row['comment'], 'sets': [] }
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

        session_query = "INSERT INTO workout_sessions (user_id, session_timestamp, record_date, template_name, duration_minutes) VALUES (:uid, :ts, :rd, :tn, :dur) ON CONFLICT(session_timestamp) DO UPDATE SET template_name = EXCLUDED.template_name, duration_minutes = EXCLUDED.duration_minutes"
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
                    comment_query = "INSERT INTO workout_session_comments (user_id, session_timestamp, exercise_id, comment) VALUES (:uid, :ts, :eid, :comm) ON CONFLICT(user_id, session_timestamp, exercise_id) DO UPDATE SET comment=EXCLUDED.comment"
                    execute_query(comment_query, {'uid': user_id, 'ts': session_timestamp, 'eid': exercise_id, 'comm': comment}, commit=True)

        flash('Allenamento salvato con successo!', 'success')
        return redirect(url_for('gym.diario_palestra'))

    templates = get_templates_with_history(user_id, current_date)
    log_data = get_session_log_data(user_id, session_ts) if session_ts else {}

    return render_template('sessione_palestra.html', title='Sessione Palestra', templates=templates, log_data=log_data, record_date=record_date, date_formatted=date_formatted, prev_day=prev_day, next_day=next_day, is_today=is_today, is_editing=(session_ts is not None), session_timestamp=session_ts if session_ts else datetime.now().strftime('%Y%m%d%H%M%S'))

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
        workouts_by_day[day]['date_formatted'] = day.strftime('%d %b %y')
        session_details = sessions_info.get(ts, {})
        s_data = workouts_by_day[day]['sessions'][ts]
        s_data['time_formatted'] = datetime.strptime(ts, '%Y%m%d%H%M%S').strftime('%H:%M')
        s_data['duration'] = session_details.get('duration_minutes')
        s_data['template_name'] = session_details.get('template_name', 'N/D')
        s_data['exercises'][ex_name].append({'set': row['set_number'], 'reps': row['reps'], 'weight': row['weight']})
    final_workouts = {day: {'date_formatted': data['date_formatted'], 'sessions': {ts: dict(s_data) for ts, s_data in data['sessions'].items()}} for day, data in workouts_by_day.items()}
    return render_template('diario_palestra.html', title='Diario Palestra', workouts_by_day=final_workouts)
