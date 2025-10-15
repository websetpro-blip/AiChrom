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