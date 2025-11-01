from __future__ import annotations

from sqlalchemy import text

from extensions import db


def ensure_database_indexes() -> None:
    """Create essential indexes if they do not yet exist."""

    statements = (
        "CREATE INDEX IF NOT EXISTS idx_daily_data_user_date ON daily_data (user_id, record_date)",
        "CREATE INDEX IF NOT EXISTS idx_workout_log_user_date ON workout_log (user_id, record_date)",
    )

    for statement in statements:
        db.session.execute(text(statement))

    db.session.commit()