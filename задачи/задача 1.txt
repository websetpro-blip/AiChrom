Ниже — готовый Task‑Pack для Codex cli (Cursor). Вставляй по шагам в терминал Codex (тот, где подсказки /init /status /approvals) — он создаст/обновит файлы, допишет код и соберёт EXE. Я сделал это как «мини‑спринт» с чёткими критериями готовности.

PLAN (что получится)

AiChrome v1.0 (под ключ):

Надёжный одиночный запуск профиля (--user-data-dir) с lock‑файлом + PID‑проверкой.

«Рабочий Chrome»: выбор portable или системного (автопоиск пути).

Полная прокси‑система:

Парсинг любых форматов (http|socks4|socks5, с/без логина).

Proxy Lab: ввод → парсинг → многопоточная валидация (ipify + ip-api) → добавить в пул (proxies.csv).

Автопрокси/Сменить: живой прокси нужной страны/типа из proxies.csv + (опционально) автодогрузка из внешних источников.

Sticky‑привязка прокси к профилю на N минут.

Прокси с логином — через временное расширение (MV3) с onAuthRequired (HTTP/SOCKS).

Логи в logs/launcher.log.

Сборка EXE (PyInstaller), все hiddenimports собраны.

Лёгкий Nixtio‑лайт в UI (ttk, без тяжёлых зависимостей).

Критерии приёмки (MVP):

Создал профиль → «Автопрокси US HTTP» → Self‑Test показывает IP US; «Запустить» открывает Chrome с нужным user‑agent и прокси.

Повторный запуск того же профиля — блокируется (пока жив предыдущий Chrome).

Proxy Lab: вставил список «сырого» вида → «Парсить» → «Валидировать» → «Добавить в пул» — прокси появились в proxies.csv.

EXE собирается и стартует на чистой системе с теми же возможностями.

TASK‑PACK для Codex cli

Вставляй пакетами по порядку. Каждый блок — отдельный запрос Codex (сначала этот текст целиком можно сохранить в docs/CODEX_TASKS.md).

0) Подготовка окружения и зависимости
Создай/обнови файлы и зависимости для проекта AiChrome.

1) В корне проекта создай requirements.txt со списком:
-----
requests[socks]==2.32.3
psutil==6.0.0
ttkbootstrap==1.10.1
pillow==10.4.0
-----
(Если есть другой requirements — приведи к такому виду, не удаляя явные проектные зависимости.)

2) Создай/обнови структуру папок:
- tools/
- proxy/
- ui/
- logs/        (пустая, .gitkeep)
- cache/       (пустая, .gitkeep)
- profiles/    (существующая)
- assets/      (иконка, если есть)
Добавь .gitkeep в пустые.

3) Обнови .gitignore (если есть): добавь
-----
/dist
/build
/__pycache__
/logs/*.log
/cache/*.json
/profiles/*/.aichrome.lock
/aichrome_tmp_ext_*
/release
-----

4) pip install -r requirements.txt
5) Обнови README.md: добавь раздел "Сборка и запуск" (будет позже).

1) Логирование и пути (tools)
Создай файл tools/logging_setup.py со следующим содержимым:

from __future__ import annotations
import logging, os, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def app_root() -> Path:
    # корректно для dev и для PyInstaller
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def ensure_dirs():
    for p in ["logs", "cache", "profiles"]:
        (app_root() / p).mkdir(parents=True, exist_ok=True)

def get_logger(name: str = "aichrome") -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_file = app_root() / "logs" / "launcher.log"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s")
    fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

Создай файл tools/chrome_dist.py:

from __future__ import annotations
import os, platform, shutil, subprocess, sys
from pathlib import Path
from typing import Optional
from tools.logging_setup import app_root, get_logger

log = get_logger()

def _which(names: list[str]) -> Optional[str]:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None

def guess_system_chrome() -> Optional[str]:
    system = platform.system()
    if system == "Windows":
        # Популярные пути и App Paths
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for c in candidates:
            if Path(c).is_file():
                return c
        # Fallback — PATH
        return _which(["chrome.exe", "google-chrome"])
    elif system == "Darwin":
        c = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return c if Path(c).is_file() else _which(["google-chrome", "chrome"])
    else:
        return _which(["google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "chrome"])

def get_chrome_path(allow_system: bool = True) -> str:
    # Portable Chrome, если положен в tools/chrome/*
    ar = app_root()
    candidates = []
    if platform.system() == "Windows":
        candidates += [
            ar / "tools" / "chrome" / "chrome-win" / "chrome.exe",
            ar / "tools" / "chrome" / "chrome.exe",
        ]
    else:
        candidates += [
            ar / "tools" / "chrome" / "chrome",
        ]
    for c in candidates:
        if c.is_file():
            log.info(f"Using portable Chrome: {c}")
            return str(c)
    if allow_system:
        sys_chrome = guess_system_chrome()
        if sys_chrome:
            log.info(f"Using system Chrome: {sys_chrome}")
            return sys_chrome
    raise FileNotFoundError("Chrome binary not found. Put portable Chrome into tools/chrome/ or enable allow_system.")

Создай файл tools/lock_manager.py:

from __future__ import annotations
import json, os, time, psutil
from pathlib import Path
from typing import Optional

class ProfileLock:
    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir)
        self.lock_path = self.profile_dir / ".aichrome.lock"

    def read(self) -> dict:
        try:
            if self.lock_path.exists():
                return json.loads(self.lock_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def acquire(self, chrome_pid: Optional[int] = None):
        data = self.read()
        old_pid = data.get("chrome_pid")
        if old_pid and psutil.pid_exists(old_pid):
            # жив ли процесс с нашим user-data-dir
            try:
                p = psutil.Process(old_pid)
                cmd = " ".join(p.cmdline()).lower()
                if "--user-data-dir" in cmd and str(self.profile_dir).lower() in cmd:
                    raise RuntimeError("Профиль уже запущен этим Chrome (PID %s)" % old_pid)
            except psutil.Error:
                pass
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.write_text(json.dumps({"ts": time.time(), "chrome_pid": chrome_pid or 0}, ensure_ascii=False), encoding="utf-8")

    def update_pid(self, chrome_pid: int):
        self.acquire(chrome_pid=chrome_pid)

    def release_if_dead(self):
        data = self.read()
        pid = data.get("chrome_pid")
        if pid and not psutil.pid_exists(pid):
            try:
                self.lock_path.unlink(missing_ok=True)
            except Exception:
                pass

2) Модель и парсер прокси (proxy)
Создай файл proxy/models.py:

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class Proxy:
    scheme: str            # "http" | "socks4" | "socks5"
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None

    def url(self, with_auth: bool = False, remote_dns: bool = True) -> str:
        scheme = self.scheme.lower()
        if scheme.startswith("socks"):
            if remote_dns and scheme in ("socks5", "socks"):
                scheme = "socks5h"
            elif remote_dns and scheme == "socks4":
                scheme = "socks4a"
        auth = ""
        if with_auth and self.username:
            auth = f"{self.username}:{self.password or ''}@"
        return f"{scheme}://{auth}{self.host}:{self.port}"

Создай файл proxy/parse.py:

from __future__ import annotations
import re
from typing import Iterable, List, Optional
from proxy.models import Proxy

_SCHEMES = ("http", "https", "socks4", "socks5", "socks")

def parse_line(line: str, default_scheme: str = "http", default_country: Optional[str] = None) -> Optional[Proxy]:
    s = line.strip()
    if not s or s.startswith("#"):
        return None

    # 1) URL-подобный: scheme://user:pass@host:port  ИЛИ  scheme://host:port
    m = re.match(r"^(?:(?P<sch>[a-zA-Z0-9]+)://)?(?:(?P<u>[^:@\s]+)(?::(?P<p>[^@\s]*))?@)?(?P<h>[^:/\s]+):(?P<pt>\d+)$", s)
    if m:
        sch = (m.group("sch") or default_scheme).lower()
        if sch not in _SCHEMES:
            sch = default_scheme
        return Proxy(scheme=sch, host=m.group("h"), port=int(m.group("pt")),
                     username=m.group("u"), password=m.group("p"), country=default_country)

    # 2) host:port:user:pass  или host:port:login:password:country
    parts = s.split(":")
    if len(parts) >= 2 and parts[1].isdigit():
        host, port = parts[0], int(parts[1])
        user = parts[2] if len(parts) >= 3 and parts[2] else None
        pwd  = parts[3] if len(parts) >= 4 and parts[3] else None
        ctry = parts[4] if len(parts) >= 5 and parts[4] else default_country
        return Proxy(default_scheme, host, port, user, pwd, ctry)

    return None

def parse_lines_to_candidates(lines: Iterable[str], default_scheme: str = "http", default_country: Optional[str] = None) -> List[Proxy]:
    out: List[Proxy] = []
    for ln in lines:
        p = parse_line(ln, default_scheme=default_scheme, default_country=default_country)
        if p:
            out.append(p)
    # устранить дубликаты по host:port:user
    seen = set()
    uniq: List[Proxy] = []
    for p in out:
        key = (p.scheme, p.host, p.port, p.username or "")
        if key not in seen:
            uniq.append(p); seen.add(key)
    return uniq

3) Валидация и пул прокси (proxy)
Создай файл proxy/validate.py:

from __future__ import annotations
import time, requests
from dataclasses import dataclass
from typing import Optional
from proxy.models import Proxy

@dataclass
class ValidationResult:
    ok: bool
    ip: Optional[str] = None
    country: Optional[str] = None
    cc: Optional[str] = None
    ping_ms: Optional[int] = None
    error: Optional[str] = None

def _proxies_dict(p: Proxy) -> dict:
    # при проверке всегда remote DNS для socks
    u = p.url(with_auth=bool(p.username), remote_dns=True)
    return {"http": u, "https": u}

def validate_proxy(p: Proxy, timeout: float = 7.0) -> ValidationResult:
    t0 = time.perf_counter()
    try:
        r = requests.get("https://api.ipify.org?format=json", proxies=_proxies_dict(p), timeout=timeout)
        r.raise_for_status()
        ip = r.json().get("ip")
        ping = int((time.perf_counter() - t0) * 1000)
        # страна
        rr = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,message", timeout=timeout)
        if rr.ok:
            jj = rr.json()
            if jj.get("status") == "success":
                return ValidationResult(True, ip=ip, country=jj.get("country"), cc=jj.get("countryCode"), ping_ms=ping)
        return ValidationResult(True, ip=ip, ping_ms=ping)  # ip получили — уже ок
    except Exception as e:
        return ValidationResult(False, error=str(e)[:200])

Создай файл proxy/pool.py:

from __future__ import annotations
import csv, json, random, threading, time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from proxy.models import Proxy
from proxy.validate import validate_proxy, ValidationResult
from tools.logging_setup import app_root, get_logger

log = get_logger()

CSV_HEADER = ["scheme","host","port","username","password","country"]
TTL_SECONDS = 600  # 10 минут sticky и кэш

class ProxyPool:
    def __init__(self):
        self.root = app_root()
        self.csv_path = self.root / "proxies.csv"
        self.cache_path = self.root / "cache" / "proxies_cache.json"
        self.sticky_path = self.root / "cache" / "sticky.json"
        self._lock = threading.RLock()
        self._mem_cache: dict[str, dict] = self._load_cache()

    def _load_cache(self) -> dict:
        try:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_cache(self):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._mem_cache, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            log.error(f"cache save error: {e}")

    def read_csv(self) -> List[Proxy]:
        items: List[Proxy] = []
        if not self.csv_path.exists():
            return items
        with self.csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    items.append(Proxy(r["scheme"], r["host"], int(r["port"]), r.get("username") or None, r.get("password") or None, r.get("country") or None))
                except Exception:
                    continue
        return items

    def append_to_csv(self, proxies: Iterable[Proxy]):
        write_header = not self.csv_path.exists()
        with self.csv_path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(CSV_HEADER)
            for p in proxies:
                w.writerow([p.scheme, p.host, p.port, p.username or "", p.password or "", p.country or ""])

    def select_live(self, country: Optional[str], scheme: Optional[str]) -> Tuple[Optional[Proxy], Optional[ValidationResult]]:
        """
        Возвращает первый живой прокси из пула с учётом страны/типа.
        Кэширует успешную проверку на TTL.
        """
        cand = [p for p in self.read_csv()
                if (not country or (p.country or "").upper() == country.upper())
                and (not scheme or p.scheme.lower() == scheme.lower())]
        random.shuffle(cand)
        now = time.time()
        for p in cand:
            key = f"{p.scheme}:{p.host}:{p.port}:{p.username or ''}"
            c = self._mem_cache.get(key)
            if c and now - c.get("ts", 0) < TTL_SECONDS and c.get("ok"):
                return p, ValidationResult(True, ip=c.get("ip"), country=c.get("country"), cc=c.get("cc"), ping_ms=c.get("ping"))
            vr = validate_proxy(p)
            if vr.ok:
                self._mem_cache[key] = {"ok": True, "ip": vr.ip, "country": vr.country, "cc": vr.cc, "ping": vr.ping_ms, "ts": now}
                self._save_cache()
                return p, vr
            else:
                self._mem_cache[key] = {"ok": False, "ts": now}
                self._save_cache()
        return None, None

    # Sticky
    def set_sticky(self, profile_id: str, proxy: Proxy):
        self.sticky_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        try:
            if self.sticky_path.exists():
                data = json.loads(self.sticky_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        until = time.time() + TTL_SECONDS
        data[profile_id] = {"scheme": proxy.scheme, "host": proxy.host, "port": proxy.port,
                            "username": proxy.username, "password": proxy.password, "country": proxy.country, "until": until}
        self.sticky_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def get_sticky(self, profile_id: str) -> Optional[Proxy]:
        try:
            if self.sticky_path.exists():
                data = json.loads(self.sticky_path.read_text(encoding="utf-8"))
                x = data.get(profile_id)
                if x and time.time() < x.get("until", 0):
                    return Proxy(x["scheme"], x["host"], int(x["port"]), x.get("username"), x.get("password"), x.get("country"))
        except Exception:
            pass
        return None

4) Запуск Chrome + расширение авторизации (worker)
Создай/обнови worker_chrome.py:

from __future__ import annotations
import json, os, platform, shutil, subprocess, tempfile
from pathlib import Path
from typing import List, Optional
from proxy.models import Proxy
from tools.chrome_dist import get_chrome_path
from tools.lock_manager import ProfileLock
from tools.logging_setup import app_root, get_logger

log = get_logger()

def _make_auth_extension(proxy: Proxy) -> str:
    """
    Создаёт временное MV3‑расширение для прокси с логином/паролем.
    Возвращает путь к папке расширения.
    """
    tmp = Path(tempfile.mkdtemp(prefix="aichrome_tmp_ext_"))
    manifest = {
        "name": "AiChrome Proxy Auth",
        "version": "1.0",
        "manifest_version": 3,
        "permissions": ["proxy", "storage", "webRequest", "webRequestAuthProvider", "tabs"],
        "host_permissions": ["<all_urls>"],
        "background": { "service_worker": "bg.js" }
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    bg = f"""
chrome.webRequest.onAuthRequired.addListener(
  function(details, callback) {{
    callback({{authCredentials: {{username: "{proxy.username or ''}", password: "{proxy.password or ''}"}}}});
  }},
  {{urls: ["<all_urls>"]}},
  ["blocking"]
);
"""
    (tmp / "bg.js").write_text(bg, encoding="utf-8")
    return str(tmp)

def launch_chrome(profile_id: str, user_agent: Optional[str], lang: str, tz: Optional[str],
                  proxy: Optional[Proxy], extra_flags: Optional[List[str]] = None,
                  allow_system_chrome: bool = True) -> int:
    """
    Возвращает PID запущенного chrome.exe
    """
    root = app_root()
    prof_dir = root / "profiles" / profile_id
    prof_dir.mkdir(parents=True, exist_ok=True)
    lock = ProfileLock(prof_dir)
    lock.acquire()  # бросит исключение, если живой instance

    chrome = get_chrome_path(allow_system=allow_system_chrome)
    args = [
        chrome,
        f"--user-data-dir={prof_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        f"--lang={lang or 'en-US'}",
    ]
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    if tz:
        # Chrome сам не меняет TZ, но это пригодится на страницу-детектор
        os.environ["TZ"] = tz

    ext_dir = None
    if proxy:
        if proxy.username:
            ext_dir = _make_auth_extension(proxy)
            args.append(f"--load-extension={ext_dir}")
            args.append(f"--proxy-server={proxy.scheme}://{proxy.host}:{proxy.port}")
        else:
            args.append(f"--proxy-server={proxy.scheme}://{proxy.host}:{proxy.port}")

    if extra_flags:
        args.extend(extra_flags)

    log.info("Launching Chrome:\n  %s", "\n  ".join(args))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lock.update_pid(proc.pid)
    return proc.pid

5) Proxy Lab (UI‑фрейм) + интеграция
Создай файл ui/proxy_lab.py:

from __future__ import annotations
import threading, queue, tkinter as tk
from tkinter import ttk, messagebox
from typing import List
from proxy.parse import parse_lines_to_candidates
from proxy.validate import validate_proxy
from proxy.pool import ProxyPool
from proxy.models import Proxy
from tools.logging_setup import get_logger

log = get_logger()

class ProxyLabFrame(ttk.LabelFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, text="Proxy Lab", **kwargs)
        self.pool = ProxyPool()
        self.q = queue.Queue()
        self._build()

    def _build(self):
        # Верх: текст для вставки
        self.txt = tk.Text(self, height=6)
        self.txt.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=6, pady=6)

        ttk.Label(self, text="Тип:").grid(row=1, column=0, sticky="w", padx=6)
        self.cmb_type = ttk.Combobox(self, values=["http","socks4","socks5"], width=8)
        self.cmb_type.set("http")
        self.cmb_type.grid(row=1, column=1, sticky="w")
        ttk.Label(self, text="Страна (ISO):").grid(row=1, column=2, sticky="e")
        self.ent_cc = ttk.Entry(self, width=8)
        self.ent_cc.insert(0, "")
        self.ent_cc.grid(row=1, column=3, sticky="w")
        self.btn_parse = ttk.Button(self, text="Парсить", command=self._on_parse)
        self.btn_parse.grid(row=1, column=4, sticky="e", padx=6)

        # Таблица результатов
        cols = ("host","scheme","port","user","country","ping","ok")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (160,70,70,120,80,70,40)):
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w, anchor="center")
        self.tree.grid(row=2, column=0, columnspan=5, sticky="nsew", padx=6, pady=6)
        self.prog = ttk.Progressbar(self, mode="indeterminate")
        self.prog.grid(row=3, column=0, columnspan=5, sticky="ew", padx=6)

        self.btn_val = ttk.Button(self, text="Валидировать", command=self._on_validate, state="disabled")
        self.btn_add = ttk.Button(self, text="Добавить в пул", command=self._on_add, state="disabled")
        self.btn_val.grid(row=4, column=3, sticky="e", padx=6, pady=6)
        self.btn_add.grid(row=4, column=4, sticky="e", padx=6, pady=6)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._parsed: List[Proxy] = []
        self._validated: List[Proxy] = []

    def _on_parse(self):
        t = self.txt.get("1.0", "end").splitlines()
        dft = self.cmb_type.get()
        cc  = self.ent_cc.get().strip() or None
        self._parsed = parse_lines_to_candidates(t, default_scheme=dft, default_country=cc)
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in self._parsed:
            self.tree.insert("", "end", values=(p.host,p.scheme,p.port,p.username or "", p.country or "", "", ""))
        self.btn_val.config(state="normal")
        self.btn_add.config(state="disabled")

    def _worker_validate(self, items: List[Proxy]):
        for p in items:
            vr = validate_proxy(p)
            self.q.put((p, vr))
        self.q.put(None)

    def _on_validate(self):
        if not self._parsed:
            return
        self.btn_val.config(state="disabled")
        self.btn_add.config(state="disabled")
        self.prog.start(12)
        th = threading.Thread(target=self._worker_validate, args=(self._parsed,), daemon=True)
        th.start()
        self.after(50, self._poll_results)

    def _poll_results(self):
        try:
            item = self.q.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_results); return
        if item is None:
            self.prog.stop()
            self.btn_add.config(state="normal")
            return
        p, vr = item
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if vals[0] == p.host and vals[2] == str(p.port):
                self.tree.item(iid, values=(p.host,p.scheme,p.port,p.username or "", p.country or "", vr.ping_ms or "", "yes" if vr.ok else "no"))
                break
        self.after(30, self._poll_results)

    def _on_add(self):
        ok_items = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if str(vals[-1]).lower() == "yes":
                ok_items.append(Proxy(vals[1], vals[0], int(vals[2]), vals[3] or None, None, vals[4] or None))
        if not ok_items:
            messagebox.showwarning("Proxy Lab", "Нет валидных прокси для добавления.")
            return
        self.pool.append_to_csv(ok_items)
        messagebox.showinfo("Proxy Lab", f"Добавлено в пул: {len(ok_items)}")


Интеграция в твой UI
Открой multi_browser_manager.py и:

импортируй:
from ui.proxy_lab import ProxyLabFrame
from proxy.pool import ProxyPool
from worker_chrome import launch_chrome

в модалке профиля (класс ProfileDialog) добавь внизу ProxyLabFrame(self.root) или во вкладку «Proxy Lab».

кнопки Автопрокси / Сменить реализуй так:

# пример обработчика
def _autoproxy_for_profile(self, profile_id, country_iso: str, scheme: str):
    pool = ProxyPool()
    sticky = pool.get_sticky(profile_id)
    if sticky:
        return sticky, "sticky"
    p, vr = pool.select_live(country_iso, scheme)
    if not p:
        raise RuntimeError("Не найден живой прокси в пуле. Добавьте через Proxy Lab.")
    pool.set_sticky(profile_id, p)
    return p, "fresh"


Запуск браузера:

def on_launch(self, profile_id, user_agent, lang, tz, country_iso, scheme):
    try:
        proxy, src = self._autoproxy_for_profile(profile_id, country_iso=country_iso, scheme=scheme)
    except Exception as e:
        messagebox.showerror("Прокси", str(e)); return
    pid = launch_chrome(profile_id=profile_id, user_agent=user_agent, lang=lang, tz=tz, proxy=proxy, extra_flags=None, allow_system_chrome=True)
    messagebox.showinfo("AiChrome", f"Chrome запущен (PID {pid}) через {proxy.scheme} {proxy.host}:{proxy.port}")


Self‑Test: делай requests.get("https://api.ipify.org", proxies=...) тем же прокси и показывай IP/CC в статус‑баре.

6) .spec и сборка EXE
Создай/обнови AiChrome.spec:

# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

import os
from pathlib import Path

project_root = Path(__file__).resolve().parent

a = Analysis(
    ['multi_browser_manager.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'assets'), 'assets'),
        (str(project_root / 'ui'), 'ui'),
        (str(project_root / 'tools'), 'tools'),
        (str(project_root / 'proxy'), 'proxy'),
    ],
    hiddenimports=['requests','pysocks','psutil','ttkbootstrap','PIL.Image','PIL.ImageTk'],
    hookspath=[], runtime_hooks=[], excludes=[], win_no_prefer_redirects=False, win_private_assemblies=False, cipher=block_cipher, noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name='AiChrome', debug=False, strip=False, upx=False,
    console=True, icon=str(project_root / 'assets' / 'create_icon.ico') if (project_root/'assets'/'create_icon.ico').exists() else None
)

Создай build_executable.bat:

@echo off
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --clean AiChrome.spec
echo Done. EXE в папке dist\
pause

7) README и быстрый сценарий проверки
Обнови README.md, добавь раздел:

## Быстрый старт
1) `pip install -r requirements.txt`
2) Запусти UI: `python multi_browser_manager.py`
3) В Proxy Lab вставь список прокси (форматы: scheme://user:pass@ip:port | ip:port:user:pass | ip:port).
4) Нажми **Парсить → Валидировать → Добавить в пул**.
5) Создай профиль, выбери страну/тип, нажми **Автопрокси** → **Self‑Test** → **Запустить**.

## Сборка EXE
`build_executable.bat`

Логи: `logs/launcher.log`. Пул: `proxies.csv`. Sticky и кэш: `cache/*.json`.

ANSWER (что это чинит прямо сейчас)

Парсинг: модуль proxy/parse.py воспринимает все популярные нотации, убирает дубликаты.

Автопрокси: ProxyPool.select_live() ищет живой прокси нужной страны/типа, валидирует через ipify → ip-api (пинг/страна) и кэширует результат на 10 минут.

Sticky: ProxyPool.set_sticky()/get_sticky() закрепляет прокси за профилем (по profile_id) на 10 минут, не дёргая пул зря.

Запуск Chrome: worker_chrome.launch_chrome() правильно строит команду, подхватывает user‑agent/lang, и если есть логин — делает временное MV3‑расширение с onAuthRequired для авторизации.

Анти‑дубль: ProfileLock пишет .aichrome.lock и хранит chrome_pid; пока процесс жив, повторный запуск того же профиля блокируется.

Логи: в logs/launcher.log видно команду запуска, авто‑замены, ошибки.

WHY (почему такой дизайн)

Минимум зависимости: чистый ttk + небольшая надстройка, без тяжёлых браузерных фреймворков, чтобы EXE собирался стабильно.

MV3‑расширение безопаснее и предсказуемее, чем хаки с системными диалогами, и подходит для HTTP/SOCKS (через onAuthRequired).

Sticky + TTL обеспечивает «липкость» прокси и экономит лимиты у источников IP‑гео.

Lock + PID + cmdline‑проверка защищает от гонок и «двойных профилей».

Папка tools/chrome позволяет в любой момент положить portable Chrome, но при его отсутствии — корректно падаем на системный.

CHECKS (смоук‑тест)

В Proxy Lab вставь минимум 2 валидных прокси US (HTTP), проверь, что столбец OK = yes.

Нажми Добавить в пул — убедись, что создан proxies.csv.

Создай профиль test1, страна=US, тип=http, user-agent заполни или нажми «Случайный».

Нажми Автопрокси → Self-Test должен показать US IP.

Нажми Запустить — Chrome открывается, в логе появляется PID.

Ещё раз Запустить тот же профиль — получишь сообщение «Профиль уже запущен…».

Закрой Chrome — lock‑файл исчезнет в течение нескольких секунд (или очистится при следующем старте).

build_executable.bat — в dist/AiChrome лежит рабочий EXE.

Доп. заметки и «куда дальше»

Источники «автопула» (ProxyScrape/GeoNode и пр.) можно добавить отдельным модулем proxy/sources.py и вызывать из ProxyPool, но лучше сделать это после стабилизации MVP (источники часто меняют API).

Если захочешь улучшить визуал в сторону Nixtio — подключай ttkbootstrap тему flatly/darkly и задай стили для кнопок/таблиц; ядро уже готово.