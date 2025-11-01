"""Utility functions for admin operations."""

from __future__ import annotations

import csv
import io
import tempfile
import zipfile
from datetime import date, datetime
from typing import Dict, List, Mapping

from utils import execute_query

_SERIALISABLE_TYPES = (datetime, date)


def _serialise_row(row: Mapping[str, object]) -> Dict[str, object]:
    serialised: Dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, _SERIALISABLE_TYPES):
            serialised[key] = value.isoformat()
        else:
            serialised[key] = value
    return serialised


def _write_csv(filename: str, rows: List[Mapping[str, object]], zip_file: zipfile.ZipFile) -> None:
    output = io.StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_serialise_row(row))
    zip_file.writestr(filename, output.getvalue())


def build_user_export_archive(user_id: int, *, spool_threshold: int = 5 * 1024 * 1024):
    """Create a zip archive containing CSV exports for the given user."""

    datasets = {
        'user_profile.csv': execute_query('SELECT * FROM user_profile WHERE user_id = :user_id', {'user_id': user_id}, fetchall=True),
        'user_notes.csv': execute_query('SELECT * FROM user_notes WHERE user_id = :user_id', {'user_id': user_id}, fetchall=True),
        'daily_data.csv': execute_query('SELECT * FROM daily_data WHERE user_id = :user_id ORDER BY record_date', {'user_id': user_id}, fetchall=True),
        'diet_log.csv': execute_query('SELECT * FROM diet_log WHERE user_id = :user_id ORDER BY log_date', {'user_id': user_id}, fetchall=True),
        'cardio_log.csv': execute_query('SELECT * FROM cardio_log WHERE user_id = :user_id ORDER BY record_date', {'user_id': user_id}, fetchall=True),
        'workout_sessions.csv': execute_query('SELECT * FROM workout_sessions WHERE user_id = :user_id ORDER BY record_date', {'user_id': user_id}, fetchall=True),
        'workout_log.csv': execute_query('SELECT * FROM workout_log WHERE user_id = :user_id ORDER BY record_date, session_timestamp, set_number', {'user_id': user_id}, fetchall=True),
        'workout_session_comments.csv': execute_query('SELECT * FROM workout_session_comments WHERE user_id = :user_id ORDER BY id', {'user_id': user_id}, fetchall=True),
        'foods.csv': execute_query('SELECT * FROM foods WHERE user_id = :user_id ORDER BY name', {'user_id': user_id}, fetchall=True),
        'workout_templates.csv': execute_query('SELECT * FROM workout_templates WHERE user_id = :user_id ORDER BY name', {'user_id': user_id}, fetchall=True),
        'template_exercises.csv': execute_query('SELECT * FROM template_exercises WHERE template_id IN (SELECT id FROM workout_templates WHERE user_id = :user_id) ORDER BY template_id, id', {'user_id': user_id}, fetchall=True),
    }

    spool = tempfile.SpooledTemporaryFile(max_size=spool_threshold)
    with zipfile.ZipFile(spool, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, rows in datasets.items():
            _write_csv(filename, rows or [], zip_file)
    spool.seek(0)
    return spool
