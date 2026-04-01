"""Tests for GET /edit/labels live label search endpoint."""
import json
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_label_cache(cache_file, labels):
    cache_file.write_text(json.dumps({"updated_at": "2026-01-01T00:00:00+00:00", "items": labels}))


def _write_valid_config(tmp_path):
    """Write a fully-configured config.json into the test tmp_path."""
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
    return cfg_file


# ---------------------------------------------------------------------------
# Empty query returns empty list
# ---------------------------------------------------------------------------

def test_labels_search_empty_query(client):
    resp = client.get("/edit/labels?q=")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_labels_search_no_query_param(client):
    resp = client.get("/edit/labels")
    assert resp.status_code == 200
    assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Cache-only results (Jira not configured)
# ---------------------------------------------------------------------------

def test_labels_search_matches_cache(app, client, tmp_path, monkeypatch):
    cache_file = tmp_path / "cache" / "labels.json"
    _write_label_cache(cache_file, ["backend", "frontend", "urgent", "database"])

    resp = client.get("/edit/labels?q=end")
    assert resp.status_code == 200
    result = resp.get_json()
    assert "backend" in result
    assert "frontend" in result
    assert "urgent" not in result


def test_labels_search_case_insensitive(app, client, tmp_path, monkeypatch):
    cache_file = tmp_path / "cache" / "labels.json"
    _write_label_cache(cache_file, ["Backend", "FRONTEND", "urgent"])

    resp = client.get("/edit/labels?q=back")
    assert resp.status_code == 200
    result = resp.get_json()
    assert "Backend" in result


def test_labels_search_no_cache_match_returns_empty_when_unconfigured(client):
    # No cache written, Jira not configured → empty result
    resp = client.get("/edit/labels?q=xyz")
    assert resp.status_code == 200
    assert resp.get_json() == []


# ---------------------------------------------------------------------------
# Live Jira fallback when cache has few matches
# ---------------------------------------------------------------------------

def test_labels_search_live_fallback_when_cache_insufficient(app, client, tmp_path, monkeypatch):
    import config as config_module
    _write_valid_config(tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    cache_file = tmp_path / "cache" / "labels.json"
    _write_label_cache(cache_file, ["backend"])  # only 1 match < 10 threshold

    mock_client = MagicMock()
    mock_client.fetch_label_names.return_value = (
        ["backend", "backend-api", "backend-db", "backlog"], None
    )

    import routes.edit as edit_module
    edit_module._label_names_cache = {"timestamp": float("-inf"), "labels": []}

    with patch("routes.edit.JiraClient", return_value=mock_client):
        resp = client.get("/edit/labels?q=back")

    assert resp.status_code == 200
    result = resp.get_json()
    assert "backend" in result
    assert "backend-api" in result
    assert "backlog" in result


def test_labels_search_deduplicates_cache_and_live(app, client, tmp_path, monkeypatch):
    import config as config_module
    _write_valid_config(tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    cache_file = tmp_path / "cache" / "labels.json"
    _write_label_cache(cache_file, ["backend"])

    mock_client = MagicMock()
    # "backend" appears in both cache and live results — must not be duplicated
    mock_client.fetch_label_names.return_value = (["backend", "backend-api"], None)

    import routes.edit as edit_module
    edit_module._label_names_cache = {"timestamp": float("-inf"), "labels": []}

    with patch("routes.edit.JiraClient", return_value=mock_client):
        resp = client.get("/edit/labels?q=back")

    result = resp.get_json()
    assert result.count("backend") == 1


def test_labels_search_caps_at_20(app, client, tmp_path, monkeypatch):
    import config as config_module
    _write_valid_config(tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    cache_file = tmp_path / "cache" / "labels.json"
    # Put 5 in cache so live fallback fires
    _write_label_cache(cache_file, [f"label-{i}" for i in range(5)])

    mock_client = MagicMock()
    mock_client.fetch_label_names.return_value = ([f"label-{i}" for i in range(30)], None)

    import routes.edit as edit_module
    edit_module._label_names_cache = {"timestamp": float("-inf"), "labels": []}

    with patch("routes.edit.JiraClient", return_value=mock_client):
        resp = client.get("/edit/labels?q=label")

    result = resp.get_json()
    assert len(result) <= 20


def test_labels_search_live_error_returns_cache_results(app, client, tmp_path, monkeypatch):
    import config as config_module
    _write_valid_config(tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    cache_file = tmp_path / "cache" / "labels.json"
    _write_label_cache(cache_file, ["backend"])

    mock_client = MagicMock()
    mock_client.fetch_label_names.return_value = ([], "connection error")

    import routes.edit as edit_module
    edit_module._label_names_cache = {"timestamp": float("-inf"), "labels": []}

    with patch("routes.edit.JiraClient", return_value=mock_client):
        resp = client.get("/edit/labels?q=back")

    assert resp.status_code == 200
    result = resp.get_json()
    # Should still return the cache match
    assert "backend" in result


def test_labels_search_no_live_fallback_when_cache_has_10_plus(app, client, tmp_path, monkeypatch):
    import config as config_module
    _write_valid_config(tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    cache_file = tmp_path / "cache" / "labels.json"
    _write_label_cache(cache_file, [f"back-{i}" for i in range(10)])

    mock_client = MagicMock()

    import routes.edit as edit_module
    edit_module._label_names_cache = {"timestamp": float("-inf"), "labels": []}

    with patch("routes.edit.JiraClient", return_value=mock_client):
        resp = client.get("/edit/labels?q=back")

    # Cache already has >= 10 matches — live API should NOT be called
    mock_client.fetch_label_names.assert_not_called()
    assert resp.status_code == 200
