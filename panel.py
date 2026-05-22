"""CC Remote Dashboard — 原生桌面管理面板"""
import os
import sys
import subprocess
import threading
from pathlib import Path

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PROJECT_DIR = Path(__file__).parent
API_KEY_FILE = PROJECT_DIR / ".api_key"
CONFIG_FILE = PROJECT_DIR / "config.yaml"


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


class Panel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CC Remote Dashboard")
        self.geometry("480x680")
        self.minsize(400, 500)
        self.configure(fg_color="#0f1117")
        self.server_process = None
        self.server_running = False
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(scroll, text="CC Remote Dashboard",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#60a5fa").pack(pady=(0, 4))
        ctk.CTkLabel(scroll, text="管理面板",
                     font=ctk.CTkFont(size=11),
                     text_color="#6b7280").pack(pady=(0, 16))

        # Service Status
        ctk.CTkLabel(scroll, text="服务状态",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#6b7280").pack(anchor="w", pady=(8, 6))
        self.status_label = ctk.CTkLabel(scroll, text="检测中...",
                                         font=ctk.CTkFont(size=13, weight="bold"))
        self.status_label.pack(anchor="w", pady=(0, 8))

        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 16))
        self.btn_start = ctk.CTkButton(btn_frame, text="启动服务", height=36,
                                        fg_color="#22c55e", hover_color="#16a34a",
                                        command=self._start)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_stop = ctk.CTkButton(btn_frame, text="停止服务", height=36,
                                       fg_color="#ef4444", hover_color="#dc2626",
                                       command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Connection Info
        ctk.CTkLabel(scroll, text="连接信息",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#6b7280").pack(anchor="w", pady=(8, 6))

        f1 = ctk.CTkFrame(scroll, fg_color="#1a1d27", corner_radius=8)
        f1.pack(fill="x", pady=2)
        ctk.CTkLabel(f1, text="访问地址", font=ctk.CTkFont(size=11),
                     text_color="#9ca3af").pack(side="left", padx=10, pady=6)
        self.url_label = ctk.CTkLabel(f1, text="--", font=ctk.CTkFont(size=12, weight="bold"),
                                      text_color="#e4e4e7")
        self.url_label.pack(side="right", padx=10, pady=6)

        f2 = ctk.CTkFrame(scroll, fg_color="#1a1d27", corner_radius=8)
        f2.pack(fill="x", pady=2)
        ctk.CTkLabel(f2, text="API 密钥", font=ctk.CTkFont(size=11),
                     text_color="#9ca3af").pack(side="left", padx=10, pady=6)
        self.key_label = ctk.CTkLabel(f2, text="--", font=ctk.CTkFont(size=12, weight="bold"),
                                      text_color="#e4e4e7")
        self.key_label.pack(side="right", padx=10, pady=6)

        ctk.CTkButton(scroll, text="复制密钥", height=28, width=100,
                       fg_color="#374151", hover_color="#4b5563",
                       command=self._copy_key).pack(anchor="e", pady=(0, 16))

        # System Status
        ctk.CTkLabel(scroll, text="系统状态",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#6b7280").pack(anchor="w", pady=(8, 6))

        sys_f = ctk.CTkFrame(scroll, fg_color="transparent")
        sys_f.pack(fill="x", pady=(0, 16))

        self.cpu_label = ctk.CTkLabel(sys_f, text="CPU: --", font=ctk.CTkFont(size=12))
        self.cpu_label.pack(anchor="w")
        self.cpu_bar = ctk.CTkProgressBar(sys_f, height=6)
        self.cpu_bar.pack(fill="x", pady=(2, 8))
        self.cpu_bar.set(0)

        self.mem_label = ctk.CTkLabel(sys_f, text="内存: --", font=ctk.CTkFont(size=12))
        self.mem_label.pack(anchor="w")
        self.mem_bar = ctk.CTkProgressBar(sys_f, height=6)
        self.mem_bar.pack(fill="x", pady=(2, 8))
        self.mem_bar.set(0)

        self.cc_label = ctk.CTkLabel(sys_f, text="CC 进程: --", font=ctk.CTkFont(size=12))
        self.cc_label.pack(anchor="w")

        # Logs
        ctk.CTkLabel(scroll, text="最近日志",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#6b7280").pack(anchor="w", pady=(8, 6))

        self.log_box = ctk.CTkTextbox(scroll, height=120,
                                       font=ctk.CTkFont(family="Consolas", size=10),
                                       fg_color="#0a0e1a", text_color="#6b7280")
        self.log_box.pack(fill="x", pady=(0, 16))
        self.log_box.insert("0.0", "暂无日志")
        self.log_box.configure(state="disabled")

        ctk.CTkLabel(scroll, text="CC Remote v1.0",
                     font=ctk.CTkFont(size=10),
                     text_color="#374151").pack(pady=(8, 0))

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
            self.status_label.configure(text=f"启动失败: {e}", text_color="#ef4444")

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
        if self.server_process:
            self.server_process.wait()
        self.server_running = False
        self.server_process = None
        self.after(0, self._refresh)

    def _refresh(self):
        port = get_port()
        api_key = get_api_key()
        if self.server_running:
            self.status_label.configure(text="● 服务运行中", text_color="#22c55e")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.url_label.configure(text=f"http://localhost:{port}")
        else:
            self.status_label.configure(text="○ 服务已停止", text_color="#6b7280")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.url_label.configure(text="--")
        self.key_label.configure(text=api_key[:12] + "..." if len(api_key) > 12 else api_key)
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            cc = sum(1 for p in psutil.process_iter(["name"]) if "claude" in (p.info["name"] or "").lower())
            self.cpu_label.configure(text=f"CPU: {cpu:.1f}%")
            self.cpu_bar.set(cpu / 100)
            color = "#22c55e" if cpu < 60 else "#f59e0b" if cpu < 85 else "#ef4444"
            self.cpu_bar.configure(progress_color=color)
            self.mem_label.configure(text=f"内存: {mem.percent:.1f}% ({mem.used // 1024**3}GB / {mem.total // 1024**3}GB)")
            self.mem_bar.set(mem.percent / 100)
            color = "#22c55e" if mem.percent < 60 else "#f59e0b" if mem.percent < 85 else "#ef4444"
            self.mem_bar.configure(progress_color=color)
            self.cc_label.configure(text=f"CC 进程: {cc} 个")
        except ImportError:
            pass
        try:
            log_dir = PROJECT_DIR / "logs"
            log_files = sorted(log_dir.glob("cc_*.log"), reverse=True) if log_dir.exists() else []
            if log_files:
                with open(log_files[0], "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()[-20:]
                self.log_box.configure(state="normal")
                self.log_box.delete("0.0", "end")
                self.log_box.insert("0.0", "".join(lines))
                self.log_box.configure(state="disabled")
        except Exception:
            pass
        if self.server_running:
            self.after(3000, self._refresh)

    def _copy_key(self):
        try:
            import pyperclip
            pyperclip.copy(get_api_key())
        except ImportError:
            import tkinter.simpledialog as sd
            # Fallback: select-all in key label
            pass


if __name__ == "__main__":
    app = Panel()
    app.mainloop()
