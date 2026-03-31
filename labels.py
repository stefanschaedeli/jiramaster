import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent / "cache" / "labels.json"


def load_label_cache() -> List[str]:
    """Return cached label list, or [] if file missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception as exc:
        log.warning("Could not load label cache %s: %s", _CACHE_FILE, exc)
        return []


def load_label_cache_meta() -> dict:
    """Return full cache wrapper {updated_at, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Could not load label cache meta %s: %s", _CACHE_FILE, exc)
        return {"updated_at": None, "items": []}


def save_label_cache(labels: List[str]) -> None:
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "items": labels}, f, indent=2)
