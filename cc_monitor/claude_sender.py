"""CC 消息发送器 — 通过 CLI --resume 注入消息到会话"""
import asyncio
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("cc_dashboard")

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects"


def detect_model_from_session(session_id: str) -> str:
    """Read the JSONL for this session and return the model name from the first assistant message."""
    # Find the JSONL file across all project dirs
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        jsonl = proj_dir / f"{session_id}.jsonl"
        if not jsonl.exists():
            continue
        try:
            with open(jsonl, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "assistant":
                            model = obj.get("message", {}).get("model", "")
                            if model and model != "<synthetic>":
                                return model
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    return ""


class ClaudeSender:
    def __init__(self, claude_binary: str = None):
        if claude_binary is None:
            claude_binary = str(Path.home() / ".claude" / "local" / "claude")
        self.claude_binary = claude_binary

    async def send_message(self, session_id: str, message: str,
                          cwd: str = None, model: str = None,
                          timeout: int = 300) -> dict:
        # Auto-detect model from session JSONL if not provided
        if not model:
            model = detect_model_from_session(session_id)
        args = [
            self.claude_binary, "--print",
            "--resume", session_id,
            message,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]
        if model:
            args.extend(["--model", model])
        success, stdout, stderr, duration = await self._run_claude(args, cwd, timeout)
        if not success:
            return {
                "success": False, "response": "",
                "error": stderr or stdout or "Unknown error",
                "session_id": session_id, "duration_seconds": duration,
            }
        parsed = self._parse_output(stdout)
        return {
            "success": True,
            "response": parsed.get("result", stdout),
            "session_id": parsed.get("session_id", session_id),
            "error": None,
            "duration_seconds": duration,
            "usage": parsed.get("usage", {}),
        }

    async def send_message_stream(self, session_id: str, message: str,
                                   cwd: str = None, model: str = None):
        """Launch CLI with stream-json output and yield parsed lines as async generator."""
        if not model:
            model = detect_model_from_session(session_id)
        args = [
            self.claude_binary, "--print",
            "--resume", session_id,
            message,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if model:
            args.extend(["--model", model])
        logger.info(f"[CC STREAM] session={session_id[:12]} model={model}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            async for line in proc.stdout:
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                    yield obj
                except json.JSONDecodeError:
                    yield {"type": "raw", "text": text}
            await proc.wait()
            yield {"type": "done", "returncode": proc.returncode}
        except Exception as e:
            logger.error(f"[CC STREAM] error: {e}")
            yield {"type": "error", "message": str(e)}

    async def start_new_session(self, message: str, cwd: str = None,
                               model: str = None, timeout: int = 300) -> dict:
        args = [
            self.claude_binary, "-p",
            message,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]
        if model:
            args.extend(["--model", model])
        success, stdout, stderr, duration = await self._run_claude(args, cwd, timeout)
        if not success:
            return {
                "success": False, "response": "", "session_id": None,
                "error": stderr or stdout or "Unknown error",
                "duration_seconds": duration,
            }
        parsed = self._parse_output(stdout)
        return {
            "success": True,
            "response": parsed.get("result", stdout),
            "session_id": parsed.get("session_id"),
            "error": None,
            "duration_seconds": duration,
            "usage": parsed.get("usage", {}),
        }

    async def upload_image(self, image_path: str, message: str = "请分析这张图片",
                          session_id: str = None, cwd: str = None,
                          timeout: int = 300) -> dict:
        # Image upload via CLI requires further testing
        # For now, send message with image path reference
        full_msg = f"{message}\n\n[图片路径: {image_path}]"
        if session_id:
            return await self.send_message(session_id, full_msg, cwd, timeout)
        return await self.start_new_session(full_msg, cwd, timeout=timeout)

    async def _run_claude(self, args: list[str], cwd: str = None,
                         timeout: int = 300) -> tuple[bool, str, str, float]:
        start = time.time()
        # Log command but redact potential API keys
        safe_args = [a if len(a) < 50 else a[:20] + "..." for a in args]
        logger.info(f"[CC SEND] {' '.join(safe_args[:4])}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            duration = time.time() - start
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            success = proc.returncode == 0
            return success, stdout, stderr, duration
        except asyncio.TimeoutError:
            duration = time.time() - start
            try:
                proc.kill()
            except Exception:
                pass
            return False, "", f"超时 ({timeout}秒)", duration
        except FileNotFoundError:
            duration = time.time() - start
            return False, "", f"Claude 二进制未找到: {self.claude_binary}", duration
        except Exception as e:
            duration = time.time() - start
            return False, "", str(e), duration

    def _parse_output(self, raw_output: str) -> dict:
        raw_output = raw_output.strip()
        if not raw_output:
            return {"result": ""}
        try:
            data = json.loads(raw_output)
            if isinstance(data, dict):
                return {
                    "result": data.get("result", data.get("text", raw_output)),
                    "session_id": data.get("session_id"),
                    "usage": data.get("usage", {}),
                }
        except (json.JSONDecodeError, ValueError):
            pass
        return {"result": raw_output}
