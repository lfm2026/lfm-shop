import os
import re
import uuid
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import libsql_client
import groq

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "gonio_secret_key_2026")

# Environment Variables
TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if TURSO_URL.startswith("libsql://") or TURSO_URL.startswith("wss://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://").replace("wss://", "https://")

def get_db():
    if not TURSO_URL or not TURSO_TOKEN:
        return None
    return libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)

groq_client = groq.Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# --- ১. ওয়েবসাইট ইউজার রুট ---
@app.route('/')
def home():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('index.html')

# চ্যাট রেসপন্স এবং অটো-ডাটা সেভ
@app.route('/get_response', methods=['POST'])
def get_response():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id', str(uuid.uuid4()))
    platform = data.get('platform', 'website')
    user_id = session.get('user_id')

    if not user_message:
        return jsonify({'response': 'কিছু লিখুন।'})

    db = get_db()

    # চ্যাট থেকে মোবাইল নম্বর ফিল্টার করা
    phone_match = re.search(r'(01[3-9]\d{8})', user_message)
    detected_mobile = phone_match.group(0) if phone_match else session.get('mobile_number', f"GUEST_{user_id[:6]}")

    if phone_match:
        session['mobile_number'] = detected_mobile
        if db:
            db.execute(
                "INSERT INTO customers (mobile_number) VALUES (?) ON CONFLICT(mobile_number) DO NOTHING",
                [detected_mobile]
            )

    # ইউজারের চ্যাট সেভ
    if db:
        db.execute(
            "INSERT INTO chat_logs (mobile_number, platform, session_id, sender, message_text) VALUES (?, ?, ?, ?, ?)",
            [detected_mobile, platform, session_id, 'user', user_message]
        )

    # AI উত্তর তৈরি
    if not groq_client:
        return jsonify({'response': 'AI সার্ভিস বর্তমানে বন্ধ রয়েছে।'})

    chat_completion = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": "আপনি GoNio AI Assistant। লুপ ফর মানি (LFM) শপের জন্য গ্রাহকদের সেবা দিন। গ্রাহক অর্ডার করতে চাইলে তার নাম, মোবাইল নম্বর ও ঠিকানা জানতে চান।"},
            {"role": "user", "content": user_message}
        ],
        model="llama-3.3-70b-versatile",
    )
    ai_response = chat_completion.choices[0].message.content

    # বটের উত্তর সেভ
    if db:
        db.execute(
            "INSERT INTO chat_logs (mobile_number, platform, session_id, sender, message_text) VALUES (?, ?, ?, ?, ?)",
            [detected_mobile, platform, session_id, 'gonio_bot', ai_response]
        )

    return jsonify({'response': ai_response, 'session_id': session_id})

# --- ২. রিপোর্ট সাবমিট ও স্ট্যাটাস চেক ---
@app.route('/api/report', methods=['POST'])
def submit_report():
    data = request.get_json()
    issue = data.get('issue')
    user_id = session.get('user_id')
    mobile = session.get('mobile_number', 'N/A')

    db = get_db()
    if db:
        db.execute(
            "INSERT INTO reports (user_id, mobile_number, issue_type, message_text) VALUES (?, ?, ?, ?)",
            [user_id, mobile, issue, issue]
        )
        return jsonify({'status': 'success', 'message': 'আপনার রিপোর্ট জমা হয়েছে। অ্যাডমিন পর্যালোচনা করছেন।'})
    return jsonify({'status': 'error'})

@app.route('/api/user/reports', methods=['GET'])
def get_user_reports():
    user_id = session.get('user_id')
    db = get_db()
    if not db:
        return jsonify([])
    res = db.execute("SELECT id, issue_type, admin_reply, status, timestamp FROM reports WHERE user_id = ? ORDER BY id DESC", [user_id])
    reports = [{'id': r[0], 'issue': r[1], 'reply': r[2], 'status': r[3], 'time': r[4]} for r in res.rows]
    return jsonify(reports)

# --- ৩. অ্যাডমিন প্যানেল রুটস ---
@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

# কাস্টমার ফোল্ডার লিস্ট
@app.route('/admin/api/folders', methods=['GET'])
def get_admin_folders():
    db = get_db()
    if not db:
        return jsonify([])
    res = db.execute("""
        SELECT mobile_number, COUNT(id) as total_msg 
        FROM chat_logs 
        GROUP BY mobile_number 
        ORDER BY id DESC
    """)
    folders = [{'mobile': r[0], 'messages': r[1]} for r in res.rows]
    return jsonify(folders)

# নির্দিষ্ট ফোল্ডারের চ্যাট দেখা
@app.route('/admin/api/folder/<mobile>', methods=['GET'])
def get_folder_chats(mobile):
    db = get_db()
    if not db:
        return jsonify([])
    res = db.execute("SELECT platform, sender, message_text, timestamp FROM chat_logs WHERE mobile_number = ? ORDER BY id ASC", [mobile])
    chats = [{'platform': r[0], 'sender': r[1], 'message': r[2], 'time': r[3]} for r in res.rows]
    return jsonify(chats)

# পেন্ডিং রিপোর্ট ট্র্যাকিং (লাল ব্যাজ এর জন্য)
@app.route('/admin/api/reports', methods=['GET'])
def get_admin_reports():
    db = get_db()
    if not db:
        return jsonify({'reports': [], 'pending_count': 0})
    res = db.execute("SELECT id, user_id, mobile_number, issue_type, admin_reply, status, timestamp FROM reports ORDER BY id DESC")
    reports = [{'id': r[0], 'user_id': r[1], 'mobile': r[2], 'issue': r[3], 'reply': r[4], 'status': r[5], 'time': r[6]} for r in res.rows]
    
    # পেন্ডিং কাউন্ট
    pending_res = db.execute("SELECT COUNT(id) FROM reports WHERE status = 'pending'")
    pending_count = pending_res.rows[0][0] if pending_res.rows else 0

    return jsonify({'reports': reports, 'pending_count': pending_count})

# রিপোর্টে অ্যাডমিনের রিপ্লাই পাঠানোর রুট
@app.route('/admin/api/report/reply', methods=['POST'])
def reply_report():
    data = request.get_json()
    report_id = data.get('report_id')
    reply_text = data.get('reply')

    db = get_db()
    if db:
        db.execute(
            "UPDATE reports SET admin_reply = ?, status = 'resolved' WHERE id = ?",
            [reply_text, report_id]
        )
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
