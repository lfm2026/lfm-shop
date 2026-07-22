from flask import Flask, render_template, request, redirect, url_for, session, flash
import urllib.parse
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "lfm_secret_key_123"

# টেস্টের জন্য মেমোরি ডেটাবেস (পরে এটি SQLite বা DB তে যাবে)
products = [
    {"id": 1, "name": "Premium Cyber T-Shirt", "price": 500, "commission": 50, "image": "https://via.placeholder.com/150"},
    {"id": 2, "name": "Hacker Neon Hoodie", "price": 1200, "commission": 120, "image": "https://via.placeholder.com/150"}
]

orders = []
managers = {"MNG101": {"name": "Sohan", "balance": 0}}

# ইমেইল পাঠানোর হেলপার ফাংশন (১০০% ফ্রি)
def send_auto_email(user_email, subject, body):
    try:
        # এখানে তোমার জিমেইল অ্যাপ পাসওয়ার্ড সেট করতে পারো
        sender_email = "your_email@gmail.com"
        sender_pass = "your_app_password"
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = user_email
        
        # with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        #     server.login(sender_email, sender_pass)
        #     server.sendmail(sender_email, user_email, msg.as_string())
        print(f"Email sent to {user_email}")
    except Exception as e:
        print(f"Email failed: {e}")

# ==================== ১. মূল হোম পেজ ====================
@app.route('/')
def home():
    ref = request.args.get('ref', '')
    return render_template('index.html', products=products, ref=ref)

# ==================== ২. ইউজার অর্ডার সিস্টেম ====================
@app.route('/order/<int:product_id>', methods=['GET', 'POST'])
def order(product_id):
    product = next((p for p in products if p['id'] == product_id), None)
    ref = request.args.get('ref', '')

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        email = request.form.get('email')
        
        order_data = {
            "order_id": len(orders) + 1,
            "product": product['name'],
            "price": product['price'],
            "customer_name": name,
            "phone": phone,
            "email": email,
            "address": address,
            "ref_manager": ref,
            "status": "Pending"
        }
        orders.append(order_data)
        
        return f"<h3>আপনার অর্ডার সফল হয়েছে! অর্ডার আইডি: #{order_data['order_id']}</h3><a href='/'>হোমে ফিরে যান</a>"

    return render_template('order.html', product=product, ref=ref)

# ==================== ৩. অ্যাডমিন প্যানেল ====================
@app.route('/admin')
def admin_panel():
    return render_template('admin.html', orders=orders, products=products)

@app.route('/admin/update-status/<int:order_id>/<status>')
def update_order_status(order_id, status):
    order = next((o for o in orders if o['order_id'] == order_id), None)
    if order:
        order['status'] = status
        
        # ১. অটোমেটিক ইমেইল পাঠাবে
        email_subject = f"LFM Order Update - Status: {status}"
        email_body = f"প্রিয় {order['customer_name']},\nআপনার অর্ডার #{order['order_id']} স্ট্যাটাস এখন: {status}।"
        send_auto_email(order['email'], email_subject, email_body)
        
        # ২. হোয়াটসঅ্যাপ মেসেজসহ ডিরেক্ট লিঙ্ক তৈরি
        wa_message = f"🔥 *LFM Order Update* 🔥\n\nপ্রিয় {order['customer_name']},\nআপনার অর্ডার আইডি #{order['order_id']} এর স্ট্যাটাস: *{status}*!\n\nধন্যবাদ,\nLFM Team"
        encoded_msg = urllib.parse.quote(wa_message)
        wa_url = f"https://wa.me/88{order['phone']}?text={encoded_msg}"
        
        return redirect(wa_url)

    return redirect(url_for('admin_panel'))

# ==================== ৪. ম্যানেজার প্যানেল (দালাল/অ্যাফিলিয়েট) ====================
@app.route('/manager')
def manager_panel():
    mng_id = "MNG101" # উদাহরণ হিসেবে আইডি
    mng_info = managers.get(mng_id)
    return render_template('manager.html', mng_id=mng_id, info=mng_info, products=products)

# ==================== ৫. কন্ট্রোলার প্যানেল (মাস্টার কন্ট্রোল) ====================
@app.route('/controller')
def controller_panel():
    total_sales = sum(o['price'] for o in orders if o['status'] in ['Approved', 'Done'])
    return render_template('controller.html', managers=managers, orders=orders, total_sales=total_sales)

if __name__ == '__main__':
    app.run(debug=True)
