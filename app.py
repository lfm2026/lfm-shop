import os
import json
import requests
import libsql_client
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from groq import Groq
from google import genai

app = Flask(__name__)

# Flask Secret Key
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "lfm_shop_secret_key_2026")

# Turso Database Credentials
TURSO_URL = "libsql://lfm-shop-db-lfm2026.aws-ap-northeast-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJh"

# 🔑 আপনার সিক্রেট পাসওয়ার্ড
ADMIN_PASSWORD = "my@as"

# Render Environment Variables থেকে API Key পড়া
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# AI Clients Initialization
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

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


# ---------------------------------------------------------
# 🤖 PUBLIC ROUTE: মেইন লিঙ্কে ভিজিটরদের AI Chatbot থাকবে
# ---------------------------------------------------------

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/api/chat-room', methods=['POST'])
def chat_room_reply():
    user_msg = request.json.get('message', '')
    if not user_msg:
        return jsonify({'reply': 'অনুগ্রহ করে কিছু লিখুন।'})

    try:
        client = get_db_client()
        products_res = client.execute("SELECT product_code, name, price, stock, colors FROM products")
        
        products_info = "শপের বর্তমান প্রোডাক্ট তালিকা ও স্টক:\n"
        for row in products_res.rows:
            products_info += f"- Code: {row[0]}, Name: {row[1]}, Price: {row[2]} Tk, Stock: {row[3]}, Colors: {row[4]}\n"

        prompt = f"""
        You are an AI Sales Assistant for 'Loop For Money (LFM)'.
        Be polite, helpful, and speak in conversational Bengali.
        Here is the current product stock data from database:
        {products_info}

        Customer Question: "{user_msg}"
        Give a clear, short answer to the customer based on available stock.
        """

        if groq_client:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile"
            )
            reply = response.choices[0].message.content
        elif gemini_client:
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            reply = response.text.strip()
        else:
            reply = "AI সার্ভিস বর্তমানে অফলাইনে আছে।"

        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'reply': f"ত্রুটি ঘটেছে: {str(e)}"})


# ---------------------------------------------------------
# 🔐 ADMIN ROUTES: /ad লিঙ্কে অ্যাডমিন ড্যাশবোর্ড থাকবে
# ---------------------------------------------------------

@app.route('/ad')
def admin_dashboard():
    if not session.get('logged_in'):
        return render_template('index.html', page='login')
    return render_template('index.html', page='dashboard')

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('admin_dashboard'))
    return render_template('index.html', page='login', error="ভুল পাসওয়ার্ড!")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_dashboard'))


# --- ADMIN BACKEND APIS ---

# API: Data Page-এর জন্য সব প্রোডাক্ট দেখানো
@app.route('/api/products', methods=['GET'])
def get_products():
    if not session.get('logged_in'): 
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        client = get_db_client()
        result = client.execute("SELECT product_code, name, price, stock, colors FROM products")
        products = []
        for row in result.rows:
            products.append({
                'code': row[0], 'name': row[1], 'price': row[2], 'stock': row[3], 'colors': row[4]
            })
        return jsonify(products)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Groq AI দিয়ে স্টক আপডেট করা (Update Page)
@app.route('/api/update-stock', methods=['POST'])
def update_stock():
    if not session.get('logged_in'): 
        return jsonify({'error': 'Unauthorized'}), 401
    
    text_input = request.json.get('text')
    
    if not text_input or not groq_client:
        return jsonify({'status': 'error', 'message': 'ইনপুট বা Groq API কি পাওয়া যায়নি!'}), 400

    try:
        prompt = f"""
        Extract product code and quantity changes from the user text.
        Text: "{text_input}"
        Respond strictly in JSON format like this:
        {{"updates": [{{"product_code": "P101", "change": 5}}, {{"product_code": "P102", "change": -2}}]}}
        """
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        client = get_db_client()
        
        for item in data.get('updates', []):
            code = item.get('product_code')
            change = item.get('change', 0)
            client.execute(
                "UPDATE products SET stock = stock + ? WHERE product_code = ?",
                (change, code)
            )
            
        return jsonify({'status': 'success', 'message': 'ডাটাবেজ স্টক সফলভাবে আপডেট হয়েছে!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API: Gemini AI দিয়ে এড্রেস ভেরিফাই করা
@app.route('/api/verify-address', methods=['POST'])
def verify_address():
    raw_address = request.json.get('address')
    if not raw_address or not gemini_client:
        return jsonify({'verified_address': raw_address})
    
    try:
        prompt = f"Verify and format this Bangladeshi shipping address clearly: {raw_address}"
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return jsonify({'verified_address': response.text.strip()})
    except Exception as e:
        return jsonify({'verified_address': raw_address})

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

# API: Access Token সেভ করা (Settings Page)
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


# ---------------------------------------------------------
# 📩 SOCIAL MEDIA WEBHOOK ROUTE (Messenger/Instagram)
# ---------------------------------------------------------

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
        return 'EVENT_RECEIVED', 200


if __name__ == '__main__':
    app.run(debug=True)
