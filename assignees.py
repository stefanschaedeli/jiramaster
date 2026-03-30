import json
import os
from typing import List, Dict

ASSIGNEES_FILE = os.path.join(os.path.dirname(__file__), "assignees.json")


def load_assignees() -> List[Dict]:
    """Return cached list, or [] if file missing/corrupt."""
    try:
        with open(ASSIGNEES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_assignees(users: List[Dict]) -> None:
    with open(ASSIGNEES_FILE, "w") as f:
        json.dump(users, f, indent=2)
