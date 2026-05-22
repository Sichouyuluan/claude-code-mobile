"""CC Remote Dashboard — 桌面管理面板"""
import os
import sys
import subprocess
import threading
import webbrowser
from pathlib import Path

import webview

PROJECT_DIR = Path(__file__).parent
API_KEY_FILE = PROJECT_DIR / ".api_key"
CONFIG_FILE = PROJECT_DIR / "config.yaml"
LOG_DIR = PROJECT_DIR / "logs"

server_process = None
server_running = False


def get_api_key():
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    return "未生成"


def get_port():
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("port", 8001)
    except Exception:
        return 8001


def get_system_info():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        cc_count = 0
        for proc in psutil.process_iter(["name"]):
            try:
                name = (proc.info["name"] or "").lower()
                if "claude" in name:
                    cc_count += 1
            except Exception:
                pass
        return {"cpu": cpu, "mem_percent": mem.percent,
                "mem_used": round(mem.used / 1024**3, 1),
                "mem_total": round(mem.total / 1024**3, 1),
                "cc_count": cc_count}
    except ImportError:
        return {"cpu": 0, "mem_percent": 0, "mem_used": 0, "mem_total": 0, "cc_count": 0}


def get_recent_logs(n=20):
    if not LOG_DIR.exists():
        return []
    log_files = sorted(LOG_DIR.glob("cc_*.log"), reverse=True)
    if not log_files:
        return []
    try:
        with open(log_files[0], "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except Exception:
        return []


PANEL_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;background:linear-gradient(135deg,#0a0e1a 0%,#0d1526 30%,#111d35 60%,#0a0e1a 100%);color:#e0e0e0;min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 20% 50%,rgba(59,130,246,0.08) 0%,transparent 50%),radial-gradient(ellipse at 80% 20%,rgba(139,92,246,0.06) 0%,transparent 50%),radial-gradient(ellipse at 50% 80%,rgba(6,182,212,0.05) 0%,transparent 50%);animation:bgFloat 20s ease-in-out infinite;z-index:0;pointer-events:none}
@keyframes bgFloat{0%,100%{transform:translate(0,0) rotate(0deg)}33%{transform:translate(2%,-1%) rotate(1deg)}66%{transform:translate(-1%,1%) rotate(-1deg)}}
.container{position:relative;z-index:1;max-width:520px;margin:0 auto;padding:24px 20px}
.header{text-align:center;margin-bottom:28px}
.header h1{font-size:22px;font-weight:700;background:linear-gradient(135deg,#60a5fa,#a78bfa,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
.header .subtitle{font-size:12px;color:rgba(255,255,255,0.4);letter-spacing:2px;text-transform:uppercase}
.glass{background:rgba(255,255,255,0.04);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:20px;margin-bottom:16px;transition:all 0.3s ease}
.glass:hover{background:rgba(255,255,255,0.06);border-color:rgba(255,255,255,0.12)}
.glass-title{font-size:11px;font-weight:600;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px}
.status-row{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.status-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.status-dot.running{background:#22c55e;box-shadow:0 0 12px rgba(34,197,94,0.5);animation:pulse 2s infinite}
.status-dot.stopped{background:#6b7280}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.status-text{font-size:15px;font-weight:500}
.btn-row{display:flex;gap:10px;margin-top:12px}
.btn{flex:1;padding:12px 16px;border:none;border-radius:12px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s;font-family:inherit}
.btn-primary{background:linear-gradient(135deg,#3b82f6,#2563eb);color:white;box-shadow:0 4px 15px rgba(59,130,246,0.3)}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(59,130,246,0.4)}
.btn-danger{background:linear-gradient(135deg,#ef4444,#dc2626);color:white;box-shadow:0 4px 15px rgba(239,68,68,0.3)}
.btn-danger:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(239,68,68,0.4)}
.btn-glass{background:rgba(255,255,255,0.06);color:#e0e0e0;border:1px solid rgba(255,255,255,0.1)}
.btn-glass:hover{background:rgba(255,255,255,0.1)}
.btn:disabled{opacity:0.4;cursor:not-allowed;transform:none !important}
.info-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04)}
.info-row:last-child{border-bottom:none}
.info-label{font-size:12px;color:rgba(255,255,255,0.5)}
.info-value{font-size:13px;font-weight:500;display:flex;align-items:center;gap:8px}
.copy-btn{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);color:rgba(255,255,255,0.6);padding:4px 10px;border-radius:6px;font-size:11px;cursor:pointer;transition:all 0.2s;font-family:inherit}
.copy-btn:hover{background:rgba(255,255,255,0.15);color:white}
.copy-btn.copied{background:rgba(34,197,94,0.2);color:#22c55e;border-color:rgba(34,197,94,0.3)}
.stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.stat-item{background:rgba(255,255,255,0.03);border-radius:10px;padding:12px;text-align:center}
.stat-value{font-size:22px;font-weight:700;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-label{font-size:11px;color:rgba(255,255,255,0.4);margin-top:2px}
.progress-bar{height:4px;background:rgba(255,255,255,0.06);border-radius:2px;margin-top:8px;overflow:hidden}
.progress-fill{height:100%;border-radius:2px;transition:width 0.5s ease,background 0.3s}
.progress-fill.low{background:#22c55e}
.progress-fill.mid{background:#f59e0b}
.progress-fill.high{background:#ef4444}
.log-box{background:rgba(0,0,0,0.3);border-radius:10px;padding:12px;max-height:160px;overflow-y:auto;font-family:'SF Mono','Fira Code',monospace;font-size:11px;line-height:1.6;color:rgba(255,255,255,0.5)}
.log-box::-webkit-scrollbar{width:4px}
.log-box::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}
.log-line{white-space:pre-wrap;word-break:break-all}
.log-line.error{color:#ef4444}
.log-line.warn{color:#f59e0b}
.footer{text-align:center;margin-top:20px;font-size:11px;color:rgba(255,255,255,0.2)}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>CC Remote Dashboard</h1>
    <div class="subtitle">管理面板</div>
  </div>
  <div class="glass">
    <div class="glass-title">服务状态</div>
    <div class="status-row">
      <div class="status-dot" id="status-dot"></div>
      <span class="status-text" id="status-text">检测中...</span>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-start" onclick="startServer()">启动服务</button>
      <button class="btn btn-danger" id="btn-stop" onclick="stopServer()" disabled>停止服务</button>
    </div>
  </div>
  <div class="glass">
    <div class="glass-title">连接信息</div>
    <div class="info-row">
      <span class="info-label">访问地址</span>
      <span class="info-value"><span id="url-text">--</span><button class="copy-btn" onclick="copyText('url-text')">复制</button></span>
    </div>
    <div class="info-row">
      <span class="info-label">API 密钥</span>
      <span class="info-value"><span id="key-text">--</span><button class="copy-btn" onclick="copyText('key-text')">复制</button></span>
    </div>
    <div class="info-row">
      <span class="info-label">端口</span>
      <span class="info-value" id="port-text">8001</span>
    </div>
    <div class="btn-row" style="margin-top:12px;">
      <button class="btn btn-glass" onclick="openDashboard()">打开面板</button>
      <button class="btn btn-glass" onclick="openTunnel()">启动隧道</button>
    </div>
  </div>
  <div class="glass">
    <div class="glass-title">系统状态</div>
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-value" id="cpu-val">--</div>
        <div class="stat-label">CPU</div>
        <div class="progress-bar"><div class="progress-fill low" id="cpu-bar" style="width:0%"></div></div>
      </div>
      <div class="stat-item">
        <div class="stat-value" id="mem-val">--</div>
        <div class="stat-label">内存</div>
        <div class="progress-bar"><div class="progress-fill low" id="mem-bar" style="width:0%"></div></div>
      </div>
    </div>
    <div class="info-row" style="margin-top:10px;">
      <span class="info-label">CC 进程</span>
      <span class="info-value" id="cc-count">--</span>
    </div>
  </div>
  <div class="glass">
    <div class="glass-title">最近日志</div>
    <div class="log-box" id="log-box">暂无日志</div>
  </div>
  <div class="footer">CC Remote Dashboard v1.0</div>
</div>
<script>
function updateStatus(){try{const i=pywebview.api.get_status();const d=document.getElementById('status-dot');const t=document.getElementById('status-text');const bs=document.getElementById('btn-start');const bp=document.getElementById('btn-stop');if(i.running){d.className='status-dot running';t.textContent='服务运行中';t.style.color='#22c55e';bs.disabled=true;bp.disabled=false;document.getElementById('url-text').textContent='http://localhost:'+i.port}else{d.className='status-dot stopped';t.textContent='服务已停止';t.style.color='#9ca3af';bs.disabled=false;bp.disabled=true;document.getElementById('url-text').textContent='--'}document.getElementById('key-text').textContent=i.api_key;document.getElementById('port-text').textContent=i.port}catch(e){}}
function updateSystem(){try{const s=pywebview.api.get_system();document.getElementById('cpu-val').textContent=s.cpu+'%';document.getElementById('mem-val').textContent=s.mem_percent+'%';document.getElementById('cc-count').textContent=s.cc_count+' 个';const cb=document.getElementById('cpu-bar');cb.style.width=s.cpu+'%';cb.className='progress-fill '+(s.cpu<60?'low':s.cpu<85?'mid':'high');const mb=document.getElementById('mem-bar');mb.style.width=s.mem_percent+'%';mb.className='progress-fill '+(s.mem_percent<60?'low':s.mem_percent<85?'mid':'high')}catch(e){}}
function updateLogs(){try{const l=pywebview.api.get_logs();const b=document.getElementById('log-box');if(l.length===0){b.innerHTML='暂无日志';return}b.innerHTML=l.map(x=>{let c='log-line';if(x.includes('ERROR')||x.includes('error'))c+=' error';else if(x.includes('WARNING')||x.includes('warn'))c+=' warn';return'<div class="'+c+'">'+x.replace(/</g,'&lt;')+'</div>'}).join('');b.scrollTop=b.scrollHeight}catch(e){}}
function startServer(){pywebview.api.start_server();setTimeout(updateStatus,1500)}
function stopServer(){pywebview.api.stop_server();setTimeout(updateStatus,1000)}
function openDashboard(){pywebview.api.open_dashboard()}
function openTunnel(){pywebview.api.open_tunnel()}
function copyText(id){const t=document.getElementById(id).textContent;if(t&&t!=='--'){navigator.clipboard.writeText(t).then(()=>{const b=document.getElementById(id).parentElement.querySelector('.copy-btn');b.textContent='已复制';b.classList.add('copied');setTimeout(()=>{b.textContent='复制';b.classList.remove('copied')},1500)})}}
setTimeout(()=>{updateStatus();updateSystem();updateLogs()},500);
setInterval(updateSystem,3000);setInterval(updateLogs,5000);setInterval(updateStatus,3000);
</script>
</body>
</html>"""


class PanelAPI:
    def start_server(self):
        global server_process, server_running
        if server_running:
            return
        python = sys.executable
        try:
            server_process = subprocess.Popen(
                [python, "-u", "server.py"],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            server_running = True
            threading.Thread(target=self._monitor, daemon=True).start()
        except Exception as e:
            pass

    def _monitor(self):
        global server_process, server_running
        if server_process:
            server_process.wait()
        server_running = False
        server_process = None

    def stop_server(self):
        global server_process, server_running
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
        server_running = False
        server_process = None

    def get_status(self):
        return {"running": server_running, "port": get_port(), "api_key": get_api_key()}

    def get_system(self):
        return get_system_info()

    def get_logs(self):
        return get_recent_logs(30)

    def open_dashboard(self):
        webbrowser.open(f"http://localhost:{get_port()}")

    def open_tunnel(self):
        subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{get_port()}"],
            cwd=str(PROJECT_DIR),
        )


def main():
    api = PanelAPI()
    window = webview.create_window(
        "CC Remote Dashboard",
        html=PANEL_HTML,
        js_api=api,
        width=560, height=720,
        resizable=True,
        background_color="#0a0e1a",
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
