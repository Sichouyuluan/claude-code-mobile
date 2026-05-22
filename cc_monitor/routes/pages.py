"""页面路由"""
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
import os

router = APIRouter()
_static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static")


@router.get("/")
async def index():
    return FileResponse(os.path.join(_static_dir, "index.html"))


@router.get("/panel")
async def panel():
    return FileResponse(os.path.join(_static_dir, "panel.html"))
