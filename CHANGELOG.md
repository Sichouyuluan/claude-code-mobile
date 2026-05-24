# Changelog

## v2.0.0 (2026-05-24)

### 新增功能
- **终端模式**：通过 WebSocket 实时流式传输 Claude CLI 完整输出到网页，支持思考过程、工具调用（Read/Bash/Edit 等）、代码回复逐行显示
- **双模式切换**：会话页面新增浮动圆形按钮，一键切换"对话模式"（消息列表）和"终端模式"（实时流式输出），两个模式互不干扰
- **桌面管理面板重写**：从 CustomTkinter 迁移到 PyWebView + Liquid Glass UI，新增 `static/panel.html` 管理面板页面
- **自动模型匹配**：发消息时从会话 JSONL 文件中自动检测使用的模型名称，通过 `--model` 参数传递给 CLI，解决跨模型切换报错问题
- **WebSocket 终端端点**：后端新增 `/ws/terminal/{project_hash}/{session_id}` 端点，支持流式 CLI 输出推送

### 修复
- **发消息不传 cwd**：前端 `sendMessage()` 未传递工作目录，导致 Claude CLI 在错误目录下运行静默失败。现在前端传递 `cwd`，后端从会话元数据回退读取
- **移动端底部遮挡**：Android 浏览器工具栏遮挡输入框，增大 `safe-area-inset-bottom` padding（20px → 40px）
- **CCM.pyw 入口适配**：面板改为 PyWebView 后，CCM.pyw 同步更新启动逻辑

### 改动文件
- `cc_monitor/claude_sender.py`：新增 `send_message_stream()` 流式输出方法、`detect_model_from_session()` 模型检测函数
- `cc_monitor/routes/api.py`：新增 WebSocket 端点、`/send` 端点增加 cwd 回退逻辑
- `static/index.html`：新增终端模式 CSS/HTML/JS、浮动切换按钮、移动端适配
- `panel.py`：完全重写为 PyWebView + PanelAPI bridge
- `static/panel.html`：新增 Liquid Glass 管理面板页面
- `CCM.pyw`：适配 PyWebView 启动方式
- `requirements.txt`：新增 `pywebview>=4.0`

---

## v1.1.0 (2026-05-23)

### 改进
- 侧边栏工作区下拉箭头加大，提升移动端点击体验
- 编写面板重设计方案 B（PyWebView）详细提示词文档

---

## v1.0.0 (2026-05-23)

### 新增功能
- **全面日志系统**：使用 Python logging + RotatingFileHandler，关键操作（启动/停止/认证/限速/发送消息）全部输出到 `logs/cc_*.log`
- **PinHidingFilter**：日志中自动隐藏 API 密钥，防止敏感信息泄露
- **thinking 内容提取**：从 JSONL 的 `content` block 中提取 `thinking` 类型内容，前端折叠显示 Claude 的思考过程
- **tool_result 内容提取**：从 JSONL 中提取工具执行结果，前端可折叠查看

### 修复
- **日志系统从未初始化**：`setup_logger()` 从未在 `server.py` 中调用，导致面板日志始终显示"暂无日志"。在 `server.py` 模块级别添加初始化调用
- **日志面板重写**：读取所有 `cc_*.log` 文件（最近 3 个），显示最后 50 行，每 3 秒自动刷新，不依赖服务器状态
- **CORS 配置修复**：`allow_origins=["*"]` + `allow_credentials=True` 被浏览器规范禁止，改为 `allow_credentials=False`
- **路径穿越防护**：`session_id` 和 `project_hash` 用于文件路径前增加白名单校验（`^[a-zA-Z0-9_-]+$`）
- **上传文件大小限制**：新增 `max_upload_mb` 配置项，防止超大文件上传
- **cookie secure=True**：会话 cookie 标记为安全传输
- **ScanGuard 阈值提高**：从 5 次提高到 20 次，减少误封
- **rate limiter 定期清理**：新增 `_cleanup_loop()` 定时清理过期限速记录
- **session status 索引缓存**：`_build_session_index()` 一次性构建会话索引，避免重复扫描

### 改动文件
- `server.py`：`setup_logger()` 初始化、CORS 修复、`init_reader_sender()` 调用、cleanup task
- `cc_monitor/routes/api.py`：路径校验、上传大小限制、删除活跃会话检查、日志
- `cc_monitor/routes/auth.py`：cookie secure=True、登录日志
- `cc_monitor/routes/pages.py`：路径穿越防护（`Path.resolve()` + `is_relative_to()`）
- `cc_monitor/middleware.py`：写操作限速 + 日志
- `cc_monitor/guard.py`：`stop_after` 默认值从 5 改为 20
- `cc_monitor/config.py`：异常兜底（FileNotFoundError、YAMLError、OSError）
- `cc_monitor/claude_reader.py`：thinking/tool_result 提取、session index 缓存、日志

---

## v0.9.0 (2026-05-23)

### 新增功能
- **分层渲染（Round Folding）**：将消息按用户提问分割为"轮次"，每个轮次用细线分隔，2000+ 条消息场景下性能显著提升
- `groupIntoRounds()` 函数：将消息数组按 user 消息分割为多个轮次
- `renderRound()` 函数：每个轮次渲染为独立分隔线 + 消息列表（不再把所有消息塞进一个容器）

### 修复
- 轮次渲染把 33 条消息放进一个 `.round` 容器导致只显示一条横线的问题，改为消息保持独立 DOM 元素
- thinking 内容提取逻辑完善，支持多段 thinking block

---

## v0.8.0 (2026-05-23)

### 新增功能
- **全量加载消息**：移除分页机制，`messageLimit` 改为 9999，一次加载会话所有消息
- **滚动条用户消息标记**：`updateScrollbarMarkers()` 在滚动条上放置蓝色圆点标记用户消息位置
- 工具调用详情折叠显示：点击展开查看工具名称、输入参数、执行结果
- 消息合并修复：`groupMessages()` 将 `tool_result` 类型的 user 消息合并到 assistant 组
- 时间戳右置：使用 flexbox 布局，时间戳显示在消息右侧
- 对话页顶部显示完整会话 ID + 一键复制按钮

### 修复
- 活跃会话点击"未找到"问题：`selectProjectByPath` 无法匹配路径，新增 `selectProjectBySession()` 通过 session_id 匹配
- 侧边栏/会话列表改进
- backdrop-filter: blur() 从行内元素（code、pre）移除，消除文字"马赛克"模糊效果
- `white-space: pre-wrap; word-break: break-word` 添加到 pre 块，修复代码溢出

---

## v0.7.0 (2026-05-23)

### 新增功能
- **对话流合并**：`groupMessages()` 将连续的 assistant 消息和关联的 tool_result 用户消息合并为一个气泡组
- **代码复制按钮**：`.code-block` 右上角新增复制按钮，`copyCodeBlock()` 函数实现一键复制
- **滚动加载更多消息**：`loadMoreMessages()` 函数，上滑到顶部自动加载历史消息
- **XSS 防护**：`safeUrl()` 函数过滤 `javascript:`、`data:`、`vbscript:` 协议
- 图片上传预览：选择图片后显示缩略图预览，支持取消

### 修复
- 前端消息重复：`sendMessage()` 中手动 `state.messages.push()` 导致与 SSE 推送重复，移除手动推送
- 分页 offset 错误：`read_conversation` 的 offset 按 JSONL 原始行数跳过而非解析后消息数，导致加载位置错误
- `hasMoreMessages` 判断条件错误：用 `messageLimit`（20）而非 `loadCount`（5）比较，导致每次加载后立即标记为"已加载全部"
- 写操作限速：中间件仅对 GET/HEAD/OPTIONS 请求豁免限速
- 面板密钥显示修复

### 安全修复
- 路径穿越防护：所有来自 URL 的参数用于文件路径时增加白名单校验
- 上传文件大小限制
- API Key 不再通过 URL 参数传输（SSE EventSource 除外）

---

## v0.6.0 (2026-05-22)

### 新增功能
- **静默启动**：`CCM.pyw` + `启动.vbs` 无命令行窗口启动桌面面板
- **权限弹窗提示**：消息中检测到 `is_permission_prompt: true` 时显示警告横幅 + 工具名 + 操作指引
- 面板关闭/启动时按端口杀残留进程 + atexit 兜底清理
- 按端口查找 PID 后只杀匹配的进程，避免误杀无关进程

### 修复
- 窗口闪烁彻底消除：移除 `print()`/`input()` 调用
- BAT 改为调用 VBS，实现零窗口启动
- 状态栏图标高清化：生成 11 个尺寸的 ICO 文件（16-256px），使用 iconbitmap 渲染
- ICO 存储完整质量 256x256 PNG

---

## v0.5.0 (2026-05-22)

### 新增功能
- **SSE 流式输出**：Server-Sent Events 实时推送新消息到前端，打字机效果逐字显示
- **液态玻璃 + 拟态 UI**：`backdrop-filter: blur()` + 内外阴影 + 渐变高光
- 面板添加修改密钥按钮
- 密钥修改直接写文件，不需要服务器运行
- 密钥输入框编辑时不会被自动刷新覆盖（`_key_loaded` 标记控制）

### 修复
- 保存密钥前检查服务是否运行，避免连接拒绝错误
- 密钥输入框只在显示默认值或当前密钥时才刷新

---

## v0.4.0 (2026-05-22)

### 新增功能
- **面板重构**：液态玻璃 UI 设计 + 修复崩溃 + 新增系统状态显示
- 重写面板为 CustomTkinter 原生桌面面板
- 9/9 测试用例全部通过

### 修复
- 放宽限速策略：降低请求频率限制阈值，防止正常使用被误封
- 工作区路径解码：修复中文路径和特殊字符导致的面板崩溃
- ICO 图标兼容性：移除 iconphoto（与 CustomTkinter 不兼容），保留 iconbitmap

---

## v0.3.0 (2026-05-21)

### 新增功能
- **PyWebView 桌面管理面板**：服务器启停、本地/局域网 URL、系统状态（CPU/内存/CC 进程）、日志查看
- 全中文界面
- 密钥/链接一键复制
- 会话卡片优化：显示项目名称、路径、消息数

### 修复
- 工作区识别和面板启动问题
- BAT 文件编码修复：GBK 编码兼容 Windows 中文系统

---

## v0.2.0 (2026-05-20)

### 新增功能
- **安全框架**：滑动窗口速率限制 + 自动封禁、扫描攻击检测（ScanGuard）+ 自动关停、在线设备追踪、HTTP 中间件
- **数据读取器**（`claude_reader.py`）：读取 `~/.claude/projects/` 目录的 JSONL 会话数据，支持分页、搜索、会话状态检测
- **消息发送器**（`claude_sender.py`）：通过 `claude --print --resume` CLI 注入消息到会话
- **API 路由**：认证（HMAC 签名 cookie）、数据 API（项目列表/会话列表/消息读取/SSE 流）、页面服务
- **前端 SPA**：响应式暗色主题、仪表盘（项目列表/会话列表/系统状态）、会话消息查看器
- 全中文界面
- 图标系统：多格式（ICO/PNG/SVG）

---

## v0.1.0 (2026-05-19)

### 新增
- 项目初始化：FastAPI + Uvicorn 后端结构
- 配置文件系统（`config.yaml`）
- 项目入口点（`server.py`）
- 基础目录结构（`cc_monitor/`、`static/`、`logs/`）
