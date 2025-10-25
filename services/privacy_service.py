"""Utility functions to manage privacy content."""

from utils import execute_query


def get_privacy_text() -> str:
    """Return the privacy text configured by the administrator."""
    row = execute_query(
        "SELECT content FROM privacy_settings WHERE id = 1",
        fetchone=True,
    )
    if row and row.get("content"):
        return row["content"]
    return ""


def update_privacy_text(content: str) -> None:
    """Persist a new privacy text in the database."""
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
