"""Helpers for applying Chrome DevTools Protocol overrides."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Dict, Optional

import requests
from websocket import create_connection

_DEFAULT_TIMEOUT = 5

__all__ = [
    "chrome_major",
    "ws_url_from_port",
    "apply_ua_lang",
    "apply_tz",
    "apply_geo",
]


def chrome_major(chrome_path: str) -> str:
    """Return Chrome major version (e.g. '127'), fallback to '120'."""
    try:
        output = subprocess.check_output(
            [chrome_path, "--version"], text=True, timeout=_DEFAULT_TIMEOUT
        ).strip()
    except Exception:
        return "120"
    match = re.search(r"(\d+)\.", output)
    return match.group(1) if match else "120"


def ws_url_from_port(port: int, timeout: float = _DEFAULT_TIMEOUT) -> str:
    """Resolve the WebSocket debugger URL for the given remote debugging port."""
    response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    ws_url = payload.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError(f"webSocketDebuggerUrl missing in payload: {payload!r}")
    return ws_url


def _send(ws_url: str, message: Dict[str, Any]) -> None:
    """Send a single CDP command and swallow the reply."""
    ws = create_connection(ws_url, timeout=_DEFAULT_TIMEOUT)
    try:
        ws.send(json.dumps(message))
        # Read the paired response to surface protocol errors eagerly.
        reply = json.loads(ws.recv())
        if "error" in reply:
            raise RuntimeError(f"CDP error: {reply['error']}")
    finally:
        ws.close()


def _extract_chrome_version(user_agent: str) -> Optional[str]:
    """Extract the Chrome version token (e.g. '127.0.6533.120') from UA string."""
    match = re.search(r"Chrome/([\d.]+)", user_agent)
    return match.group(1) if match else None


def _build_default_user_agent(major: str) -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.0.0 Safari/537.36"
    )


def _build_metadata(major: str, full_version: Optional[str]) -> Dict[str, Any]:
    full = full_version or f"{major}.0.0.0"
    return {
        "brands": [
            {"brand": "Chromium", "version": major},
            {"brand": "Google Chrome", "version": major},
            {"brand": "Not=A?Brand", "version": "99"},
        ],
        "fullVersionList": [
            {"brand": "Chromium", "version": full},
            {"brand": "Google Chrome", "version": full},
            {"brand": "Not=A?Brand", "version": "99.0.0.0"},
        ],
        "platform": "Windows",
        "platformVersion": "10.0.0",
        "architecture": "x86_64",
        "model": "",
        "mobile": False,
    }


def apply_ua_lang(
    ws_url: str,
    chrome_path: str,
    accept_language: Optional[str],
    *,
    user_agent: Optional[str] = None,
) -> None:
    """Apply UA + Accept-Language (with Client Hints) through CDP."""
    major = chrome_major(chrome_path)
    ua_string = user_agent or ""
    if "Chrome/" not in ua_string:
        ua_string = _build_default_user_agent(major)
        full_version = None
    else:
        full_version = _extract_chrome_version(ua_string)
        if not full_version:
            full_version = f"{major}.0.0.0"
    metadata = _build_metadata(major, full_version)

    message = {
        "id": 1,
        "method": "Emulation.setUserAgentOverride",
        "params": {
            "userAgent": ua_string,
            "acceptLanguage": (accept_language or "en-US,en;q=0.9"),
            "platform": metadata["platform"],
            "userAgentMetadata": metadata,
        },
    }
    _send(ws_url, message)


def apply_tz(ws_url: str, tz_id: str) -> None:
    """Apply timezone override through CDP."""
    message = {
        "id": 2,
        "method": "Emulation.setTimezoneOverride",
        "params": {"timezoneId": tz_id},
    }
    _send(ws_url, message)


def apply_geo(ws_url: str, latitude: float, longitude: float, accuracy: int = 50) -> None:
    """Apply geolocation override through CDP."""
    message = {
        "id": 3,
        "method": "Emulation.setGeolocationOverride",
        "params": {"latitude": latitude, "longitude": longitude, "accuracy": accuracy},
    }
    _send(ws_url, message)

