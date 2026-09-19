"""
Database & SQLite Storage Layer for AOV Checker SaaS
Manages users, API keys, check quotas, and history logs.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aov_saas.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with conn:
        # 1. Users Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                credits INTEGER DEFAULT 50,
                created_at INTEGER
            )
        """)
        # 2. API Keys Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT 'Default Key',
                status TEXT DEFAULT 'active',
                requests_count INTEGER DEFAULT 0,
                created_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # 3. Check History Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT,
                created_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Default Admin if not exists
        admin = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if not admin:
            salt = secrets.token_hex(16)
            pwd_hash = _hash_password("admin123", salt)
            conn.execute(
                "INSERT INTO users (username, password_hash, role, credits, created_at) VALUES (?, ?, ?, ?, ?)",
                ("admin", f"{salt}${pwd_hash}", "admin", 999999, int(time.time()))
            )
    conn.close()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def register_user(username: str, password: str) -> dict:
    username = username.strip().lower()
    if len(username) < 3 or len(password) < 6:
        return {"success": False, "error": "Tài khoản tối thiểu 3 ký tự, mật khẩu tối thiểu 6 ký tự!"}
    
    conn = get_db()
    try:
        salt = secrets.token_hex(16)
        pwd_hash = _hash_password(password, salt)
        full_hash = f"{salt}${pwd_hash}"
        now = int(time.time())
        with conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, credits, created_at) VALUES (?, ?, 'user', 50, ?)",
                (username, full_hash, now)
            )
            user_id = cur.lastrowid
            # Create default API Key for new user
            key_val = f"aov_live_{secrets.token_hex(16)}"
            conn.execute(
                "INSERT INTO api_keys (user_id, api_key, name, status, created_at) VALUES (?, ?, 'Default Key', 'active', ?)",
                (user_id, key_val, now)
            )
        return {"success": True, "message": "Đăng ký thành công! Bạn nhận được 50 lượt check miễn phí.", "user_id": user_id, "api_key": key_val}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Tài khoản này đã có người đăng ký!"}
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    username = username.strip().lower()
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            return {"success": False, "error": "Tài khoản hoặc mật khẩu không chính xác!"}
        
        stored_hash = row["password_hash"]
        if "$" not in stored_hash:
            return {"success": False, "error": "Lỗi xác thực hash!"}
        
        salt, p_hash = stored_hash.split("$", 1)
        check_hash = _hash_password(password, salt)
        if not hmac.compare_digest(p_hash, check_hash):
            return {"success": False, "error": "Tài khoản hoặc mật khẩu không chính xác!"}
        
        # Get active API Key
        key_row = conn.execute("SELECT api_key FROM api_keys WHERE user_id = ? AND status = 'active' LIMIT 1", (row["id"],)).fetchone()
        api_key = key_row["api_key"] if key_row else ""

        return {
            "success": True,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "credits": row["credits"],
                "api_key": api_key
            }
        }
    finally:
        conn.close()


def validate_api_key(api_key: str) -> dict:
    if not api_key:
        return {"valid": False, "error": "Thiếu API Key (truyền qua Authorization: Bearer <key> hoặc query ?key=...)"}
    
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT k.id as key_id, k.status, u.id as user_id, u.username, u.credits, u.role
            FROM api_keys k
            JOIN users u ON k.user_id = u.id
            WHERE k.api_key = ?
        """, (api_key.strip(),)).fetchone()

        if not row:
            return {"valid": False, "error": "API Key không hợp lệ hoặc không tồn tại!"}
        if row["status"] != "active":
            return {"valid": False, "error": "API Key đã bị vô hiệu hóa!"}
        if row["credits"] <= 0 and row["role"] != "admin":
            return {"valid": False, "error": "Tài khoản đã hết số lượt check (credits = 0). Vui lòng liên hệ Admin!"}
        
        return {
            "valid": True,
            "key_id": row["key_id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "credits": row["credits"],
            "role": row["role"]
        }
    finally:
        conn.close()


def deduct_credit(user_id: int, count: int = 1):
    conn = get_db()
    try:
        with conn:
            conn.execute("UPDATE users SET credits = MAX(0, credits - ?) WHERE id = ? AND role != 'admin'", (count, user_id))
    finally:
        conn.close()


def generate_new_api_key(user_id: int, key_name: str = "New Key") -> dict:
    conn = get_db()
    try:
        new_key = f"aov_live_{secrets.token_hex(16)}"
        now = int(time.time())
        with conn:
            conn.execute(
                "INSERT INTO api_keys (user_id, api_key, name, status, created_at) VALUES (?, ?, ?, 'active', ?)",
                (user_id, new_key, key_name, now)
            )
        return {"success": True, "api_key": new_key}
    finally:
        conn.close()


def get_user_keys(user_id: int) -> list:
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, api_key, name, status, requests_count, created_at FROM api_keys WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
