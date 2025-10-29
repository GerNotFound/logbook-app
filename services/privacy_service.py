"""Utility functions to manage privacy content."""

from utils import execute_query


def _ensure_storage() -> None:
    """Create the backing table and seed row if they are missing."""
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS privacy_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            content TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        commit=True,
    )
    execute_query(
        """
        INSERT INTO privacy_settings (id, content)
        VALUES (1, '')
        ON CONFLICT (id) DO NOTHING
        """,
        commit=True,
    )


def get_privacy_text() -> str:
    """Return the privacy text configured by the administrator."""
    _ensure_storage()
    row = execute_query(
        "SELECT content FROM privacy_settings WHERE id = 1",
        fetchone=True,
    )
    if row and row.get("content"):
        return row["content"]
    return ""


def update_privacy_text(content: str) -> None:
    """Persist a new privacy text in the database."""
    _ensure_storage()
    execute_query(
        """
        INSERT INTO privacy_settings (id, content, updated_at)
        VALUES (1, :content, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO UPDATE
        SET content = EXCLUDED.content,
            updated_at = CURRENT_TIMESTAMP
        """,
        {"content": content},
        commit=True,
    )
