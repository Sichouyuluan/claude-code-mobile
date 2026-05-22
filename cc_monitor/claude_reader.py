"""CC Data Reader"""
import json, os, time
from pathlib import Path


class ClaudeReader:
    def __init__(self, claude_home=None):
        if claude_home is None:
            claude_home = os.path.join(str(Path.home()), ".claude")
        self.claude_home = Path(claude_home)
        self.projects_dir = self.claude_home / "projects"
        self.sessions_dir = self.claude_home / "sessions"

    def list_projects(self):
        if not self.projects_dir.exists():
            return []
        projects = []
        for d in self.projects_dir.iterdir():
            if not d.is_dir():
                continue
            jsonl_files = list(d.glob("*.jsonl"))
            last_active = max((f.stat().st_mtime for f in jsonl_files), default=0)
            projects.append({
                "hash": d.name, "path": d.name,
                "session_count": len(jsonl_files),
                "last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_active)) if last_active else None,
            })
        projects.sort(key=lambda p: p["last_active"] or "", reverse=True)
        return projects

    def list_sessions(self, project_hash):
        proj_dir = self.projects_dir / project_hash
        if not proj_dir.exists():
            return []
        sessions = []
        for f in proj_dir.glob("*.jsonl"):
            if f.is_dir():
                continue
            stat = f.stat()
            meta = self._read_meta(f)
            sessions.append({
                "session_id": f.stem, "filename": f.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "last_modified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
                "status": "idle",
                "cwd": meta.get("cwd", ""), "entrypoint": meta.get("entrypoint", ""),
            })
        sessions.sort(key=lambda s: s["last_modified"], reverse=True)
        return sessions

    def get_active_sessions(self):
        active = []
        if not self.sessions_dir.exists():
            return active
        # sessions/<pid>.json contains session info
        for p in self.sessions_dir.glob("*.json"):
            try:
                pid = int(p.stem)
            except ValueError:
                continue
            info = self._read_session_json(pid)
            if not info:
                continue
            running = self._is_running(pid)
            active.append({
                "pid": pid, "running": running,
                "session_id": info.get("sessionId", ""),
                "cwd": info.get("cwd", ""),
                "version": info.get("version", ""),
                "entrypoint": info.get("entrypoint", ""),
                "started_at": info.get("startedAt", 0),
            })
        # Sort by started_at descending (most recent first)
        active.sort(key=lambda x: x.get("started_at", 0), reverse=True)
        return active

    def _read_session_json(self, pid):
        """Read sessions/<pid>.json for session metadata"""
        p = self.sessions_dir / f"{pid}.json"
        if not p.exists():
            return {}
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return json.loads(f.read())
        except Exception:
            return {}

    def read_conversation(self, project_hash, session_id, last_n=50):
        p = self.projects_dir / project_hash / f"{session_id}.jsonl"
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return []
        lines = lines[-last_n:] if len(lines) > last_n else lines
        return self._parse(lines)

    def read_full_conversation(self, project_hash, session_id):
        p = self.projects_dir / project_hash / f"{session_id}.jsonl"
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return []
        return self._parse(lines)

    def get_system_info(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            cc_procs, vscode_count = [], 0
            for proc in psutil.process_iter(["pid", "name", "memory_info", "exe"]):
                try:
                    name = (proc.info["name"] or "").lower()
                    exe = (proc.info["exe"] or "").lower()
                    if "claude" in name or "claude" in exe:
                        mi = proc.info["memory_info"]
                        cc_procs.append({"pid": proc.info["pid"],
                                         "memory_mb": round(mi.rss / 1024**2, 1) if mi else 0})
                    if "code" in name and "electron" in name:
                        vscode_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return {"cpu_percent": cpu, "memory_percent": mem.percent,
                    "memory_used_gb": round(mem.used / 1024**3, 1),
                    "memory_total_gb": round(mem.total / 1024**3, 1),
                    "cc_processes": cc_procs, "cc_count": len(cc_procs),
                    "vscode_count": vscode_count,
                    "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1)}
        except ImportError:
            return {"error": "psutil not installed"}

    def search_projects(self, query):
        return [p for p in self.list_projects() if query.lower() in p["path"].lower()]

    def _read_meta(self, p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 20: break
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "user" and "cwd" in obj:
                            return {"cwd": obj["cwd"], "entrypoint": obj.get("entrypoint", ""), "version": obj.get("version", "")}
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return {}

    def _is_running(self, pid):
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

    def _parse(self, lines):
        messages = []
        for line in lines:
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type")
            if t not in ("user", "assistant"): continue
            msg = obj.get("message", {})
            content = msg.get("content", [])
            text_parts, tools = [], []
            for b in content:
                if isinstance(b, dict):
                    if b.get("type") == "text": text_parts.append(b.get("text", ""))
                    elif b.get("type") == "tool_use": tools.append(b.get("name", "unknown"))
                elif isinstance(b, str): text_parts.append(b)
            parsed = {"type": t, "text": "\n".join(text_parts),
                      "timestamp": obj.get("timestamp", ""), "uuid": obj.get("uuid", "")}
            if t == "assistant":
                parsed["model"] = msg.get("model", "")
                parsed["tool_uses"] = tools
                parsed["tokens"] = msg.get("usage", {})
            messages.append(parsed)
        return messages
