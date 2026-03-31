import hashlib
import json
import logging
import time
from pathlib import Path

from flask import request, session

from models import Epic
from routes import is_valid_work_id

log = logging.getLogger(__name__)

WORK_DIR = Path(__file__).parent / ".work"


def _safe_work_path(work_id: str) -> Path:
    """Return the work file path after validating work_id format and path safety.

    Raises ValueError if work_id is invalid or resolves outside WORK_DIR.
    """
    if not is_valid_work_id(work_id):
        raise ValueError(f"Invalid work_id: {work_id!r}")
    path = (WORK_DIR / f"{work_id}.json").resolve()
    if not str(path).startswith(str(WORK_DIR.resolve())):
        raise ValueError("Path traversal detected")
    return path


def load_epics(work_id: str) -> list:
    """Load epics from the work file. Returns [] if the file does not exist."""
    path = _safe_work_path(work_id)
    if not path.exists():
        log.warning("Work file not found: %s", path.name)
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Epic.from_dict(d) for d in data]


def save_epics(work_id: str, epics: list) -> None:
    """Save epics to the work file."""
    path = _safe_work_path(work_id)
    data = [e.to_dict() for e in epics]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.debug("Saved %d epic(s) to %s", len(epics), path.name)


def _compute_fingerprint() -> str:
    """Return a short hash of browser-specific request headers.

    This is NOT authentication — it is a lightweight consistency check to detect
    session cookie reuse across different browsers or machines.
    """
    ua = request.headers.get("User-Agent", "")
    lang = request.headers.get("Accept-Language", "")
    raw = f"{ua}|{lang}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def set_session_work_id(work_id: str) -> None:
    """Store work_id and a browser fingerprint in the session."""
    session["work_id"] = work_id
    session["_fp"] = _compute_fingerprint()


def get_session_work_id():
    """Return the work_id from the session if valid and fingerprint matches.

    Returns None if work_id is missing, malformed, or the fingerprint does not
    match the current browser context.
    """
    work_id = session.get("work_id")
    if not work_id:
        return None
    if not is_valid_work_id(work_id):
        log.warning("Invalid work_id in session: %s", work_id)
        return None
    stored_fp = session.get("_fp")
    if stored_fp and stored_fp != _compute_fingerprint():
        log.warning("Session fingerprint mismatch for work_id %s", work_id)
        return None
    return work_id


def cleanup_stale_work_files(max_age_hours: int = 24) -> int:
    """Delete .work/*.json files older than max_age_hours. Returns count deleted."""
    cutoff = time.time() - (max_age_hours * 3600)
    count = 0
    for path in WORK_DIR.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                count += 1
        except OSError as exc:
            log.warning("Could not clean up work file %s: %s", path.name, exc)
    if count:
        log.info("Cleaned up %d stale work file(s) older than %dh", count, max_age_hours)
    return count
