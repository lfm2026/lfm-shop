import os
import requests
import libsql_client
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

app = Flask(__name__)

# Render-এর Environment Variable থেকে Secret Key ও API Keys নেওয়া
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "lfm_shop_secret_key_2026")

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "libsql://lfm-shop-db-lfm2026.aws-ap-northeast-1.turso.io")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJh")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Turso Database Client
def get_db_client():
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

# ডাটাবেজ টেবিল অটো-ক্রিয়েশন
def init_db():
    try:
        client = get_db_client()
        
        # ১. প্রোডাক্ট টেবিল
        client.execute('''
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
        
        # ২. পলিসি টেবিল
        client.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_text TEXT NOT NULL
            )
        ''')
        
        # ৩. অর্ডার টেবিল
        client.execute('''
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
        
        # ৪. সেটিংসে Access Token রাখার টেবিল
        client.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        print("Turso Database Table setup successfully!")
    except Exception as e:
        print(f"Turso Setup Error: {e}")

# ডাটাবেজ ইনিশিয়ালাইজেশন রান করা
init_db()

# --- WEB ROUTES & ADMIN DASHBOARD ---

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

# API: Natural Language দিয়ে স্টক এডিট করা (Update Page)
@app.route('/api/update-stock', methods=['POST'])
def update_stock():
    if not session.get('logged_in'): 
        return jsonify({'error': 'Unauthorized'}), 401
    
    text_input = request.json.get('text')
    # AI দিয়ে স্টক আপডেট করার লজিক
    return jsonify({'status': 'success', 'message': f"ইনপুট গ্রহণ করা হয়েছে: {text_input}"})

# API: পলিসি যুক্ত করা (Policy Page)
@app.route('/api/policy/add', methods=['POST'])
def add_policy():
    if not session.get('logged_in'): 
        return jsonify({'error': 'Unauthorized'}), 401
    
    rule = request.json.get('rule')
    if rule:
        client = get_db_client()
        client.execute("INSERT INTO policies (rule_text) VALUES (?)", (rule,))
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid Input'}), 400

# API: Page Access Token সেভ করা (Settings Page)
@app.route('/api/settings/save', methods=['POST'])
def save_settings():
    if not session.get('logged_in'): 
        return jsonify({'error': 'Unauthorized'}), 401
    
    page_token = request.json.get('page_access_token')
    if page_token:
        client = get_db_client()
        client.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('meta_page_token', ?)", (page_token,))
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid Input'}), 400

# --- SOCIAL MEDIA WEBHOOK ROUTE ---

@app.route('/webhook/facebook', methods=['GET', 'POST'])
def facebook_webhook():
    if request.method == 'GET':
        # মেটা ডেভলপার প্যানেল ভেরিফিকেশন
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == "lfm_shop_verify_token":
            return challenge, 200
        return 'Verification failed', 403
        
    elif request.method == 'POST':
        # কাস্টমারের মেসেজ গ্রহণ ও Groq/Gemini AI দিয়ে উত্তর দেওয়ার মূল জায়গা
        data = request.json
        return 'EVENT_RECEIVED', 200

if __name__ == '__main__':
    app.run(debug=True)
