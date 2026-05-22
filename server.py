"""CC Remote Dashboard — FastAPI 入口"""
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from cc_monitor.config import load_config, get_config, get_project_root
from cc_monitor.state import app_state
from cc_monitor.middleware import rate_limit_middleware
from cc_monitor.rate_limiter import RateLimiter
from cc_monitor.guard import ScanGuard, set_guard
from cc_monitor.device_tracker import OnlineDeviceTracker

load_config()


def _load_or_generate_api_key() -> str:
    key = os.environ.get("CC_DASHBOARD_API_KEY")
    if key:
        return key
    key_file = os.path.join(get_project_root(), ".api_key")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            key = f.read().strip()
    if not key:
        key = secrets.token_urlsafe(32)
        with open(key_file, "w") as f:
            f.write(key)
    return key


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.rate_limiter = RateLimiter(
        max_requests=get_config("rate_limit_per_minute", 30),
        window_seconds=60,
    )
    app_state.device_tracker = OnlineDeviceTracker(offline_threshold=30)

    def _stop_uvicorn():
        import signal
        os.kill(os.getpid(), signal.SIGTERM)

    set_guard(ScanGuard(stop_callback=_stop_uvicorn))
    app_state.api_key = _load_or_generate_api_key()
    print(f"[CC Dashboard] API Key: {app_state.api_key[:4]}...***")
    print(f"[CC Dashboard] 启动: http://0.0.0.0:{get_config('port', 8001)}")
    yield
    print("[CC Dashboard] 关闭")


app = FastAPI(title="CC Remote Dashboard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(rate_limit_middleware)

from cc_monitor.routes.auth import router as auth_router
from cc_monitor.routes.api import router as api_router
from cc_monitor.routes.pages import router as pages_router

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(pages_router)

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=get_config("host", "0.0.0.0"),
        port=get_config("port", 8001),
        reload=False,
    )
