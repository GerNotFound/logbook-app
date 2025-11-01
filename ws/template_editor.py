"""Socket.IO namespace used by the workout template editor."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from flask import current_app, request, session, url_for

try:
    from flask_socketio import Namespace
except ModuleNotFoundError:  # pragma: no cover - fallback when dependency missing
    class Namespace:  # type: ignore[override]
        namespace = '/'  # default namespace used for compatibility

        def __init__(self, namespace: str | None = None):
            if namespace is not None:
                self.namespace = namespace

        def emit(self, *args, **kwargs):
            return None
from markupsafe import escape

from utils import execute_query

MAX_RESULTS = 50


def _highlight_match(name: str, query: str) -> str:
    """Return HTML markup with the first occurrence of *query* highlighted."""

    if not query:
        return str(escape(name))

    lowered_name = name.lower()
    lowered_query = query.lower()
    match_index = lowered_name.find(lowered_query)
    if match_index == -1:
        return str(escape(name))

    before = escape(name[:match_index])
    match = escape(name[match_index : match_index + len(query)])
    after = escape(name[match_index + len(query) :])
    return f"{before}<mark>{match}</mark>{after}"


def _format_search_results(rows: Sequence[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Transform raw database rows into the payload returned to the client."""

    display_query = query.strip()
    formatted: list[dict[str, Any]] = []
    for row in rows:
        formatted.append(
            {
                'id': row['id'],
                'name': row['name'],
                'highlighted_name': _highlight_match(row['name'], display_query),
                'is_global': row['user_id'] is None,
                'info_url': url_for('gym.esercizio_info', exercise_id=row['id']),
            }
        )
    return formatted


def _fetch_matching_exercises(user_id: int, query: str) -> list[dict[str, Any]]:
    """Fetch exercises that match *query* prioritising prefix matches."""

    normalized_query = query.strip().lower()
    base_params = {'uid': user_id, 'limit': MAX_RESULTS}

    if not normalized_query:
        rows = execute_query(
            'SELECT id, name, user_id '
            'FROM exercises WHERE user_id IS NULL OR user_id = :uid '
            'ORDER BY name LIMIT :limit',
            base_params,
            fetchall=True,
        )
        return rows or []

    prefix_rows = execute_query(
        'SELECT id, name, user_id '
        'FROM exercises '
        'WHERE (user_id IS NULL OR user_id = :uid) '
        'AND LOWER(name) LIKE :prefix '
        'ORDER BY name LIMIT :limit',
        {**base_params, 'prefix': f"{normalized_query}%"},
        fetchall=True,
    ) or []

    if len(prefix_rows) >= MAX_RESULTS:
        return prefix_rows[:MAX_RESULTS]

    remaining = MAX_RESULTS - len(prefix_rows)
    if remaining <= 0:
        return prefix_rows

    contains_rows = execute_query(
        'SELECT id, name, user_id '
        'FROM exercises '
        'WHERE (user_id IS NULL OR user_id = :uid) '
        'AND LOWER(name) LIKE :contains '
        'ORDER BY name LIMIT :limit',
        {**base_params, 'contains': f"%{normalized_query}%", 'limit': remaining},
        fetchall=True,
    ) or []

    seen_ids = {row['id'] for row in prefix_rows}
    combined = prefix_rows + [row for row in contains_rows if row['id'] not in seen_ids]
    return combined[:MAX_RESULTS]


def _summarize_preview_items(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Calculate quick metrics for the live preview synchronisation ack."""

    total_exercises = 0
    total_sets = 0
    for item in items:
        try:
            sets = int(item.get('sets', 0))
        except (TypeError, ValueError):
            continue
        total_exercises += 1
        if sets > 0:
            total_sets += sets
    return {'total_exercises': total_exercises, 'total_sets': total_sets}


class TemplateEditorNamespace(Namespace):
    """Namespace responsible for real-time workout template interactions."""

    def on_connect(self):  # pragma: no cover - exercised via runtime interaction
        user_id = session.get('user_id')
        if not user_id:
            return False
        current_app.logger.debug('Template editor socket connected for user %s', user_id)

    def on_disconnect(self):  # pragma: no cover - exercised via runtime interaction
        user_id = session.get('user_id')
        if user_id:
            current_app.logger.debug('Template editor socket disconnected for user %s', user_id)

    def on_template_search(self, payload: dict[str, Any] | None) -> None:
        user_id = session.get('user_id')
        if not user_id:
            return

        query = (payload or {}).get('query', '')
        rows = _fetch_matching_exercises(user_id, query)
        results = _format_search_results(rows, query)
        self.emit(
            'template_search_results',
            {'query': query, 'results': results},
            to=request.sid,
        )

    def on_template_state_preview(self, payload: dict[str, Any] | None) -> None:
        user_id = session.get('user_id')
        if not user_id:
            return

        items = (payload or {}).get('items', [])
        if not isinstance(items, Iterable) or isinstance(items, (str, bytes)):
            items = []
        summary = _summarize_preview_items(items)
        self.emit(
            'template_state_ack',
            {
                'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
                'summary': summary,
            },
            to=request.sid,
        )
