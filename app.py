import os
import secrets
import string
import bcrypt
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message

app = Flask(__name__)

# -------------------------------------------------------------
# CONFIGURATION & DB SETUP
# -------------------------------------------------------------
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    'postgresql://neondb_owner:npg_kw3iXOsVvyd7@ep-gentle-field-azrvkgpz-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lfm_super_secret_key_2026')

# Flask Mail Configurations
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')

db = SQLAlchemy(app)
mail = Mail(app)

# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------
def generate_secure_id(prefix="id_", length=8):
    chars = string.ascii_uppercase + string.digits
    return f"{prefix}{''.join(secrets.choice(chars) for _ in range(length))}"

def generate_variant_id(color, size):
    # কালার এবং সাইজ এর সাথে ৪ সংখ্যার ইউনিক র্যান্ডম কোড দিয়ে অটোমেটিক ID তৈরি
    clean_color = "".join(e for e in color if e.isalnum()).upper()[:3]
    clean_size = "".join(e for e in size if e.isalnum()).upper()[:3]
    rand_code = ''.join(secrets.choice(string.digits) for _ in range(4))
    return f"VAR-{clean_color}-{clean_size}-{rand_code}"

def hash_pw(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

def check_pw(password, stored_hash):
    if not stored_hash:
        return False
    if password == stored_hash: # Fallback plain-text check
        return True
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        return False

def send_async_email(subject, recipient, body):
    try:
        msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[recipient])
        msg.body = body
        mail.send(msg)
    except Exception as e:
        print(f"Email Error: {e}")

# -------------------------------------------------------------
# MODELS
# -------------------------------------------------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("usr_"))
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    village = db.Column(db.String(100), nullable=True)
    thana = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(100), nullable=True)
    house_or_road = db.Column(db.String(200), nullable=True)
    
    role = db.Column(db.String(20), default='user')
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("pro_"))
    name = db.Column(db.String(200), nullable=False)
    category_type = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProductVariant(db.Model):
    __tablename__ = 'product_variants'
    id = db.Column(db.String(50), primary_key=True) # E.g., VAR-RED-S-1029
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    pic_urls = db.Column(db.Text, nullable=False) # Comma separated URLs
    video_urls = db.Column(db.Text, nullable=True)
    
    product = db.relationship('Product', backref=db.backref('variants', lazy=True, cascade="all, delete-orphan"))

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("crt_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.String(50), db.ForeignKey('product_variants.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    variant = db.relationship('ProductVariant')

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("ord_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.String(50), db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='pending') # pending, on_road, delivered, rejected
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    variant = db.relationship('ProductVariant')

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("rev_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.String(32), db.ForeignKey('products.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=True) # Null for plain comment
    comment = db.Column(db.Text, nullable=False)
    is_verified_buyer = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

# -------------------------------------------------------------
# SYSTEM INITIALIZATION & DEVICE ROUTING
# -------------------------------------------------------------
with app.app_context():
    try:
        db.create_all()
        controller = User.query.filter_by(username="srs10.").first()
        if not controller:
            controller = User(
                full_name="System Controller", username="srs10.",
                email="admin@lfmshop.com", mobile="01829627718",
                password_hash=hash_pw("12qw3e"), role="controller", is_approved=True
            )
            db.session.add(controller)
            db.session.commit()
            
        defaults = [
            ("facebook_page", "https://www.facebook.com/profile.php?id=61577340780308"),
            ("messenger_link", "https://m.me/61577340780308"),
            ("whatsapp_number", "01829627718"),
            ("youtube_channel", "https://youtube.com/@weber-ST"),
            ("tiktok_link", "https://tiktok.com"),
            ("instagram_link", "https://instagram.com"),
            ("gmail_address", "support@lfmshop.com")
        ]
        for key, val in defaults:
            if not SiteSettings.query.get(key):
                db.session.add(SiteSettings(key=key, value=val))
        db.session.commit()
    except Exception as e:
        print(f"Init Error: {e}")

@app.before_request
def detect_device():
    ua = request.headers.get('User-Agent', '').lower()
    btn_keywords = ['opera mini/att', 'ucweb/2.0', 'nokia', 'symbian', 'series40', 'maemo']
    request.is_button_phone = any(k in ua for k in btn_keywords) and not ('android' in ua or 'iphone' in ua)

# -------------------------------------------------------------
# PUBLIC / HOMEPAGE / SEARCH
# -------------------------------------------------------------
@app.route('/')
def home():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    
    # ID দিয়ে নিখুঁত প্রোডাক্ট সার্চ
    if query:
        variant = ProductVariant.query.filter_by(id=query).first()
        if variant:
            products = [variant]
        else:
            products = ProductVariant.query.join(Product).filter(Product.name.ilike(f"%{query}%")).all()
    else:
        products = ProductVariant.query.all()
        
    categories = [c[0] for c in db.session.query(Product.category_type).distinct().all()]
    template = 'button_phone_index.html' if request.is_button_phone else 'modern_index.html'
    
    return render_template(template, products=products, settings=settings, categories=categories)

# -------------------------------------------------------------
# AUTHENTICATION
# -------------------------------------------------------------
@app.route('/signup', methods=['POST'])
def user_signup():
    data = request.form
    if User.query.filter((User.username == data['username']) | (User.mobile == data['mobile'])).first():
        flash("ইউজারনাম বা মোবাইল নম্বর ব্যবহার করা হয়েছে!", "danger")
        return redirect(url_for('home'))
        
    user = User(
        full_name=data['full_name'], username=data['username'],
        email=data['email'], mobile=data['mobile'],
        village=data.get('village'), thana=data.get('thana'),
        district=data.get('district'), house_or_road=data.get('house_or_road'),
        password_hash=hash_pw(data['password']), role='user', is_approved=True
    )
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    session['role'] = 'user'
    flash("সাইনআপ সফল হয়েছে!", "success")
    return redirect(url_for('home'))

@app.route('/login', methods=['POST'])
def login():
    login_id = request.form.get('login_id')
    password = request.form.get('password')
    
    user = User.query.filter((User.username == login_id) | (User.mobile == login_id)).first()
    if user and check_pw(password, user.password_hash):
        if not user.is_active:
            flash("আপনার অ্যাকাউন্ট ব্লক করা হয়েছে!", "danger")
            return redirect(url_for('home'))
            
        if user.role == 'admin' and not user.is_approved:
            flash("অ্যাডমিন অ্যাকাউন্ট অনুমোদনের অপেক্ষায় আছে!", "warning")
            return redirect(url_for('home'))
            
        session['user_id'] = user.id
        session['role'] = user.role
        flash("লগইন সফল!", "success")
        
        if user.role == 'controller':
            return redirect(url_for('controller_dashboard', username=user.username))
        elif user.role == 'admin':
            return redirect(url_for('admin_dashboard', username=user.username))
        return redirect(url_for('user_profile', username=user.username))
        
    flash("ভুল ইউজারনাম বা পাসওয়ার্ড!", "danger")
    return redirect(url_for('home'))

# -------------------------------------------------------------
# CART & ORDER SYSTEM WITH AUTOMATED EMAILS
# -------------------------------------------------------------
@app.route('/cart/add/<variant_id>', methods=['POST'])
def add_to_cart(variant_id):
    if 'user_id' not in session:
        flash("কার্টে যোগ করতে প্রথমে লগইন করুন!", "warning")
        return redirect(url_for('home'))
        
    cart_item = Cart(user_id=session['user_id'], variant_id=variant_id)
    db.session.add(cart_item)
    db.session.commit()
    flash("প্রোডাক্ট কার্টে যুক্ত হয়েছে! স্টক বা দাম আপডেট হলে মেইল পাবেন।", "info")
    return redirect(url_for('home'))

@app.route('/order/place', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        flash("অর্ডার করতে লগইন করুন!", "warning")
        return redirect(url_for('home'))
        
    user = User.query.get(session['user_id'])
    data = request.form
    variant = ProductVariant.query.get_or_404(data['variant_id'])
    
    qty = int(data.get('quantity', 1))
    total = variant.price * qty
    
    # এড্রেস সেভ রাখা
    if not user.village:
        user.village = data.get('village')
        user.thana = data.get('thana')
        user.district = data.get('district')
        user.house_or_road = data.get('house_or_road')
        db.session.commit()
        
    address = f"{user.house_or_road or ''}, {user.village}, {user.thana}, {user.district}"
    order = Order(user_id=user.id, variant_id=variant.id, quantity=qty, total_price=total, shipping_address=address)
    db.session.add(order)
    db.session.commit()
    
    # ইমেইল নোটিফিকেশন
    send_async_email("Order Received - LFM Shop", user.email, f"আপনার অর্ডার সফল হয়েছে! প্রোডাক্ট ID: {variant.id}, মোট দাম: {total} টাকা।")
    
    # অপশনাল হোয়াটসঅ্যাপ বাটনের তথ্য
    wa_num = SiteSettings.query.get("whatsapp_number").value
    wa_text = f"Hello Admin, I placed an order. Order ID: {order.id}, Variant ID: {variant.id}, Qty: {qty}"
    wa_url = f"https://wa.me/{wa_num}?text={wa_text}"
    
    flash("অর্ডার সফলভাবে জমা হয়েছে!", "success")
    return render_template('order_success.html', order=order, wa_url=wa_url)

@app.route('/order/receive/<order_id>')
def receive_order(order_id):
    if 'user_id' not in session:
        flash("প্রথমে লগইন করুন!", "warning")
        return redirect(url_for('home'))
        
    order = Order.query.get_or_404(order_id)
    if order.user_id != session['user_id']:
        flash("অনুমতি নেই!", "danger")
        return redirect(url_for('home'))
        
    return render_template('confirm_receipt.html', order=order)

@app.route('/order/confirm_delivery/<order_id>', methods=['POST'])
def confirm_delivery(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'delivered'
    db.session.commit()
    flash("পণ্য গ্রহণের নিশ্চিতকরণ সম্পন্ন হয়েছে!", "success")
    return redirect(url_for('user_profile', username=order.user.username))

# -------------------------------------------------------------
# ADMIN ROUTES
# -------------------------------------------------------------
@app.route('/admin/dashboard/<username>')
def admin_dashboard(username):
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if user.username != username or not user.is_approved:
        return redirect(url_for('home'))
        
    products = Product.query.all()
    orders = Order.query.all()
    categories = [c[0] for c in db.session.query(Product.category_type).distinct().all()]
    return render_template('admin_dashboard.html', user=user, products=products, orders=orders, categories=categories)

@app.route('/admin/product/add', methods=['POST'])
def add_product():
    if session.get('role') != 'admin': return redirect(url_for('home'))
    data = request.form
    
    product = Product(name=data['name'], category_type=data['category_type'])
    db.session.add(product)
    db.session.flush()
    
    v_id = generate_variant_id(data['color'], data['size'])
    variant = ProductVariant(
        id=v_id, product_id=product.id, color=data['color'], size=data['size'],
        price=float(data['price']), stock=int(data['stock']),
        pic_urls=data['pic_urls'], video_urls=data.get('video_urls')
    )
    db.session.add(variant)
    db.session.commit()
    flash(f"প্রোডাক্ট আপলোড সফল! Variant ID: {v_id}", "success")
    
    curr_admin = User.query.get(session['user_id'])
    return redirect(url_for('admin_dashboard', username=curr_admin.username))

@app.route('/admin/order/update/<order_id>', methods=['POST'])
def update_order_status(order_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    status = request.form.get('status')
    order = Order.query.get_or_404(order_id)
    order.status = status
    db.session.commit()
    
    # অটো ইমেইল
    send_async_email(
        f"Order Status Updated: {status.upper()}", order.user.email,
        f"আপনার অর্ডারের বর্তমান স্ট্যাটাস: {status}\nযদি ডেলিভারি পেয়ে থাকেন তবে লিংকে ক্লিক করে কনফার্ম করুন:\n"
        f"{url_for('receive_order', order_id=order.id, _external=True)}"
    )
    flash("অর্ডার আপডেট পাঠানো হয়েছে!", "info")
    curr_admin = User.query.get(session['user_id'])
    return redirect(url_for('admin_dashboard', username=curr_admin.username))

# -------------------------------------------------------------
# CONTROLLER ROUTES
# -------------------------------------------------------------
@app.route('/controller/dashboard/<username>')
def controller_dashboard(username):
    if session.get('role') != 'controller': return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if user.username != username: return redirect(url_for('home'))
    
    pending_admins = User.query.filter_by(role='admin', is_approved=False).all()
    all_users = User.query.all()
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    
    return render_template('controller_dashboard.html', user=user, pending_admins=pending_admins, users=all_users, settings=settings)

@app.route('/controller/settings/update', methods=['POST'])
def update_site_settings():
    if session.get('role') != 'controller': return redirect(url_for('home'))
    for key, val in request.form.items():
        s = SiteSettings.query.get(key)
        if s: s.value = val
    db.session.commit()
    flash("সোশ্যাল মিডিয়া ও কন্টাক্ট লিংক আপডেট করা হয়েছে!", "success")
    curr_c = User.query.get(session['user_id'])
    return redirect(url_for('controller_dashboard', username=curr_c.username))

# -------------------------------------------------------------
# USER PROFILE & REVIEW SYSTEM
# -------------------------------------------------------------
@app.route('/profile/<username>')
def user_profile(username):
    if 'user_id' not in session: return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if user.username != username: return redirect(url_for('user_profile', username=user.username))
    return render_template('profile.html', user=user)

@app.route('/review/add/<product_id>', methods=['POST'])
def add_review(product_id):
    if 'user_id' not in session: return redirect(url_for('home'))
    user_id = session['user_id']
    comment = request.form.get('comment')
    rating = request.form.get('rating')
    
    # বায়িং ভেরিফিকেশন চেক
    has_bought = Order.query.join(ProductVariant).filter(
        Order.user_id == user_id, 
        ProductVariant.product_id == product_id, 
        Order.status == 'delivered'
    ).first() is not None
    
    rev = Review(user_id=user_id, product_id=product_id, rating=int(rating) if has_bought else None, comment=comment, is_verified_buyer=has_bought)
    db.session.add(rev)
    db.session.commit()
    flash("আপনার মতামত যোগ হয়েছে!", "success")
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
