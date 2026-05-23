"""CC Data Reader"""
import json, os, time
from collections import deque
from pathlib import Path

# Permission-related keywords for detecting CC permission prompts
_PERM_KEYWORDS = (
    "allow", "reject", "approve", "deny", "permission",
    "允许", "拒绝", "批准", "授权",
)


class ClaudeReader:
    def __init__(self, claude_home=None):
        if not claude_home:
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
            # Read real path from first JSONL file's cwd field
            real_path = self._resolve_path_from_jsonl(d, jsonl_files)
            projects.append({
                "hash": d.name, "path": real_path or d.name,
                "session_count": len(jsonl_files),
                "last_active": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_active)) if last_active else None,
            })
        projects.sort(key=lambda p: p["last_active"] or "", reverse=True)
        return projects

    def _resolve_path_from_jsonl(self, proj_dir, jsonl_files):
        """Read the cwd field from the first JSONL file to get the real project path"""
        for f in sorted(jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh):
                        if i > 10:
                            break
                        try:
                            obj = json.loads(line)
                            if "cwd" in obj:
                                return obj["cwd"]
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue
        return None

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

    def _build_session_index(self):
        """Build a mapping of session_id -> project_hash for fast lookup."""
        index = {}
        if not self.projects_dir.exists():
            return index
        for proj_dir in self.projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            for f in proj_dir.glob("*.jsonl"):
                index[f.stem] = proj_dir.name
        return index

    def get_cc_status(self):
        """Detect if CC is busy or idle by checking:
        - Lock files in sessions/ directory (pid.json files with recent timestamps)
        - The last message in each active session's JSONL
        - If last assistant message has stop_reason='tool_use', CC is busy
        - If last message is user, CC is processing
        - Otherwise CC is idle
        Return: list of {session_id, cwd, status: 'busy'|'idle'|'waiting', last_activity}
        """
        results = []
        if not self.sessions_dir.exists():
            return results
        # Build session index once for all status lookups
        session_index = self._build_session_index()
        for pid_file in self.sessions_dir.glob("*.json"):
            try:
                pid = int(pid_file.stem)
            except ValueError:
                continue
            info = self._read_session_json(pid)
            if not info:
                continue
            session_id = info.get("sessionId", "")
            cwd = info.get("cwd", "")
            last_activity = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(pid_file.stat().st_mtime),
            )
            status = self._determine_session_status(pid, session_id, cwd, session_index)
            results.append({
                "session_id": session_id,
                "cwd": cwd,
                "status": status,
                "last_activity": last_activity,
            })
        return results

    def _determine_session_status(self, pid, session_id, cwd, session_index=None):
        """Determine a single session's status from its JSONL last line."""
        if not session_id:
            return "idle"
        # Find the JSONL file: use index if available, otherwise scan
        jsonl_path = None
        if session_index and session_id in session_index:
            proj_hash = session_index[session_id]
            candidate = self.projects_dir / proj_hash / f"{session_id}.jsonl"
            if candidate.exists():
                jsonl_path = candidate
        if not jsonl_path and self.projects_dir.exists():
            for proj_dir in self.projects_dir.iterdir():
                if not proj_dir.is_dir():
                    continue
                candidate = proj_dir / f"{session_id}.jsonl"
                if candidate.exists():
                    jsonl_path = candidate
                    break
        if not jsonl_path:
            return "waiting" if self._is_running(pid) else "idle"
        try:
            last_line = self._read_last_line(jsonl_path)
            if not last_line:
                return "idle"
            obj = json.loads(last_line)
            t = obj.get("type")
            if t == "user":
                return "waiting"
            if t == "assistant":
                msg = obj.get("message", {})
                if msg.get("stop_reason") == "tool_use":
                    return "busy"
                return "idle"
        except Exception:
            pass
        return "idle"

    def _read_last_line(self, filepath):
        """Read the last non-empty line from a file efficiently."""
        try:
            with open(filepath, "rb") as f:
                f.seek(0, 2)  # seek to end
                fsize = f.tell()
                if fsize == 0:
                    return None
                # Read last 8KB max, then take last line
                read_size = min(8192, fsize)
                f.seek(-read_size, 2)
                data = f.read().decode("utf-8", errors="replace")
                lines = [l for l in data.splitlines() if l.strip()]
                return lines[-1] if lines else None
        except Exception:
            return None

    def read_conversation(self, project_hash, session_id, last_n=50, offset=0):
        """Read messages with pagination.
        offset=0 means latest, offset=N means skip the latest N parsed messages.
        Returns at most `last_n` parsed messages from the tail after skipping `offset` messages.
        """
        p = self.projects_dir / project_hash / f"{session_id}.jsonl"
        if not p.exists():
            return []
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            # Parse all messages first, then apply offset/last_n on parsed results
            all_messages = self._parse(all_lines)
            if offset == 0:
                return all_messages[-last_n:] if last_n else all_messages
            # Skip the last `offset` parsed messages, then take `last_n`
            trimmed = all_messages[:len(all_messages) - offset] if offset < len(all_messages) else []
            return trimmed[-last_n:] if last_n else trimmed
        except Exception:
            return []

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
            cpu = psutil.cpu_percent(interval=0)
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

    def _read_meta_from_session(self, project_hash, session_id):
        """Read metadata from a session's JSONL by project hash and session id."""
        p = self.projects_dir / project_hash / f"{session_id}.jsonl"
        if not p.exists():
            return {}
        return self._read_meta(p)

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
            # Detect permission dialog in user messages
            if t == "user" and self._detect_permission(content, text_parts):
                parsed["is_permission_prompt"] = True
                parsed["permission_tool"] = tools[0] if tools else ""
            messages.append(parsed)
        return messages

    @staticmethod
    def _detect_permission(content_blocks, text_parts):
        """Check if a user message is a permission dialog from CC.
        Returns True if permission-related keywords are found in the content.
        """
        for block in content_blocks:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                # CC permission prompts often have type 'human' or contain approval buttons
                if block_type in ("human", "permission_request"):
                    return True
                text = (block.get("text") or "").lower()
                if any(kw in text for kw in _PERM_KEYWORDS):
                    return True
            elif isinstance(block, str):
                if any(kw in block.lower() for kw in _PERM_KEYWORDS):
                    return True
        for txt in text_parts:
            lower = txt.lower()
            # Match patterns like "Claude wants to" + permission keyword
            if ("wants to" in lower or "请求" in lower) and any(kw in lower for kw in _PERM_KEYWORDS):
                return True
            if any(f"{kw}?" in lower or f"{kw}：" in lower or f"{kw}:" in lower for kw in _PERM_KEYWORDS):
                return True
        return False
