"""
Interactive CLI for Garena Lien Quan Checker
Supports arrow key navigation (Up/Down + Enter) on PC with automatic fallback to numeric menu on Mobile (Termux/SSH).
"""
import ctypes
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

from core.aov_engine import check_account, parse_combo_line

# ── ANSI Colors ─────────────────────────────────────────────────────────────
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    BG_CYAN = "\033[46m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def c(color: str, text: str) -> str:
    return f"{color}{text}{Colors.RESET}"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}+----------------------------------------------------------------+
|          GARENA - LIEN QUAN MOBILE (AOV) CHECKER PRO           |
|                HIGH PERFORMANCE TERMINAL ENGINE                |
+----------------------------------------------------------------+{Colors.RESET}
"""
    print(banner)


# ── Cross-Platform Key Handler ──────────────────────────────────────────────
def is_windows():
    return sys.platform == "win32"


def get_key_input() -> str:
    """
    Returns 'UP', 'DOWN', 'ENTER', 'ESC', or regular character.
    Gracefully falls back if running in non-raw environments (e.g. mobile).
    """
    if is_windows():
        try:
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                sub = msvcrt.getch()
                if sub == b"H":
                    return "UP"
                elif sub == b"P":
                    return "DOWN"
            elif ch in (b"\r", b"\n"):
                return "ENTER"
            elif ch == b"\x1b":
                return "ESC"
            return ch.decode("latin1", errors="ignore")
        except Exception:
            return ""
    else:
        # Unix / Termux
        try:
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    seq = sys.stdin.read(2)
                    if seq == "[A":
                        return "UP"
                    elif seq == "[B":
                        return "DOWN"
                    return "ESC"
                elif ch in ("\r", "\n"):
                    return "ENTER"
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            # Fallback for phone terminal where raw mode fails
            line = sys.stdin.readline().strip()
            return line


def select_menu(options: list[str], title: str = "CHỌN CHỨC NĂNG:") -> int:
    """
    Interactive selection menu.
    Uses Arrow Keys for PC, and falls back to numbers if arrow keys are not supported.
    """
    is_interactive = sys.stdin.isatty()
    # Check if mobile / non-interactive
    if not is_interactive or os.environ.get("TERMUX_VERSION") or os.environ.get("ANDROID_ROOT"):
        # Mobile mode
        print(f"\n{c(Colors.CYAN + Colors.BOLD, title)}")
        for idx, opt in enumerate(options, 1):
            print(f"  {c(Colors.YELLOW, f'[{idx}]')} {opt}")
        print(f"  {c(Colors.RED, '[0]')} Quay lại / Thoát")
        while True:
            choice = input(f"\n{c(Colors.GREEN, '👉 Nhập số (0-' + str(len(options)) + '): ')}").strip()
            if choice == "0":
                return -1
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                return int(choice) - 1
            print(c(Colors.RED, "Lựa chọn không hợp lệ, vui lòng thử lại!"))

    # PC Arrow Key interactive mode
    selected = 0
    while True:
        clear_screen()
        print_banner()
        print(f"{c(Colors.YELLOW + Colors.BOLD, title)}")
        print(c(Colors.DIM, "(Dùng phím mũi tên ↑ / ↓ để di chuyển, phím Enter để chọn)\n"))

        for i, opt in enumerate(options):
            if i == selected:
                print(f"  {c(Colors.BG_CYAN + Colors.WHITE + Colors.BOLD, ' 👉 ' + opt + ' ')}")
            else:
                print(f"     {c(Colors.WHITE, opt)}")

        print(f"\n{c(Colors.DIM, '[Esc / q] Để thoát')}")

        key = get_key_input()
        if key == "UP":
            selected = (selected - 1) % len(options)
        elif key == "DOWN":
            selected = (selected + 1) % len(options)
        elif key == "ENTER":
            return selected
        elif key in ("ESC", "q", "Q"):
            return -1


# ── Render Account Result ────────────────────────────────────────────────────
def print_account_card(r: dict):
    print("\n" + c(Colors.CYAN + Colors.BOLD, "-----------------------------------------------------------------"))
    acc = r.get("account", "")
    pwd = r.get("password", "")
    status = r.get("status", "ERROR")
    tinh_trang = r.get("tinh_trang", "Chua xac dinh")
    is_trang = r.get("is_trang", False)
    shells = r.get("shells", 0)

    # Status tag
    if status == "HIT":
        st_color = Colors.GREEN + Colors.BOLD
        st_text = "[SUCCESS / HIT]"
    elif status == "INVALID":
        st_color = Colors.RED + Colors.BOLD
        st_text = "[FAIL / WRONG PASSWORD]"
    else:
        st_color = Colors.YELLOW + Colors.BOLD
        st_text = f"[ERROR: {r.get('message', '')}]"

    print(f"  Account     : {c(Colors.WHITE + Colors.BOLD, acc)} | Pass: {c(Colors.WHITE, pwd)}")
    print(f"  Trang thai  : {c(st_color, st_text)}")

    if status == "HIT":
        tt_color = Colors.GREEN + Colors.BOLD if is_trang else Colors.YELLOW
        print(f"  Thong tin   : {c(tt_color, tinh_trang)} (So: {c(Colors.CYAN, str(shells))})")

        aov = r.get("aov", {})
        print(c(Colors.CYAN, "  -- [LIEN QUAN MOBILE] -----------------------------------------"))
        print(f"  Ingame      : {c(Colors.WHITE + Colors.BOLD, aov.get('name') or 'Chua dat ten')}")
        print(f"  Cap do (Lv) : {aov.get('level', 0)} | Banned: {c(Colors.RED if aov.get('banned') == 'CO' else Colors.GREEN, aov.get('banned', 'KHONG'))}")
        print(f"  Rank        : {c(Colors.YELLOW + Colors.BOLD, aov.get('rank', 'Chua Dau Hang'))}")
        print(f"  Tuong/Skin  : {c(Colors.CYAN, str(aov.get('total_champs', 0)))} Tuong | {c(Colors.MAGENTA, str(aov.get('total_skins', 0)))} Trang phuc")

        sss = aov.get("sss_list", [])
        anime = aov.get("anime_list", [])
        ss = aov.get("ss_list", [])

        if sss:
            print(f"  * {c(Colors.YELLOW + Colors.BOLD, f'SSS / Thu Nguyen ({len(sss)}):')} {', '.join(sss[:6])}{'...' if len(sss)>6 else ''}")
        if anime:
            print(f"  * {c(Colors.MAGENTA + Colors.BOLD, f'Anime / Collab ({len(anime)}):')} {', '.join(anime[:6])}{'...' if len(anime)>6 else ''}")
        if ss:
            print(f"  * {c(Colors.CYAN + Colors.BOLD, f'SS / Tuyet Sac ({len(ss)}):')} {', '.join(ss[:6])}{'...' if len(ss)>6 else ''}")

        sec = r.get("security", {})
        print(c(Colors.CYAN, "  -- [BAO MAT GARENA] -------------------------------------------"))
        print(f"  SDT: {sec.get('masked_phone') or 'Trang'} | Email: {sec.get('masked_email') or 'Trang'} | CCCD: {'Co' if sec.get('has_cccd') else 'Trang'}")
        print(f"  2FA: {'Bat' if sec.get('auth_2fa') else 'Tat'} | Facebook: {'Lien ket' if sec.get('fb_linked') else 'Khong'}")

    print(c(Colors.CYAN + Colors.BOLD, "-----------------------------------------------------------------") + "\n")


# ── Operations ───────────────────────────────────────────────────────────────
def handle_single_check():
    clear_screen()
    print_banner()
    print(c(Colors.YELLOW + Colors.BOLD, ">>> KIEM TRA DON LE TAI KHOAN"))
    acc = input(f"{c(Colors.CYAN, 'Nhap Tai khoan Garena:')} ").strip()
    if not acc:
        return
    pwd = input(f"{c(Colors.CYAN, 'Nhap Mat khau:')} ").strip()
    if not pwd:
        return

    print(c(Colors.YELLOW, f"\n[*] Dang ket noi server va phan tich du lieu..."))
    res = check_account(acc, pwd)
    from core.aov_engine import format_account_full_info
    if res.get("status") == "HIT":
        print("\n" + c(Colors.GREEN + Colors.BOLD, format_account_full_info(res)) + "\n")
    else:
        print(f"\n{acc}:{pwd} | STATUS : {res.get('status')} | DETAIL : {res.get('message', 'Thất bại')}\n")

    input(c(Colors.DIM, "Bam Enter de quay lai menu chinh..."))


def handle_bulk_check():
    clear_screen()
    print_banner()
    print(c(Colors.YELLOW + Colors.BOLD, "--- KIỂM TRA DANH SÁCH TÀI KHOẢN (COMBO FILE) ---"))
    file_path = input(f"{c(Colors.CYAN, 'Đường dẫn file combo (ví dụ: combo.txt):')} ").strip().strip('"')
    if not os.path.exists(file_path):
        print(c(Colors.RED, f"File '{file_path}' không tồn tại!"))
        time.sleep(2)
        return

    threads_str = input(f"{c(Colors.CYAN, 'Số luồng chạy (mặc định 5):')} ").strip()
    threads = int(threads_str) if threads_str.isdigit() and int(threads_str) > 0 else 5

    combos = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            u, p = parse_combo_line(line)
            if u and p:
                combos.append((u, p))

    total = len(combos)
    if total == 0:
        print(c(Colors.RED, "File không có tài khoản hợp lệ (hỗ trợ các dạng user:pass, user|pass, user;pass, user/pass, user pass)!"))
        time.sleep(2)
        return

    os.makedirs("results", exist_ok=True)
    live_file = os.path.join("results", "hit_lienquan.txt")
    trang_file = os.path.join("results", "acc_trang_ttt.txt")

    print(c(Colors.GREEN, f"\n🚀 Bắt đầu check {total} tài khoản với {threads} luồng...\n"))

    stats = {"done": 0, "hit": 0, "invalid": 0, "trang": 0}
    lock = threading.Lock()

    def worker(item):
        a, p = item
        r = check_account(a, p)
        with lock:
            stats["done"] += 1
            from core.aov_engine import format_account_full_info
            if r["status"] == "HIT":
                stats["hit"] += 1
                full_line = format_account_full_info(r)
                if r.get("is_trang"):
                    stats["trang"] += 1
                    with open(trang_file, "a", encoding="utf-8") as f_trang:
                        f_trang.write(full_line + "\n")

                with open(live_file, "a", encoding="utf-8") as f_hit:
                    f_hit.write(full_line + "\n")
                
                print(c(Colors.GREEN + Colors.BOLD, f"[{stats['done']}/{total}] ") + full_line, flush=True)
            else:
                if r["status"] == "INVALID":
                    stats["invalid"] += 1
                print(c(Colors.RED, f"[{stats['done']}/{total}] {a}:{p} | {r.get('status')} | {r.get('message', 'FAIL')}"), flush=True)

    import threading
    with ThreadPoolExecutor(max_workers=threads) as ex:
        ex.map(worker, combos)

    print("\n" + c(Colors.CYAN + Colors.BOLD, "═" * 60))
    print(f"  HOÀN THÀNH: {stats['hit']} SỐNG / {total} TỔNG")
    print(f"  {c(Colors.YELLOW + Colors.BOLD, f'ACC TRẮNG (TTT): {stats['trang']}')} -> Lưu tại: {trang_file}")
    print(f"  Tất cả acc sống lưu tại: {live_file}")
    print(c(Colors.CYAN + Colors.BOLD, "═" * 60) + "\n")
    input(c(Colors.DIM, "Bấm Enter để quay lại..."))


def run_cli():
    """Main CLI entry loop"""
    options = [
        "1. Check 1 Tài Khoản Đơn Lẻ (Nhập Trực Tiếp)",
        "2. Check Danh Sách Combo File (.txt) Đa Luồng",
        "3. Khởi Chạy Web Server (Giao Diện Trình Duyệt PC & Mobile)",
        "4. Thoát",
    ]

    while True:
        idx = select_menu(options, title="MENU QUẢN LÝ CHECK ACC LIÊN QUÂN (CLI TERMINAL):")
        if idx == 0:
            handle_single_check()
        elif idx == 1:
            handle_bulk_check()
        elif idx == 2:
            from web.server import start_web_server
            start_web_server(auto_open=True)
            break
        else:
            print(c(Colors.YELLOW, "\nTạm biệt Boss! Hẹn gặp lại."))
            break
