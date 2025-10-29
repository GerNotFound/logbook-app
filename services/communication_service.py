"""Utility functions to manage admin communications such as the welcome message."""

from __future__ import annotations

from typing import Final

from utils import execute_query

WELCOME_DEFAULT: Final[str] = (
    "Benvenuto in Logbook! Gli amministratori possono aiutarti a mantenere aggiornati i tuoi dati di allenamento. "
    "Puoi sempre gestire le autorizzazioni dalle impostazioni del tuo profilo."
)


def _ensure_storage() -> None:
    """Create the storage table and seed row if missing."""
    execute_query(
        """
        CREATE TABLE IF NOT EXISTS communication_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            welcome_message TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        commit=True,
    )
    execute_query(
        """
        INSERT INTO communication_settings (id, welcome_message)
        VALUES (1, :welcome_message)
        ON CONFLICT (id) DO NOTHING
        """,
        {"welcome_message": WELCOME_DEFAULT},
        commit=True,
    )


def get_welcome_message() -> str:
    """Return the configured welcome message, falling back to the default."""
    _ensure_storage()
    row = execute_query(
        "SELECT welcome_message FROM communication_settings WHERE id = 1",
        fetchone=True,
    )
    message = row.get("welcome_message") if row else None
    return message or WELCOME_DEFAULT


def update_welcome_message(message: str) -> None:
    """Persist a new welcome message."""
    _ensure_storage()
    execute_query(
        """
        INSERT INTO communication_settings (id, welcome_message, updated_at)
        VALUES (1, :message, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO UPDATE
        SET welcome_message = EXCLUDED.welcome_message,
            updated_at = CURRENT_TIMESTAMP
        """,
        {"message": message},
        commit=True,
    )
