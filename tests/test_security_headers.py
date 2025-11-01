import importlib
import os

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SKIP_DB_MIGRATIONS', '1')
os.environ.setdefault('SKIP_DB_BOOTSTRAP', '1')

application = importlib.import_module('app').application


def test_security_headers_present():
    client = application.test_client()
    response = client.get('/', base_url='https://example.com')

    csp = response.headers.get('Content-Security-Policy')
    assert csp is not None
    assert "default-src 'self'" in csp
    assert 'https://cdn.socket.io' in csp

    hsts = response.headers.get('Strict-Transport-Security')
    assert hsts is not None
    assert hsts.startswith('max-age=')


def test_security_txt_endpoint():
    client = application.test_client()
    response = client.get('/.well-known/security.txt', base_url='https://example.com')

    assert response.status_code == 200
    assert response.mimetype == 'text/plain'
    assert 'security@logbook.click' in response.get_data(as_text=True)
