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

# DB_PATH: read from env var DB_PATH (set this on deploy platform to a persistent volume path)
# Falls back to <project_root>/data/aov_saas.db so git deploys don't wipe the DB
_ROOT = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(_ROOT, "data", "aov_saas.db")
)
# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


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

        # Auto-migration for users table (additive, safe for existing DBs)
        for col_def in [
            ("display_name", "TEXT"),
            ("avatar_url", "TEXT"),
            ("email", "TEXT"),
            ("is_banned", "INTEGER DEFAULT 0"),
            ("ban_reason", "TEXT"),
            ("tier", "TEXT DEFAULT 'free'"),
            ("ai_usage_counter", "INTEGER DEFAULT 0"),
            # AI Token Economy (replaces old 10-message credit model)
            ("ai_free_tokens", "INTEGER DEFAULT 10000"),
            ("ai_paid_tokens", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col_def[0]} {col_def[1]}")
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

        # 6. Immutable Credit Transactions Ledger (Sổ Cái Bất Biến)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                balance_before INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                description TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 7. Admin Audit & Security Violation Logs (Nhật Ký Thanh Tra & Vi Phạm)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                target_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at INTEGER NOT NULL
            )
        """)

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


# ── HMAC SESSION SECURITY & SECRETS ─────────────────────────────────────────
SERVER_SESSION_SECRET = os.environ.get("SERVER_SESSION_SECRET", "aov_triz_root_secure_vault_2026_cipher_key_!@#$")

def generate_session_token(user_id: int, role: str) -> str:
    """Generate tamper-proof HMAC-SHA256 authenticated session token"""
    ts = int(time.time())
    payload = f"{user_id}:{role}:{ts}"
    sig = hmac.new(SERVER_SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"

def verify_session_token(token: str) -> dict:
    """Verify session token and extract verified user_id and role"""
    if not token or "." not in token:
        return {"valid": False, "error": "Missing or invalid token format"}
    try:
        payload, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(SERVER_SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return {"valid": False, "error": "Token signature mismatch (Tampering detected)"}
        parts = payload.split(":")
        if len(parts) < 3:
            return {"valid": False, "error": "Malformed token payload"}
        uid = int(parts[0])
        role = parts[1]
        
        # Verify in database that user exists and is not banned
        conn = get_db()
        try:
            row = conn.execute("SELECT id, role, is_banned, credits, tier FROM users WHERE id = ?", (uid,)).fetchone()
            if not row:
                return {"valid": False, "error": "User does not exist"}
            if row["is_banned"]:
                return {"valid": False, "is_banned": True, "error": "Tài khoản của bạn đã bị khóa do vi phạm quy tắc!"}
            return {
                "valid": True,
                "user_id": uid,
                "role": row["role"],
                "credits": row["credits"],
                "tier": row["tier"] if "tier" in row.keys() else "free"
            }
        finally:
            conn.close()
    except Exception as e:
        return {"valid": False, "error": f"Token verification error: {str(e)}"}


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
            # QUY TẮC BẤT BIẾN: Chỉ duy nhất người đầu tiên là Root Owner
            # Kiểm tra xem đã có bất kỳ tài khoản Owner nào tồn tại chưa
            owner_row = conn.execute("SELECT id FROM users WHERE role = 'owner' LIMIT 1").fetchone()
            count_row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
            total_users = count_row["count"] if count_row else 0

            is_first_user = (owner_row is None and total_users == 0)
            assigned_role = "owner" if is_first_user else "user"
            initial_credits = 999999 if is_first_user else 50
            assigned_tier = "vip_unlimited" if is_first_user else "free"

            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, credits, tier, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (username, full_hash, assigned_role, initial_credits, assigned_tier, now)
            )
            user_id = cur.lastrowid
            key_prefix = "aov_owner_" if is_first_user else "aov_live_"
            key_val = f"{key_prefix}{secrets.token_hex(16)}"
            key_name = 'Master Key' if is_first_user else 'Default Key'
            conn.execute(
                "INSERT INTO api_keys (user_id, api_key, name, status, created_at) VALUES (?, ?, ?, 'active', ?)",
                (user_id, key_val, key_name, now)
            )

            # Ghi sổ cái khởi tạo credits
            conn.execute("""
                INSERT INTO credit_transactions (user_id, amount, balance_before, balance_after, action_type, description, created_at)
                VALUES (?, ?, 0, ?, 'INITIAL_GRANT', ?, ?)
            """, (user_id, initial_credits, initial_credits, f"Cấp Credits khởi tạo tài khoản [{assigned_role.upper()}]", now))

        session_token = generate_session_token(user_id, assigned_role)
        msg = "Đăng ký thành công tài khoản ROOT OWNER (Chủ sở hữu tối cao)!" if is_first_user else "Đăng ký thành công! Bạn nhận được 50 lượt check miễn phí."
        return {
            "success": True,
            "status": "ok",
            "message": msg,
            "session_token": session_token,
            "user": {
                "id": user_id,
                "username": username,
                "role": assigned_role,
                "tier": assigned_tier,
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
        
        # Check if banned
        if "is_banned" in row.keys() and row["is_banned"]:
            reason = row["ban_reason"] or "Vi phạm điều khoản hoặc nghi vấn can thiệp hệ thống"
            return {"success": False, "is_banned": True, "error": f"[TÀI KHOẢN BỊ KHÓA] {reason}"}

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

        session_token = generate_session_token(row["id"], row["role"])

        return {
            "success": True,
            "status": "ok",
            "session_token": session_token,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "display_name": (row["display_name"] if "display_name" in row.keys() and row["display_name"] else row["username"]),
                "avatar_url": (row["avatar_url"] if "avatar_url" in row.keys() and row["avatar_url"] else ""),
                "email": (row["email"] if "email" in row.keys() and row["email"] else ""),
                "role": row["role"],
                "tier": row["tier"] if "tier" in row.keys() else "free",
                "credits": row["credits"],
                "ai_free_tokens": row["ai_free_tokens"] if "ai_free_tokens" in row.keys() else 0,
                "ai_paid_tokens": row["ai_paid_tokens"] if "ai_paid_tokens" in row.keys() else 0,
                "api_key": api_key,
                "key": api_key
            }
        }
    finally:
        conn.close()


def get_user_profile(user_id: int) -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return {"success": False, "error": "Không tìm thấy người dùng"}
        key_row = conn.execute("SELECT api_key FROM api_keys WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        return {
            "success": True,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "display_name": (row["display_name"] if "display_name" in row.keys() and row["display_name"] else row["username"]),
                "avatar_url": (row["avatar_url"] if "avatar_url" in row.keys() and row["avatar_url"] else ""),
                "email": (row["email"] if "email" in row.keys() and row["email"] else ""),
                "role": row["role"],
                "credits": row["credits"],
                "ai_free_tokens": row["ai_free_tokens"] if "ai_free_tokens" in row.keys() else 0,
                "ai_paid_tokens": row["ai_paid_tokens"] if "ai_paid_tokens" in row.keys() else 0,
                "api_key": key_row["api_key"] if key_row else "",
                "created_at": row["created_at"]
            }
        }
    finally:
        conn.close()


def update_user_profile(user_id: int, display_name: str = None, avatar_url: str = None, email: str = None) -> dict:
    """
    Update display_name, avatar_url, and email.
    CRITICAL: username is strictly immutable and cannot be altered.
    """
    conn = get_db()
    try:
        user = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return {"success": False, "error": "Không tìm thấy người dùng!"}
        
        updates = []
        params = []
        if display_name is not None:
            clean_display = str(display_name).strip()[:50]
            updates.append("display_name = ?")
            params.append(clean_display if clean_display else user["username"])
        if avatar_url is not None:
            clean_avatar = str(avatar_url).strip()
            # Support both URLs (http...) and base64 data URLs (data:image/...;base64,...)
            # No aggressive truncation - base64 images can be large
            if len(clean_avatar) > 600000:
                return {"success": False, "error": "Ảnh quá lớn để lưu trữ! Vui lòng nén ảnh nhỏ hơn (< 400KB)."}
            updates.append("avatar_url = ?")
            params.append(clean_avatar)
        if email is not None:
            clean_email = str(email).strip()[:100]
            updates.append("email = ?")
            params.append(clean_email)
        
        if not updates:
            return {"success": True, "message": "Không có gì thay đổi."}
        
        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        with conn:
            conn.execute(sql, tuple(params))
            
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return {
            "success": True,
            "message": "Cập nhật hồ sơ tài khoản thành công!",
            "user": {
                "id": updated["id"],
                "username": updated["username"],
                "display_name": (updated["display_name"] if "display_name" in updated.keys() and updated["display_name"] else updated["username"]),
                "avatar_url": (updated["avatar_url"] if "avatar_url" in updated.keys() and updated["avatar_url"] else ""),
                "email": (updated["email"] if "email" in updated.keys() and updated["email"] else ""),
                "role": updated["role"],
                "credits": updated["credits"]
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


import math

def record_credit_ledger(conn, user_id: int, amount: int, action_type: str, description: str):
    """Ghi lại biến động số dư bất biến vào bảng credit_transactions"""
    now = int(time.time())
    u = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()
    if not u:
        return
    current_balance = u["credits"]
    balance_before = current_balance - amount
    conn.execute("""
        INSERT INTO credit_transactions (user_id, amount, balance_before, balance_after, action_type, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, amount, balance_before, current_balance, action_type, description, now))


def deduct_check_credits(user_id: int, account_count: int, action_type: str = "BATCH_CHECK", description: str = "") -> dict:
    """
    Tỷ lệ quy đổi tối ưu: 1 CREDIT = 10 TÀI KHOẢN CHECK
    Ví dụ: 1-10 acc = 1 Cr | 50 acc = 5 Cr | 100 acc = 10 Cr
    Owner, Admin, hoặc gói VIP Unlimited được miễn phí vô hạn.
    """
    if not user_id or account_count <= 0:
        return {"success": True, "credits_deducted": 0}

    credits_needed = max(1, math.ceil(account_count / 10))
    conn = get_db()
    try:
        with conn:
            u = conn.execute("SELECT id, username, role, credits, tier, is_banned FROM users WHERE id = ?", (user_id,)).fetchone()
            if not u:
                return {"success": False, "error": "Không tìm thấy người dùng!"}
            if u["is_banned"]:
                return {"success": False, "error": "Tài khoản của bạn đã bị khóa do vi phạm điều khoản!"}

            # Miễn phí cho Owner, Admin hoặc VIP Unlimited
            if u["role"] in ("owner", "admin") or u["tier"] == "vip_unlimited":
                return {"success": True, "credits_deducted": 0, "remaining_credits": u["credits"], "is_vip": True}

            if u["credits"] < credits_needed:
                return {
                    "success": False,
                    "error": f"Không đủ Credits! Bạn cần {credits_needed} Credits để quét {account_count} tài khoản (1 Credit = 10 Acc). Số dư hiện tại: {u['credits']} Credits.",
                    "credits_needed": credits_needed,
                    "credits_available": u["credits"]
                }

            conn.execute("UPDATE users SET credits = credits - ? WHERE id = ?", (credits_needed, user_id))
            record_credit_ledger(conn, user_id, -credits_needed, action_type, description or f"Quét {account_count} tài khoản (Tỷ lệ: 1 Cr = 10 Acc)")

            updated = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()
            return {
                "success": True,
                "credits_deducted": credits_needed,
                "remaining_credits": updated["credits"]
            }
    finally:
        conn.close()


# AI_TOKEN_COST_TABLE - Mức tiêu thụ token theo từng tác vụ
AI_TOKEN_COSTS = {
    "text_per_char": 0.25,         # 1 token / 4 ký tự (input + output estimate)
    "search_extra": 500,           # Web/live search context injection
    "image_vision_extra": 800,     # Vision tensor + OCR analysis
    "file_analysis_per_char": 0.25, # Same as text, capped at 2000 tokens
    "file_analysis_max": 2000,     # Hard cap per file
    "thinking_cot_extra": 300,     # Chain-of-Thought reasoning overhead
    "deep_research_extra": 300,    # Deep research mode overhead
}
AI_FREE_TOKENS_INITIAL = 10_000    # Token free tặng khi đăng ký
AI_TOKENS_PER_CREDIT = 2_000       # 1 Credit = 2,000 AI Tokens


def estimate_ai_tokens(
    message: str = "",
    has_image: bool = False,
    file_content: str = "",
    enable_search: bool = False,
    enable_thinking: bool = False,
    enable_deep_research: bool = False,
) -> int:
    """Ước tính số token tiêu thụ trước khi gửi request AI"""
    total = 0
    # Text cost (input message + estimated output)
    total += max(20, int(len(message) * AI_TOKEN_COSTS["text_per_char"] * 2))  # *2 for output estimate
    # Vision cost
    if has_image:
        total += AI_TOKEN_COSTS["image_vision_extra"]
    # File analysis cost
    if file_content:
        file_tokens = min(int(len(file_content) * AI_TOKEN_COSTS["file_analysis_per_char"]),
                          int(AI_TOKEN_COSTS["file_analysis_max"]))
        total += file_tokens
    # Feature toggles
    if enable_search:
        total += AI_TOKEN_COSTS["search_extra"]
    if enable_thinking:
        total += AI_TOKEN_COSTS["thinking_cot_extra"]
    if enable_deep_research:
        total += AI_TOKEN_COSTS["deep_research_extra"]
    return max(20, int(total))


def deduct_ai_tokens(
    user_id: int,
    tokens_needed: int,
    action_type: str = "AI_CHAT",
    description: str = "",
) -> dict:
    """
    Trừ AI Tokens theo thứ tự ưu tiên: Free Tokens trước -> Paid Tokens sau.
    Owner/Admin/VIP Unlimited được miễn phí vô hạn.
    Khi hết cả hai nguồn token -> Trả về out_of_tokens: True để frontend hiển thị prompt quy đổi.
    """
    if not user_id or tokens_needed <= 0:
        return {"success": True, "tokens_deducted": 0, "charged": False}

    conn = get_db()
    try:
        with conn:
            u = conn.execute(
                "SELECT id, role, credits, tier, ai_free_tokens, ai_paid_tokens FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            if not u:
                return {"success": False, "error": "Không tìm thấy người dùng!"}

            # VIP / privileged: unlimited free usage
            if u["role"] in ("owner", "admin") or (u["tier"] or "") == "vip_unlimited":
                return {
                    "success": True, "charged": False,
                    "tokens_deducted": tokens_needed,
                    "free_tokens_remaining": u["ai_free_tokens"] or 0,
                    "paid_tokens_remaining": u["ai_paid_tokens"] or 0,
                }

            free_t = u["ai_free_tokens"] or 0
            paid_t = u["ai_paid_tokens"] or 0
            total_available = free_t + paid_t

            if total_available < tokens_needed:
                return {
                    "success": False,
                    "out_of_tokens": True,
                    "remaining_tokens": total_available,
                    "free_tokens": free_t,
                    "paid_tokens": paid_t,
                    "credits_available": u["credits"],
                    "rate_per_credit": AI_TOKENS_PER_CREDIT,
                    "tokens_needed": tokens_needed,
                    "error": (
                        f"Bạn đã sử dụng hết Token AI! (Còn {total_available:,} tokens, cần {tokens_needed:,} tokens). "
                        "Hãy dùng Credit của tài khoản để đổi lấy thêm Token AI và tiếp tục trò chuyện!"
                    )
                }

            # Deduct: free first, then paid
            free_deduct = min(free_t, tokens_needed)
            paid_deduct = tokens_needed - free_deduct
            new_free = free_t - free_deduct
            new_paid = paid_t - paid_deduct

            conn.execute(
                "UPDATE users SET ai_free_tokens = ?, ai_paid_tokens = ? WHERE id = ?",
                (new_free, new_paid, user_id)
            )

            desc = description or f"Tiêu thụ {tokens_needed:,} AI Tokens ({action_type})"
            now = int(time.time())
            conn.execute("""
                INSERT INTO credit_transactions
                    (user_id, amount, balance_before, balance_after, action_type, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, 0, free_t + paid_t, new_free + new_paid, action_type, desc, now))

            return {
                "success": True, "charged": True,
                "tokens_deducted": tokens_needed,
                "free_tokens_remaining": new_free,
                "paid_tokens_remaining": new_paid,
            }
    finally:
        conn.close()


def convert_credits_to_tokens(user_id: int, credits_to_spend: int) -> dict:
    """
    Quy đổi Credits của tài khoản sang AI Paid Tokens.
    Tỷ lệ: 1 Credit = 2,000 AI Tokens.
    Ghi nhận bất biến vào Sổ cái Credit Transactions.
    """
    if not user_id or credits_to_spend <= 0:
        return {"success": False, "error": "Số Credits quy đổi phải lớn hơn 0!"}

    tokens_gained = credits_to_spend * AI_TOKENS_PER_CREDIT
    conn = get_db()
    try:
        with conn:
            u = conn.execute(
                "SELECT id, role, credits, ai_free_tokens, ai_paid_tokens FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            if not u:
                return {"success": False, "error": "Không tìm thấy người dùng!"}
            if u["credits"] < credits_to_spend:
                return {
                    "success": False,
                    "error": f"Không đủ Credits! Bạn có {u['credits']:,} Credits, cần {credits_to_spend:,} Credits."
                }

            # Deduct credits, add paid tokens
            new_credits = u["credits"] - credits_to_spend
            new_paid = (u["ai_paid_tokens"] or 0) + tokens_gained
            conn.execute(
                "UPDATE users SET credits = ?, ai_paid_tokens = ? WHERE id = ?",
                (new_credits, new_paid, user_id)
            )

            # Record immutable ledger entry
            now = int(time.time())
            record_credit_ledger(
                conn, user_id, -credits_to_spend,
                "AI_TOKEN_EXCHANGE",
                f"Quy đổi {credits_to_spend:,} Credits → +{tokens_gained:,} AI Tokens (Tỷ lệ 1 Cr = {AI_TOKENS_PER_CREDIT:,} Tokens)"
            )

            return {
                "success": True,
                "credits_spent": credits_to_spend,
                "tokens_gained": tokens_gained,
                "credits_remaining": new_credits,
                "free_tokens_remaining": u["ai_free_tokens"] or 0,
                "paid_tokens_remaining": new_paid,
                "total_tokens": (u["ai_free_tokens"] or 0) + new_paid,
                "message": f"Đã đổi thành công {credits_to_spend:,} Credits lấy +{tokens_gained:,} AI Tokens!"
            }
    finally:
        conn.close()


def record_ai_copilot_usage(user_id: int) -> dict:
    """
    Backward-compat wrapper: Chuyển tiếp sang hệ thống Token mới.
    Mỗi lần gọi tương đương với 1 tin nhắn ngắn (~100 tokens).
    """
    return deduct_ai_tokens(
        user_id,
        tokens_needed=100,
        action_type="AI_CHAT_LEGACY",
        description="Chat AI Copilot (legacy usage)"
    )


def deduct_credit(user_id: int, count: int = 1):
    """Legacy helper fallback - trừ credit và ghi ledger"""
    conn = get_db()
    try:
        with conn:
            u = conn.execute("SELECT role, credits FROM users WHERE id = ?", (user_id,)).fetchone()
            if u and u["role"] not in ("owner", "admin"):
                conn.execute("UPDATE users SET credits = MAX(0, credits - ?) WHERE id = ?", (count, user_id))
                record_credit_ledger(conn, user_id, -count, "MANUAL_CHECK", f"Trừ {count} Credit lượt check đơn lẻ")
    finally:
        conn.close()


def add_credits(user_id: int, count: int, reason: str = "Nạp thủ công"):
    conn = get_db()
    try:
        with conn:
            conn.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (count, user_id))
            record_credit_ledger(conn, user_id, count, "ADMIN_ADJUST", reason)
    finally:
        conn.close()


def get_user_credit_history(user_id: int, limit: int = 50) -> list:
    """Lấy danh sách sao kê biến động số dư cho người dùng"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT id, amount, balance_before, balance_after, action_type, description, created_at
            FROM credit_transactions
            WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_admin_audit(admin_id: int, target_id: int, action: str, details: str, ip_address: str = ""):
    """Ghi nhật ký thanh tra quản trị và các hành vi an ninh"""
    conn = get_db()
    try:
        now = int(time.time())
        with conn:
            conn.execute("""
                INSERT INTO admin_audit_logs (admin_id, target_id, action, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (admin_id, target_id, action, details, ip_address, now))
    finally:
        conn.close()


def get_admin_audit_logs(limit: int = 50) -> list:
    """Lấy danh sách nhật ký thanh tra an ninh cho Root Owner / Admin Panel"""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT a.*, u.username as admin_name, t.username as target_name
            FROM admin_audit_logs a
            LEFT JOIN users u ON a.admin_id = u.id
            LEFT JOIN users t ON a.target_id = t.id
            ORDER BY a.id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
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
                "DELETE FROM api_keys WHERE user_id = ? AND api_key = ?",
                (user_id, api_key.strip())
            )
            if cur.rowcount == 0:
                conn.execute(
                    "DELETE FROM api_keys WHERE api_key = ?",
                    (api_key.strip(),)
                )
        return {"success": True, "status": "ok", "message": "Đã xóa API Key vĩnh viễn khỏi tài khoản"}
    finally:
        conn.close()


def get_user_keys(user_id: int) -> list:
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, api_key, name, status, requests_count, created_at FROM api_keys WHERE user_id = ? AND status != 'revoked' ORDER BY id DESC", (user_id,)).fetchall()
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


def admin_update_role(requester_id: int, target_user_id: int, new_role: str, client_ip: str = "") -> dict:
    """Promote or Demote roles. ONLY ROOT OWNER can do this. Security trap enabled."""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()

        # BẪY AN NINH: Không để lộ logic 'Chỉ Root Owner...'
        if not req or req["role"] != "owner":
            # Log security violation using same connection
            now = int(time.time())
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO admin_audit_logs (admin_id, target_id, action, details, ip_address, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (requester_id, target_user_id,
                          "SECURITY_VIOLATION_ESCALATION",
                          f"Cố tình can thiệp thăng cấp quyền lên [{new_role}] cho user_id={target_user_id}",
                          client_ip, now))
            except Exception:
                pass
            return {
                "success": False,
                "error": "[CẢNH BÁO HỆ THỐNG] Phát hiện hành vi bất thường và can thiệp trái phép! Địa chỉ IP và định danh của bạn đã được ghi nhận vào nhật ký thanh tra an ninh.",
                "security_violation": True
            }

        if target_user_id == requester_id:
            return {"success": False, "error": "Không thể tự thay đổi quyền của chính Root Owner!"}

        if new_role not in ("admin", "user"):
            return {"success": False, "error": "Quyền không hợp lệ (chỉ được cấp admin hoặc user)!"}

        target = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if not target:
            return {"success": False, "error": "Không tìm thấy người dùng!"}

        now = int(time.time())
        with conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_user_id))
            conn.execute("""
                INSERT INTO admin_audit_logs (admin_id, target_id, action, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (requester_id, target_user_id,
                  "ROLE_CHANGE",
                  f"Root Owner đã đổi quyền của {target['username']} thành [{new_role.upper()}]",
                  client_ip, now))

        return {
            "success": True,
            "message": f"Đã cập nhật quyền của {target['username']} thành [{new_role.upper()}]!"
        }
    finally:
        conn.close()


def admin_ban_user(requester_id: int, target_user_id: int, reason: str = "Vi phạm quy tắc hệ thống", client_ip: str = "") -> dict:
    """Khóa tài khoản người dùng"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {
                "success": False,
                "error": "[CẢNH BÁO HỆ THỐNG] Phát hiện hành vi bất thường và can thiệp trái phép! Hành vi đã được ghi nhận.",
                "security_violation": True
            }

        target = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if not target:
            return {"success": False, "error": "Không tìm thấy người dùng!"}
        if target["role"] == "owner":
            return {"success": False, "error": "Không thể khóa tài khoản Root Owner tối cao!"}

        now = int(time.time())
        with conn:
            conn.execute("UPDATE users SET is_banned = 1, ban_reason = ? WHERE id = ?", (reason, target_user_id))
            conn.execute("""
                INSERT INTO admin_audit_logs (admin_id, target_id, action, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (requester_id, target_user_id, "BAN_USER",
                  f"Đã khóa tài khoản {target['username']}. Lý do: {reason}",
                  client_ip, now))

        return {"success": True, "message": f"Đã khóa vĩnh viễn tài khoản [{target['username']}] thành công!"}
    finally:
        conn.close()


def admin_unban_user(requester_id: int, target_user_id: int, client_ip: str = "") -> dict:
    """Mở khóa tài khoản người dùng"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] not in ("owner", "admin"):
            return {
                "success": False,
                "error": "[CẢNH BÁO HỆ THỐNG] Phát hiện hành vi bất thường và can thiệp trái phép!",
                "security_violation": True
            }

        target = conn.execute("SELECT id, username FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if not target:
            return {"success": False, "error": "Không tìm thấy người dùng!"}

        now = int(time.time())
        with conn:
            conn.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE id = ?", (target_user_id,))
            conn.execute("""
                INSERT INTO admin_audit_logs (admin_id, target_id, action, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (requester_id, target_user_id, "UNBAN_USER",
                  f"?? mở khóa tài khoản {target['username']}",
                  client_ip, now))

        return {"success": True, "message": f"Đã mở khóa thành công cho tài khoản [{target['username']}]!"}
    finally:
        conn.close()


def admin_set_user_tier(requester_id: int, target_user_id: int, tier: str, client_ip: str = "") -> dict:
    """Cấp gói thành viên (free, pro, vip_unlimited)"""
    conn = get_db()
    try:
        req = conn.execute("SELECT role FROM users WHERE id = ?", (requester_id,)).fetchone()
        if not req or req["role"] != "owner":
            return {
                "success": False,
                "error": "[CẢNH BÁO HỆ THỐNG] Phát hiện hành vi bất thường và can thiệp trái phép!",
                "security_violation": True
            }

        valid_tiers = ("free", "pro", "vip_unlimited")
        if tier not in valid_tiers:
            return {"success": False, "error": "Gói không hợp lệ (free, pro, vip_unlimited)"}

        target = conn.execute("SELECT id, username FROM users WHERE id = ?", (target_user_id,)).fetchone()
        if not target:
            return {"success": False, "error": "Không tìm thấy người dùng!"}

        now = int(time.time())
        with conn:
            conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, target_user_id))
            conn.execute("""
                INSERT INTO admin_audit_logs (admin_id, target_id, action, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (requester_id, target_user_id, "SET_TIER",
                  f"Cấp gói [{tier.upper()}] cho {target['username']}",
                  client_ip, now))

        return {"success": True, "message": f"Đã cập nhật gói thành viên của {target['username']} thành [{tier.upper()}]!"}
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

