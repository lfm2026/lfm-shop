import os
import secrets
import string
import bcrypt
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# -------------------------------------------------------------
# DATABASE & SYSTEM CONFIGURATION
# -------------------------------------------------------------
# Supabase Direct Connection URL with SSL Mode Required (Render Compatible)
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://postgres:%26N8*pme%26Z_%3F3gSs@db.vumzmmvufzbdabrysjdh.supabase.co:5432/postgres?sslmode=require'
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

db = SQLAlchemy(app)


# -------------------------------------------------------------
# HELPER FUNCTIONS (Dynamic Unique IDs & Security)
# -------------------------------------------------------------
def generate_secure_id(prefix="id_", length=16):
    """১৬ ডিজিটের আলফানিউমেরিক ইউনিক আইডি জেনারেটর"""
    chars = string.ascii_letters + string.digits
    random_str = ''.join(secrets.choice(chars) for _ in range(length))
    return f"{prefix}{random_str}"

def hash_pw(password):
    """Bcrypt + Dynamic Salt password hashing"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

def check_pw(password, hashed):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# -------------------------------------------------------------
# DATABASE MODELS
# -------------------------------------------------------------

# ১. User Model (User, Admin, Controller)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("usr_"))
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Address Details
    house_or_road = db.Column(db.String(200), nullable=True)
    village = db.Column(db.String(100), nullable=True)
    thana = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    
    # Account Status
    role = db.Column(db.String(20), default='user') # 'user', 'admin', 'controller'
    is_active = db.Column(db.Boolean, default=True) # Controller can block/unblock
    is_approved = db.Column(db.Boolean, default=True) # Admin requires Controller approval

# ২. Base Product Model
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("pro_"))
    name = db.Column(db.String(200), nullable=False)
    category_type = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ৩. Product Variant Model (Every Color & Size combo gets unique ID)
class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("var_"))
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    pic_urls = db.Column(db.Text, nullable=False)
    video_urls = db.Column(db.Text, nullable=True)
    
    product = db.relationship('Product', backref=db.backref('variants', lazy=True))

# ৪. Order Model
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("ord_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.String(32), db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    status = db.Column(db.String(30), default='pending') # 'pending', 'approved', 'on_way', 'received', 'rejected'
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    variant = db.relationship('ProductVariant', backref=db.backref('orders', lazy=True))

# ৫. Review & Comment Model
class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'), nullable=False)
    is_purchased = db.Column(db.Boolean, default=False)
    order_count_for_item = db.Column(db.Integer, default=0)
    rating = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ৬. System Settings Model
class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)


# -------------------------------------------------------------
# INITIALIZE DATABASE & DEFAULT CONTROLLER ACCOUNT
# -------------------------------------------------------------
with app.app_context():
    db.create_all()
    
    # System Controller Account Auto Creation
    if not User.query.filter_by(role='controller').first():
        master_controller = User(
            full_name="System Controller",
            username="controller_master",
            email="admin@lfmshop.com",
            mobile="01829627718",
            password_hash=hash_pw("controller1234"),
            role="controller"
        )
        db.session.add(master_controller)
        
        default_settings = [
            SiteSettings(key="whatsapp_number", value="01829627718"),
            SiteSettings(key="facebook_page", value="https://www.facebook.com/profile.php?id=61577340780308"),
            SiteSettings(key="youtube_channel", value=""),
            SiteSettings(key="tiktok_acc", value=""),
            SiteSettings(key="instagram_acc", value=""),
            SiteSettings(key="support_email", value="support@lfmshop.com")
        ]
        db.session.add_all(default_settings)
        db.session.commit()


# -------------------------------------------------------------
# MIDDLEWARE: DEVICE DETECTION (Button Phone vs Android/PC)
# -------------------------------------------------------------
@app.before_request
def detect_device():
    user_agent = request.headers.get('User-Agent', '').lower()
    button_phone_keywords = ['opera mini', 'ucbrowser', 'symbian', 'nokia', 'mobi', 'feature', 'maemo']
    request.is_button_phone = any(keyword in user_agent for keyword in button_phone_keywords)


# -------------------------------------------------------------
# PUBLIC ROUTES
# -------------------------------------------------------------
@app.route('/')
def home():
    variants = ProductVariant.query.filter(ProductVariant.stock > 0).all()
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    
    template = 'mobile_index.html' if request.is_button_phone else 'modern_index.html'
    return render_template(template, products=variants, settings=settings)

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    
    if query.startswith('var_'):
        variants = ProductVariant.query.filter_by(id=query).all()
    else:
        variants = ProductVariant.query.join(Product).filter(Product.name.ilike(f'%{query}%')).all()
        
    template = 'mobile_index.html' if request.is_button_phone else 'modern_index.html'
    return render_template(template, products=variants, search_query=query)

@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    if User.query.filter((User.username == data['username']) | (User.mobile == data['mobile'])).first():
        return jsonify({"error": "Username or Mobile Number already registered!"}), 400

    new_user = User(
        full_name=data['full_name'],
        username=data['username'],
        email=data['email'],
        mobile=data['mobile'],
        password_hash=hash_pw(data['password']),
        house_or_road=data.get('house_or_road'),
        village=data.get('village'),
        thana=data.get('thana'),
        district=data.get('district')
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Registration Successful! Please login."}), 201

@app.route('/login', methods=['POST'])
def login():
    login_id = request.form.get('login_id')
    password = request.form.get('password')
    
    user = User.query.filter((User.username == login_id) | (User.mobile == login_id)).first()
    
    if user and check_pw(password, user.password_hash):
        if not user.is_active:
            return jsonify({"error": "Account has been blocked by Controller!"}), 403
        if user.role == 'admin' and not user.is_approved:
            return jsonify({"error": "Admin account pending approval!"}), 403
            
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify({"message": "Login successful!", "role": user.role}), 200
        
    return jsonify({"error": "Invalid credentials!"}), 401


# -------------------------------------------------------------
# ADMIN PANEL ROUTES
# -------------------------------------------------------------
@app.route('/admin/upload_product', methods=['POST'])
def upload_product():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized access!"}), 403
        
    name = request.form.get('name')
    category_type = request.form.get('category_type')
    colors = [c.strip() for c in request.form.get('colors').split(',')]
    sizes = [s.strip() for s in request.form.get('sizes').split(',')]
    price = float(request.form.get('price'))
    stock = int(request.form.get('stock'))
    pic_urls = request.form.get('pic_urls')
    video_urls = request.form.get('video_urls', '')

    base_product = Product(name=name, category_type=category_type)
    db.session.add(base_product)
    db.session.commit()

    for color in colors:
        for size in sizes:
            variant = ProductVariant(
                product_id=base_product.id,
                color=color,
                size=size,
                price=price,
                stock=stock,
                pic_urls=pic_urls,
                video_urls=video_urls
            )
            db.session.add(variant)
            
    db.session.commit()
    return jsonify({"message": "Product and Variants uploaded with Unique IDs successfully!"})

@app.route('/admin/orders')
def admin_orders():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_panel.html', orders=orders)


# -------------------------------------------------------------
# CONTROLLER PANEL ROUTES
# -------------------------------------------------------------
@app.route('/controller/dashboard')
def controller_dashboard():
    if session.get('role') != 'controller':
        return jsonify({"error": "Master Controller access required!"}), 403
        
    all_users = User.query.all()
    all_orders = Order.query.all()
    settings = SiteSettings.query.all()
    
    return render_template('controller_panel.html', users=all_users, orders=all_orders, settings=settings)

@app.route('/controller/toggle_user/<user_id>', methods=['POST'])
def toggle_user_status(user_id):
    if session.get('role') != 'controller':
        return jsonify({"error": "Unauthorized"}), 403
    
    user = User.query.get_or_404(user_id)
    if user.role == 'controller':
        return jsonify({"error": "Cannot block Controller!"}), 400
        
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({"message": f"User status updated. Active: {user.is_active}"})

@app.route('/controller/approve_admin/<admin_id>', methods=['POST'])
def approve_admin(admin_id):
    if session.get('role') != 'controller':
        return jsonify({"error": "Unauthorized"}), 403
        
    admin = User.query.get_or_404(admin_id)
    admin.is_approved = True
    db.session.commit()
    return jsonify({"message": "Admin account approved!"})

@app.route('/controller/update_links', methods=['POST'])
def update_contact_links():
    if session.get('role') != 'controller':
        return jsonify({"error": "Unauthorized"}), 403
        
    for key in request.form:
        setting = SiteSettings.query.get(key)
        if setting:
            setting.value = request.form[key]
        else:
            db.session.add(SiteSettings(key=key, value=request.form[key]))
            
    db.session.commit()
    return jsonify({"message": "System Contact Links updated successfully!"})


# -------------------------------------------------------------
# APP START
# -------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
