import pytest
import config as config_module
from prompt_builder import build_tuning_instructions, build_prompt, SAMPLE_INSTRUCTION


SIMPLE_TEMPLATE = "{{TUNING_INSTRUCTIONS}}\n\nNotes:\n{{MEETING_NOTES}}"


# ---------------------------------------------------------------------------
# build_tuning_instructions (pure)
# ---------------------------------------------------------------------------

def test_tuning_defaults():
    result = build_tuning_instructions({})
    assert "2 and 6 Stories" in result
    assert "RULES:" in result
    # Default aggressiveness is 2
    assert "significant actions" in result


def test_tuning_aggressiveness_1():
    result = build_tuning_instructions({"aggressiveness": 1})
    assert "ONLY explicit decisions" in result


def test_tuning_aggressiveness_3():
    result = build_tuning_instructions({"aggressiveness": 3})
    assert "ALL action items" in result


def test_tuning_invalid_aggressiveness_defaults_to_2():
    result = build_tuning_instructions({"aggressiveness": 99})
    assert "significant actions" in result


def test_tuning_subtasks():
    result = build_tuning_instructions({"include_subtasks": True})
    assert "subtasks" in result.lower()


def test_tuning_no_subtasks():
    result = build_tuning_instructions({"include_subtasks": False})
    assert "subtasks" not in result.lower()


@pytest.mark.parametrize("level,expected", [
    ("Brief", "one-sentence description"),
    ("Standard", "all fields"),
    ("Detailed", "thorough descriptions"),
])
def test_tuning_detail_levels(level, expected):
    result = build_tuning_instructions({"detail_level": level})
    assert expected in result


def test_tuning_story_range():
    result = build_tuning_instructions({"stories_min": 3, "stories_max": 8})
    assert "3 and 8 Stories" in result


# ---------------------------------------------------------------------------
# build_prompt (needs template mock)
# ---------------------------------------------------------------------------

def test_build_prompt_with_notes(monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_FILE", "/nonexistent")
    # Provide template via monkeypatching load_prompt_template
    import prompt_builder
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: SIMPLE_TEMPLATE)

    result = build_prompt("My meeting notes here", {})
    assert "My meeting notes here" in result


def test_build_prompt_empty_notes(monkeypatch):
    import prompt_builder
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: SIMPLE_TEMPLATE)

    result = build_prompt("", {})
    assert SAMPLE_INSTRUCTION in result


def test_build_prompt_whitespace_notes_treated_as_empty(monkeypatch):
    import prompt_builder
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: SIMPLE_TEMPLATE)

    result = build_prompt("   ", {})
    assert SAMPLE_INSTRUCTION in result


def test_build_prompt_no_tuning_placeholder(monkeypatch):
    import prompt_builder
    template_without_tuning = "Static intro\n\n{{MEETING_NOTES}}"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template_without_tuning)

    result = build_prompt("Notes here", {})
    # Tuning block should be prepended
    assert "RULES:" in result
    assert "Notes here" in result


def test_build_prompt_no_notes_placeholder(monkeypatch):
    import prompt_builder
    template_without_notes = "{{TUNING_INSTRUCTIONS}}\n\nFixed template"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template_without_notes)

    result = build_prompt("My notes", {})
    # Notes appended at end
    assert "My notes" in result
