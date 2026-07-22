from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import urllib.parse
from functools import wraps

app = Flask(__name__)
app.secret_key = "lfm_pro_luxury_key_2026"
DB_NAME = "database.db"

# ==================== Database Setup ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        is_blocked INTEGER DEFAULT 0
    )''')
    
    # Products Table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        size TEXT,
        description TEXT,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        image TEXT,
        video TEXT
    )''')
    
    # Orders Table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        address TEXT,
        status TEXT DEFAULT 'Pending'
    )''')
    
    # Cart Table
    c.execute('''CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER
    )''')
    
    # Reviews Table
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        user_id INTEGER,
        rating INTEGER,
        comment TEXT
    )''')

    # Controller Account setup
    c.execute("SELECT * FROM users WHERE role='controller'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, phone, password, role) VALUES (?, ?, ?, ?)", 
                  ('SuperAdmin', '01700000000', '12345', 'controller'))
        
    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("অনুগ্রহ করে আগে লগইন করুন!", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== Auth Routes (Separated) ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE phone=? AND password=?", (phone, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            if user[5] == 1:
                flash("আপনার অ্যাকাউন্টটি ব্লক করা হয়েছে! হেল্পডেস্কে যোগাযোগ করুন।", "danger")
            else:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[4]
                flash("সফলভাবে লগইন হয়েছে!", "success")
                return redirect(url_for('home'))
        else:
            flash("ফোন নম্বর বা পাসওয়ার্ড ভুল দেওয়া হয়েছে!", "danger")
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, phone, password) VALUES (?, ?, ?)", (username, phone, password))
            conn.commit()
            conn.close()
            flash("অ্যাকাউন্ট তৈরি হয়েছে! এবার লগইন করুন।", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash("এই ফোন নম্বর বা ইউজারনেম দিয়ে ইতিমধ্যেই অ্যাকাউন্ট রয়েছে!", "danger")
            
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("লগআউট সফল হয়েছে।", "info")
    return redirect(url_for('home'))

# ==================== Main Store Routes ====================
@app.route('/')
def home():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()
    return render_template('index.html', products=products)

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def view_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if request.method == 'POST' and 'user_id' in session:
        rating = request.form.get('rating')
        comment = request.form.get('comment')
        
        c.execute("SELECT * FROM orders WHERE user_id=? AND product_id=? AND status='Delivered'", (session['user_id'], product_id))
        if c.fetchone():
            c.execute("INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)", 
                      (product_id, session['user_id'], rating, comment))
            conn.commit()
            flash("আপনার রিভিউ যোগ করা হয়েছে!", "success")
        else:
            flash("পণ্যটি হাতে পাওয়ার পরেই কেবল রিভিউ দেওয়া সম্ভব!", "warning")
            
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = c.fetchone()
    
    c.execute("SELECT r.rating, r.comment, u.username FROM reviews r JOIN users u ON r.user_id = u.id WHERE r.product_id=?", (product_id,))
    reviews = c.fetchall()
    conn.close()
    
    return render_template('product.html', product=product, reviews=reviews)

@app.route('/add_to_cart/<int:product_id>')
@login_required
def add_to_cart(product_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (session['user_id'], product_id))
    conn.commit()
    conn.close()
    flash("পণ্যটি কার্টে যোগ করা হয়েছে!", "success")
    return redirect(url_for('cart'))

@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if request.method == 'POST':
        address = request.form.get('address')
        c.execute("SELECT product_id FROM cart WHERE user_id=?", (session['user_id'],))
        cart_items = c.fetchall()
        
        for item in cart_items:
            c.execute("UPDATE products SET stock = stock - 1 WHERE id=?", (item[0],))
            c.execute("INSERT INTO orders (user_id, product_id, address) VALUES (?, ?, ?)", (session['user_id'], item[0], address))
            
        c.execute("DELETE FROM cart WHERE user_id=?", (session['user_id'],))
        conn.commit()
        flash("অর্ডার সফলভাবে প্লেস হয়েছে!", "success")
        return redirect(url_for('home'))
        
    c.execute("SELECT p.*, c.id FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?", (session['user_id'],))
    items = c.fetchall()
    total = sum([item[4] for item in items])
    conn.close()
    return render_template('cart.html', items=items, total=total)

# ==================== Admin & Controller Routes ====================
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if session.get('role') not in ['admin', 'controller']:
        return "Access Denied"
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_product':
            c.execute("INSERT INTO products (name, size, description, price, stock, image, video) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (request.form.get('name'), request.form.get('size'), request.form.get('description'), 
                       request.form.get('price'), request.form.get('stock'), request.form.get('image'), request.form.get('video')))
            conn.commit()
        elif action == 'delete_product':
            c.execute("DELETE FROM products WHERE id=?", (request.form.get('product_id'),))
            conn.commit()
            
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    c.execute("SELECT o.id, u.username, u.phone, p.name, o.address, o.status FROM orders o JOIN users u ON o.user_id = u.id JOIN products p ON o.product_id = p.id ORDER BY o.id DESC")
    orders = c.fetchall()
    conn.close()
    return render_template('admin.html', products=products, orders=orders)

@app.route('/admin/update_order/<int:order_id>/<status>')
@login_required
def update_order(order_id, status):
    if session.get('role') not in ['admin', 'controller']:
        return "Access Denied"
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    c.execute("SELECT u.phone, u.username FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?", (order_id,))
    user_info = c.fetchone()
    conn.commit()
    conn.close()
    
    if user_info:
        wa_text = urllib.parse.quote(f"প্রিয় {user_info[1]},\nআপনার অর্ডার #{order_id} এর বর্তমান স্ট্যাটাস: *{status}*।\n- LFM Team")
        wa_url = f"https://wa.me/88{user_info[0]}?text={wa_text}"
        return redirect(wa_url)
        
    return redirect(url_for('admin_panel'))

@app.route('/controller', methods=['GET', 'POST'])
@login_required
def controller_panel():
    if session.get('role') != 'controller':
        return "Only SuperAdmin (Controller) can access."
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        uid = request.form.get('user_id')
        
        if action == 'block':
            c.execute("UPDATE users SET is_blocked=1 WHERE id=?", (uid,))
        elif action == 'unblock':
            c.execute("UPDATE users SET is_blocked=0 WHERE id=?", (uid,))
        elif action == 'make_admin':
            c.execute("UPDATE users SET role='admin' WHERE id=?", (uid,))
        elif action == 'delete':
            c.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()
    return render_template('controller.html', users=users)

if __name__ == '__main__':
    app.run(debug=True)
