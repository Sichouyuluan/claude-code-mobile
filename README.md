# claude-code-mobile

通过手机或任意设备的浏览器，远程监控和管理你的 Claude Code 会话。

[English](#english) | 中文

---

## 这是什么

claude-code-mobile 是一个本地 Web 服务，运行在你的电脑上。它读取 Claude Code 的会话数据（`~/.claude/` 目录），通过网页界面展示出来。你可以用手机、平板、或任何设备的浏览器访问它，远程查看对话、发送消息、监控状态。

**核心能力：**
- 从手机浏览器远程给 Claude Code 发消息，自动匹配会话模型
- 实时流式显示 Claude 的完整输出（思考过程、工具调用、代码回复）
- 双模式切换：对话模式（消息列表）+ 终端模式（实时流式输出）
- 桌面管理面板：一键启停服务器、查看系统状态、实时日志
- 完整安全体系：API 密钥认证、速率限制、攻击检测

---

## 功能详解

### 网页面板（手机/浏览器访问）

| 功能 | 说明 |
|------|------|
| 项目列表 | 自动扫描 `~/.claude/projects/` 下的所有项目 |
| 会话列表 | 每个项目下的所有对话，显示最近活动时间和消息数 |
| 对话查看 | 分层渲染，按轮次折叠，支持 thinking 内容、工具调用详情 |
| 远程发消息 | 输入框发送消息，自动检测会话使用的模型，通过 CLI 注入 |
| 图片上传 | 支持上传图片发送给 Claude 分析 |
| 搜索过滤 | 按关键词搜索会话内容 |
| SSE 实时推送 | 新消息自动推送，无需手动刷新 |
| 会话 ID 显示 | 顶部显示完整会话 ID，一键复制 |
| 代码复制按钮 | 代码块右上角一键复制 |
| XSS 防护 | 所有 URL 经过安全过滤 |

### 终端模式（WebSocket 流式）

点击会话页面的浮动按钮切换到终端模式：

| 功能 | 说明 |
|------|------|
| 实时流式输出 | Claude CLI 的完整输出逐行推送到网页 |
| 思考过程 | 折叠显示 Claude 的 thinking 内容 |
| 工具调用 | 显示工具名称和输入参数（Read、Bash、Edit 等） |
| 工具结果 | 折叠显示工具执行结果 |
| 费用统计 | 底部显示本次对话的 API 花费 |
| 自动滚动 | 新内容自动滚动到底部 |

### 桌面管理面板（电脑本地）

双击 `CCM.pyw` 或 `启动.bat` 打开：

| 功能 | 说明 |
|------|------|
| 服务器启停 | 一键启动/停止 FastAPI 后端服务 |
| 连接信息 | 显示本地 URL 和局域网 URL，一键复制 |
| API 密钥 | 显示/修改密钥，自动保存并同步到运行中的服务器 |
| 系统状态 | CPU 使用率、内存使用率、CC 进程数，进度条实时更新 |
| 日志查看 | 读取所有日志文件，每 3 秒自动刷新 |

---

## 安装

### 前提条件

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) 已安装并配置
- Node.js（Claude Code CLI 依赖）

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/Sichouyuluan/claude-code-mobile.git
cd claude-code-mobile

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动桌面面板（推荐）
python panel.py
# 或双击 CCM.pyw / 启动.bat

# 4. 或直接启动服务器
python server.py
```

### 依赖列表

| 包 | 版本 | 用途 |
|---|---|---|
| fastapi | >=0.100.0 | Web 框架 |
| uvicorn | >=0.23.0 | ASGI 服务器 |
| python-multipart | >=0.0.6 | 文件上传 |
| pyyaml | >=6.0 | 配置文件解析 |
| psutil | >=5.9.0 | 系统监控 |
| pywebview | >=4.0 | 桌面管理面板 |

---

## 使用方法

### 启动服务器

**方式一：桌面面板（推荐）**

```
双击 CCM.pyw 或 启动.bat
```

面板会自动：
1. 杀掉端口上的残留进程
2. 生成或读取 API 密钥
3. 显示面板界面

点击"启动"按钮开启服务器。

**方式二：命令行**

```bash
python server.py
```

服务器默认监听 `0.0.0.0:8001`。

### 访问 Web 面板

1. 打开手机/电脑浏览器
2. 输入 `http://你的电脑IP:8001`
3. 输入 API 密钥登录
4. 首次访问会自动提示密钥

**获取局域网 IP：**
- Windows: `ipconfig` → 无线局域网适配器 → IPv4 地址
- macOS/Linux: `ifconfig` 或 `ip addr`

### 对话模式操作

1. 左侧选择项目 → 选择会话
2. 消息列表显示所有历史消息
3. 底部输入框输入消息，点发送或按 Enter
4. 新消息通过 SSE 实时推送显示
5. 点击代码块右上角复制按钮复制代码
6. 点击 thinking 块展开/折叠思考过程

### 终端模式操作

1. 进入会话后，点击输入框上方的圆形 **CLI** 按钮
2. 切换到终端模式，按钮变为 **会话**
3. 输入消息发送，Claude 的完整输出实时流式显示
4. 包括：思考过程（紫色）、工具调用（蓝色）、执行结果（绿色）、回复文字
5. 底部状态栏显示连接状态和 API 花费
6. 点击 **会话** 按钮切回对话模式

### 桌面面板操作

| 按钮 | 功能 |
|------|------|
| 启动 | 启动 FastAPI 服务器（subprocess 方式，无窗口） |
| 停止 | 终止服务器进程 + 按端口杀残留进程 |
| 复制 | 复制本地/局域网 URL |
| 打开面板 | 在浏览器中打开 Web 面板 |
| 密钥输入框 | 修改 API 密钥，自动保存到 `.api_key` 文件 |

---

## 配置

编辑 `config.yaml`：

```yaml
host: 0.0.0.0          # 监听地址（0.0.0.0 = 允许外部访问）
port: 8001              # 监听端口
require_api_key: true   # 是否需要 API 密钥
rate_limit_per_minute: 300  # 每分钟请求限制
claude_home: ""         # Claude 数据目录（空 = 自动检测 ~/.claude）
max_upload_mb: 5        # 最大上传文件大小（MB）
session_cookie_days: 30 # 会话 Cookie 有效期（天）
```

### 环境变量

| 变量 | 说明 |
|------|------|
| `CC_DASHBOARD_API_KEY` | 直接指定 API 密钥（优先级高于 `.api_key` 文件） |

---

## 项目结构

```
claude-code-mobile/
├── server.py                  # FastAPI 服务器入口
├── panel.py                   # 桌面管理面板（PyWebView）
├── CCM.pyw                    # 静默启动入口（Windows）
├── 启动.bat / 启动.vbs        # 启动脚本
├── config.yaml                # 配置文件
├── requirements.txt           # Python 依赖
├── .api_key                   # API 密钥（自动生成，不提交）
├── static/
│   ├── index.html             # Web 面板前端（SPA）
│   ├── panel.html             # 桌面管理面板页面
│   ├── icon.ico / .png / .svg # 项目图标
├── cc_monitor/
│   ├── claude_reader.py       # JSONL 会话数据读取器
│   ├── claude_sender.py       # CLI 消息发送器（含流式输出）
│   ├── config.py              # 配置加载
│   ├── logger.py              # 日志系统（RotatingFileHandler）
│   ├── middleware.py           # HTTP 中间件（限速、认证）
│   ├── guard.py               # 扫描攻击检测
│   ├── rate_limiter.py        # 滑动窗口速率限制
│   ├── device_tracker.py      # 在线设备追踪
│   ├── state.py               # 全局状态管理
│   └── routes/
│       ├── api.py             # 数据 API + WebSocket 端点
│       ├── auth.py            # 认证路由（登录、密钥管理）
│       └── pages.py           # 静态文件服务
├── logs/                      # 日志目录（自动生成，不提交）
└── CHANGELOG.md               # 版本更新日志
```

---

## API 端点

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录，设置 HMAC 签名 Cookie |
| POST | `/api/auth/change-key` | 修改 API 密钥 |

### 数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 获取项目列表 |
| GET | `/api/projects/{hash}/sessions` | 获取会话列表 |
| GET | `/api/projects/{hash}/sessions/{id}/messages` | 获取消息列表 |
| POST | `/api/projects/{hash}/sessions/{id}/send` | 发送消息 |
| POST | `/api/projects/{hash}/sessions/{id}/upload` | 上传图片 |
| GET | `/api/projects/{hash}/sessions/{id}/stream` | SSE 实时消息流 |
| GET | `/api/status` | 获取 CC 运行状态 |
| GET | `/api/health` | 健康检查 |

### WebSocket

| 路径 | 说明 |
|------|------|
| `ws://host:8001/ws/terminal/{hash}/{sid}` | 终端模式流式输出 |

连接后发送 `{"message": "你的消息"}`，服务端逐行推送 Claude CLI 的 stream-json 输出。

---

## 安全机制

| 机制 | 说明 |
|------|------|
| API 密钥认证 | 所有请求需要 Bearer Token 或 Cookie |
| 路径穿越防护 | session_id / project_hash 白名单校验 |
| 速率限制 | 滑动窗口算法，默认 300 次/分钟 |
| 扫描攻击检测 | 20 次异常请求自动封禁 |
| 上传大小限制 | 默认 5MB，可配置 |
| XSS 防护 | 前端 URL 过滤（javascript:/data:/vbscript:） |
| Cookie 安全 | Secure + HttpOnly + SameSite |
| 日志脱敏 | API 密钥在日志中自动隐藏 |

---

## 常见问题

### 手机访问不了？

1. 确认电脑和手机在同一局域网
2. 检查防火墙是否放行了 8001 端口
3. 确认 `config.yaml` 中 `host: 0.0.0.0`（不是 `127.0.0.1`）

### 发消息没有回复？

1. 检查 Claude Code CLI 是否已安装：`claude --version`
2. 检查会话是否存在：查看 `~/.claude/projects/` 目录
3. 查看日志：桌面面板 → 日志区域，或 `logs/` 目录

### 模型报错？

项目会自动检测会话使用的模型并匹配。如果仍然报错：
1. 确认你的 API key 有该模型的访问权限
2. 确认模型名称正确（在对话历史中查看）

### 终端模式连接失败？

1. 确认服务器正在运行
2. 检查浏览器控制台是否有 WebSocket 错误
3. 确认 `pywebview` 已安装：`pip install pywebview`

---

## 版本历史

详见 [CHANGELOG.md](CHANGELOG.md)

当前版本：**v2.0.0**

---

## License

MIT

---

## English

### What is this

claude-code-mobile is a local web service that lets you monitor and manage your Claude Code sessions from any device's browser. It reads Claude Code's session data from `~/.claude/` and serves a web interface for remote access.

### Quick Start

```bash
git clone https://github.com/Sichouyuluan/claude-code-mobile.git
cd claude-code-mobile
pip install -r requirements.txt
python panel.py  # Opens desktop management panel
```

Open your phone browser and navigate to `http://YOUR_PC_IP:8001`.

### Features

- **Remote messaging**: Send messages to Claude Code from your phone, with automatic model detection
- **Terminal mode**: Real-time streaming of Claude CLI output via WebSocket
- **Dual-mode UI**: Conversation view (message list) + Terminal view (live stream), one-tap switch
- **Desktop panel**: Liquid Glass UI management panel with server control, system monitoring, log viewer
- **Mobile optimized**: Safe-area handling for all mobile browsers
- **Security**: API key auth, rate limiting, path traversal protection, XSS filtering

### Tech Stack

- **Backend**: FastAPI + Uvicorn + WebSocket
- **Frontend**: Vanilla JS SPA + Liquid Glass CSS
- **Desktop**: PyWebView + HTML
- **Data**: Claude Code JSONL session files
