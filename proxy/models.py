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