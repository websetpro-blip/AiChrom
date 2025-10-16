"""worker_chrome.py
Universal HTTPS proxy profile implementation (ready-to-use out of the box).

Proxy Configuration:
- Server: 213.139.222.220:9869
- Username: nDRYz5
- Password: EP0wPC
- Protocol: HTTPS

Profile Features:
- Unique user-data-dir per profile
- Isolated cookies and storage per profile
- Custom user-agent, language, timezone per profile
- Direct proxy authentication via --proxy-server=https://user:pass@host:port
- No extensions required (maximum simplicity)
- All other params (screen, fingerprint) remain as configured
- Self-test included for proxy verification

Usage:
  Simply clone from GitHub and run - everything applies automatically per profile.
"""
from __future__ import annotations
import subprocess
import shutil
import threading
import os
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
    
    for p in candidates:
        if p.exists():
            log.info(f"Detected Chrome at: {p}")
            return p
    
    log.warning("Chrome executable not found")
    return None

def ensure_worker_chrome(auto: bool = True, ask: Optional[Callable[[str], bool]] = None) -> Path:
    """
    Ensure Chrome is available, raise if not found.
    
    Args:
        auto: If True, automatically use detected Chrome (default)
        ask: Optional callback function to prompt user for confirmation
    
    Returns:
        Path: Chrome executable path
    """
    chrome = detect_worker_chrome()
    if not chrome:
        raise FileNotFoundError(
            "Chrome not found. Please install Chrome or Chromium."
        )
    
    # If ask callback is provided and auto is False, ask user
    if ask is not None and not auto:
        if not ask(f"Use Chrome at {chrome}?"):
            raise FileNotFoundError(
                "User declined to use detected Chrome."
            )
    
    return chrome

def launch_chrome(
    profile_id: str,
    user_agent: Optional[str],
    lang: str,
    tz: Optional[str],
    proxy: Optional[object],
    extra_flags: Optional[List[str]] = None,
    allow_system_chrome: bool = True,
    force_pac: bool = False,
) -> int:
    """
    Launch Chrome with HTTPS proxy and profile isolation.
    
    Args:
        profile_id: Profile identifier
        user_agent: Custom user agent string
        lang: Accept-Language header (e.g., "en-US")
        tz: Timezone override (e.g., "America/New_York")
        proxy: Proxy object (from database/config) - for future use
        extra_flags: Additional Chrome arguments
        allow_system_chrome: Whether to allow system Chrome installation
        force_pac: Legacy parameter (ignored, kept for compatibility)
    
    Returns:
        int: Chrome process PID
    """
    chrome_exe = ensure_worker_chrome()
    
    # Auto-generate user_data_dir based on profile_id
    base_dir = Path.cwd() / 'chrome_profiles'
    base_dir.mkdir(exist_ok=True)
    user_data_dir = base_dir / profile_id
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Construct proxy URL with authentication
    proxy_url = f"https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    
    args = [
        str(chrome_exe),
        f"--user-data-dir={user_data_dir}",
        f"--proxy-server={proxy_url}",
        f"--lang={lang}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
    ]
    
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    
    # Timezone override (via environment or arg)
    env = os.environ.copy()
    if tz:
        env['TZ'] = tz
    
    if extra_flags:
        args.extend(extra_flags)
    
    log.info(f"Launching Chrome with profile '{profile_id}' via proxy {PROXY_HOST}:{PROXY_PORT}")
    
    proc = subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    log.info(f"Chrome launched with PID {proc.pid}")
    return proc.pid

def launch_chrome_with_profile(
    profile_name: str = "default",
    user_data_dir: Optional[Path] = None,
    user_agent: Optional[str] = None,
    language: str = "en-US",
    timezone: str = "America/New_York",
    screen_width: int = 1920,
    screen_height: int = 1080,
    extra_args: Optional[list] = None,
) -> subprocess.Popen:
    """
    Backward compatibility function for direct script usage.
    Launches Chrome with simplified parameters and returns process object.
    """
    chrome_exe = ensure_worker_chrome()
    
    # Auto-generate user_data_dir if not provided
    if user_data_dir is None:
        base_dir = Path.cwd() / 'chrome_profiles'
        base_dir.mkdir(exist_ok=True)
        user_data_dir = base_dir / profile_name
    
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Construct proxy URL with authentication
    proxy_url = f"https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    
    args = [
        str(chrome_exe),
        f"--user-data-dir={user_data_dir}",
        f"--proxy-server={proxy_url}",
        f"--window-size={screen_width},{screen_height}",
        f"--lang={language}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
    ]
    
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    
    # Timezone override (via environment or arg)
    env = os.environ.copy()
    env['TZ'] = timezone
    
    if extra_args:
        args.extend(extra_args)
    
    log.info(f"Launching Chrome with profile '{profile_name}' via proxy {PROXY_HOST}:{PROXY_PORT}")
    
    proc = subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    return proc

def self_test_proxy():
    """
    Test proxy connectivity.
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
    else:
        log.error("Proxy test failed. Please check proxy configuration.")
