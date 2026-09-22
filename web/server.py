"""
Web Server for Lien Quan Checker - SaaS & Developer REST API Edition
Includes:
- User Authentication (Register / Login / Profile / Giftcodes)
- API Key Service (Generate / Revoke / Validate / Deduct Credits)
- External Developer REST API:
    * POST /api/v1/check (Header: Authorization: Bearer <API_KEY>)
    * POST /api/v1/check-batch (Batch processing via Developer API)
    * GET /api/v1/me & GET /api/v1/user/me
- Web Dashboard, Check History & Live Monospace Batch Stream
"""
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Auto-load .env file if present
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_dotenv()

from core.aov_engine import check_account, parse_combo_line, format_account_full_info
from core.captcha import verify_google_recaptcha, generate_adaptive_challenge, GOOGLE_RECAPTCHA_SITE_KEY
from core.ai_copilot import chat_with_copilot
from core.db import (
    init_db, register_user, login_user, get_user_profile,
    validate_api_key, deduct_credit, add_credits,
    generate_new_api_key, revoke_api_key, get_user_keys,
    save_check_history, get_user_history, clear_user_history,
    redeem_giftcode, admin_get_all_users, admin_adjust_credits,
    admin_update_role, admin_list_giftcodes, admin_create_giftcode,
    admin_delete_giftcode, update_user_profile,
    verify_session_token, deduct_check_credits, record_ai_copilot_usage,
    get_user_credit_history, get_admin_audit_logs, admin_ban_user,
    admin_unban_user, admin_set_user_tier, log_admin_audit,
    estimate_ai_tokens, deduct_ai_tokens, convert_credits_to_tokens,
    AI_TOKENS_PER_CREDIT, AI_FREE_TOKENS_INITIAL,
    sync_from_supabase_cloud
)

# Initialize Database on server start
init_db()
# Pull persistent cloud state from Supabase (critical on Render - ephemeral filesystem)
# Ensures all users/giftcodes survive deploys and container restarts
try:
    sync_from_supabase_cloud()
except Exception as _sync_err:
    print(f"[WARN] Supabase sync failed on startup: {_sync_err}", flush=True)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# In-memory batch tasks
_TASKS = {}
_TASKS_LOCK = threading.Lock()

# Upload sessions for large (MB/GB) files
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)
_UPLOAD_SESSIONS = {}
_UPLOAD_LOCK = threading.Lock()


def enrich_account_result(r: dict) -> dict:
    if not isinstance(r, dict):
        return r
    aov_data = r.get("aov") or {}
    sec_data = r.get("security") or {}
    r["hero_count"] = aov_data.get("total_champs", 0)
    r["skin_count"] = aov_data.get("total_skins", 0)
    r["rank"] = aov_data.get("rank", "Chưa Đấu Hạng")
    r["ingame"] = aov_data.get("name", "")
    r["level"] = aov_data.get("level", 0)
    r["ss_count"] = aov_data.get("ss_count", 0)
    r["ss_list"] = aov_data.get("ss_list", [])
    r["sss_count"] = aov_data.get("sss_count", 0)
    r["sss_list"] = aov_data.get("sss_list", [])
    r["anime_count"] = aov_data.get("anime_count", 0)
    r["anime_list"] = aov_data.get("anime_list", [])
    r["other_count"] = aov_data.get("other_count", 0)
    r["other_list"] = aov_data.get("other_list", [])
    r["is_vip"] = bool(r["sss_count"] > 0 or r["ss_count"] > 0 or r["anime_count"] > 0)
    
    # Pre-format security strings
    masked_phone = (sec_data.get("masked_phone") or "").strip()
    has_phone = bool(sec_data.get("has_phone")) or bool(sec_data.get("mobile_bound"))
    if masked_phone and masked_phone != "Trắng":
        r["sdt_str"] = f"YES [{masked_phone}]"
    elif has_phone:
        r["sdt_str"] = "YES [ĐÃ LIÊN KẾT]"
    else:
        r["sdt_str"] = "NO"

    masked_email = (sec_data.get("masked_email") or "").strip()
    email_verified = sec_data.get("email_v", False)
    if not masked_email or masked_email == "Trắng":
        r["email_str"] = "NO [CHƯA LIÊN KẾT]"
    elif email_verified:
        r["email_str"] = f"YES [{masked_email} - ĐÃ XÁC THỰC]"
    else:
        r["email_str"] = f"NO [{masked_email} - CHƯA XÁC THỰC]"

    idcard = (sec_data.get("idcard") or "").strip()
    if sec_data.get("has_cccd"):
        r["cmnd_str"] = f"YES [{idcard}]" if idcard and idcard.replace("*", "").strip() else "YES"
    else:
        r["cmnd_str"] = "NO"

    r["authen_str"] = "YES" if sec_data.get("auth_2fa") else "NO"

    fb_uid = (sec_data.get("fb_uid") or "").strip()
    if sec_data.get("fb_linked"):
        r["fb_str"] = f"YES [{fb_uid}]" if fb_uid else "YES"
    else:
        r["fb_str"] = "DIE"

    r["full_line"] = r.get("full_info") or format_account_full_info(r)
    return r


class AOVWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress verbose terminal logs
        return

    def _send_json(self, data: dict, status: int = 200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            print(f"[SEND_JSON_WARN] {e}", flush=True)

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
        except Exception:
            pass

    def _get_client_ip(self) -> str:
        fwd = self.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
        real_ip = self.headers.get("X-Real-IP", "")
        if real_ip:
            return real_ip.strip()
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def _get_auth_session(self, payload: dict = None) -> dict:
        """Trích xuất và verify HMAC session token bảo mật tuyệt đối"""
        auth = self.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
        elif auth.startswith("Session "):
            token = auth[8:].strip()
        elif self.headers.get("X-Session-Token"):
            token = self.headers.get("X-Session-Token").strip()
        elif payload and isinstance(payload, dict):
            token = str(payload.get("session_token") or payload.get("token") or "").strip()

        if not token:
            return {"valid": False, "error": "Thiếu Session Token xác thực"}
        return verify_session_token(token)

    def _get_api_key_from_request(self) -> str:
        # Check Authorization: Bearer <key>
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        if auth.startswith("Token "):
            return auth[6:].strip()
        # Check query string ?key=... or ?api_key=...
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if "key" in qs:
            return qs["key"][0].strip()
        if "api_key" in qs:
            return qs["api_key"][0].strip()
        return ""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # ── 1. Developer REST API: Check API Key status & balance ─────────────
        if path in ("/api/v1/me", "/api/v1/user/me", "/api/user/me"):
            api_key = self._get_api_key_from_request()
            uid = query.get("user_id", [""])[0]
            if api_key:
                v = validate_api_key(api_key)
                if not v["valid"]:
                    self._send_json({"success": False, "error": v["error"]}, 401)
                    return
                self._send_json({
                    "success": True,
                    "status": "ok",
                    "user": {
                        "id": v["user_id"],
                        "username": v["username"],
                        "credits": v["credits"],
                        "role": v["role"]
                    }
                })
                return
            elif uid and uid.isdigit():
                prof = get_user_profile(int(uid))
                self._send_json(prof, 200 if prof["success"] else 404)
                return
            else:
                self._send_json({"success": False, "error": "Thiếu Authorization header hoặc user_id"}, 401)
                return

        # ── 2. Get User Keys ──────────────────────────────────────────────────
        if path in ("/api/user/keys", "/api/keys/list"):
            uid = query.get("user_id", [""])[0]
            if not uid or not uid.isdigit():
                # Check via api_key
                api_key = self._get_api_key_from_request()
                if api_key:
                    v = validate_api_key(api_key)
                    if v["valid"]:
                        uid = str(v["user_id"])
            if not uid or not uid.isdigit():
                self._send_json({"success": False, "error": "Thiếu user_id hợp lệ"}, 400)
                return
            keys = get_user_keys(int(uid))
            self._send_json({"success": True, "status": "ok", "keys": keys})
            return

        # ── 2b. Admin / Owner Overview ─────────────────────────────────────────
        if path == "/api/admin/overview":
            uid = query.get("user_id", [""])[0]
            if not uid or not uid.isdigit():
                self._send_json({"success": False, "error": "Thiếu user_id"}, 400)
                return
            users_res = admin_get_all_users(int(uid))
            if not users_res.get("success"):
                self._send_json(users_res, 403)
                return
            giftcodes_res = admin_list_giftcodes(int(uid))
            users_list = users_res.get("users", [])
            total_credits = sum(u.get("credits", 0) for u in users_list)
            self._send_json({
                "success": True,
                "overview": {
                    "total_users": len(users_list),
                    "total_credits": total_credits,
                    "users": users_list,
                    "giftcodes": giftcodes_res.get("giftcodes", [])
                }
            })
            return

        # ── 3. Check History API ──────────────────────────────────────────────
        if path == "/api/user/history":
            uid = query.get("user_id", [""])[0]
            if not uid or not uid.isdigit():
                self._send_json({"success": False, "error": "Thiếu user_id hợp lệ"}, 400)
                return
            limit = int(query.get("limit", [200])[0])
            status_filter = query.get("status", [""])[0] or None
            history = get_user_history(int(uid), limit=limit, filter_status=status_filter)
            self._send_json({"success": True, "status": "ok", "history": history, "total": len(history)})
            return

        # ── 3b. User Credit Ledger / History ──────────────────────────────────
        if path == "/api/user/credit-history":
            uid = query.get("user_id", [""])[0]
            if not uid or not uid.isdigit():
                self._send_json({"success": False, "error": "Thiếu user_id hợp lệ"}, 400)
                return
            limit = int(query.get("limit", [50])[0])
            ledger = get_user_credit_history(int(uid), limit=limit)
            self._send_json({"success": True, "ledger": ledger, "total": len(ledger)})
            return

        # ── 3c. Admin Audit & Security Logs ───────────────────────────────────
        if path == "/api/admin/audit-logs":
            uid = query.get("user_id", [""])[0]
            if not uid or not uid.isdigit():
                self._send_json({"success": False, "error": "Thiếu user_id"}, 400)
                return
            # Chỉ Owner hoặc Admin mới được xem nhật ký
            users_res = admin_get_all_users(int(uid))
            if not users_res.get("success"):
                self._send_json(users_res, 403)
                return
            limit = int(query.get("limit", [50])[0])
            logs = get_admin_audit_logs(limit=limit)
            self._send_json({"success": True, "logs": logs})
            return

        # ── 4. Web Batch Task Status ──────────────────────────────────────────
        if path in ("/api/task-status", "/api/batch/status", "/api/task/status"):
            task_id = query.get("task_id", [""])[0] or query.get("id", [""])[0]
            offset = int(query.get("offset", [0])[0] or 0)
            with _TASKS_LOCK:
                task = _TASKS.get(task_id)
                if not task:
                    self._send_json({"error": f"Task '{task_id}' not found"}, 404)
                    return
                all_res = task["results"]
                new_slice = all_res[offset:] if offset < len(all_res) else []
                is_running = bool(task.get("is_running", False))
                should_stop = bool(task.get("should_stop", False))
                total = int(task.get("total", 0) or 0)
                done = int(task.get("done", 0) or 0)

                # is_done is True only if explicitly stopped, or all items finished, or worker thread completed
                is_done = should_stop or (done >= total and total > 0) or (not is_running)
                status_text = "STOPPED" if should_stop else ("DONE" if is_done else "RUNNING")

                start_ts = task.get("start_time") or time.time()
                end_ts = task.get("end_time") or (time.time() if not is_done else time.time())
                if is_done and not task.get("end_time"):
                    task["end_time"] = time.time()
                    end_ts = task["end_time"]

                elapsed_sec = max(0.1, (end_ts - start_ts) if is_done else (time.time() - start_ts))
                speed = round(done / elapsed_sec, 2) if elapsed_sec > 0 else 0.0

                # Check if client requested RAM-Offloading Stream (offset > 0 or stream=true)
                # In streaming mode, server only returns new_slice and summary, letting client store all accounts
                client_stream = bool(query.get("stream", ["0"])[0] in ("1", "true") or offset > 0)

                resp_data = {
                    "task_id": task_id,
                    "total": total,
                    "done": done,
                    "progress": done,
                    "hits": task.get("hits", 0),
                    "trang": task.get("trang", 0),
                    "invalid": task.get("invalid", 0),
                    "is_running": is_running and not should_stop,
                    "is_done": is_done,
                    "was_stopped": should_stop,
                    "elapsed_sec": round(elapsed_sec, 1),
                    "speed": speed,
                    "status": status_text,
                    "results": [] if client_stream else all_res,
                    "new_results": new_slice,
                    "all_hits_count": len(task.get("all_hits", [])),
                    "next_offset": len(all_res),
                }

                # RAM Offload: If client has confirmed receiving up to offset and task is done or large,
                # we retain only the last 100 items on server to prevent server memory bloat
                purge_server = query.get("purge", ["0"])[0] in ("1", "true")
                if purge_server and offset > 200 and len(all_res) > 300:
                    pass
            self._send_json(resp_data)
            return

        # ── 5. Captcha Challenge Endpoint (Google reCAPTCHA v2 + Adaptive) ────
        if path == "/api/captcha/new":
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            challenge = generate_adaptive_challenge(client_ip)
            self._send_json({"success": True, "challenge": challenge, "site_key": challenge["site_key"]})
            return

        # ── 6. Admin User Directory ───────────────────────────────────────────
        if path == "/api/admin/users":
            raw_uid = query.get("user_id", ["0"])[0]
            requester_id = int(raw_uid) if raw_uid.isdigit() else 0
            res = admin_get_all_users(requester_id)
            self._send_json(res, 200 if res.get("success") else 403)
            return

        # ── 7. Admin Giftcode Directory ───────────────────────────────────────
        if path == "/api/admin/giftcodes":
            raw_uid = query.get("user_id", ["0"])[0]
            requester_id = int(raw_uid) if raw_uid.isdigit() else 0
            res = admin_list_giftcodes(requester_id)
            self._send_json(res, 200 if res.get("success") else 403)
            return

        # ── 8. Static Files Serving ───────────────────────────────────────────
        if path in ("/", "/index.html"):
            file_path = os.path.join(STATIC_DIR, "index.html")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            mime, _ = mimetypes.guess_type(file_path)
            mime = mime or "application/octet-stream"
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8" if "text" in mime or "javascript" in mime else mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception:
            payload = {}

        # ── 1. AUTH: REGISTER ─────────────────────────────────────────────────
        if path in ("/api/auth/register", "/api/register"):
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", "")).strip()
            
            # Verify Google reCAPTCHA
            recaptcha_token = payload.get("recaptcha_response") or payload.get("captcha_token", "")
            client_ip = self.client_address[0] if self.client_address else ""

            if not recaptcha_token:
                self._send_json({"success": False, "error": "Vui lòng xác minh Google Captcha (Tôi không phải là người máy)!"}, 400)
                return

            if not verify_google_recaptcha(recaptcha_token, client_ip):
                self._send_json({"success": False, "error": "Xác thực Google Captcha thất bại hoặc nghi vấn bot! Vui lòng thử lại."}, 400)
                return

            res = register_user(username, password)
            status_code = 200 if res["success"] else 400
            self._send_json(res, status_code)
            return

        # ── 2. AUTH: LOGIN ────────────────────────────────────────────────────
        if path in ("/api/auth/login", "/api/login"):
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", "")).strip()

            # Verify Google reCAPTCHA on login
            recaptcha_token = payload.get("recaptcha_response") or payload.get("captcha_token", "")
            client_ip = self.client_address[0] if self.client_address else ""

            if not recaptcha_token:
                self._send_json({"success": False, "error": "Vui lòng xác minh Google Captcha trước khi đăng nhập!"}, 400)
                return

            if not verify_google_recaptcha(recaptcha_token, client_ip):
                self._send_json({"success": False, "error": "Xác thực Google Captcha không thành công! Vui lòng thử lại."}, 400)
                return

            res = login_user(username, password)
            status_code = 200 if res["success"] else 401
            self._send_json(res, status_code)
            return

        # ── 3. API KEYS: CREATE NEW KEY ───────────────────────────────────────
        if path in ("/api/keys/generate", "/api/keys/create"):
            uid = payload.get("user_id")
            name = payload.get("name", "Default Key")
            if not uid:
                self._send_json({"success": False, "error": "Thiếu user_id"}, 400)
                return
            res = generate_new_api_key(int(uid), name)
            self._send_json(res)
            return

        # ── 4. API KEYS: REVOKE KEY ───────────────────────────────────────────
        if path in ("/api/keys/revoke", "/api/keys/delete"):
            uid = payload.get("user_id")
            key_val = payload.get("api_key") or payload.get("key")
            if not uid or not key_val:
                self._send_json({"success": False, "error": "Thiếu user_id hoặc api_key"}, 400)
                return
            res = revoke_api_key(int(uid), str(key_val))
            self._send_json(res)
            return

        # ── 5. USER: REDEEM GIFTCODE ──────────────────────────────────────────
        if path in ("/api/user/redeem", "/api/redeem"):
            uid = payload.get("user_id")
            code = payload.get("code", "").strip()
            if not uid or not code:
                self._send_json({"success": False, "error": "Thiếu user_id hoặc mã Giftcode"}, 400)
                return
            res = redeem_giftcode(int(uid), code)
            status_code = 200 if res["success"] else 400
            self._send_json(res, status_code)
            return

        # ── 6. USER: CLEAR HISTORY ────────────────────────────────────────────
        if path in ("/api/user/history/clear", "/api/history/clear"):
            uid = payload.get("user_id")
            if not uid:
                self._send_json({"success": False, "error": "Thiếu user_id"}, 400)
                return
            res = clear_user_history(int(uid))
            self._send_json(res)
            return

        # ── 6b. USER: UPDATE PROFILE (Avatar, Display Name, Email) ───────────
        if path in ("/api/user/profile/update", "/api/profile/update"):
            uid = payload.get("user_id")
            if not uid:
                self._send_json({"success": False, "error": "Thiếu user_id"}, 400)
                return
            display_name = payload.get("display_name")
            avatar_url = payload.get("avatar_url")
            email = payload.get("email")
            res = update_user_profile(int(uid), display_name=display_name, avatar_url=avatar_url, email=email)
            status_code = 200 if res["success"] else 400
            self._send_json(res, status_code)
            return

        # ── 6c. ADMIN / OWNER: ADJUST USER CREDITS ───────────────────────────
        if path == "/api/admin/users/credits":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            target_id = payload.get("target_user_id")
            amount = payload.get("amount", 0)
            if not req_id or not target_id:
                self._send_json({"success": False, "error": "Thiếu thông tin người yêu cầu hoặc mục tiêu"}, 400)
                return
            res = admin_adjust_credits(int(req_id), int(target_id), int(amount))
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 6d. ADMIN / OWNER: UPDATE USER ROLE (SECURITY TRAP ACTIVE) ───────
        if path == "/api/admin/users/role":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            target_id = payload.get("target_user_id")
            new_role = payload.get("new_role", "").strip().lower()
            client_ip = self._get_client_ip()

            if not req_id or not target_id or not new_role:
                self._send_json({"success": False, "error": "Thiếu thông tin phân quyền"}, 400)
                return
            res = admin_update_role(int(req_id), int(target_id), new_role, client_ip=client_ip)
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 6d.1 ADMIN / OWNER: BAN USER ─────────────────────────────────────
        if path == "/api/admin/users/ban":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            target_id = payload.get("target_user_id")
            reason = payload.get("reason", "Vi phạm điều khoản dịch vụ")
            client_ip = self._get_client_ip()

            if not req_id or not target_id:
                self._send_json({"success": False, "error": "Thiếu thông tin mục tiêu khóa"}, 400)
                return
            res = admin_ban_user(int(req_id), int(target_id), reason=reason, client_ip=client_ip)
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 6d.2 ADMIN / OWNER: UNBAN USER ───────────────────────────────────
        if path == "/api/admin/users/unban":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            target_id = payload.get("target_user_id")
            client_ip = self._get_client_ip()

            if not req_id or not target_id:
                self._send_json({"success": False, "error": "Thiếu thông tin mục tiêu mở khóa"}, 400)
                return
            res = admin_unban_user(int(req_id), int(target_id), client_ip=client_ip)
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 6d.3 ROOT OWNER: SET USER TIER (FREE / PRO / VIP_UNLIMITED) ──────
        if path == "/api/admin/users/tier":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            target_id = payload.get("target_user_id")
            tier = payload.get("tier", "free").strip().lower()
            client_ip = self._get_client_ip()

            if not req_id or not target_id:
                self._send_json({"success": False, "error": "Thiếu thông tin cấp gói"}, 400)
                return
            res = admin_set_user_tier(int(req_id), int(target_id), tier, client_ip=client_ip)
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 6e. ADMIN / OWNER: CREATE GIFTCODE ───────────────────────────────
        if path == "/api/admin/giftcodes/create":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            code = payload.get("code", "")
            credits_val = payload.get("credits", 0)
            max_uses = payload.get("max_uses", 1)
            if not req_id or not code or credits_val <= 0:
                self._send_json({"success": False, "error": "Dữ liệu giftcode không hợp lệ"}, 400)
                return
            res = admin_create_giftcode(int(req_id), code, int(credits_val), int(max_uses))
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 6f. ADMIN / OWNER: DELETE GIFTCODE ───────────────────────────────
        if path == "/api/admin/giftcodes/delete":
            auth = self._get_auth_session(payload)
            req_id = auth["user_id"] if auth.get("valid") else payload.get("requester_id")
            code = payload.get("code", "")
            if not req_id or not code:
                self._send_json({"success": False, "error": "Thiếu thông tin xóa giftcode"}, 400)
                return
            res = admin_delete_giftcode(int(req_id), code)
            status_code = 200 if res["success"] else 403
            self._send_json(res, status_code)
            return

        # ── 7. DEVELOPER REST API: CHECK SINGLE (/api/v1/check) ───────────────
        if path == "/api/v1/check":
            api_key = self._get_api_key_from_request() or payload.get("api_key", "")
            val = validate_api_key(api_key)
            if not val["valid"]:
                self._send_json({"success": False, "error": val["error"]}, 401)
                return

            acc = payload.get("account", "").strip()
            pwd = payload.get("password", "").strip()

            # Support "acc:pwd" single combo inside account field
            if acc and not pwd:
                u, p = parse_combo_line(acc)
                if u and p:
                    acc, pwd = u, p

            if not acc or not pwd:
                self._send_json({"success": False, "error": "Vui lòng nhập account và password (hoặc account:password)!"}, 400)
                return

            res = check_account(acc, pwd)
            deduct_credit(val["user_id"], 1)

            # Save to history
            save_check_history(val["user_id"], f"{acc}:{pwd}", res.get("status", "FAIL"), res)

            if res.get("status") == "HIT":
                print(f"[REST API v1] [{val['username']}] {format_account_full_info(res)}", flush=True)
            else:
                print(f"[REST API v1] [{val['username']}] {acc}:{pwd} | {res.get('status')}", flush=True)

            self._send_json({
                "success": True,
                "status": "ok",
                "formatted": format_account_full_info(res),
                "credits_remaining": max(0, val["credits"] - 1),
                "data": res
            })
            return

        # ── 8. DEVELOPER REST API: CHECK BATCH (/api/v1/check-batch) ──────────
        if path == "/api/v1/check-batch":
            api_key = self._get_api_key_from_request() or payload.get("api_key", "")
            val = validate_api_key(api_key)
            if not val["valid"]:
                self._send_json({"success": False, "error": val["error"]}, 401)
                return

            combos_raw = payload.get("combos", [])
            threads = int(payload.get("threads", 10) or 10)
            threads = max(1, min(threads, 500))

            combos = []
            for item in combos_raw:
                u, p = parse_combo_line(str(item))
                if u and p:
                    combos.append((u, p))

            if not combos:
                self._send_json({"success": False, "error": "Danh sách combos trống hoặc sai định dạng!"}, 400)
                return

            # Check if user has enough credits
            if val["role"] != "admin" and val["credits"] < len(combos):
                self._send_json({
                    "success": False,
                    "error": f"Không đủ Credits! Cần {len(combos)} Credits nhưng bạn chỉ còn {val['credits']} Credits."
                }, 402)
                return

            task_id = str(uuid.uuid4())[:8]
            task_state = {
                "total": len(combos),
                "done": 0,
                "hits": 0,
                "trang": 0,
                "invalid": 0,
                "is_running": True,
                "results": [],
                "all_hits": [],
            }

            with _TASKS_LOCK:
                _TASKS[task_id] = task_state

            # Launch background worker thread
            def run_api_batch():
                def check_worker(pair):
                    a, p = pair
                    r = check_account(a, p)
                    with _TASKS_LOCK:
                        task_state["done"] += 1
                        task_state["results"].append(r)
                        if r["status"] == "HIT":
                            task_state["hits"] += 1
                            task_state["all_hits"].append(r)
                            if r.get("is_trang"):
                                task_state["trang"] += 1
                        else:
                            if r["status"] == "INVALID":
                                task_state["invalid"] += 1

                    # Save history
                    save_check_history(val["user_id"], f"{a}:{p}", r.get("status", "FAIL"), r)

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    executor.map(check_worker, combos)

                with _TASKS_LOCK:
                    task_state["is_running"] = False

                deduct_credit(val["user_id"], len(combos))

            threading.Thread(target=run_api_batch, daemon=True).start()
            self._send_json({
                "success": True,
                "status": "ok",
                "task_id": task_id,
                "total": len(combos),
                "threads": threads,
                "poll_url": f"/api/task-status?task_id={task_id}"
            })
            return

        # ── 9. WEB UI: CHECK SINGLE ───────────────────────────────────────────
        if path == "/api/check-single":
            acc = payload.get("account", "").strip()
            pwd = payload.get("password", "").strip()
            if not acc or not pwd:
                self._send_json({"error": "Vui lòng nhập tài khoản và mật khẩu"}, 400)
                return

            uid = payload.get("user_id")
            if uid:
                deduct_credit(int(uid), 1)

            res = enrich_account_result(check_account(acc, pwd))

            if uid:
                save_check_history(int(uid), f"{acc}:{pwd}", res.get("status", "FAIL"), res)

            if res.get("status") == "HIT":
                print(f"[WEB SINGLE] {format_account_full_info(res)}", flush=True)
            else:
                print(f"[WEB SINGLE] {acc}:{pwd} | STATUS : {res.get('status')} | DETAIL : {res.get('message', 'FAIL')}", flush=True)
            self._send_json(res)
            return

        # ── 10. WEB UI: CHECK BATCH ───────────────────────────────────────────
        elif path in ("/api/check-batch", "/api/batch/start", "/api/batch/check"):
            combos_raw = payload.get("combos", [])
            threads = int(payload.get("threads", 10) or 10)
            threads = max(1, min(threads, 500))
            uid = payload.get("user_id")
            client_id = str(payload.get("client_id") or uid or "default_client").strip()

            combos = []
            for item in combos_raw:
                u, p = parse_combo_line(str(item))
                if u and p:
                    combos.append((u, p))

            if not combos:
                self._send_json({"error": "Không có danh sách tài khoản hợp lệ (hỗ trợ : | ; / khoảng trắng)!"}, 400)
                return

            # Kiểm tra & Trừ Credit theo tỷ lệ 1 Credit = 10 Acc
            if uid:
                try:
                    c_res = deduct_check_credits(int(uid), len(combos), action_type="BATCH_TEXT_CHECK", description=f"Quét dán text {len(combos)} acc (Tỷ lệ 1 Cr = 10 Acc)")
                    if not c_res.get("success"):
                        self._send_json(c_res, 402)
                        return
                except Exception as c_err:
                    print(f"[BATCH CREDIT DEDUCT ERROR] {c_err}", flush=True)

            # Clean-up / hard stop any active task for this client
            with _TASKS_LOCK:
                for existing_tid, existing_t in list(_TASKS.items()):
                    if existing_t.get("client_id") == client_id and existing_t.get("is_running"):
                        existing_t["should_stop"] = True
                        existing_t["is_running"] = False
                        for fut in existing_t.get("futures", []):
                            if not fut.done():
                                fut.cancel()
                        print(f"[MUTEX] Đã hủy task cũ '{existing_tid}' của client '{client_id}' để chạy task mới.", flush=True)

            task_id = str(uuid.uuid4())[:8]

            task_state = {
                "client_id": client_id,
                "total": len(combos),
                "done": 0,
                "hits": 0,
                "trang": 0,
                "invalid": 0,
                "is_running": True,
                "should_stop": False,
                "start_time": time.time(),
                "end_time": None,
                "futures": [],
                "results": [],
                "all_hits": [],
            }

            with _TASKS_LOCK:
                _TASKS[task_id] = task_state

            # Launch background worker thread
            def run_batch():
                print(f"\n[BẮT ĐẦU CHECK BATCH {task_id}] Client: {client_id} | Tổng: {len(combos)} tài khoản | Luồng: {threads}", flush=True)

                def check_worker(pair):
                    if task_state.get("should_stop"):
                        return
                    a, p = pair
                    try:
                        r = enrich_account_result(check_account(a, p))
                    except Exception as err:
                        r = {
                            "account": a,
                            "password": p,
                            "status": "ERROR",
                            "message": f"Lỗi xử lý: {str(err)}",
                            "is_trang": False,
                            "is_vip": False,
                            "hero_count": 0,
                            "skin_count": 0,
                            "rank": "Chưa Đấu Hạng",
                            "sdt_str": "NO",
                            "email_str": "NO",
                            "cmnd_str": "NO",
                            "authen_str": "NO",
                            "fb_str": "DIE",
                            "full_line": f"{a}:{p} | STATUS : ERROR | DETAIL : {str(err)}"
                        }

                    with _TASKS_LOCK:
                        if task_state.get("should_stop"):
                            return
                        task_state["done"] += 1
                        task_state["results"].append(r)
                        done_str = f"[{task_state['done']}/{task_state['total']}]"
                        if r.get("status") == "HIT":
                            task_state["hits"] += 1
                            task_state["all_hits"].append(r)
                            full_line = r.get("full_line") or format_account_full_info(r)
                            if r.get("is_trang"):
                                task_state["trang"] += 1
                            print(f"{done_str} {full_line}", flush=True)
                        else:
                            if r.get("status") == "INVALID":
                                task_state["invalid"] += 1
                            print(f"{done_str} {a}:{p} | STATUS : {r.get('status')} | DETAIL : {r.get('message', 'FAIL')}", flush=True)

                    if uid:
                        try:
                            save_check_history(int(uid), f"{a}:{p}", r.get("status", "FAIL"), r)
                        except Exception:
                            pass

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    fut_list = []
                    for combo in combos:
                        if task_state.get("should_stop"):
                            break
                        f = executor.submit(check_worker, combo)
                        fut_list.append(f)
                    with _TASKS_LOCK:
                        task_state["futures"] = fut_list

                with _TASKS_LOCK:
                    task_state["is_running"] = False
                    if not task_state.get("end_time"):
                        task_state["end_time"] = time.time()

                if uid:
                    actual_checked = task_state.get("done", len(combos))
                    deduct_credit(int(uid), actual_checked)

                print(f"\n[KẾT THÚC BATCH {task_id}] Tổng: {task_state['done']}/{task_state['total']} | Sống: {task_state['hits']} | Trắng TTT: {task_state['trang']}\n", flush=True)

            threading.Thread(target=run_batch, daemon=True).start()
            self._send_json({"status": "ok", "success": True, "task_id": task_id, "total": len(combos)})
            return

        # ── 10.1 STOP RUNNING BATCH TASK ──────────────────────────────────────
        elif path in ("/api/batch/stop", "/api/task/stop"):
            req_tid = str(payload.get("task_id") or "").strip()
            client_id = str(payload.get("client_id") or "").strip()
            stopped = 0
            with _TASKS_LOCK:
                targets = []
                if req_tid and req_tid in _TASKS:
                    targets.append(_TASKS[req_tid])
                elif client_id:
                    targets = [t for t in _TASKS.values() if t.get("client_id") == client_id and t.get("is_running")]
                else:
                    targets = [t for t in _TASKS.values() if t.get("is_running")]

                for t in targets:
                    t["should_stop"] = True
                    t["is_running"] = False
                    t["end_time"] = time.time()
                    for f in t.get("futures", []):
                        if not f.done():
                            f.cancel()
                    stopped += 1

            print(f"[STOP BATCH] Đã dừng và hủy thành công {stopped} tiến trình quét!", flush=True)
            self._send_json({"success": True, "message": f"Đã dừng thành công {stopped} tiến trình quét!"})
            return

        # ── 10.5. STATELESS MINI-BATCH FOR CLIENT STREAMING (10GB+ FILES) ────
        elif path == "/api/check-mini-batch":
            combos_raw = payload.get("combos", [])
            threads = int(payload.get("threads", 15) or 15)
            threads = max(1, min(threads, 30))  # Capping to protect Render 512MB RAM
            uid = payload.get("user_id")

            if not isinstance(combos_raw, list) or not combos_raw:
                self._send_json({"error": "Danh sách combos trống!"}, 400)
                return

            # Hard cap: tối đa 100 acc mỗi mini-batch để triệt tiêu nguy cơ OOM
            if len(combos_raw) > 100:
                combos_raw = combos_raw[:100]

            valid_combos = []
            for item in combos_raw:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    u, p = str(item[0]).strip(), str(item[1]).strip()
                    if u and p:
                        valid_combos.append((u, p))
                elif isinstance(item, str):
                    u, p = parse_combo_line(item)
                    if u and p:
                        valid_combos.append((u, p))

            if not valid_combos:
                self._send_json({"error": "Không có combo hợp lệ!"}, 400)
                return

            # Thắt chặt Credit Ledger: 1 Credit = 10 Tài khoản!
            if uid:
                try:
                    c_res = deduct_check_credits(int(uid), len(valid_combos), action_type="STREAM_MINI_BATCH", description=f"Quét Stream {len(valid_combos)} acc (Tỷ lệ 1 Cr = 10 Acc)")
                    if not c_res.get("success"):
                        self._send_json(c_res, 402)
                        return
                except Exception as c_err:
                    print(f"[CREDIT DEDUCT ERROR] {c_err}", flush=True)

            results = []
            def mini_worker(pair):
                a, p = pair
                try:
                    r = enrich_account_result(check_account(a, p))
                except Exception as err:
                    r = {
                        "account": a,
                        "password": p,
                        "status": "ERROR",
                        "status_code": 999,
                        "message": f"Exception: {str(err)}",
                        "skins": 0, "heroes": 0, "rank": "Unknown",
                        "level": 0, "gold": 0, "ruby": 0, "vouchers": 0,
                        "skin_list": [], "raw_skins": [], "ingame_name": "", "raw_hero_ids": [],
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }

                # Lưu DB nếu có user_id và acc Live/Trắng
                if uid:
                    try:
                        st = r.get("status")
                        if st in ("LIVE", "LIVE_TRANG"):
                            insert_scanned_account(
                                user_id=uid,
                                username=r.get("account", a),
                                password=r.get("password", p),
                                status=st,
                                heroes=r.get("heroes", 0),
                                skins=r.get("skins", 0),
                                rank=r.get("rank", "Unknown"),
                                skin_list=",".join(r.get("skin_list", [])) if isinstance(r.get("skin_list"), list) else str(r.get("skin_list", "")),
                                level=r.get("level", 0),
                                gold=r.get("gold", 0),
                                ruby=r.get("ruby", 0),
                                vouchers=r.get("vouchers", 0),
                                ingame_name=r.get("ingame_name", ""),
                                full_info=json.dumps(r, ensure_ascii=False)
                            )
                    except Exception as db_err:
                        print(f"[MINI-BATCH DB ERROR] {db_err}", flush=True)

                return r

            with ThreadPoolExecutor(max_workers=min(threads, len(valid_combos))) as executor:
                results = list(executor.map(mini_worker, valid_combos))

            self._send_json({
                "success": True,
                "total": len(results),
                "results": results
            })
            return

        # ── 11. CHUNKED UPLOAD FOR LARGE (MB/GB) COMBO FILES ──────────────────
        elif path == "/api/upload-chunk":
            upload_id = str(payload.get("upload_id", "")).strip()
            chunk_data = payload.get("chunk", "")
            is_last = bool(payload.get("is_last", False))

            if not upload_id:
                upload_id = str(uuid.uuid4())[:12]

            temp_path = os.path.join(_UPLOAD_DIR, f"{upload_id}.tmp")

            try:
                with open(temp_path, "a", encoding="utf-8", errors="ignore") as f:
                    if chunk_data:
                        f.write(chunk_data)
            except Exception as e:
                self._send_json({"success": False, "error": f"Lỗi ghi chunk: {str(e)}"}, 500)
                return

            if is_last:
                # Count total lines efficiently without loading entire file to RAM
                total_valid = 0
                try:
                    with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            l = line.strip()
                            if l and not l.startswith("#") and any(sep in l for sep in (":", "|", ";", "\t", " ", "/")):
                                total_valid += 1
                except Exception:
                    total_valid = 0

                self._send_json({
                    "success": True,
                    "upload_id": upload_id,
                    "is_complete": True,
                    "total_valid": total_valid
                })
            else:
                self._send_json({
                    "success": True,
                    "upload_id": upload_id,
                    "is_complete": False
                })
            return

        # ── 12. RUN BATCH DIRECTLY FROM UPLOADED LARGE FILE ───────────────────
        elif path == "/api/check-uploaded-file":
            upload_id = str(payload.get("upload_id", "")).strip()
            threads = int(payload.get("threads", 10) or 10)
            threads = max(1, min(threads, 500))
            uid = payload.get("user_id")

            temp_path = os.path.join(_UPLOAD_DIR, f"{upload_id}.tmp")
            if not os.path.exists(temp_path):
                self._send_json({"error": "File tải lên không tồn tại hoặc đã bị xoá!"}, 404)
                return

            # Read combos generator-style or memory-efficient list
            combos = []
            try:
                with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        u, p = parse_combo_line(line)
                        if u and p:
                            combos.append((u, p))
            except Exception as e:
                self._send_json({"error": f"Lỗi đọc file: {str(e)}"}, 500)
                return

            if not combos:
                self._send_json({"error": "Không tìm thấy dòng tài khoản hợp lệ trong file!"}, 400)
                return

            task_id = str(uuid.uuid4())[:8]
            task_state = {
                "total": len(combos),
                "done": 0,
                "hits": 0,
                "trang": 0,
                "invalid": 0,
                "is_running": True,
                "should_stop": False,
                "start_time": time.time(),
                "end_time": None,
                "results": [],
                "all_hits": [],
            }

            with _TASKS_LOCK:
                _TASKS[task_id] = task_state

            def run_file_batch():
                os.makedirs("results", exist_ok=True)
                live_path = os.path.join("results", f"file_hits_{task_id}.txt")
                trang_path = os.path.join("results", f"file_trang_{task_id}.txt")

                print(f"\n[BẮT ĐẦU FILE BATCH {task_id}] File: {upload_id}.tmp | Tổng: {len(combos)} tài khoản | Luồng: {threads}", flush=True)

                def check_worker(pair):
                    if task_state.get("should_stop"):
                        return
                    a, p = pair
                    try:
                        r = enrich_account_result(check_account(a, p))
                    except Exception as err:
                        r = {
                            "account": a,
                            "password": p,
                            "status": "ERROR",
                            "message": f"Lỗi xử lý: {str(err)}",
                            "is_trang": False,
                            "is_vip": False,
                            "hero_count": 0,
                            "skin_count": 0,
                            "rank": "Chưa Đấu Hạng",
                            "sdt_str": "NO",
                            "email_str": "NO",
                            "cmnd_str": "NO",
                            "authen_str": "NO",
                            "fb_str": "DIE",
                            "full_line": f"{a}:{p} | STATUS : ERROR | DETAIL : {str(err)}"
                        }

                    with _TASKS_LOCK:
                        if task_state.get("should_stop"):
                            return
                        task_state["done"] += 1
                        task_state["results"].append(r)
                        done_str = f"[{task_state['done']}/{task_state['total']}]"
                        if r.get("status") == "HIT":
                            task_state["hits"] += 1
                            task_state["all_hits"].append(r)
                            full_line = r.get("full_line") or format_account_full_info(r)
                            if r.get("is_trang"):
                                task_state["trang"] += 1
                                try:
                                    with open(trang_path, "a", encoding="utf-8") as ft:
                                        ft.write(full_line + "\n")
                                except Exception:
                                    pass
                            try:
                                with open(live_path, "a", encoding="utf-8") as fh:
                                    fh.write(full_line + "\n")
                            except Exception:
                                pass
                            print(f"{done_str} {full_line}", flush=True)
                        else:
                            if r.get("status") == "INVALID":
                                task_state["invalid"] += 1
                            print(f"{done_str} {a}:{p} | STATUS : {r.get('status')} | DETAIL : {r.get('message', 'FAIL')}", flush=True)

                    if uid:
                        try:
                            save_check_history(int(uid), f"{a}:{p}", r.get("status", "FAIL"), r)
                        except Exception:
                            pass

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    fut_list = []
                    for combo in combos:
                        if task_state.get("should_stop"):
                            break
                        f = executor.submit(check_worker, combo)
                        fut_list.append(f)
                    with _TASKS_LOCK:
                        task_state["futures"] = fut_list

                with _TASKS_LOCK:
                    task_state["is_running"] = False
                    if not task_state.get("end_time"):
                        task_state["end_time"] = time.time()

                if uid:
                    actual_checked = task_state.get("done", len(combos))
                    deduct_credit(int(uid), actual_checked)

                # Clean up temp file
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

                print(f"\n[HOÀN THÀNH FILE BATCH {task_id}] Tổng: {task_state['done']}/{task_state['total']} | Sống: {task_state['hits']} | Trắng: {task_state['trang']} (File lưu tại results/)\n", flush=True)

            threading.Thread(target=run_file_batch, daemon=True).start()
            self._send_json({"task_id": task_id, "total": len(combos)})
            return

        # ── 13. AI STUDIO COPILOT RAG CHAT (/api/ai/chat) ─────────────────────
        elif path == "/api/ai/chat":
            user_msg = str(payload.get("message") or payload.get("prompt") or "").strip()
            user_name = str(payload.get("user_name") or payload.get("display_name") or "Tris").strip()
            user_id = payload.get("user_id")
            image_data = payload.get("image_data") or None    # base64 string
            file_data = payload.get("file_data") or None      # plaintext content
            file_name = payload.get("file_name") or None
            enable_search = bool(payload.get("enable_search") or payload.get("search"))
            enable_thinking = bool(payload.get("thinking") or payload.get("enable_thinking"))
            enable_deep_research = bool(payload.get("deep_research") or payload.get("enable_deep_research"))
            tokens_needed = 0

            if user_id:
                try:
                    user_id = int(user_id)
                    # Estimate token cost before executing
                    tokens_needed = estimate_ai_tokens(
                        message=user_msg,
                        has_image=bool(image_data),
                        file_content=file_data or "",
                        enable_search=enable_search,
                        enable_thinking=enable_thinking,
                        enable_deep_research=enable_deep_research,
                    )
                    quota = deduct_ai_tokens(
                        user_id, tokens_needed,
                        action_type="AI_CHAT_MULTIMODAL" if (image_data or file_data) else "AI_CHAT",
                        description=(
                            "Chat AI"
                            + (" + Vision" if image_data else "")
                            + (f" + File({file_name or '?'})" if file_data else "")
                            + (" + Search" if enable_search else "")
                            + f" [{tokens_needed:,} tokens]"
                        )
                    )
                    if not quota.get("success"):
                        # Token exhausted → send structured out_of_tokens response
                        err_payload = {
                            "success": False,
                            "out_of_tokens": quota.get("out_of_tokens", False),
                            "error": quota.get("error", "Hết AI Tokens"),
                            "reply": quota.get("error", "Hết AI Tokens"),
                            "remaining_tokens": quota.get("remaining_tokens", 0),
                            "credits_available": quota.get("credits_available", 0),
                            "rate_per_credit": quota.get("rate_per_credit", AI_TOKENS_PER_CREDIT),
                            "tokens_needed": quota.get("tokens_needed", tokens_needed),
                        }
                        self._send_json(err_payload, 402)
                        return
                except ValueError:
                    user_id = None

            history = payload.get("history", [])
            task_id = payload.get("task_id", "")

            batch_context = None
            if task_id:
                with _TASKS_LOCK:
                    t = _TASKS.get(task_id)
                    if t:
                        batch_context = {
                            "total": t.get("total", 0),
                            "hits": t.get("hits", 0),
                            "trang": t.get("trang", 0),
                            "recent_hits": t.get("all_hits", [])[-10:]
                        }

            res_data = chat_with_copilot(
                user_msg,
                history=history,
                batch_context=batch_context,
                user_name=user_name,
                enable_thinking=enable_thinking,
                enable_deep_research=enable_deep_research,
                user_id=user_id,
                image_data=image_data,
                file_data=file_data,
                file_name=file_name,
                enable_search=enable_search,
            )

            reply_text = res_data.get("reply") if isinstance(res_data, dict) else str(res_data)
            thought_text = res_data.get("thought") if isinstance(res_data, dict) else None
            account_result = res_data.get("account_result") if isinstance(res_data, dict) else None

            self._send_json({
                "success": True,
                "status": "ok",
                "reply": reply_text,
                "response": reply_text,
                "thought": thought_text,
                "account_result": account_result,
                "tokens_used": tokens_needed,
            })
            return

        # ── 14. ADMIN ACTIONS: ADJUST CREDITS ─────────────────────────────────
        elif path == "/api/admin/adjust-credits":
            requester_id = int(payload.get("requester_id", 0))
            target_id = int(payload.get("target_id", 0))
            amount = int(payload.get("amount", 0))
            res = admin_adjust_credits(requester_id, target_id, amount)
            self._send_json(res, 200 if res["success"] else 400)
            return

        # ── 15. ADMIN ACTIONS: UPDATE ROLE (OWNER ONLY) ───────────────────────
        elif path == "/api/admin/update-role":
            requester_id = int(payload.get("requester_id", 0))
            target_id = int(payload.get("target_id", 0))
            new_role = str(payload.get("role", "")).strip()
            res = admin_update_role(requester_id, target_id, new_role)
            self._send_json(res, 200 if res["success"] else 400)
            return

        # ── 16. ADMIN ACTIONS: CREATE GIFTCODE ────────────────────────────────
        elif path == "/api/admin/create-giftcode":
            requester_id = int(payload.get("requester_id", 0))
            code = str(payload.get("code", "")).strip()
            credits = int(payload.get("credits", 0))
            max_uses = int(payload.get("max_uses", 0))
            res = admin_create_giftcode(requester_id, code, credits, max_uses)
            self._send_json(res, 200 if res["success"] else 400)
            return

        # ── 17. ADMIN ACTIONS: DELETE GIFTCODE ────────────────────────────────
        elif path == "/api/admin/delete-giftcode":
            requester_id = int(payload.get("requester_id", 0))
            code = str(payload.get("code", "")).strip()
            res = admin_delete_giftcode(requester_id, code)
            self._send_json(res, 200 if res["success"] else 400)
            return

        # ── 18. AI TOKEN EXCHANGE: CREDITS → AI TOKENS (/api/ai/convert-tokens) ──
        elif path == "/api/ai/convert-tokens":
            user_id_raw = payload.get("user_id")
            credits_to_spend = payload.get("credits", 0)
            try:
                uid = int(user_id_raw)
                cr = int(credits_to_spend)
            except (TypeError, ValueError):
                self._send_json({"success": False, "error": "user_id và credits phải là số hợp lệ!"}, 400)
                return
            res = convert_credits_to_tokens(uid, cr)
            self._send_json(res, 200 if res["success"] else 400)
            return

        self._send_json({"error": "Unknown endpoint"}, 404)


def start_web_server(port: int = 8080, auto_open: bool = True):
    """Start local web server and open in browser"""
    server_address = ("", port)
    try:
        httpd = ThreadingHTTPServer(server_address, AOVWebHandler)
    except OSError:
        port = port + 1
        server_address = ("", port)
        httpd = ThreadingHTTPServer(server_address, AOVWebHandler)

    local_url = f"http://127.0.0.1:{port}"
    print("\n" + "=" * 62)
    print(f"  [AOV CHECKER SAAS WEB ENGINE RUNNING] : {local_url}")
    print(f"  [DEVELOPER REST API ENDPOINT]         : {local_url}/api/v1/check")
    print(f"  [MOBILE LAN ACCESS]                   : http://<YOUR_LAN_IP>:{port}")
    print("=" * 62 + "\n")

    if auto_open:
        try:
            webbrowser.open(local_url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Đã dừng Web Server.")
        httpd.server_close()
