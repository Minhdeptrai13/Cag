"""
App Launcher for AOV Checker
Launches as a standalone Desktop App window using pywebview or browser app mode.
"""
import os
import subprocess
import sys
import threading
import time
import webbrowser

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from web.server import start_web_server

PORT = 8080
APP_URL = f"http://127.0.0.1:{PORT}"


def _find_browser_app_executable():
    """Find Google Chrome or Microsoft Edge executable for --app mode on Windows/macOS/Linux"""
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    elif sys.platform == "darwin":
        c = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(c):
            return c
    else:
        # Linux
        for c in ["google-chrome", "chromium-browser", "chromium"]:
            import shutil
            p = shutil.which(c)
            if p:
                return p
    return None


def launch_app():
    """Start local web server in background and launch desktop window"""
    print("\n" + "=" * 60)
    print("  🚀 KHỞI ĐỘNG ỨNG DỤNG CỬA SỔ (DESKTOP APP)...")
    print("=" * 60)

    # 1. Start Web Server in daemon thread
    server_thread = threading.Thread(target=start_web_server, kwargs={"port": PORT, "auto_open": False}, daemon=True)
    server_thread.start()
    time.sleep(1.2)  # Give server time to bind port

    # 2. Try pywebview if installed
    try:
        import webview
        print("  ✔ Sử dụng PyWebView Native Desktop Window...")
        webview.create_window(
            title="AOV Pro Checker - Garena Liên Quân Mobile",
            url=APP_URL,
            width=1240,
            height=820,
            resizable=True,
        )
        webview.start()
        return
    except ImportError:
        pass

    # 3. Launch in standalone Application Window mode (--app flag)
    browser_exe = _find_browser_app_executable()
    if browser_exe:
        print("  ✔ Đang mở chế độ Cửa Sổ Ứng Dụng Độc Lập...")
        try:
            cmd = [browser_exe, f"--app={APP_URL}", "--window-size=1240,820"]
            subprocess.Popen(cmd)
            # Keep process running
            while True:
                time.sleep(1)
        except Exception:
            pass

    # 4. Fallback: regular browser
    print("  ✔ Đang mở trên Trình duyệt...")
    webbrowser.open(APP_URL)
    while True:
        time.sleep(1)
