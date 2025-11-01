from __future__ import annotations

import os

from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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