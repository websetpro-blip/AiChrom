from __future__ import annotations
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from tools.logging_setup import app_root, get_logger

log = get_logger()


def _which(names: list[str]) -> Optional[str]:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def guess_system_chrome() -> Optional[str]:
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for candidate in candidates:
            if Path(candidate).is_file():
                return candidate
        return _which(["chrome.exe", "google-chrome"])
    if system == "Darwin":
        candidate = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return candidate if Path(candidate).is_file() else _which(["google-chrome", "chrome"])
    return _which(["google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "chrome"])


def get_chrome_path(allow_system: bool = True) -> str:
    """
    Resolve Chrome binary with priority on production/system builds.
    Set env AICHROME_PREFER_SYSTEM=0 to prefer portable folder first.
    """
    prefer_system = os.getenv("AICHROME_PREFER_SYSTEM", "1") != "0"
    root = app_root()

    if allow_system and prefer_system:
        system_chrome = guess_system_chrome()
        if system_chrome:
            log.info("Using system Chrome: %s", system_chrome)
            return system_chrome

    portable_candidates: list[Path] = []
    if platform.system() == "Windows":
        portable_candidates.extend(
            [
                root / "tools" / "chrome" / "chrome-win" / "chrome.exe",
                root / "tools" / "chrome" / "chrome.exe",
            ]
        )
    else:
        portable_candidates.append(root / "tools" / "chrome" / "chrome")

    for candidate in portable_candidates:
        if candidate.is_file():
            log.info("Using portable Chrome: %s", candidate)
            return str(candidate)

    if allow_system and not prefer_system:
        system_chrome = guess_system_chrome()
        if system_chrome:
            log.info("Using system Chrome: %s", system_chrome)
            return system_chrome

    raise FileNotFoundError(
        "Chrome binary not found. Install Chrome or place a portable build into tools/chrome/."
    )
