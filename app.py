import os
from datetime import timedelta
from flask import Flask
from extensions import db, csrf, talisman, limiter
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)

    # --- CONFIGURAZIONE ---

    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

    # --- MODIFICA QUI: SOLUZIONE PER L'ERRORE DEL DATABASE SU KOYEB ---
    # Aggiungi queste opzioni per gestire meglio le connessioni al database
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    # Inizializza le estensioni
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Configurazione di Sicurezza Talisman
    csp = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            'https://cdn.jsdelivr.net'
        ],
        'style-src': [
            "'self'",
            'https://cdn.jsdelivr.net',
            'https://fonts.googleapis.com',
            "'unsafe-inline'"
        ],
        'font-src': [
            "'self'",
            'https://fonts.gstatic.com',
            'https://cdn.jsdelivr.net'
        ],
        'img-src': [
            "'self'",
            'data:'
        ],
    }

    talisman.init_app(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src'],
        force_https=not app.debug,
    )

    with app.app_context():

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
