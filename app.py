import os
from flask import Flask, render_template, request, jsonify
from groq import Groq
from google import genai

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_msg = data.get("message", "").strip()

    if not user_msg:
        return jsonify({"status": "error", "response": "অনুগ্রহ করে একটি বার্তা লিখুন।"})

    bot_reply = ""

    # ১. Groq AI দিয়েই প্রসেস করার চেষ্টা
    if groq_client:
        try:
            sys_prompt = "তুমি GoNeo AI, একটি বুদ্ধিমান কাস্টমার সাপোর্ট অ্যাসিস্ট্যান্ট। প্রাকৃতিকভাবে বাংলায় চ্যাট করো।"
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
        except Exception as e:
            print("Groq Error:", e)

    # ২. Groq কাজ না করলে Gemini API ব্যবহার
    if not bot_reply and gemini_client:
        try:
            res = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"তুমি GoNeo AI। উত্তর দাও: {user_msg}"
            )
            bot_reply = res.text
        except Exception as e:
            print("Gemini Error:", e)

    # ৩. যদি API Key না থাকে, তবে স্মার্ট ডায়নামিক লোকাল লজিক (যা মানুষ বা AI এর মতো উত্তর দেবে)
    if not bot_reply:
        msg_lower = user_msg.lower()
        if any(w in msg_lower for w in ["hi", "hello", "হাই", "হ্যালো", "হে"]):
            bot_reply = "হ্যালো! কীভাবে সাহায্য করতে পারি বলুন?"
        elif any(w in msg_lower for w in ["product", "প্রোডাক্ট", "পণ্য", "মাল", "lagbe", "লাগবে"]):
            bot_reply = "আমাদের কাছে বেশ কিছু কোয়ালিটি প্রোডাক্ট রয়েছে। আপনার ঠিক কী ধরনের প্রোডাক্ট পছন্দ?"
        elif any(w in msg_lower for w in ["ki", "কি", "কেমন", "kemon"]):
            bot_reply = "আমি ভালো আছি! আপনি কেমন আছেন? আপনাকে কীভাবে সহায়তা করতে পারি?"
        elif any(w in msg_lower for w in ["dam", "দাম", "price", "কত"]):
            bot_reply = "নির্দিষ্ট প্রোডাক্টের নাম বললে আমি আপনাকে সঠিক দামটি জানিয়ে দিতে পারবো।"
        elif any(w in msg_lower for w in ["moja", "মজা", "ai", "এআই"]):
            bot_reply = "না না, আমি মোটেও মজা করছি না! আমি আপনার কথা বুঝতে পারছি। বলুন কী সাহায্য লাগবে?"
        else:
            bot_reply = f"বুঝতে পেরেছি। আপনি '{user_msg}' নিয়ে জানতে চেয়েছেন। বিস্তারিত বললে সুবিধা হতো।"

    return jsonify({"status": "success", "response": bot_reply})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
