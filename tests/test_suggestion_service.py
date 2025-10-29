import pytest

from services.suggestion_service import get_catalog_suggestions, resolve_catalog_item


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
    assert captured['params']['pattern'] == '%panca%'
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


def test_resolve_catalog_item_prefers_explicit_id(monkeypatch):
    calls = []

    def fake_execute_query(query, params, *, fetchone=False, fetchall=False):
        calls.append(query.strip())
        if 'WHERE id = :id' in query and fetchone:
            return {'id': params['id'], 'name': 'Pane', 'user_id': None, 'ref_weight': 100, 'protein': 8, 'carbs': 54, 'fat': 2, 'calories': 270}
        raise AssertionError('Unexpected query execution')

    monkeypatch.setattr('services.suggestion_service.execute_query', fake_execute_query)
    monkeypatch.setattr('services.suggestion_service.get_catalog_suggestions', lambda *args, **kwargs: pytest.fail('Should not fetch suggestions'))

    result = resolve_catalog_item('foods', 7, entry_id='15', name='pane')

    assert result['id'] == 15
    assert any('FROM foods' in call for call in calls)


def test_resolve_catalog_item_exact_name(monkeypatch):
    def fake_execute_query(query, params, *, fetchone=False, fetchall=False):
        if 'WHERE id = :id' in query:
            return None
        if 'LOWER(name) = LOWER(:name)' in query:
            return {'id': 21, 'name': 'Pasta', 'user_id': 3, 'ref_weight': 100, 'protein': 12, 'carbs': 60, 'fat': 1, 'calories': 290}
        raise AssertionError('Unexpected query execution')

    monkeypatch.setattr('services.suggestion_service.execute_query', fake_execute_query)
    monkeypatch.setattr('services.suggestion_service.get_catalog_suggestions', lambda *args, **kwargs: [])

    result = resolve_catalog_item('foods', 3, entry_id=None, name='Pasta')

    assert result['id'] == 21
    assert result['user_id'] == 3


def test_resolve_catalog_item_uses_suggestions(monkeypatch):
    queries = []

    def fake_execute_query(query, params, *, fetchone=False, fetchall=False):
        queries.append(query.strip())
        if 'LOWER(name) = LOWER(:name)' in query:
            return None
        if 'WHERE id = :id' in query and fetchone:
            if params['id'] == 99:
                return {'id': 99, 'name': 'Pectoral Fly', 'user_id': None, 'ref_weight': 1, 'protein': 0, 'carbs': 0, 'fat': 0, 'calories': 0}
            return None
        raise AssertionError('Unexpected query execution')

    monkeypatch.setattr('services.suggestion_service.execute_query', fake_execute_query)
    monkeypatch.setattr('services.suggestion_service.get_catalog_suggestions', lambda *args, **kwargs: [{'id': 99, 'name': 'Pectoral Fly', 'is_global': True}])

    result = resolve_catalog_item('exercises', 11, entry_id=None, name='pecto')

    assert result['id'] == 99
    assert any('FROM exercises' in query for query in queries)
