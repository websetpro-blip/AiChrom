# tools/worker_chrome.py
from __future__ import annotations
import os, sys, json, zipfile, io, shutil, pathlib, requests, tempfile

BASE_DIR = pathlib.Path(getattr(sys, "frozen", False) and pathlib.Path(sys.executable).parent or pathlib.Path(__file__).resolve().parents[1])
SETTINGS_FILE = BASE_DIR / "settings.json"
WORKER_DIR = pathlib.Path(os.getenv("AICHROME_WORKER_DIR") or r"C:\AI\ChromeWorker")
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
    s = _load_settings()
    s["chrome_worker_path"] = path
    _save_settings(s)

def get_worker_path_from_settings() -> str | None:
    s = _load_settings()
    p = s.get("chrome_worker_path")
    return p if p and pathlib.Path(p).is_file() else None

def detect_worker_chrome() -> str | None:
    # 1) env var has priority
    env = os.getenv("CHROME_PATH_WORKER")
    if env and pathlib.Path(env).is_file():
        return env
    # 2) settings.json
    cfg = get_worker_path_from_settings()
    if cfg: return cfg
    # 3) default folder
    for p in [
        WORKER_DIR / "chrome-win64" / "chrome.exe",
        WORKER_DIR / "chrome-win32" / "chrome.exe",
        WORKER_DIR / "chrome.exe",
    ]:
        if p.is_file():
            return str(p)
    return None

def download_latest_cft_win64() -> str:
    """
    Скачивает Chrome for Testing (Stable/win64) в C:\AI\ChromeWorker и
    возвращает путь к chrome.exe.
    Источник: Chrome for Testing (Google) — стабильный официальный билд.
    """
    # Узнаём последнюю стабильную версию
    meta = requests.get(
        "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json",
        timeout=15,
    ).json()
    ver = meta["channels"]["Stable"]["version"]  # например "127.0.6533.72"
    zip_url = f"https://storage.googleapis.com/chrome-for-testing-public/{ver}/win64/chrome-win64.zip"

    # Скачиваем ZIP в память и распаковываем
    r = requests.get(zip_url, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        # распаковка в WORKER_DIR, полностью затираем старое
        target = WORKER_DIR / "chrome-win64"
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        z.extractall(WORKER_DIR)

    exe = WORKER_DIR / "chrome-win64" / "chrome.exe"
    if not exe.is_file():
        raise RuntimeError("chrome.exe не найден после распаковки.")
    set_worker_path(str(exe))
    return str(exe)

def ensure_worker_chrome(auto=False, ask=None) -> str | None:
    """
    Возвращает путь к chrome.exe рабочего браузера.
    Если не найден — при auto=True пытается скачать без вопросов.
    Если передан ask(title, text)->bool — спросит пользователя о загрузке.
    """
    # 0) если у пользователя явно задан путь переменной окружения — используем его
    env = os.getenv("CHROME_PATH_WORKER")
    if env and pathlib.Path(env).is_file():
        set_worker_path(env)
        return env

    p = detect_worker_chrome()
    if p:  # уже установлен
        return p

    if ask and not auto:
        ok = ask("Установить рабочий Chrome?",
                 "Будет скачан портативный Chrome for Testing (Stable, ~180–250 МБ) "
                 "в C:\\AI\\ChromeWorker. Продолжить?")
        if not ok:
            return None

    # авто-загрузка
    return download_latest_cft_win64()

def _build_auth_extension(host, port, user, pwd, scheme="http"):
    """Создает расширение для авторизации прокси"""
    manifest = {
      "version":"1.0.0","manifest_version":2,"name":"ProxyAuth",
      "permissions":["proxy","tabs","storage","unlimitedStorage","<all_urls>","webRequest","webRequestBlocking"]
    }
    background = f"""
var config={{mode:"fixed_servers",rules:{{singleProxy:{{scheme:"{scheme}",host:"{host}",port:parseInt({int(port)})}},bypassList:["localhost","127.0.0.1"]}}}};
chrome.proxy.settings.set({{value:config,scope:"regular"}},function(){{}});
function cb(d){{return {{authCredentials:{{username:"{user}",password:"{pwd}"}}}};}}
chrome.webRequest.onAuthRequired.addListener(cb,{{urls:["<all_urls>"]}},["blocking"]);
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("background.js", background)
    return buf.getvalue()


def _make_webrtc_block_extension() -> str:
    """Создаёт временное расширение, которое блокирует WebRTC (в document_start).
    Это предотвращает утечку реального IP через WebRTC/STUN.
    """
    tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="aichrome_ext_webrtc_"))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "manifest_version": 2,
        "name": "AiChrome WebRTC Block",
        "version": "1.0",
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": ["block.js"],
                "run_at": "document_start",
            }
        ],
    }
    (tmp_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    block_js = r"""
(function(){
    try {
        // Override RTCPeerConnection to prevent ICE gathering
        const Noop = function() { throw new Error('WebRTC blocked'); };
        if (window.RTCPeerConnection) {
            window.RTCPeerConnection.prototype.createOffer = Noop;
            window.RTCPeerConnection.prototype.createAnswer = Noop;
        }
        if (window.webkitRTCPeerConnection) {
            window.webkitRTCPeerConnection.prototype.createOffer = Noop;
            window.webkitRTCPeerConnection.prototype.createAnswer = Noop;
        }
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia = function() { return Promise.reject(new Error('getUserMedia blocked')); };
        }
    } catch (e) {}
})();
"""
    (tmp_dir / "block.js").write_text(block_js, encoding="utf-8")
    return str(tmp_dir)

def apply_proxy_to_chrome(chrome_args, *, host:str, port:int, proto:str, user:str="", pwd:str=""):
    """Применяет прокси к аргументам Chrome"""
    scheme = {"HTTP":"http","HTTPS":"http","SOCKS5":"socks5","SOCKS4":"socks4"}.get(proto.upper(),"http")
    if user and pwd:
        # С авторизацией - через расширение
        ext_bytes = _build_auth_extension(host, port, user, pwd, scheme)
        ext_path = os.path.abspath(f"proxy_auth_{host.replace('.','_')}_{port}.zip")
        with open(ext_path,"wb") as f: 
            f.write(ext_bytes)
        # Принудительно разрешаем только это расширение и загружаем его —
        # это помогает в случае, когда Chrome блокирует загрузку расширений
        chrome_args.append(f"--disable-extensions-except={ext_path}")
        chrome_args.append(f"--load-extension={ext_path}")
        # Разрешаем передачу учётных данных для прокси
        chrome_args.append("--auth-server-whitelist=*")
        chrome_args.append("--auth-negotiate-delegate-whitelist=*")
        # Также добавляем временное расширение для блокировки WebRTC, чтобы
        # исключить утечку реального IP через STUN (WebRTC).
        webrtc_ext = _make_webrtc_block_extension()
        chrome_args.append(f"--disable-extensions-except={ext_path};{webrtc_ext}")
        chrome_args.append(f"--load-extension={webrtc_ext}")
    else:
        # Без авторизации - через --proxy-server
        chrome_args.append(f"--proxy-server={scheme}://{host}:{int(port)}")
