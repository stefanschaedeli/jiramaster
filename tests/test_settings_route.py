import pytest
from unittest.mock import patch, MagicMock
from models import JiraConfig


VALID_FORM = {
    "base_url": "https://test.atlassian.net",
    "username": "user@example.com",
    "api_token": "fake-token-12345",
    "project_key": "TEST",
    "ac_field_id": "customfield_11401",
    "proxy_url": "",
    "org_id": "",
}


def _post_save(client, data=None):
    form = {**VALID_FORM, **(data or {})}
    return client.post("/settings/save", data=form, follow_redirects=False)


# ---------------------------------------------------------------------------
# Page load
# ---------------------------------------------------------------------------

def test_settings_page_loads(client):
    resp = client.get("/settings/")
    assert resp.status_code == 200
    assert b"Jira Configuration" in resp.data


# ---------------------------------------------------------------------------
# Valid save
# ---------------------------------------------------------------------------

def test_save_valid_settings(client, tmp_path, monkeypatch):
    import config as config_module
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config_module, "_KEYRING_AVAILABLE", False)

    resp = _post_save(client)
    # Should redirect to settings index on success
    assert resp.status_code == 302
    assert "/settings/" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# URL validation — preserves form data on error
# ---------------------------------------------------------------------------

def test_save_rejects_http_url(client):
    resp = _post_save(client, {"base_url": "http://test.atlassian.net"})
    # Must NOT redirect (302 loses form data) — must re-render (200)
    assert resp.status_code == 200
    assert b"https://" in resp.data


def test_save_rejects_http_url_preserves_other_fields(client):
    resp = _post_save(client, {"base_url": "http://test.atlassian.net"})
    # Username entered by user should still appear in the returned form
    assert b"user@example.com" in resp.data


# ---------------------------------------------------------------------------
# Field validation errors — form data preserved
# ---------------------------------------------------------------------------

def test_save_rejects_invalid_project_key(client):
    resp = _post_save(client, {"project_key": "abc"})
    assert resp.status_code == 200
    assert b"Project key" in resp.data


def test_save_rejects_invalid_email(client):
    resp = _post_save(client, {"username": "notanemail"})
    assert resp.status_code == 200
    assert b"email" in resp.data.lower()


def test_save_rejects_invalid_ac_field(client):
    resp = _post_save(client, {"ac_field_id": "badfield"})
    assert resp.status_code == 200
    assert b"customfield_" in resp.data


def test_save_preserves_form_data_on_validation_error(client):
    # Multiple invalid fields — all entered data must be preserved in the response
    resp = _post_save(client, {
        "base_url": "http://bad.example.com",
        "username": "user@example.com",
        "project_key": "VALID",
    })
    assert resp.status_code == 200
    # The URL we entered (even bad) should be reflected back in the form
    assert b"http://bad.example.com" in resp.data


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

def test_security_headers_on_settings_page(client):
    resp = client.get("/settings/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "SAMEORIGIN" in resp.headers.get("X-Frame-Options", "")
    assert "Content-Security-Policy" in resp.headers
