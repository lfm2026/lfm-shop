import os
import sqlite3
import requests
import libsql_experimental as libsql
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "lfm_shop_secret_key_2026")

# Turso Credentials
TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "libsql://lfm-shop-db-lfm2026.aws-ap-northeast-1.turso.io")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJh")

# Admin Password Configuration
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")

def get_db():
    return libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)

# DB Initialization
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Products Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            colors TEXT,
            description TEXT
        )
    ''')
    
    # 2. Policies Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_text TEXT NOT NULL
        )
    ''')
    
    # 3. Orders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            product_code TEXT NOT NULL,
            color TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 4. Settings Table (For Access Tokens)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

# Run DB Initialization
init_db()

# --- ROUTES ---

@app.route('/')
def home():
    if not session.get('logged_in'):
        return render_template('index.html', page='login')
    return render_template('index.html', page='dashboard')

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('home'))
    return render_template('index.html', page='login', error="ভুল পাসওয়ার্ড!")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

# API: Add Policy
@app.route('/api/policy/add', methods=['POST'])
def add_policy():
    if not session.get('logged_in'): return jsonify({'error': 'Unauthorized'}), 401
    rule = request.json.get('rule')
    if rule:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO policies (rule_text) VALUES (?)", (rule,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid Input'}), 400

# API: Update Stock via Natural Language
@app.route('/api/update-stock', methods=['POST'])
def update_stock():
    if not session.get('logged_in'): return jsonify({'error': 'Unauthorized'}), 401
    text_input = request.json.get('text')
    # AI logic runs here to process text like "5 fan restocked"
    return jsonify({'status': 'success', 'message': f"ইনপুট গ্রহণ করা হয়েছে: {text_input}"})

# API: Save Access Token Settings
@app.route('/api/settings/save', methods=['POST'])
def save_settings():
    if not session.get('logged_in'): return jsonify({'error': 'Unauthorized'}), 401
    page_token = request.json.get('page_access_token')
    if page_token:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('meta_page_token', ?)", (page_token,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid Input'}), 400

# Social Media Webhook Route
@app.route('/webhook/facebook', methods=['GET', 'POST'])
def facebook_webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == "lfm_shop_verify_token":
            return challenge, 200
        return 'Verification failed', 403
    elif request.method == 'POST':
        # AI Webhook Response logic runs here
        return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    app.run(debug=True)
