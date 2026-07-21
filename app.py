import os
import sqlite3
from flask import Flask, render_template, request

app = Flask(__name__)

# ডেটাবেস পাথ নিশ্চিত করা
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # প্রোডাক্ট টেবিল তৈরি
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            price INTEGER,
            image TEXT
        )
    ''')
    # কাস্টমার অর্ডার টেবিল তৈরি
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            payment_method TEXT,
            txid TEXT,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    
    # প্রাথমিক প্রোডাক্ট যোগ করা
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO products (name, price, image) VALUES (?, ?, ?)", 
                       ("LFM Premium T-Shirt", 450, "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500"))
        cursor.execute("INSERT INTO products (name, price, image) VALUES (?, ?, ?)", 
                       ("Smart Wireless Headphones", 1200, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500"))
    conn.commit()
    conn.close()

# Gunicorn ও Flask চালুর সাথে সাথে নিশ্চিতভাবে ডেটাবেস ইনিশিয়ালাইজ করা
init_db()

@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    all_products = cursor.fetchall()
    conn.close()
    return render_template('index.html', products=all_products)

@app.route('/buy/<int:product_id>', methods=['POST'])
def buy_product(product_id):
    customer_name = request.form.get('customer_name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    payment_method = request.form.get('payment_method')
    txid = request.form.get('txid', 'N/A')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if product and customer_name and phone and address:
        cursor.execute('''
            INSERT INTO orders (product_name, customer_name, phone, address, payment_method, txid) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (product[0], customer_name, phone, address, payment_method, txid))
        conn.commit()
    conn.close()
    return "<h1 style='text-align:center; color:green; margin-top:50px;'>অর্ডার সফল হয়েছে! আমরা আপনার সাথে যোগাযোগ করব।</h1><div style='text-align:center;'><a href='/'>হোম পেজে ফিরুন</a></div>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
