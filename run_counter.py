import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_COUNTER_FILE = Path(__file__).parent / "cache" / "run_counter.json"


def load_counter() -> int:
    """
    Load counter from cache/run_counter.json.

    Returns current counter value, or 0 if file is absent or malformed.
    """
    try:
        with open(_COUNTER_FILE) as f:
            data = json.load(f)
        value = data.get("counter", 0)
        if isinstance(value, int) and value >= 0:
            return value
        log.warning("Counter value is not a valid non-negative int: %s", value)
        return 0
    except FileNotFoundError:
        log.debug("Counter file not found, returning 0")
        return 0
    except Exception as exc:
        log.warning("Could not load counter from %s: %s", _COUNTER_FILE, exc)
        return 0


def increment_and_save() -> int:
    """
    Increment counter by 1, save to cache/run_counter.json, and return new value.

    If file is absent or malformed, starts from 0.
    Creates cache/ directory if it doesn't exist.
    """
    current = load_counter()
    new_value = current + 1

    try:
        _COUNTER_FILE.parent.mkdir(exist_ok=True)
        with open(_COUNTER_FILE, "w") as f:
            json.dump({"counter": new_value}, f, indent=2)
        log.debug("Counter incremented from %d to %d", current, new_value)
        return new_value
    except Exception:
        log.exception("Could not save counter to %s", _COUNTER_FILE)
        raise


def build_run_label(username: str) -> str:
    """
    Build a run label from a Jira username and current counter value.

    Format: JiraMaster-BBB-XXXXXX
    - BBB: initials derived from email local part (before @)
      - Split on '.', take first 2 chars of first segment + first char of second
      - If only one segment, take first 3 chars
      - Strip non-alpha, uppercase
    - XXXXXX: zero-padded 6-digit counter value

    Args:
        username: Jira username (email address, e.g. "stefan.mueller@company.com")

    Returns:
        Label string like "JiraMaster-STM-000042"
    """
    # Get current counter
    counter = increment_and_save()

    # Extract initials from email
    local_part = username.split("@")[0] if "@" in username else username
    segments = local_part.split(".")

    if len(segments) >= 2:
        # Multiple segments: first 2 chars of first segment + first char of second
        initials = (segments[0][:2] + segments[1][:1]).upper()
    else:
        # Single segment: first 3 chars
        initials = segments[0][:3].upper()

    # Strip non-alpha characters
    initials = "".join(c for c in initials if c.isalpha())

    # Pad to 3 chars if needed (shouldn't happen with the above logic, but be safe)
    if len(initials) < 3:
        initials = initials.ljust(3, "X")
    else:
        initials = initials[:3]

    # Format counter as 6-digit zero-padded string
    counter_str = str(counter).zfill(6)

    label = f"JiraMaster-{initials}-{counter_str}"
    log.debug("Built label '%s' from username '%s' with counter %d", label, username, counter)
    return label
