"""限速器 — 按 IP 的滑动窗口限速 + 自动封禁（线程安全）"""
import time
import threading
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests=30, window_seconds=60, ban_minutes=5):
        self.max_requests = max_requests
        self.window = window_seconds
        self.ban_minutes = ban_minutes
        self._lock = threading.Lock()
        self._requests = defaultdict(list)
        self._last_cleanup = 0.0
        self._ban_counts: dict[str, int] = {}
        self._banned: dict[str, float] = {}

    def _cleanup_old(self):
        now = time.time()
        cutoff = now - 2 * self.window
        stale = [ip for ip, ts in self._requests.items()
                 if not ts or all(t <= cutoff for t in ts)]
        for ip in stale:
            del self._requests[ip]

    def is_allowed(self, client_ip: str) -> bool:
        with self._lock:
            now = time.time()
            if now - self._last_cleanup > 600:
                self._cleanup_old()
                self._last_cleanup = now
            cutoff = now - self.window
            self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]
            if len(self._requests[client_ip]) >= self.max_requests:
                return False
            self._requests[client_ip].append(now)
            return True

    def is_banned(self, client_ip: str) -> bool:
        with self._lock:
            unban_ts = self._banned.get(client_ip)
            if unban_ts is None:
                return False
            if time.time() < unban_ts:
                return True
            del self._banned[client_ip]
            self._ban_counts.pop(client_ip, None)
            return False

    def record_rejection(self, client_ip: str):
        with self._lock:
            self._ban_counts[client_ip] = self._ban_counts.get(client_ip, 0) + 1
            if self._ban_counts[client_ip] >= 10:
                self._banned[client_ip] = time.time() + self.ban_minutes * 60
                self._ban_counts.pop(client_ip, None)
