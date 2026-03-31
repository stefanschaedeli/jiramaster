"""Centralised logging setup for JiraMaster.

Call ``setup_logging()`` once at startup (in app.py) before any other imports
that use ``logging.getLogger()``.  All modules then simply do:

    import logging
    log = logging.getLogger(__name__)

Logs go to both the console **and** ``logs/jiramaster.log`` (auto-rotated at
5 MB, keeping the last 3 files).
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_INITIALISED = False

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "jiramaster.log"


def setup_logging() -> None:
    global _INITIALISED
    if _INITIALISED:
        return
    _INITIALISED = True

    LOG_DIR.mkdir(exist_ok=True)

    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    level = logging.DEBUG if debug else logging.INFO

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — rotates at 5 MB, keeps 3 backups
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)  # always capture full detail in the file
    fh.setFormatter(fmt)

    # Console handler — respects the FLASK_DEBUG level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(ch)

    # Quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "Logging initialised — level=%s, file=%s", logging.getLevelName(level), LOG_FILE,
    )
