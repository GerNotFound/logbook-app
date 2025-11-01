from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, session, current_app, flash, redirect, url_for
from dotenv import load_dotenv

import commands
from config import ProductionConfig
from migrations import run_migrations
from bootstrap import ensure_database_indexes
from extensions import csrf, db, limiter
from logging_config import setup_logging
from routes import admin_bp, auth_bp, cardio_bp, gym_bp, main_bp, nutrition_bp
from routes.health import health_bp
from security import init_security
from utils import execute_query


def _load_app_version() -> str:
    try:
        return Path('versione.txt').read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        return 'N/D'

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(ProductionConfig())
    ProductionConfig.init_app(app)

    setup_logging(app.config['LOG_LEVEL'])
    app.logger.handlers = []
    app.logger.propagate = True

    db.init_app(app)
    csrf.init_app(app)
    init_security(app)

    limiter.init_app(app)

    commands.init_app(app)

    app.config['APP_VERSION'] = _load_app_version()

    with app.app_context():
        run_migrations()
        ensure_database_indexes()

    @app.before_request
    def ensure_user_session_is_valid():
        user_id = session.get('user_id')
        if not user_id:
            return

        user_exists = execute_query(
            'SELECT 1 FROM users WHERE id = :uid',
            {'uid': user_id},
            fetchone=True,
        )

        if user_exists:
            return

        session.clear()
        flash('La tua sessione è stata chiusa. Effettua nuovamente l\'accesso.', 'info')
        return redirect(url_for('auth.login'))

    @app.before_request
    def update_last_active_timestamp() -> None:
        user_id = session.get('user_id')
        if not user_id:
            session.pop('last_activity_update', None)
            session.pop('next_activity_update', None)
            return

        now = datetime.utcnow()
        next_update_iso = session.get('next_activity_update')
        if next_update_iso:
            try:
                next_update = datetime.fromisoformat(next_update_iso)
                if now < next_update:
                    return
            except ValueError:
                current_app.logger.debug('Invalid next_activity_update in session, forcing refresh.')

        update_interval = current_app.config.get('LAST_ACTIVITY_UPDATE_INTERVAL_SECONDS', 900)

        try:
            execute_query(
                'UPDATE users SET last_active_at = :ts WHERE id = :uid',
                {'ts': now, 'uid': user_id},
                commit=True,
            )
        except Exception as exc:  # pragma: no cover - safeguard
            current_app.logger.warning('Unable to persist last_active_at for user %s: %s', user_id, exc)
            return

        session['last_activity_update'] = now.isoformat()
        session['next_activity_update'] = (now + timedelta(seconds=update_interval)).isoformat()

    @app.context_processor
    def inject_version() -> dict[str, str]:
        return {'app_version': current_app.config.get('APP_VERSION', 'N/D')}

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(gym_bp)
    app.register_blueprint(cardio_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(health_bp)

    return app


if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5000)