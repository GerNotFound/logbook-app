# utils.py

from extensions import db
from sqlalchemy import text
from datetime import datetime

def execute_query(query, params=None, fetchall=False, fetchone=False, commit=False):
    """
    Funzione helper centralizzata per eseguire query SQL con SQLAlchemy.
    """
    result = db.session.execute(text(query), params or {})
    if fetchone:
        row = result.mappings().first()
        return dict(row) if row else None
    if fetchall:
        return [dict(row) for row in result.mappings()]
    if commit:
        db.session.commit()
    return None

def is_valid_time_format(time_str):
    """Controlla se una stringa è in formato HH:MM."""
    if not time_str:
        return True
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False

def allowed_file(filename):
    """Controlla se l'estensione di un file è permessa."""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS