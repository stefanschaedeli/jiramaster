import pytest
from parser import (
    _strip_markdown_fences,
    _normalize_priority,
    _parse_story,
    _parse_epic,
    parse_copilot_output,
)
from models import Priority


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------

def test_strip_fences_yaml():
    text = "```yaml\nepics:\n  - title: A\n```"
    assert _strip_markdown_fences(text) == "epics:\n  - title: A"


def test_strip_fences_json():
    text = "```json\n{\"epics\": []}\n```"
    assert _strip_markdown_fences(text) == '{"epics": []}'


def test_strip_fences_bare():
    text = "```\nepics:\n  - title: A\n```"
    assert _strip_markdown_fences(text) == "epics:\n  - title: A"


def test_strip_fences_none():
    text = "epics:\n  - title: A"
    assert _strip_markdown_fences(text) == text


# ---------------------------------------------------------------------------
# _normalize_priority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("low", Priority.LOW),
    ("Low", Priority.LOW),
    ("HIGH", Priority.HIGH),
    ("High", Priority.HIGH),
    ("medium", Priority.MEDIUM),
    ("critical", Priority.CRITICAL),
    ("Critical", Priority.CRITICAL),
])
def test_normalize_priority_valid(value, expected):
    assert _normalize_priority(value) == expected


def test_normalize_priority_unknown_defaults_medium():
    assert _normalize_priority("urgent") == Priority.MEDIUM


def test_normalize_priority_empty_defaults_medium():
    assert _normalize_priority("") == Priority.MEDIUM


# ---------------------------------------------------------------------------
# _parse_story
# ---------------------------------------------------------------------------

def test_parse_story_full():
    raw = {
        "title": "My Story",
        "description": "Desc",
        "acceptance_criteria": "AC",
        "due_date": "2026-01-01",
        "priority": "High",
        "assignee": "alice",
        "comment": "note",
    }
    s = _parse_story(raw)
    assert s.title == "My Story"
    assert s.priority == Priority.HIGH
    assert s.assignee == "alice"
    assert s.comment == "note"


def test_parse_story_minimal():
    s = _parse_story({})
    assert s.title == "Untitled Story"
    assert s.description == ""
    assert s.priority == Priority.MEDIUM


def test_parse_story_none_fields_coerced():
    s = _parse_story({"title": "T", "due_date": None, "assignee": None, "comment": None})
    assert s.due_date == ""
    assert s.assignee == ""
    assert s.comment == ""


# ---------------------------------------------------------------------------
# _parse_epic
# ---------------------------------------------------------------------------

def test_parse_epic_with_stories():
    raw = {
        "title": "Epic A",
        "stories": [
            {"title": "S1"},
            {"title": "S2", "priority": "Low"},
        ],
    }
    e = _parse_epic(raw)
    assert e.title == "Epic A"
    assert len(e.stories) == 2
    assert e.stories[1].priority == Priority.LOW


def test_parse_epic_filters_non_dict_stories():
    raw = {
        "title": "Epic",
        "stories": ["not a dict", {"title": "Valid"}],
    }
    e = _parse_epic(raw)
    assert len(e.stories) == 1
    assert e.stories[0].title == "Valid"


# ---------------------------------------------------------------------------
# parse_copilot_output
# ---------------------------------------------------------------------------

SIMPLE_YAML = """
epics:
  - title: Epic One
    description: About it
    stories:
      - title: Story One
"""

SIMPLE_JSON = '{"epics": [{"title": "Epic One", "stories": [{"title": "Story One"}]}]}'


def test_parse_output_yaml():
    epics = parse_copilot_output(SIMPLE_YAML)
    assert len(epics) == 1
    assert epics[0].title == "Epic One"
    assert epics[0].stories[0].title == "Story One"


def test_parse_output_json():
    epics = parse_copilot_output(SIMPLE_JSON)
    assert len(epics) == 1
    assert epics[0].title == "Epic One"


def test_parse_output_with_fences():
    fenced = f"```yaml\n{SIMPLE_YAML.strip()}\n```"
    epics = parse_copilot_output(fenced)
    assert len(epics) == 1


def test_parse_output_invalid_raises():
    with pytest.raises(ValueError, match="Could not parse"):
        parse_copilot_output("this is not yaml or json ::::")


def test_parse_output_no_epics_key_raises():
    with pytest.raises(ValueError, match="epics"):
        parse_copilot_output("stories:\n  - title: X")


def test_parse_output_empty_epics_raises():
    with pytest.raises(ValueError, match="No epics"):
        parse_copilot_output("epics: []")
