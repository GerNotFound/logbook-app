"""Add security tracking columns to users table."""

from sqlalchemy import text

from extensions import db

revision = "0001_add_user_security_columns"

def upgrade() -> None:
    statements = (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS lock_until TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP",
    )
    for statement in statements:
        db.session.execute(text(statement))
    db.session.commit()
