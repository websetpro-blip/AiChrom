from __future__ import annotations
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _proc_cmdline(pid: int) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            output = subprocess.check_output(
                [
                    "wmic",
                    "process",
                    "where",
                    f"ProcessId={pid}",
                    "get",
                    "CommandLine",
                ],
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                text=True,
            )
            lines = [ln.strip() for ln in output.splitlines() if ln.strip() and ln.strip().lower() != "commandline"]
            return " ".join(lines)
        proc_path = Path(f"/proc/{pid}/cmdline")
        if proc_path.exists():
            return proc_path.read_text(errors="ignore").replace("\0", " ")
    except Exception:
        pass
    return ""


def _normalize_path(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


class ProfileLock:
    """Prevent double launching of the same Chrome profile."""

    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir)
        self.lock_path = self.profile_dir / ".aichrome.lock"

    def read(self) -> dict:
        try:
            if self.lock_path.exists():
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if not content:
                    return {}
                
                # Пробуем распарсить как JSON
                try:
                    data = json.loads(content)
                    # Если это число (старый формат), конвертируем в новый
                    if isinstance(data, (int, str)):
                        try:
                            pid = int(data)
                            return {"chrome_pid": pid, "ts": 0}
                        except (ValueError, TypeError):
                            return {}
                    return data if isinstance(data, dict) else {}
                except json.JSONDecodeError:
                    # Если не JSON, пробуем как простое число (старый формат)
                    try:
                        pid = int(content)
                        return {"chrome_pid": pid, "ts": 0}
                    except (ValueError, TypeError):
                        return {}
        except Exception:
            pass
        return {}

    def acquire(self, chrome_pid: Optional[int] = None) -> None:
        data = self.read()
        old_pid = data.get("chrome_pid")
        if old_pid and _pid_exists(old_pid):
            cmd = _proc_cmdline(old_pid).lower().replace("\\", "/")
            profile_str = _normalize_path(self.profile_dir)
            if "--user-data-dir" in cmd and profile_str in cmd:
                raise RuntimeError(f"Профиль уже запущен (PID {old_pid})")
            else:
                try:
                    self.lock_path.unlink(missing_ok=True)
                except Exception:
                    pass
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": time.time(), "chrome_pid": chrome_pid or 0}
        self.lock_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def update_pid(self, chrome_pid: int) -> None:
        self.acquire(chrome_pid=chrome_pid)

    def release_if_dead(self) -> None:
        data = self.read()
        pid = data.get("chrome_pid")
        if pid and not _pid_exists(pid):
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass
