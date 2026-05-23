"""认证路由 — 登录/登出/session cookie 管理"""
import hmac
import hashlib
import os
import time
import base64
import secrets

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from cc_monitor.state import app_state
from cc_monitor.config import get_config

router = APIRouter()

COOKIE_NAME = "cc_session"
COOKIE_DAYS = 30


def _sign(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_session_cookie(api_key: str) -> str:
    prefix = api_key[:8]
    ts = str(int(time.time()))
    sig = _sign(f"{prefix}|{ts}", api_key)
    raw = f"{prefix}|{ts}|{sig}"
    return base64.b64encode(raw.encode()).decode()


def verify_session_cookie(cookie_value: str, api_key: str) -> bool:
    try:
        raw = base64.b64decode(cookie_value).decode()
        parts = raw.split("|")
        if len(parts) != 3:
            return False
        prefix, ts_str, sig = parts
        if not hmac.compare_digest(sig, _sign(f"{prefix}|{ts_str}", api_key)):
            return False
        ts = int(ts_str)
        if time.time() - ts > COOKIE_DAYS * 86400:
            return False
        return hmac.compare_digest(prefix, api_key[:8])
    except Exception:
        return False


def check_auth(request: Request) -> bool:
    if not get_config("require_api_key", True):
        return True
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie and verify_session_cookie(cookie, app_state.api_key):
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        return hmac.compare_digest(token, app_state.api_key)
    # Support api_key as query parameter (needed for EventSource which can't set headers)
    query_key = request.query_params.get("api_key")
    if query_key:
        return hmac.compare_digest(query_key.strip(), app_state.api_key)
    return False


def require_auth(request: Request):
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="未认证")


class LoginRequest(BaseModel):
    api_key: str


@router.post("/api/auth/login")
async def login(req: LoginRequest):
    if not hmac.compare_digest(req.api_key.strip(), app_state.api_key):
        raise HTTPException(status_code=403, detail="API Key 无效")
    cookie_val = create_session_cookie(app_state.api_key)
    resp = JSONResponse({"success": True, "message": "登录成功"})
    resp.set_cookie(
        COOKIE_NAME, cookie_val,
        max_age=COOKIE_DAYS * 86400,
        httponly=True, samesite="strict",
        secure=True
    )
    return resp


@router.post("/api/auth/logout")
async def logout():
    resp = JSONResponse({"success": True})
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/api/auth/check")
async def auth_check(request: Request):
    return {"authenticated": check_auth(request)}


class ChangeKeyRequest(BaseModel):
    current_key: str
    new_key: str


@router.post("/api/auth/change-key")
async def change_api_key(req: ChangeKeyRequest, request: Request):
    """Change the API key. Requires current key + new key."""
    require_auth(request)
    if not hmac.compare_digest(req.current_key.strip(), app_state.api_key):
        raise HTTPException(status_code=403, detail="当前 API Key 无效")
    new_key = req.new_key.strip()
    if len(new_key) < 8:
        raise HTTPException(status_code=400, detail="新 API Key 至少 8 个字符")
    # Save new key to .api_key file
    try:
        from cc_monitor.config import get_project_root
        key_file = os.path.join(get_project_root(), ".api_key")
        with open(key_file, "w") as f:
            f.write(new_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")
    # Update in-memory state
    app_state.api_key = new_key
    return {"success": True, "message": "API Key 已更新"}
