# --- START OF FILE database.py ---
import sqlite3
from datetime import datetime, timedelta
import pytz

# NOTE on Security: In a production environment, passwords should be hashed.
# For simplicity here, we are storing them as plain text.
# Consider using a library like `werkzeug.security` for hashing.

def get_db_connection():
    conn = sqlite3.connect('healthcare.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, age INTEGER NOT NULL, gender TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_blocked BOOLEAN DEFAULT 0,
            weight REAL, height REAL, blood_group TEXT, chronic_illnesses TEXT,
            past_surgeries TEXT, genetic_diseases TEXT, last_checkup_date DATE,
            phone_number TEXT, emergency_number TEXT, address TEXT, photo_filename TEXT,
            notifications_enabled BOOLEAN DEFAULT 1, timezone TEXT, blood_sugar INTEGER,
            systolic_bp INTEGER, diastolic_bp INTEGER, cholesterol INTEGER,
            health_insurance_provider TEXT, health_policy_id TEXT, health_group_number TEXT,
            life_insurance_provider TEXT, life_policy_id TEXT, is_admin BOOLEAN DEFAULT 0
        )
    ''')
    
    user_columns = [i[1] for i in c.execute('PRAGMA table_info(users)').fetchall()]
    if 'weight' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN weight REAL')
    if 'height' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN height REAL')
    if 'blood_group' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN blood_group TEXT')
    if 'chronic_illnesses' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN chronic_illnesses TEXT')
    if 'past_surgeries' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN past_surgeries TEXT')
    if 'genetic_diseases' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN genetic_diseases TEXT')
    if 'last_checkup_date' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN last_checkup_date DATE')
    if 'phone_number' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN phone_number TEXT')
    if 'emergency_number' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN emergency_number TEXT')
    if 'address' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN address TEXT')
    if 'photo_filename' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN photo_filename TEXT')
    if 'notifications_enabled' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN notifications_enabled BOOLEAN DEFAULT 1')
    if 'timezone' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN timezone TEXT')
    if 'blood_sugar' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN blood_sugar INTEGER')
    if 'systolic_bp' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN systolic_bp INTEGER')
    if 'diastolic_bp' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN diastolic_bp INTEGER')
    if 'cholesterol' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN cholesterol INTEGER')
    if 'health_insurance_provider' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN health_insurance_provider TEXT')
    if 'health_policy_id' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN health_policy_id TEXT')
    if 'health_group_number' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN health_group_number TEXT')
    if 'life_insurance_provider' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN life_insurance_provider TEXT')
    if 'life_policy_id' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN life_policy_id TEXT')
    if 'is_admin' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
    if 'is_blocked' not in user_columns: c.execute('ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0')

    c.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
            dosage TEXT NOT NULL, frequency TEXT NOT NULL, start_date DATE NOT NULL, end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, medication_id INTEGER,
            med_name TEXT NOT NULL, time TEXT NOT NULL, days TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, doctor_name TEXT NOT NULL,
            specialty TEXT NOT NULL, date DATE NOT NULL, time TEXT NOT NULL, reason TEXT NOT NULL,
            reminder_time INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS exercise_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            calories_burned REAL NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS history_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT,
            event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS journal_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mood INTEGER NOT NULL,
            entry_text TEXT,
            gratitude_text TEXT, 
            sentiment TEXT,
            logged_at DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS physical_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS mental_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE, -- One subscription per user
            subscription_json TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS diet_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_html TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS health_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            review_html TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')


    plan_columns = [i[1] for i in c.execute('PRAGMA table_info(diet_plans)').fetchall()]
    if 'plan_text' not in plan_columns:
        c.execute('ALTER TABLE diet_plans ADD COLUMN plan_text TEXT NOT NULL DEFAULT ""')

    conn.commit()
    conn.close()

# New functions for Admin
def get_all_users():
    conn = get_db_connection()
    users = conn.execute('SELECT id, name, email, created_at, is_admin, is_blocked FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(user) for user in users]

def delete_user_and_data(user_id):
    conn = get_db_connection()
    # The ON DELETE CASCADE rule in the table definitions will handle deleting all associated data
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

# New functions for Journal
def add_journal_entry(user_id, mood, entry_text, gratitude_text, sentiment):
    conn = get_db_connection()
    today = datetime.now().date() # This is correct, it's just a date
    existing = conn.execute('SELECT id FROM journal_log WHERE user_id = ? AND logged_at = ?', (user_id, today)).fetchone()
    if existing:
        conn.execute('UPDATE journal_log SET mood = ?, entry_text = ?, gratitude_text = ?, sentiment = ? WHERE id = ?', (mood, entry_text, gratitude_text, sentiment, existing['id']))
    else:
        # START: EXPLICITLY SET created_at to UTC
        conn.execute('INSERT INTO journal_log (user_id, mood, entry_text, gratitude_text, sentiment, logged_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, mood, entry_text, gratitude_text, sentiment, today, datetime.utcnow()))
        # END: MODIFICATION
    conn.commit()
    conn.close()
    log_history(user_id, "Journal", "Logged daily mood and journal entry.")


def toggle_user_block_status(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    # Toggle the boolean value (0 to 1, or 1 to 0)
    c.execute('UPDATE users SET is_blocked = NOT is_blocked WHERE id = ?', (user_id,))
    conn.commit()
    # Get the new status to return it
    new_status = c.execute('SELECT is_blocked FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return new_status['is_blocked']

def get_journal_summary(user_id):
    conn = get_db_connection()
    query = """
        SELECT mood, logged_at, sentiment FROM journal_log
        WHERE user_id = ? AND date(logged_at) >= date('now', '-30 days')
        ORDER BY logged_at ASC
    """
    summary = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in summary]

def get_todays_journal_entry(user_id):
    conn = get_db_connection()
    today = datetime.now().date()
    entry = conn.execute('SELECT * FROM journal_log WHERE user_id = ? AND logged_at = ?', (user_id, today)).fetchone()
    conn.close()
    return dict(entry) if entry else None

# New function to add history events
def log_history(user_id, event_type, description):
    conn = get_db_connection()
    # START: EXPLICITLY SET event_timestamp to UTC
    conn.execute(
        'INSERT INTO history_log (user_id, event_type, description, event_timestamp) VALUES (?, ?, ?, ?)',
        (user_id, event_type, description, datetime.utcnow())
    )
    # END: MODIFICATION
    conn.commit()
    conn.close()

# New function to get user history
def get_user_history(user_id):
    conn = get_db_connection()
    history = conn.execute('SELECT * FROM history_log WHERE user_id = ? ORDER BY event_timestamp DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in history]

# New function to log weight
def log_weight_entry(user_id, weight):
    conn = get_db_connection()
    today = datetime.now().date()
    # Check if an entry for today already exists
    existing = conn.execute('SELECT id FROM weight_log WHERE user_id = ? AND logged_at = ?', (user_id, today)).fetchone()
    if existing:
        # Update today's entry
        conn.execute('UPDATE weight_log SET weight = ? WHERE id = ?', (weight, existing['id']))
    else:
        # Insert new entry for today
        conn.execute('INSERT INTO weight_log (user_id, weight, logged_at) VALUES (?, ?, ?)', (user_id, weight, today))
    conn.commit()
    conn.close()

# New function to get weight history
def get_user_weight_history(user_id):
    conn = get_db_connection()
    history = conn.execute('SELECT weight, logged_at FROM weight_log WHERE user_id = ? ORDER BY logged_at ASC', (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in history]

def log_exercise_entry(user_id, exercise_name, duration_seconds, calories_burned):
    conn = get_db_connection()
    c = conn.cursor()
    # START: EXPLICITLY SET completed_at to UTC
    c.execute('''
        INSERT INTO exercise_log (user_id, exercise_name, duration_seconds, calories_burned, completed_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, exercise_name, duration_seconds, calories_burned, datetime.utcnow()))
    # END: MODIFICATION
    conn.commit()
    log_id = c.lastrowid
    conn.close()
    log_history(user_id, 'Exercise', f"Completed {exercise_name} for {duration_seconds // 60}m {duration_seconds % 60}s.")
    return log_id


def get_user_exercise_log(user_id):
    conn = get_db_connection()
    logs = conn.execute('SELECT * FROM exercise_log WHERE user_id = ? ORDER BY completed_at DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(log) for log in logs]

# New function to get recent exercise for the dashboard chart
def get_exercise_summary(user_id):
    conn = get_db_connection()
    # Get total exercise duration per day for the last 7 days
    query = """
        SELECT date(completed_at) as day, SUM(duration_seconds) as total_duration
        FROM exercise_log
        WHERE user_id = ? AND date(completed_at) >= date('now', '-7 days')
        GROUP BY day
        ORDER BY day ASC
    """
    summary = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(row) for row in summary]


def create_user(name, email, password, age, gender, timezone='UTC'):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # START: EXPLICITLY SET created_at to UTC
        c.execute('''
            INSERT INTO users (name, email, password, age, gender, timezone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, password, age, gender, timezone, datetime.utcnow()))
        # END: MODIFICATION
        conn.commit()
        user_id = c.lastrowid
        log_history(user_id, 'Account', 'Account created successfully.')
        return user_id
    except sqlite3.IntegrityError: return None
    finally: conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_details(user_id, data):
    conn = get_db_connection()
    c = conn.cursor()

    # If weight is being updated, also log it
    if data.get('weight') is not None:
        log_weight_entry(user_id, data['weight'])
    
    # Log the update event
    log_history(user_id, 'Profile', 'User profile settings updated.')

    c.execute('''
        UPDATE users SET
            name = ?, age = ?, gender = ?, weight = ?, height = ?, 
            blood_group = ?, chronic_illnesses = ?, past_surgeries = ?, 
            genetic_diseases = ?, last_checkup_date = ?, phone_number = ?,
            emergency_number = ?, address = ?, notifications_enabled = ?,
            timezone = ?, blood_sugar = ?, systolic_bp = ?, diastolic_bp = ?, cholesterol = ?,
            health_insurance_provider = ?, health_policy_id = ?, health_group_number = ?,
            life_insurance_provider = ?, life_policy_id = ?
        WHERE id = ?
    ''', (
        data['name'], data['age'], data['gender'], data.get('weight'), data.get('height'),
        data.get('blood_group'), data.get('chronic_illnesses'), data.get('past_surgeries'),
        data.get('genetic_diseases'), data.get('last_checkup_date'), data.get('phone_number'),
        data.get('emergency_number'), data.get('address'), data.get('notifications_enabled'),
        data.get('timezone', 'UTC'), 
        data.get('blood_sugar'), data.get('systolic_bp'), data.get('diastolic_bp'), data.get('cholesterol'),
        data.get('health_insurance_provider'), data.get('health_policy_id'), data.get('health_group_number'),
        data.get('life_insurance_provider'), data.get('life_policy_id'),
        user_id
    ))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    return rows_affected > 0

def update_user_photo(user_id, photo_filename):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET photo_filename = ? WHERE id = ?', (photo_filename, user_id))
    conn.commit()
    conn.close()

def update_user_password(user_id, new_password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
    conn.commit()
    conn.close()
    # Log the password change event
    log_history(user_id, 'Security', 'Password was changed.')

def add_medication(user_id, name, dosage, frequency, start_date, end_date=None):
    conn = get_db_connection()
    c = conn.cursor()
    # START: EXPLICITLY SET created_at to UTC
    c.execute('''
        INSERT INTO medications (user_id, name, dosage, frequency, start_date, end_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, name, dosage, frequency, start_date, end_date, datetime.utcnow()))
    # END: MODIFICATION
    conn.commit()
    medication_id = c.lastrowid
    conn.close()
    log_history(user_id, 'Medication', f"Added new medication: {name}.")
    return medication_id

def get_user_medications(user_id):
    conn = get_db_connection()
    medications = conn.execute('SELECT * FROM medications WHERE user_id = ? ORDER BY start_date DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(med) for med in medications]

def update_medication(medication_id, user_id, data):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE medications SET name = ?, dosage = ?, frequency = ?, start_date = ?, end_date = ?
        WHERE id = ? AND user_id = ?
    ''', (data['name'], data['dosage'], data['frequency'], data['start_date'], data.get('end_date'), medication_id, user_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    if rows_affected > 0:
        log_history(user_id, 'Medication', f"Updated medication: {data['name']}.")
    return rows_affected > 0

def delete_medication(medication_id, user_id):
    conn = get_db_connection()
    c = conn.cursor()
    # We need to get the name before deleting
    med_name = c.execute('SELECT name FROM medications WHERE id = ?', (medication_id,)).fetchone()
    c.execute('DELETE FROM medications WHERE id = ? AND user_id = ?', (medication_id, user_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    if rows_affected > 0 and med_name:
        log_history(user_id, 'Medication', f"Deleted medication: {med_name['name']}.")
    return rows_affected > 0

def add_reminder(user_id, med_name, time, days, medication_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    # START: EXPLICITLY SET created_at to UTC
    c.execute('''
        INSERT INTO reminders (user_id, medication_id, med_name, time, days, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, medication_id, med_name, time, ','.join(days), datetime.utcnow()))
    # END: MODIFICATION
    conn.commit()
    reminder_id = c.lastrowid
    conn.close()
    return reminder_id

def get_user_reminders(user_id):
    conn = get_db_connection()
    reminders = conn.execute('SELECT * FROM reminders WHERE user_id = ? ORDER BY time', (user_id,)).fetchall()
    conn.close()
    return [dict(rem) for rem in reminders]

def update_reminder(reminder_id, user_id, data):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE reminders SET med_name = ?, time = ?, days = ?
        WHERE id = ? AND user_id = ?
    ''', (data['medName'], data['time'], ','.join(data['days']), reminder_id, user_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    return rows_affected > 0

def delete_reminder(reminder_id, user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM reminders WHERE id = ? AND user_id = ?', (reminder_id, user_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    return rows_affected > 0

def add_appointment(user_id, doctor_name, specialty, date, time, reason, reminder_time):
    conn = get_db_connection()
    c = conn.cursor()
    # START: EXPLICITLY SET created_at to UTC
    c.execute('''
        INSERT INTO appointments (user_id, doctor_name, specialty, date, time, reason, reminder_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, doctor_name, specialty, date, time, reason, reminder_time, datetime.utcnow()))
    # END: MODIFICATION
    conn.commit()
    appointment_id = c.lastrowid
    conn.close()
    log_history(user_id, 'Appointment', f"Scheduled with Dr. {doctor_name} on {date}.")
    return appointment_id

def get_user_appointments(user_id):
    conn = get_db_connection()
    # Sort by date and time
    appointments = conn.execute('SELECT * FROM appointments WHERE user_id = ? ORDER BY date, time', (user_id,)).fetchall()
    conn.close()
    return [dict(app) for app in appointments]

def update_appointment(appointment_id, user_id, data):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE appointments SET doctor_name = ?, specialty = ?, date = ?, time = ?, reason = ?, reminder_time = ?
        WHERE id = ? AND user_id = ?
    ''', (data['doctorName'], data['specialty'], data['date'], data['time'], data['reason'], data['reminderTime'], appointment_id, user_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    if rows_affected > 0:
        log_history(user_id, 'Appointment', f"Updated appointment with Dr. {data['doctorName']}.")
    return rows_affected > 0

def delete_appointment(appointment_id, user_id):
    conn = get_db_connection()
    c = conn.cursor()
    appt = c.execute('SELECT doctor_name FROM appointments WHERE id = ?', (appointment_id,)).fetchone()
    c.execute('DELETE FROM appointments WHERE id = ? AND user_id = ?', (appointment_id, user_id))
    conn.commit()
    rows_affected = c.rowcount
    conn.close()
    if rows_affected > 0 and appt:
        log_history(user_id, 'Appointment', f"Canceled appointment with Dr. {appt['doctor_name']}.")
    return rows_affected > 0

def get_all_journal_entries(user_id):
    conn = get_db_connection()
    query = """
        SELECT * FROM journal_log
        WHERE user_id = ?
        ORDER BY logged_at DESC
    """
    entries = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(entry) for entry in entries]

def add_physical_chat_message(user_id, role, content):
    conn = get_db_connection()
    # START: EXPLICITLY SET timestamp to UTC
    conn.execute(
        'INSERT INTO physical_chat_history (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
        (user_id, role, content, datetime.utcnow())
    )
    # END: MODIFICATION
    conn.commit()
    conn.close()

def get_physical_chat_history(user_id):
    conn = get_db_connection()
    history = conn.execute(
        'SELECT role, content, timestamp FROM physical_chat_history WHERE user_id = ? ORDER BY timestamp ASC',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in history]

def add_mental_chat_message(user_id, role, content):
    conn = get_db_connection()
    # START: EXPLICITLY SET timestamp to UTC
    conn.execute(
        'INSERT INTO mental_chat_history (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
        (user_id, role, content, datetime.utcnow())
    )
    # END: MODIFICATION
    conn.commit()
    conn.close()

def get_mental_chat_history(user_id):
    conn = get_db_connection()
    history = conn.execute(
        'SELECT role, content, timestamp FROM mental_chat_history WHERE user_id = ? ORDER BY timestamp ASC',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in history]

def clear_physical_chat_history(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM physical_chat_history WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def clear_mental_chat_history(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM mental_chat_history WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def save_push_subscription(user_id, subscription_json):
    conn = get_db_connection()
    # Using REPLACE ensures that if a subscription for the user already exists,
    # it gets updated without causing a UNIQUE constraint error. This is crucial.
    conn.execute(
        'REPLACE INTO push_subscriptions (user_id, subscription_json) VALUES (?, ?)',
        (user_id, subscription_json)
    )
    conn.commit()
    conn.close()
    
def get_push_subscription(user_id):
    conn = get_db_connection()
    sub = conn.execute('SELECT subscription_json FROM push_subscriptions WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return sub['subscription_json'] if sub else None

def get_users_with_push_subscriptions():
    """
    Fetches all users who have both push notifications enabled and a saved subscription.
    """
    conn = get_db_connection()
    # We join the users table with the push_subscriptions table
    users = conn.execute("""
        SELECT u.id, u.timezone
        FROM users u
        JOIN push_subscriptions ps ON u.id = ps.user_id
        WHERE u.notifications_enabled = 1
    """).fetchall()
    conn.close()
    return [dict(user) for user in users]

def get_due_reminders(current_utc_time):
    """
    Fetches reminders that are due at the given UTC time.
    """
    conn = get_db_connection()
    
    # We need to get all users and their timezones to check the time correctly for each one.
    users = conn.execute('SELECT id, timezone FROM users').fetchall()
    
    due_reminders = []
    
    for user in users:
        user_id = user['id']
        try:
            # Get the current time in the user's specific timezone
            user_tz = pytz.timezone(user['timezone'] or 'UTC')
            now_local = current_utc_time.astimezone(user_tz)
            
            # Format to 'HH:MM' for matching and 'dddd' for weekday
            current_local_time_str = now_local.strftime('%H:%M')
            current_local_weekday_str = now_local.strftime('%A').lower()
            
            # Query reminders for this user that match the current time and weekday
            reminders = conn.execute(
                "SELECT med_name, user_id FROM reminders WHERE user_id = ? AND time = ? AND days LIKE ?",
                (user_id, current_local_time_str, f'%{current_local_weekday_str}%')
            ).fetchall()
            
            for rem in reminders:
                due_reminders.append(dict(rem))

        except pytz.UnknownTimeZoneError:
            # Handle cases where the timezone string is invalid
            continue
            
    conn.close()
    return due_reminders

def get_due_appointment_reminders(current_utc_time):
    """
    Fetches appointments that are due for a reminder at the given UTC time.
    """
    conn = get_db_connection()
    
    # Get all users to check against their local time
    users = conn.execute('SELECT id, timezone FROM users').fetchall()
    
    due_appointments = []
    
    for user in users:
        user_id = user['id']
        try:
            user_tz = pytz.timezone(user['timezone'] or 'UTC')
            now_local = current_utc_time.astimezone(user_tz)

            # Get all upcoming appointments for this user
            appointments = conn.execute(
                "SELECT * FROM appointments WHERE user_id = ? AND date >= ?",
                (user_id, now_local.strftime('%Y-%m-%d'))
            ).fetchall()

            for appt in appointments:
                # Combine the appointment date and time into a single datetime object
                appt_dt_str = f"{appt['date']} {appt['time']}"
                appt_dt_naive = datetime.strptime(appt_dt_str, '%Y-%m-%d %H:%M')
                appt_dt_local = user_tz.localize(appt_dt_naive)
                
                # Calculate when the reminder should be sent
                reminder_hours_before = appt['reminder_time']
                reminder_send_time = appt_dt_local - timedelta(hours=reminder_hours_before)
                
                # CHECK IF THE CURRENT MINUTE MATCHES THE CALCULATED REMINDER TIME
                # We check if the current time is within the same minute as the reminder time
                if now_local.strftime('%Y-%m-%d %H:%M') == reminder_send_time.strftime('%Y-%m-%d %H:%M'):
                    due_appointments.append(dict(appt))

        except (pytz.UnknownTimeZoneError, ValueError):
            continue
            
    conn.close()
    return due_appointments

def save_diet_plan(user_id, plan_html):
    """Saves a new diet plan for the user and returns True on success."""
    conn = None
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO diet_plans (user_id, plan_html, created_at) VALUES (?, ?, ?)',
            (user_id, plan_html, datetime.utcnow())
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"DATABASE ERROR in save_diet_plan: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_latest_diet_plan(user_id):
    """Retrieves the most recent diet plan (as HTML) for the user."""
    conn = get_db_connection()
    plan = conn.execute(
        'SELECT plan_html FROM diet_plans WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    conn.close()
    return plan['plan_html'] if plan else None

def toggle_user_admin_status(user_id):
    """Toggles a user's is_admin status from 0 to 1 or 1 to 0."""
    conn = get_db_connection()
    # Get the current status first to log it correctly later
    current_status = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if current_status is None:
        conn.close()
        return None # User not found

    # Toggle the boolean value
    conn.execute('UPDATE users SET is_admin = NOT is_admin WHERE id = ?', (user_id,))
    conn.commit()
    
    # Get the new status to return it
    new_status = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return new_status['is_admin']

def save_health_review(user_id, review_html):
    """Saves a new health review for the user."""
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO health_reviews (user_id, review_html, created_at) VALUES (?, ?, ?)',
        (user_id, review_html, datetime.utcnow())
    )
    conn.commit()
    conn.close()

def get_latest_health_review(user_id):
    """Retrieves the most recent health review for the user."""
    conn = get_db_connection()
    review = conn.execute(
        'SELECT review_html FROM health_reviews WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    conn.close()
    return review['review_html'] if review else None

init_db()
# --- END OF FILE database.py ---