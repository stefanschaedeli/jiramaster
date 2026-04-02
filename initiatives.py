import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent / "cache" / "initiatives.json"


def load_initiatives() -> List[Dict]:
    """Return cached initiative list [{key, summary, project_key}], or [] if file missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception as exc:
        log.warning("Could not load initiatives cache %s: %s", _CACHE_FILE, exc)
        return []


def load_initiatives_meta() -> dict:
    """Return full cache wrapper {updated_at, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception as exc:
        log.warning("Could not load initiatives cache meta %s: %s", _CACHE_FILE, exc)
        return {"updated_at": None, "items": []}


def save_initiatives(initiatives: List[Dict]) -> None:
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "items": initiatives}, f, indent=2)
