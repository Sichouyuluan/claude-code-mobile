"""CC Remote Dashboard — PyWebView 本地管理面板 (Liquid Glass)"""
import os
import sys
import subprocess
import threading
import socket
import webbrowser
import json
import secrets
from pathlib import Path

import psutil
import webview

PROJECT_DIR = Path(__file__).parent
API_KEY_FILE = PROJECT_DIR / ".api_key"
CONFIG_FILE = PROJECT_DIR / "config.yaml"


def get_api_key():
    try:
        key = API_KEY_FILE.read_text().strip()
        if key:
            return key
    except Exception:
        pass
    key = secrets.token_urlsafe(32)
    API_KEY_FILE.write_text(key)
    return key


def get_port():
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f).get("port", 8001)
    except Exception:
        return 8001


def get_lan_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        if s:
            s.close()


def _kill_pid(pid):
    """Kill a process by PID (Windows-safe)."""
    try:
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=5,
                       creationflags=subprocess.CREATE_NO_WINDOW,
                       startupinfo=_si)
    except Exception:
        pass


def _find_pid_on_port(port):
    """Find PID listening on a given port."""
    try:
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=_si)
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                if pid > 0:
                    return pid
    except Exception:
        pass
    return None


class PanelAPI:
    """JS-Python bridge，供 panel.html 的 JavaScript 调用"""

    def __init__(self):
        self.server_process = None
        self.server_running = False
        self.server_pid = None

    def start_server(self):
        if self.server_running:
            return {"success": True, "message": "服务器已在运行"}
        try:
            port = get_port()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                self.server_running = True
                pid = _find_pid_on_port(port)
                if pid:
                    self.server_pid = pid
                return {"success": True, "message": "检测到已有服务器运行"}

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.server_process = subprocess.Popen(
                [sys.executable, "-u", "server.py"],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self.server_pid = self.server_process.pid
            self.server_running = True
            threading.Thread(target=self._monitor, daemon=True).start()
            return {"success": True, "message": "服务器已启动"}
        except Exception as e:
            return {"success": False, "message": f"启动失败: {e}"}

    def _monitor(self):
        """Background thread: watch server process, update status on exit."""
        if self.server_process:
            self.server_process.wait()
            self.server_running = False
            self.server_process = None
            self.server_pid = None

    def stop_server(self):
        try:
            if self.server_process:
                self.server_process.terminate()
                try:
                    self.server_process.wait(timeout=5)
                except Exception:
                    self.server_process.kill()
                self.server_process = None
            # Also kill by port to catch orphans
            port = get_port()
            pid = _find_pid_on_port(port)
            if pid and pid == self.server_pid:
                _kill_pid(pid)
            self.server_running = False
            self.server_pid = None
            return {"success": True, "message": "服务器已停止"}
        except Exception as e:
            return {"success": False, "message": f"停止失败: {e}"}

    def get_status(self):
        port = get_port()
        lan_ip = get_lan_ip()
        api_key = get_api_key()

        # Check if server is actually running on port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        actually_running = result == 0
        if actually_running and not self.server_running:
            self.server_running = True
            pid = _find_pid_on_port(port)
            if pid:
                self.server_pid = pid
        elif not actually_running and self.server_running:
            self.server_running = False
            self.server_process = None
            self.server_pid = None

        # System info
        cpu = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory()
        cc_count = sum(1 for p in psutil.process_iter(["name"])
                       if "claude" in (p.info["name"] or "").lower())

        return {
            "server_running": self.server_running,
            "local_url": f"http://localhost:{port}" if self.server_running else "--",
            "lan_url": f"http://{lan_ip}:{port}" if self.server_running else "--",
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 1),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "cc_count": cc_count,
            "api_key": api_key,
        }

    def get_logs(self):
        log_dir = PROJECT_DIR / "logs"
        if not log_dir.exists():
            return {"logs": "暂无日志"}
        try:
            log_files = sorted(log_dir.glob("cc_*.log"), key=lambda f: f.stat().st_mtime)
            all_lines = []
            for lf in log_files[-3:]:
                try:
                    with open(lf, "r", encoding="utf-8", errors="replace") as f:
                        all_lines.extend(f.readlines())
                except Exception:
                    continue
            recent = all_lines[-50:] if len(all_lines) > 50 else all_lines
            return {"logs": "".join(recent) if recent else "暂无日志"}
        except Exception:
            return {"logs": "读取日志失败"}

    def copy_to_clipboard(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            return {"success": True}
        except ImportError:
            return {"success": False, "message": "pyperclip 未安装"}

    def save_api_key(self, new_key):
        if not new_key or len(new_key) < 8:
            return {"success": False, "message": "密钥长度至少8位"}
        try:
            old_key = get_api_key()
            API_KEY_FILE.write_text(new_key)
            if self.server_running:
                try:
                    port = get_port()
                    import urllib.request
                    req = urllib.request.Request(
                        f"http://localhost:{port}/api/auth/change-key",
                        data=json.dumps({"current_key": old_key, "new_key": new_key}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    urllib.request.urlopen(req, timeout=3)
                except Exception:
                    pass
            return {"success": True, "message": "密钥已保存"}
        except Exception as e:
            return {"success": False, "message": f"保存失败: {e}"}

    def open_browser(self):
        port = get_port()
        webbrowser.open(f"http://localhost:{port}")
        return {"success": True}


def _cleanup_orphaned():
    """Kill any orphaned server process on exit."""
    try:
        port = get_port()
        pid = _find_pid_on_port(port)
        if pid:
            _kill_pid(pid)
    except Exception:
        pass


import atexit
atexit.register(_cleanup_orphaned)


if __name__ == "__main__":
    api = PanelAPI()
    # Kill orphaned server on startup
    _cleanup_orphaned()

    window = webview.create_window(
        'claude-code-mobile',
        url=str(PROJECT_DIR / 'static' / 'panel.html'),
        js_api=api,
        width=820,
        height=620,
        min_size=(640, 450),
        background_color='#080b14',
    )
    webview.start(debug=False)
