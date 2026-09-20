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
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.aov_engine import check_account, parse_combo_line, format_account_full_info
from core.captcha import generate_captcha_challenge, verify_captcha_response
from core.ai_copilot import chat_with_copilot
from core.db import (
    init_db, register_user, login_user, get_user_profile,
    validate_api_key, deduct_credit, add_credits,
    generate_new_api_key, revoke_api_key, get_user_keys,
    save_check_history, get_user_history, clear_user_history,
    redeem_giftcode, admin_get_all_users, admin_adjust_credits,
    admin_update_role, admin_list_giftcodes, admin_create_giftcode,
    admin_delete_giftcode
)

# Initialize Database on server start
init_db()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# In-memory batch tasks
_TASKS = {}
_TASKS_LOCK = threading.Lock()

# Upload sessions for large (MB/GB) files
_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)
_UPLOAD_SESSIONS = {}
_UPLOAD_LOCK = threading.Lock()


class AOVWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress verbose terminal logs
        return

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

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

        # ── 4. Web Batch Task Status ──────────────────────────────────────────
        if path == "/api/task-status":
            task_id = query.get("task_id", [""])[0] or query.get("id", [""])[0]
            offset = int(query.get("offset", [0])[0] or 0)
            with _TASKS_LOCK:
                task = _TASKS.get(task_id)
                if not task:
                    self._send_json({"error": f"Task '{task_id}' not found"}, 404)
                    return
                all_res = task["results"]
                new_slice = all_res[offset:] if offset < len(all_res) else []
                resp_data = {
                    "total": task["total"],
                    "done": task["done"],
                    "hits": task["hits"],
                    "trang": task["trang"],
                    "invalid": task["invalid"],
                    "is_running": task["is_running"],
                    "status": "DONE" if not task["is_running"] else "RUNNING",
                    "results": new_slice,
                    "all_hits_count": len(task["all_hits"]),
                    "next_offset": len(all_res),
                }
            self._send_json(resp_data)
            return

        # ── 5. Internal Captcha Challenge (Multi-mode) ────────────────────────
        if path == "/api/captcha/new":
            mode = query.get("mode", ["slider"])[0]
            if mode not in ("click", "slider", "matrix"):
                mode = "slider"
            challenge = generate_captcha_challenge(mode)
            self._send_json({"success": True, "challenge": challenge})
            return

        # ── 6. Admin User Directory ───────────────────────────────────────────
        if path == "/api/admin/users":
            requester_id = int(query.get("user_id", [0])[0] or 0)
            res = admin_get_all_users(requester_id)
            self._send_json(res, 200 if res["success"] else 403)
            return

        # ── 7. Admin Giftcode Directory ───────────────────────────────────────
        if path == "/api/admin/giftcodes":
            requester_id = int(query.get("user_id", [0])[0] or 0)
            res = admin_list_giftcodes(requester_id)
            self._send_json(res, 200 if res["success"] else 403)
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
            
            # Verify Captcha
            captcha_token = payload.get("captcha_token", "")
            captcha_mode = payload.get("captcha_mode", "slider")
            user_answer = payload.get("user_answer", {})

            # Fallback for old slider fields
            if not user_answer and "submitted_x" in payload:
                user_answer = {
                    "user_x": payload.get("submitted_x", 0),
                    "track_width": payload.get("track_width", 300)
                }

            if captcha_token:
                if not verify_captcha_response(captcha_mode, captcha_token, user_answer):
                    self._send_json({"success": False, "error": f"Xác thực bảo mật ({captcha_mode}) không chính xác! Vui lòng thử lại."}, 400)
                    return
            else:
                self._send_json({"success": False, "error": "Vui lòng hoàn thành xác thực bảo mật Captcha!"}, 400)
                return

            res = register_user(username, password)
            status_code = 200 if res["success"] else 400
            self._send_json(res, status_code)
            return

        # ── 2. AUTH: LOGIN ────────────────────────────────────────────────────
        if path in ("/api/auth/login", "/api/login"):
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", "")).strip()
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
                os.makedirs("results", exist_ok=True)
                live_path = os.path.join("results", f"api_hits_{task_id}.txt")
                trang_path = os.path.join("results", f"api_trang_{task_id}.txt")

                def check_worker(pair):
                    a, p = pair
                    r = check_account(a, p)
                    with _TASKS_LOCK:
                        task_state["done"] += 1
                        task_state["results"].append(r)
                        if r["status"] == "HIT":
                            task_state["hits"] += 1
                            task_state["all_hits"].append(r)
                            full_line = format_account_full_info(r)
                            if r.get("is_trang"):
                                task_state["trang"] += 1
                                with open(trang_path, "a", encoding="utf-8") as ft:
                                    ft.write(full_line + "\n")
                            with open(live_path, "a", encoding="utf-8") as fh:
                                fh.write(full_line + "\n")
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

            res = check_account(acc, pwd)

            if uid:
                save_check_history(int(uid), f"{acc}:{pwd}", res.get("status", "FAIL"), res)

            if res.get("status") == "HIT":
                print(f"[WEB SINGLE] {format_account_full_info(res)}", flush=True)
            else:
                print(f"[WEB SINGLE] {acc}:{pwd} | STATUS : {res.get('status')} | DETAIL : {res.get('message', 'FAIL')}", flush=True)
            self._send_json(res)
            return

        # ── 10. WEB UI: CHECK BATCH ───────────────────────────────────────────
        elif path == "/api/check-batch":
            combos_raw = payload.get("combos", [])
            threads = int(payload.get("threads", 10) or 10)
            threads = max(1, min(threads, 500))
            uid = payload.get("user_id")

            combos = []
            for item in combos_raw:
                u, p = parse_combo_line(str(item))
                if u and p:
                    combos.append((u, p))

            if not combos:
                self._send_json({"error": "Không có danh sách tài khoản hợp lệ (hỗ trợ : | ; / khoảng trắng)!"}, 400)
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
            def run_batch():
                os.makedirs("results", exist_ok=True)
                live_path = os.path.join("results", f"web_hits_{task_id}.txt")
                trang_path = os.path.join("results", f"web_trang_{task_id}.txt")

                print(f"\n[BẮT ĐẦU CHECK BATCH {task_id}] Tổng: {len(combos)} tài khoản | Luồng: {threads}", flush=True)

                def check_worker(pair):
                    a, p = pair
                    r = check_account(a, p)
                    with _TASKS_LOCK:
                        task_state["done"] += 1
                        task_state["results"].append(r)
                        done_str = f"[{task_state['done']}/{task_state['total']}]"
                        if r["status"] == "HIT":
                            task_state["hits"] += 1
                            task_state["all_hits"].append(r)
                            full_line = format_account_full_info(r)
                            if r.get("is_trang"):
                                task_state["trang"] += 1
                                with open(trang_path, "a", encoding="utf-8") as ft:
                                    ft.write(full_line + "\n")
                            with open(live_path, "a", encoding="utf-8") as fh:
                                fh.write(full_line + "\n")
                            print(f"{done_str} {full_line}", flush=True)
                        else:
                            if r["status"] == "INVALID":
                                task_state["invalid"] += 1
                            print(f"{done_str} {a}:{p} | STATUS : {r.get('status')} | DETAIL : {r.get('message', 'FAIL')}", flush=True)

                    if uid:
                        save_check_history(int(uid), f"{a}:{p}", r.get("status", "FAIL"), r)

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    executor.map(check_worker, combos)

                with _TASKS_LOCK:
                    task_state["is_running"] = False

                if uid:
                    deduct_credit(int(uid), len(combos))

                print(f"\n[HOÀN THÀNH BATCH {task_id}] Tổng: {task_state['total']} | Sống: {task_state['hits']} | Trắng TTT: {task_state['trang']} (File lưu tại results/)\n", flush=True)

            threading.Thread(target=run_batch, daemon=True).start()
            self._send_json({"task_id": task_id, "total": len(combos)})
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
                    a, p = pair
                    r = check_account(a, p)
                    with _TASKS_LOCK:
                        task_state["done"] += 1
                        task_state["results"].append(r)
                        done_str = f"[{task_state['done']}/{task_state['total']}]"
                        if r["status"] == "HIT":
                            task_state["hits"] += 1
                            task_state["all_hits"].append(r)
                            full_line = format_account_full_info(r)
                            if r.get("is_trang"):
                                task_state["trang"] += 1
                                with open(trang_path, "a", encoding="utf-8") as ft:
                                    ft.write(full_line + "\n")
                            with open(live_path, "a", encoding="utf-8") as fh:
                                fh.write(full_line + "\n")
                            print(f"{done_str} {full_line}", flush=True)
                        else:
                            if r["status"] == "INVALID":
                                task_state["invalid"] += 1
                            print(f"{done_str} {a}:{p} | STATUS : {r.get('status')} | DETAIL : {r.get('message', 'FAIL')}", flush=True)

                    if uid:
                        save_check_history(int(uid), f"{a}:{p}", r.get("status", "FAIL"), r)

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    executor.map(check_worker, combos)

                with _TASKS_LOCK:
                    task_state["is_running"] = False

                if uid:
                    deduct_credit(int(uid), len(combos))

                # Clean up temp file
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

                print(f"\n[HOÀN THÀNH FILE BATCH {task_id}] Tổng: {task_state['total']} | Sống: {task_state['hits']} | Trắng: {task_state['trang']} (File lưu tại results/)\n", flush=True)

            threading.Thread(target=run_file_batch, daemon=True).start()
            self._send_json({"task_id": task_id, "total": len(combos)})
            return

        # ── 13. AI STUDIO COPILOT RAG CHAT (/api/ai/chat) ─────────────────────
        elif path == "/api/ai/chat":
            user_msg = str(payload.get("message", "")).strip()
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

            reply = chat_with_copilot(user_msg, history=history, batch_context=batch_context)
            self._send_json({"success": True, "reply": reply})
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
