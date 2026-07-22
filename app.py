from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import urllib.parse
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)
app.secret_key = "lfm_secret_key_2026"
DB_NAME = "database.db"

# ==================== ১. ডেটাবেস অটো-ইনিশিয়ালাইজেশন ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Products টেবিল তৈরি
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            commission REAL DEFAULT 0,
            image TEXT
        )
    ''')
    
    # Orders টেবিল তৈরি
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            customer_name TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            ref_manager TEXT,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    
    # Managers (দালাল) টেবিল তৈরি
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mng_id TEXT UNIQUE,
            name TEXT,
            balance REAL DEFAULT 0
        )
    ''')
    
    # ডেমো ডাটা যোগ করা
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO products (name, price, commission, image) VALUES (?, ?, ?, ?)",
                       ("Premium Cyber T-Shirt", 500, 50, "https://via.placeholder.com/150"))
        cursor.execute("INSERT INTO products (name, price, commission, image) VALUES (?, ?, ?, ?)",
                       ("Hacker Neon Hoodie", 1200, 120, "https://via.placeholder.com/150"))
        
    cursor.execute("SELECT COUNT(*) FROM managers")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO managers (mng_id, name, balance) VALUES (?, ?, ?)",
                       ("MNG101", "Sohan", 0))

    conn.commit()
    conn.close()

# অ্যাপ চালু হওয়ার সাথে সাথে টেবিল সেটআপ হবে
init_db()

# ==================== ২. অটো ইমেইল হেলপার ====================
def send_auto_email(user_email, subject, body):
    try:
        sender_email = "your_email@gmail.com"
        sender_pass = "your_app_password"
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = user_email
        print(f"Email sent to {user_email}")
    except Exception as e:
        print(f"Email error: {e}")

# ==================== ৩. হোম পেজ (User Panel) ====================
@app.route('/')
def home():
    ref = request.args.get('ref', '')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template('index.html', products=products, ref=ref)

# ==================== ৪. ইউজার অর্ডার সিস্টেম ====================
@app.route('/order/<int:product_id>', methods=['GET', 'POST'])
def order(product_id):
    ref = request.args.get('ref', '')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        email = request.form.get('email')
        
        cursor.execute('''
            INSERT INTO orders (product_name, customer_name, phone, email, address, ref_manager, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending')
        ''', (product[1], name, phone, email, address, ref))
        
        conn.commit()
        conn.close()
        
        return f"<div style='text-align:center; padding:50px; background:#0d1117; color:#00ff66; font-family:monospace;'><h2>আপনার অর্ডারটি সফলভাবে গ্রহণ করা হয়েছে!</h2><a href='/' style='color:#fff;'>হোম পেজে ফিরে যান</a></div>"

    conn.close()
    return render_template('order.html', product=product, ref=ref)

# ==================== ৫. অ্যাডমিন প্যানেল ====================
@app.route('/admin')
def admin_panel():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template('admin.html', orders=orders, products=products)

# অর্ডার স্ট্যাটাস আপডেট
@app.route('/admin/update-status/<int:order_id>/<status>')
def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    if order:
        cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        
        if status == 'Done' and order[6]:
            cursor.execute("SELECT price, commission FROM products WHERE name = ?", (order[1],))
            prod = cursor.fetchone()
            if prod:
                commission = prod[1]
                cursor.execute("UPDATE managers SET balance = balance + ? WHERE mng_id = ?", (commission, order[6]))

        conn.commit()
        conn.close()

        subject = f"LFM Order Update - #{order_id}"
        body = f"প্রিয় {order[2]},\nআপনার অর্ডার #{order_id} এর বর্তমান স্ট্যাটাস: {status}।"
        send_auto_email(order[4], subject, body)

        wa_message = f"🔥 *LFM Order Update* 🔥\n\nপ্রিয় {order[2]},\nআপনার অর্ডার #{order_id} এর বর্তমান স্ট্যাটাস: *{status}*!\n\nধন্যবাদ,\nLFM Team"
        encoded_msg = urllib.parse.quote(wa_message)
        wa_url = f"https://wa.me/88{order[3]}?text={encoded_msg}"
        
        return redirect(wa_url)

    conn.close()
    return redirect(url_for('admin_panel'))

# ==================== ৬. ম্যানেজার প্যানেল ====================
@app.route('/manager')
def manager_panel():
    mng_id = "MNG101"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM managers WHERE mng_id = ?", (mng_id,))
    info = cursor.fetchone()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()
    return render_template('manager.html', mng_id=mng_id, info=info, products=products)

# ==================== ৭. কন্ট্রোলার প্যানেল ====================
@app.route('/controller')
def controller_panel():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM managers")
    managers = cursor.fetchall()
    cursor.execute("SELECT * FROM orders")
    orders = cursor.fetchall()
    conn.close()
    return render_template('controller.html', managers=managers, orders=orders)

if __name__ == '__main__':
    app.run(debug=True)
