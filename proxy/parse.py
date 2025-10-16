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