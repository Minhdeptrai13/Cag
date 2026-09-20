"""
Database & SQLite Storage Layer for AOV Checker SaaS
Manages users, API keys, check quotas, giftcodes, and history logs.
"""
import hashlib
import hmac
import json
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
                rank TEXT,
                hero_count INTEGER DEFAULT 0,
                skin_count INTEGER DEFAULT 0,
                is_trang INTEGER DEFAULT 0,
                created_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Auto-migration for older table schemas
        for col_def in [
            ("rank", "TEXT"),
            ("hero_count", "INTEGER DEFAULT 0"),
            ("skin_count", "INTEGER DEFAULT 0"),
            ("is_trang", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE check_history ADD COLUMN {col_def[0]} {col_def[1]}")
            except sqlite3.OperationalError:
                pass  # column already exists

        # 4. Giftcodes Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giftcodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                credits INTEGER NOT NULL,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                created_at INTEGER
            )
        """)
        # 5. User Giftcode Redeems Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_redeems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                giftcode_id INTEGER NOT NULL,
                redeemed_at INTEGER,
                UNIQUE(user_id, giftcode_id)
            )
        """)

        # Remove hardcoded admin creation so first real registered user becomes Root Owner
        # (Preserve existing tables and giftcodes)

        # Default Giftcodes for testing/freebies if not exists
        default_codes = [
            ("AOV2026", 100, 10000),
            ("TRIZ_VIP", 500, 1000),
            ("PROCHECKER", 50, 10000)
        ]
        for c, cr, mu in default_codes:
            conn.execute(
                "INSERT OR IGNORE INTO giftcodes (code, credits, max_uses, used_count, created_at) VALUES (?, ?, ?, 0, ?)",
                (c, cr, mu, int(time.time()))
            )
    conn.close()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()


def register_user(username: str, password: str) -> dict:
    username = username.strip().lower()
    if len(username) < 3 or len(password) < 4:
        return {"success": False, "error": "Tài khoản tối thiểu 3 ký tự, mật khẩu tối thiểu 4 ký tự!"}
    
    conn = get_db()
    try:
        salt = secrets.token_hex(16)
        pwd_hash = _hash_password(password, salt)
        full_hash = f"{salt}${pwd_hash}"
        now = int(time.time())
        with conn:
            # Check if this is the very first account registered
            row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
            is_first_user = (row["count"] == 0) if row else False
            assigned_role = "owner" if is_first_user else "user"
            initial_credits = 999999 if is_first_user else 50

            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, credits, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, full_hash, assigned_role, initial_credits, now)
            )
            user_id = cur.lastrowid
            key_prefix = "aov_owner_" if is_first_user else "aov_live_"
            key_val = f"{key_prefix}{secrets.token_hex(16)}"
            key_name = 'Master Key' if is_first_user else 'Default Key'
            conn.execute(
                "INSERT INTO api_keys (user_id, api_key, name, status, created_at) VALUES (?, ?, ?, 'active', ?)",
                (user_id, key_val, key_name, now)
            )
        msg = "Đăng ký thành công tài khoản ROOT OWNER (Chủ sở hữu tối cao)!" if is_first_user else "Đăng ký thành công! Bạn nhận được 50 lượt check miễn phí."
        return {
            "success": True,
            "status": "ok",
            "message": msg,
            "user": {
                "id": user_id,
                "username": username,
                "role": assigned_role,
                "credits": initial_credits,
                "api_key": key_val,
                "key": key_val
            }
        }
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
        key_row = conn.execute("SELECT api_key FROM api_keys WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
        api_key = key_row["api_key"] if key_row else ""

        return {
            "success": True,
            "status": "ok",
            "user": {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "credits": row["credits"],
                "api_key": api_key,
                "key": api_key
            }
        }
    finally:
        conn.close()


def get_user_profile(user_id: int) -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT id, username, role, credits, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return {"success": False, "error": "Không tìm thấy người dùng"}
        key_row = conn.execute("SELECT api_key FROM api_keys WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        return {
            "success": True,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "credits": row["credits"],
                "api_key": key_row["api_key"] if key_row else ""
            }
        }
    finally:
        conn.close()


def validate_api_key(api_key: str) -> dict:
    if not api_key:
        return {"valid": False, "error": "Thiếu API Key (truyền qua Authorization: Bearer <key> hoặc param ?key=...)"}
    
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
            return {"valid": False, "error": "Tài khoản đã hết số lượt check (credits = 0). Vui lòng nạp thêm lượt check!"}
        
        # Increment requests count
        with conn:
            conn.execute("UPDATE api_keys SET requests_count = requests_count + 1 WHERE id = ?", (row["key_id"],))

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


def add_credits(user_id: int, count: int):
    conn = get_db()
    try:
        with conn:
            conn.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (count, user_id))
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
        return {"success": True, "status": "ok", "api_key": new_key, "key": new_key}
    finally:
        conn.close()


def revoke_api_key(user_id: int, api_key: str) -> dict:
    conn = get_db()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE api_keys SET status = 'revoked' WHERE user_id = ? AND api_key = ?",
                (user_id, api_key.strip())
            )
            if cur.rowcount == 0:
                return {"success": False, "error": "Không tìm thấy API Key cần vô hiệu hóa"}
        return {"success": True, "status": "ok", "message": "Đã vô hiệu hóa API Key"}
    finally:
        conn.close()


def get_user_keys(user_id: int) -> list:
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, api_key, name, status, requests_count, created_at FROM api_keys WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["key"] = d["api_key"]  # alias for backward compatibility
            res.append(d)
        return res
    finally:
        conn.close()


def save_check_history(user_id: int, account: str, status: str, detail_data: dict = None):
    """Save account check result to database history"""
    if not user_id:
        return
    conn = get_db()
    try:
        rank = ""
        heroes = 0
        skins = 0
        is_trang = 0
        detail_json = ""
        if detail_data:
            aov_obj = detail_data.get("aov", {}) if isinstance(detail_data.get("aov"), dict) else {}
            rank = detail_data.get("rank") or aov_obj.get("rank", "")
            heroes = detail_data.get("heroes_count") or aov_obj.get("heroes_count", 0)
            skins = detail_data.get("skins_count") or aov_obj.get("skins_count", 0)
            is_trang = 1 if (detail_data.get("is_trang") or aov_obj.get("is_trang")) else 0
            detail_json = json.dumps(detail_data, ensure_ascii=False)

        now = int(time.time())
        with conn:
            conn.execute("""
                INSERT INTO check_history (user_id, account, status, detail, rank, hero_count, skin_count, is_trang, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, account, status, detail_json, rank, heroes, skins, is_trang, now))
    except Exception as e:
        pass
    finally:
        conn.close()


def get_user_history(user_id: int, limit: int = 200, filter_status: str = None) -> list:
    """Get history of accounts checked by user"""
    conn = get_db()
    try:
        query = "SELECT * FROM check_history WHERE user_id = ?"
        params = [user_id]
        if filter_status:
            if filter_status == "trang":
                query += " AND is_trang = 1"
            elif filter_status == "hit":
                query += " AND status = 'HIT'"
            elif filter_status == "invalid":
                query += " AND status = 'INVALID'"
            elif filter_status != "all":
                query += " AND status = ?"
                params.append(filter_status.upper())
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        history = []
        for r in rows:
            item = dict(r)
            if item.get("detail"):
                try:
                    item["detail_parsed"] = json.loads(item["detail"])
                except Exception:
                    item["detail_parsed"] = None
            history.append(item)
        return history
    finally:
        conn.close()


def clear_user_history(user_id: int) -> dict:
    conn = get_db()
    try:
        with conn:
            conn.execute("DELETE FROM check_history WHERE user_id = ?", (user_id,))
        return {"success": True, "message": "Đã xóa toàn bộ lịch sử check"}
    finally:
        conn.close()


def redeem_giftcode(user_id: int, code_str: str) -> dict:
    """Redeem a giftcode to add credits"""
    code_str = code_str.strip().upper()
    if not code_str:
        return {"success": False, "error": "Vui lòng nhập mã Giftcode!"}

    conn = get_db()
    try:
        code_row = conn.execute("SELECT * FROM giftcodes WHERE code = ?", (code_str,)).fetchone()
        if not code_row:
            return {"success": False, "error": "Mã Giftcode không tồn tại hoặc đã hết hạn!"}

        if code_row["used_count"] >= code_row["max_uses"]:
            return {"success": False, "error": "Mã Giftcode này đã hết lượt kích hoạt!"}

        # Check if user already redeemed
        redeem_row = conn.execute("SELECT id FROM user_redeems WHERE user_id = ? AND giftcode_id = ?", (user_id, code_row["id"])).fetchone()
        if redeem_row:
            return {"success": False, "error": "Bạn đã kích hoạt mã Giftcode này rồi!"}

        credits_to_add = code_row["credits"]
        now = int(time.time())
        with conn:
            conn.execute("INSERT INTO user_redeems (user_id, giftcode_id, redeemed_at) VALUES (?, ?, ?)", (user_id, code_row["id"], now))
            conn.execute("UPDATE giftcodes SET used_count = used_count + 1 WHERE id = ?", (code_row["id"],))
            conn.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (credits_to_add, user_id))
            
            user_row = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()

        return {
            "success": True,
            "status": "ok",
            "message": f"Kích hoạt thành công! Đã cộng +{credits_to_add} Credits vào tài khoản.",
            "credits_added": credits_to_add,
            "new_credits": user_row["credits"] if user_row else 0
        }
    finally:
        conn.close()


def admin_get_all_users(requester_id: int) -> dict:
    """Return all users for Root Owner / Admin panel"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {"success": False, "error": "Bạn không có quyền quản trị!"}

        rows = conn.execute("SELECT id, username, role, credits, created_at FROM users ORDER BY id ASC").fetchall()
        users = [dict(r) for r in rows]
        return {"success": True, "users": users}
    finally:
        conn.close()


def admin_adjust_credits(requester_id: int, target_user_id: int, amount: int) -> dict:
    """Adjust credits of a user (Owner and Admin can do this)"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {"success": False, "error": "Bạn không có quyền quản trị!"}

        target = conn.execute("SELECT id, username, credits, role FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if not target:
            return {"success": False, "error": "Không tìm thấy người dùng!"}

        # Admin cannot reduce credits of Owner
        if req["role"] == "admin" and target["role"] == "owner":
            return {"success": False, "error": "Admin không có quyền can thiệp tài khoản Root Owner!"}

        with conn:
            conn.execute("UPDATE users SET credits = MAX(0, credits + ?) WHERE id = ?", (amount, target_user_id))
            updated = conn.execute("SELECT credits FROM users WHERE id = ?", (target_user_id,)).fetchone()

        return {
            "success": True,
            "message": f"Đã cập nhật Credits cho {target['username']}: {'+' if amount >= 0 else ''}{amount}",
            "new_credits": updated["credits"]
        }
    finally:
        conn.close()


def admin_update_role(requester_id: int, target_user_id: int, new_role: str) -> dict:
    """Promote or Demote roles. ONLY ROOT OWNER can do this."""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] != "owner":
            return {"success": False, "error": "CHỈ ROOT OWNER mới có quyền thăng cấp hoặc hạ cấp Admin!"}

        if target_user_id == requester_id:
            return {"success": False, "error": "Không thể tự thay đổi quyền của chính Root Owner!"}

        if new_role not in ("admin", "user"):
            return {"success": False, "error": "Quyền không hợp lệ (chỉ được cấp admin hoặc user)!"}

        target = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if not target:
            return {"success": False, "error": "Không tìm thấy người dùng!"}

        with conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_user_id))

        return {
            "success": True,
            "message": f"Đã cập nhật quyền của {target['username']} thành [{new_role.upper()}]!"
        }
    finally:
        conn.close()


def admin_list_giftcodes(requester_id: int) -> dict:
    """List all giftcodes for admin panel"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {"success": False, "error": "Bạn không có quyền quản trị!"}

        rows = conn.execute("SELECT * FROM giftcodes ORDER BY id DESC").fetchall()
        return {"success": True, "giftcodes": [dict(r) for r in rows]}
    finally:
        conn.close()


def admin_create_giftcode(requester_id: int, code: str, credits: int, max_uses: int) -> dict:
    """Create a new giftcode"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {"success": False, "error": "Bạn không có quyền quản trị!"}

        code = code.strip().upper()
        if not code or credits <= 0 or max_uses <= 0:
            return {"success": False, "error": "Thông tin giftcode không hợp lệ!"}

        now = int(time.time())
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO giftcodes (code, credits, max_uses, used_count, created_at) VALUES (?, ?, ?, 0, ?)",
                (code, credits, max_uses, now)
            )
        return {"success": True, "message": f"Đã tạo thành công Giftcode [{code}] với +{credits} Credits!"}
    finally:
        conn.close()


def admin_delete_giftcode(requester_id: int, code: str) -> dict:
    """Delete a giftcode"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {"success": False, "error": "Bạn không có quyền quản trị!"}

        with conn:
            conn.execute("DELETE FROM giftcodes WHERE code = ?", (code.strip().upper(),))
        return {"success": True, "message": f"Đã xóa Giftcode [{code}]!"}
    finally:
        conn.close()

