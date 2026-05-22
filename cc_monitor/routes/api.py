"""数据 API 路由"""
import os
import shutil
import tempfile
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse

from cc_monitor.routes.auth import require_auth
from cc_monitor.claude_reader import ClaudeReader
from cc_monitor.claude_sender import ClaudeSender
from cc_monitor.config import get_config

router = APIRouter()
reader = ClaudeReader(get_config("claude_home"))
sender = ClaudeSender()


@router.get("/api/ping")
async def ping():
    return {"pong": True}


@router.get("/api/system")
async def system_info(request: Request):
    require_auth(request)
    return reader.get_system_info()


@router.get("/api/projects")
async def list_projects(request: Request):
    require_auth(request)
    return {"projects": reader.list_projects()}


@router.get("/api/active")
async def active_sessions(request: Request):
    require_auth(request)
    return {"active": reader.get_active_sessions()}


@router.get("/api/projects/{project_hash}/sessions")
async def list_sessions(project_hash: str, request: Request):
    require_auth(request)
    return {"sessions": reader.list_sessions(project_hash)}


@router.get("/api/projects/{project_hash}/sessions/{session_id}/messages")
async def get_messages(project_hash: str, session_id: str,
                       last_n: int = 50, request: Request = None):
    require_auth(request)
    messages = reader.read_conversation(project_hash, session_id, last_n)
    return {"messages": messages, "count": len(messages)}


@router.post("/api/projects/{project_hash}/sessions/{session_id}/send")
async def send_message(project_hash: str, session_id: str, request: Request):
    require_auth(request)
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})
    cwd = body.get("cwd")
    result = await sender.send_message(session_id, message, cwd=cwd)
    return result


@router.post("/api/projects/{project_hash}/sessions/{session_id}/upload")
async def upload_image(project_hash: str, session_id: str,
                       file: UploadFile = File(...),
                       message: str = Form("请分析这张图片"),
                       request: Request = None):
    require_auth(request)
    upload_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(file.filename or "upload.jpg")[1]
        path = os.path.join(upload_dir, f"upload{ext}")
        with open(path, "wb") as f:
            content = await file.read()
            f.write(content)
        result = await sender.upload_image(path, message, session_id=session_id)
        return result
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)


@router.post("/api/projects/{project_hash}/new-session")
async def new_session(project_hash: str, request: Request):
    require_auth(request)
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})
    cwd = body.get("cwd")
    model = body.get("model")
    result = await sender.start_new_session(message, cwd=cwd, model=model)
    return result


@router.get("/api/health")
async def health():
    return {"status": "ok"}
