# routes/cardio.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import date, datetime, timedelta
from .auth import login_required
from utils import execute_query

cardio_bp = Blueprint('cardio', __name__)

@cardio_bp.route('/corsa')
@login_required
def corsa():
    return render_template('corsa.html', title='Corsa')

@cardio_bp.route('/sessione_corsa', defaults={'date_str': None}, methods=['GET', 'POST'])
@cardio_bp.route('/sessione_corsa/<date_str>', methods=['GET', 'POST'])
@login_required
def sessione_corsa(date_str):
    user_id = session['user_id']
    
    if date_str: current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else: current_date = date.today()

    current_date_str = current_date.strftime('%Y-%m-%d')
    prev_day = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    is_today = (current_date == date.today())
    
    if request.method == 'POST':
        location = request.form.get('location') or 'STRADA'
        activity_type = request.form.get('activity_type') or 'CORSA'
        distance_raw = (request.form.get('distance_km') or '').strip()
        duration_raw = (request.form.get('duration_min') or '').strip()
        incline_raw = (request.form.get('incline') or '').strip() if location == 'TAPPETO' else ''

        form_data = {
            'location': location,
            'activity_type': activity_type,
            'distance_km': distance_raw,
            'duration_min': duration_raw,
            'incline': incline_raw,
        }

        try:
            distance_val = float(distance_raw) if distance_raw else None
            if distance_val is not None and distance_val < 0:
                raise ValueError
        except ValueError:
            flash('La distanza deve essere un numero valido maggiore o uguale a zero.', 'danger')
            return render_template('sessione_corsa.html', title='Sessione Corsa', date_formatted=current_date.strftime('%d %b %y'),
                                   current_date_str=current_date_str, prev_day=prev_day, next_day=next_day,
                                   is_today=is_today, form_data=form_data)

        try:
            duration_val = int(duration_raw) if duration_raw else None
            if duration_val is not None and duration_val < 0:
                raise ValueError
        except ValueError:
            flash('La durata deve essere un numero intero maggiore o uguale a zero.', 'danger')
            return render_template('sessione_corsa.html', title='Sessione Corsa', date_formatted=current_date.strftime('%d %b %y'),
                                   current_date_str=current_date_str, prev_day=prev_day, next_day=next_day,
                                   is_today=is_today, form_data=form_data)

        try:
            incline_val = float(incline_raw) if incline_raw else None
            if incline_val is not None and incline_val < 0:
                raise ValueError
        except ValueError:
            flash('L\'inclinazione deve essere un numero valido maggiore o uguale a zero.', 'danger')
            return render_template('sessione_corsa.html', title='Sessione Corsa', date_formatted=current_date.strftime('%d %b %y'),
                                   current_date_str=current_date_str, prev_day=prev_day, next_day=next_day,
                                   is_today=is_today, form_data=form_data)

        query = "INSERT INTO cardio_log (user_id, record_date, location, activity_type, distance_km, duration_min, incline) VALUES (:user_id, :rd, :loc, :act, :dist, :dur, :inc)"
        params = {
            'user_id': user_id,
            'rd': current_date_str,
            'loc': location,
            'act': activity_type,
            'dist': distance_val,
            'dur': duration_val,
            'inc': incline_val if location == 'TAPPETO' else None,
        }
        execute_query(query, params, commit=True)
        flash('Sessione di corsa salvata.', 'success')
        return redirect(url_for('cardio.diario_corsa'))

    return render_template('sessione_corsa.html', title='Sessione Corsa', date_formatted=current_date.strftime('%d %b %y'),
                           current_date_str=current_date_str, prev_day=prev_day, next_day=next_day, is_today=is_today,
                           form_data=None)

@cardio_bp.route('/diario_corsa')
@login_required
def diario_corsa():
    user_id = session['user_id']
    entries_raw = execute_query('SELECT * FROM cardio_log WHERE user_id = :user_id ORDER BY record_date DESC, id DESC', {'user_id': user_id}, fetchall=True)
    
    entries = []
    for entry in entries_raw:
        entry_dict = dict(entry)
        entry_dict['date_formatted'] = entry['record_date'].strftime('%d %b %y')
        entries.append(entry_dict)

    return render_template('diario_corsa.html', title='Diario Corsa', entries=entries)

@cardio_bp.route('/modifica_corsa/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def modifica_corsa(entry_id):
    user_id = session['user_id']
    
    entry = execute_query('SELECT * FROM cardio_log WHERE id = :id AND user_id = :user_id', {'id': entry_id, 'user_id': user_id}, fetchone=True)
    if not entry:
        flash('Sessione non trovata.', 'danger')
        return redirect(url_for('cardio.diario_corsa'))
    
    if request.method == 'POST':
        location = request.form.get('location') or entry['location']
        activity_type = request.form.get('activity_type') or entry['activity_type']
        distance_raw = (request.form.get('distance_km') or '').strip()
        duration_raw = (request.form.get('duration_min') or '').strip()
        incline_raw = (request.form.get('incline') or '').strip() if location == 'TAPPETO' else ''

        entry_dict = dict(entry)
        entry_dict['date_formatted'] = entry['record_date'].strftime('%d %b %y')
        entry_dict.update({
            'location': location,
            'activity_type': activity_type,
            'distance_km': distance_raw or None,
            'duration_min': duration_raw or None,
            'incline': incline_raw or None,
        })

        try:
            distance_val = float(distance_raw) if distance_raw else None
            if distance_val is not None and distance_val < 0:
                raise ValueError
        except ValueError:
            flash('La distanza deve essere un numero valido maggiore o uguale a zero.', 'danger')
            return render_template('modifica_cardio.html', title='Modifica Corsa', entry=entry_dict)

        try:
            duration_val = int(duration_raw) if duration_raw else None
            if duration_val is not None and duration_val < 0:
                raise ValueError
        except ValueError:
            flash('La durata deve essere un numero intero maggiore o uguale a zero.', 'danger')
            return render_template('modifica_cardio.html', title='Modifica Corsa', entry=entry_dict)

        try:
            incline_val = float(incline_raw) if incline_raw else None
            if incline_val is not None and incline_val < 0:
                raise ValueError
        except ValueError:
            flash('L\'inclinazione deve essere un numero valido maggiore o uguale a zero.', 'danger')
            return render_template('modifica_cardio.html', title='Modifica Corsa', entry=entry_dict)

        query = "UPDATE cardio_log SET location = :loc, activity_type = :act, distance_km = :dist, duration_min = :dur, incline = :inc WHERE id = :id AND user_id = :user_id"
        params = {
            'loc': location,
            'act': activity_type,
            'dist': distance_val,
            'dur': duration_val,
            'inc': incline_val if location == 'TAPPETO' else None,
            'id': entry_id,
            'user_id': user_id,
        }
        execute_query(query, params, commit=True)
        flash('Sessione aggiornata.', 'success')
        return redirect(url_for('cardio.diario_corsa'))

    entry_dict = dict(entry)
    entry_dict['date_formatted'] = entry['record_date'].strftime('%d %b %y')
    return render_template('modifica_cardio.html', title='Modifica Corsa', entry=entry_dict)

@cardio_bp.route('/elimina_corsa', methods=['POST'])
@login_required
def elimina_corsa():
    user_id = session['user_id']
    entry_id = request.form.get('entry_id')
    
    execute_query('DELETE FROM cardio_log WHERE id = :id AND user_id = :user_id', {'id': entry_id, 'user_id': user_id}, commit=True)
    flash('Sessione eliminata.', 'success')
    return redirect(url_for('cardio.diario_corsa'))