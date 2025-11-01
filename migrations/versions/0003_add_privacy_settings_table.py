"""Create table to store privacy content."""

from sqlalchemy import text

from extensions import db

revision = "0003_add_privacy_settings_table"


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS privacy_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            content TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        INSERT INTO privacy_settings (id, content)
        VALUES (1, '')
        ON CONFLICT (id) DO NOTHING
        """,
    )

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()