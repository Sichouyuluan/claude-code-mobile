"""CC Remote Dashboard — 原生桌面管理面板 (Liquid Glass)"""
import os
import sys
import subprocess
import threading
import socket
import webbrowser
from collections import deque
from pathlib import Path

import tkinter as tk
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PROJECT_DIR = Path(__file__).parent
API_KEY_FILE = PROJECT_DIR / ".api_key"
CONFIG_FILE = PROJECT_DIR / "config.yaml"

# Liquid glass color palette
BG = "#080b14"
CARD_BG = "#0d1220"
CARD_BORDER = "#1a2440"
ACCENT = "#3b82f6"
GLOW = "#60a5fa"
TEXT = "#e2e8f0"
TEXT2 = "#94a3b8"
TEXT3 = "#475569"
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#f59e0b"


def get_api_key():
    try:
        key = API_KEY_FILE.read_text().strip()
        if key:
            return key
    except Exception:
        pass
    # Auto-generate if file doesn't exist or is empty
    import secrets
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


class GlassCard(ctk.CTkFrame):
    """Liquid glass effect card"""
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=CARD_BG, corner_radius=14,
                         border_width=1, border_color=CARD_BORDER, **kw)


class GlowButton(ctk.CTkButton):
    """Button with glow effect"""
    def __init__(self, master, glow_color=ACCENT, **kw):
        super().__init__(master, **kw)
        self.configure(fg_color=glow_color, hover_color=glow_color,
                       corner_radius=10, border_width=0,
                       font=ctk.CTkFont(size=12, weight="bold"))


class Panel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("claude-code-mobile")
        self.geometry("750x480")
        self.minsize(600, 400)
        self.configure(fg_color=BG)
        # Set window icon
        import os
        ico_path = str(PROJECT_DIR / "static" / "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass
        self.server_process = None
        self.server_running = False
        # Kill subprocess when window closes
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Kill orphaned server on startup
        self._kill_by_port()
        self._build_ui()
        self.after(500, self._refresh)

    def _build_ui(self):
        # Title bar
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkLabel(title_frame, text="claude-code-mobile",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=GLOW).pack(side="left")
        ctk.CTkLabel(title_frame, text="管理面板",
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT3).pack(side="left", padx=(8, 0), pady=(4, 0))

        # Two-column layout
        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=(8, 12))

        # Left column
        left = ctk.CTkFrame(columns, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Right column
        right = ctk.CTkFrame(columns, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # === LEFT: Service Status ===
        card1 = GlassCard(left)
        card1.pack(fill="x", pady=(0, 8))

        header1 = ctk.CTkFrame(card1, fg_color="transparent")
        header1.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header1, text="服务状态",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(side="left")
        self.status_dot = ctk.CTkLabel(header1, text="●", font=ctk.CTkFont(size=14), text_color=TEXT3)
        self.status_dot.pack(side="right")

        self.status_label = ctk.CTkLabel(card1, text="检测中...",
                                         font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT)
        self.status_label.pack(anchor="w", padx=12, pady=(0, 8))

        btn_frame = ctk.CTkFrame(card1, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.btn_start = GlowButton(btn_frame, text="▶ 启动", glow_color=GREEN, height=32, command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_stop = GlowButton(btn_frame, text="■ 停止", glow_color=RED, height=32, command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # === LEFT: Connection Info ===
        card2 = GlassCard(left)
        card2.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card2, text="连接信息", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(anchor="w", padx=12, pady=(10, 4))
        self._url_row(card2, "本地", "local_url")
        self._url_row(card2, "局域网", "lan_url")

        key_frame = ctk.CTkFrame(card2, fg_color="#0a0f1e", corner_radius=8)
        key_frame.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(key_frame, text="密钥", font=ctk.CTkFont(size=9),
                     text_color=TEXT3).pack(anchor="w", padx=8, pady=(6, 2))
        key_row = ctk.CTkFrame(key_frame, fg_color="transparent")
        key_row.pack(fill="x", padx=8, pady=(0, 6))
        self.key_entry = ctk.CTkEntry(key_row, font=ctk.CTkFont(family="Consolas", size=10),
                                       fg_color="#0a0f1e", border_color=CARD_BORDER,
                                       text_color=GLOW, height=28, show="*")
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        GlowButton(key_row, text="保存", width=45, height=26, glow_color=GREEN,
                   font=ctk.CTkFont(size=9), command=self._save_key).pack(side="right")
        GlowButton(key_row, text="复制", width=45, height=26, glow_color="#374151",
                   font=ctk.CTkFont(size=9), command=self._copy_key).pack(side="right", padx=(0, 3))

        action_frame = ctk.CTkFrame(card2, fg_color="transparent")
        action_frame.pack(fill="x", padx=8, pady=(2, 8))
        GlowButton(action_frame, text="打开面板", height=28, glow_color=ACCENT,
                   command=self._open_dashboard).pack(side="left", expand=True, fill="x", padx=(0, 3))
        GlowButton(action_frame, text="复制链接", height=28, glow_color="#374151",
                   command=self._copy_local_url).pack(side="left", expand=True, fill="x", padx=(3, 0))

        # === RIGHT: System Status ===
        card3 = GlassCard(right)
        card3.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card3, text="系统状态", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(anchor="w", padx=12, pady=(10, 4))

        sys_frame = ctk.CTkFrame(card3, fg_color="transparent")
        sys_frame.pack(fill="x", padx=12, pady=(0, 8))

        self.cpu_label = ctk.CTkLabel(sys_frame, text="CPU  --", font=ctk.CTkFont(size=11), text_color=TEXT2)
        self.cpu_label.pack(anchor="w")
        self.cpu_bar = ctk.CTkProgressBar(sys_frame, height=4, corner_radius=2)
        self.cpu_bar.pack(fill="x", pady=(2, 6))
        self.cpu_bar.set(0)

        self.mem_label = ctk.CTkLabel(sys_frame, text="内存  --", font=ctk.CTkFont(size=11), text_color=TEXT2)
        self.mem_label.pack(anchor="w")
        self.mem_bar = ctk.CTkProgressBar(sys_frame, height=4, corner_radius=2)
        self.mem_bar.pack(fill="x", pady=(2, 6))
        self.mem_bar.set(0)

        self.cc_label = ctk.CTkLabel(sys_frame, text="CC 进程  --", font=ctk.CTkFont(size=11), text_color=TEXT2)
        self.cc_label.pack(anchor="w")

        # === RIGHT: Logs ===
        card4 = GlassCard(right)
        card4.pack(fill="both", expand=True)

        ctk.CTkLabel(card4, text="日志", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(anchor="w", padx=12, pady=(10, 4))

        self.log_box = ctk.CTkTextbox(card4, height=80,
                                       font=ctk.CTkFont(family="Consolas", size=9),
                                       fg_color="#060910", text_color=TEXT3, corner_radius=6)
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.log_box.insert("0.0", "暂无日志")
        self.log_box.configure(state="disabled")

        # Footer
        ctk.CTkLabel(self, text="CCM v1.0", font=ctk.CTkFont(size=9), text_color=TEXT3).pack(pady=(0, 4))

    def _url_row(self, parent, label, attr):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=9), text_color=TEXT3, width=30).pack(side="left")
        lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family="Consolas", size=10), text_color=TEXT)
        lbl.pack(side="left", padx=(4, 0))
        setattr(self, attr, lbl)
        GlowButton(row, text="复制", width=40, height=22, glow_color="#374151",
                   font=ctk.CTkFont(size=9), command=lambda a=attr: self._copy_url(a)).pack(side="right")

    def _start(self):
        if self.server_running:
            return
        try:
            # Check if port is already in use
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', get_port()))
            sock.close()
            if result == 0:
                # Port in use, assume server is already running
                self.server_running = True
                self._refresh()
                return

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.server_process = subprocess.Popen(
                [sys.executable, "-u", "server.py"],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self.server_pid = self.server_process.pid
            self.server_running = True
            self._refresh()
            threading.Thread(target=self._monitor, daemon=True).start()
        except Exception as e:
            try:
                self.status_label.configure(text=f"启动失败: {e}", text_color=RED)
            except Exception:
                pass  # Label may not exist yet during early init

    def _on_close(self):
        self._kill_server()
        self.destroy()

    def _kill_server(self):
        """Kill server by handle AND by port (catches orphans)"""
        # Kill by subprocess handle
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=3)
            except Exception:
                try:
                    self.server_process.kill()
                except Exception:
                    pass
            self.server_process = None
        # Kill by port (catches orphaned processes)
        self._kill_by_port()

    def _kill_by_port(self):
        """Kill our own server process on the port (by PID match).
        Only kills the process if it matches the PID we started,
        to avoid killing unrelated processes on the same port.
        """
        try:
            import subprocess
            port = get_port()
            _si = subprocess.STARTUPINFO()
            _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0  # SW_HIDE
            # Find PID on port
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
                startupinfo=_si,
            )
            our_pid = getattr(self, 'server_pid', None)
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = int(parts[-1])
                    if pid > 0 and pid == our_pid:
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                       capture_output=True, timeout=5,
                                       creationflags=subprocess.CREATE_NO_WINDOW,
                                       startupinfo=_si)
        except Exception:
            pass  # Best-effort cleanup; port may not be in use

    def _stop(self):
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except Exception:
                try:
                    self.server_process.kill()
                except Exception:
                    pass
        self.server_running = False
        self.server_process = None
        self._refresh()

    def _monitor(self):
        try:
            if self.server_process:
                self.server_process.wait()
        except Exception:
            pass  # Process may already be terminated
        self.server_running = False
        self.server_process = None
        try:
            if self.winfo_exists():
                self.after(0, self._refresh)
        except Exception:
            pass  # Widget may be destroyed during shutdown

    def _refresh(self):
        try:
            if not self.winfo_exists():
                return
            port = get_port()
            lan_ip = get_lan_ip()
            api_key = get_api_key()

            if self.server_running:
                self.status_label.configure(text="服务运行中", text_color=GREEN)
                self.status_dot.configure(text_color=GREEN)
                self.btn_start.configure(state="disabled")
                self.btn_stop.configure(state="normal")
                self.local_url.configure(text=f"http://localhost:{port}")
                self.lan_url.configure(text=f"http://{lan_ip}:{port}")
            else:
                self.status_label.configure(text="服务已停止", text_color=TEXT3)
                self.status_dot.configure(text_color=TEXT3)
                self.btn_start.configure(state="normal")
                self.btn_stop.configure(state="disabled")
                self.local_url.configure(text="--")
                self.lan_url.configure(text="--")

            # Only update entry if it's empty, shows placeholder, or matches current key
            current_val = self.key_entry.get()
            if not current_val or current_val == "--" or current_val == api_key:
                self.key_entry.delete(0, "end")
                self.key_entry.insert(0, api_key)

            # System info
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0)
                mem = psutil.virtual_memory()
                cc = sum(1 for p in psutil.process_iter(["name"])
                        if "claude" in (p.info["name"] or "").lower())

                self.cpu_label.configure(text=f"CPU  {cpu:.1f}%")
                self.cpu_bar.set(cpu / 100)
                c = GREEN if cpu < 60 else YELLOW if cpu < 85 else RED
                self.cpu_bar.configure(progress_color=c)

                self.mem_label.configure(text=f"内存  {mem.percent:.1f}%  ({mem.used // 1024**3}/{mem.total // 1024**3} GB)")
                self.mem_bar.set(mem.percent / 100)
                c = GREEN if mem.percent < 60 else YELLOW if mem.percent < 85 else RED
                self.mem_bar.configure(progress_color=c)

                self.cc_label.configure(text=f"CC 进程  {cc} 个")
            except Exception:
                pass  # psutil may not be installed or process iteration fails

            # Logs
            try:
                log_dir = PROJECT_DIR / "logs"
                if log_dir.exists():
                    log_files = sorted(log_dir.glob("cc_*.log"), reverse=True)
                    if log_files:
                        with open(log_files[0], "r", encoding="utf-8", errors="replace") as f:
                            lines = list(deque(f, maxlen=15))
                        self.log_box.configure(state="normal")
                        self.log_box.delete("0.0", "end")
                        self.log_box.insert("0.0", "".join(lines))
                        self.log_box.configure(state="disabled")
            except Exception:
                pass  # Log files may not exist or be locked

            if self.server_running:
                self.after(3000, self._refresh)
        except Exception:
            pass  # Widget may be destroyed during refresh cycle

    def _open_dashboard(self):
        port = get_port()
        webbrowser.open(f"http://localhost:{port}")

    def _copy_key(self):
        key = self.key_entry.get().strip() or get_api_key()
        try:
            import pyperclip
            pyperclip.copy(key)
        except ImportError:
            self._clipboard_paste(key)

    def _save_key(self):
        """Save new key from the entry field, sync with running server if possible."""
        import urllib.request
        import json
        new_key = self.key_entry.get().strip()
        if not new_key:
            return
        if len(new_key) < 8:
            self.status_label.configure(text="密钥至少8位", text_color=YELLOW)
            self.after(2000, lambda: self._refresh())
            return
        try:
            # Read old key before overwriting (needed for server auth)
            old_key = get_api_key()
            API_KEY_FILE.write_text(new_key)
            # Try to sync with running server
            if self.server_running:
                try:
                    port = get_port()
                    req = urllib.request.Request(
                        f"http://localhost:{port}/api/auth/change-key",
                        data=json.dumps({
                            "current_key": old_key,
                            "new_key": new_key
                        }).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    urllib.request.urlopen(req, timeout=3)
                except Exception:
                    pass  # Server may not be running or key mismatch is OK; file is already updated
            self.status_label.configure(text="密钥已更新", text_color=GREEN)
            self.after(2000, lambda: self._refresh())
        except Exception as e:
            self.status_label.configure(text=f"保存失败: {e}", text_color=RED)
            self.after(3000, lambda: self._refresh())

    def _copy_url(self, attr):
        try:
            label = getattr(self, attr)
            url = label.cget("text")
            if url and url != "--":
                try:
                    import pyperclip
                    pyperclip.copy(url)
                except ImportError:
                    self._clipboard_paste(url)
        except Exception:
            pass  # Attribute may not exist or clipboard unavailable

    def _copy_local_url(self):
        self._copy_url("local_url")

    def _clipboard_paste(self, text):
        """Fallback clipboard using tkinter"""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass  # Clipboard may not be available in some environments


import atexit

def _cleanup_orphaned():
    """Kill any orphaned server process on exit.
    WARNING: This is a best-effort atexit handler that kills ANY process on the
    configured port. It cannot access Panel.server_pid since it runs outside
    the class. Use with caution if other services share the same port.
    """
    try:
        import subprocess
        port = get_port()
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0  # SW_HIDE
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                startupinfo=_si)
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                if pid > 0:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW,
                                   startupinfo=_si)
    except Exception:
        pass  # Best-effort cleanup; failure is non-critical

atexit.register(_cleanup_orphaned)

if __name__ == "__main__":
    try:
        app = Panel()
        app.mainloop()
    except Exception:
        pass
