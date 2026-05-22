"""CC 消息发送器 — 通过 CLI --resume 注入消息到会话"""
import asyncio
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("cc_dashboard")


class ClaudeSender:
    def __init__(self, claude_binary: str = None):
        if claude_binary is None:
            claude_binary = str(Path.home() / ".claude" / "local" / "claude")
        self.claude_binary = claude_binary

    async def send_message(self, session_id: str, message: str,
                          cwd: str = None, timeout: int = 300) -> dict:
        args = [
            self.claude_binary, "--print",
            "--resume", session_id,
            message,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]
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
