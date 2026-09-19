"""
Web Server for Lien Quan Checker
Built-in HTTP server with REST API & static file serving.
Zero extra heavy framework requirements!
"""
import json
import mimetypes
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.aov_engine import check_account, parse_combo_line

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# In-memory batch tasks
_TASKS = {}
_TASKS_LOCK = threading.Lock()


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
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/task-status":
            query = urllib.parse.parse_qs(parsed.query)
            task_id = query.get("task_id", [""])[0] or query.get("id", [""])[0]
            with _TASKS_LOCK:
                task = _TASKS.get(task_id)
                if not task:
                    self._send_json({"error": f"Task '{task_id}' not found"}, 404)
                    return
                # Return snapshot
                resp_data = {
                    "total": task["total"],
                    "done": task["done"],
                    "hits": task["hits"],
                    "trang": task["trang"],
                    "invalid": task["invalid"],
                    "is_running": task["is_running"],
                    "status": "DONE" if not task["is_running"] else "RUNNING",
                    "results": list(task["results"]),  # all finished results so client has full stream
                    "all_hits_count": len(task["all_hits"]),
                }
            self._send_json(resp_data)
            return

        # Static files
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

        if path == "/api/check-single":
            acc = payload.get("account", "").strip()
            pwd = payload.get("password", "").strip()
            if not acc or not pwd:
                self._send_json({"error": "Vui lòng nhập tài khoản và mật khẩu"}, 400)
                return

            res = check_account(acc, pwd)
            from core.aov_engine import format_account_full_info
            if res.get("status") == "HIT":
                print(f"[API SINGLE] {format_account_full_info(res)}", flush=True)
            else:
                print(f"[API SINGLE] {acc}:{pwd} | STATUS : {res.get('status')} | DETAIL : {res.get('message', 'FAIL')}", flush=True)
            self._send_json(res)
            return

        elif path == "/api/check-batch":
            combos_raw = payload.get("combos", [])
            threads = int(payload.get("threads", 5) or 5)
            threads = max(1, min(threads, 30))

            combos = []
            for item in combos_raw:
                u, p = parse_combo_line(str(item))
                if u and p:
                    combos.append((u, p))

            if not combos:
                self._send_json({"error": "Không có danh sách tài khoản hợp lệ (hỗ trợ : | ; / khoảng trắng)!"}, 400)
                return

            import uuid
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
                        from core.aov_engine import format_account_full_info
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

                with ThreadPoolExecutor(max_workers=threads) as executor:
                    executor.map(check_worker, combos)

                with _TASKS_LOCK:
                    task_state["is_running"] = False

                print(f"\n[HOÀN THÀNH BATCH {task_id}] Tổng: {task_state['total']} | Sống: {task_state['hits']} | Trắng TTT: {task_state['trang']} (File lưu tại results/)\n", flush=True)

            threading.Thread(target=run_batch, daemon=True).start()
            self._send_json({"task_id": task_id, "total": len(combos)})
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
    print(f"  [WEB SERVER RUNNING] : {local_url}")
    print(f"  [MOBILE LAN ACCESS]  : http://<YOUR_LAN_IP>:{port}")
    print("=" * 62 + "\n")

    if auto_open:
        try:
            webbrowser.open(local_url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Da dung Web Server.")
        httpd.server_close()
