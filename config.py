import os
from datetime import timedelta


def _normalize_database_url(url: str | None) -> str | None:
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


class BaseConfig:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': _as_int(os.environ.get('DB_POOL_SIZE'), 5),
        'max_overflow': _as_int(os.environ.get('DB_MAX_OVERFLOW'), 10),
    }

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Strict')
    PREFERRED_URL_SCHEME = 'https'

    CROSS_ORIGIN_OPENER_POLICY = os.environ.get(
        'CROSS_ORIGIN_OPENER_POLICY',
        'same-origin',
    )
    CROSS_ORIGIN_EMBEDDER_POLICY = os.environ.get(
        'CROSS_ORIGIN_EMBEDDER_POLICY',
        'require-corp',
    )
    CROSS_ORIGIN_RESOURCE_POLICY = os.environ.get(
        'CROSS_ORIGIN_RESOURCE_POLICY',
        'same-origin',
    )

    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    SECURITY_MAX_FAILED_LOGINS = _as_int(os.environ.get('SECURITY_MAX_FAILED_LOGINS'), 5)
    SECURITY_LOCKOUT_MINUTES = _as_int(os.environ.get('SECURITY_LOCKOUT_MINUTES'), 15)
    SECURITY_ONLINE_THRESHOLD_MINUTES = _as_int(os.environ.get('SECURITY_ONLINE_THRESHOLD_MINUTES'), 5)

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    DEFAULT_RATE_LIMIT = os.environ.get('DEFAULT_RATE_LIMIT', '200 per hour')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True

    LAST_ACTIVITY_UPDATE_INTERVAL_SECONDS = _as_int(
        os.environ.get('LAST_ACTIVITY_UPDATE_INTERVAL_SECONDS'),
        120,
    )
    GENERAL_METRICS_ENTRY_LIMIT = _as_int(
        os.environ.get('GENERAL_METRICS_ENTRY_LIMIT'),
        90,
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False

    @staticmethod
    def init_app(app):
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            raise RuntimeError('DATABASE_URL environment variable is required')
        if not app.config.get('SECRET_KEY'):
            raise RuntimeError('SECRET_KEY environment variable is required')