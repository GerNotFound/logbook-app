"""Services and repositories for workout operations."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List

from utils import execute_query


def _fetch_templates(user_id: int) -> List[Dict]:
    templates_raw = execute_query(
        'SELECT id, name FROM workout_templates WHERE user_id = :user_id ORDER BY name',
        {'user_id': user_id},
        fetchall=True,
    )
    if not templates_raw:
        return []

    template_ids = [tpl['id'] for tpl in templates_raw]
    exercises_raw = execute_query(
        'SELECT te.id, te.template_id, te.exercise_id, te.sets, e.name, uen.notes '
        'FROM template_exercises te '
        'JOIN exercises e ON te.exercise_id = e.id '
        'LEFT JOIN user_exercise_notes uen ON uen.exercise_id = e.id AND uen.user_id = :user_id '
        'WHERE te.template_id = ANY(:template_ids) '
        'ORDER BY te.id',
        {'user_id': user_id, 'template_ids': template_ids},
        fetchall=True,
    )

    exercises_by_template: Dict[int, List[Dict]] = defaultdict(list)
    for row in exercises_raw or []:
        exercises_by_template[row['template_id']].append(dict(row))

    templates: List[Dict] = []
    for tpl in templates_raw:
        tpl_dict = dict(tpl)
        tpl_dict['exercises'] = exercises_by_template.get(tpl['id'], [])
        templates.append(tpl_dict)
    return templates


def _fetch_recent_sessions(
    user_id: int,
    exercise_ids: Iterable[int],
    before_date: date,
) -> Dict[int, List[Dict]]:
    if not exercise_ids:
        return {}

    history_rows = execute_query(
        """
        WITH ranked_sessions AS (
            SELECT DISTINCT exercise_id,
                            session_timestamp,
                            record_date,
                            ROW_NUMBER() OVER (
                                PARTITION BY exercise_id
                                ORDER BY record_date DESC, session_timestamp DESC
                            ) AS session_rank
            FROM workout_log
            WHERE user_id = :user_id
              AND exercise_id = ANY(:exercise_ids)
              AND record_date < :record_date
        ), limited_sessions AS (
            SELECT exercise_id, session_timestamp, record_date
            FROM ranked_sessions
            WHERE session_rank <= 2
        )
        SELECT wl.exercise_id,
               wl.session_timestamp,
               ls.record_date,
               wl.set_number,
               wl.reps,
               wl.weight
        FROM workout_log wl
        JOIN limited_sessions ls
          ON wl.exercise_id = ls.exercise_id
         AND wl.session_timestamp = ls.session_timestamp
        WHERE wl.user_id = :user_id
        ORDER BY wl.exercise_id, ls.record_date DESC, wl.session_timestamp DESC, wl.set_number ASC
        """,
        {'user_id': user_id, 'exercise_ids': list(exercise_ids), 'record_date': before_date},
        fetchall=True,
    )

    history_by_exercise: Dict[int, List[Dict]] = defaultdict(list)
    for row in history_rows or []:
        history_by_exercise[row['exercise_id']].append(row)
    return history_by_exercise


def _fetch_recent_comments(
    user_id: int,
    exercise_ids: Iterable[int],
    before_date: date,
) -> Dict[int, Dict]:
    if not exercise_ids:
        return {}

    comment_rows = execute_query(
        """
        WITH ranked_sessions AS (
            SELECT DISTINCT exercise_id,
                            session_timestamp,
                            record_date,
                            ROW_NUMBER() OVER (
                                PARTITION BY exercise_id
                                ORDER BY record_date DESC, session_timestamp DESC
                            ) AS session_rank
            FROM workout_log
            WHERE user_id = :user_id
              AND exercise_id = ANY(:exercise_ids)
              AND record_date < :record_date
        ), limited_sessions AS (
            SELECT exercise_id, session_timestamp, record_date
            FROM ranked_sessions
            WHERE session_rank <= 2
        )
        SELECT wsc.exercise_id,
               wsc.comment,
               ls.record_date,
               wsc.id
        FROM workout_session_comments wsc
        JOIN limited_sessions ls
          ON wsc.exercise_id = ls.exercise_id
         AND wsc.session_timestamp = ls.session_timestamp
        WHERE wsc.user_id = :user_id
        ORDER BY ls.record_date DESC, wsc.id DESC
        """,
        {'user_id': user_id, 'exercise_ids': list(exercise_ids), 'record_date': before_date},
        fetchall=True,
    )

    latest_comments: Dict[int, Dict] = {}
    for row in comment_rows or []:
        if row['exercise_id'] not in latest_comments:
            latest_comments[row['exercise_id']] = row
    return latest_comments


def get_templates_with_history(user_id: int, before_date: date) -> List[Dict]:
    """Return templates enriched with history and comments."""

    templates = _fetch_templates(user_id)
    if not templates:
        return []

    exercise_ids = {ex['exercise_id'] for tpl in templates for ex in tpl['exercises']}
    history_map = _fetch_recent_sessions(user_id, exercise_ids, before_date)
    comment_map = _fetch_recent_comments(user_id, exercise_ids, before_date)

    for template in templates:
        for exercise in template['exercises']:
            sessions = []
            for row in history_map.get(exercise['exercise_id'], []):
                if not sessions or sessions[-1]['timestamp'] != row['session_timestamp']:
                    sessions.append(
                        {
                            'timestamp': row['session_timestamp'],
                            'date_formatted': row['record_date'].strftime('%d %b'),
                            'sets': [],
                        }
                    )
                sessions[-1]['sets'].append(f"{row['weight']}kg x {row['reps']}")
            exercise['history'] = sessions

            last_comment = comment_map.get(exercise['exercise_id'])
            exercise['last_comment'] = last_comment['comment'] if last_comment else None
            exercise['last_comment_date'] = (
                last_comment['record_date'].strftime('%d %b') if last_comment else None
            )
    return templates


def get_session_log_data(user_id: int, session_timestamp: str) -> Dict[str, Dict]:
    log_data: Dict[str, Dict] = {}
    if not session_timestamp:
        return log_data

    log_rows = execute_query(
        'SELECT exercise_id, set_number, reps, weight FROM workout_log '
        'WHERE user_id = :user_id AND session_timestamp = :timestamp',
        {'user_id': user_id, 'timestamp': session_timestamp},
        fetchall=True,
    )
    for row in log_rows or []:
        log_data[f"{row['exercise_id']}_{row['set_number']}"] = {'reps': row['reps'], 'weight': row['weight']}

    comment_rows = execute_query(
        'SELECT exercise_id, comment FROM workout_session_comments '
        'WHERE user_id = :user_id AND session_timestamp = :timestamp',
        {'user_id': user_id, 'timestamp': session_timestamp},
        fetchall=True,
    )
    for row in comment_rows or []:
        log_data[f"comment_{row['exercise_id']}"] = row['comment']

    return log_data
