import os
import secrets
import string
import bcrypt
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# -------------------------------------------------------------
# DATABASE CONFIGURATION
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

db = SQLAlchemy(app)

# -------------------------------------------------------------
# FIXED 16-DIGIT SECRET KEYS
# -------------------------------------------------------------
ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', 'a8f9c2d1b4e3f5a7') 
CONTROLLER_SECRET_KEY = os.environ.get('CONTROLLER_SECRET_KEY', 'c7d2e4f6a8b1c3d5')

# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------
def generate_secure_id(prefix="id_", length=12):
    chars = string.ascii_uppercase + string.digits
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
    is_approved = db.Column(db.Boolean, default=False) 

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
    
    product = db.relationship('Product', backref=db.backref('variants', lazy=True, cascade="all, delete-orphan"))

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(32), primary_key=True, default=lambda: generate_secure_id("ord_"))
    user_id = db.Column(db.String(32), db.ForeignKey('users.id'), nullable=False)
    variant_id = db.Column(db.String(32), db.ForeignKey('product_variants.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='pending')
    shipping_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    variant = db.relationship('ProductVariant', backref=db.backref('orders', lazy=True))

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

# -------------------------------------------------------------
# INIT DATABASE & DEFAULT DATA
# -------------------------------------------------------------
with app.app_context():
    db.create_all()
    
    # ক্রিয়েট মাস্টার কন্ট্রোলার একাউন্ট (যদি ডাটাবেসে না থাকে)
    controller_exist = User.query.filter_by(role='controller').first()
    if not controller_exist:
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
        db.session.commit()
        
    # ডিফল্ট সাইট সেটিংস
    if not SiteSettings.query.first():
        default_settings = [
            SiteSettings(key="facebook_page", value="https://www.facebook.com/profile.php?id=61577340780308"),
            SiteSettings(key="messenger_link", value="https://m.me/61577340780308"),
            SiteSettings(key="whatsapp_number", value="01829627718"),
            SiteSettings(key="tiktok_link", value="https://www.tiktok.com"),
            SiteSettings(key="instagram_link", value="https://www.instagram.com"),
            SiteSettings(key="support_email", value="support@lfmshop.com")
        ]
        db.session.add_all(default_settings)
        db.session.commit()

# -------------------------------------------------------------
# DEVICE DETECTION
# -------------------------------------------------------------
@app.before_request
def detect_device():
    ua = request.headers.get('User-Agent', '').lower()
    button_keywords = ['opera mini/att', 'ucweb/2.0', 'nokia', 'symbian', 'series40', 'maemo']
    request.is_button_phone = any(k in ua for k in button_keywords) and not ('android' in ua or 'iphone' in ua)

# -------------------------------------------------------------
# SECRET ROUTES (ADMIN & CONTROLLER)
# -------------------------------------------------------------
@app.route('/admin/signup/<secret_token>', methods=['GET', 'POST'])
def admin_signup(secret_token):
    # টোকেন চেক
    if str(secret_token).strip() != ADMIN_SECRET_KEY:
        flash("অবৈধ এক্সেস লিংক!", "danger")
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        data = request.form
        if User.query.filter((User.username == data['username']) | (User.mobile == data['mobile'])).first():
            flash("ইউজারনাম বা নম্বর আগের থেকেই বিদ্যমান!", "danger")
            return redirect(request.url)

        new_admin = User(
            full_name=data['full_name'],
            username=data['username'],
            email=data['email'],
            mobile=data['mobile'],
            password_hash=hash_pw(data['password']),
            role='admin',
            is_approved=False
        )
        db.session.add(new_admin)
        db.session.commit()
        flash("অ্যাডমিন রেজিস্ট্রেশন সফল! কন্ট্রোলারের অনুমোদনের অপেক্ষা করুন।", "success")
        return redirect(url_for('home'))

    return render_template('admin_signup.html', token=secret_token)

@app.route('/controller/login/<secret_token>', methods=['GET', 'POST'])
def controller_login(secret_token):
    # টোকেন চেক
    if str(secret_token).strip() != CONTROLLER_SECRET_KEY:
        flash("অবৈধ এক্সেস লিংক!", "danger")
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        login_id = request.form.get('login_id')
        password = request.form.get('password')
        
        user = User.query.filter_by(role='controller').filter(
            (User.username == login_id) | (User.mobile == login_id)
        ).first()
        
        if user and check_pw(password, user.password_hash):
            session['user_id'] = user.id
            session['role'] = user.role
            flash("কন্ট্রোলার প্যানেলে সফলভাবে প্রবেশ করেছেন!", "success")
            return redirect(url_for('controller_dashboard'))
            
        flash("ভুল ইউজারনাম বা পাসওয়ার্ড!", "danger")
        
    return render_template('controller_login.html', token=secret_token)

@app.route('/controller/dashboard')
def controller_dashboard():
    if session.get('role') != 'controller':
        flash("আপনার কন্ট্রোলার প্যানেলে প্রবেশের অনুমতি নেই!", "danger")
        return redirect(url_for('home'))
        
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    pending_admins = User.query.filter_by(role='admin', is_approved=False).all()
    all_users = User.query.filter(User.role != 'controller').all()
    
    return render_template('controller_dashboard.html', settings=settings, pending_admins=pending_admins, users=all_users)

@app.route('/controller/update_settings', methods=['POST'])
def update_settings():
    if session.get('role') != 'controller':
        flash("অনুমতি নেই!", "danger")
        return redirect(url_for('home'))
        
    for k, v in request.form.items():
        st = SiteSettings.query.get(k)
        if st:
            st.value = v
        else:
            db.session.add(SiteSettings(key=k, value=v))
            
    db.session.commit()
    flash("সামাজিক যোগাযোগ এবং সাপোর্ট লিংকসমূহ আপডেট হয়েছে!", "success")
    return redirect(url_for('controller_dashboard'))

@app.route('/controller/approve_admin/<user_id>', methods=['POST'])
def approve_admin(user_id):
    if session.get('role') != 'controller':
        flash("অনুমতি নেই!", "danger")
        return redirect(url_for('home'))
        
    usr = User.query.get_or_404(user_id)
    usr.is_approved = True
    db.session.commit()
    flash(f"অ্যাডমিন {usr.full_name} অনুমোদিত হয়েছে!", "success")
    return redirect(url_for('controller_dashboard'))

# -------------------------------------------------------------
# PUBLIC & USER ROUTES
# -------------------------------------------------------------
@app.route('/')
def home():
    variants = ProductVariant.query.all()
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    categories = db.session.query(Product.category_type).distinct().all()
    cat_list = [c[0] for c in categories]
    current_user = User.query.get(session.get('user_id')) if 'user_id' in session else None
    
    template = 'mobile_index.html' if request.is_button_phone else 'modern_index.html'
    return render_template(template, products=variants, settings=settings, categories=cat_list, current_user=current_user)

@app.route('/signup', methods=['POST'])
def signup():
    data = request.form
    if User.query.filter((User.username == data['username']) | (User.mobile == data['mobile'])).first():
        flash("ইউজারনাম বা মোবাইল নম্বর রেজিস্টার করা আছে!", "danger")
        return redirect(url_for('home'))

    new_user = User(
        full_name=data['full_name'],
        username=data['username'],
        email=data['email'],
        mobile=data['mobile'],
        password_hash=hash_pw(data['password']),
        house_or_road=data.get('house_or_road', ''),
        village=data.get('village', ''),
        thana=data.get('thana', ''),
        district=data.get('district', ''),
        role='user',
        is_approved=True
    )
    db.session.add(new_user)
    db.session.commit()
    flash("সাইনআপ সফল হয়েছে! এখন লগইন করুন।", "success")
    return redirect(url_for('home'))

@app.route('/login', methods=['POST'])
def login():
    login_id = request.form.get('login_id')
    password = request.form.get('password')
    user = User.query.filter((User.username == login_id) | (User.mobile == login_id)).first()
    
    if user and check_pw(password, user.password_hash):
        if user.role == 'admin' and not user.is_approved:
            flash("অ্যাডমিন অ্যাকাউন্টটি এখনও কন্ট্রোলারের অনুমোদনের অপেক্ষায় আছে!", "warning")
            return redirect(url_for('home'))
            
        session['user_id'] = user.id
        session['role'] = user.role
        flash("লগইন সফল!", "success")
        
        # কন্ট্রোলার হলে সরাসরি ড্যাশবোর্ডে পাঠাবে
        if user.role == 'controller':
            return redirect(url_for('controller_dashboard'))
            
        return redirect(url_for('home'))
        
    flash("ভুল ইউজারনাম বা পাসওয়ার্ড!", "danger")
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    flash("লগআউট করা হয়েছে!", "info")
    return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
