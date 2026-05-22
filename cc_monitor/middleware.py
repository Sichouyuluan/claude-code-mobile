"""中间件 — API Key 认证 + Session Cookie + 限速 + 设备追踪 + 扫描防护"""
import time

from fastapi import Header, Request
from fastapi.responses import JSONResponse

from cc_monitor.config import get_config
from cc_monitor.guard import get_guard
from cc_monitor.state import app_state
from cc_monitor.routes.auth import check_auth


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    path = request.url.path

    guard = get_guard()
    if guard:
        gs = guard.get_stats()
        if gs["is_protected"]:
            return JSONResponse(
                status_code=503,
                content={"error": f"服务器进入保护模式，请{gs['remaining_seconds']}秒后再试"},
            )

    dt = app_state.device_tracker
    if dt and path not in ("/api/online-devices", "/api/kick-device") and dt.is_kicked(client_ip):
        return JSONResponse(status_code=403, content={"error": "你已被暂时移除"})

    limiter = app_state.rate_limiter
    # Exempt read-only data paths and auth paths from rate limiting
    exempt_exact = ("/api/ping", "/api/health", "/api/system", "/api/active",
                    "/api/auth/login", "/api/auth/check", "/api/auth/logout")
    exempt_prefix = ("/api/projects",)
    if limiter and path not in exempt_exact and not any(path.startswith(p) for p in exempt_prefix):
        if limiter.is_banned(client_ip):
            return JSONResponse(status_code=403, content={"error": "你已被暂时封禁"})
        if not limiter.is_allowed(client_ip):
            limiter.record_rejection(client_ip)
            return JSONResponse(status_code=429, content={"error": "请求过于频繁"})

    if dt and client_ip not in ("127.0.0.1", "::1"):
        ua = request.headers.get("user-agent", "")
        dt.update_activity(client_ip, ua)

    response = await call_next(request)

    if guard:
        guard.check_and_record(client_ip, response.status_code, path)

    return response
