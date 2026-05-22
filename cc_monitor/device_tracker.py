"""在线设备追踪器 — 线程安全的设备管理 + 踢出"""
import time
import threading


class OnlineDeviceTracker:
    def __init__(self, offline_threshold=30):
        self._lock = threading.RLock()
        self._devices = {}
        self._kicked = {}
        self.offline_threshold = offline_threshold
        self.kick_duration = 300
        self._last_cleanup = 0.0

    def update_activity(self, client_ip: str, user_agent: str = ""):
        now = time.time()
        with self._lock:
            if client_ip in self._devices:
                self._devices[client_ip]["last_seen"] = now
            else:
                self._devices[client_ip] = {
                    "first_seen": now, "last_seen": now,
                    "user_agent": user_agent,
                }

    def is_kicked(self, client_ip: str) -> bool:
        with self._lock:
            if client_ip in self._kicked:
                if time.time() < self._kicked[client_ip]:
                    return True
                del self._kicked[client_ip]
            return False

    def kick(self, client_ip: str):
        with self._lock:
            self._kicked[client_ip] = time.time() + self.kick_duration

    def _cleanup_offline(self):
        now = time.time()
        threshold = self.offline_threshold * 20
        with self._lock:
            stale = [ip for ip, info in self._devices.items()
                     if now - info["last_seen"] > threshold]
            for ip in stale:
                del self._devices[ip]

    def get_online_devices(self) -> list:
        now = time.time()
        if now - self._last_cleanup > 600:
            self._cleanup_offline()
            self._last_cleanup = now
        online = []
        with self._lock:
            for ip, info in self._devices.items():
                if now - info["last_seen"] <= self.offline_threshold:
                    online.append({
                        "ip": ip,
                        "user_agent": info["user_agent"],
                        "connected_seconds": round(now - info["first_seen"]),
                        "last_seen_seconds_ago": round(now - info["last_seen"]),
                    })
        return online

    def get_online_count(self) -> int:
        now = time.time()
        with self._lock:
            return sum(1 for info in self._devices.values()
                       if now - info["last_seen"] <= self.offline_threshold)
