"""Add superuser flag and communication settings."""

from sqlalchemy import text

from extensions import db

revision = "0004_add_superuser_and_comms"

WELCOME_DEFAULT = (
    "Benvenuto in Logbook! Gli amministratori possono aiutarti a mantenere aggiornati i tuoi dati di allenamento. "
    "Puoi sempre gestire le autorizzazioni dalle impostazioni del tuo profilo."
)


def upgrade() -> None:
    statements = (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser INTEGER NOT NULL DEFAULT 0",
        """
        CREATE TABLE IF NOT EXISTS communication_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            welcome_message TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        INSERT INTO communication_settings (id, welcome_message)
        VALUES (1, :welcome_message)
        ON CONFLICT (id) DO UPDATE
        SET welcome_message = EXCLUDED.welcome_message,
            updated_at = CURRENT_TIMESTAMP
        """,
    )

    for statement in statements:
        if ":welcome_message" in statement:
            db.session.execute(text(statement), {"welcome_message": WELCOME_DEFAULT})
        else:
            db.session.execute(text(statement))

    db.session.commit()
