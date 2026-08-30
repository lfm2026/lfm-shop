import os
import libsql_client
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from groq import Groq

app = Flask(__name__)
CORS(app)  # Cross-Origin Resource Sharing অন করার জন্য

# Environment Variables থেকে API Keys এবং DB Config সংগ্রহ
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# Client Initializations
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# Turso Database Client Function
def get_db_client():
    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        # libsql-client-এর জন্য URL স্কিম https:// তে রূপান্তর করা
        url = TURSO_DATABASE_URL.replace("libsql://", "https://")
        return libsql_client.create_client_sync(url=url, auth_token=TURSO_AUTH_TOKEN)
    else:
        raise Exception("Turso Database URL or Auth Token is missing in Environment")


# Home Route (Health Check)
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "success",
        "message": "GoNeo AI Backend with Gemini, Groq & Turso DB is Running!"
    })


# Gemini API Route
@app.route("/chat/gemini", methods=["POST"])
def chat_gemini():
    if not gemini_client:
        return jsonify({"error": "Gemini API Key missing in Environment"}), 500

    data = request.get_json() or {}
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
        )
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Groq API Route (Llama 3.3)
@app.route("/chat/groq", methods=["POST"])
def chat_groq():
    if not groq_client:
        return jsonify({"error": "Groq API Key missing in Environment"}), 500

    data = request.get_json() or {}
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": user_message}],
            model="llama-3.3-70b-versatile",
        )
        return jsonify({"reply": chat_completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Turso DB Test Route (ডাটাবেজ কানেকশন টেস্ট করার জন্য)
@app.route("/db-test", methods=["GET"])
def db_test():
    try:
        client = get_db_client()
        result = client.execute("SELECT 1 + 1 AS result")
        return jsonify({"status": "Database Connected Successfully!", "data": result.rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
