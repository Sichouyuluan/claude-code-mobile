"""数据 API 路由"""
import asyncio
import json
import os
import re
import shutil
import tempfile
import time

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse

from cc_monitor.routes.auth import require_auth
from cc_monitor.claude_reader import ClaudeReader
from cc_monitor.claude_sender import ClaudeSender
from cc_monitor.config import get_config

_SAFE_ID = re.compile(r'^[a-zA-Z0-9_-]+$')


def _validate_id(value: str, name: str = "id"):
    """Validate that a path component contains only safe characters."""
    if not value or not _SAFE_ID.match(value):
        raise HTTPException(status_code=400, detail=f"无效的 {name}")
    return value

router = APIRouter()
_reader = None
_sender = None


def init_reader_sender():
    """Called once at server startup to initialize singletons."""
    global _reader, _sender
    _reader = ClaudeReader(get_config("claude_home"))
    _sender = ClaudeSender()


def _get_reader():
    global _reader
    if _reader is None:
        _reader = ClaudeReader(get_config("claude_home"))
    return _reader


def _get_sender():
    global _sender
    if _sender is None:
        _sender = ClaudeSender()
    return _sender


@router.get("/api/ping")
async def ping():
    return {"pong": True}


@router.get("/api/system")
def system_info(request: Request):
    require_auth(request)
    return _get_reader().get_system_info()


@router.get("/api/projects")
def list_projects(request: Request):
    require_auth(request)
    return {"projects": _get_reader().list_projects()}


@router.get("/api/active")
def active_sessions(request: Request):
    require_auth(request)
    return {"active": _get_reader().get_active_sessions()}


@router.get("/api/projects/{project_hash}/sessions")
def list_sessions(project_hash: str, request: Request):
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    return {"sessions": _get_reader().list_sessions(project_hash)}


@router.get("/api/projects/{project_hash}/sessions/{session_id}/messages")
def get_messages(project_hash: str, session_id: str,
                 last_n: int = 50, offset: int = 0, request: Request = None):
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    _validate_id(session_id, "session_id")
    messages = _get_reader().read_conversation(project_hash, session_id, last_n, offset)
    return {"messages": messages, "count": len(messages)}


@router.post("/api/projects/{project_hash}/sessions/{session_id}/send")
async def send_message(project_hash: str, session_id: str, request: Request):
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    _validate_id(session_id, "session_id")
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})
    cwd = body.get("cwd")
    result = await _get_sender().send_message(session_id, message, cwd=cwd)
    return result


@router.post("/api/projects/{project_hash}/sessions/{session_id}/upload")
async def upload_image(project_hash: str, session_id: str,
                       file: UploadFile = File(...),
                       message: str = Form("请分析这张图片"),
                       request: Request = None):
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    _validate_id(session_id, "session_id")
    reader = _get_reader()
    # Resolve project cwd from session metadata
    meta = reader._read_meta_from_session(project_hash, session_id)
    proj_cwd = meta.get("cwd", "")
    content = await file.read()
    max_mb = get_config("max_upload_mb", 5)
    if len(content) > max_mb * 1024 * 1024:
        return JSONResponse(status_code=413, content={"error": f"文件超过 {max_mb}MB 限制"})
    # Save to temp for sending to CC
    upload_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(file.filename or "upload.jpg")[1]
        tmp_path = os.path.join(upload_dir, f"upload{ext}")
        with open(tmp_path, "wb") as f:
            f.write(content)
        # Save permanent copy to project's pictures/ directory
        saved_path = _save_to_pictures(proj_cwd, file.filename, content)
        # Ensure pictures/ is in .gitignore
        if proj_cwd:
            _ensure_gitignore(proj_cwd)
        result = await _get_sender().upload_image(tmp_path, message, session_id=session_id)
        if saved_path:
            result["saved_path"] = saved_path
        return result
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)


def _save_to_pictures(proj_cwd: str, original_filename: str, content: bytes) -> str | None:
    """Save an uploaded file to {proj_cwd}/pictures/ with timestamp prefix.
    Returns the saved file path, or None if proj_cwd is empty.
    """
    if not proj_cwd:
        return None
    pictures_dir = os.path.join(proj_cwd, "pictures")
    os.makedirs(pictures_dir, exist_ok=True)
    ext = os.path.splitext(original_filename or "upload.jpg")[1]
    base = os.path.splitext(os.path.basename(original_filename or "upload"))[0]
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{base}{ext}"
    path = os.path.join(pictures_dir, filename)
    # Avoid collision by appending a counter
    counter = 1
    while os.path.exists(path):
        filename = f"{ts}_{base}_{counter}{ext}"
        path = os.path.join(pictures_dir, filename)
        counter += 1
    with open(path, "wb") as f:
        f.write(content)
    return path


def _ensure_gitignore(proj_cwd: str):
    """Ensure 'pictures/' is listed in the project's .gitignore.
    Only acts if a .git file or directory exists in proj_cwd.
    """
    git_path = os.path.join(proj_cwd, ".git")
    if not os.path.exists(git_path):
        return
    gitignore_path = os.path.join(proj_cwd, ".gitignore")
    try:
        existing = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
                existing = f.read()
        if "pictures/" not in existing:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("pictures/\n")
    except Exception:
        pass


@router.post("/api/projects/{project_hash}/new-session")
async def new_session(project_hash: str, request: Request):
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})
    cwd = body.get("cwd")
    model = body.get("model")
    result = await _get_sender().start_new_session(message, cwd=cwd, model=model)
    return result


@router.delete("/api/projects/{project_hash}/sessions/{session_id}")
async def delete_session(project_hash: str, session_id: str, request: Request):
    """Delete a session's JSONL file and related data."""
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    _validate_id(session_id, "session_id")
    reader = _get_reader()
    # Check if session is currently active
    active = reader.get_active_sessions()
    active_ids = {s.get("session_id") for s in active if s.get("running")}
    if session_id in active_ids:
        return JSONResponse(status_code=409, content={"error": "会话正在运行中，无法删除"})
    proj_dir = reader.projects_dir / project_hash
    jsonl_path = proj_dir / f"{session_id}.jsonl"
    if not jsonl_path.exists():
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    try:
        jsonl_path.unlink()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"删除文件失败: {e}"})
    # Delete session subdirectory if it exists
    session_subdir = proj_dir / session_id
    if session_subdir.is_dir():
        shutil.rmtree(session_subdir, ignore_errors=True)
    return {"success": True, "message": f"会话 {session_id} 已删除"}


@router.get("/api/cc-status")
def cc_status(request: Request):
    """Get status of all CC sessions."""
    require_auth(request)
    return {"sessions": _get_reader().get_cc_status()}


@router.get("/api/projects/{project_hash}/sessions/{session_id}/stream")
async def stream_session(project_hash: str, session_id: str, request: Request):
    """SSE endpoint that streams new messages as they appear.
    Polls the JSONL file every 1.5 seconds using byte offset tracking.
    Sends only new lines since last check, including tool_use and thinking data.
    Handles file rotation (size decrease) gracefully.
    """
    require_auth(request)
    _validate_id(project_hash, "project_hash")
    _validate_id(session_id, "session_id")
    reader = _get_reader()
    jsonl_path = reader.projects_dir / project_hash / f"{session_id}.jsonl"

    async def event_generator():
        if not jsonl_path.exists():
            yield "event: error\ndata: {\"error\": \"会话文件不存在\"}\n\n"
            return

        # Start from current end of file (only stream new data)
        try:
            last_offset = jsonl_path.stat().st_size
        except OSError:
            yield "event: error\ndata: {\"error\": \"无法读取文件\"}\n\n"
            return

        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(1.5)
            try:
                current_size = jsonl_path.stat().st_size
            except OSError:
                yield "event: error\ndata: {\"error\": \"文件已被删除\"}\n\n"
                break

            # File rotation detection: if file shrank, reset offset
            if current_size < last_offset:
                last_offset = 0

            if current_size <= last_offset:
                continue

            # Read only new bytes
            try:
                with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_offset)
                    new_data = f.read()
                    last_offset = f.tell()
            except Exception:
                continue

            for raw_line in new_data.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = obj.get("type")
                if t not in ("user", "assistant"):
                    continue
                msg = obj.get("message", {})
                content = msg.get("content", [])
                text_parts = []
                tool_calls = []
                tool_results = []
                thinking_text = ""
                for b in content:
                    if not isinstance(b, dict):
                        if isinstance(b, str):
                            text_parts.append(b)
                        continue
                    btype = b.get("type", "")
                    if btype == "text":
                        text_parts.append(b.get("text", ""))
                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": b.get("id", ""),
                            "name": b.get("name", "unknown"),
                            "input": b.get("input", {}),
                        })
                    elif btype == "tool_result":
                        rc = b.get("content", "")
                        if isinstance(rc, list):
                            rc = "\n".join(c.get("text", "") for c in rc if isinstance(c, dict))
                        tool_results.append({
                            "tool_use_id": b.get("tool_use_id", ""),
                            "content": str(rc)[:2000],
                        })
                    elif btype == "thinking":
                        thinking_text = b.get("thinking", "")
                event_data = {
                    "type": t,
                    "text": "\n".join(text_parts),
                    "timestamp": obj.get("timestamp", ""),
                    "uuid": obj.get("uuid", ""),
                }
                if t == "assistant":
                    event_data["model"] = msg.get("model", "")
                    event_data["tool_uses"] = tool_calls
                    event_data["stop_reason"] = msg.get("stop_reason", "")
                    if thinking_text:
                        event_data["thinking"] = thinking_text
                if t == "user" and tool_results:
                    event_data["tool_results"] = tool_results
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/health")
async def health():
    return {"status": "ok"}
