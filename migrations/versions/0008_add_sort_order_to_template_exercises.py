"""Add sort_order column to template_exercises table."""

from sqlalchemy import text

from extensions import db

revision = "0008_add_sort_order_to_template_exercises"


def upgrade() -> None:
    """Add sort_order column and backfill existing rows."""
    db.session.execute(
        text(
            "ALTER TABLE template_exercises "
            "ADD COLUMN IF NOT EXISTS sort_order INTEGER"
        )
    )

    db.session.execute(
        text(
            """
            WITH ordered AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY template_id
                        ORDER BY COALESCE(sort_order, id), id
                    ) AS rn
                FROM template_exercises
            )
            UPDATE template_exercises AS te
            SET sort_order = ordered.rn
            FROM ordered
            WHERE te.id = ordered.id AND te.sort_order IS DISTINCT FROM ordered.rn
            """
        )
    )

    db.session.commit()
