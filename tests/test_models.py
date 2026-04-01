import pytest
from models import Story, Epic, JiraConfig, UploadResult, Priority


# ---------------------------------------------------------------------------
# Story
# ---------------------------------------------------------------------------

def test_story_roundtrip():
    s = Story(
        title="Do the thing",
        description="Desc",
        acceptance_criteria="AC",
        due_date="2026-01-01",
        priority=Priority.HIGH,
        assignee="alice",
        status="Open",
        labels=["backend"],
        comment="note",
        jira_key="TEST-1",
        include=False,
    )
    assert Story.from_dict(s.to_dict()) == s


def test_story_defaults():
    s = Story.from_dict({})
    assert s.title == ""
    assert s.priority == Priority.MEDIUM
    assert s.include is True
    assert s.labels == []
    assert s.jira_key is None


def test_story_from_dict_minimal():
    s = Story.from_dict({"title": "Only title"})
    assert s.title == "Only title"
    assert s.description == ""
    assert s.assignee == ""


# ---------------------------------------------------------------------------
# Epic
# ---------------------------------------------------------------------------

def test_epic_roundtrip():
    e = Epic(
        title="Big Epic",
        description="Desc",
        acceptance_criteria="AC",
        due_date="2026-06-01",
        priority=Priority.CRITICAL,
        assignee="bob",
        comment="c",
        stories=[Story(title="Story A"), Story(title="Story B")],
        include=True,
        initiative_id="INI-1",
        project_key="PROJ",
        jira_key="PROJ-10",
    )
    assert Epic.from_dict(e.to_dict()) == e


def test_epic_defaults():
    e = Epic.from_dict({})
    assert e.title == ""
    assert e.stories == []
    assert e.include is True
    assert e.initiative_id is None


def test_epic_with_stories():
    data = {
        "title": "Epic",
        "stories": [
            {"title": "S1", "priority": "High"},
            {"title": "S2"},
        ],
    }
    e = Epic.from_dict(data)
    assert len(e.stories) == 2
    assert e.stories[0].title == "S1"
    assert e.stories[0].priority == Priority.HIGH
    assert e.stories[1].title == "S2"


# ---------------------------------------------------------------------------
# JiraConfig
# ---------------------------------------------------------------------------

def test_jiraconfig_roundtrip():
    cfg = JiraConfig(
        base_url="https://example.atlassian.net",
        username="u@x.com",
        api_token="tok",
        project_key="PROJ",
        ac_field_id="customfield_99",
        proxy_url="http://proxy:8080",
        org_id="abc-123",
        labels=["a", "b"],
        verbose_logging=True,
    )
    assert JiraConfig.from_dict(cfg.to_dict()) == cfg


def test_jiraconfig_labels_as_string():
    cfg = JiraConfig.from_dict({"labels": "foo, bar, baz"})
    assert cfg.labels == ["foo", "bar", "baz"]


def test_jiraconfig_labels_as_list():
    cfg = JiraConfig.from_dict({"labels": ["x", "y"]})
    assert cfg.labels == ["x", "y"]


def test_jiraconfig_strips_trailing_slash():
    cfg = JiraConfig.from_dict({"base_url": "https://x.atlassian.net/"})
    assert cfg.base_url == "https://x.atlassian.net"


def test_jiraconfig_is_configured_true():
    cfg = JiraConfig(
        base_url="https://x.atlassian.net",
        username="u@x.com",
        api_token="tok",
        project_key="PROJ",
    )
    assert cfg.is_configured() is True


@pytest.mark.parametrize("field", ["base_url", "username", "api_token", "project_key"])
def test_jiraconfig_is_configured_false_when_field_missing(field):
    kwargs = {
        "base_url": "https://x.atlassian.net",
        "username": "u@x.com",
        "api_token": "tok",
        "project_key": "PROJ",
    }
    kwargs[field] = ""
    assert JiraConfig(**kwargs).is_configured() is False


# ---------------------------------------------------------------------------
# UploadResult
# ---------------------------------------------------------------------------

def test_upload_result_construction():
    r = UploadResult(title="Epic", issue_type="Epic", success=True, jira_key="TEST-1")
    assert r.success is True
    assert r.error_message is None
