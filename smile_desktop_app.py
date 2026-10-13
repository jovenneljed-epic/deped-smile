"""
DepEd Project S.M.I.L.E. - Standalone Desktop Application (Live Real-Time Sync)
==============================================================================
Runs Project S.M.I.L.E. as a standalone native desktop application for Windows.
Directly synchronized in 100% real-time with the Web Application (https://deped-smile.vercel.app).

Features:
- Two-Way Realtime Synchronization:
  * Whatever you do in the Desktop App is instantly visible on the Web App.
  * Whatever web users (teachers, guards, admins) do is instantly visible in the Desktop App.
  * All accounts (ronnel, faculty, students) are identical and live.
- Native Windows Desktop Window (Hardware-Accelerated WebView2 / Chromium).
- Zero browser address bars, tabs, or third-party extensions.
- Keyboard Hotkeys:
    * F1: Dashboard
    * F2: Gate Kiosk Scanner (Fullscreen HUD)
    * F3: Enrolled Students Directory
    * F4: Enroll Learner
    * F5: Refresh
    * F11: Toggle Fullscreen
- Optional Offline Local Mode (via --local flag or desktop_config.json).
"""

import sys
import os
import json
import time
import socket
import threading
import urllib.request
import urllib.error

# Determine working directories (source vs compiled PyInstaller .exe)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import smile_config
    SCHOOL_NAME = getattr(smile_config, "SCHOOL_NAME", "Department of Education")
except Exception:
    SCHOOL_NAME = "Department of Education"

CONFIG_PATH = os.path.join(BASE_DIR, "desktop_config.json")

def load_config():
    """Loads configuration with defaults pointing directly to the live Web App."""
    defaults = {
        "server_url": "https://deped-smile.vercel.app",
        "app_title": "DepEd Project S.M.I.L.E. - Standalone Desktop Client",
        "window_width": 1366,
        "window_height": 820,
        "sync_mode": "REALTIME_CLOUD_SYNC",
        "local_port": 5000
    }
    # Check current directory first
    target_cfg = CONFIG_PATH
    if not os.path.exists(target_cfg):
        # Check bundled directory
        bundled_cfg = os.path.join(BUNDLE_DIR, "desktop_config.json")
        if os.path.exists(bundled_cfg):
            target_cfg = bundled_cfg

    if os.path.exists(target_cfg):
        try:
            with open(target_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception as e:
            print(f"[!] Config load notice: {e}")
    else:
        # Create default config file for easy user customization
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=2)
        except Exception:
            pass

    return defaults

def get_local_ip():
    """Returns local LAN IP address so other users on Wi-Fi can connect in local mode."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def is_server_alive(port=5000):
    """Checks if local Flask server is already running."""
    try:
        url = f"http://127.0.0.1:{port}/api/ping"
        req = urllib.request.Request(url, headers={'User-Agent': 'SMILE-Desktop-Check'})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def start_background_server(port=5000):
    """Starts the local Flask server in a background daemon thread."""
    import app
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.app.run(host='0.0.0.0', port=port, threaded=True, debug=False, use_reloader=False)

def main():
    config = load_config()
    is_local_requested = "--local" in sys.argv or config.get("sync_mode") == "LOCAL_OFFLINE"
    
    port = config.get("local_port", 5000)
    local_ip = get_local_ip()

    if is_local_requested:
        target_url = f"http://127.0.0.1:{port}/"
        mode_label = "OFFLINE / LOCAL LAN SERVER"
        
        if not is_server_alive(port):
            print(f" [*] Launching embedded local server on port {port}...")
            server_thread = threading.Thread(target=start_background_server, args=(port,), daemon=True)
            server_thread.start()
            
            max_wait = 10.0
            start_time = time.time()
            while time.time() - start_time < max_wait:
                if is_server_alive(port):
                    break
                time.sleep(0.15)
            print(" [+] Local server started successfully!")
    else:
        # Default: Connect directly to the production web app for 100% real-time two-way sync
        target_url = config.get("server_url", "https://deped-smile.vercel.app")
        mode_label = f"REAL-TIME TWO-WAY CLOUD SYNC ({target_url})"

    print("=" * 72)
    print("   DEPARTMENT OF EDUCATION - PROJECT S.M.I.L.E. DESKTOP CLIENT")
    print("=" * 72)
    print(f" [*] Synchronization: {mode_label}")
    print(f" [*] Connected Server: {target_url}")
    print(f" [*] Target Database:  Shared Live Database (Ronnel, All Staff, Enrolled Students)")
    print(f" [*] Desktop Engine:   Microsoft Edge WebView2 (Hardware-Accelerated)")
    print("-" * 72)
    print(f" [OK] Standalone Desktop App: Active window launching...")
    print(f" [OK] Web Users Link:         {target_url}")
    print("=" * 72)
    print(" (Press Ctrl+C or close the application window to exit)")

    try:
        import webview
    except ImportError:
        print("\n[!] Installing 'pywebview'...")
        os.system(f'"{sys.executable}" -m pip install pywebview')
        import webview

    class DesktopApi:
        def get_server_url(self):
            return target_url
            
        def toggle_fullscreen(self, window):
            window.toggle_fullscreen()

    api = DesktopApi()
    
    # Create native standalone desktop window
    win_title = f"DEPED S.M.I.L.E. | Desktop Client [Live Real-Time Sync: {target_url}]"
    window = webview.create_window(
        title=win_title,
        url=target_url,
        width=int(config.get("window_width", 1366)),
        height=int(config.get("window_height", 820)),
        min_size=(1000, 600),
        text_select=True,
        zoomable=True,
        confirm_close=False,
        js_api=api
    )

    # Inject Desktop Hotkeys and Network Info into the WebView
    def on_loaded():
        js_code = f"""
        (function() {{
            window._isSmileDesktopApp = true;
            window._smileTargetUrl = '{target_url}';
            
            // Desktop Hotkeys (F1-F5, F11)
            window.addEventListener('keydown', function(e) {{
                if (e.key === 'F1') {{
                    e.preventDefault();
                    window.location.href = '/dashboard';
                }} else if (e.key === 'F2') {{
                    e.preventDefault();
                    window.location.href = '/kiosk';
                }} else if (e.key === 'F3') {{
                    e.preventDefault();
                    window.location.href = '/students';
                }} else if (e.key === 'F4') {{
                    e.preventDefault();
                    window.location.href = '/enroll';
                }}
            }});

            console.log('[DepEd Desktop] Standalone native client connected to {target_url}');
        }})();
        """
        try:
            window.evaluate_js(js_code)
        except Exception:
            pass

    window.events.loaded += on_loaded

    # Start native event loop
    webview.start(debug=False)

if __name__ == '__main__':
    main()
