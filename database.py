import os
import libsql_client

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

def get_db_client():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise ValueError("Turso Database URL or Auth Token missing!")
    return libsql_client.create_client(url=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)

def init_db():
    client = get_db_client()
    
    # ১. প্রোডাক্ট টেবিল
    client.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_code TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            stock_count INTEGER DEFAULT 0,
            colors TEXT,
            price REAL
        );
    """)
    
    # ২. পলিসি টেবিল
    client.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_text TEXT NOT NULL
        );
    """)
    
    # ৩. কাস্টমার টেবিল
    client.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            phone_number TEXT PRIMARY KEY,
            customer_name TEXT,
            password TEXT,
            messenger_id TEXT,
            instagram_id TEXT,
            address TEXT,
            reset_request INTEGER DEFAULT 0
        );
    """)
    
    # ৪. অর্ডার টেবিল
    client.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_code TEXT PRIMARY KEY,
            phone_number TEXT,
            details TEXT,
            color TEXT,
            status TEXT DEFAULT 'Pending',
            platform TEXT,
            FOREIGN KEY (phone_number) REFERENCES customers(phone_number)
        );
    """)

    # ৫. চ্যাট সেশন টেবিল
    client.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            phone_number TEXT,
            title TEXT,
            is_deleted INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 𝖹. চ্যাট মেসেজ টেবিল
    client.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            platform TEXT,
            sender_type TEXT, 
            sender_id TEXT,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 🔄 ৭. ডাইনামিক ওয়েবহুক সেটিংস টেবিল (নতুন)
    client.execute("""
        CREATE TABLE IF NOT EXISTS webhook_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meta_verify_token TEXT,
            meta_page_access_token TEXT,
            tiktok_client_key TEXT,
            tiktok_client_secret TEXT
        );
    """)
    
    # ডিফল্ট সেটিংস রো তৈরি করা (যদি না থাকে)
    res = client.execute("SELECT COUNT(*) as count FROM webhook_settings").rows[0]
    if res[0] == 0:
        client.execute("""
            INSERT INTO webhook_settings (meta_verify_token, meta_page_access_token, tiktok_client_key, tiktok_client_secret)
            VALUES ('lfm_verify_token_2026', '', '', '');
        """)
    
    print("✅ All Turso Tables Initialized and Webhook Storage Ready!")
    client.close()

if __name__ == "__main__":
    init_db()
