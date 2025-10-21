import psycopg2
import bcrypt
import os
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

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Esegui lo schema SQL
    with open('schema.sql', 'r') as f:
        cur.execute(f.read())
    
    # Controlla e inserisci utente Admin
    cur.execute("SELECT id FROM users WHERE username = 'Admin'")
    if cur.fetchone() is None:
        hashed_pw = bcrypt.hashpw('BingoBongo1998!%'.encode('utf-8'), bcrypt.gensalt())
        cur.execute(
            "INSERT INTO users (username, password, is_admin, has_seen_welcome_message) VALUES (%s, %s, %s, %s)",
            ('Admin', hashed_pw.decode('utf-8'), 1, 1)
        )
        print("Utente amministratore 'Admin' creato con successo.")

    # Controlla e inserisci utente Gerardo
    cur.execute("SELECT id FROM users WHERE username = 'Gerardo'")
    if cur.fetchone() is None:
        hashed_pw = bcrypt.hashpw('ScemoChiLegge1998!%'.encode('utf-8'), bcrypt.gensalt())
        cur.execute(
            "INSERT INTO users (username, password, is_admin, has_seen_welcome_message) VALUES (%s, %s, %s, %s)",
            ('Gerardo', hashed_pw.decode('utf-8'), 0, 1)
        )
        print("Utente 'Gerardo' creato con successo.")

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