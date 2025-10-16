"""worker_chrome.py
Universal HTTPS proxy profile implementation with proper authentication support.

Proxy Configuration:
- Server: 213.139.222.220:9869
- Username: nDRYz5
- Password: EP0wPC
- Protocol: HTTPS

Proxy Authentication Fix:
- Chrome doesn't support user:pass@ in --proxy-server (causes ERR_NO_SUPPORTED_PROXIES)
- For HTTP/HTTPS with authentication: auto-generates MV3 extension for proxy auth
- For SOCKS or no-auth proxies: uses direct --proxy-server flag
- Automatic proxy type detection (HTTP/HTTPS/SOCKS)
- All applied automatically per profile

Profile Features:
- Unique user-data-dir per profile
- Isolated cookies and storage per profile
- Custom user-agent, language, timezone per profile
- MV3 proxy auth extension (temporary, auto-cleanup)
- Self-test included for proxy verification

Usage:
  Simply clone from GitHub and run - everything applies automatically per profile.
"""

from __future__ import annotations

import subprocess
import shutil
import threading
import os
import json
import tempfile
import requests
from pathlib import Path
from typing import Optional, List, Callable
import logging

log = logging.getLogger(__name__)

# Proxy configuration (ready-to-use)
PROXY_HOST = "213.139.222.220"
PROXY_PORT = 9869
PROXY_USER = "nDRYz5"
PROXY_PASS = "EP0wPC"
PROXY_TYPE = "https"  # Auto-detect: http, https, socks4, socks5


def create_proxy_auth_extension(proxy_host: str, proxy_port: int, 
                                 proxy_user: str, proxy_pass: str) -> Path:
    """
    Create a temporary MV3 extension for proxy authentication.
    This is how anti-detect browsers handle authenticated proxies.
    
    Returns: Path to the extension directory
    """
    ext_dir = Path(tempfile.mkdtemp(prefix="chrome_proxy_auth_"))
    
    # manifest.json (Manifest V3)
    manifest = {
        "manifest_version": 3,
        "name": "Proxy Auth",
        "version": "1.0.0",
        "permissions": ["proxy", "webRequest", "webRequestAuthProvider"],
        "host_permissions": ["<all_urls>"],
        "background": {
            "service_worker": "background.js"
        }
    }
    
    # background.js - handles proxy authentication
    background_js = f"""
chrome.webRequest.onAuthRequired.addListener(
  function(details, callbackFn) {{
    console.log('Proxy auth required for:', details.url);
    callbackFn({{
      authCredentials: {{
        username: '{proxy_user}',
        password: '{proxy_pass}'
      }}
    }});
  }},
  {{urls: ["<all_urls>"]}},
  ['asyncBlocking']
);

console.log('Proxy auth extension loaded');
"""
    
    # Write files
    (ext_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (ext_dir / "background.js").write_text(background_js)
    
    log.info(f"Created proxy auth extension at: {ext_dir}")
    return ext_dir


def detect_proxy_type(proxy_string: str) -> tuple[str, str, int, Optional[str], Optional[str]]:
    """
    Detect proxy type and parse credentials.
    
    Supported formats:
    - http://host:port
    - https://host:port
    - http://user:pass@host:port
    - https://user:pass@host:port
    - socks4://host:port
    - socks5://host:port
    - socks5://user:pass@host:port
    - host:port (defaults to http)
    
    Returns: (proxy_type, host, port, username, password)
    """
    import re
    
    # Parse proxy URL
    pattern = r'^(?:(\w+)://)?(?:([^:@]+):([^@]+)@)?([^:]+):(\d+)$'
    match = re.match(pattern, proxy_string)
    
    if not match:
        raise ValueError(f"Invalid proxy format: {proxy_string}")
    
    proto, user, passwd, host, port = match.groups()
    proto = proto or "http"  # Default to http
    
    return (proto.lower(), host, int(port), user, passwd)


def detect_worker_chrome() -> Optional[Path]:
    """
    Detect Chrome/Chromium executable.
    Returns Path or None.
    """
    if os.name == 'nt':
        candidates = [
            Path(os.environ.get('PROGRAMFILES', 'C:\\Program Files')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
        ]
    else:
        candidates = [
            Path('/usr/bin/google-chrome'),
            Path('/usr/bin/chromium-browser'),
            Path('/usr/bin/chromium'),
            Path('/snap/bin/chromium'),
        ]
    
    for c in candidates:
        if c.exists():
            return c
    return None


def launch_chrome_with_profile(
    profile_name: str = "default",
    user_agent: Optional[str] = None,
    language: str = "en-US",
    timezone: str = "America/New_York",
    extra_args: Optional[List[str]] = None,
    proxy_string: Optional[str] = None,
) -> subprocess.Popen:
    """
    Launch Chrome with profile and proxy settings.
    
    Args:
        profile_name: Unique profile identifier
        user_agent: Custom user agent
        language: Browser language
        timezone: System timezone
        extra_args: Additional Chrome arguments
        proxy_string: Proxy in format "[protocol://][user:pass@]host:port"
                      If None, uses default PROXY_* constants
    
    Returns:
        subprocess.Popen object
    """
    chrome_exe = detect_worker_chrome()
    if not chrome_exe:
        raise FileNotFoundError("Chrome/Chromium not found")
    
    # Profile directory
    profile_dir = Path.home() / ".aichrom_profiles" / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    # Base Chrome arguments
    args = [
        str(chrome_exe),
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--lang={language}",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-translate",
    ]
    
    # Handle proxy configuration
    if proxy_string is None:
        # Use default configuration
        proxy_string = f"{PROXY_TYPE}://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    
    # Parse proxy
    try:
        proto, host, port, user, passwd = detect_proxy_type(proxy_string)
        
        log.info(f"Detected proxy type: {proto}, auth: {bool(user and passwd)}")
        
        # Handle proxy based on type and authentication
        if (proto in ['http', 'https']) and user and passwd:
            # HTTP/HTTPS with authentication: use MV3 extension
            log.info("Using MV3 extension for proxy authentication")
            ext_dir = create_proxy_auth_extension(host, port, user, passwd)
            args.append(f"--load-extension={ext_dir}")
            # For extension method, use simple proxy-server without credentials
            args.append(f"--proxy-server={proto}://{host}:{port}")
        elif proto.startswith('socks'):
            # SOCKS proxy: direct flag (Chrome supports socks without extension)
            log.info(f"Using direct {proto} proxy configuration")
            if user and passwd:
                # Note: SOCKS with auth may require extension too in newer Chrome versions
                log.warning("SOCKS with authentication may not work in all Chrome versions")
            args.append(f"--proxy-server={proto}://{host}:{port}")
        else:
            # HTTP/HTTPS without authentication: direct flag
            log.info("Using direct proxy configuration (no authentication)")
            args.append(f"--proxy-server={proto}://{host}:{port}")
    
    except Exception as e:
        log.error(f"Failed to configure proxy: {e}")
        raise
    
    # User agent
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    
    # Timezone override (via environment or arg)
    env = os.environ.copy()
    env['TZ'] = timezone
    
    if extra_args:
        args.extend(extra_args)
    
    log.info(f"Launching Chrome with profile '{profile_name}' via proxy {host}:{port}")
    
    proc = subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    return proc


def self_test_proxy():
    """
    Test proxy connectivity using requests library.
    """
    proxy_url = f"https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    proxies = {
        'http': proxy_url,
        'https': proxy_url,
    }
    
    try:
        log.info("Testing proxy connection...")
        resp = requests.get('https://api.ipify.org?format=json', proxies=proxies, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log.info(f"Proxy OK. External IP: {data.get('ip')}")
            return True
        else:
            log.error(f"Proxy test failed with status {resp.status_code}")
            return False
    except Exception as e:
        log.error(f"Proxy test exception: {e}")
        return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Run self-test
    if self_test_proxy():
        log.info("Proxy test passed. Launching Chrome...")
        proc = launch_chrome_with_profile(profile_name="test_profile")
        log.info(f"Chrome launched with PID {proc.pid}")
        log.info("Chrome will continue running. Close manually when done.")
        log.info("Check your IP in browser: https://api.ipify.org or https://whatismyipaddress.com")
    else:
        log.error("Proxy test failed. Please check proxy configuration.")
