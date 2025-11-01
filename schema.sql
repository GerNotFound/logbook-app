-- Abilita la cancellazione a cascata per le chiavi esterne
-- (Buona pratica da avere all'inizio dello script)
DROP TABLE IF EXISTS workout_session_comments, workout_log, workout_sessions, template_exercises, workout_templates, user_exercise_notes, exercises, user_macro_targets, cardio_log, diet_log, foods, daily_data, user_notes, user_profile, users CASCADE;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_superuser INTEGER NOT NULL DEFAULT 0,
    has_seen_welcome_message INTEGER NOT NULL DEFAULT 0,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    lock_until TIMESTAMP,
    last_login_at TIMESTAMP,
    last_active_at TIMESTAMP
);

CREATE TABLE user_profile (
    user_id INTEGER PRIMARY KEY,
    birth_date DATE,
    height REAL,
    gender TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE user_login_activity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    login_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ip_address TEXT
);

CREATE TABLE user_notes (
    user_id INTEGER PRIMARY KEY,
    content TEXT,
    content_shared TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE daily_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    weight REAL,
    weight_time TEXT,
    sleep TEXT,
    sleep_quality INTEGER,
    calories INTEGER,
    neck REAL,
    waist REAL,
    hip REAL,
    measure_time TEXT,
    bfp_manual REAL,
    total_protein REAL DEFAULT 0,
    total_carbs REAL DEFAULT 0,
    total_fat REAL DEFAULT 0,
    day_type TEXT,
    UNIQUE(user_id, record_date),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE foods (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    name TEXT NOT NULL,
    ref_weight REAL NOT NULL DEFAULT 100,
    protein REAL NOT NULL,
    carbs REAL NOT NULL,
    fat REAL NOT NULL,
    calories REAL NOT NULL,
    UNIQUE(name, user_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE diet_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    food_id INTEGER NOT NULL,
    weight REAL NOT NULL,
    protein REAL NOT NULL,
    carbs REAL NOT NULL,
    fat REAL NOT NULL,
    calories REAL NOT NULL,
    log_date DATE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (food_id) REFERENCES foods (id) ON DELETE CASCADE
);

CREATE TABLE intake_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    tracker_type TEXT NOT NULL,
    amount REAL NOT NULL,
    unit TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX idx_intake_log_user_date ON intake_log(user_id, record_date);

CREATE TABLE cardio_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    location TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    distance_km REAL,
    duration_min INTEGER,
    incline REAL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE user_macro_targets (
    user_id INTEGER PRIMARY KEY,
    days_on INTEGER DEFAULT 0,
    days_off INTEGER DEFAULT 0,
    p_on REAL DEFAULT 1.8,
    c_on REAL DEFAULT 5.0,
    f_on REAL DEFAULT 0.55,
    p_off REAL DEFAULT 1.8,
    c_off REAL DEFAULT 3.0,
    f_off REAL DEFAULT 0.70,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE exercises (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    name TEXT NOT NULL,
    consigli TEXT,
    UNIQUE(name, user_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE user_exercise_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    notes TEXT,
    UNIQUE(user_id, exercise_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
);

CREATE TABLE workout_templates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE template_exercises (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    sets TEXT NOT NULL,
    FOREIGN KEY (template_id) REFERENCES workout_templates (id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
);

CREATE TABLE workout_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_timestamp TEXT NOT NULL UNIQUE,
    record_date DATE NOT NULL,
    template_name TEXT,
    duration_minutes INTEGER,
    session_note TEXT,
    session_rating INTEGER CHECK (session_rating BETWEEN 1 AND 10),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE workout_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    record_date DATE NOT NULL,
    session_timestamp TEXT NOT NULL,
    set_number INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    weight REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE,
    FOREIGN KEY (session_timestamp) REFERENCES workout_sessions(session_timestamp) ON DELETE CASCADE
);

CREATE TABLE workout_session_comments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_timestamp TEXT NOT NULL,
    exercise_id INTEGER NOT NULL,
    comment TEXT,
    UNIQUE(user_id, session_timestamp, exercise_id),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS privacy_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    content TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO privacy_settings (id, content)
VALUES (1, '')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS communication_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    welcome_message TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO communication_settings (id, welcome_message)
VALUES (1, 'Benvenuto in Logbook! Gli amministratori possono aiutarti a mantenere aggiornati i tuoi dati di allenamento. Puoi sempre gestire le autorizzazioni dalle impostazioni del tuo profilo.')
ON CONFLICT (id) DO UPDATE SET welcome_message = EXCLUDED.welcome_message, updated_at = CURRENT_TIMESTAMP;

-- NUOVO: Aggiunta degli indici per migliorare le performance
CREATE INDEX IF NOT EXISTS idx_daily_data_user_date ON daily_data(user_id, record_date);
CREATE INDEX IF NOT EXISTS idx_diet_log_user_date ON diet_log(user_id, log_date);
CREATE INDEX IF NOT EXISTS idx_cardio_log_user_date ON cardio_log(user_id, record_date);
CREATE INDEX IF NOT EXISTS idx_workout_log_user_date ON workout_log(user_id, record_date);
CREATE INDEX IF NOT EXISTS idx_workout_log_user_exercise ON workout_log(user_id, exercise_id);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_user_date ON workout_sessions(user_id, record_date);
CREATE INDEX IF NOT EXISTS idx_user_login_activity_user_time ON user_login_activity(user_id, login_at DESC);