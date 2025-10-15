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