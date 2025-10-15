from __future__ import annotations
import io
import json
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Callable, List, Optional

import requests
import tempfile

from proxy.models import Proxy
from tools.chrome_dist import get_chrome_path
from tools.lock_manager import ProfileLock
from tools.logging_setup import app_root, get_logger

log = get_logger(__name__)

BASE_DIR = app_root()
SETTINGS_FILE = BASE_DIR / "settings.json"
WORKER_DIR = Path(os.getenv("AICHROME_WORKER_DIR") or r"C:\AI\ChromeWorker")
WORKER_DIR.mkdir(parents=True, exist_ok=True)


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_settings(data: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_worker_path(path: str) -> None:
    data = _load_settings()
    data["chrome_worker_path"] = path
    _save_settings(data)


def get_worker_path_from_settings() -> Optional[str]:
    data = _load_settings()
    path = data.get("chrome_worker_path")
    if path and Path(path).is_file():
        return path
    return None


def detect_worker_chrome() -> Optional[str]:
    env = os.getenv("CHROME_PATH_WORKER")
    if env and Path(env).is_file():
        return env
    stored = get_worker_path_from_settings()
    if stored:
        return stored
    for candidate in [
        WORKER_DIR / "chrome-win64" / "chrome.exe",
        WORKER_DIR / "chrome-win32" / "chrome.exe",
        WORKER_DIR / "chrome.exe",
    ]:
        if candidate.is_file():
            return str(candidate)
    return None


def download_latest_cft_win64() -> str:
    meta_url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json"
    log.info("worker chrome: fetch metadata %s", meta_url)
    meta = requests.get(meta_url, timeout=20).json()
    version = meta["channels"]["Stable"]["version"]
    zip_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chrome-win64.zip"
    log.info("worker chrome: download %s", zip_url)
    response = requests.get(zip_url, timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        target = WORKER_DIR / "chrome-win64"
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        archive.extractall(WORKER_DIR)
    exe = WORKER_DIR / "chrome-win64" / "chrome.exe"
    if not exe.is_file():
        raise RuntimeError("chrome.exe не найден после распаковки")
    set_worker_path(str(exe))
    return str(exe)


def ensure_worker_chrome(auto: bool = False, ask: Optional[Callable[[str, str], bool]] = None) -> Optional[str]:
    env = os.getenv("CHROME_PATH_WORKER")
    if env and Path(env).is_file():
        set_worker_path(env)
        return env

    found = detect_worker_chrome()
    if found:
        return found

    if ask and not auto:
        if not ask(
            "Установить рабочий Chrome?",
            "Будет скачан Chrome for Testing (Stable) в C:\\AI\\ChromeWorker. Продолжить?",
        ):
            return None

    return download_latest_cft_win64()


def _make_pac_file(proxy: Proxy) -> str:
    """Создаёт PAC файл для прокси с авторизацией"""
    tmp_dir = Path(tempfile.mkdtemp(prefix="aichrome_pac_"))
    pac_content = f"""
function FindProxyForURL(url, host) {{
    return "PROXY {proxy.host}:{proxy.port}";
}}
"""
    pac_file = tmp_dir / "proxy.pac"
    pac_file.write_text(pac_content, encoding="utf-8")
    return str(pac_file)


def _make_auth_extension(proxy: Proxy) -> str:
    """Создаёт расширение (MV3) для установки прокси и автоматической авторизации."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="aichrome_ext_"))
    manifest = {
        "manifest_version": 3,
        "name": "Proxy Auth Helper",
        "version": "1.0",
        "permissions": ["proxy", "webRequest", "webRequestAuthProvider"],
        "host_permissions": ["<all_urls>"],
        "background": {"service_worker": "background.js"},
    }
    (tmp_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    background = f"""
chrome.runtime.onInstalled.addListener(() => {{
  const config = {{
    mode: "fixed_servers",
    rules: {{
      singleProxy: {{ scheme: "{proxy.scheme}", host: "{proxy.host}", port: {int(proxy.port)} }},
      bypassList: ["localhost","127.0.0.1"]
    }}
  }};
  chrome.proxy.settings.set({{value: config, scope: "regular"}}, () => {{
    if (chrome.runtime.lastError) {{
      console.error('Proxy setup failed:', chrome.runtime.lastError);
    }}
  }});
}});

// Use async handling where available. MV3 supports asyncBlocking/webRequestAuthProvider in newer Chrome.
async function provideCredentials(details) {{
  return {{authCredentials: {{username: "{proxy.username or ''}", password: "{proxy.password or ''}"}}}};
}}

chrome.webRequest.onAuthRequired.addListener(
    provideCredentials,
    {{urls: ["<all_urls>"]}},
    ["asyncBlocking"]
);
"""
    (tmp_dir / "background.js").write_text(background, encoding="utf-8")
    return str(tmp_dir)


def _make_webrtc_block_extension() -> str:
    """Creates a Manifest V3 extension to block WebRTC and prevent IP leaks."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="aichrome_ext_webrtc_"))
    manifest = {
        "manifest_version": 3,
        "name": "AiChrome WebRTC Shield",
        "version": "1.0",
        "permissions": ["scripting"],
        "host_permissions": ["<all_urls>"],
        "background": {
            "service_worker": "background.js"
        }
    }
    (tmp_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    background_js = """
// Register a content script to block WebRTC on all pages
chrome.scripting.registerContentScripts([{
  id: 'webrtc-blocker',
  js: ['block.js'],
  matches: ['<all_urls>'],
  runAt: 'document_start',
  world: 'MAIN'
}]);
"""
    (tmp_dir / "background.js").write_text(background_js, encoding="utf-8")
    
    block_js = r"""
(() => {
  try {
    const originalRTCPeerConnection = window.RTCPeerConnection;
    window.RTCPeerConnection = function(...args) {
      console.log('WebRTC blocked by AiChrome Shield.');
      // You can either return a dummy object or throw an error
      // Throwing an error is more explicit.
      throw new Error('WebRTC connection blocked by extension.');
    };
    // It's also good practice to restore the original if needed, though not required for simple blocking
    window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;
  } catch (e) {
    // console.error('Error blocking WebRTC:', e);
  }
})();
"""
    (tmp_dir / "block.js").write_text(block_js, encoding="utf-8")
    return str(tmp_dir)


def launch_chrome(
    profile_id: str,
    user_agent: Optional[str],
    lang: str,
    tz: Optional[str],
    proxy: Optional[Proxy],
    extra_flags: Optional[List[str]] = None,
    allow_system_chrome: bool = True,
) -> int:
    root = app_root()
    profile_dir = root / "profiles" / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    lock = ProfileLock(profile_dir)
    lock.acquire()

    # Приоритет: сначала ищем рабочий Chrome, потом системный
    chrome_path = detect_worker_chrome()
    if chrome_path:
        log.info("Using worker Chrome: %s", chrome_path)
    elif allow_system_chrome:
        try:
            from tools.chrome_dist import guess_system_chrome
            chrome_path = guess_system_chrome()
            if chrome_path:
                log.info("Falling back to system Chrome: %s", chrome_path)
        except Exception:
            pass
    
    if not chrome_path:
        # Если ничего не найдено, показываем ошибку
        raise RuntimeError("Не удалось найти исполняемый файл Chrome. Попробуйте установить рабочий Chrome через главное меню.")

    args = [
        chrome_path,
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        # Improve responsiveness and avoid Win occlusion throttling
        "--disable-renderer-backgrounding",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-features=CalculateNativeWinOcclusion,Prerender2",
        # Performance optimizations to reduce lag and CPU usage
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
        # Reduce process count and improve typing performance
        "--process-per-site",
        # Note: removed flags that disable site isolation and IPC flood protection
        # as they trigger detection heuristics (CfT banner) and can break site behavior.
        f"--lang={lang or 'en-US'}",
    ]
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    if tz:
        os.environ["TZ"] = tz

    extension_dirs: List[str] = []
    pac_file: Optional[str] = None # Not used with MV3 extension, but kept for cleanup logic
    
    if proxy:
        webrtc_ext = _make_webrtc_block_extension()
        extension_dirs.append(webrtc_ext)
        if proxy.username:
            # Modern MV3 extension handles both proxy setup and auth
            auth_ext = _make_auth_extension(proxy)
            extension_dirs.append(auth_ext)
        else:
            # For simple proxies without auth, the direct flag is simplest
            args.append(f"--proxy-server={proxy.scheme}://{proxy.host}:{proxy.port}")
    
    if extension_dirs:
        # Use comma as separator for extension paths on Windows
        load_ext_value = ','.join(extension_dirs)
        args.append(f"--load-extension={load_ext_value}")
        args.append(f"--disable-extensions-except={load_ext_value}")
    else:
        # Disable extensions if we are not loading any
        args.append("--disable-extensions")

    if extra_flags:
        args.extend(extra_flags)

    # Optional: force software rendering to reduce GPU usage
    if os.getenv("AICHROME_SOFTGPU", "0") == "1":
        args.extend([
            "--disable-gpu",
            "--disable-gpu-compositing",
            "--use-gl=swiftshader",
            "--disable-accelerated-2d-canvas",
        ])
    
    # Self-test: verify proxy IP and geolocation before launching
    def _proxy_self_test(p: Proxy) -> bool:
        try:
            resp = requests.get("https://api.ipify.org?format=json", timeout=6)
            ip = resp.json().get("ip")
            if not ip:
                log.warning("Self-test: ipify returned no ip")
                return False
            geo = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,query", timeout=6).json()
            if geo.get("status") != "success":
                log.warning("Self-test: ip-api failed for %s", ip)
                return False
            log.info("Proxy self-test: ip=%s country=%s", geo.get("query"), geo.get("country"))
            return True
        except Exception as e:
            log.exception("Proxy self-test error: %s", e)
            return False

    if proxy:
        ok = _proxy_self_test(proxy)
        if not ok:
            log.warning("Proxy self-test failed — launching anyway but consider verifying proxy")

    log.info("Launching Chrome:\n  %s", "\n  ".join(args))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lock.update_pid(proc.pid)

    def _watch() -> None:
        try:
            proc.wait()
        finally:
            lock.release_if_dead()
            for ed in extension_dirs:
                try:
                    shutil.rmtree(ed, ignore_errors=True)
                except Exception:
                    pass
            if pac_file:
                try:
                    Path(pac_file).parent.rmdir()
                except Exception:
                    pass

    threading.Thread(target=_watch, daemon=True).start()
    return proc.pid
