from flask import Flask, render_template, request, jsonify
from user_agents import parse
import json
import os
from utils_security import generate_18char_token

app = Flask(__name__)
app.secret_key = generate_18char_token("secret")

DATA_DIR = "data"
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
POLICIES_FILE = os.path.join(DATA_DIR, "policies.txt")

def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def load_policies():
    if os.path.exists(POLICIES_FILE):
        with open(POLICIES_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def is_button_phone(ua_string):
    ua = parse(ua_string)
    if ua.is_bot or "Opera Mini" in ua_string or "MAUI" in ua_string or "KaiOS" in ua_string:
        return True
    return False

@app.route("/")
def home():
    ua_string = request.headers.get('User-Agent', '')
    products = load_json(PRODUCTS_FILE)
    
    # বাটন ফোন ডিটেকশন
    if is_button_phone(ua_string):
        return render_template("lite/index_lite.html", products=products)
    
    # এন্ড্রয়েড/পিসি (Toffee UI)
    return render_template("desktop/index.html", products=products)

@app.route("/get-policies")
def get_policies():
    return jsonify({"policies": load_policies()})

if __name__ == "__main__":
    app.run(debug=True)
