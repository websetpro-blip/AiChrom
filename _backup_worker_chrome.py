from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
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

# Default proxy settings (used by legacy helper functions)
DEFAULT_PROXY = Proxy(
    scheme="https",
    host="213.139.222.220",
    port=9869,
    username="nDRYz5",
    password="EP0wPC",
)


def _ensure_text(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


def create_proxy_auth_extension(host: str, port: int, username: str, password: str, scheme: str) -> Path:
    """
    Generate a temporary Manifest V3 extension that supplies proxy credentials via onAuthRequired.
    Chrome no longer accepts user:pass in --proxy-server for HTTPS proxies, so we emulate
    what commercial antidetect browsers do: inject credentials through MV3 background worker.
    """
    extension_dir = Path(tempfile.mkdtemp(prefix="aichrome_proxy_auth_"))
    manifest = {
        "manifest_version": 2,
        "name": "AiChrome Proxy Auth",
        "version": "1.0.0",
        "permissions": [
            "proxy",
            "tabs",
            "storage",
            "unlimitedStorage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking",
            "webRequestAuthProvider",
        ],
        "background": {"scripts": ["background.js"], "persistent": True},
    }
    background_js = f"""
chrome.proxy.settings.set(
  {{
    value: {{
      mode: "fixed_servers",
      rules: {{
        singleProxy: {{
          scheme: {json.dumps(scheme)},
          host: {json.dumps(host)},
          port: {int(port)}
        }},
        bypassList: ["localhost", "127.0.0.1"]
      }}
    }},
    scope: "regular"
  }},
  function() {{}}
);

chrome.webRequest.onAuthRequired.addListener(
  function(details) {{
    return {{
      authCredentials: {{
        username: {json.dumps(username)},
        password: {json.dumps(password)}
      }}
    }};
  }},
  {{ urls: ["<all_urls>"] }},
  ["blocking"]
);
"""
    _ensure_text(extension_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    _ensure_text(extension_dir / "background.js", background_js.strip())
    log.info("Created proxy-auth MV3 extension: %s", extension_dir)
    return extension_dir


def _create_webrtc_block_extension() -> Path:
    """
    Optional helper to block WebRTC leaks (kept for parity with previous releases).
    """
    ext_dir = Path(tempfile.mkdtemp(prefix="aichrome_webrtc_block_"))
    manifest = {
        "manifest_version": 3,
        "name": "AiChrome WebRTC Block",
        "version": "1.0.0",
        "background": {"service_worker": "blocker.js"},
        "permissions": ["scripting"],
        "host_permissions": ["<all_urls>"],
    }
    service_worker = r"""
chrome.runtime.onInstalled.addListener(() => {
  const script = {
    target: { allFrames: true, tabId: 0 },
    func: () => {
      try {
        const noop = () => { throw new Error("WebRTC disabled"); };
        if (window.RTCPeerConnection) {
          window.RTCPeerConnection.prototype.createOffer = noop;
          window.RTCPeerConnection.prototype.createAnswer = noop;
        }
        if (window.webkitRTCPeerConnection) {
          window.webkitRTCPeerConnection.prototype.createOffer = noop;
          window.webkitRTCPeerConnection.prototype.createAnswer = noop;
        }
        if (navigator.mediaDevices?.getUserMedia) {
          navigator.mediaDevices.getUserMedia = () => Promise.reject(new Error("WebRTC disabled"));
        }
      } catch (e) {}
    }
  };
  chrome.scripting.registerContentScripts([{
    id: "aichrome-webrtc",
    js: ["content.js"],
    matches: ["<all_urls>"],
    runAt: "document_start"
  }]);
});
"""
    content_js = ""
    _ensure_text(ext_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    _ensure_text(ext_dir / "blocker.js", service_worker.strip())
    _ensure_text(ext_dir / "content.js", content_js)
    return ext_dir


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
    match = re.match(pattern, proxy_string.strip())
    if not match:
        raise ValueError(f"Invalid proxy format: {proxy_string}")
    groups = match.groupdict()
    scheme = (groups.get("scheme") or "http").lower()
    port = int(groups["port"])
    return Proxy(
        scheme=scheme,
        host=groups["host"],
        port=port,
        username=groups.get("user"),
        password=groups.get("pwd"),
    )


def _proxy_self_test(proxy: Proxy, timeout: float = 7.0) -> Optional[Tuple[str, Optional[str]]]:
    scheme = (proxy.scheme or "http").lower()
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
    """
    Re-export detection logic so other modules can query available Chrome builds.
    """
    path = worker_tools.detect_worker_chrome()
    if path:
        return path
    try:
        return get_chrome_path(allow_system=True)
    except FileNotFoundError:
        return None


def ensure_worker_chrome(auto: bool = False, ask: Optional[Callable[[str, str], bool]] = None) -> Optional[str]:
    """
    Ensure that a dedicated Chrome for Testing build exists; fall back to system Chrome.
    """
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
    """
    Launch Chrome tied to a profile with full proxy/isolation support.
    This is the entry point used by multi_browser_manager.
    """
    profile_dir = ROOT / "profiles" / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    lock = ProfileLock(profile_dir)
    lock.acquire()

    cleanup_paths: List[Path] = []

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

        extensions: List[str] = []

        if proxy:
            scheme, host, port, username, password = detect_proxy_type(proxy)
            _proxy_self_test(proxy)

            args.append(f"--proxy-server={scheme}://{host}:{port}")

            if force_pac and not (username and password):
                pac_path = _create_pac_file(host, port, scheme)
                cleanup_paths.append(pac_path.parent)
                args.append(f"--proxy-pac-url={pac_path.as_uri()}")
                log.info("PAC fallback enabled: %s", pac_path)
            elif force_pac:
                log.info("PAC fallback skipped because proxy requires authentication.")

            if scheme in {"http", "https"} and username and password:
                ext_dir = create_proxy_auth_extension(host, port, username, password, scheme)
                extensions.append(str(ext_dir))
                cleanup_paths.append(ext_dir)
            elif scheme.startswith("socks") and username and password:
                log.warning("SOCKS authentication is not handled automatically; Chrome may prompt for credentials.")
        else:
            log.info("Launching Chrome without proxy")

        # Optional WebRTC blocker to prevent IP leaks
        try:
            webrtc_ext = _create_webrtc_block_extension()
            extensions.append(str(webrtc_ext))
            cleanup_paths.append(webrtc_ext)
        except Exception as exc:
            log.warning("Failed to prepare WebRTC block extension: %s", exc)

        if extensions:
            joined = ",".join(extensions)
            args.append(f"--load-extension={joined}")
            args.append(f"--disable-extensions-except={joined}")

        if extra_flags:
            args.extend(extra_flags)

        log.info("Launching Chrome:\n  %s", "\n  ".join(args))
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        lock.update_pid(proc.pid)

        def _cleanup() -> None:
            try:
                proc.wait()
            finally:
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
    """
    Backwards-compatible helper used by standalone scripts.
    """
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
    # For legacy compatibility return a dummy object-like wrapper
    class _Proc:
        def __init__(self, pid_: int) -> None:
            self.pid = pid_

    return _Proc(pid)


def self_test_proxy(proxy: Proxy = DEFAULT_PROXY) -> bool:
    result = _proxy_self_test(proxy)
    return result is not None


if __name__ == "__main__":
    if self_test_proxy():
        log.info("Proxy self-test passed.")
        proc = launch_chrome(
            profile_id="test_profile",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            lang="en-US",
            tz="America/New_York",
            proxy=DEFAULT_PROXY,
            extra_flags=["--window-size=1920,1080"],
        )
        log.info("Chrome launched with PID %s", proc)
    else:
        log.error("Proxy self-test failed. Check your proxy configuration.")

