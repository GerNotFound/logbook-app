# routes/nutrition.py
from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash
from datetime import date, datetime, timedelta
from .auth import login_required
from utils import execute_query
from sqlalchemy.exc import IntegrityError
from extensions import db

nutrition_bp = Blueprint('nutrition', __name__)

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
            food_name = request.form.get('food_name')
            food_data = execute_query('SELECT * FROM foods WHERE name = :name AND (user_id IS NULL OR user_id = :uid)', {'name': food_name, 'uid': user_id}, fetchone=True)
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
                flash('Alimento non trovato o peso non valido.', 'danger')

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

    food_names_rows = execute_query('SELECT name FROM foods WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    food_names = [row['name'] for row in food_names_rows]
    diet_log = execute_query('SELECT dl.id, f.name as food_name, dl.weight, dl.protein, dl.carbs, dl.fat, dl.calories FROM diet_log dl JOIN foods f ON dl.food_id = f.id WHERE dl.user_id = :uid AND dl.log_date = :ld', 
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
    
    return render_template('dieta.html', title='Dieta', food_names=food_names, diet_log=diet_log, totals=totals, date_formatted=current_date.strftime('%d %b %y'), target_macros=target_macros, current_day_type=current_day_type, current_date_str=current_date_str, prev_day=prev_day, next_day=next_day, is_today=is_today)

@nutrition_bp.route('/alimenti', methods=['GET', 'POST'])
@login_required
def alimenti():
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        food_id = request.form.get('food_id')

        if action == 'add':
            name = request.form.get('name'); protein = float(request.form.get('protein', 0)); carbs = float(request.form.get('carbs', 0)); fat = float(request.form.get('fat', 0))
            calories = (protein * 4) + (carbs * 4) + (fat * 9)
            try:
                execute_query('INSERT INTO foods (name, protein, carbs, fat, calories, user_id) VALUES (:name, :p, :c, :f, :cal, :uid)',
                              {'name': name, 'p': protein, 'c': carbs, 'f': fat, 'cal': calories, 'uid': user_id}, commit=True)
                flash('Alimento personale aggiunto.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f"Errore: L'alimento '{name}' esiste già.", 'danger')

        elif action == 'delete':
            execute_query('DELETE FROM foods WHERE id = :id AND user_id = :uid', {'id': food_id, 'uid': user_id}, commit=True)
            flash('Alimento personale eliminato.', 'success')
        
        # NUOVA LOGICA: Rinomina Alimento
        elif action == 'rename_food':
            new_name = request.form.get('new_food_name')
            if new_name and food_id:
                try:
                    query = "UPDATE foods SET name = :name WHERE id = :id AND user_id = :uid"
                    execute_query(query, {'name': new_name, 'id': food_id, 'uid': user_id}, commit=True)
                    flash('Alimento rinominato con successo.', 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(f"Errore: Esiste già un alimento con il nome '{new_name}'.", 'danger')

        if food_id:
            return redirect(url_for('nutrition.alimenti', _anchor=f"food-{food_id}"))
        return redirect(url_for('nutrition.alimenti'))

    foods = execute_query('SELECT * FROM foods WHERE user_id IS NULL OR user_id = :uid ORDER BY name', {'uid': user_id}, fetchall=True)
    return render_template('alimenti.html', title='Database Alimenti', foods=foods)

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