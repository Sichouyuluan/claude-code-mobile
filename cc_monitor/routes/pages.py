"""页面路由"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
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
    if os.path.exists(filepath):
        return FileResponse(filepath)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"error": "not found"})
