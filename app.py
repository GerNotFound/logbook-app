import os
from datetime import datetime, timedelta
from flask import Flask, session
from extensions import db, csrf, talisman
from dotenv import load_dotenv
import commands # NUOVA IMPORTAZIONE
from utils import ensure_user_security_columns, execute_query

load_dotenv()

def create_app():
    app = Flask(__name__)

    # --- CONFIGURAZIONE ---
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # MODIFICA: Fallisce se la SECRET_KEY non è impostata in produzione
    if os.environ.get('FLASK_ENV') == 'production' and not os.environ.get('SECRET_KEY'):
        raise ValueError("Nessuna SECRET_KEY impostata per l'ambiente di produzione")
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-insecure') 
    
    app.debug = os.environ.get('FLASK_ENV') == 'development'

    app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
    app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    
    app.config.update(
        SESSION_COOKIE_SECURE=not app.debug,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

    db.init_app(app)
    csrf.init_app(app)
    
    csp = {
        'default-src': "'self'",
        'script-src': ["'self'", 'https://cdn.jsdelivr.net', "'unsafe-inline'"],
        'style-src': ["'self'", 'https://cdn.jsdelivr.net', 'https://fonts.googleapis.com', "'unsafe-inline'"],
        'font-src': ["'self'", 'https://fonts.gstatic.com', 'https://cdn.jsdelivr.net'],
        'img-src': ["'self'", 'data:']
    }
    
    talisman.init_app(app, content_security_policy=csp, force_https=not app.debug)

    # NUOVA SEZIONE: Registra i comandi CLI
    commands.init_app(app)

    with app.app_context():
        ensure_user_security_columns()

        @app.before_request
        def update_last_active_timestamp():
            user_id = session.get('user_id')
            if not user_id:
                session.pop('last_activity_update', None)
                return

            now = datetime.utcnow()
            last_update_iso = session.get('last_activity_update')
            should_update = True
            if last_update_iso:
                try:
                    last_update = datetime.fromisoformat(last_update_iso)
                    should_update = (now - last_update) > timedelta(minutes=1)
                except ValueError:
                    should_update = True

            if should_update:
                execute_query(
                    'UPDATE users SET last_active_at = :ts WHERE id = :uid',
                    {'ts': now, 'uid': user_id},
                    commit=True,
                )
                session['last_activity_update'] = now.isoformat()

        @app.context_processor
        def inject_version():
            try:
                with open('versione.txt', 'r') as f:
                    version = f.read().strip()
            except FileNotFoundError:
                version = 'N/D'
            return dict(app_version=version)
        
        from routes import main_bp, auth_bp, nutrition_bp, gym_bp, cardio_bp, admin_bp
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(nutrition_bp)
        app.register_blueprint(gym_bp)
        app.register_blueprint(cardio_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)