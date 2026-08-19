import random
import string
import hashlib

def generate_18char_token(prefix="lfm"):
    characters = string.ascii_letters + string.digits + "!@#$%"
    random_str = ''.join(random.choice(characters) for _ in range(18))
    return f"{prefix}_{random_str}"

def generate_unique_product_id(title, size, color):
    raw_str = f"{title}-{size}-{color}-{generate_18char_token('id')}"
    short_hash = hashlib.md5(raw_str.encode()).hexdigest()[:6]
    return f"LFM-{short_hash.upper()}"
