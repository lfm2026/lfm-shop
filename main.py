import os
import json
import random
import string
import smtplib
from email.mime.text import MIMEText
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from groq import Groq
import google.generativeai as genai
from database import get_db_client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Secrets Config
SECRET_KEY = "lfm_super_secret_session_encryption_key_2026"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ALERT_EMAILS = ["fourbd10@gmail.com", "bdsrs2007@gmail.com", "loopformoney2026@gmail.com"]
SMTP_SERVER = "://gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.environ.get("ALERT_EMAIL_SENDER") 
EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")

# AI Client Init
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    gemini_model = None

# --- হেল্পার ফাংশন ---
def get_admin_password():
    if os.path.exists("password.txt"):
        with open("password.txt", "r") as f:
            return f.read().strip()
    return "lfmadmin2026"

def verify_admin_tok(request: Request):
    token = request.cookies.get("admin_session")
    if token != get_admin_password():
        raise HTTPException(status_code=401, detail="Unauthorized Admin")
    return True

def get_webhooks_from_db():
    db = get_db_client()
    res = db.execute("SELECT * FROM webhook_settings LIMIT 1").rows[0]
    db.close()
    return {
        "meta_verify_token": res[1],
        "meta_page_access_token": res[2],
        "tiktok_client_key": res[3],
        "tiktok_client_secret": res[4]
    }

def send_alert_email(session_id, user_info="Guest User"):
    if not EMAIL_SENDER or not EMAIL_PASSWORD: return
    try:
        msg_text = f"🚨 Alert! A customer has opened the Chatroom.\nSession ID: {session_id}\nUser Info: {user_info}"
        msg = MIMEText(msg_text)
        msg['Subject'] = '🔴 New Customer Chatroom Opened'
        msg['From'] = EMAIL_SENDER
        msg['To'] = ", ".join(ALERT_EMAILS)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, ALERT_EMAILS, msg.as_string())
    except Exception as e: print(f"Email Failed: {e}")

def ask_groq(prompt, system_instruction):
    if not groq_client: return "Groq API Offline."
    comp = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
        temperature=0.3
    )
    return comp.choices.message.content

def ask_gemini(prompt):
    if not gemini_model: return prompt
    return gemini_model.generate_content(prompt).text

# --- ⚙️ ৫. অ্যাডমিন কন্ট্রোলার ও সেটিংস রাউটস ---
@app.get("/", response_class=HTMLResponse)
async def admin_login_ui(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(password: str = Form(...)):
    if password == get_admin_password():
        res = RedirectResponse(url="/admin/update", status_code=303)
        res.set_cookie(key="admin_session", value=password)
        return res
    return RedirectResponse(url="/?error=1", status_code=303)

@app.get("/admin/update", response_class=HTMLResponse)
async def update_page(request: Request, auth=Depends(verify_admin_tok)):
    return templates.TemplateResponse("update.html", {"request": request})

@app.post("/admin/update")
async def process_stock_update(text_input: str = Form(...), auth=Depends(verify_admin_tok)):
    # এআই ব্যাকএন্ড স্টক প্রসেসিং লজিক...
    return RedirectResponse(url="/admin/data", status_code=303)

@app.get("/admin/data", response_class=HTMLResponse)
async def data_page(request: Request, auth=Depends(verify_admin_tok)):
    db = get_db_client()
    prods = db.execute("SELECT * FROM products").rows
    db.close()
    return templates.TemplateResponse("data.html", {"request": request, "products": prods})

@app.get("/admin/policy", response_class=HTMLResponse)
async def policy_page(request: Request, auth=Depends(verify_admin_tok)):
    db = get_db_client()
    pols = db.execute("SELECT * FROM policies").rows
    db.close()
    return templates.TemplateResponse("policy.html", {"request": request, "policies": pols})

@app.post("/admin/policy")
async def add_policy(rule_text: str = Form(...), auth=Depends(verify_admin_tok)):
    db = get_db_client()
    db.execute("INSERT INTO policies (rule_text) VALUES (?)", [rule_text])
    db.close()
    return RedirectResponse(url="/admin/policy", status_code=303)

@app.get("/admin/order", response_class=HTMLResponse)
async def order_page(request: Request, auth=Depends(verify_admin_tok)):
    db = get_db_client()
    ords = db.execute("SELECT * FROM orders").rows
    db.close()
    return templates.TemplateResponse("order.html", {"request": request, "orders": ords})

@app.post("/admin/order/status")
async def change_order_status(order_code: str = Form(...), action: str = Form(...), auth=Depends(verify_admin_tok)):
    db = get_db_client()
    status_map = {"approve": "Approved", "onroad": "On Road", "delivered": "Delivered", "reject": "Rejected"}
    if action in status_map:
        db.execute("UPDATE orders SET status = ? WHERE order_code = ?", [status_map[action], order_code])
    db.close()
    return RedirectResponse(url="/admin/order", status_code=303)

@app.get("/admin/chats", response_class=HTMLResponse)
async def admin_chats_dashboard(request: Request, auth=Depends(verify_admin_tok)):
    db = get_db_client()
    sessions = db.execute("SELECT * FROM chat_sessions WHERE is_deleted = 0").rows
    history = db.execute("SELECT * FROM chat_history ORDER BY timestamp ASC").rows
    db.close()
    return templates.TemplateResponse("admin_chats.html", {"request": request, "sessions": sessions, "history": history})

# 🛠️ নতুন ডাইনামিক ওয়েবহুক সেটিংস ড্যাশবোর্ড রাউট
@app.get("/admin/webhooks", response_class=HTMLResponse)
async def webhook_settings_ui(request: Request, auth=Depends(verify_admin_tok)):
    keys = get_webhooks_from_db()
    return templates.TemplateResponse("webhook_settings.html", {"request": request, "keys": keys})

@app.post("/admin/webhooks/save")
async def save_webhooks_to_db(meta_token: str = Form(...), meta_secret: str = Form(...), tt_key: str = Form(...), tt_secret: str = Form(...), auth=Depends(verify_admin_tok)):
    db = get_db_client()
    db.execute("""
        UPDATE webhook_settings 
        SET meta_verify_token = ?, meta_page_access_token = ?, tiktok_client_key = ?, tiktok_client_secret = ?
        WHERE id = 1
    """, [meta_token, meta_secret, tt_key, tt_secret])
    db.close()
    return RedirectResponse(url="/admin/webhooks?success=1", status_code=303)

# --- 👤 কাস্টমার লাইভ এপিআই রাউটস ---
@app.get("/chatroom", response_class=HTMLResponse)
async def user_chatroom_ui(request: Request):
    return templates.TemplateResponse("chatroom.html", {"request": request})

@app.post("/api/chat/session/init")
async def init_chat_session(phone: str = None, name: str = "Guest User"):
    session_id = "SESS" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    session_title = ask_gemini(f"Generate short 3 words sweet title for conversation by {name}.").replace('"', '')
    db = get_db_client()
    db.execute("INSERT INTO chat_sessions (session_id, phone_number, title) VALUES (?, ?, ?)", [session_id, phone, session_title])
    db.close()
    send_alert_email(session_id, f"Name: {name}")
    return {"session_id": session_id, "title": session_title}

@app.post("/api/chat/message")
async def handle_web_chat_message(session_id: str = Form(...), message: str = Form(...), phone: str = None):
    db = get_db_client()
    db.execute("INSERT INTO chat_history (session_id, platform, sender_type, sender_id, message_text) VALUES (?, 'web', 'user', ?, ?)", [session_id, phone if phone else "guest", message])
    pols = [r for r in db.execute("SELECT * FROM policies").rows]
    prods = db.execute("SELECT * FROM products").rows
    ai_reply = ask_groq(message, f"Policies: {pols}. Products: {prods}")
    if "address" in message or "ঠিকানা" in message:
        ai_reply = ask_gemini(f"Verify location format. Fix errors like 'sonaour' to 'Sonapur'. Text: {message}")
    db.execute("INSERT INTO chat_history (session_id, platform, sender_type, sender_id, message_text) VALUES (?, 'web', 'ai', 'ai', ?)", [session_id, ai_reply])
    db.close()
    return {"reply": ai_reply}

# --- 🔗 ডাইনামিক মেটা এবং সোশ্যাল মিডিয়া ওয়েবহুক অ্যান্ডপয়েন্ট ---
@app.get("/webhook")
async def verify_fb_webhook(request: Request):
    params = request.query_params
    db_keys = get_webhooks_from_db()
    # ডাটাবেস থেকে ডাইনামিকালি ভেরিফাই টোকেন ম্যাচিং করানো
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == db_keys["meta_verify_token"]:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(content="Forbidden Verification Failed", status_code=403)
