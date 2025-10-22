# routes/main.py

from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash, Response, make_response, send_from_directory
from extensions import db
import bcrypt
import os
from datetime import datetime, date, timedelta
import math
import io
import csv
from werkzeug.utils import secure_filename
import uuid
from PIL import Image
from collections import defaultdict
from .auth import login_required
from utils import execute_query, is_valid_time_format, allowed_file

main_bp = Blueprint('main', __name__)

@main_bp.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

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
    profile = execute_query('SELECT profile_image_file FROM user_profile WHERE user_id = :user_id', {'user_id': session['user_id']}, fetchone=True)
    profile_image = profile['profile_image_file'] if profile else None
    return render_template('home.html', title='Home', profile_image=profile_image)

@main_bp.route('/impostazioni',methods=['GET','POST'])
@login_required
def impostazioni():
    user_id=session['user_id']
    if request.method=='POST':
        action=request.form.get('action')
        user = execute_query('SELECT * FROM users WHERE id = :id', {'id': user_id}, fetchone=True)

        if action=='change_password':
            current_password=request.form.get('current_password').encode('utf-8');new_password=request.form.get('new_password').encode('utf-8')
            if bcrypt.checkpw(current_password, user['password'].encode('utf-8')):
                hashed_pw=bcrypt.hashpw(new_password,bcrypt.gensalt()).decode('utf-8')
                execute_query('UPDATE users SET password = :password WHERE id = :id', {'password': hashed_pw, 'id': user_id}, commit=True)
                flash('Password aggiornata.','success')
            else:
                flash('Password attuale non corretta.','danger')
            return redirect(url_for('main.impostazioni'))
        
        elif action=='export_data':
            output=io.StringIO();writer=csv.writer(output,delimiter=';');writer.writerow(['DATI GIORNALIERI'])
            daily_data_rows = execute_query('SELECT record_date, weight, weight_time, sleep, sleep_quality, calories, neck, waist, measure_time, day_type FROM daily_data WHERE user_id = :user_id ORDER BY record_date', {'user_id': user_id}, fetchall=True)
            if daily_data_rows:
                writer.writerow(daily_data_rows[0].keys())
                for row in daily_data_rows: writer.writerow(row.values())
            writer.writerow([]);writer.writerow(['DIARIO ALIMENTARE'])
            diet_log_rows = execute_query('SELECT dl.log_date, f.name, dl.weight, dl.protein, dl.carbs, dl.fat, dl.calories FROM diet_log dl JOIN foods f ON dl.food_id = f.id WHERE dl.user_id = :user_id ORDER BY dl.log_date', {'user_id': user_id}, fetchall=True)
            if diet_log_rows:
                writer.writerow(diet_log_rows[0].keys())
                for row in diet_log_rows: writer.writerow(row.values())
            output.seek(0);return Response(output,mimetype="text/csv",headers={"Content-Disposition":"attachment;filename=logbook_export.csv"})
        
        elif action=='delete_account':
            password_confirm=request.form.get('password_confirm').encode('utf-8')
            if bcrypt.checkpw(password_confirm, user['password'].encode('utf-8')):
                if session.get('is_admin'):
                    flash('Gli amministratori non possono eliminare il proprio account.', 'danger')
                    return redirect(url_for('main.impostazioni'))
                profile_to_delete = execute_query('SELECT profile_image_file FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
                if profile_to_delete and profile_to_delete['profile_image_file']:
                    try:
                        file_path = os.path.join('static', 'profile_pics', profile_to_delete['profile_image_file'])
                        if os.path.exists(file_path): os.remove(file_path)
                    except Exception as e:
                        print(f"Errore durante l'eliminazione del file immagine per l'utente {user_id}: {e}")
                
                execute_query('DELETE FROM users WHERE id = :id', {'id': user_id}, commit=True)
                session.clear()
                flash('Account eliminato con successo.','success')
                return redirect(url_for('auth.login'))
            else:
                flash('Password non corretta.','danger')
                return redirect(url_for('main.impostazioni'))
        
        elif action=='upload_pic':
            file=request.files.get('profile_pic')
            if file and file.filename!='' and allowed_file(file.filename):
                profile=execute_query('SELECT profile_image_file FROM user_profile WHERE user_id = :user_id',{'user_id':user_id}, fetchone=True)
                if profile and profile['profile_image_file']:
                    try:os.remove(os.path.join('static', 'profile_pics', profile['profile_image_file']))
                    except Exception as e:print(f"Errore durante la sostituzione dell'immagine: {e}")
                extension=file.filename.rsplit('.',1)[1].lower();new_filename=secure_filename(f"{uuid.uuid4()}.{extension}");filepath=os.path.join('static', 'profile_pics',new_filename)
                try:
                    output_size=(300,300);img=Image.open(file.stream);img.thumbnail(output_size);img.save(filepath)
                    query = "INSERT INTO user_profile (user_id, profile_image_file) VALUES (:user_id, :filename) ON CONFLICT(user_id) DO UPDATE SET profile_image_file = EXCLUDED.profile_image_file"
                    execute_query(query, {'user_id': user_id, 'filename': new_filename}, commit=True)
                    flash('Immagine aggiornata.','success')
                except Exception as e:
                    flash(f'Errore durante il salvataggio dell\'immagine: {e}','danger')
            else:
                flash('File non valido o non selezionato.','danger')
            return redirect(url_for('main.impostazioni'))

        elif action=='delete_pic':
            profile=execute_query('SELECT profile_image_file FROM user_profile WHERE user_id = :user_id',{'user_id':user_id}, fetchone=True)
            if profile and profile['profile_image_file']:
                try:os.remove(os.path.join('static', 'profile_pics', profile['profile_image_file']))
                except Exception as e:print(f"Errore durante l'eliminazione dell'immagine: {e}")
                execute_query('UPDATE user_profile SET profile_image_file = NULL WHERE user_id = :user_id',{'user_id':user_id}, commit=True)
                flash('Immagine eliminata.','success')
            return redirect(url_for('main.impostazioni'))
    
    profile = execute_query('SELECT * FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    return render_template('impostazioni.html',title='Impostazioni', profile=profile or {})

@main_bp.route('/utente',methods=['GET','POST'])
@login_required
def utente():
    user_id=session['user_id']
    if request.method=='POST':
        action=request.form.get('action')
        if action=='update_data':
            birth_date=request.form.get('birth_date'); height=request.form.get('height'); gender=request.form.get('gender')
            query = "INSERT INTO user_profile (user_id, birth_date, height, gender) VALUES (:user_id, :birth_date, :height, :gender) ON CONFLICT(user_id) DO UPDATE SET birth_date = EXCLUDED.birth_date, height = EXCLUDED.height, gender = EXCLUDED.gender"
            execute_query(query, {'user_id': user_id, 'birth_date': birth_date, 'height': height, 'gender': gender}, commit=True)
            flash('Dati anagrafici aggiornati.','success')
        return redirect(url_for('main.utente'))

    profile=execute_query('SELECT * FROM user_profile WHERE user_id = :user_id',{'user_id':user_id}, fetchone=True)
    return render_template('utente.html',title='Dati Personali',profile=profile or{})

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
                if height_cm > 0:
                    if gender == 'F' and entry.get('waist') and entry.get('hip') and entry.get('neck'):
                        entry_dict['bfp'] = 495 / (1.29579 - 0.35004 * math.log10(entry['waist'] + entry['hip'] - entry['neck']) + 0.22100 * math.log10(height_cm)) - 450
                    elif gender == 'M' and entry.get('waist') and entry.get('neck'):
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
            
        # --- MODIFICA QUI: Rimossa la conversione strptime ---
        entry_dict['date_formatted'] = record_date.strftime('%d %b %y')
        entries.append(entry_dict)
        
    return render_template('generale.html', title='Generale', entries=entries)

@main_bp.route('/misure',defaults={'date_str':None},methods=['GET','POST'])
@main_bp.route('/misure/<date_str>',methods=['GET','POST'])
@login_required
def misure(date_str):
    user_id=session['user_id']
    if date_str:current_date=datetime.strptime(date_str,'%Y-%m-%d').date()
    else:current_date=date.today()
    current_date_str=current_date.strftime('%Y-%m-%d');prev_day=(current_date-timedelta(days=1)).strftime('%Y-%m-%d');next_day=(current_date+timedelta(days=1)).strftime('%Y-%m-%d');is_today=(current_date==date.today())
    
    profile = execute_query('SELECT gender FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    gender = profile['gender'] if profile and profile.get('gender') else 'M'

    if request.method=='POST':
        weight_time=request.form.get('weight_time');measure_time=request.form.get('measure_time')
        if not is_valid_time_format(weight_time) or not is_valid_time_format(measure_time):
            flash('Formato orario non valido. Usa HH:MM.','danger')
            misure_giorno=execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date',{'user_id': user_id, 'date': current_date_str}, fetchone=True)
            return render_template('misure.html',title='Misure',date_formatted=current_date.strftime('%d %b %y'),misure=misure_giorno or{},prev_day=prev_day,next_day=next_day,is_today=is_today,current_date_str=current_date_str, gender=gender)
        
        bfp_mode = request.form.get('bfp-mode-selector')
        try:
            form_values = {
                'weight': float(request.form.get('weight')) if request.form.get('weight') else None,
                'sleep_quality': int(request.form.get('sleep_quality')) if request.form.get('sleep_quality') else None,
                'neck': float(request.form.get('neck')) if request.form.get('neck') else None,
                'waist': float(request.form.get('waist')) if request.form.get('waist') else None,
                'hip': float(request.form.get('hip')) if request.form.get('hip') else None,
                'bfp_manual': float(request.form.get('bfp_manual')) if request.form.get('bfp_manual') else None
            }
            for key, value in form_values.items():
                if value is not None and value < 0:
                    flash(f'Il valore per "{key}" non può essere negativo.', 'danger')
                    misure_giorno=execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date',{'user_id': user_id, 'date': current_date_str}, fetchone=True)
                    return render_template('misure.html',title='Misure',date_formatted=current_date.strftime('%d %b %y'),misure=misure_giorno or{},prev_day=prev_day,next_day=next_day,is_today=is_today,current_date_str=current_date_str, gender=gender)
            form_data={
                'weight': form_values['weight'], 'weight_time':weight_time or None,
                'sleep':request.form.get('sleep') or None, 'sleep_quality': form_values['sleep_quality'],
                'neck': form_values['neck'] if bfp_mode == 'formula' else None,
                'waist': form_values['waist'] if bfp_mode == 'formula' else None,
                'hip': form_values['hip'] if bfp_mode == 'formula' else None,
                'measure_time': measure_time if bfp_mode == 'formula' else None,
                'bfp_manual': form_values['bfp_manual'] if bfp_mode == 'manual' else None
            }
        except (ValueError, TypeError):
             flash('Inserisci solo valori numerici validi.', 'danger')
             return redirect(url_for('main.misure', date_str=current_date_str))

        query = "INSERT INTO daily_data (user_id, record_date, weight, weight_time, sleep, sleep_quality, neck, waist, hip, measure_time, bfp_manual) VALUES (:user_id, :record_date, :weight, :weight_time, :sleep, :sleep_quality, :neck, :waist, :hip, :measure_time, :bfp_manual) ON CONFLICT(user_id, record_date) DO UPDATE SET weight=excluded.weight, weight_time=excluded.weight_time, sleep=excluded.sleep, sleep_quality=excluded.sleep_quality, neck=excluded.neck, waist=excluded.waist, hip=excluded.hip, measure_time=excluded.measure_time, bfp_manual=excluded.bfp_manual"
        params = {'user_id': user_id, 'record_date': current_date_str, **form_data}
        execute_query(query, params, commit=True)
        flash('Misure salvate con successo.', 'success')
        return redirect(url_for('main.generale'))
    
    misure_giorno=execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date',{'user_id': user_id, 'date': current_date_str}, fetchone=True)
    return render_template('misure.html',title='Misure',date_formatted=current_date.strftime('%d %b %y'),misure=misure_giorno or{},prev_day=prev_day,next_day=next_day,is_today=is_today,current_date_str=current_date_str, gender=gender)

@main_bp.route('/note',methods=['GET','POST'])
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

@main_bp.route('/modifica_misure/<record_date>',methods=['GET','POST'])
@login_required
def modifica_misure(record_date):
    user_id=session['user_id']
    profile = execute_query('SELECT gender FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchone=True)
    gender = profile['gender'] if profile and profile.get('gender') else 'M'

    if request.method=='POST':
        weight_time=request.form.get('weight_time');measure_time=request.form.get('measure_time')
        if not is_valid_time_format(weight_time) or not is_valid_time_format(measure_time):
            flash('Formato orario non valido. Usa HH:MM.','danger')
            misure=execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date',{'user_id':user_id, 'date':record_date}, fetchone=True)
            date_obj = datetime.strptime(record_date,'%Y-%m-%d').date()
            return render_template('modifica_misure.html',title=f'Modifica {date_obj.strftime("%d %b %y")}',misure=misure,date_formatted=date_obj.strftime("%d %b %y"),record_date=record_date, gender=gender)
        
        bfp_mode = request.form.get('bfp-mode-selector')
        try:
            form_values = {
                'weight': float(request.form.get('weight')) if request.form.get('weight') else None,
                'sleep_quality': int(request.form.get('sleep_quality')) if request.form.get('sleep_quality') else None,
                'neck': float(request.form.get('neck')) if request.form.get('neck') else None,
                'waist': float(request.form.get('waist')) if request.form.get('waist') else None,
                'hip': float(request.form.get('hip')) if request.form.get('hip') else None,
                'bfp_manual': float(request.form.get('bfp_manual')) if request.form.get('bfp_manual') else None
            }
            for key, value in form_values.items():
                if value is not None and value < 0:
                    flash(f'Il valore per "{key}" non può essere negativo.', 'danger')
                    misure=execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date',{'user_id':user_id, 'date':record_date}, fetchone=True)
                    date_obj = datetime.strptime(record_date,'%Y-%m-%d').date()
                    return render_template('modifica_misure.html',title=f'Modifica {date_obj.strftime("%d %b %y")}',misure=misure,date_formatted=date_obj.strftime("%d %b %y"),record_date=record_date, gender=gender)
            form_data={
                'weight': form_values['weight'], 'weight_time':weight_time or None,
                'sleep':request.form.get('sleep') or None, 'sleep_quality': form_values['sleep_quality'],
                'neck': form_values['neck'] if bfp_mode == 'formula' else None,
                'waist': form_values['waist'] if bfp_mode == 'formula' else None,
                'hip': form_values['hip'] if bfp_mode == 'formula' else None,
                'measure_time': measure_time if bfp_mode == 'formula' else None,
                'bfp_manual': form_values['bfp_manual'] if bfp_mode == 'manual' else None
            }
        except (ValueError, TypeError):
             flash('Inserisci solo valori numerici validi.', 'danger')
             return redirect(url_for('main.modifica_misure', record_date=record_date))

        query = "INSERT INTO daily_data (user_id, record_date, weight, weight_time, sleep, sleep_quality, neck, waist, hip, measure_time, bfp_manual) VALUES (:user_id, :record_date, :weight, :weight_time, :sleep, :sleep_quality, :neck, :waist, :hip, :measure_time, :bfp_manual) ON CONFLICT(user_id, record_date) DO UPDATE SET weight=excluded.weight, weight_time=excluded.weight_time, sleep=excluded.sleep, sleep_quality=excluded.sleep_quality, neck=excluded.neck, waist=excluded.waist, hip=excluded.hip, measure_time=excluded.measure_time, bfp_manual=excluded.bfp_manual"
        params = {'user_id': user_id, 'record_date': record_date, **form_data}
        execute_query(query, params, commit=True)
        flash('Misure aggiornate con successo.', 'success');return redirect(url_for('main.generale'))
    
    misure=execute_query('SELECT * FROM daily_data WHERE user_id = :user_id AND record_date = :date',{'user_id':user_id, 'date':record_date}, fetchone=True)
    if not misure:return redirect(url_for('main.generale'))
    date_obj = datetime.strptime(record_date,'%Y-%m-%d').date()
    return render_template('modifica_misure.html',title=f'Modifica {date_obj.strftime("%d %b %y")}',misure=misure,date_formatted=date_obj.strftime("%d %b %y"),record_date=record_date, gender=gender)

@main_bp.route('/elimina_giorno',methods=['POST'])
@login_required
def elimina_giorno():
    date_to_delete = request.form.get('date')
    user_id = session['user_id']
    try:
        execute_query('DELETE FROM workout_sessions WHERE user_id = :user_id AND record_date = :date', {'user_id':user_id, 'date':date_to_delete}, commit=True)
        execute_query('DELETE FROM cardio_log WHERE user_id = :user_id AND record_date = :date', {'user_id':user_id, 'date':date_to_delete}, commit=True)
        execute_query('DELETE FROM diet_log WHERE user_id = :user_id AND log_date = :date', {'user_id':user_id, 'date':date_to_delete}, commit=True)
        execute_query('DELETE FROM daily_data WHERE user_id = :user_id AND record_date = :date', {'user_id':user_id, 'date':date_to_delete}, commit=True)
        flash(f'Tutti i dati del giorno {date_to_delete} sono stati eliminati.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Si è verificato un errore durante l\'eliminazione: {e}', 'danger')
    return redirect(url_for('main.generale'))

@main_bp.route('/allenamento')
@login_required
def allenamento():
    return render_template('allenamento.html', title='Allenamento')