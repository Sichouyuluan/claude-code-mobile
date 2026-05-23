"""页面路由"""
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
import os

router = APIRouter()
_static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static")


@router.get("/")
async def index():
    return FileResponse(os.path.join(_static_dir, "index.html"))


@router.get("/favicon.ico")
async def favicon():
    return FileResponse(os.path.join(_static_dir, "icon.ico"), media_type="image/x-icon")


@router.get("/static/{filename}")
async def static_file(filename: str):
    filepath = os.path.join(_static_dir, filename)
    resolved = Path(filepath).resolve()
    if not resolved.is_relative_to(Path(_static_dir).resolve()):
        return JSONResponse(status_code=403, content={"error": "禁止访问"})
    if os.path.exists(filepath):
        return FileResponse(filepath)
    return JSONResponse(status_code=404, content={"error": "not found"})
