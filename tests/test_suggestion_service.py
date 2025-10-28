import pytest

from services.suggestion_service import get_catalog_suggestions


def test_get_catalog_suggestions_normalizes_input(monkeypatch):
    captured = {}

    def fake_execute_query(query, params, *, fetchall=False):
        captured['query'] = query
        captured['params'] = params
        captured['fetchall'] = fetchall
        return [
            {'id': 1, 'name': 'Panca Piana', 'is_global': True},
            {'id': 8, 'name': 'Panca Inclinata', 'is_global': False},
        ]

    monkeypatch.setattr('services.suggestion_service.execute_query', fake_execute_query)

    results = get_catalog_suggestions('exercises', 42, '  Panca  ')

    assert len(results) == 2
    assert results[0] == {'id': 1, 'name': 'Panca Piana', 'is_global': True}
    assert results[1]['is_global'] is False
    assert captured['fetchall'] is True
    assert captured['params']['uid'] == 42
    assert captured['params']['pattern'] == '%Panca%'
    assert captured['params']['limit'] == 5


def test_get_catalog_suggestions_with_custom_limit(monkeypatch):
    observed_limits = []

    def fake_execute_query(query, params, *, fetchall=False):
        observed_limits.append(params['limit'])
        return []

    monkeypatch.setattr('services.suggestion_service.execute_query', fake_execute_query)

    get_catalog_suggestions('foods', 5, 'mele', limit=10)

    assert observed_limits == [10]


def test_get_catalog_suggestions_empty_term(monkeypatch):
    def boom(*args, **kwargs):  # pragma: no cover - should not execute
        raise AssertionError('execute_query should not be called for empty term')

    monkeypatch.setattr('services.suggestion_service.execute_query', boom)

    assert get_catalog_suggestions('exercises', 1, '   ') == []


def test_get_catalog_suggestions_invalid_resource():
    with pytest.raises(ValueError):
        get_catalog_suggestions('unknown', 1, 'ciao')
