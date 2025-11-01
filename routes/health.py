from __future__ import annotations

from flask import Blueprint, jsonify, current_app
from sqlalchemy import text

from extensions import db

health_bp = Blueprint('health', __name__)


@health_bp.route('/healthz', methods=['GET'])
def healthcheck():
    try:
        db.session.execute(text('SELECT 1'))
        db.session.commit()
    except Exception:  # pragma: no cover - logging branch
        db.session.rollback()
        current_app.logger.exception('Healthcheck database probe failed')
        return jsonify({'status': 'error'}), 500

    return jsonify({'status': 'ok'}), 200
