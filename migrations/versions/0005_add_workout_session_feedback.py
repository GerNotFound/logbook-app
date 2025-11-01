"""Add training note and rating fields to workout sessions."""

from sqlalchemy import text

from extensions import db

revision = "0005_add_workout_session_feedback"


def upgrade() -> None:
    statements = (
        "ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS session_note TEXT",
        "ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS session_rating INTEGER",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_workout_sessions_rating_range'
            ) THEN
                ALTER TABLE workout_sessions
                ADD CONSTRAINT ck_workout_sessions_rating_range
                CHECK (session_rating BETWEEN 1 AND 10);
            END IF;
        END $$;
        """,
    )

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()