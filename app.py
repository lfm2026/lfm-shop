import os
import secrets
import string
import bcrypt
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# -------------------------------------------------------------
# DATABASE & SYSTEM CONFIGURATION (Neon.tech PostgreSQL)
# -------------------------------------------------------------
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://neondb_owner:npg_kw3iXOsVvyd7@ep-gentle-field-azrvkgpz-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

db = SQLAlchemy(app)

# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------
def generate_secure_id(prefix="id_", length=12):
    chars = string.ascii_letters + string.digits
    return f"{prefix}{''.join(secrets.choice(chars) for _ in range(length))}"

def hash_pw(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

def check_pw(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# -------------------------------------------------------------
# DATABASE MODELS
# -------------------------------------------------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("usr_"))
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    house_or_road = db.Column(db.String(200), nullable=True)
    village = db.Column(db.String(100), nullable=True)
    thana = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    
    role = db.Column(db.String(20), default='user') # 'user', 'admin', 'controller'
    is_active = db.Column(db.Boolean, default=True) 
    is_approved = db.Column(db.Boolean, default=False) # Admin requires Controller approval

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("pro_"))
    name = db.Column(db.String(200), nullable=False)
    category_type = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("ord_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.String(32), db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='pending') # pending, approved, on_way, received, rejected
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    variant = db.relationship('ProductVariant', backref=db.backref('orders', lazy=True))

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

# -------------------------------------------------------------
# INIT DB & CONTROLLER
# -------------------------------------------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='controller').first():
        master_controller = User(
            full_name="System Controller",
            username="controller_master",
            email="admin@lfmshop.com",
            mobile="01829627718",
            password_hash=hash_pw("controller1234"),
            role="controller",
            is_approved=True
        )
        db.session.add(master_controller)
        
        defaults = [
            SiteSettings(key="whatsapp_number", value="01829627718"),
            SiteSettings(key="facebook_page", value="https://www.facebook.com/profile.php?id=61577340780308"),
            SiteSettings(key="messenger_link", value="https://m.me/61577340780308"),
            SiteSettings(key="support_email", value="support@lfmshop.com")
        ]
        db.session.add_all(defaults)
        db.session.commit()

# -------------------------------------------------------------
# DEVICE DETECTION MIDDLEWARE
# -------------------------------------------------------------
@app.before_request
def detect_device():
    ua = request.headers.get('User-Agent', '').lower()
    button_keywords = ['opera mini', 'ucbrowser', 'symbian', 'nokia', 'mobi', 'feature', 'maemo']
    request.is_button_phone = any(k in ua for k in button_keywords)

# -------------------------------------------------------------
# PUBLIC & USER ROUTES
# -------------------------------------------------------------
@app.route('/')
def home():
    variants = ProductVariant.query.filter(ProductVariant.stock > 0).all()
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    template = 'mobile_index.html' if request.is_button_phone else 'modern_index.html'
    return render_template(template, products=variants, settings=settings)

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if q.startswith('var_'):
        variants = ProductVariant.query.filter_by(id=q).all()
    else:
        variants = ProductVariant.query.join(Product).filter(Product.name.ilike(f'%{q}%')).all()
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    template = 'mobile_index.html' if request.is_button_phone else 'modern_index.html'
    return render_template(template, products=variants, settings=settings, search_query=q)

@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    if User.query.filter((User.username == data['username']) | (User.mobile == data['mobile'])).first():
        return jsonify({"error": "Username or Mobile already registered!"}), 400

    role = data.get('role', 'user')
    is_approved = True if role == 'user' else False # Admin needs controller approval

    new_user = User(
        full_name=data['full_name'],
        username=data['username'],
        email=data['email'],
        mobile=data['mobile'],
        password_hash=hash_pw(data['password']),
        house_or_road=data.get('house_or_road'),
        village=data.get('village'),
        thana=data.get('thana'),
        district=data.get('district'),
        role=role,
        is_approved=is_approved
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Registration successful! Please login."}), 201

@app.route('/login', methods=['POST'])
def login():
    login_id = request.form.get('login_id')
    password = request.form.get('password')
    user = User.query.filter((User.username == login_id) | (User.mobile == login_id)).first()
    
    if user and check_pw(password, user.password_hash):
        if not user.is_active:
            return jsonify({"error": "Your account has been blocked!"}), 403
        if user.role == 'admin' and not user.is_approved:
            return jsonify({"error": "Admin account is pending Controller approval!"}), 403
            
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify({"message": "Login successful!", "role": user.role}), 200
    return jsonify({"error": "Invalid credentials!"}), 401

@app.route('/order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return jsonify({"error": "Please login to place an order!"}), 401
    
    data = request.json
    variant_id = data.get('variant_id')
    quantity = int(data.get('quantity', 1))
    address = data.get('address')
    
    variant = ProductVariant.query.get_or_404(variant_id)
    if variant.stock < quantity:
        return jsonify({"error": "Insufficient stock!"}), 400
        
    total_price = variant.price * quantity
    order = Order(
        user_id=session['user_id'],
        variant_id=variant_id,
        quantity=quantity,
        total_price=total_price,
        shipping_address=address,
        status='pending'
    )
    db.session.add(order)
    db.session.commit()
    
    whatsapp_number = SiteSettings.query.get('whatsapp_number')
    wa_num = whatsapp_number.value if whatsapp_number else "01829627718"
    wa_msg = f"Hello Admin, I want to order. Product ID: {variant.id}, Quantity: {quantity}, Total Price: {total_price} TK."
    
    return jsonify({
        "message": "Order placed successfully!", 
        "order_id": order.id,
        "whatsapp_url": f"https://wa.me/{wa_num}?text={wa_msg}"
    }), 201

# -------------------------------------------------------------
# ADMIN ROUTES
# -------------------------------------------------------------
@app.route('/admin/upload_product', methods=['POST'])
def upload_product():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.form
    name = data.get('name')
    category_type = data.get('category_type')
    colors = [c.strip() for c in data.get('colors').split(',')]
    sizes = [s.strip() for s in data.get('sizes').split(',')]
    price = float(data.get('price'))
    stock = int(data.get('stock'))
    pic_urls = data.get('pic_urls')
    video_urls = data.get('video_urls', '')

    prod = Product(name=name, category_type=category_type)
    db.session.add(prod)
    db.session.commit()

    for col in colors:
        for sz in sizes:
            variant = ProductVariant(
                product_id=prod.id,
                color=col,
                size=sz,
                price=price,
                stock=stock,
                pic_urls=pic_urls,
                video_urls=video_urls
            )
            db.session.add(variant)
    db.session.commit()
    return jsonify({"message": "Product variants uploaded successfully with unique IDs!"})

@app.route('/admin/order_action/<string:order_id>', methods=['POST'])
def order_action(order_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    action = request.form.get('action') # approve, on_way, reject
    order = Order.query.get_or_404(order_id)
    
    if action == 'approve':
        order.status = 'approved'
    elif action == 'on_way':
        order.status = 'on_way'
    elif action == 'reject':
        order.status = 'rejected'
        
    db.session.commit()
    return jsonify({"message": f"Order status updated to {order.status}"})

# -------------------------------------------------------------
# CONTROLLER ROUTES
# -------------------------------------------------------------
@app.route('/controller/toggle_user/<string:user_id>', methods=['POST'])
def toggle_user(user_id):
    if session.get('role') != 'controller':
        return jsonify({"error": "Unauthorized"}), 403
    user = User.query.get_or_404(user_id)
    if user.role == 'controller':
        return jsonify({"error": "Cannot modify Controller!"}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({"message": f"User status changed. Active: {user.is_active}"})

@app.route('/controller/approve_admin/<string:admin_id>', methods=['POST'])
def approve_admin_account(admin_id):
    if session.get('role') != 'controller':
        return jsonify({"error": "Unauthorized"}), 403
    adm = User.query.get_or_404(admin_id)
    adm.is_approved = True
    db.session.commit()
    return jsonify({"message": "Admin account approved!"})

@app.route('/controller/update_links', methods=['POST'])
def update_links():
    if session.get('role') != 'controller':
        return jsonify({"error": "Unauthorized"}), 403
    for key, val in request.form.items():
        st = SiteSettings.query.get(key)
        if st:
            st.value = val
        else:
            db.session.add(SiteSettings(key=key, value=val))
    db.session.commit()
    return jsonify({"message": "Site links updated successfully!"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
