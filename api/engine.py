import os, json, subprocess, sys, time, uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROFILES_DIR = Path(os.getenv("PROFILES_DIR", BASE / "profiles"))
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
DB = Path(__file__).with_name("profiles.json")
if not DB.exists(): 
    DB.write_text("[]", encoding="utf-8")

def load():
    return json.loads(DB.read_text(encoding="utf-8"))

def save(items):
    DB.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def _ensure_prefs(profile_dir: Path, lang: str):
    default = profile_dir / "Default"
    default.mkdir(parents=True, exist_ok=True)
    prefs = default / "Preferences"
    data = {"intl": {"accept_languages": lang}}
    if prefs.exists():
        try:
            exist = json.loads(prefs.read_text(encoding="utf-8"))
            exist.setdefault("intl", {})["accept_languages"] = lang
            data = exist
        except Exception: 
            pass
    prefs.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

def _attach_proxy_ext(args, p):
    """Расширение для авторизации в прокси (если есть user/pass)."""
    if not p.get("proxy") or "@" not in p["proxy"]:  # формат user:pass@host:port | scheme://user:pass@host:port
        return args
    raw = p["proxy"]
    scheme = "http"
    if "://" in raw:
        scheme, raw = raw.split("://", 1)
    creds, host = raw.split("@", 1)
    user, pwd = creds.split(":", 1)
    host, port = host.split(":", 1)

    ext_dir = (PROFILES_DIR / p["id"] / "ext_proxy_auth")
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "manifest.json").write_text(json.dumps({
        "manifest_version": 3,
        "name": "Proxy Auth Helper",
        "version": "1.0",
        "permissions": ["proxy", "webRequest", "webRequestAuthProvider", "storage", "tabs"],
        "host_permissions": ["<all_urls>"],
        "background": {"service_worker": "background.js"}
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (ext_dir / "background.js").write_text(f"""
chrome.runtime.onInstalled.addListener(() => {{
  const config = {{
    mode: "fixed_servers",
    rules: {{
      singleProxy: {{ scheme: "{scheme}", host: "{host}", port: parseInt("{port}") }},
      bypassList: ["localhost","127.0.0.1"]
    }}
  }};
  chrome.proxy.settings.set({{value: config, scope: "regular"}}, () => {{}});
}});
chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => {{
    callback({{ authCredentials: {{ username: "{user}", password: "{pwd}" }} }});
  }},
  {{ urls: ["<all_urls>"] }},
  ["blocking"]
);
""", encoding="utf-8")

    args += [
        f"--disable-extensions-except={ext_dir.as_posix()}",
        f"--load-extension={ext_dir.as_posix()}"
    ]
    # также добавим --proxy-server на всякий
    args.append(f"--proxy-server={scheme}://{host}:{port}")
    return args

def start_profile(p):
    chrome = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    profile_dir = PROFILES_DIR / p["id"]
    profile_dir.mkdir(parents=True, exist_ok=True)

    lang = p.get("language", "ru-RU")
    _ensure_prefs(profile_dir, lang)

    args = [
        chrome,
        "--no-first-run", "--no-default-browser-check",
        f"--user-agent={p.get('user_agent','Mozilla/5.0 AiChrome')}",
        f"--user-data-dir={profile_dir.resolve()}",
        f"--window-size={p.get('screen_width', 1280)},{p.get('screen_height', 800)}",
        f"--lang={lang}"
    ]
    if p.get("proxy") and "@" not in p["proxy"]:
        # без логина/пароля: scheme://host:port или host:port
        v = p["proxy"]
        if "://" not in v:
            v = "http://" + v
        args.append(f"--proxy-server={v}")
    args = _attach_proxy_ext(args, p)

    env = os.environ.copy()
    if sys.platform != "win32" and p.get("timezone"):
        env["TZ"] = p["timezone"]

    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

def selftest(p):
    """Headless проверка IP (без пароля; с паролем советуем открыть обычный запуск)."""
    chrome = os.getenv("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    args = [chrome, "--headless=new", "--disable-gpu", "--dump-dom", "https://api.ipify.org?format=text"]
    if p.get("proxy") and "@" not in p["proxy"]:
        v = p["proxy"]
        if "://" not in v: 
            v = "http://" + v
        args.append(f"--proxy-server={v}")
    try:
        out = subprocess.check_output(args, timeout=30)
        ip = out.decode().strip()
        return {"ok": True, "ip": ip}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def create_profile():
    items = load()
    pid = uuid.uuid4().hex[:8]
    p = {
        "id": pid, 
        "name": f"Профиль {pid}",
        "language": "ru-RU",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "screen_width": 1280, 
        "screen_height": 800,
        "proxy": "", 
        "timezone": "", 
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "active": False
    }
    items.append(p)
    save(items)
    return p
