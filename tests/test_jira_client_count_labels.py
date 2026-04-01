"""Regression tests for JiraClient.count_label_usage POST/GET fallback logic."""
import pytest
from unittest.mock import MagicMock, call, patch
from models import JiraConfig
from jira_client import JiraClient


@pytest.fixture
def cfg():
    return JiraConfig(
        base_url="https://test.atlassian.net",
        username="user@example.com",
        api_token="fake-token",
        project_key="TEST",
        ac_field_id="customfield_11401",
    )


def _make_response(status_code, json_body):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    return resp


class TestCountLabelUsagePostFallback:
    """count_label_usage should try POST, fall back to GET on 405."""

    def test_post_succeeds(self, cfg):
        """Happy path: POST returns 200 for all labels."""
        client = JiraClient(cfg)
        ok = _make_response(200, {"total": 3})
        with patch.object(client, "_request", return_value=ok) as mock_req:
            results, err = client.count_label_usage(["alpha", "beta"])

        assert err is None
        assert results == [{"name": "alpha", "count": 3}, {"name": "beta", "count": 3}]
        # Both calls must be POST
        for c in mock_req.call_args_list:
            assert c.args[0] == "POST"

    def test_get_fallback_on_405(self, cfg):
        """When first POST returns 405, remaining labels must use GET."""
        client = JiraClient(cfg)
        resp_405 = _make_response(405, {})
        resp_ok = _make_response(200, {"total": 7})

        call_count = {"n": 0}

        def side_effect(method, url, **kwargs):
            call_count["n"] += 1
            if method == "POST":
                return resp_405
            return resp_ok

        with patch.object(client, "_request", side_effect=side_effect) as mock_req:
            results, err = client.count_label_usage(["first", "second", "third"])

        assert err is None
        methods = [c.args[0] for c in mock_req.call_args_list]
        # First call is POST (which returns 405), rest must be GET
        assert methods[0] == "POST"
        assert all(m == "GET" for m in methods[1:])
        # After 405, GET is issued immediately for "first" (same iteration), so all get 7
        assert results == [
            {"name": "first", "count": 7},
            {"name": "second", "count": 7},
            {"name": "third", "count": 7},
        ]

    def test_special_char_labels_use_post(self, cfg):
        """Labels with hyphens/underscores must still go through POST first."""
        client = JiraClient(cfg)
        ok = _make_response(200, {"total": 5})
        with patch.object(client, "_request", return_value=ok) as mock_req:
            results, err = client.count_label_usage(["CIS-Infra_Eng_SAN"])

        assert err is None
        assert results == [{"name": "CIS-Infra_Eng_SAN", "count": 5}]
        assert mock_req.call_args_list[0].args[0] == "POST"

    def test_non_405_error_counts_as_zero(self, cfg):
        """Non-200/non-405 responses (e.g. 400) count as 0 but don't switch to GET."""
        client = JiraClient(cfg)
        resp_400 = _make_response(400, {})
        with patch.object(client, "_request", return_value=resp_400) as mock_req:
            results, err = client.count_label_usage(["foo", "bar"])

        assert err is None
        assert all(r["count"] == 0 for r in results)
        # Should remain POST throughout
        assert all(c.args[0] == "POST" for c in mock_req.call_args_list)
