"""Add consigli column to exercises table."""

from sqlalchemy import text

from extensions import db

revision = "0007_add_consigli_to_exercises"

def upgrade() -> None:
    """Add a 'consigli' text column to the 'exercises' table."""
    db.session.execute(
        text("ALTER TABLE exercises ADD COLUMN IF NOT EXISTS consigli TEXT")
    )
    db.session.commit()