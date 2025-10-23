# utils.py

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import text

from extensions import db


def execute_query(
    query: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    fetchall: bool = False,
    fetchone: bool = False,
    commit: bool = False,
) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
    """Funzione helper centralizzata per eseguire query SQL con SQLAlchemy."""

    result = db.session.execute(text(query), params or {})
    payload: Optional[Any] = None

    if fetchone:
        row = result.mappings().first()
        payload = dict(row) if row else None
    elif fetchall:
        payload = [dict(row) for row in result.mappings()]

    if commit:
        db.session.commit()

    return payload

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