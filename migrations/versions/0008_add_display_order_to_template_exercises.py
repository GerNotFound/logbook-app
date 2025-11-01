"""Add display_order to template_exercises table."""

from sqlalchemy import text

from extensions import db

revision = "0008_add_display_order_to_template_exercises"

def upgrade() -> None:
    """Add display_order column and initialize it."""
    db.session.execute(
        text("ALTER TABLE template_exercises ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0")
    )
    
    # Inizializza l'ordine per i dati esistenti basandosi sull'ID per mantenere un ordine stabile
    db.session.execute(
        text("""
            WITH ordered_exercises AS (
                SELECT 
                    id, 
                    ROW_NUMBER() OVER(PARTITION BY template_id ORDER BY id) as rn
                FROM template_exercises
            )
            UPDATE template_exercises
            SET display_order = ordered_exercises.rn
            FROM ordered_exercises
            WHERE template_exercises.id = ordered_exercises.id
        """)
    )
    
    db.session.commit()