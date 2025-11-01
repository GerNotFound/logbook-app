"""Create table to track user login activity."""

from sqlalchemy import text

from extensions import db

revision = "0002_add_user_login_activity_table"


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS user_login_activity (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            login_at TIMESTAMP NOT NULL DEFAULT NOW(),
            ip_address TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_user_login_activity_user_time ON user_login_activity (user_id, login_at DESC)",
    )

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()