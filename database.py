import json
import os

import bcrypt
import psycopg2
from dotenv import load_dotenv

# Carica le variabili d'ambiente
load_dotenv()

# Legge la stringa di connessione completa dal file .env
DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL non è impostato nel file .env")
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def _seed_initial_users(cur):
    seed_payload = os.environ.get('INITIAL_USERS_JSON')
    if not seed_payload:
        return

    try:
        initial_users = json.loads(seed_payload)
    except json.JSONDecodeError:
        print("INITIAL_USERS_JSON non valido. Assicurati che sia una lista JSON di utenti.")
        return

    if not isinstance(initial_users, list):
        print("INITIAL_USERS_JSON deve essere una lista di oggetti utente.")
        return

    for entry in initial_users:
        username = entry.get('username')
        password = entry.get('password')
        is_admin = 1 if entry.get('is_admin') else 0
        has_seen_welcome = 1 if entry.get('has_seen_welcome_message', False) else 0

        if not username or not password:
            continue

        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone() is not None:
            continue

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "INSERT INTO users (username, password, is_admin, has_seen_welcome_message) VALUES (%s, %s, %s, %s)",
            (username, hashed_pw, is_admin, has_seen_welcome),
        )
        print(f"Utente '{username}' creato dal seeding iniziale.")


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Esegui lo schema SQL
    with open('schema.sql', 'r') as f:
        cur.execute(f.read())

    _seed_initial_users(cur)

    # Inserisci alimenti globali
    cur.execute("SELECT COUNT(id) FROM foods WHERE user_id IS NULL")
    if cur.fetchone()[0] == 0:
        initial_foods = [
            ('Petto di pollo', 100, 31.0, 0.0, 3.6, 165.0),
            ('Riso bianco', 100, 2.7, 28.0, 0.3, 130.0)
        ]
        cur.executemany(
            "INSERT INTO foods (name, ref_weight, protein, carbs, fat, calories) VALUES (%s, %s, %s, %s, %s, %s)",
            initial_foods
        )
        print(f"{len(initial_foods)} alimenti globali iniziali aggiunti.")

    # Inserisci esercizi globali
    cur.execute("SELECT COUNT(id) FROM exercises WHERE user_id IS NULL")
    if cur.fetchone()[0] == 0:
        initial_exercises = [
            ('Panca Piana',),
            ('Squat con Bilanciere',),
            ('Trazioni alla Sbarra',)
        ]
        cur.executemany(
            "INSERT INTO exercises (name) VALUES (%s)",
            initial_exercises
        )
        print(f"{len(initial_exercises)} esercizi globali iniziali aggiunti.")

    conn.commit()
    cur.close()
    conn.close()


if __name__ == '__main__':
    print("Inizializzazione del database PostgreSQL...")
    init_db()
    print("Database inizializzato con successo.")
