# routes/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from secrets import token_hex

from extensions import limiter
from utils import execute_query
from services.communication_service import get_welcome_message

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
@limiter.limit('5 per minute', methods=['POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.home'))
        
    if request.method == 'POST':
        max_attempts = current_app.config.get('SECURITY_MAX_FAILED_LOGINS', 5)
        lockout_minutes = current_app.config.get('SECURITY_LOCKOUT_MINUTES', 15)
        username = request.form['username']
        password_raw = request.form['password']
        password = password_raw.encode('utf-8')
        user = execute_query('SELECT * FROM users WHERE username = :username', {'username': username}, fetchone=True)
        now = datetime.utcnow()

        if user:
            lock_until = user.get('lock_until')
            if lock_until and lock_until > now:
                remaining = lock_until - now
                minutes = max(1, int(remaining.total_seconds() // 60) + (1 if remaining.total_seconds() % 60 else 0))
                message = f"Account temporaneamente bloccato. Riprova tra circa {minutes} minuti."
                return render_template('login.html', title='Login', error=message, username=username)

        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            session.clear()
            session['session_nonce'] = token_hex(16)
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            session['is_superuser'] = user.get('is_superuser', 0)
            session['last_activity_update'] = now.isoformat()

            execute_query(
                'UPDATE users SET failed_login_attempts = 0, lock_until = NULL, last_login_at = :now, last_active_at = :now WHERE id = :id',
                {'now': now, 'id': user['id']},
                commit=True,
            )

            forwarded_for = request.headers.get('X-Forwarded-For', '')
            client_ip = forwarded_for.split(',')[0].strip() if forwarded_for else request.remote_addr
            execute_query(
                'INSERT INTO user_login_activity (user_id, login_at, ip_address) VALUES (:user_id, :login_at, :ip_address)',
                {'user_id': user['id'], 'login_at': now, 'ip_address': client_ip},
                commit=True,
            )

            remember_me = request.form.get('remember_me')
            if remember_me:
                session.permanent = True
            
            if not user['has_seen_welcome_message']:
                flash(get_welcome_message(), 'info')
                execute_query('UPDATE users SET has_seen_welcome_message = 1 WHERE id = :id', {'id': user['id']}, commit=True)
            
            if user['is_admin']:
                return redirect(url_for('admin.admin_generale'))
            else:
                return redirect(url_for('main.home'))
        else:
            if user:
                attempts = (user.get('failed_login_attempts') or 0) + 1
                lock_until_val = None
                error_message = 'Credenziali non valide.'
                if attempts >= max_attempts:
                    lock_until_val = now + timedelta(minutes=lockout_minutes)
                    error_message = 'Account temporaneamente bloccato per troppi tentativi falliti. Riprova più tardi.'
                    attempts = 0
                execute_query(
                    'UPDATE users SET failed_login_attempts = :attempts, lock_until = :lock_until WHERE id = :id',
                    {'attempts': attempts, 'lock_until': lock_until_val, 'id': user['id']},
                    commit=True,
                )
                current_app.logger.warning('Tentativo di login fallito per username: %s', username)
                return render_template('login.html', title='Login', error=error_message, username=username)

            current_app.logger.warning('Tentativo di login fallito per username inesistente: %s', username)
            return render_template('login.html', title='Login', error='Credenziali non valide.', username=username)
    return render_template('login.html', title='Login')

@auth_bp.route('/logout')
def logout():
    session.clear()
    session.pop('last_activity_update', None)
    flash('Logout effettuato con successo.', 'success')
    return redirect(url_for('auth.login'))