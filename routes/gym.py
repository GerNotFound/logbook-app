# routes/gym.py

import json

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from datetime import date, datetime, timedelta
from collections import defaultdict
from .auth import login_required
from utils import execute_query, slugify
from sqlalchemy.exc import IntegrityError
from extensions import db
from services.workout_service import get_templates_with_history, get_session_log_data
from services.suggestion_service import get_catalog_suggestions, resolve_catalog_item

gym_bp = Blueprint('gym', __name__)

# --- ENDPOINT API PER AJAX ---


def _get_template_by_slug(user_id: int, template_slug: str):
    """Recupera una scheda utilizzando lo slug del suo nome."""

    if not template_slug:
        return None

    templates = execute_query(
        'SELECT * FROM workout_templates WHERE user_id = :uid',
        {'uid': user_id},
        fetchall=True,
    )
    for tpl in templates:
        if slugify(tpl['name']) == template_slug:
            return tpl
    return None


def _ensure_template_exercise_order(template_id: int) -> None:
    """Normalizza l'ordinamento degli esercizi di una scheda."""

    if not template_id:
        return

    rows = execute_query(
        'SELECT id, sort_order '
        'FROM template_exercises '
        'WHERE template_id = :tid '
        'ORDER BY COALESCE(sort_order, id), id',
        {'tid': template_id},
        fetchall=True,
    ) or []

    dirty = False
    for index, row in enumerate(rows, start=1):
        current_order = row.get('sort_order')
        if current_order != index:
            execute_query(
                'UPDATE template_exercises SET sort_order = :order WHERE id = :id',
                {'order': index, 'id': row['id']},
            )
            dirty = True

    if dirty:
        db.session.commit()

@gym_bp.route('/api/suggest/exercises')
@login_required
def suggest_exercises():
    user_id = session['user_id']
    search_term = (request.args.get('q') or '').strip()
    suggestions = get_catalog_suggestions('exercises', user_id, search_term)
    return jsonify({'results': suggestions})

@gym_bp.route('/scheda/aggiorna-serie', methods=['POST'])
@login_required
def aggiorna_serie():
    user_id = session['user_id']
    template_exercise_id = request.form.get('template_exercise_id')
    sets = request.form.get('sets', '')

    if not template_exercise_id:
        return jsonify({'success': False, 'error': 'ID mancante.'}), 400

    query = """
        UPDATE template_exercises SET sets = :sets 
        WHERE id = :teid AND EXISTS (
            SELECT 1 FROM workout_templates wt 
            WHERE wt.id = template_exercises.template_id AND wt.user_id = :uid
        )
    """
    try:
        execute_query(query, {'sets': sets, 'teid': template_exercise_id, 'uid': user_id}, commit=True)
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Errore durante l'aggiornamento delle serie: {e}")
        return jsonify({'success': False, 'error': 'Errore del server.'}), 500


@gym_bp.route('/scheda/riordina-esercizio', methods=['POST'])
@login_required
def riordina_esercizio():
    user_id = session['user_id']
    template_exercise_id = request.form.get('template_exercise_id')
    direction = request.form.get('direction')

    if not template_exercise_id or direction not in {'up', 'down'}:
        return jsonify({'success': False, 'error': 'Parametri non validi.'}), 400

    try:
        te_id = int(template_exercise_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'ID non valido.'}), 400

    record = execute_query(
        'SELECT te.template_id '
        'FROM template_exercises te '
        'JOIN workout_templates wt ON wt.id = te.template_id '
        'WHERE te.id = :teid AND wt.user_id = :uid',
        {'teid': te_id, 'uid': user_id},
        fetchone=True,
    )

    if not record:
        return jsonify({'success': False, 'error': 'Esercizio non trovato.'}), 404

    template_id = record['template_id']
    _ensure_template_exercise_order(template_id)

    exercises = execute_query(
        'SELECT id, sort_order '
        'FROM template_exercises '
        'WHERE template_id = :tid '
        'ORDER BY sort_order, id',
        {'tid': template_id},
        fetchall=True,
    ) or []

    index = next((idx for idx, row in enumerate(exercises) if row['id'] == te_id), None)
    if index is None:
        return jsonify({'success': False, 'error': 'Esercizio non trovato.'}), 404

    swap_index = index - 1 if direction == 'up' else index + 1
    if swap_index < 0 or swap_index >= len(exercises):
        return jsonify({'success': False, 'error': 'Nessun elemento da scambiare.'}), 400

    current_order = exercises[index]['sort_order']
    swap_order = exercises[swap_index]['sort_order']
    swap_id = exercises[swap_index]['id']

    execute_query(
        'UPDATE template_exercises SET sort_order = :order WHERE id = :id',
        {'order': swap_order, 'id': te_id},
    )
    execute_query(
        'UPDATE template_exercises SET sort_order = :order WHERE id = :id',
        {'order': current_order, 'id': swap_id},
        commit=True,
    )

    return jsonify({'success': True})


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
    templates = []
    for t in templates_raw:
        template_dict = dict(t)
        template_dict['slug'] = slugify(template_dict['name'])
        _ensure_template_exercise_order(t['id'])
        exercises = execute_query(
            'SELECT te.id, e.name, e.user_id, te.sets '
            'FROM template_exercises te '
            'JOIN exercises e ON te.exercise_id = e.id '
            'WHERE te.template_id = :tid '
            'ORDER BY te.sort_order, te.id',
            {'tid': t['id']},
            fetchall=True,
        )
        template_dict['exercises'] = [dict(row) for row in exercises]
        templates.append(template_dict)
    
    return render_template('scheda.html', title='Scheda Allenamento', templates=templates)

@gym_bp.route('/scheda/<int:template_id>/modifica_scheda', methods=['GET', 'POST'])
@gym_bp.route('/scheda/modifica_scheda/<template_slug>', methods=['GET', 'POST'], defaults={'template_id': None})
@login_required
def modifica_scheda_dettaglio(template_id=None, template_slug=None):
    user_id = session['user_id']

    template = None
    if template_slug:
        template = _get_template_by_slug(user_id, template_slug)
        if template:
            template_id = template['id']

    if template is None and template_id is not None:
        template = execute_query('SELECT * FROM workout_templates WHERE id = :id AND user_id = :uid', {'id': template_id, 'uid': user_id}, fetchone=True)

    if not template:
        flash('Scheda non trovata o non autorizzata.', 'danger')
        return redirect(url_for('gym.scheda'))

    canonical_slug = slugify(template['name'])
    if request.method == 'GET' and template_slug != canonical_slug:
        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_exercise_to_template':
            exercise_id = request.form.get('exercise_id')
            if exercise_id:
                execute_query(
                    'INSERT INTO template_exercises (template_id, exercise_id, sets, sort_order) '
                    'VALUES (:tid, :eid, :sets, '
                    '        (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM template_exercises WHERE template_id = :tid))',
                    {'tid': template_id, 'eid': exercise_id, 'sets': '1'},
                    commit=True,
                )
                flash('Esercizio aggiunto.', 'success')
            else:
                flash('Nessun esercizio selezionato.', 'danger')
        elif action == 'delete_template_exercise':
            template_exercise_id = request.form.get('template_exercise_id')
            execute_query('DELETE FROM template_exercises WHERE id = :id', {'id': template_exercise_id}, commit=True)
            flash('Esercizio rimosso dalla scheda.', 'success')
        elif action == 'save_template_changes':
            payload_raw = request.form.get('state_payload', '').strip()
            try:
                state_payload = json.loads(payload_raw) if payload_raw else {'items': [], 'deleted': []}
            except json.JSONDecodeError:
                flash('Formato dati non valido. Riprova.', 'danger')
                return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

            items = state_payload.get('items', [])
            deleted_ids = state_payload.get('deleted', [])

            if not isinstance(items, list) or not isinstance(deleted_ids, list):
                flash('Formato dati non valido. Riprova.', 'danger')
                return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

            existing_records = execute_query(
                'SELECT id FROM template_exercises WHERE template_id = :tid',
                {'tid': template_id},
                fetchall=True,
            ) or []
            valid_existing_ids = {row['id'] for row in existing_records}

            normalized_deleted_ids = set()
            for raw_id in deleted_ids:
                try:
                    parsed_id = int(raw_id)
                except (TypeError, ValueError):
                    flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))
                if parsed_id not in valid_existing_ids:
                    flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))
                normalized_deleted_ids.add(parsed_id)

            normalized_items = []
            seen_existing = set()
            for entry in items:
                if not isinstance(entry, dict):
                    flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                entry_type = entry.get('type')
                sets_value = entry.get('sets')
                try:
                    parsed_sets = int(sets_value)
                except (TypeError, ValueError):
                    flash('Inserisci un numero di serie valido per ogni esercizio.', 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                if parsed_sets < 0:
                    flash('Inserisci un numero di serie valido per ogni esercizio.', 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                if entry_type == 'existing':
                    try:
                        template_exercise_id = int(entry.get('template_exercise_id'))
                    except (TypeError, ValueError):
                        flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                    if template_exercise_id not in valid_existing_ids or template_exercise_id in normalized_deleted_ids:
                        flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                    if template_exercise_id in seen_existing:
                        flash('Impossibile salvare le modifiche. Dati duplicati.', 'danger')
                        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                    seen_existing.add(template_exercise_id)
                    normalized_items.append({
                        'type': 'existing',
                        'template_exercise_id': template_exercise_id,
                        'sets': parsed_sets,
                    })
                elif entry_type == 'new':
                    try:
                        exercise_id = int(entry.get('exercise_id'))
                    except (TypeError, ValueError):
                        flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                    exercise_record = execute_query(
                        'SELECT id FROM exercises WHERE id = :eid AND (user_id IS NULL OR user_id = :uid)',
                        {'eid': exercise_id, 'uid': user_id},
                        fetchone=True,
                    )
                    if not exercise_record:
                        flash('Impossibile salvare le modifiche. Esercizio non valido.', 'danger')
                        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

                    normalized_items.append({
                        'type': 'new',
                        'exercise_id': exercise_id,
                        'sets': parsed_sets,
                    })
                else:
                    flash('Impossibile salvare le modifiche. Dati non validi.', 'danger')
                    return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

            missing_existing = valid_existing_ids - seen_existing - normalized_deleted_ids
            if missing_existing:
                flash('Impossibile salvare le modifiche. Alcuni esercizi non sono stati inclusi.', 'danger')
                return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

            try:
                for delete_id in normalized_deleted_ids:
                    execute_query(
                        'DELETE FROM template_exercises WHERE id = :id AND template_id = :tid',
                        {'id': delete_id, 'tid': template_id},
                    )

                sort_order = 1
                for entry in normalized_items:
                    if entry['type'] == 'existing':
                        execute_query(
                            'UPDATE template_exercises SET sets = :sets, sort_order = :sort_order '
                            'WHERE id = :id AND template_id = :tid',
                            {
                                'sets': entry['sets'],
                                'sort_order': sort_order,
                                'id': entry['template_exercise_id'],
                                'tid': template_id,
                            },
                        )
                    else:
                        execute_query(
                            'INSERT INTO template_exercises (template_id, exercise_id, sets, sort_order) '
                            'VALUES (:tid, :eid, :sets, :sort_order)',
                            {
                                'tid': template_id,
                                'eid': entry['exercise_id'],
                                'sets': entry['sets'],
                                'sort_order': sort_order,
                            },
                        )
                    sort_order += 1

                db.session.commit()
                flash('Scheda aggiornata con successo.', 'success')
            except Exception:
                db.session.rollback()
                flash('Errore durante il salvataggio delle modifiche.', 'danger')

            return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))
        return redirect(url_for('gym.modifica_scheda_dettaglio', template_slug=canonical_slug))

    _ensure_template_exercise_order(template_id)
    current_exercises = execute_query(
        'SELECT te.id, e.name, te.sets '
        'FROM template_exercises te '
        'JOIN exercises e ON te.exercise_id = e.id '
        'WHERE te.template_id = :tid '
        'ORDER BY te.sort_order, te.id',
        {'tid': template_id},
        fetchall=True,
    )
    all_exercises = execute_query('SELECT id, name, user_id FROM exercises WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)

    return render_template('modifica_scheda.html',
                           title=f'Modifica {template["name"]}',
                           template=template,
                           template_slug=canonical_slug,
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
    # ... (Il resto del file rimane invariato)
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