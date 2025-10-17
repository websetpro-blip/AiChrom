from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import atexit
import socket
import ssl
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

# Import websocket for CDP
try:
    from websocket import create_connection
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

ROOT = app_root()
log = get_logger(__name__)

DEFAULT_PROXY = Proxy(
    scheme="https",
    host="213.139.222.220",
    port=9869,
    username="nDRYz5",
    password="EP0wPC",
)

# Kazakhstan presets for geo/language/timezone
KZ_ACCEPT_LANGUAGE = "ru-KZ,ru;q=0.9,kk-KZ;q=0.8,en-US;q=0.7"
KZ_TZ = "Asia/Almaty"  # UTC+5 for all Kazakhstan since 2024-03-01
KZ_ALMATY_GEO = {"latitude": 43.2567, "longitude": 76.9286, "accuracy": 50}
KZ_ASTANA_GEO = {"latitude": 51.1801, "longitude": 71.4460, "accuracy": 50}


def _ensure_text(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


_LOCAL_WRAPPERS: dict[str, subprocess.Popen] = {}


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ensure_pproxy() -> None:
    try:
        import pproxy  # noqa: F401
    except Exception:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "pproxy>=2.7"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _wait_listen(port: int, deadline_sec: float = 3.0) -> bool:
    start = time.time()
    while time.time() - start < deadline_sec:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _start_local_proxy_wrapper(
    profile_id: str,
    scheme: str,
    host: str,
    port: int,
    user: str,
    password: str,
) -> Optional[str]:
    candidates: List[str] = []
    scheme_lower = (scheme or "http").lower()
    if scheme_lower == "https":
        candidates.append(f"http+ssl://{user}:{password}@{host}:{port}")
    candidates.append(f"http://{user}:{password}@{host}:{port}")

    for upstream in candidates:
        try:
            _ensure_pproxy()
            local_port = _pick_free_port()
            listen = f"http://127.0.0.1:{local_port}"
            cmd = [sys.executable, "-m", "pproxy", "-l", listen, "-r", upstream]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not _wait_listen(local_port):
                proc.kill()
                continue
            _LOCAL_WRAPPERS[profile_id] = proc
            log.info("Local proxy wrapper started: %s -> %s", listen, upstream)
            return listen
        except Exception as exc:
            log.error("Wrapper attempt failed (%s): %s", upstream, exc)
            _stop_local_proxy_wrapper(profile_id)
    return None


def _stop_local_proxy_wrapper(profile_id: str) -> None:
    proc = _LOCAL_WRAPPERS.pop(profile_id, None)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _cleanup_all_wrappers() -> None:
    for pid in list(_LOCAL_WRAPPERS.keys()):
        _stop_local_proxy_wrapper(pid)


atexit.register(_cleanup_all_wrappers)


def _build_accept_language(language: str) -> str:
    lang = (language or "en-US").replace("_", "-")
    parts = [lang]
    primary = lang.split("-")[0]
    lowered = {lang.lower()}
    if primary and primary.lower() not in lowered:
        parts.append(f"{primary};q=0.9")
        lowered.add(primary.lower())
    if "en-us" not in lowered:
        parts.append("en-US;q=0.8")
        lowered.add("en-us")
    if "en" not in lowered:
        parts.append("en;q=0.7")
    return ",".join(parts)


def _apply_profile_preferences(profile_dir: Path, *, language: str) -> None:
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    pref_path = default_dir / "Preferences"
    data: dict = {}
    if pref_path.exists():
        try:
            data = json.loads(pref_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    intl = data.setdefault("intl", {})
    intl["accept_languages"] = _build_accept_language(language)

    webrtc = data.setdefault("webrtc", {})
    webrtc["ip_handling_policy"] = "disable_non_proxied_udp"
    webrtc["multiple_routes_enabled"] = False
    webrtc["nonproxied_udp_enabled"] = False

    profile_prefs = data.setdefault("profile", {})
    defaults = profile_prefs.setdefault("default_content_setting_values", {})
    defaults["geolocation"] = 2  # block geolocation prompts

    data["credentials_enable_service"] = False
    profile_prefs["password_manager_enabled"] = False

    pref_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_chrome_major_version(chrome_path: str) -> str:
    """Extract Chrome major version"""
    try:
        output = subprocess.check_output([chrome_path, "--version"], text=True, timeout=5).strip()
        match = re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", output)
        return match.group(1) if match else "120"
    except Exception:
        return "120"


def _cdp_call(ws, method: str, params: Optional[dict] = None, _id=[0]) -> dict:
    """Make a CDP (Chrome DevTools Protocol) call"""
    _id[0] += 1
    payload = {"id": _id[0], "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == _id[0]:
            if "error" in msg:
                raise RuntimeError(f"CDP error {method}: {msg['error']}")
            return msg.get("result", {})


def _apply_cdp_overrides(debug_port: int, chrome_path: str, user_agent: Optional[str], 
                         lang: str, tz: Optional[str], geo: Optional[dict] = None) -> None:
    """Apply UA/Language/Timezone/Geo through Chrome DevTools Protocol"""
    if not HAS_WEBSOCKET:
        log.warning("websocket-client not installed, skipping CDP overrides")
        return
    
    try:
        # Get WebSocket debugger URL
        version_url = f"http://127.0.0.1:{debug_port}/json/version"
        ver_response = requests.get(version_url, timeout=5)
        ver = ver_response.json()
        ws_url = ver["webSocketDebuggerUrl"]
        
        # Build User-Agent (Chrome, not Firefox!)
        if not user_agent or "Chrome/" not in user_agent:
            major = _get_chrome_major_version(chrome_path)
            user_agent = (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         f"AppleWebKit/537.36 (KHTML, like Gecko) "
                         f"Chrome/{major}.0.0.0 Safari/537.36")
        
        accept_language = lang or KZ_ACCEPT_LANGUAGE
        timezone_id = tz or KZ_TZ
        
        # Connect and apply overrides
        ws = create_connection(ws_url, timeout=5)
        try:
            # Set User-Agent and Accept-Language
            _cdp_call(ws, "Emulation.setUserAgentOverride", {
                "userAgent": user_agent,
                "acceptLanguage": accept_language
            })
            log.info("CDP: Set UA and Accept-Language")
            
            # Set Timezone
            if timezone_id:
                _cdp_call(ws, "Emulation.setTimezoneOverride", {"timezoneId": timezone_id})
                log.info(f"CDP: Set timezone to {timezone_id}")
            
            # Set Geolocation
            if geo:
                _cdp_call(ws, "Emulation.setGeolocationOverride", geo)
                log.info(f"CDP: Set geolocation to {geo}")
                
        finally:
            ws.close()
            
    except Exception as exc:
        log.warning(f"Failed to apply CDP overrides: {exc}")


def _create_pac_file(host: str, port: int, scheme: str) -> Path:
    directive = {
        "http": "PROXY",
        "https": "HTTPS",
        "socks4": "SOCKS",
        "socks5": "SOCKS5",
    }.get(scheme.lower(), "PROXY")
    pac_dir = Path(tempfile.mkdtemp(prefix="aichrome_pac_"))
    pac_path = pac_dir / "proxy.pac"
    pac_source = f"""function FindProxyForURL(url, host) {{
  return \"{directive} {host}:{port}; DIRECT\";
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

    pattern = r"^(?:(?P<scheme>[a-zA-Z0-9]+)://)?(?:(?P<user>[^:@]+)(?::(?P<pwd>[^@]*))?@)?(?P<host>[^:]+):(?P<port>\d+)"  # noqa: E501
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
    scheme, host, port, username, password = detect_proxy_type(proxy)
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
            geo = requests.get(
                f"http://ip-api.com/json/{ip}?fields=status,country",
                proxies=proxies,
                timeout=timeout,
            )
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
    path = get_chrome_path(allow_system=allow_system_chrome)
    log.info("Using system Chrome: %s", path)
    return path


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

    cleanup_paths: List[Path] = []
    wrapper_id = str(profile_id)
    wrapper_url: Optional[str] = None

    try:
        chrome_path = _resolve_chrome_path(allow_system_chrome)
        
        # Pick a free port for remote debugging (CDP)
        debug_port = _pick_free_port()

        args = [
            chrome_path,
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={debug_port}",
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
                wrapper_url = _start_local_proxy_wrapper(wrapper_id, scheme, host, port, username, password)

            if wrapper_url:
                args.append(f"--proxy-server={wrapper_url}")
            else:
                args.append(f"--proxy-server={scheme}://{host}:{port}")
                if force_pac and not (username and password):
                    pac_path = _create_pac_file(host, port, scheme)
                    cleanup_paths.append(pac_path.parent)
                    args.append(f"--proxy-pac-url={pac_path.as_uri()}")
                    log.info("PAC fallback enabled: %s", pac_path)
                elif force_pac:
                    log.info("PAC fallback skipped because proxy requires authentication.")
                if scheme.startswith("socks") and username and password:
                    log.warning("SOCKS authentication with wrapper not implemented; Chrome may prompt for credentials.")
        else:
            log.info("Launching Chrome without proxy")

        if extra_flags:
            args.extend(extra_flags)

        _apply_profile_preferences(profile_dir, language=lang or "en-US")

        logs_dir = ROOT / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "launcher.log").write_text(" ".join(args), encoding="utf-8")

        log.info("Launching Chrome:\n  %s", "\n  ".join(args))
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        lock.update_pid(proc.pid)
        
        # Wait for Chrome to start and apply CDP overrides
        time.sleep(2)
        try:
            # Use Kazakhstan preset if language is Kazakh/Russian
            geo = None
            if lang and any(x in lang.lower() for x in ["ru-kz", "kk-kz", "ru_kz"]):
                geo = KZ_ALMATY_GEO  # Default to Almaty
            
            _apply_cdp_overrides(
                debug_port=debug_port,
                chrome_path=chrome_path,
                user_agent=user_agent,
                lang=lang or "en-US",
                tz=tz,
                geo=geo
            )
        except Exception as exc:
            log.warning(f"CDP overrides failed (non-critical): {exc}")

        def _cleanup() -> None:
            try:
                proc.wait()
            finally:
                if wrapper_url:
                    _stop_local_proxy_wrapper(wrapper_id)
                for path in cleanup_paths:
                    try:
                        if path.is_dir():
                            shutil.rmtree(path, ignore_errors=True)
                        elif path.is_file():
                            path.unlink(missing_ok=True)
                    except Exception:
                        pass
                lock.release_if_dead()

        threading.Thread(target=_cleanup, daemon=True).start()
        return proc.pid

    except Exception:
        if wrapper_url:
            _stop_local_proxy_wrapper(wrapper_id)
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
    proxy_obj = DEFAULT_PROXY if proxy_string is None else _parse_proxy_string(proxy_string)
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
            lang="ru-RU",
            tz="Asia/Almaty",
            proxy=DEFAULT_PROXY,
            extra_flags=["--window-size=1920,1080"],
        )
        log.info("Chrome launched with PID %s", proc)
    else:
        log.error("Proxy self-test failed. Check your proxy configuration.")
