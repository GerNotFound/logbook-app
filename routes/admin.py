# routes/admin.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, current_app
import bcrypt
from datetime import datetime, timedelta, date
from sqlalchemy.exc import IntegrityError
from collections import defaultdict
from .auth import login_required, admin_required
from extensions import db
from utils import execute_query
from services.admin_service import build_user_export_archive
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@login_required
@admin_required
def admin_generale():
    return render_template('admin_generale.html', title='Admin Generale')

@admin_bp.route('/utenti', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_utenti():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            username = request.form['new_username']
            password = request.form['new_password']
            password_confirm = request.form['new_password_confirm']
            if password != password_confirm:
                flash('Le password non coincidono.', 'danger')
            else:
                hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                try:
                    execute_query("INSERT INTO users (username, password) VALUES (:username, :password)", 
                                  {'username': username, 'password': hashed_pw}, commit=True)
                    flash('Utente aggiunto con successo.', 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: L'utente '{username}' esiste già.", 'danger')
        return redirect(url_for('admin.admin_utenti'))

    search_term = request.args.get('search', '')
    query = "SELECT id, username, last_active_at FROM users WHERE is_admin = 0"
    params = {}
    if search_term:
        query += " AND (username ILIKE :search OR CAST(id AS TEXT) ILIKE :search)"
        params['search'] = f'%{search_term}%'
    query += " ORDER BY username"
    
    users = execute_query(query, params, fetchall=True)
    online_window = current_app.config.get('SECURITY_ONLINE_THRESHOLD_MINUTES', 5)
    online_cutoff = datetime.utcnow() - timedelta(minutes=online_window)
    for user in users:
        last_active = user.get('last_active_at')
        if isinstance(last_active, str):
            try:
                last_active = datetime.fromisoformat(last_active)
            except ValueError:
                last_active = None
        user['is_online'] = bool(last_active and last_active >= online_cutoff)
    return render_template('admin_utenti.html', title='Admin Utenti', users=users, search_term=search_term)

@admin_bp.route('/utente/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_utente_dettaglio(user_id):
    user = execute_query('SELECT * FROM users WHERE id = :id AND is_admin = 0', {'id': user_id}, fetchone=True)
    if not user:
        flash('Utente non trovato.', 'danger')
        return redirect(url_for('admin.admin_utenti'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            new_password = request.form.get('new_password')
            if new_password:
                hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                execute_query('UPDATE users SET password = :pw WHERE id = :id', {'pw': hashed_pw, 'id': user_id}, commit=True)
                flash(f'Password per {user["username"]} aggiornata.', 'success')
            else:
                flash('Il campo password non può essere vuoto.', 'warning')
            return redirect(url_for('admin.admin_utente_dettaglio', user_id=user_id))
        elif action == 'delete_account':
            profile_to_delete = execute_query('SELECT profile_image_file FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
            if profile_to_delete and profile_to_delete.get('profile_image_file'):
                try:
                    file_path = os.path.join('static', 'profile_pics', profile_to_delete['profile_image_file'])
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Errore durante l'eliminazione del file immagine per l'utente {user_id}: {e}")
            
            execute_query('DELETE FROM users WHERE id = :id', {'id': user_id}, commit=True)
            
            flash(f'Utente {user["username"]} e tutti i suoi dati sono stati eliminati con successo.', 'success')
            return redirect(url_for('admin.admin_utenti'))

    login_logs = execute_query(
        'SELECT login_at, ip_address FROM user_login_activity WHERE user_id = :id ORDER BY login_at DESC LIMIT 50',
        {'id': user_id},
        fetchall=True,
    )

    return render_template(
        'admin_utente_dettaglio.html',
        title=f'Gestione {user["username"]}',
        user=user,
        login_logs=login_logs or [],
    )


@admin_bp.route('/utente/<int:user_id>/export', methods=['POST'])
@login_required
@admin_required
def admin_utente_export(user_id):
    user = execute_query('SELECT username FROM users WHERE id = :id AND is_admin = 0', {'id': user_id}, fetchone=True)
    if not user:
        flash('Utente non trovato.', 'danger')
        return redirect(url_for('admin.admin_utenti'))

    spool_threshold = current_app.config.get('ADMIN_EXPORT_SPOOL_THRESHOLD', 5 * 1024 * 1024)
    archive_file = build_user_export_archive(user_id, spool_threshold=spool_threshold)
    return send_file(
        archive_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{user['username']}_export.zip",
    )

@admin_bp.route('/utente/<int:user_id>/schede', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_utente_schede(user_id):
    user = execute_query('SELECT * FROM users WHERE id = :id', {'id': user_id}, fetchone=True)
    if not user: return redirect(url_for('admin.admin_utenti'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete_template':
            template_id = request.form.get('template_id')
            execute_query('DELETE FROM workout_templates WHERE id = :id AND user_id = :user_id', {'id': template_id, 'user_id': user_id}, commit=True)
            flash('Scheda eliminata.', 'success')
        return redirect(url_for('admin.admin_utente_schede', user_id=user_id))
        
    schede = execute_query('SELECT * FROM workout_templates WHERE user_id = :user_id ORDER BY name', {'user_id': user_id}, fetchall=True)
    return render_template('admin_utente_schede.html', title=f'Schede di {user["username"]}', user=user, schede=schede)

@admin_bp.route('/utente/<int:user_id>/scheda/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_utente_scheda_modifica(user_id, template_id):
    user = execute_query('SELECT * FROM users WHERE id = :id', {'id': user_id}, fetchone=True)
    template = execute_query('SELECT * FROM workout_templates WHERE id = :id AND user_id = :user_id', {'id': template_id, 'user_id': user_id}, fetchone=True)
    if not user or not template: return redirect(url_for('admin.admin_utenti'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_exercise':
            exercise_id = request.form.get('exercise_id')
            sets = request.form.get('sets')
            if exercise_id and sets:
                execute_query('INSERT INTO template_exercises (template_id, exercise_id, sets) VALUES (:tid, :eid, :sets)',
                              {'tid': template_id, 'eid': exercise_id, 'sets': sets}, commit=True)
                flash('Esercizio aggiunto alla scheda.', 'success')
        elif action == 'delete_template_exercise':
            template_exercise_id = request.form.get('template_exercise_id')
            execute_query('DELETE FROM template_exercises WHERE id = :id', {'id': template_exercise_id}, commit=True)
            flash('Esercizio rimosso dalla scheda.', 'success')
        return redirect(url_for('admin.admin_utente_scheda_modifica', user_id=user_id, template_id=template_id))

    template_exercises = execute_query('SELECT te.id, e.name, te.sets FROM template_exercises te JOIN exercises e ON te.exercise_id = e.id WHERE te.template_id = :tid ORDER BY te.id', {'tid': template_id}, fetchall=True)
    all_exercises = execute_query('SELECT * FROM exercises WHERE user_id IS NULL OR user_id = :user_id ORDER BY name', {'user_id': user_id}, fetchall=True)
    
    return render_template('admin_utente_scheda_modifica.html', title=f'Modifica {template["name"]}', user=user, template=template, template_exercises=template_exercises, all_exercises=all_exercises)

@admin_bp.route('/utente/<int:user_id>/alimenti', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_utente_alimenti(user_id):
    user = execute_query('SELECT * FROM users WHERE id = :id', {'id': user_id}, fetchone=True)
    if not user: return redirect(url_for('admin.admin_utenti'))

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_food':
            food_id = request.form.get('food_id')
            name = request.form.get('name')
            protein = float(request.form.get('protein', 0))
            carbs = float(request.form.get('carbs', 0))
            fat = float(request.form.get('fat', 0))
            execute_query('UPDATE foods SET name = :name, protein = :p, carbs = :c, fat = :f WHERE id = :id AND user_id = :user_id', 
                          {'name': name, 'p': protein, 'c': carbs, 'f': fat, 'id': food_id, 'user_id': user_id}, commit=True)
            flash('Alimento aggiornato.', 'success')
        elif action == 'delete_food':
            food_id = request.form.get('food_id')
            execute_query('DELETE FROM foods WHERE id = :id AND user_id = :user_id', {'id': food_id, 'user_id': user_id}, commit=True)
            flash('Alimento personale eliminato.', 'success')
        return redirect(url_for('admin.admin_utente_alimenti', user_id=user_id))

    alimenti = execute_query('SELECT * FROM foods WHERE user_id = :user_id ORDER BY name', {'user_id': user_id}, fetchall=True)
    return render_template('admin_utente_alimenti.html', title=f'Alimenti di {user["username"]}', user=user, alimenti=alimenti)

@admin_bp.route('/utente/<int:user_id>/diario_palestra')
@login_required
@admin_required
def admin_utente_diario_palestra(user_id):
    user = execute_query('SELECT * FROM users WHERE id = :id', {'id': user_id}, fetchone=True)
    if not user: return redirect(url_for('admin.admin_utenti'))
    
    logs_raw = execute_query('SELECT wl.record_date, wl.session_timestamp, e.name as exercise_name, wl.set_number, wl.reps, wl.weight FROM workout_log wl JOIN exercises e ON wl.exercise_id = e.id WHERE wl.user_id = :user_id ORDER BY wl.record_date DESC, wl.session_timestamp DESC, wl.id ASC', {'user_id': user_id}, fetchall=True)
    workouts_by_day = defaultdict(lambda: {'date_formatted': '', 'sessions': defaultdict(lambda: {'time_formatted': '', 'exercises': defaultdict(list)})})
    for row in logs_raw:
        day, ts, ex_name = row['record_date'], row['session_timestamp'], row['exercise_name']
        workouts_by_day[day]['date_formatted'] = day.strftime('%d %b %y')
        workouts_by_day[day]['sessions'][ts]['time_formatted'] = datetime.strptime(ts, '%Y%m%d%H%M%S').strftime('%H:%M')
        workouts_by_day[day]['sessions'][ts]['exercises'][ex_name].append({'set': row['set_number'], 'reps': row['reps'], 'weight': row['weight']})
    final_workouts = {day: {'date_formatted': data['date_formatted'], 'sessions': {ts: dict(s_data) for ts, s_data in data['sessions'].items()}} for day, data in workouts_by_day.items()}
    return render_template('admin_utente_diario_palestra.html', title=f'Diario Palestra di {user["username"]}', user=user, workouts_by_day=final_workouts)

@admin_bp.route('/utente/<int:user_id>/diario_corsa')
@login_required
@admin_required
def admin_utente_diario_corsa(user_id):
    user = execute_query('SELECT * FROM users WHERE id = :id', {'id': user_id}, fetchone=True)
    if not user: return redirect(url_for('admin.admin_utenti'))
    entries_raw = execute_query('SELECT * FROM cardio_log WHERE user_id = :user_id ORDER BY record_date DESC, id DESC', {'user_id': user_id}, fetchall=True)
    entries = [{'date_formatted': entry['record_date'].strftime('%d %b %y'), **entry} for entry in entries_raw]
    return render_template('admin_utente_diario_corsa.html', title=f'Diario Corsa di {user["username"]}', user=user, entries=entries)

@admin_bp.route('/esercizi', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_esercizi():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_exercise':
            name = request.form.get('name')
            if name:
                execute_query('INSERT INTO exercises (name, user_id) VALUES (:name, NULL)', {'name': name}, commit=True)
                flash('Esercizio globale aggiunto.', 'success')
        elif action == 'delete_exercise':
            exercise_id = request.form.get('exercise_id')
            execute_query('DELETE FROM exercises WHERE id = :id AND user_id IS NULL', {'id': exercise_id}, commit=True)
            flash('Esercizio globale eliminato.', 'success')
        return redirect(url_for('admin.admin_esercizi'))
    exercises = execute_query('SELECT * FROM exercises WHERE user_id IS NULL ORDER BY name', fetchall=True)
    return render_template('admin_esercizi.html', title='Admin Esercizi', exercises=exercises)

@admin_bp.route('/alimenti', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_alimenti():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            protein = float(request.form.get('protein', 0)); carbs = float(request.form.get('carbs', 0)); fat = float(request.form.get('fat', 0))
            calories = (protein * 4) + (carbs * 4) + (fat * 9)
            execute_query('INSERT INTO foods (name, protein, carbs, fat, calories, user_id) VALUES (:name, :p, :c, :f, :cal, NULL)',
                          {'name': name, 'p': protein, 'c': carbs, 'f': fat, 'cal': calories}, commit=True)
            flash('Alimento globale aggiunto.', 'success')
        elif action == 'delete':
            food_id = request.form.get('food_id')
            execute_query('DELETE FROM foods WHERE id = :id AND user_id IS NULL', {'id': food_id}, commit=True)
            flash('Alimento globale eliminato.', 'success')
        return redirect(url_for('admin.admin_alimenti'))
    foods = execute_query('SELECT * FROM foods WHERE user_id IS NULL ORDER BY name', fetchall=True)
    return render_template('admin_alimenti.html', title='Admin Alimenti', foods=foods)

@admin_bp.route('/note_condivise')
@login_required
@admin_required
def admin_note_condivise():
    query = "SELECT u.username, un.content_shared FROM user_notes un JOIN users u ON un.user_id = u.id WHERE u.is_admin = 0 AND un.content_shared IS NOT NULL AND un.content_shared != '' ORDER BY u.username"
    notes = execute_query(query, fetchall=True)
    return render_template('admin_note_condivise.html', title='Note Utenti', notes=notes)