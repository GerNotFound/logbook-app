"""Create intake_log table for nutrition tracking."""

from sqlalchemy import text

from extensions import db

revision = "0006_add_intake_log_table"


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS intake_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            record_date DATE NOT NULL,
            tracker_type TEXT NOT NULL,
            amount REAL NOT NULL,
            unit TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_intake_log_user_date ON intake_log (user_id, record_date)",
    )

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()
