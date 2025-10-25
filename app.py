from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, session, current_app
from dotenv import load_dotenv

import commands
from bootstrap import ensure_database_indexes
from config import ProductionConfig
from extensions import csrf, db, limiter
from logging_config import setup_logging
from migrations import run_migrations
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
        def update_last_active_timestamp() -> None:
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
