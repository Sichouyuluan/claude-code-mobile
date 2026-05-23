"""扫描攻击检测 — 全局异常统计 + 自动保护 + 停服"""
import time
import threading
from collections import deque


class ScanGuard:
    def __init__(self, window_seconds=10, path_threshold=15,
                 flood_threshold=50, protect_minutes=3, stop_after=20,
                 stop_callback=None):
        self._lock = threading.Lock()
        self._window_seconds = window_seconds
        self._path_threshold = path_threshold
        self._flood_threshold = flood_threshold
        self._protect_seconds = protect_minutes * 60
        self._stop_after = stop_after
        self._stop_callback = stop_callback
        self._window: deque = deque()
        self._protected_until = 0.0
        self._protection_count = 0
        self._trigger_reason = ""

    def check_and_record(self, client_ip: str, status: int, path: str):
        now = time.time()
        with self._lock:
            cutoff = now - self._window_seconds
            while self._window and self._window[0][0] < cutoff:
                self._window.popleft()
            self._window.append((now, client_ip, status, path))
            abnormal = [r for r in self._window if r[2] in (404, 403, 429)]
            unique_paths = len(set(r[3] for r in abnormal))
            triggered = False
            if unique_paths > self._path_threshold:
                self._trigger_reason = f"path_scan({unique_paths}>{self._path_threshold})"
                triggered = True
            elif len(abnormal) > self._flood_threshold:
                self._trigger_reason = f"flood({len(abnormal)}>{self._flood_threshold})"
                triggered = True
            if triggered:
                self._trigger_protection(now)

    def _trigger_protection(self, now: float):
        self._protected_until = now + self._protect_seconds
        self._protection_count += 1
        if self._protection_count >= self._stop_after and self._stop_callback:
            self._stop_callback()

    def is_protected(self) -> bool:
        with self._lock:
            return time.time() < self._protected_until

    def get_stats(self) -> dict:
        with self._lock:
            now = time.time()
            return {
                "is_protected": now < self._protected_until,
                "remaining_seconds": max(0, int(self._protected_until - now)),
                "protection_count": self._protection_count,
            }


_guard: ScanGuard | None = None


def get_guard() -> ScanGuard | None:
    return _guard


def set_guard(g: ScanGuard):
    global _guard
    _guard = g
