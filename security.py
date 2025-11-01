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
        'object-src': ["'none'"],
        'frame-ancestors': ["'none'"],
        'base-uri': ["'self'"],
        'form-action': ["'self'"],
    }

    permissions_policy = {
        'accelerometer': '()',
        'autoplay': '()',
        'camera': '()',
        'fullscreen': '()',
        'display-capture': '()',
        'geolocation': '()',
        'gyroscope': '()',
        'hid': '()',
        'magnetometer': '()',
        'microphone': '()',
        'payment': '()',
        'usb': '()',
        'xr-spatial-tracking': '()',
    }

    talisman.init_app(
        app,
        content_security_policy=csp,
        permissions_policy=permissions_policy,
        force_https=True,
        force_https_permanent=True,
        strict_transport_security=True,
        strict_transport_security_include_subdomains=True,
        strict_transport_security_preload=True,
        frame_options='DENY',
        referrer_policy='no-referrer',
        x_content_type_options=True,
        session_cookie_samesite=app.config.get('SESSION_COOKIE_SAMESITE', 'Strict'),
    )

    @app.after_request
    def _set_cross_origin_policies(response):
        """Apply additional cross-origin isolation headers."""

        opener_policy = app.config.get('CROSS_ORIGIN_OPENER_POLICY')
        if opener_policy:
            response.headers.setdefault('Cross-Origin-Opener-Policy', opener_policy)

        embedder_policy = app.config.get('CROSS_ORIGIN_EMBEDDER_POLICY')
        if embedder_policy:
            response.headers.setdefault('Cross-Origin-Embedder-Policy', embedder_policy)

        resource_policy = app.config.get('CROSS_ORIGIN_RESOURCE_POLICY')
        if resource_policy:
            response.headers.setdefault('Cross-Origin-Resource-Policy', resource_policy)

        return response
