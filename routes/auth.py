# routes/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import bcrypt
from functools import wraps
from extensions import db
from utils import execute_query

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Accesso non autorizzato.', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/')
def index():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin.admin_generale'))
        return redirect(url_for('main.home'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.home'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        user = execute_query('SELECT * FROM users WHERE username = :username', {'username': username}, fetchone=True)
        
        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            
            remember_me = request.form.get('remember_me')
            if remember_me:
                session.permanent = True
            
            if not user['has_seen_welcome_message']:
                flash('AVVISO: SE USI QUESTA APP L\'ADMIN PUÒ MODIFICARE O CANCELLARE I TUOI DATI PERCHÉ NON SA PROGRAMMARE. SE NON SEI D\'ACCORDO NON USARE QUESTA APP.', 'warning')
                execute_query('UPDATE users SET has_seen_welcome_message = 1 WHERE id = :id', {'id': user['id']}, commit=True)
            
            if user['is_admin']:
                return redirect(url_for('admin.admin_generale'))
            else:
                return redirect(url_for('main.home'))
        else:
            return render_template('login.html', title='Login', error='Credenziali non valide.')
    return render_template('login.html', title='Login')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logout effettuato con successo.', 'success')
    return redirect(url_for('auth.login'))