import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent / "cache" / "labels.json"


def _normalize_items(items: list) -> List[dict]:
    """Normalize items to v2 format: list of {name, count} dicts.

    Handles both v1 (list of strings) and v2 (list of dicts) transparently.
    """
    if not items:
        return []
    if isinstance(items[0], str):
        return [{"name": lbl, "count": None} for lbl in items]
    return items


def load_label_cache() -> List[str]:
    """Return cached label names as a flat list of strings, or [] if missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        items = _normalize_items(data.get("items", []))
        return [item["name"] for item in items]
    except Exception as exc:
        log.warning("Could not load label cache %s: %s", _CACHE_FILE, exc)
        return []


def load_label_cache_rich() -> List[dict]:
    """Return cached labels as list of {name, count} dicts, or [] if missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return _normalize_items(data.get("items", []))
    except Exception as exc:
        log.warning("Could not load label cache (rich) %s: %s", _CACHE_FILE, exc)
        return []


def load_label_cache_meta() -> dict:
    """Return full cache wrapper {updated_at, version, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        # Normalize items to v2 format in-memory
        data["items"] = _normalize_items(data.get("items", []))
        return data
    except Exception as exc:
        log.warning("Could not load label cache meta %s: %s", _CACHE_FILE, exc)
        return {"updated_at": None, "version": 2, "items": []}


def save_label_cache(labels: Union[List[str], List[dict]]) -> None:
    """Save labels to cache. Accepts both List[str] and List[dict] with {name, count}."""
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    items = _normalize_items(labels) if labels else []
    with open(_CACHE_FILE, "w") as f:
        json.dump(
            {"updated_at": datetime.now(timezone.utc).isoformat(), "version": 2, "items": items},
            f,
            indent=2,
        )
