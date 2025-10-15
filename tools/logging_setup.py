from __future__ import annotations
import logging, os, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def app_root() -> Path:
    # корректно для dev и для PyInstaller
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def ensure_dirs():
    for p in ["logs", "cache", "profiles"]:
        (app_root() / p).mkdir(parents=True, exist_ok=True)

def get_logger(name: str = "aichrome") -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_file = app_root() / "logs" / "launcher.log"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s")
    fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger