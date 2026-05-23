# ============================================================
# 1. IMPORTS & SETUP
# ============================================================
from flask import Flask, render_template, request, redirect, session
import requests
from icalevents.icalevents import events
from datetime import datetime
import os
import sqlite3  
from functools import wraps
app = Flask(__name__)

# ============================================================
# 2. CONFIGURATION
# ============================================================
app.secret_key = 'my_local_testing_key'

# Tells Flask to instantly update the website when an HTML file is saved!
app.config['TEMPLATES_AUTO_RELOAD'] = True

family_users = {
    "dad": "hub123",
    "mom": "hub123",
    "kara": "hub123"
}


# ============================================================
# 3. DATABASE INITIALIZATION & HELPERS
# ============================================================
DB_PATH = os.environ.get('DATABASE_PATH', 'hub.db')

def init_db():
    """Creates our database file and tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Groceries Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS groceries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL
        )
    ''')

    # Chores Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            chore TEXT NOT NULL
        )
    ''')

    # Bugs Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS bugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'active'
        )
    ''')

    # Mileage Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS mileage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            doctor TEXT NOT NULL,
            distance_km REAL NOT NULL,
            notes TEXT
        )
    ''')

    conn.commit()   
    conn.close()    

# Run the setup function immediately when the app starts
init_db()

def get_db():
    """Helper function to cleanly open a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Lets us access columns by name (row['item'])
    return conn


# ============================================================
# 4. AUTHENTICATION & DECORATORS
# ============================================================
def login_required(f):
    """Decorator to protect routes from logged-out users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').lower()
        password = request.form.get('password')

        if username in family_users and family_users[username] == password:
            session['user'] = username
            return redirect('/')
        else:
            return "Incorrect password! Hit 'Back' and try again."

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


# ============================================================
# 5. PAGE & ACTION ROUTES
# ============================================================

# --- DASHBOARD ---
@app.route('/')
@login_required  
def home():
    # Weather Injection (Open-Meteo)
    current_temp = "Unavailable"
    try:
        # Belleville, ON coordinates
        url = "https://api.open-meteo.com/v1/forecast?latitude=44.18&longitude=-77.58&current_weather=true"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            current_temp = data.get('current_weather', {}).get('temperature', "Unavailable")
        else:
            app.logger.error(f"Weather API returned status {response.status_code}")
    except Exception as e:
        app.logger.error(f"Weather fetching failed: {e}")

    # Calendar Injection
    appointments = []
    try:
        secret_URL = os.environ.get('CALENDAR_URL', 'https://calendar.google.com/calendar/ical/josh.maddigan%40gmail.com/private-bcd741a8f528c29c34b74fee94de4788/basic.ics')
        upcoming_events = events(secret_URL, start=datetime.now())
        upcoming_events.sort(key=lambda x: x.start)
        appointments = upcoming_events[:5]
    except Exception as e:
        app.logger.error(f"Calendar fetching failed: {e}")

    return render_template('index.html', temp=current_temp, appointments=appointments)


# --- GROCERIES ---
@app.route('/groceries')
@login_required  
def groceries():
    conn = get_db()
    saved_groceries = conn.execute('SELECT * FROM groceries').fetchall()
    conn.close()
    return render_template('groceries.html', groceries=saved_groceries)

@app.route('/add', methods=['POST'])
@login_required
def add_item():
    new_item = request.form.get('item_name')
    if new_item:
        conn = get_db()
        conn.execute('INSERT INTO groceries (item) VALUES (?)', (new_item,))
        conn.commit()
        conn.close()
    return redirect('/groceries')

@app.route('/delete', methods=['POST'])
@login_required
def delete_item():
    item_id = request.form.get('item_id')
    if item_id:
        conn = get_db()
        conn.execute('DELETE FROM groceries WHERE id = ?', (item_id,))
        conn.commit()
        conn.close()
    return redirect('/groceries')


# --- CHORES ---
@app.route('/chores')
@login_required  
def chores():
    conn = get_db()
    rows = conn.execute('SELECT * FROM chores ORDER BY person').fetchall()
    conn.close()

    all_chores = {}
    for row in rows:
        person = row['person']
        if person not in all_chores:
            all_chores[person] = []
        if row['chore'] != '__placeholder__':
            all_chores[person].append({'chore': row['chore'], 'id': row['id']})

    return render_template('chores.html', all_chores=all_chores)

@app.route('/add_person', methods=['POST'])
@login_required
def add_person():
    name = request.form.get('new_person')
    if name:
        conn = get_db()
        existing = conn.execute('SELECT 1 FROM chores WHERE person = ?', (name,)).fetchone()
        if not existing:
            conn.execute('INSERT INTO chores (person, chore) VALUES (?, ?)', (name, '__placeholder__'))
            conn.commit()
        conn.close()
    return redirect('/chores')

@app.route('/add_chore', methods=['POST'])
@login_required
def add_chore():
    person = request.form.get('person')
    chore = request.form.get('chore_name')
    if person and chore:
        conn = get_db()
        conn.execute('INSERT INTO chores (person, chore) VALUES (?, ?)', (person, chore))
        conn.commit()
        conn.close()
    return redirect('/chores')

@app.route('/delete_chore', methods=['POST'])
@login_required
def delete_chore():
    chore_id = request.form.get('chore_id')
    if chore_id:
        conn = get_db()
        conn.execute('DELETE FROM chores WHERE id = ?', (chore_id,))
        conn.commit()
        conn.close()
    return redirect('/chores')


# --- BUG TRACKER ---
@app.route('/bugs')
@login_required
def view_bugs():
    conn = get_db()
    active_bugs = conn.execute("SELECT * FROM bugs WHERE status = 'active' ORDER BY id DESC").fetchall()
    resolved_bugs = conn.execute("SELECT * FROM bugs WHERE status = 'resolved' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('bugs.html', active_bugs=active_bugs, resolved_bugs=resolved_bugs)

@app.route('/report_bug', methods=['POST'])
@login_required
def report_bug():
    bug_text = request.form.get('bug_report')
    current_user = session.get('user', 'Unknown')
    if bug_text:
        timestamp = datetime.now().strftime('%b %d - %I:%M %p')
        conn = get_db()
        conn.execute(
            'INSERT INTO bugs (timestamp, reported_by, description) VALUES (?, ?, ?)',
            (timestamp, current_user, bug_text)
        )
        conn.commit()
        conn.close()
    return redirect('/')

@app.route('/resolve_bug', methods=['POST'])
@login_required
def resolved_bug():
    bug_id = request.form.get('bug_id')
    if bug_id:
        conn = get_db()
        conn.execute("UPDATE bugs SET status = 'resolved' WHERE id = ?", (bug_id,))
        conn.commit()
        conn.close()
    return redirect('/bugs')


# --- MILEAGE TRACKER ---
@app.route('/mileage')
@login_required
def mileage():
    conn = get_db()
    trips = conn.execute('SELECT * FROM mileage ORDER BY date DESC').fetchall()
    total_km = conn.execute('SELECT COALESCE(SUM(distance_km), 0) FROM mileage').fetchone()[0]
    conn.close()
    return render_template('mileage.html', trips=trips, total_km=total_km)

@app.route('/add_trip', methods=['POST'])
@login_required
def add_trip():
    date = request.form.get('date')
    doctor = request.form.get('doctor')
    distance_km = request.form.get('distance_km')
    notes = request.form.get('notes', '').strip()
    if date and doctor and distance_km:
        try:
            distance_km = float(distance_km)
            conn = get_db()
            conn.execute(
                'INSERT INTO mileage (date, doctor, distance_km, notes) VALUES (?, ?, ?, ?)',
                (date, doctor, distance_km, notes or None)
            )
            conn.commit()
            conn.close()
        except ValueError:
            pass
    return redirect('/mileage')

@app.route('/delete_trip', methods=['POST'])
@login_required
def delete_trip():
    trip_id = request.form.get('trip_id')
    if trip_id:
        conn = get_db()
        conn.execute('DELETE FROM mileage WHERE id = ?', (trip_id,))
        conn.commit()
        conn.close()
    return redirect('/mileage')


# ============================================================
# 6. SERVER START
# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

#  test!