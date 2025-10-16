from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import atexit
import socket
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import requests

from proxy.models import Proxy
from tools.chrome_dist import get_chrome_path
from tools.lock_manager import ProfileLock
from tools.logging_setup import app_root, get_logger
import tools.worker_chrome as worker_tools

ROOT = app_root()
log = get_logger(__name__)

DEFAULT_PROXY = Proxy(
    scheme="https",
    host="213.139.222.220",
    port=9869,
    username="nDRYz5",
    password="EP0wPC",
)


def _ensure_text(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


# ---------- Local proxy wrapper to avoid Chrome auth prompts ----------
_LOCAL_WRAPPERS: dict[str, subprocess.Popen] = {}


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ensure_pproxy() -> None:
    try:
        import pproxy  # noqa: F401
    except Exception:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "pproxy>=2.7"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pproxy>=2.7"])  # last resort


def _start_local_proxy_wrapper(profile_id: str, scheme: str, host: str, port: int, user: str, password: str) -> str:
    _ensure_pproxy()
    local_port = _pick_free_port()
    upstream = f"{scheme}://{user}:{password}@{host}:{int(port)}"
    listen = f"http://127.0.0.1:{local_port}"
    cmd = [sys.executable, "-m", "pproxy", "-l", listen, "-r", upstream, "-q"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    time.sleep(0.5)
    _LOCAL_WRAPPERS[str(profile_id)] = proc
    log.info("Local proxy wrapper started: %s -> %s", listen, upstream)
    return listen


def _stop_local_proxy_wrapper(profile_id: str) -> None:
    proc = _LOCAL_WRAPPERS.pop(str(profile_id), None)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _cleanup_all_wrappers() -> None:
    for pid in list(_LOCAL_WRAPPERS.keys()):
        _stop_local_proxy_wrapper(pid)


aexit = atexit.register(_cleanup_all_wrappers)


# -------------------- Helpers kept for compatibility --------------------

def _create_pac_file(host: str, port: int, scheme: str) -> Path:
    directive = {"http": "PROXY", "https": "HTTPS", "socks4": "SOCKS", "socks5": "SOCKS5"}.get(scheme.lower(), "PROXY")
    pac_dir = Path(tempfile.mkdtemp(prefix="aichrome_pac_"))
    pac_path = pac_dir / "proxy.pac"
    pac_source = f"""function FindProxyForURL(url, host) {{
  return "{directive} {host}:{port}; DIRECT";
}}"""
    _ensure_text(pac_path, pac_source)
    return pac_path


def detect_proxy_type(proxy: Proxy) -> Tuple[str, str, int, Optional[str], Optional[str]]:
    scheme = (proxy.scheme or "http").lower()
    host = proxy.host
    port = int(proxy.port)
    return scheme, host, port, proxy.username, proxy.password


def _parse_proxy_string(proxy_string: str) -> Proxy:
    import re
    pattern = r"^(?:(?P<scheme>[a-zA-Z0-9]+)://)?(?:(?P<user>[^:@]+)(?::(?P<pwd>[^@]*))?@)?(?P<host>[^:]+):(?P<port>\d+)$"
    m = re.match(pattern, proxy_string.strip())
    if not m:
        raise ValueError(f"Invalid proxy format: {proxy_string}")
    g = m.groupdict()
    return Proxy(
        scheme=(g.get("scheme") or "http").lower(),
        host=g["host"],
        port=int(g["port"]),
        username=g.get("user"),
        password=g.get("pwd"),
    )


def _proxy_self_test(proxy: Proxy, timeout: float = 7.0) -> Optional[Tuple[str, Optional[str]]]:
    url = proxy.url(with_auth=True)
    proxies = {"http": url, "https": url}
    try:
        resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=timeout)
        resp.raise_for_status()
        ip = resp.json().get("ip")
        if not ip:
            return None
        country = None
        try:
            geo = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country", timeout=timeout)
            if geo.ok and geo.json().get("status") == "success":
                country = geo.json().get("country")
        except Exception:
            country = None
        log.info("Proxy self-test OK: ip=%s country=%s", ip, country or "n/a")
        return ip, country
    except Exception as exc:
        log.warning("Proxy self-test failed: %s", exc)
        return None


def detect_worker_chrome() -> Optional[str]:
    path = worker_tools.detect_worker_chrome()
    if path:
        return path
    try:
        return get_chrome_path(allow_system=True)
    except FileNotFoundError:
        return None


def ensure_worker_chrome(auto: bool = False, ask: Optional[Callable[[str, str], bool]] = None) -> Optional[str]:
    try:
        worker_path = worker_tools.ensure_worker_chrome(auto=auto, ask=ask)
        if worker_path:
            return worker_path
    except Exception as exc:
        log.warning("ensure_worker_chrome via tools.worker_chrome failed: %s", exc)
    return detect_worker_chrome()


def _resolve_chrome_path(allow_system_chrome: bool) -> str:
    if allow_system_chrome:
        path = get_chrome_path(allow_system=True)
        log.info("Using system Chrome: %s", path)
        return path
    candidate = detect_worker_chrome()
    if candidate:
        log.info("Using worker Chrome: %s", candidate)
        return candidate
    raise FileNotFoundError("Chrome binary not found. Install Chrome or configure AICHROME_WORKER_DIR.")


def launch_chrome(
    profile_id: str,
    user_agent: Optional[str],
    lang: str,
    tz: Optional[str],
    proxy: Optional[Proxy],
    extra_flags: Optional[List[str]] = None,
    allow_system_chrome: bool = True,
    force_pac: bool = False,
) -> int:
    profile_dir = ROOT / "profiles" / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    lock = ProfileLock(profile_dir)
    lock.acquire()

    try:
        chrome_path = _resolve_chrome_path(allow_system_chrome)

        args = [
            chrome_path,
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=CalculateNativeWinOcclusion,Prerender2",
            "--disable-sync",
            "--disable-translate",
            "--disable-breakpad",
            "--disable-client-side-phishing-detection",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-features=OptimizationHints,MediaRouter",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--metrics-recording-only",
            "--no-pings",
            "--password-store=basic",
            "--process-per-site",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--webrtc-max-cpu-consumption-percentage=1",
            "--disable-features=WebRtcHideLocalIpsWithMdns",
            f"--lang={lang or 'en-US'}",
        ]
        if user_agent:
            args.append(f"--user-agent={user_agent}")

        env = os.environ.copy()
        if tz:
            env["TZ"] = tz

        if proxy:
            scheme, host, port, username, password = detect_proxy_type(proxy)
            _proxy_self_test(proxy)

            if username and password and scheme in {"http", "https"}:
                # Use local wrapper to avoid Chrome auth dialog and any extensions
                local_url = _start_local_proxy_wrapper(profile_id, scheme, host, port, username, password)
                args.append(f"--proxy-server={local_url}")
            else:
                args.append(f"--proxy-server={scheme}://{host}:{port}")
                if force_pac and not (username and password):
                    pac_path = _create_pac_file(host, port, scheme)
                    args.append(f"--proxy-pac-url={pac_path.as_uri()}")
                    log.info("PAC fallback enabled: %s", pac_path)
        else:
            log.info("Launching Chrome without proxy")

        if extra_flags:
            args.extend(extra_flags)

        log.info("Launching Chrome:\n  %s", "\n  ".join(args))
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        lock.update_pid(proc.pid)

        def _cleanup() -> None:
            try:
                proc.wait()
            finally:
                _stop_local_proxy_wrapper(profile_id)
                lock.release_if_dead()

        threading.Thread(target=_cleanup, daemon=True).start()
        return proc.pid

    except Exception:
        try:
            lock.lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def launch_chrome_with_profile(
    profile_name: str = "default",
    user_agent: Optional[str] = None,
    language: str = "en-US",
    timezone: str = "America/New_York",
    extra_args: Optional[List[str]] = None,
    proxy_string: Optional[str] = None,
) -> subprocess.Popen:
    proxy_obj = None
    if proxy_string is None:
        proxy_obj = DEFAULT_PROXY
    else:
        proxy_obj = _parse_proxy_string(proxy_string)

    extra = list(extra_args or [])
    pid = launch_chrome(
        profile_id=profile_name,
        user_agent=user_agent,
        lang=language,
        tz=timezone,
        proxy=proxy_obj,
        extra_flags=extra,
        allow_system_chrome=True,
        force_pac=False,
    )
    log.info("Chrome launched with PID %s", pid)

    class _Proc:
        def __init__(self, pid_: int) -> None:
            self.pid = pid_

    return _Proc(pid)


def self_test_proxy(proxy: Proxy = DEFAULT_PROXY) -> bool:
    return _proxy_self_test(proxy) is not None


if __name__ == "__main__":
    if self_test_proxy():
        log.info("Proxy self-test passed.")
        proc = launch_chrome(
            profile_id="test_profile",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            lang="en-US",
            tz="America/New_York",
            proxy=DEFAULT_PROXY,
            extra_flags=["--window-size=1920,1080"],
        )
        log.info("Chrome launched with PID %s", proc)
    else:
        log.error("Proxy self-test failed. Check proxy configuration.")
