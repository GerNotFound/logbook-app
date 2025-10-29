"""Utility helpers for autosuggest search endpoints."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from utils import execute_query

_TABLE_MAP: Dict[str, str] = {
    'exercises': 'exercises',
    'foods': 'foods',
}


def get_catalog_suggestions(
    resource: str,
    user_id: int,
    term: str,
    *,
    limit: int = 5,
) -> List[Dict[str, object]]:
    """Return sanitized autosuggest results for the given catalog.

    Args:
        resource: The catalog to search (``exercises`` or ``foods``).
        user_id: The requesting user identifier.
        term: Raw search term supplied by the client.
        limit: Maximum number of records to return.

    Returns:
        A list of dictionaries ``{"id": int, "name": str, "is_global": bool}``.
    """

    table_name = _TABLE_MAP.get(resource)
    if table_name is None:
        raise ValueError(f'Unsupported catalog resource: {resource!r}')

    sanitized = (term or '').strip()
    if not sanitized:
        return []

    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = 5

    if limit_value <= 0:
        limit_value = 5

    normalized = sanitized.lower()
    pattern = f"%{normalized}%"

    # ``LOWER`` keeps the lookup portable across SQLite/PostgreSQL while still
    # providing a case-insensitive match. Results are ordered with global entries
    # (``user_id`` NULL) first, then alphabetically by name.
    rows: Iterable[Dict[str, object]] = execute_query(
        f"""
        SELECT id, name, user_id IS NULL AS is_global
        FROM {table_name}
        WHERE (user_id IS NULL OR user_id = :uid)
          AND LOWER(name) LIKE :pattern
        ORDER BY CASE WHEN user_id IS NULL THEN 0 ELSE 1 END,
                 LOWER(name) ASC,
                 name ASC
        LIMIT :limit
        """,
        {
            'uid': user_id,
            'pattern': pattern,
            'limit': limit_value,
        },
        fetchall=True,
    ) or []

    return [
        {
            'id': row['id'],
            'name': row['name'],
            'is_global': bool(row['is_global']),
        }
        for row in rows
    ]


def resolve_catalog_item(
    resource: str,
    user_id: int,
    *,
    entry_id: Optional[object] = None,
    name: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    """Return a catalog row matching either the provided id or name.

    The resolver first attempts to look up the explicit ``entry_id``. If it is not
    provided or the lookup fails, an exact case-insensitive name match is tried.
    As a final fallback a prefix/substring lookup reuses the autosuggest service
    so that partially typed values (e.g. ``"pa"``) can still resolve to the first
    available suggestion.
    """

    table_name = _TABLE_MAP.get(resource)
    if table_name is None:
        raise ValueError(f'Unsupported catalog resource: {resource!r}')

    candidate_id: Optional[int] = None
    if entry_id not in (None, ''):
        try:
            candidate_id = int(entry_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            candidate_id = None

    if candidate_id is not None:
        row = execute_query(
            f"""
            SELECT *
            FROM {table_name}
            WHERE id = :id AND (user_id IS NULL OR user_id = :uid)
            LIMIT 1
            """,
            {'id': candidate_id, 'uid': user_id},
            fetchone=True,
        )
        if row:
            return row

    sanitized_name = (name or '').strip()
    if not sanitized_name:
        return None

    exact_match = execute_query(
        f"""
        SELECT *
        FROM {table_name}
        WHERE LOWER(name) = LOWER(:name)
          AND (user_id IS NULL OR user_id = :uid)
        LIMIT 1
        """,
        {'name': sanitized_name, 'uid': user_id},
        fetchone=True,
    )
    if exact_match:
        return exact_match

    suggestions = get_catalog_suggestions(resource, user_id, sanitized_name, limit=1)
    if not suggestions:
        return None

    resolved_id = suggestions[0]['id']
    return execute_query(
        f"""
        SELECT *
        FROM {table_name}
        WHERE id = :id AND (user_id IS NULL OR user_id = :uid)
        LIMIT 1
        """,
        {'id': resolved_id, 'uid': user_id},
        fetchone=True,
    )

