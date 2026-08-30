import os
import libsql_client
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__, template_folder="templates")
CORS(app)

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

def get_db_client():
    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        url = TURSO_DATABASE_URL.replace("libsql://", "https://")
        return libsql_client.create_client_sync(url=url, auth_token=TURSO_AUTH_TOKEN)
    else:
        raise Exception("Turso Database Config missing")

# ডাটাবেজ টেবিল অটোমেটিক তৈরি করার ফাংশন
def init_db():
    try:
        client = get_db_client()
        client.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception as e:
        print("Database Init Error:", str(e))

init_db()

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/admin", methods=["GET"])
def admin_panel():
    return render_template("admin.html")

# কাস্টমার ও অ্যাডমিন থেকে মেসেজ পাঠানো
@app.route("/api/send-message", methods=["POST"])
def send_message():
    data = request.get_json() or {}
    sender = data.get("sender", "customer") # 'customer' অথবা 'admin'
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message body is empty"}), 400

    try:
        client = get_db_client()
        client.execute(
            "INSERT INTO messages (sender, message) VALUES (?, ?)",
            [sender, message]
        )
        return jsonify({"status": "success", "message": "Message sent successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# সব মেসেজ লিস্ট নিয়ে আসা (কাস্টমার ও অ্যাডমিনের চ্যাট হিস্ট্রি)
@app.route("/api/get-messages", methods=["GET"])
def get_messages():
    try:
        client = get_db_client()
        result = client.execute("SELECT id, sender, message, timestamp FROM messages ORDER BY id ASC")
        
        messages = []
        for row in result.rows:
            messages.append({
                "id": row[0],
                "sender": row[1],
                "message": row[2],
                "timestamp": row[3]
            })
        return jsonify({"status": "success", "messages": messages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
