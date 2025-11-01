from __future__ import annotations

import os

from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
try:
    from flask_socketio import SocketIO
except ModuleNotFoundError:  # pragma: no cover - fallback for limited environments
    class SocketIO:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self._init_args = args
            self._init_kwargs = kwargs

        def init_app(self, app, **kwargs):
            app.logger.warning('Flask-SocketIO non disponibile: funzionalità realtime disabilitate in questo ambiente di test.')

        def on_namespace(self, namespace):
            return namespace

        def run(self, app, **kwargs):
            raise RuntimeError('Flask-SocketIO non è installato. Installa le dipendenze per abilitare il server realtime.')

from config import BaseConfig


def _default_rate_limit() -> list[str]:
    limit = os.getenv('DEFAULT_RATE_LIMIT', BaseConfig.DEFAULT_RATE_LIMIT)
    return [limit] if limit else []


db = SQLAlchemy()
csrf = CSRFProtect()
talisman = Talisman()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=_default_rate_limit(),
    storage_uri=os.getenv('RATELIMIT_STORAGE_URI', BaseConfig.RATELIMIT_STORAGE_URI),
    headers_enabled=BaseConfig.RATELIMIT_HEADERS_ENABLED,
)
socketio = SocketIO(async_mode='eventlet', manage_session=False)
