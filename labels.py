import json
import os
from typing import List

LABELS_FILE = os.path.join(os.path.dirname(__file__), "labels.json")


def load_label_cache() -> List[str]:
    """Return cached label list, or [] if file missing/corrupt."""
    try:
        with open(LABELS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_label_cache(labels: List[str]) -> None:
    with open(LABELS_FILE, "w") as f:
        json.dump(labels, f, indent=2)
