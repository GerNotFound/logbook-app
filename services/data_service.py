# services/data_service.py

import io
import csv
from flask import Response
from extensions import db
from utils import execute_query

def export_user_data(user_id: int):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(["DATI GIORNALIERI"])
    daily_data_rows = execute_query(
        "SELECT record_date, weight, weight_time, sleep, sleep_quality, calories, neck, waist, measure_time, day_type FROM daily_data WHERE user_id = :user_id ORDER BY record_date",
        {"user_id": user_id},
        fetchall=True,
    )
    if daily_data_rows:
        writer.writerow(daily_data_rows[0].keys())
        for row in daily_data_rows:
            writer.writerow(row.values())

    writer.writerow([])
    writer.writerow(["DIARIO ALIMENTARE"])
    diet_log_rows = execute_query(
        "SELECT dl.log_date, f.name, dl.weight, dl.protein, dl.carbs, dl.fat, dl.calories FROM diet_log dl JOIN foods f ON dl.food_id = f.id WHERE dl.user_id = :user_id ORDER BY dl.log_date",
        {"user_id": user_id},
        fetchall=True,
    )
    if diet_log_rows:
        writer.writerow(diet_log_rows[0].keys())
        for row in diet_log_rows:
            writer.writerow(row.values())

    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=logbook_export.csv"},
    )

def delete_all_day_data(user_id: int, date_to_delete: str):
    try:
        execute_query('DELETE FROM workout_sessions WHERE user_id = :user_id AND record_date = :date', {'user_id': user_id, 'date': date_to_delete})
        execute_query('DELETE FROM cardio_log WHERE user_id = :user_id AND record_date = :date', {'user_id': user_id, 'date': date_to_delete})
        execute_query('DELETE FROM diet_log WHERE user_id = :user_id AND log_date = :date', {'user_id': user_id, 'date': date_to_delete})
        execute_query('DELETE FROM daily_data WHERE user_id = :user_id AND record_date = :date', {'user_id': user_id, 'date': date_to_delete})
        db.session.commit()
        return True, f'Tutti i dati del giorno {date_to_delete} sono stati eliminati.'
    except Exception as e:
        db.session.rollback()
        return False, f'Si è verificato un errore durante l\'eliminazione: {e}'