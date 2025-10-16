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
from typing import Optional
import logging

log = logging.getLogger(__name__)

# Proxy configuration (ready-to-use)
PROXY_HOST = "213.139.222.220"
PROXY_PORT = "9869"
PROXY_USER = "nDRYz5"
PROXY_PASS = "EP0wPC"
PROXY_PROTOCOL = "https"

def launch_chrome_with_profile(
    profile_id: str,
    user_agent: Optional[str] = None,
    language: str = "en-US",
    timezone: str = "America/New_York",
    screen_width: int = 1920,
    screen_height: int = 1080,
    extra_flags: Optional[list] = None,
    use_proxy: bool = True,
    headless: bool = False
) -> int:
    """
    Launch Chrome with unique profile and HTTPS proxy.
    
    Args:
        profile_id: Unique profile identifier for full isolation
        user_agent: Custom user-agent (if None, Chrome default is used)
        language: Browser language
        timezone: Timezone for the profile
        screen_width: Screen width
        screen_height: Screen height
        extra_flags: Additional Chrome flags
        use_proxy: Enable HTTPS proxy (default: True)
        headless: Run in headless mode
    
    Returns:
        Process PID
    """
    
    # Unique user-data-dir per profile (strict isolation)
    user_data_dir = Path.home() / ".aichrome_profiles" / f"profile_{profile_id}"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    args = [
        "google-chrome",  # or "chromium-browser" depending on system
        f"--user-data-dir={user_data_dir}",
        f"--window-size={screen_width},{screen_height}",
        f"--lang={language}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-blink-features=AutomationControlled",
    ]
    
    # HTTPS Proxy with authentication
    if use_proxy:
        proxy_url = f"{PROXY_PROTOCOL}://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        args.append(f"--proxy-server={proxy_url}")
        log.info(f"Profile {profile_id}: Using proxy {PROXY_PROTOCOL}://{PROXY_HOST}:{PROXY_PORT}")
    
    # Custom user-agent
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    
    # Timezone (via environment variable for Chromium)
    env = os.environ.copy()
    env["TZ"] = timezone
    
    # Headless mode
    if headless:
        args.extend(["--headless", "--disable-gpu"])
    
    # Optional: force software rendering to reduce GPU usage
    if os.getenv("AICHROME_SOFTGPU", "0") == "1":
        args.extend([
            "--disable-gpu",
            "--disable-gpu-compositing",
            "--use-gl=swiftshader",
            "--disable-accelerated-2d-canvas",
        ])
    
    # Additional flags
    if extra_flags:
        args.extend(extra_flags)
    
    # Self-test: verify proxy IP and geolocation before launching
    def _proxy_self_test() -> bool:
        if not use_proxy:
            return True
        try:
            # Test via proxy
            proxy_dict = {
                "http": f"{PROXY_PROTOCOL}://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
                "https": f"{PROXY_PROTOCOL}://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
            }
            resp = requests.get("https://api.ipify.org?format=json", proxies=proxy_dict, timeout=6)
            ip = resp.json().get("ip")
            if not ip:
                log.warning("Self-test: ipify returned no ip")
                return False
            geo = requests.get(
                f"http://ip-api.com/json/{ip}?fields=status,country,query",
                proxies=proxy_dict,
                timeout=6
            ).json()
            if geo.get("status") != "success":
                log.warning("Self-test: ip-api failed for %s", ip)
                return False
            log.info("Proxy self-test OK: ip=%s country=%s", geo.get("query"), geo.get("country"))
            return True
        except Exception as e:
            log.exception("Proxy self-test error: %s", e)
            return False
    
    # Run self-test
    if use_proxy:
        ok = _proxy_self_test()
        if not ok:
            log.warning("Proxy self-test failed — launching anyway but verify proxy manually")
    
    log.info(f"Launching Chrome for profile {profile_id}:\n  %s", "\n  ".join(args))
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    
    def _watch() -> None:
        try:
            proc.wait()
        finally:
            log.info(f"Chrome process for profile {profile_id} terminated")
    
    threading.Thread(target=_watch, daemon=True).start()
    return proc.pid


if __name__ == "__main__":
    # Example usage: launch with default proxy configuration
    logging.basicConfig(level=logging.INFO)
    
    pid = launch_chrome_with_profile(
        profile_id="test_profile_001",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        language="en-US",
        timezone="America/New_York",
        use_proxy=True,
        headless=False
    )
    
    log.info(f"Chrome launched with PID: {pid}")
    log.info("Profile is fully isolated with unique cookies, storage, and proxy configuration")
