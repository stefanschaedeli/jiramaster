import json
import pytest
import config as config_module
from config import load_config, save_config, load_prompt_template, save_prompt_template
from models import JiraConfig


def _make_cfg(**kwargs):
    defaults = {
        "base_url": "https://x.atlassian.net",
        "username": "u@x.com",
        "api_token": "tok",
        "project_key": "PROJ",
        "ac_field_id": "customfield_11401",
        "proxy_url": "",
        "org_id": "",
        "labels": [],
        "verbose_logging": False,
    }
    defaults.update(kwargs)
    return JiraConfig(**defaults)


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def test_load_config_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", False)
    cfg = load_config()
    assert cfg.base_url == ""
    assert cfg.project_key == ""


def test_load_config_valid(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "base_url": "https://test.atlassian.net",
        "username": "u@x.com",
        "api_token": "tok",
        "project_key": "TEST",
        "ac_field_id": "customfield_99",
        "proxy_url": "",
        "org_id": "",
        "labels": [],
        "verbose_logging": False,
    }))
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", False)
    cfg = load_config()
    assert cfg.base_url == "https://test.atlassian.net"
    assert cfg.project_key == "TEST"
    assert cfg.ac_field_id == "customfield_99"


def test_load_config_corrupt_json(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("not valid json {{{{")
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", False)
    cfg = load_config()
    assert cfg.base_url == ""


def test_load_config_keyring_overlay(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "base_url": "https://x.atlassian.net",
        "username": "",
        "api_token": "",
        "project_key": "P",
        "ac_field_id": "customfield_11401",
    }))
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", True)

    import types
    fake_keyring = types.SimpleNamespace(
        get_password=lambda service, key: ("keyring@email.com" if key == "username" else "keyring-token"),
        set_password=lambda *a: None,
        errors=types.SimpleNamespace(KeyringError=Exception),
    )
    monkeypatch.setattr(config_module, "keyring", fake_keyring)

    cfg = load_config()
    assert cfg.username == "keyring@email.com"
    assert cfg.api_token == "keyring-token"


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------

def test_save_config_no_keyring(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", False)
    cfg = _make_cfg(api_token="my-secret-token", username="u@x.com")
    save_config(cfg)
    data = json.loads(cfg_file.read_text())
    assert data["api_token"] == "my-secret-token"
    assert data["username"] == "u@x.com"
    assert data["base_url"] == "https://x.atlassian.net"


def test_save_config_with_keyring(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", True)

    stored = {}
    import types
    fake_keyring = types.SimpleNamespace(
        set_password=lambda service, key, val: stored.update({key: val}),
        get_password=lambda *a: None,
    )
    monkeypatch.setattr(config_module, "keyring", fake_keyring)

    cfg = _make_cfg(api_token="my-secret-token", username="u@x.com")
    save_config(cfg)

    data = json.loads(cfg_file.read_text())
    assert data["api_token"] == ""
    assert data["username"] == ""
    assert stored["api_token"] == "my-secret-token"
    assert stored["username"] == "u@x.com"


def test_save_config_keyring_failure_fallback(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", True)

    import types
    fake_keyring = types.SimpleNamespace(
        set_password=lambda *a: (_ for _ in ()).throw(Exception("keyring broken")),
        get_password=lambda *a: None,
    )
    monkeypatch.setattr(config_module, "keyring", fake_keyring)

    cfg = _make_cfg(api_token="fallback-token")
    save_config(cfg)
    data = json.loads(cfg_file.read_text())
    assert data["api_token"] == "fallback-token"


# ---------------------------------------------------------------------------
# prompt template
# ---------------------------------------------------------------------------

def test_load_prompt_template_creates_default(tmp_path, monkeypatch):
    template_file = tmp_path / "prompt_template.txt"
    monkeypatch.setattr(config_module, "PROMPT_TEMPLATE_FILE", template_file)
    content = load_prompt_template()
    assert "{{MEETING_NOTES}}" in content
    assert template_file.exists()


def test_load_prompt_template_existing(tmp_path, monkeypatch):
    template_file = tmp_path / "prompt_template.txt"
    template_file.write_text("Custom template {{MEETING_NOTES}}")
    monkeypatch.setattr(config_module, "PROMPT_TEMPLATE_FILE", template_file)
    assert load_prompt_template() == "Custom template {{MEETING_NOTES}}"


def test_save_prompt_template(tmp_path, monkeypatch):
    template_file = tmp_path / "prompt_template.txt"
    monkeypatch.setattr(config_module, "PROMPT_TEMPLATE_FILE", template_file)
    save_prompt_template("New template content")
    assert template_file.read_text() == "New template content"
