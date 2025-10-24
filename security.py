from __future__ import annotations

from flask import Flask

from extensions import talisman


def init_security(app: Flask) -> None:
    """Configure HTTP security headers and HTTPS enforcement."""

    csp = {
        'default-src': ["'self'", 'https:'],
        'script-src': ["'self'", 'https:'],
        'style-src': ["'self'", 'https:'],
        'img-src': ["'self'", 'data:', 'https:'],
        'font-src': ["'self'", 'https:'],
        'connect-src': ["'self'", 'https:'],
    }

    talisman.init_app(
        app,
        content_security_policy=csp,
        force_https=True,
        force_https_permanent=True,
        strict_transport_security=True,
        strict_transport_security_include_subdomains=True,
        strict_transport_security_preload=True,
        referrer_policy='no-referrer',
    )
