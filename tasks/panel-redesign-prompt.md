# Panel Redesign Prompt — 方案 B: PyWebView

## 任务

将 `panel.py`（CustomTkinter 桌面管理面板）重写为 PyWebView 本地窗口 + HTML 仪表盘页面。

## 要求

- **本地直接启动**：双击 `CCM.pyw` 或 `启动.bat` 就能打开管理窗口，不需要先手动启动服务器
- **所有现有功能必须保留**，不能丢失任何一个
- **UI 风格**：复用现有 `static/index.html` 的 Liquid Glass 设计系统（CSS 变量、glassmorphism、深色主题）
- **日志区域要大**：占窗口 50-60% 面积，实时滚动，支持自动滚动到底部

## 现有功能清单（panel.py 当前实现）

1. **服务器启停**
   - 启动按钮：以 subprocess 方式运行 `python -u server.py`
   - 停止按钮：terminate 进程 + 按端口杀进程（netstat + taskkill）
   - 状态指示：绿色/灰色圆点 + 文字

2. **连接信息**
   - 本地 URL：`http://localhost:{port}`
   - 局域网 URL：`http://{lan_ip}:{port}`（通过 socket 连 8.8.8.8 获取本机 IP）
   - 复制按钮

3. **API 密钥管理**
   - 显示当前密钥（密码掩码）
   - 复制密钥
   - 修改密钥后自动保存到 `.api_key` 文件 + 同步到运行中的服务器（POST /api/auth/change-key）

4. **系统状态**
   - CPU 使用率（psutil）
   - 内存使用率 + 已用/总量 GB
   - CC 进程数量
   - 进度条颜色：绿(<60%) → 黄(<85%) → 红(>=85%)

5. **日志查看器**
   - 读取 `logs/cc_*.log` 文件（最近 3 个文件，最后 50 行）
   - 自动刷新（每 3 秒）
   - 等宽字体，深色背景

6. **快捷操作**
   - "打开面板"按钮：webbrowser.open 本地 URL
   - "复制链接"按钮

7. **窗口管理**
   - 关闭窗口时自动杀掉服务器进程（atexit + WM_DELETE_WINDOW）
   - 启动时杀掉端口上的遗留进程

## 技术方案

### 依赖
```
pywebview>=4.0
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
python-multipart>=0.0.6
pyyaml>=6.0
psutil>=5.9.0
```

### 文件结构
```
panel.py              # 重写：PyWebView 窗口 + JS-Python bridge
static/panel.html     # 新增：管理面板 HTML 页面
CCM.pyw              # 不变：静默启动 panel.py
启动.bat / 启动.vbs  # 不变
```

### 实现要点

#### panel.py 核心逻辑
```python
import webview
import threading
import subprocess
import psutil
import socket
import os
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).parent

class PanelAPI:
    """JS-Python bridge API，供 panel.html 的 JavaScript 调用"""

    def __init__(self):
        self.server_process = None
        self.server_running = False

    def start_server(self):
        """启动服务器，返回 {success, message}"""

    def stop_server(self):
        """停止服务器，返回 {success, message}"""

    def get_status(self):
        """返回服务器状态 + 系统信息
        返回: {
            server_running: bool,
            local_url: str,
            lan_url: str,
            cpu_percent: float,
            memory_percent: float,
            memory_used_gb: float,
            memory_total_gb: float,
            cc_count: int,
            api_key: str
        }
        """

    def get_logs(self):
        """返回最近日志内容（最近3个文件，最后50行）
        返回: {logs: str}
        """

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""

    def save_api_key(self, new_key):
        """保存新密钥到文件 + 同步服务器
        返回: {success, message}
        """

    def open_browser(self):
        """打开浏览器访问面板 URL"""

    def kill_server_by_port(self):
        """按端口杀掉遗留进程"""

# PyWebView 窗口
api = PanelAPI()
window = webview.create_window(
    'claude-code-mobile',
    url=str(PROJECT_DIR / 'static' / 'panel.html'),
    js_api=api,
    width=800,
    height=600,
    min_size=(600, 400),
    background_color='#080b14'
)
webview.start(debug=False)
```

#### static/panel.html 核心结构
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        /* 复用 Liquid Glass CSS 变量和设计系统 */
        :root { --bg: #080b14; --card-bg: #0d1220; ... }
        /* 布局：上半部分控制面板 + 下半部分日志 */
    </style>
</head>
<body>
    <!-- 顶部：标题栏 -->
    <!-- 左侧：服务器控制 + 连接信息 + 密钥管理 -->
    <!-- 右侧：系统状态 -->
    <!-- 底部大区域：日志面板 -->
    <script>
        // 调用 pywebview.api.xxx() 与 Python 通信
        // 定时刷新状态和日志
    </script>
</body>
</html>
```

### JS-Python Bridge 调用方式
```javascript
// JavaScript 调用 Python 方法
const status = await pywebview.api.get_status();
const result = await pywebview.api.start_server();
const logs = await pywebview.api.get_logs();
```

## 当前项目结构

```
claude-code-mobile/
├── CCM.pyw                    # 静默启动入口（不改）
├── panel.py                   # 要重写的文件
├── server.py                  # FastAPI 服务器入口（不改）
├── config.yaml                # 配置（不改）
├── requirements.txt           # 需要加 pywebview
├── .api_key                   # API 密钥文件
├── static/
│   ├── index.html             # Web 面板前端（不改）
│   ├── panel.html             # 新增：桌面管理面板页面
│   ├── icon.ico / icon.png    # 图标
├── cc_monitor/                # 后端模块（不改）
├── logs/                      # 日志目录
├── 启动.bat / 启动.vbs        # 启动脚本（不改）
```

## 注意事项

1. `CCM.pyw` 和 `启动.bat`/`启动.vbs` 不需要改，它们只是调用 `panel.py`
2. `server.py` 不需要改
3. `cc_monitor/` 目录下的文件不需要改
4. `static/index.html` 不需要改（那是 Web 面板，不是桌面管理面板）
5. 只需要改 `panel.py`（重写）和新增 `static/panel.html`
6. `requirements.txt` 加 `pywebview>=4.0`
7. 日志区域要大，这是用户最关注的
8. 服务器启停逻辑要和现有 `panel.py` 一致（subprocess + 端口检测 + atexit 清理）
9. 密钥修改后要同步到运行中的服务器（POST /api/auth/change-key）
10. 系统状态每 3 秒自动刷新
