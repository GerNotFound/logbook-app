import os
from datetime import timedelta
from flask import Flask
from extensions import db, csrf
from dotenv import load_dotenv # NUOVA IMPORTAZIONE

# Carica le variabili d'ambiente dal file .env (se esiste)
load_dotenv()

def create_app():
    """Application Factory"""
    app = Flask(__name__)

    # --- CONFIGURAZIONE BASATA SU VARIABILI D'AMBIENTE ---
    
    # Chiave segreta: usa quella dal .env/server, altrimenti ne genera una casuale
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    
    # Connessione al database: usa quella dal .env/server
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Modalità Debug: attivata solo se FLASK_ENV è 'development'
    app.debug = os.environ.get('FLASK_ENV') == 'development'

    app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
    app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    # Inizializza le estensioni
    db.init_app(app)
    csrf.init_app(app)

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
    # L'host e la porta sono gestiti da Flask in base alla modalità debug
    app.run(host='0.0.0.0', port=5000)