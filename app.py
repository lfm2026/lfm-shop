import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'lfm_secret_key_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            file_url TEXT NOT NULL,
            file_type TEXT NOT NULL,
            download_link TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# হোম পেজ
@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    all_products = cursor.fetchall()
    conn.close()
    return render_template('index.html', products=all_products)

# প্রোডাক্টের জন্য আলাদা পেজ
@app.route('/products')
def products_page():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    all_products = cursor.fetchall()
    conn.close()
    return render_template('index.html', products=all_products, show_all=True)

# লগইন ও সাইন আপ পেজ
@app.route('/login')
def login():
    return render_template('login.html')

# এডমিন প্যানেল
@app.route('/admin')
def admin():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    all_products = cursor.fetchall()
    conn.close()
    return render_template('admin.html', products=all_products)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
