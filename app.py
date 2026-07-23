import os
import secrets
import string
import bcrypt
from flask import Flask, request, jsonify, render_template, redirect, url_session, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Supabase Connection URI
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgres:%26N8*pme%26Z_%3F3gSs@db.vumzmmvufzbdabrysjdh.supabase.co:5432/postgres'
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

db = SQLAlchemy(app)

# --- HELPER FUNCTIONS ---
def generate_secure_id(prefix="id_", length=16):
    chars = string.ascii_letters + string.digits
    return f"{prefix}{''.join(secrets.choice(chars) for _ in range(length))}"

def hash_pw(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

def check_pw(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ==========================================
# DATABASE MODELS (All Panels)
# ==========================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("usr_"))
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Address details (Optional initially)
    village_or_house = db.Column(db.String(200), nullable=True)
    thana = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    
    # Roles: 'user', 'admin', 'controller'
    role = db.Column(db.String(20), default='user')
    is_active = db.Column(db.Boolean, default=True) # Controller can block
    is_approved = db.Column(db.Boolean, default=True) # Admin needs approval from controller

class Product(db.Model):
    __tablename__ = 'products'
    # Base product (e.g., T-Shirt)
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("pro_"))
    name = db.Column(db.String(200), nullable=False)
    category_type = db.Column(db.String(100), nullable=False) # Auto-saves new types
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    # Unique ID for every combination (e.g., Red + Size M)
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("var_"))
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    pic_urls = db.Column(db.Text, nullable=False) # Comma separated URLs
    video_urls = db.Column(db.Text, nullable=True) # Optional

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("ord_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.String(32), db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    # Status: pending, approved, on_way, received, rejected
    status = db.Column(db.String(50), default='pending') 
    shipping_address = db.Column(db.Text, nullable=False)

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'))
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'))
    is_purchased = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Integer, nullable=True) # Only if purchased
    comment = db.Column(db.Text, nullable=True)

class SiteSettings(db.Model):
    __tablename__ = 'site_settings' # Controller manages this
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

with app.app_context():
    db.create_all()
    # Add default controller if not exists
    if not User.query.filter_by(role='controller').first():
        controller = User(
            full_name="System Controller", username="controller_admin", 
            email="controller@lfm.com", mobile="01829627718", 
            password_hash=hash_pw("controller123"), role="controller"
        )
        db.session.add(controller)
        db.session.commit()

# ==========================================
# ROUTES & LOGIC
# ==========================================

# Device Detection Middleware
@app.before_request
def check_device():
    user_agent = request.headers.get('User-Agent', '').lower()
    button_phones = ['opera mini', 'ucbrowser', 'symbian', 'nokia', 'mobi', 'feature']
    request.is_mobile = any(phone in user_agent for phone in button_phones)

@app.route('/')
def home():
    # Fetch all variants for display
    products = ProductVariant.query.filter(ProductVariant.stock > 0).all()
    template = 'mobile_index.html' if request.is_mobile else 'desktop_index.html'
    return render_template(template, products=products)

@app.route('/signup', methods=['POST'])
def signup():
    # Registration logic...
    pass

@app.route('/login', methods=['POST'])
def login():
    # Login logic (Mobile or Username)...
    pass

@app.route('/product/<variant_id>')
def view_product(variant_id):
    # Fetch exact unique product ID
    product = ProductVariant.query.get_or_404(variant_id)
    return render_template('product_detail.html', product=product)

# --- Admin Routes ---
@app.route('/admin/upload_product', methods=['POST'])
def upload_product():
    # Check if admin and is_approved
    # Upload product and variations, pending state logic to avoid duplicates
    pass

@app.route('/admin/update_order/<order_id>', methods=['POST'])
def update_order(order_id):
    # Change status to approved, on_way, etc.
    # Send email automatically
    pass

# --- Controller Routes ---
@app.route('/controller/dashboard')
def controller_dashboard():
    # Check if role == 'controller'
    # Show everything, allow block/unblock, edit settings
    pass

if __name__ == '__main__':
    app.run(debug=True)
