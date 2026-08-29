import os
import json
import sqlite3
import libsql_client
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from google import genai  # Google Gemini SDK
from groq import Groq

app = Flask(__name__)
app.secret_key = "lfm_gonio_super_secret_key_2026"

# Environment Variables Setup
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "https://lfm-shop-db-lfm2026.aws-ap-northeast-1.turso.io")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Fix LibSQL Protocol
if TURSO_URL and (TURSO_URL.startswith("libsql://") or TURSO_URL.startswith("wss://")):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://").replace("wss://", "https://")

def get_turso_client():
    if TURSO_URL and TURSO_TOKEN:
        return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    return None

# AI Clients Initialization
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# DB Execution Handler (Groq/Backend-এর ডাটাবেজ সামলানোর প্রধান ফাংশন)
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

@app.route('/')
def home():
    user_info = session.get('user', None)
    return render_template('index.html', user=user_info)

# --- Continue with Google Auth API ---
@app.route('/api/google-login', methods=['POST'])
def google_login():
    data = request.json or {}
    google_id = data.get("google_id")
    name = data.get("name")
    mobile = data.get("mobile", "")

    if not google_id:
        return jsonify({"status": "error", "message": "Invalid Google Auth"})

    session['user'] = {"google_id": google_id, "name": name, "mobile": mobile}

    if mobile:
        db_execute(
            "INSERT INTO customers (mobile_number, name, google_id) VALUES (?, ?, ?) ON CONFLICT(mobile_number) DO UPDATE SET name=excluded.name, google_id=excluded.google_id",
            (mobile, name, google_id)
        )

    return jsonify({"status": "success", "user": session['user']})


# --- ১. চ্যাট ও অ্যাড্রেস প্রসেসিং (Groq চ্যাট সামলাবে এবং Gemini Maps ব্যবহার করবে) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    user_msg = data.get("message", "").strip()
    mobile = data.get("mobile", "").strip()
    address_input = data.get("address", "").strip()

    if not user_msg or not mobile:
        return jsonify({"response": "অনুগ্রহ করে মোবাইল নম্বর এবং বার্তা প্রদান করুন।"})

    # কাস্টমার নতুন ঠিকানা দিলে Gemini লাইভ Google Maps টুল দিয়ে তা ভেরিফাই করবে
    verified_address = ""
    if address_input and gemini_client:
        try:
            map_prompt = f"কাস্টমারের প্রদানকৃত ঠিকানাটি বিশ্লেষণ করে গুগল ম্যাপস অনুযায়ী সঠিক পূর্ণাঙ্গ ঠিকানা বের করো: '{address_input}'"
            map_res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=map_prompt,
                config={'tools': [{'google_search': {}}]}  # Live Search / Maps Integration
            )
            verified_address = map_res.text
            # Groq-এর বদলে ডাটাবেজে ঠিকানা সেভ প্রসেস
            db_execute("UPDATE customers SET address = ? WHERE mobile_number = ?", (verified_address, mobile))
        except Exception as e:
            verified_address = address_input

    # ভুল শনাক্তকরণের ক্ষেত্রে Groq ক্ষমা চাইবে এবং সাপোর্ট নোটিফিকেশন পাঠাবে
    negative_keywords = ["ভুল", "ভুল হইছে", "ভুল শনাক্ত", "এডা না", "এটা না", "wrong"]
    if any(k in user_msg.lower() for k in negative_keywords):
        db_execute(
            "INSERT INTO reports (mobile_number, issue_type, message_text, status) VALUES (?, ?, ?, ?)",
            (mobile, "Live Admin Support", f"প্রোডাক্ট ভুল শনাক্ত হয়েছে বলে ইউজার অভিযোগ করেছে: {user_msg}", "unread")
        )
        apology_reply = "আন্তরিকভাবে দুঃখিত! প্রোডাক্টটি ভুল সনাক্ত করার জন্য আমরা অনুতপ্ত। অনুগ্রহ করে আমাদের অ্যাডমিন লাইনে আসা পর্যন্ত অপেক্ষা করুন, একজন প্রতিনিধি খুব দ্রুত আপনার চ্যাটে যোগ দিচ্ছেন।"
        
        # ডাটা সেভ সামলাবে Groq Logic/Engine
        db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'web', 'bot', ?)", (mobile, apology_reply))
        return jsonify({"response": apology_reply, "admin_alert": True})

    # সাধারণ চ্যাট প্রসেসিং (Groq সামলাবে, কারণ Groq এর স্পিড ও লিমিট বেশি)
    bot_reply = "সিস্টেমে সাময়িক সমস্যা হচ্ছে।"
    if groq_client:
        try:
            sys_prompt = """তুমি Loop For Money (LFM) ই-কমার্স শপের এআই কাস্টমার অ্যাসিস্ট্যান্ট। 
            কাস্টমার প্রোডাক্ট কোড বলতে না পারলে তাকে ইনবক্স/DM-এ প্রোডাক্টের ফটো পাঠাতে বলো। 
            বাংলায় সংক্ষেপে সুন্দর উত্তর দাও।"""
            
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7,
                max_tokens=300
            )
            bot_reply = completion.choices[0].message.content
        except Exception as e:
            bot_reply = "বর্তমানে সার্ভিস অনুপলব্ধ।"

    # Groq-এর মাধ্যমে চ্যাট ডাটাবেজে সেভ
    db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'web', 'user', ?)", (mobile, user_msg))
    db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'web', 'bot', ?)", (mobile, bot_reply))

    return jsonify({"response": bot_reply, "map_verified_address": verified_address})


# --- ২. ইনবক্স/DM ইমেজ প্রসেসিং (শুধুমাত্র Gemini Vision ব্যবহার হবে) ---
@app.route('/api/inbox/image-process', methods=['POST'])
def process_inbox_image():
    mobile = request.form.get("mobile", "").strip()
    image_file = request.files.get("image")

    if not mobile or not image_file:
        return jsonify({"error": "মোবাইল নম্বর ও ছবি প্রয়োজন।"}), 400

    image_bytes = image_file.read()
    detected_info = "ছবি শনাক্ত করা সম্ভব হয়নি।"

    # Groq যা পারে না (ছবি দেখা), তা Gemini Vision সম্পন্ন করবে
    if gemini_client:
        try:
            prompt = "ছবিতে থাকা পোশাকটি (টি-শার্ট/প্যান্ট) দেখে এর কালার, টাইপ ও কাপড়ের বিবরণ সংক্ষেপে বাংলায় বলো।"
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, image_bytes]
            )
            detected_info = response.text
        except Exception as e:
            detected_info = "Gemini ছবিটি স্ক্যান করতে পারেনি।"

    reply_msg = f"ধন্যবাদ! পাঠানো ছবি বিশ্লেষণ করে মনে হচ্ছে এটি: {detected_info}। এটি কি সঠিক?"

    # Groq-এর ডাটাবেজ সিস্টেমে ডাটা রাইট করা
    db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'DM', 'user_image', 'Sent an Image')", (mobile,))
    db_execute("INSERT INTO chat_logs (mobile_number, platform, sender, message_text) VALUES (?, 'DM', 'bot', ?)", (mobile, reply_msg))

    return jsonify({"response": reply_msg, "detected_info": detected_info})


# --- ৩. অ্যাডমিন প্যানেল ও লাইভ নোটিফিকেশন API ---
@app.route('/admin')
def admin_dashboard():
    cust_res = db_execute("SELECT mobile_number, name, address, created_at FROM customers ORDER BY created_at DESC")
    customers = getattr(cust_res, 'rows', cust_res)

    rep_res = db_execute("SELECT id, mobile_number, issue_type, message_text, admin_reply, status, timestamp FROM reports ORDER BY timestamp DESC")
    reports = getattr(rep_res, 'rows', rep_res)

    return render_template('admin.html', customers=customers, reports=reports)

@app.route('/api/admin/notifications', methods=['GET'])
def get_admin_notifications():
    res = db_execute("SELECT id, mobile_number, message_text, timestamp FROM reports WHERE status = 'unread' ORDER BY timestamp DESC")
    unread = getattr(res, 'rows', res)
    return jsonify({"notifications": unread})

if __name__ == '__main__':
    app.run(debug=True)
