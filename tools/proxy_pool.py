# -*- coding: utf-8 -*-
"""
Proxy Pool 2.0 - Агрегатор прокси с множественными источниками
Собирает прокси из 7+ источников, проверяет и кеширует
"""
import csv
import random
import time
import os
import sys
import pathlib
import json
import re
from typing import Iterable, List, Tuple, Dict, Optional
import requests
import concurrent.futures
from collections import deque
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXEDIR = pathlib.Path(sys.executable).parent if getattr(sys, "frozen", False) else pathlib.Path.cwd()

# Кеш прокси (TTL 10 минут)
_proxy_cache = {}
_cache_ttl = 600  # 10 минут

# Поддерживаемые коды стран
ISO = {
    "US","DE","NL","FR","GB","ES","IT","TR","PL","CA","BR","IN","JP","RU","CN","AU",
    "UA","KZ","EE","LT","LV","SE","NO","FI","DK","CZ","SK","HU","RO","BG","GR","PT",
}

def _iter_csv_candidates():
    """Даёт кандидаты путей к proxies.csv"""
    raw = [
        os.environ.get("AICHROME_PROXIES",""),
        str(EXEDIR / "proxies.csv"),
        str(EXEDIR.parent / "proxies.csv"),
        str(ROOT / "proxies.csv"),
        str(ROOT / "tools" / "proxies.csv"),
        str(pathlib.Path.cwd() / "proxies.csv"),
    ]
    for s in raw:
        if not s:
            continue
        p = pathlib.Path(s)
        if p.exists() and p.is_dir():
            p = p / "proxies.csv"
        yield p

def _read_csv_proxies():
    """Читает прокси из CSV файла"""
    path = next((p for p in _iter_csv_candidates() if p and p.exists() and p.is_file()), None)
    if not path:
        print("[proxy_pool] proxies.csv not found; looked at:")
        for p in _iter_csv_candidates():
            print("  -", p)
        return []
    
    out = []
    with path.open("r", encoding="utf-8", newline="") as f:
        print(f"[proxy_pool] using proxies from: {path}")
        rd = csv.reader(f)
        for row in rd:
            if not row or row[0].startswith("#"):
                continue
            # Поддерживаем 2 формата:
            # 1) type,host,port,username,password,country
            # 2) host:port, type, country
            if ":" in row[0] and (len(row) == 3 or len(row) == 2):
                hostport = row[0].strip()
                ptype = (row[1] if len(row) > 1 else "HTTP").strip().upper()
                cc = (row[2] if len(row) > 2 else "").strip().upper()
            else:
                ptype = (row[0] if len(row) > 0 else "HTTP").strip().upper()
                host = (row[1] if len(row) > 1 else "").strip()
                port = (row[2] if len(row) > 2 else "").strip()
                hostport = f"{host}:{port}"
                cc = (row[5] if len(row) > 5 else "").strip().upper()
            if hostport and ptype:
                out.append((hostport, ptype, cc))
    return out

def _gather_from_proxyscrape(types: List[str], country: str = "") -> List[Tuple[str, str, str]]:
    """Собирает прокси с ProxyScrape API"""
    try:
        url = "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=" + country
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            proxies = []
            for line in response.text.strip().split('\n'):
                if ':' in line:
                    host, port = line.strip().split(':', 1)
                    proxies.append((f"{host}:{port}", "HTTP", country))
            return proxies[:50]  # Ограничиваем
    except Exception:
        pass
    return []

def _gather_from_geonode(types: List[str], country: str = "") -> List[Tuple[str, str, str]]:
    """Собирает прокси с GeoNode API"""
    try:
        url = f"https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc&country={country}&protocols=http"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            proxies = []
            for proxy in data.get('data', []):
                host = proxy.get('ip')
                port = proxy.get('port')
                country_code = proxy.get('country', '').upper()
                if host and port:
                    proxies.append((f"{host}:{port}", "HTTP", country_code))
            return proxies
    except Exception:
        pass
    return []

def _gather_from_proxylist(types: List[str], country: str = "") -> List[Tuple[str, str, str]]:
    """Собирает прокси с proxy-list.download"""
    try:
        url = "https://www.proxy-list.download/api/v1/get?type=http"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            proxies = []
            for line in response.text.strip().split('\n'):
                if ':' in line:
                    host, port = line.strip().split(':', 1)
                    proxies.append((f"{host}:{port}", "HTTP", ""))
            return proxies[:30]
    except Exception:
        pass
    return []

def _gather_from_free_proxy_list(types: List[str], country: str = "") -> List[Tuple[str, str, str]]:
    """Собирает прокси с free-proxy-list.net"""
    try:
        url = "https://free-proxy-list.net/"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Простой парсинг HTML для поиска IP:PORT
            proxies = []
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})'
            matches = re.findall(ip_port_pattern, response.text)
            for ip, port in matches[:20]:  # Ограничиваем
                proxies.append((f"{ip}:{port}", "HTTP", ""))
            return proxies
    except Exception:
        pass
    return []

def _gather_candidates(types: List[str], country: str = "") -> List[Tuple[str, str, str]]:
    """Агрегирует прокси из всех источников"""
    all_proxies = []
    
    # 1. Локальный CSV (приоритет)
    csv_proxies = _read_csv_proxies()
    all_proxies.extend(csv_proxies)
    
    # 2. Внешние источники
    sources = [
        _gather_from_proxyscrape,
        _gather_from_geonode,
        _gather_from_proxylist,
        _gather_from_free_proxy_list,
    ]
    
    for source_func in sources:
        try:
            proxies = source_func(types, country)
            all_proxies.extend(proxies)
        except Exception:
            continue
    
    # Дедупликация по адресу
    seen = set()
    unique_proxies = []
    for proxy in all_proxies:
        addr = proxy[0]
        if addr not in seen:
            seen.add(addr)
            unique_proxies.append(proxy)
    
    # Перемешиваем
    random.shuffle(unique_proxies)
    return unique_proxies

def _probe_enhanced(addr: str, proto: str, want_country: str = "", retries: int = 2) -> Tuple[bool, str, float]:
    """
    Улучшенная проверка прокси
    Возвращает (ok, real_country, ping_ms)
    """
    host, port = addr.split(":", 1)
    scheme = "http" if proto.upper() in ("HTTP", "HTTPS") else proto.lower()
    proxies = {"http": f"{scheme}://{addr}", "https": f"{scheme}://{addr}"}
    
    start_time = time.time()
    
    for attempt in range(retries):
        try:
            # Проверяем через ipify.org
            response = requests.get("https://api.ipify.org?format=json", 
                                 proxies=proxies, timeout=8, 
                                 headers={"User-Agent": "Mozilla/5.0"})
            
            if response.status_code == 200:
                data = response.json()
                ip = data.get("ip")
                if ip:
                    # Проверяем страну
                    country = ""
                    try:
                        geo_response = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode", 
                                                  timeout=5)
                        if geo_response.status_code == 200:
                            geo_data = geo_response.json()
                            country = (geo_data.get("countryCode") or "").upper()
                    except Exception:
                        pass
                    
                    # Если указана страна - проверяем соответствие
                    if want_country and country and country != want_country.upper():
                        return False, country, 0
                    
                    ping_ms = (time.time() - start_time) * 1000
                    return True, country, ping_ms
                    
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
            continue
    
    return False, "", 0

def pick(country: str = "", types: List[str] = None, need: int = 6, limit_test: int = 160) -> List[Tuple[str, str, str, float]]:
    """
    Основная функция выбора прокси
    Возвращает [(addr, proto, country, ping_ms)]
    """
    types = [t.upper() for t in (types or ["HTTP"])]
    country = country.upper()
    
    # Проверяем кеш
    cache_key = (country, tuple(types))
    now = datetime.now()
    
    if cache_key in _proxy_cache:
        cached_data, cache_time = _proxy_cache[cache_key]
        if now - cache_time < timedelta(seconds=_cache_ttl):
            return cached_data[:need]
    
    # Собираем кандидатов
    candidates = _gather_candidates(types, country)
    if not candidates:
        return []
    
    # Ограничиваем количество тестов
    candidates = candidates[:limit_test]
    
    # Параллельная проверка
    tested_proxies = []
    seen_ips = set()
    
    def _test_proxy(proxy_data):
        addr, proto, _ = proxy_data
        ok, real_country, ping = _probe_enhanced(addr, proto, country)
        if ok:
            ip = addr.split(":")[0]
            if ip not in seen_ips:
                seen_ips.add(ip)
                return (addr, proto, real_country, ping)
        return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
        results = list(executor.map(_test_proxy, candidates))
        tested_proxies = [r for r in results if r is not None]
    
    # Сортируем по пингу
    tested_proxies.sort(key=lambda x: x[3])
    
    # Кешируем результат
    _proxy_cache[cache_key] = (tested_proxies, now)
    
    return tested_proxies[:need]

def quick_probe(host: str, port: int, proto: str = "HTTP", timeout: int = 6) -> bool:
    """Быстрая проверка прокси"""
    try:
        scheme = "http" if proto.upper() in ("HTTP", "HTTPS") else proto.lower()
        proxies = {"http": f"{scheme}://{host}:{port}", "https": f"{scheme}://{host}:{port}"}
        response = requests.get("https://api.ipify.org?format=json", 
                             proxies=proxies, timeout=timeout, 
                             headers={"User-Agent": "Mozilla/5.0"})
        return response.ok and bool(response.json().get("ip"))
    except Exception:
        return False

# === Proxy Lab helpers ===
from typing import NamedTuple, Iterable
import time, concurrent.futures

class ProbeResult(NamedTuple):
    addr: str         # "host:port"
    proto: str        # "HTTP"/"SOCKS5"/"SOCKS4"
    ip: str|None
    cc: str|None
    ping_ms: int|None
    alive: bool
    err: str|None

def parse_lines_to_candidates(text: str, default_type="HTTP", default_cc="") -> list[tuple[str,str,str]]:
    """
    Поддерживаем форматы строк:
      - host:port
      - host:port,TYPE
      - host:port,TYPE,CC
      - TYPE,host,port,username,password,country  (игнорим user/pass здесь)
    Возврат: [(addr, PROTO, CC)]
    """
    out = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"): 
            continue
        parts = [p.strip() for p in s.split(",")]
        addr, proto, cc = None, None, None
        if ":" in parts[0] and (len(parts) <= 3):
            # host:port[,TYPE[,CC]]
            addr = parts[0]
            proto = (parts[1] if len(parts) > 1 and parts[1] else default_type).upper()
            cc    = (parts[2] if len(parts) > 2 else default_cc).upper()
        elif len(parts) >= 3:
            # TYPE,host,port,username,password,country?
            proto = (parts[0] or default_type).upper()
            addr  = f"{parts[1]}:{parts[2]}"
            cc    = (parts[5] if len(parts) > 5 else default_cc).upper()
        else:
            continue
        if proto == "HTTPS": proto = "HTTP"
        out.append((addr, proto, cc))
    # дедуп по адресу
    uniq, seen = [], set()
    for a,p,c in out:
        if a not in seen:
            uniq.append((a,p,c))
            seen.add(a)
    return uniq

def validate_candidates(cands: Iterable[tuple[str,str,str]], want_cc: str|None=None, timeout=5.0, max_workers=24) -> list[ProbeResult]:
    """
    Проверяем через ipify и cc через ip-api. Быстро и многопоточно.
    """
    want_cc = (want_cc or "").upper()
    def _one(item):
        addr, proto, cc_meta = item
        scheme = {"HTTP":"http","HTTPS":"http","SOCKS5":"socks5h","SOCKS4":"socks4a"}.get(proto.upper(),"http")
        proxies = {"http": f"{scheme}://{addr}", "https": f"{scheme}://{addr}"}
        t0 = time.perf_counter()
        try:
            r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=timeout)
            if r.status_code != 200:
                return ProbeResult(addr, proto, None, None, None, False, f"ipify {r.status_code}")
            ip = (r.json() or {}).get("ip")
            ping = int((time.perf_counter()-t0)*1000)
            cc = None
            try:
                g = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode,status", timeout=timeout)
                if g.ok and (g.json() or {}).get("status") == "success":
                    cc = (g.json().get("countryCode") or "").upper()
            except Exception:
                pass
            alive = True if ip else False
            if alive and want_cc and cc and cc != want_cc:
                return ProbeResult(addr, proto, ip, cc, ping, False, f"CC {cc}!= {want_cc}")
            return ProbeResult(addr, proto, ip, cc, ping, alive, None)
        except Exception as e:
            return ProbeResult(addr, proto, None, None, None, False, str(e))
    cands = list(cands)
    out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for res in ex.map(_one, cands):
            out.append(res)
    # живые первыми, сортировка по ping
    out.sort(key=lambda r: (not r.alive, r.ping_ms or 1_000_000))
    return out

def append_to_proxies_csv(items: Iterable[tuple[str,str,str]], path: pathlib.Path|None=None) -> int:
    """
    Добавляет новые адреса в proxies.csv с заголовком (если отсутствует).
    Формат: type,host,port,username,password,country
    """
    # выберем тот же путь, что _read_local_csv() нашёл
    path = path or next((p for p in _iter_csv_candidates() if p and p.exists() and p.is_file()), None) or (ROOT/"proxies.csv")
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = set()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or line.startswith("type,"): 
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts)>=3:
                        existing.add(f"{parts[1]}:{parts[2]}")  # host:port
        except Exception:
            pass
    new_rows, added = [], 0
    for addr, proto, cc in items:
        host, port = addr.split(":")
        key = f"{host}:{port}"
        if key in existing:
            continue
        new_rows.append(f"{proto},{host},{port},,,{cc}\n")
        existing.add(key); added += 1
    header = "type,host,port,username,password,country\n"
    mode = "a" if path.exists() else "w"
    with path.open(mode, encoding="utf-8", newline="") as f:
        if mode == "w": f.write(header)
        for row in new_rows: f.write(row)
    print(f"[proxy_pool] appended {added} rows into {path}")
    return added

# Экспорт для совместимости
__all__ = ["pick", "quick_probe", "ISO", "parse_lines_to_candidates", "validate_candidates", "append_to_proxies_csv", "ProbeResult"]