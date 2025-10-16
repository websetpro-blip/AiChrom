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

def validate_proxy(p: Proxy, timeout: float = 5.0) -> ValidationResult:
    t0 = time.perf_counter()
    try:
        # Сначала пробуем простую проверку
        r = requests.get("https://httpbin.org/ip", proxies=_proxies_dict(p), timeout=timeout)
        r.raise_for_status()
        data = r.json()
        ip = data.get("origin", "").split(',')[0].strip()
        
        if not ip:
            # Fallback на ipify
            r2 = requests.get("https://api.ipify.org?format=json", proxies=_proxies_dict(p), timeout=timeout)
            r2.raise_for_status()
            ip = r2.json().get("ip")
        
        ping = int((time.perf_counter() - t0) * 1000)
        
        # Получаем страну
        country = None
        cc = None
        try:
            rr = requests.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,message", timeout=3)
            if rr.ok:
                jj = rr.json()
                if jj.get("status") == "success":
                    country = jj.get("country")
                    cc = jj.get("countryCode")
        except:
            pass  # Страна не критична
        
        return ValidationResult(True, ip=ip, country=country, cc=cc, ping_ms=ping)
        
    except Exception as e:
        return ValidationResult(False, error=str(e)[:200])