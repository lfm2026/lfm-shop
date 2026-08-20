import os
import json
import random
import string
import hashlib
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from user_agents import parse

app = Flask(__name__)

# ---------------------------------------------------------
# SECURITY & TOKEN GENERATOR UTILS
# ---------------------------------------------------------
def generate_18char_token(prefix="lfm"):
    """১৮-অক্ষরের র্যান্ডম সিকিউর টোকেন জেনারেট করে"""
    characters = string.ascii_letters + string.digits + "!@#$%"
    random_str = ''.join(random.choice(characters) for _ in range(18))
    return f"{prefix}_{random_str}"

def generate_unique_product_id(title, size, color):
    """প্রতিটি সাইজ ও কালার ভেরিয়েশনের জন্য ইউনিক LFM ID তৈরি করে"""
    raw_str = f"{title}-{size}-{color}-{generate_18char_token('id')}"
    short_hash = hashlib.md5(raw_str.encode()).hexdigest()[:6]
    return f"LFM-{short_hash.upper()}"

app.secret_key = generate_18char_token("secret")

# ---------------------------------------------------------
# FILE PATHS & DATA HELPERS
# ---------------------------------------------------------
DATA_DIR = "data"
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "system_config.json")
POLICIES_FILE = os.path.join(DATA_DIR, "policies.txt")

# ডাটা ডিরেক্টরি না থাকলে তৈরি করা
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_json(filepath, default_value=[]):
    if not os.path.exists(filepath):
        save_json(filepath, default_value)
        return default_value
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_policies():
    """data/policies.txt ফাইল থেকে মানসিকভাবে যুক্ত করা নিয়মাবলী পড়ে আনবে"""
    if os.path.exists(POLICIES_FILE):
        try:
            with open(POLICIES_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return "কোনো বিশেষ পলিসি পাওয়া যায়নি।"
    return "পলিসি ফাইল অনুপস্থিত।"

def is_button_phone(ua_string):
    """ইউজার কি বাটন/ফিচার ফোন নাকি স্মার্টফোন তা চিহ্নিত করে"""
    ua = parse(ua_string)
    lowered_ua = ua_string.lower()
    button_keywords = ["opera mini", "maui", "kaios", "symbian", "series40", "j2me", "dorado", "samsung-sgh"]
    
    if ua.is_bot:
        return False
    if any(keyword in lowered_ua for keyword in button_keywords):
        return True
    return False

# ---------------------------------------------------------
# WEBSITE ROUTES (DESKTOP & LITE VERSION ROUTING)
# ---------------------------------------------------------
@app.route("/")
def home():
    ua_string = request.headers.get('User-Agent', '')
    products = load_json(PRODUCTS_FILE)
    config = load_json(CONFIG_FILE, default_value={})
    
    # বাটন ফোন ডিটেকশন
    if is_button_phone(ua_string):
        return render_template("lite/index_lite.html", products=products, config=config)
    
    # এন্ড্রয়েড/পিসি (Toffee UI Theme)
    return render_template("desktop/index.html", products=products, config=config)

@app.route("/product/<product_id>")
def product_detail(product_id):
    ua_string = request.headers.get('User-Agent', '')
    products = load_json(PRODUCTS_FILE)
    product = next((p for p in products if p.get("product_id") == product_id), None)
    
    if not product:
        return "পণ্যটি পাওয়া যায়নি!", 404

    if is_button_phone(ua_string):
        return render_template("lite/product_lite.html", product=product)
    return render_template("desktop/product_detail.html", product=product)

@app.route("/get-policies", methods=["GET"])
def get_policies_api():
    """AI এজেন্ট বা ফ্রন্টএন্ড থেকে পলিসি পাওয়ার এপিআই"""
    policies = load_policies()
    return jsonify({"status": "success", "policies": policies})

# ---------------------------------------------------------
# ORDER & CHECKOUT SYSTEM
# ---------------------------------------------------------
@app.route("/checkout", methods=["POST"])
def checkout():
    data = request.form if request.form else request.get_json()
    orders = load_json(ORDERS_FILE)
    
    new_order = {
        "order_id": generate_18char_token("ord"),
        "customer_name": data.get("name"),
        "phone": data.get("phone"),
        "address": data.get("address"),
        "product_id": data.get("product_id"),
        "color": data.get("color"),
        "size": data.get("size"),
        "quantity": int(data.get("quantity", 1)),
        "delivery_type": data.get("delivery_type", "Standard"),
        "status": "Pending",  # Pending -> Approved -> On Road -> Delivered -> Cancelled
        "user_token": session.get("user_token", generate_18char_token("usr"))
    }
    
    orders.append(new_order)
    save_json(ORDERS_FILE, orders)
    
    if request.is_json:
        return jsonify({"status": "success", "message": "অর্ডার সফলভাবে সম্পন্ন হয়েছে!", "order_id": new_order["order_id"]})
    return redirect(url_for("user_inbox"))

@app.route("/user/inbox")
def user_inbox():
    orders = load_json(ORDERS_FILE)
    user_token = session.get("user_token")
    my_orders = [o for o in orders if o.get("user_token") == user_token] if user_token else []
    
    ua_string = request.headers.get('User-Agent', '')
    if is_button_phone(ua_string):
        return render_template("lite/chat_lite.html", orders=my_orders)
    return render_template("desktop/user_inbox.html", orders=my_orders)

# ---------------------------------------------------------
# LFM NEO AI CHAT SYSTEM (MULTI-AGENT ASSISTANT)
# ---------------------------------------------------------
@app.route("/api/ai-chat", methods=["POST"])
def ai_chat():
    req_data = request.get_json() or {}
    user_message = req_data.get("message", "")
    
    # পলিসি লোড করে AI এর কাছে প্রম্পট পাঠানো হবে
    policies = load_policies()
    
    # এখানে Groq ও Gemini ইন্টিগ্রেশনের লজিক কাজ করবে
    reply = f"LFM Neo [AI Support]: ধন্যবাদ আপনার মেসেজের জন্য। নীতিসমূহ অনুযায়ী: {policies[:100]}... শীঘ্রই সাহায্য করা হচ্ছে।"
    
    return jsonify({"status": "success", "reply": reply})

# ---------------------------------------------------------
# ADMIN PANEL (PRODUCT UPLOAD & ORDER MANAGEMENT)
# ---------------------------------------------------------
@app.route("/admin")
def admin_panel():
    products = load_json(PRODUCTS_FILE)
    orders = load_json(ORDERS_FILE)
    return render_template("desktop/admin.html", products=products, orders=orders)

@app.route("/admin/upload-product", methods=["POST"])
def upload_product():
    title = request.form.get("title")
    category = request.form.get("category")
    colors = [c.strip() for c in request.form.get("colors", "").split(",") if c.strip()]
    sizes = [s.strip() for s in request.form.get("sizes", "").split(",") if s.strip()]
    stock = int(request.form.get("stock", 0))
    price = float(request.form.get("price", 0))
    weight_kg = float(request.form.get("weight_kg", 0.25))
    pic_urls = [p.strip() for p in request.form.get("pic_urls", "").split(",") if p.strip()]
    video_urls = [v.strip() for v in request.form.get("video_urls", "").split(",") if v.strip()]

    products = load_json(PRODUCTS_FILE)

    # কালার ও সাইজের প্রতিটি কম্বিনেশনের জন্য অটো স্পেশাল ইউনিক ID
    for size in sizes:
        for color in colors:
            unique_id = generate_unique_product_id(title, size, color)
            new_product = {
                "product_id": unique_id,
                "title": title,
                "category": category,
                "color": color,
                "size": size,
                "stock": stock,
                "price": price,
                "weight_kg": weight_kg,
                "pic_urls": pic_urls,
                "video_urls": video_urls
            }
            products.append(new_product)

    save_json(PRODUCTS_FILE, products)
    return redirect(url_for("admin_panel"))

@app.route("/admin/update-order-status", methods=["POST"])
def update_order_status():
    order_id = request.form.get("order_id")
    new_status = request.form.get("status") # Pending, Approved, On Road, Delivered, Cancelled
    
    orders = load_json(ORDERS_FILE)
    for order in orders:
        if order.get("order_id") == order_id:
            order["status"] = new_status
            break
            
    save_json(ORDERS_FILE, orders)
    return redirect(url_for("admin_panel"))

# ---------------------------------------------------------
# CONTROLLER PANEL (SYSTEM LINKS & USER BLOCK/UNBLOCK)
# ---------------------------------------------------------
@app.route("/controller")
def controller_panel():
    config = load_json(CONFIG_FILE, default_value={})
    users = load_json(USERS_FILE)
    return render_template("desktop/controller.html", config=config, users=users)

@app.route("/controller/update-config", methods=["POST"])
def update_config():
    new_config = {
        "whatsapp_number": request.form.get("whatsapp_number"),
        "messenger_link": request.form.get("messenger_link"),
        "facebook_page": request.form.get("facebook_page"),
        "youtube_link": request.form.get("youtube_link"),
        "tiktok_link": request.form.get("tiktok_link"),
        "instagram_link": request.form.get("instagram_link"),
        "gmail_contact": request.form.get("gmail_contact")
    }
    save_json(CONFIG_FILE, new_config)
    return redirect(url_for("controller_panel"))

@app.route("/controller/toggle-user-block", methods=["POST"])
def toggle_user_block():
    user_token = request.form.get("user_token")
    users = load_json(USERS_FILE)
    
    for u in users:
        if u.get("token") == user_token:
            u["is_blocked"] = not u.get("is_blocked", False)
            break
            
    save_json(USERS_FILE, users)
    return redirect(url_for("controller_panel"))

# ---------------------------------------------------------
# RUN APPLICATION
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
