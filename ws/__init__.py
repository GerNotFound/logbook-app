"""Socket.IO namespaces registration for the Logbook app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .template_editor import TemplateEditorNamespace

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from flask_socketio import SocketIO
else:  # pragma: no cover - runtime fallback when dependency is unavailable
    SocketIO = Any


def register_socketio_namespaces(socketio: SocketIO) -> None:
    """Attach all Socket.IO namespaces to the provided instance."""
    socketio.on_namespace(TemplateEditorNamespace('/template-editor'))
