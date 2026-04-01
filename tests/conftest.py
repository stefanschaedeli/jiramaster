import json
import pytest
from models import JiraConfig


@pytest.fixture
def mock_config():
    """A fully-populated JiraConfig with fake but valid data."""
    return JiraConfig(
        base_url="https://test.atlassian.net",
        username="user@example.com",
        api_token="fake-token-12345",
        project_key="TEST",
        ac_field_id="customfield_11401",
    )


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app with CSRF disabled, TESTING=True, all file paths in tmp_path."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Redirect all module-level Path constants before any route calls use them
    monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr("config.PROMPT_TEMPLATE_FILE", data_dir / "prompt_template.txt")
    monkeypatch.setattr("config._KEYRING_AVAILABLE", False)
    monkeypatch.setattr("work_store.WORK_DIR", work_dir)
    monkeypatch.setattr("assignees._CACHE_FILE", cache_dir / "assignees.json")
    monkeypatch.setattr("labels._CACHE_FILE", cache_dir / "labels.json")
    monkeypatch.setattr("projects._CACHE_FILE", cache_dir / "projects.json")

    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SERVER_NAME"] = "localhost"
    yield flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def configured_config_file(tmp_path, monkeypatch):
    """Write a valid config.json to tmp_path and monkeypatch CONFIG_FILE to it."""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "base_url": "https://test.atlassian.net",
        "username": "user@example.com",
        "api_token": "secret-token",
        "project_key": "TEST",
        "ac_field_id": "customfield_11401",
        "proxy_url": "",
        "org_id": "",
        "labels": [],
        "verbose_logging": False,
    }))
    monkeypatch.setattr("config.CONFIG_FILE", cfg_file)
    monkeypatch.setattr("config._KEYRING_AVAILABLE", False)
    return cfg_file
