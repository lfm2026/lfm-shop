import os
import json
import random
import string
import smtplib
import time
from email.mime.text import MIMEText
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
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

SECRET_KEY = "lfm_super_secret_session_encryption_key_2026"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

ALERT_EMAILS = ["fourbd10@gmail.com", "bdsrs2007@gmail.com", "loopformoney2026@gmail.com"]
SMTP_SERVER = "://gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.environ.get("ALERT_EMAIL_SENDER") 
EMAIL_PASSWORD = os.environ.get("ALERT_EMAIL_PASSWORD")

# গ্লোবাল ট্র্যাকিং ভেরিয়েবল (প্রতি মিনিটে ফেইলওভার ইমেইল কন্ট্রোল করার জন্য)
LAST_CRITICAL_EMAIL_TIME = 0

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    gemini_model = None

def get_admin_password():
    if os.path.exists("password.txt"):
        with open("password.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    return "@#$"

def is_authenticated(request: Request):
    return request.cookies.get("admin_session") == get_admin_password()

def get_webhooks_from_db():
    db = get_db_client()
    res = db.execute("SELECT * FROM webhook_settings LIMIT 1").rows
    db.close()
    if res:
        return {"meta_verify_token": res[0][1], "meta_page_access_token": res[0][2], "tiktok_client_key": res[0][3], "tiktok_client_secret": res[0][4]}
    return {"meta_verify_token": "lfm_verify_token_2026", "meta_page_access_token": "", "tiktok_client_key": "", "tiktok_client_secret": ""}

def send_alert_email(subject, text_content):
    if not EMAIL_SENDER or not EMAIL_PASSWORD: return
    try:
        msg = MIMEText(text_content)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = ", ".join(ALERT_EMAILS)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, ALERT_EMAILS, msg.as_string())
    except Exception as e:
        print(f"SMTP Error: {e}")

# --- 🧠 GoNeo এআই কোর রেসিলিয়েন্স ইঞ্জিন (লজিক ৩ - ব্যাকআপ ও ফেইলওভার) ---
def generate_ai_response(user_message, system_instruction, image_data=None):
    global LAST_CRITICAL_EMAIL_TIME
    
    # ইমেজ ভিশন ও ডাবল ভেরিফিকেশন প্রসেসিং (লজিক ২)
    if image_data:
        if gemini_model:
            try:
                vision_prompt = f"ইউজার শপ 'PotBest'-এ এই ছবিটি পাঠিয়েছে। ছবি দেখে ধারণা করো এটি কী প্রোডাক্ট। ইন্টারনেট ও ইন্টারনাল নলেজ ব্যবহার করে এর নিখুঁত বিবরণ বের করো এবং ডেটাবেসের প্রোডাক্ট লিস্টের সাথে মেলাও। ছবি থেকে কোনো প্রোডাক্ট কোড বা বিবরণ পাও কি না খুঁজে বের করো। প্রোডাক্ট লিস্ট: {system_instruction}"
                vision_res = gemini_model.generate_content([vision_prompt, image_data]).text
                return f"apnar deowa chobita dekhe mone hoy ata... (GoNeo AI Response): {vision_res}\n\njodi amar deowa information sothik na hoy tobe apni wait korte paren...amader akjon protinidhi ase apnar messege er sothik reply dibe..."
            except Exception as e:
                pass

    # সাধারণ চ্যাট ফেইলওভার চেইন
    try:
        # ১ম অগ্রাধিকার: Groq (Llama)
        if not groq_client: raise Exception("Groq Offline")
        comp = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": user_message}],
            temperature=0.3
        )
        return comp.choices.message.content
    except Exception as groq_err:
        print(f"Groq Down, switching to Gemini backup... Error: {groq_err}")
        try:
            # ২য় অগ্রাধিকার (ব্যাকআপ): Gemini 
            if not gemini_model: raise Exception("Gemini Offline")
            full_prompt = f"{system_instruction}\n\nCustomer: {user_message}"
            return gemini_model.generate_content(full_prompt).text
        except Exception as gemini_err:
            # ৩য় স্তর: দুটি এআই-ই ডাউন হলে ক্রিপ্টিক ফেইলওভার ও ইমেইল অ্যালার্ট
            print(f"Both AI Engines are offline! Triggering crisis protocols.")
            current_time = time.time()
            if current_time - LAST_CRITICAL_EMAIL_TIME > 60:
                send_alert_email(
                    "🚨 CRITICAL SYSTEM FAILURE - BOTH AI ENGINES OFFLINE",
                    f"Alert! GoNeo Bot is failing to respond because both Groq and Gemini APIs are down simultaneously.\nTimestamp: 2026\nMessage: {user_message}"
                )
                LAST_CRITICAL_EMAIL_TIME = current_time
            return "please wait for few sec... (Generating answer...)"

# --- ⚙️ অ্যাডমিন রাউটস (`/ad`) ---
@app.get("/ad", response_class=HTMLResponse)
async def admin_panel(request: Request):
    if not is_authenticated(request):
        return templates.TemplateResponse("index.html", {"request": request, "authenticated": False, "error": request.query_params.get("error")})
    
    db = get_db_client()
    products = db.execute("SELECT * FROM products").rows
    policies = db.execute("SELECT * FROM policies").rows
    orders = db.execute("SELECT * FROM orders").rows
    sessions = db.execute("SELECT * FROM chat_sessions WHERE is_deleted = 0").rows
    history = db.execute("SELECT * FROM chat_history ORDER BY timestamp ASC").rows
    db.close()
    
    webhooks = get_webhooks_from_db()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "authenticated": True,
        "products": products,
        "policies": policies,
        "orders": orders,
        "sessions": sessions,
        "history": history,
        "keys": webhooks
    })

@app.post("/ad/login")
async def admin_login(password: str = Form(...)):
    if password == get_admin_password():
        res = RedirectResponse(url="/ad", status_code=303)
        res.set_cookie(key="admin_session", value=password, httponly=True)
        return res
    return RedirectResponse(url="/ad?error=1", status_code=303)

@app.get("/ad/logout")
async def admin_logout():
    res = RedirectResponse(url="/ad", status_code=303)
    res.delete_cookie("admin_session")
    return res

@app.post("/ad/update")
async def process_stock_update(text_input: str = Form(...), request: Request = None):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    db = get_db_client()
    curr_stock = db.execute("SELECT * FROM products").rows
    prompt = f"ইউজার টেক্সট: '{text_input}'. বর্তমান ইনভেন্টরি ডাটা: {curr_stock}. এই নির্দেশনা অনুযায়ী স্টক হ্রাস বা বৃদ্ধি ঘটিয়ে আপডেটেড SQL ইনসার্ট/আপডেট লজিক তৈরি করো।"
    # ডাইনামিক আপডেট প্রোসেস...
    db.close()
    return RedirectResponse(url="/ad", status_code=303)

@app.post("/ad/policy")
async def add_policy(rule_text: str = Form(...), request: Request = None):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    db = get_db_client()
    db.execute("INSERT INTO policies (rule_text) VALUES (?)", [rule_text])
    db.close()
    return RedirectResponse(url="/ad", status_code=303)

@app.get("/ad/policy/delete/{pid}")
async def delete_policy(pid: int, request: Request = None):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    db = get_db_client()
    db.execute("DELETE FROM policies WHERE id = ?", [pid])
    db.close()
    return RedirectResponse(url="/ad", status_code=303)

@app.post("/ad/order/status")
async def change_order_status(order_code: str = Form(...), action: str = Form(...), request: Request = None):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    db = get_db_client()
    status_map = {"approve": "Approved", "onroad": "On Road", "delivered": "Delivered", "reject": "Rejected"}
    if action in status_map:
        db.execute("UPDATE orders SET status = ? WHERE order_code = ?", [status_map[action], order_code])
    db.close()
    return RedirectResponse(url="/ad", status_code=303)

@app.post("/ad/webhooks/save")
async def save_webhooks(meta_token: str = Form(...), meta_secret: str = Form(...), tt_key: str = Form(...), tt_secret: str = Form(...), request: Request = None):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    db = get_db_client()
    db.execute("""
        UPDATE webhook_settings 
        SET meta_verify_token = ?, meta_page_access_token = ?, tiktok_client_key = ?, tiktok_client_secret = ?
        WHERE id = 1
    """, [meta_token, meta_secret, tt_key, tt_secret])
    db.close()
    return RedirectResponse(url="/ad", status_code=303)

@app.post("/ad/chats/reply")
async def admin_manual_reply(session_id: str = Form(...), reply_text: str = Form(...), request: Request = None):
    if not is_authenticated(request): raise HTTPException(status_code=401)
    db = get_db_client()
    db.execute("INSERT INTO chat_history (session_id, platform, sender_type, sender_id, message_text) VALUES (?, 'web', 'admin', 'admin', ?)", [session_id, reply_text])
    db.close()
    return RedirectResponse(url="/ad", status_code=303)

# --- 👤 কাস্টমার চ্যাটরুম কোর অ্যান্ডপয়েন্টস ---
@app.get("/chatroom", response_class=HTMLResponse)
async def user_chatroom_ui(request: Request):
    return templates.TemplateResponse("chatroom.html", {"request": request})

@app.post("/api/chat/session/init")
async def init_chat_session(phone: str = None, name: str = "Guest User"):
