"""Utility helpers for autosuggest search endpoints."""

from __future__ import annotations

from typing import Dict, Iterable, List

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

    # ``ILIKE`` keeps the query simple while supporting case-insensitive search.
    # Results are already ordered prioritising global entries on top of the list.
    rows: Iterable[Dict[str, object]] = execute_query(
        f"""
        SELECT id, name, user_id IS NULL AS is_global
        FROM {table_name}
        WHERE (user_id IS NULL OR user_id = :uid)
          AND name ILIKE :pattern
        ORDER BY (user_id IS NULL) DESC, name ASC
        LIMIT :limit
        """,
        {
            'uid': user_id,
            'pattern': f"%{sanitized}%",
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

