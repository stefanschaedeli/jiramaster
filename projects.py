import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent / "cache" / "projects.json"


def load_projects() -> List[Dict]:
    """Return cached project list [{key, name}], or [] if file missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception as exc:
        log.warning("Could not load projects cache %s: %s", _CACHE_FILE, exc)
        return []


def load_projects_meta() -> dict:
    """Return full cache wrapper {updated_at, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Could not load projects cache meta %s: %s", _CACHE_FILE, exc)
        return {"updated_at": None, "items": []}


def save_projects(projects: List[Dict]) -> None:
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "items": projects}, f, indent=2)
