# -*- coding: utf-8 -*-
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
import psutil

from proxy.models import Proxy
from tools.chrome_dist import get_chrome_path
from tools.lock_manager import ProfileLock
from tools.logging_setup import app_root, get_logger
import tools.worker_chrome as worker_tools
from aichrom.cdp_overrides import (
    apply_geo,
    apply_tz,
    apply_ua_lang,
    ws_url_from_port,
)
from aichrom.presets import DEFAULT_CHROME_UA, GEO_PRESETS, label_by_key

# Import websocket for CDP
try:
    from websocket import create_connection
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

ROOT = app_root()
log = get_logger(__name__)


def _resolve_chrome_binary(profile: dict, chrome_path: str = None) -> str:
    """
    Порядок выбора Chrome бинаря:
    1) chrome_path из аргумента (если задан и файл существует)
    2) profile["chrome_path"] (если существует файл)
    3) (fallback) get_chrome_path() - portable Chrome из tools/chrome/ или системный
    """
    # 1) chrome_path из аргумента
    if chrome_path and Path(chrome_path).is_file():
        log.info("Using Chrome from argument: %s", chrome_path)
        return chrome_path

    # 2) chrome_path из профиля
    p = (profile or {}).get("chrome_path")
    if p and p.strip() and Path(p).is_file():
        log.info("Using Chrome from profile: %s", p)
        return p

    # 3) fallback - используем старую логику get_chrome_path (portable + системный)
    try:
        c = get_chrome_path(allow_system=True)
        log.info("Using fallback Chrome: %s", c)
        return c
    except FileNotFoundError:
        raise RuntimeError("Chrome binary not found. Укажи 'Браузер (exe)' в профиле или помести portable Chrome в tools/chrome/.")

# Функции блокировки профилей
def _user_data_dir_for(profile_id: str) -> Path:
    return Path("profiles") / str(profile_id)

def _lock_path_for(user_data_dir: Path) -> Path:
    return user_data_dir / ".aichrome.lock"

def _find_running_chrome(user_data_dir: Path):
    """Вернёт psutil.Process если Chrome уже запущен с этим --user-data-dir."""
    target = str(user_data_dir).replace("\\", "/")
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            if "chrome" not in name and "chromium" not in name:
                continue
            cmd = " ".join(p.info["cmdline"] or [])
            if f"--user-data-dir={target}" in cmd:
                return p
        except psutil.Error:
            pass
    return None

def _acquire_profile_lock(user_data_dir: Path) -> bool:
    """Создаёт lock c PID текущего процесса-лаунчера.
       Если есть живой Chrome с этим профилем — отказ (False). Сдохший lock — очищаем и берём."""
    lock = _lock_path_for(user_data_dir)
    if lock.exists():
        try:
            data = lock.read_text(encoding="utf-8").strip()
            pid = int(data or "0")
            if pid and psutil.pid_exists(pid):
                # Дополнительно сверим, не висит ли именно chrome с этим профилем
                if _find_running_chrome(user_data_dir):
                    return False
            # lock протух — удалим
        except Exception:
            pass
        try:
            lock.unlink()
        except Exception:
            pass
    try:
        lock.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        return False

def _release_profile_lock(user_data_dir: Path):
    try:
        _lock_path_for(user_data_dir).unlink(missing_ok=True)
    except Exception:
        pass

DEFAULT_PROXY = Proxy(
    scheme="https",
    host="213.139.222.220",
    port=9869,
    username="nDRYz5",
    password="EP0wPC",
)

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
    profile_key = str(profile_id)
    if scheme_lower == "https":
        candidates.append(f"http+ssl://{host}:{port}#{user}:{password}")
    if user and password:
        # Используем правильный синтаксис для pproxy с # для аутентификации
        candidates.append(f"http://{host}:{port}#{user}:{password}")
    else:
        candidates.append(f"http://{host}:{port}")

    for upstream in candidates:
        try:
            log.info("Trying pproxy wrapper: %s", upstream)
            _ensure_pproxy()
            local_port = _pick_free_port()
            listen = f"http://127.0.0.1:{local_port}"
            cmd = [sys.executable, "-m", "pproxy", "-l", listen, "-r", upstream]
            log.info("Starting pproxy: %s", " ".join(cmd))
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("pproxy process started with PID: %s", proc.pid)
            
            if not _wait_listen(local_port):
                log.error("pproxy failed to bind to port %s, killing process", local_port)
                proc.kill()
                continue
                
            _LOCAL_WRAPPERS[profile_key] = proc
            log.info("Local proxy wrapper started: %s -> %s", listen, upstream)
            return listen
        except Exception as exc:
            log.error("Wrapper attempt failed (%s): %s", upstream, exc)
            _stop_local_proxy_wrapper(profile_key)
    return None


def _stop_local_proxy_wrapper(profile_id: str) -> None:
    proc = _LOCAL_WRAPPERS.pop(str(profile_id), None)
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


def _apply_profile_preferences(
    profile_dir: Path, *, accept_language: str, force_webrtc: bool
) -> None:
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
    intl["accept_languages"] = accept_language

    if force_webrtc:
        webrtc = data.setdefault("webrtc", {})
        webrtc["ip_handling_policy"] = "disable_non_proxied_udp"
        webrtc["multiple_routes_enabled"] = False
        webrtc["nonproxied_udp_enabled"] = False
    else:
        if "webrtc" in data:
            for key in ("ip_handling_policy", "multiple_routes_enabled", "nonproxied_udp_enabled"):
                data["webrtc"].pop(key, None)
            if not data["webrtc"]:
                data.pop("webrtc")

    profile_prefs = data.setdefault("profile", {})
    defaults = profile_prefs.setdefault("default_content_setting_values", {})
    defaults["geolocation"] = 2  # block geolocation prompts

    data["credentials_enable_service"] = False
    profile_prefs["password_manager_enabled"] = False

    pref_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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


def _normalize_preset(preset: Optional[str]) -> str:
    key = (preset or "none").strip()
    return key if key in GEO_PRESETS else "none"


def _resolve_accept_language(lang: Optional[str], preset_cfg: dict) -> str:
    candidate = (lang or "").strip()
    if candidate:
        if "," in candidate or ";" in candidate:
            return candidate
        return _build_accept_language(candidate)
    value = preset_cfg.get("accept_language")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _build_accept_language("en-US")


def _resolve_timezone(tz: Optional[str], preset_cfg: dict) -> Optional[str]:
    candidate = (tz or "").strip()
    if candidate:
        return candidate
    value = preset_cfg.get("timezone")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _resolve_geo(preset_cfg: dict) -> Optional[dict]:
    geo = preset_cfg.get("geo")
    if isinstance(geo, dict):
        return dict(geo)
    return None


def _lang_cli_value(accept_language: str, preset_cfg: dict) -> str:
    custom = preset_cfg.get("lang_cli")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    if not accept_language:
        return "en-US"
    token = accept_language.split(",")[0].strip()
    token = token.split(";")[0].strip()
    return token or "en-US"


def launch_chrome(
    profile_id: str,
    user_agent: Optional[str],
    lang: str,
    tz: Optional[str],
    proxy: Optional[Proxy],
    extra_flags: Optional[List[str]] = None,
    allow_system_chrome: bool = True,
    force_pac: bool = False,
    preset: str = "none",
    apply_cdp_overrides: bool = True,
    profile: dict = None,
    chrome_path: str = None,
    force_webrtc_proxy: bool = True,
) -> int:
    """
    Стартует один (!) Chrome для профиля.
    Возвращает PID процесса Chrome или поднятого psutil.Process, если уже запущен.
    """
    user_data_dir = _user_data_dir_for(profile_id)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # Если уже есть запущенный — не стартуем второй
    running = _find_running_chrome(user_data_dir)
    if running:
        log.info(f"[launch] profile {profile_id} already running pid={running.pid}")
        return running.pid

    # Жёсткая защита lock-файлом
    if not _acquire_profile_lock(user_data_dir):
        log.info(f"[launch] lock busy for {profile_id}, skip second launch")
        # финальный дубль-чек — вдруг lock чужой, а процесса нет
        running = _find_running_chrome(user_data_dir)
        if running:
            return running.pid
        # как fallback — снимем lock и пойдём дальше
        try:
            _release_profile_lock(user_data_dir)
        except Exception:
            pass

    # выбираем один браузер, без двойных попыток
    chrome_binary = _resolve_chrome_binary(profile or {}, chrome_path)
    if not chrome_binary:
        _release_profile_lock(user_data_dir)
        raise RuntimeError("Chrome not found")

    cleanup_paths: List[Path] = []
    wrapper_id = str(profile_id)
    wrapper_url: Optional[str] = None

    try:
        preset_key = _normalize_preset(preset)
        preset_cfg = GEO_PRESETS.get(preset_key, GEO_PRESETS["none"])
        accept_language = _resolve_accept_language(lang, preset_cfg)
        timezone_id = _resolve_timezone(tz, preset_cfg)
        geo = _resolve_geo(preset_cfg)
        lang_flag = _lang_cli_value(accept_language, preset_cfg)

        # Pick a free port for remote debugging (CDP)
        debug_port = _pick_free_port()

        args = [
            chrome_binary,
            f"--user-data-dir={user_data_dir}",
            f"--remote-debugging-port={debug_port}",
            f"--remote-allow-origins=*",
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
            f"--lang={lang_flag}",
        ]
        if force_webrtc_proxy:
            args.extend(
                [
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--webrtc-max-cpu-consumption-percentage=1",
                    "--disable-features=WebRtcHideLocalIpsWithMdns",
                ]
            )
        preset_user_agent = preset_cfg.get("user_agent") if preset_key != "none" else None
        raw_user_agent = user_agent or preset_user_agent or (DEFAULT_CHROME_UA if preset_key != "none" else "")
        effective_user_agent = str(raw_user_agent).strip()
        if effective_user_agent:
            args.append(f"--user-agent={effective_user_agent}")
        else:
            effective_user_agent = None
        user_agent = effective_user_agent

        env = os.environ.copy()
        if timezone_id:
            env["TZ"] = timezone_id

        if proxy:
            scheme, host, port, username, password = detect_proxy_type(proxy)
            log.info("Proxy detected: scheme=%s host=%s port=%s username=%s password=%s", 
                    scheme, host, port, username, "***" if password else None)
            _proxy_self_test(proxy)

            if username and password and scheme in {"http", "https"}:
                log.info("Creating pproxy wrapper for authenticated proxy")
                wrapper_url = _start_local_proxy_wrapper(wrapper_id, scheme, host, port, username, password)
                log.info("Wrapper URL: %s", wrapper_url)
            else:
                log.info("No wrapper created - username=%s password=%s scheme=%s", 
                        bool(username), bool(password), scheme)

            if wrapper_url:
                args.append(f"--proxy-server={wrapper_url}")
                log.info("Using wrapper proxy: %s", wrapper_url)
            else:
                args.append(f"--proxy-server={scheme}://{host}:{port}")
                log.info("Using direct proxy: %s://%s:%s", scheme, host, port)
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

        _apply_profile_preferences(
            user_data_dir,
            accept_language=accept_language,
            force_webrtc=force_webrtc_proxy,
        )

        logs_dir = ROOT / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "launcher.log").write_text(" ".join(args), encoding="utf-8")

        log.info(
            "Launching Chrome (preset=%s, lang=%s, tz=%s, geo=%s):\n  %s",
            f"{preset_key} | {label_by_key(preset_key)}",
            accept_language,
            timezone_id or "default",
            geo or "none",
            "\n  ".join(args),
        )
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        
        # перезаписываем lock PID'ом Chrome, не питона-лаунчера — удобнее проверять
        try:
            import json
            import time
            lock_data = {"ts": time.time(), "chrome_pid": proc.pid}
            _lock_path_for(user_data_dir).write_text(json.dumps(lock_data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        
        # Ждем пока Chrome запустится и CDP станет доступен
        time.sleep(3)
        if apply_cdp_overrides:
            if not HAS_WEBSOCKET:
                log.warning("websocket-client not installed, skipping CDP overrides")
            else:
                try:
                    ws_url = ws_url_from_port(debug_port)
                    apply_ua_lang(
                        ws_url,
                        chrome_path,
                        accept_language,
                        user_agent=user_agent,
                    )
                    if timezone_id:
                        apply_tz(ws_url, timezone_id)
                    if geo:
                        apply_geo(
                            ws_url,
                            geo["latitude"],
                            geo["longitude"],
                            geo.get("accuracy", 50),
                        )
                    log.info("CDP overrides applied successfully")
                except Exception as exc:
                    log.warning("CDP overrides failed: %s", exc)

        # перезаписываем lock PID'ом Chrome, не питона-лаунчера — удобнее проверять
        try:
            _lock_path_for(user_data_dir).write_text(str(proc.pid), encoding="utf-8")
        except Exception:
            pass

        # лог финальной команды
        log.info("Final Chrome command: %s", " ".join(args))

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
                _release_profile_lock(user_data_dir)

        threading.Thread(target=_cleanup, daemon=True).start()
        return proc.pid

    except Exception:
        if wrapper_url:
            _stop_local_proxy_wrapper(wrapper_id)
        _release_profile_lock(user_data_dir)
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
        preset="none",
        apply_cdp_overrides=True,
        force_webrtc_proxy=True,
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



