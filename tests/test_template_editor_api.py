import importlib
import os

import pytest
from flask import session

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SKIP_DB_MIGRATIONS', '1')
os.environ.setdefault('SKIP_DB_BOOTSTRAP', '1')

application = importlib.import_module('app').application


def test_template_editor_data_api_returns_exercises(monkeypatch):
    from routes import gym as gym_routes

    template_payload = {'id': 42, 'name': 'Forza'}

    def fake_get_template_by_slug(user_id, slug):
        assert user_id == 1
        assert slug == 'forza'
        return template_payload

    def fake_execute_query(query, params=None, *, fetchall=False, fetchone=False, commit=False):
        if 'SELECT 1 FROM users WHERE id = :uid' in query:
            return {'exists': 1}
        if 'FROM template_exercises te' in query:
            return [
                {
                    'template_exercise_id': 7,
                    'exercise_id': 3,
                    'name': 'Rematore Bilanciere',
                    'exercise_owner_id': None,
                    'sets': '4',
                }
            ]
        if 'FROM exercises WHERE user_id IS NULL OR user_id = :uid' in query:
            return [
                {'id': 3, 'name': 'Rematore Bilanciere', 'user_id': None},
                {'id': 11, 'name': 'Curl Manubri', 'user_id': 1},
            ]
        return None

    monkeypatch.setattr(gym_routes, '_get_template_by_slug', fake_get_template_by_slug)
    monkeypatch.setattr(gym_routes, 'execute_query', fake_execute_query)
    monkeypatch.setattr('utils.execute_query', fake_execute_query)

    with application.test_request_context('/api/templates/forza/editor-data', base_url='https://example.com'):
        session['user_id'] = 1
        response = gym_routes.template_editor_data_api('forza')

    assert response.status_code == 200

    payload = response.get_json()
    assert payload['template'] == template_payload
    assert payload['current_exercises'][0]['name'] == 'Rematore Bilanciere'
    assert len(payload['all_exercises']) == 2


def test_template_editor_data_api_not_found(monkeypatch):
    from routes import gym as gym_routes

    monkeypatch.setattr(gym_routes, '_get_template_by_slug', lambda user_id, slug: None)

    with application.test_request_context('/api/templates/inesistente/editor-data', base_url='https://example.com'):
        session['user_id'] = 1
        result = gym_routes.template_editor_data_api('inesistente')

    if isinstance(result, tuple):
        response, status_code = result
    else:
        response, status_code = result, result.status_code

    assert status_code == 404
    assert response.get_json()['error'] == 'Scheda non trovata.'
