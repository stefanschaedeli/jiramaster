import json
import re
from typing import List

import yaml

from models import Epic, Story, Priority


def _normalize_priority(value: str) -> str:
    if not value:
        return Priority.MEDIUM
    mapping = {
        "low": Priority.LOW,
        "medium": Priority.MEDIUM,
        "high": Priority.HIGH,
        "critical": Priority.CRITICAL,
    }
    return mapping.get(str(value).lower(), Priority.MEDIUM)


def _parse_story(raw: dict) -> Story:
    return Story(
        title=str(raw.get("title", "Untitled Story")),
        description=str(raw.get("description", "")),
        acceptance_criteria=str(raw.get("acceptance_criteria", "")),
        due_date=str(raw.get("due_date", "") or ""),
        priority=_normalize_priority(raw.get("priority", "")),
        assignee=str(raw.get("assignee", "") or ""),
        comment=str(raw.get("comment", "") or ""),
    )


def _parse_epic(raw: dict) -> Epic:
    stories = [_parse_story(s) for s in raw.get("stories", []) if isinstance(s, dict)]
    return Epic(
        title=str(raw.get("title", "Untitled Epic")),
        description=str(raw.get("description", "")),
        acceptance_criteria=str(raw.get("acceptance_criteria", "")),
        due_date=str(raw.get("due_date", "") or ""),
        priority=_normalize_priority(raw.get("priority", "")),
        assignee=str(raw.get("assignee", "") or ""),
        comment=str(raw.get("comment", "") or ""),
        stories=stories,
    )


def _strip_markdown_fences(text: str) -> str:
    """Remove ```yaml ... ``` or ```json ... ``` wrappers if present."""
    text = text.strip()
    pattern = r"^```(?:yaml|json)?\s*\n(.*?)\n```\s*$"
    match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def parse_copilot_output(text: str) -> List[Epic]:
    """Parse YAML or JSON Copilot output into a list of Epic objects."""
    text = _strip_markdown_fences(text)

    data = None

    # Try YAML first (handles both YAML and JSON since JSON is valid YAML)
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        pass

    # Fallback: try JSON explicitly
    if data is None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse input as YAML or JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Parsed data must be a YAML/JSON object with an 'epics' key.")

    epics_raw = data.get("epics", [])
    if not isinstance(epics_raw, list):
        raise ValueError("'epics' must be a list.")

    if not epics_raw:
        raise ValueError("No epics found in parsed data.")

    return [_parse_epic(e) for e in epics_raw if isinstance(e, dict)]
