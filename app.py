import os
import sqlite3
import libsql_client
from flask import Flask, render_template, request, jsonify, session
from google import genai  # Google Gemini SDK
from groq import Groq

app = Flask(__name__)
app.secret_key = "goneo_super_secret_key_2026"

# Environment Variables Configuration
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Fix LibSQL Protocol for Turso Connection
if TURSO_URL and (TURSO_URL.startswith("libsql://") or TURSO_URL.startswith("wss://")):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://").replace("wss://", "https://")

def get_turso_client():
    if TURSO_URL and TURSO_TOKEN:
        return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    return None

# AI Clients Initialization
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Database Handler Function
def db_execute(query, params=()):
    client = get_turso_client()
    if client:
        return client.execute(query, params)
    else:
        conn = sqlite3.connect("gonio.db")
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        rows = cursor.fetchall()
        conn.close()
        return rows

# Initialize Database Tables
def init_db():
    queries = [
        """CREATE TABLE IF NOT EXISTS customers (
            mobile_number TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            address TEXT,
            google_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mobile_number TEXT,
            platform TEXT,
            sender TEXT,
            message_text TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mobile_number TEXT,
            issue_type TEXT,
            message_text TEXT,
            admin_reply TEXT,
            status TEXT DEFAULT 'unread',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    ]
    for q in queries:
        try:
            db_execute(q)
        except Exception as e:
            print(f"DB Init Warning: {e}")

init_db()

@app.route('/')
def home():
    return render_template('index.html')

# --- ১. চ্যাট API (Groq + Gemini Live Maps Integration) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_msg = data.get("message", "").strip()
    mobile = data.get("mobile", "").strip()
    address_input = data.get("address", "").strip()

    if not user_msg:
        return jsonify({"status": "error", "response": "অনুগ্রহ করে একটি বার্তা লিখুন।"})

    # ১. ইউজার ঠিকানা দিলে Gemini Live Search/Maps ব্যবহার করে ভেরিফাই করা
    verified_address = ""
    if address_input and gemini_client:
        try:
            map_prompt = f"কাস্টমারের প্রদানকৃত ঠিকানাটি বিশ্লেষণ করে গুগল ম্যাপস অনুযায়ী সঠিক পূর্ণাঙ্গ ঠিকানা বের করো: '{address_input}'"
            map_res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=map_prompt,
                config={'tools': [{'google_search': {}}]}
            )
            verified_address = map_res.text
            if mobile:
                db_execute("UPDATE customers SET address = ? WHERE mobile_number = ?", (verified_address, mobile))
        except Exception:
            verified_address = address_input

    # ২. ভুল সনাক্তকরণের ক্ষেত্রে অটো-অ্যালার্ট
    negative_keywords = ["ভুল", "ভুল হইছে", "ভুল শনাক্ত", "এডা না", "এটা না", "wrong"]
    if any(k in user_msg.lower() for k in negative_keywords):
        if mobile:
            db_execute(
                "INSERT INTO reports (mobile_number, issue_type, message_text, status) VALUES (?, ?, ?, ?)",
                (mobile, "Live Admin Support", f"প্রোডাক্ট ভুল শনাক্তের অভিযোগ: {user_msg}", "unread")
            )
            db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'web', 'bot', ?)", 
                       (mobile, "ভুল সনাক্তকরণের জন্য দুঃখিত। আমাদের লাইভ অ্যাডমিন দ্রুত আপনার সাথে যোগাযোগ করছে।"))
        
        return jsonify({
            "status": "success", 
            "response": "আন্তরিকভাবে দুঃখিত! প্রোডাক্টটি ভুল সনাক্ত করার জন্য আমরা অনুতপ্ত। অনুগ্রহ করে আমাদের অ্যাডমিন লাইনে আসা পর্যন্ত অপেক্ষা করুন, একজন প্রতিনিধি খুব দ্রুত চ্যাটে যোগ দিচ্ছেন।"
        })

    # ৩. মূল AI রেসপন্স (Groq Primary Bot)
    bot_reply = ""
    if groq_client:
        try:
            sys_prompt = """তুমি GoNeo AI - একটি অত্যন্ত বুদ্ধিমতি ও কাস্টমার ফ্রেন্ডলি এআই অ্যাসিস্ট্যান্ট। 
            বাংলায় সুন্দর ও সংক্ষিপ্ত উত্তর দেবে। কাস্টমারকে যথাসম্ভব সঠিক তথ্য দিয়ে সাহায্য করবে।"""
            
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7,
                max_tokens=400
            )
            bot_reply = completion.choices[0].message.content
        except Exception:
            bot_reply = None

    # Groq API কাজ না করলে বা কনফিগার করা না থাকলে Gemini/Fallback সিস্টেম
    if not bot_reply and gemini_client:
        try:
            res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_msg
            )
            bot_reply = res.text
        except Exception:
            bot_reply = None

    if not bot_reply:
        bot_reply = f"GoNeo: আমি আপনার বার্তা '{user_msg}' পেয়েছি। আপনাকে কীভাবে সাহায্য করতে পারি?"

    # ডাটাবেজে চ্যাট সেভ
    if mobile:
        db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'web', 'user', ?)", (mobile, user_msg))
        db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'web', 'bot', ?)", (mobile, bot_reply))

    return jsonify({"status": "success", "response": bot_reply, "map_verified_address": verified_address})


# --- ২. ইনবক্স ইমেজ প্রসেসিং (Gemini Vision API) ---
@app.route('/api/inbox/image-process', methods=['POST'])
def process_inbox_image():
    mobile = request.form.get("mobile", "").strip()
    image_file = request.files.get("image")

    if not image_file:
        return jsonify({"status": "error", "message": "ছবি প্রদান করুন।"}), 400

    image_bytes = image_file.read()
    detected_info = "ছবিটি স্ক্যান করা সম্ভব হয়নি।"

    if gemini_client:
        try:
            prompt = "ছবিটি বিশ্লেষণ করে এর বিষয়বস্তু সংক্ষেপে বাংলায় উপস্থাপন করো।"
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, image_bytes]
            )
            detected_info = response.text
        except Exception as e:
            detected_info = f"Gemini Vision এরর: {str(e)}"

    reply_msg = f"ধন্যবাদ! আপনার ছবি বিশ্লেষণ করে প্রাপ্ত তথ্য: {detected_info}"

    if mobile:
        db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'DM', 'user_image', 'Sent an Image')", (mobile,))
        db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'DM', 'bot', ?)", (mobile, reply_msg))

    return jsonify({"status": "success", "response": reply_msg, "detected_info": detected_info})


# --- ৩. ইউজার রিপোর্ট API ---
@app.route('/api/report', methods=['POST'])
def report():
    data = request.get_json() or {}
    mobile = data.get("mobile", "").strip()
    issue_type = data.get("issue_type", "General Issue").strip()
    message = data.get("message", "").strip()

    if not mobile or not message:
        return jsonify({"status": "error", "message": "মোবাইল নম্বর ও বিস্তারিত লিখুন।"}), 400

    db_execute(
        "INSERT INTO reports (mobile_number, issue_type, message_text, status) VALUES (?, ?, ?, 'unread')",
        (mobile, issue_type, message)
    )

    return jsonify({"status": "success", "message": "আপনার রিপোর্টটি সফলভাবে অ্যাডমিনের কাছে জমা হয়েছে!"})


# --- ৪. অ্যাডমিন ড্যাশবোর্ড ও নোটিফিকেশন API ---
@app.route('/admin')
def admin_dashboard():
    cust_res = db_execute("SELECT mobile_number, name, address, created_at FROM customers ORDER BY created_at DESC")
    customers = getattr(cust_res, 'rows', cust_res)

    rep_res = db_execute("SELECT id, mobile_number, issue_type, message_text, admin_reply, status, timestamp FROM reports ORDER BY timestamp DESC")
    reports = getattr(rep_res, 'rows', rep_res)

    return render_template('admin.html', customers=customers, reports=reports)

@app.route('/api/admin/notifications', methods=['GET'])
def get_admin_notifications():
    res = db_execute("SELECT id, mobile_number, issue_type, message_text, timestamp FROM reports WHERE status = 'unread' ORDER BY timestamp DESC")
    unread = getattr(res, 'rows', res)
    return jsonify({"status": "success", "notifications": unread})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
