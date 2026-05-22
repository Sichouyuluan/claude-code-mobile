"""CC Remote Dashboard — 原生桌面管理面板 (Liquid Glass)"""
import os
import sys
import subprocess
import threading
import socket
import webbrowser
from pathlib import Path

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
        return API_KEY_FILE.read_text().strip()
    except Exception:
        return "未生成"


def get_port():
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f).get("port", 8001)
    except Exception:
        return 8001


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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
        self.title("CC Remote Dashboard")
        self.geometry("500x750")
        self.minsize(420, 600)
        self.configure(fg_color=BG)
        self.server_process = None
        self.server_running = False
        self._build_ui()
        self.after(500, self._refresh)

    def _build_ui(self):
        # Main scrollable frame
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                              scrollbar_button_color=TEXT3,
                                              scrollbar_button_hover_color=TEXT2)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # Title with glow
        title_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(title_frame, text="CC",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=GLOW).pack(side="left")
        ctk.CTkLabel(title_frame, text="Remote Dashboard",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=TEXT).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(title_frame, text="管理面板",
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT3).pack(side="left", padx=(8, 0), pady=(8, 0))

        # === Service Status Card ===
        card1 = GlassCard(self.scroll)
        card1.pack(fill="x", pady=(0, 12))

        header1 = ctk.CTkFrame(card1, fg_color="transparent")
        header1.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(header1, text="服务状态",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(side="left")

        self.status_dot = ctk.CTkLabel(header1, text="●",
                                        font=ctk.CTkFont(size=16),
                                        text_color=TEXT3)
        self.status_dot.pack(side="right")

        self.status_label = ctk.CTkLabel(card1, text="检测中...",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         text_color=TEXT)
        self.status_label.pack(anchor="w", padx=16, pady=(0, 10))

        btn_frame = ctk.CTkFrame(card1, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 14))

        self.btn_start = GlowButton(btn_frame, text="▶  启动服务",
                                     glow_color=GREEN, height=38,
                                     command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_stop = GlowButton(btn_frame, text="■  停止服务",
                                    glow_color=RED, height=38,
                                    command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # === Connection Info Card ===
        card2 = GlassCard(self.scroll)
        card2.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(card2, text="连接信息",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(anchor="w", padx=16, pady=(14, 8))

        # Local URL
        self._url_row(card2, "本地地址", "local_url")
        # LAN URL
        self._url_row(card2, "局域网地址", "lan_url")

        # API Key
        key_frame = ctk.CTkFrame(card2, fg_color="#0a0f1e", corner_radius=8)
        key_frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(key_frame, text="密钥",
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT3).pack(anchor="w", padx=10, pady=(6, 0))
        key_row = ctk.CTkFrame(key_frame, fg_color="transparent")
        key_row.pack(fill="x", padx=10, pady=(0, 8))
        self.key_label = ctk.CTkLabel(key_row, text="--",
                                       font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                                       text_color=GLOW)
        self.key_label.pack(side="left")
        GlowButton(key_row, text="复制", width=50, height=26,
                   glow_color="#374151",
                   font=ctk.CTkFont(size=10),
                   command=self._copy_key).pack(side="right")

        # Action buttons
        action_frame = ctk.CTkFrame(card2, fg_color="transparent")
        action_frame.pack(fill="x", padx=12, pady=(4, 14))

        GlowButton(action_frame, text="打开面板", height=32,
                   glow_color=ACCENT,
                   command=self._open_dashboard).pack(side="left", expand=True, fill="x", padx=(0, 4))
        GlowButton(action_frame, text="复制链接", height=32,
                   glow_color="#374151",
                   command=self._copy_local_url).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # === System Status Card ===
        card3 = GlassCard(self.scroll)
        card3.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(card3, text="系统状态",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(anchor="w", padx=16, pady=(14, 8))

        sys_frame = ctk.CTkFrame(card3, fg_color="transparent")
        sys_frame.pack(fill="x", padx=16, pady=(0, 14))

        self.cpu_label = ctk.CTkLabel(sys_frame, text="CPU  --",
                                       font=ctk.CTkFont(size=12),
                                       text_color=TEXT2)
        self.cpu_label.pack(anchor="w")
        self.cpu_bar = ctk.CTkProgressBar(sys_frame, height=5, corner_radius=3)
        self.cpu_bar.pack(fill="x", pady=(3, 10))
        self.cpu_bar.set(0)

        self.mem_label = ctk.CTkLabel(sys_frame, text="内存  --",
                                       font=ctk.CTkFont(size=12),
                                       text_color=TEXT2)
        self.mem_label.pack(anchor="w")
        self.mem_bar = ctk.CTkProgressBar(sys_frame, height=5, corner_radius=3)
        self.mem_bar.pack(fill="x", pady=(3, 10))
        self.mem_bar.set(0)

        self.cc_label = ctk.CTkLabel(sys_frame, text="CC 进程  --",
                                      font=ctk.CTkFont(size=12),
                                      text_color=TEXT2)
        self.cc_label.pack(anchor="w")

        # === Logs Card ===
        card4 = GlassCard(self.scroll)
        card4.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(card4, text="最近日志",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT3).pack(anchor="w", padx=16, pady=(14, 8))

        self.log_box = ctk.CTkTextbox(card4, height=100,
                                       font=ctk.CTkFont(family="Consolas", size=10),
                                       fg_color="#060910", text_color=TEXT3,
                                       corner_radius=8)
        self.log_box.pack(fill="x", padx=12, pady=(0, 12))
        self.log_box.insert("0.0", "暂无日志")
        self.log_box.configure(state="disabled")

        # Footer
        ctk.CTkLabel(self.scroll, text="CC Remote v1.0",
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT3).pack(pady=(4, 0))

    def _url_row(self, parent, label, attr):
        frame = ctk.CTkFrame(parent, fg_color="#0a0f1e", corner_radius=8)
        frame.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(frame, text=label,
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT3).pack(anchor="w", padx=10, pady=(6, 0))
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        lbl = ctk.CTkLabel(row, text="--",
                            font=ctk.CTkFont(family="Consolas", size=11),
                            text_color=TEXT)
        lbl.pack(side="left")
        setattr(self, attr, lbl)
        GlowButton(row, text="复制", width=50, height=26,
                   glow_color="#374151",
                   font=ctk.CTkFont(size=10),
                   command=lambda a=attr: self._copy_url(a)).pack(side="right")

    def _start(self):
        if self.server_running:
            return
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.server_process = subprocess.Popen(
                [sys.executable, "-u", "server.py"],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self.server_running = True
            self._refresh()
            threading.Thread(target=self._monitor, daemon=True).start()
        except Exception as e:
            self.status_label.configure(text=f"启动失败: {e}", text_color=RED)

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
            pass
        self.server_running = False
        self.server_process = None
        try:
            self.after(0, self._refresh)
        except Exception:
            pass

    def _refresh(self):
        try:
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

            display_key = api_key[:16] + "..." if len(api_key) > 16 else api_key
            self.key_label.configure(text=display_key)

            # System info
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=0.1)
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
                pass

            # Logs
            try:
                log_dir = PROJECT_DIR / "logs"
                if log_dir.exists():
                    log_files = sorted(log_dir.glob("cc_*.log"), reverse=True)
                    if log_files:
                        with open(log_files[0], "r", encoding="utf-8", errors="replace") as f:
                            lines = f.readlines()[-15:]
                        self.log_box.configure(state="normal")
                        self.log_box.delete("0.0", "end")
                        self.log_box.insert("0.0", "".join(lines))
                        self.log_box.configure(state="disabled")
            except Exception:
                pass

            if self.server_running:
                self.after(3000, self._refresh)
        except Exception:
            pass

    def _open_dashboard(self):
        port = get_port()
        webbrowser.open(f"http://localhost:{port}")

    def _copy_key(self):
        try:
            import pyperclip
            pyperclip.copy(get_api_key())
        except ImportError:
            self._clipboard_paste(get_api_key())

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
            pass

    def _copy_local_url(self):
        self._copy_url("local_url")

    def _clipboard_paste(self, text):
        """Fallback clipboard using tkinter"""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        app = Panel()
        app.mainloop()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to exit...")
