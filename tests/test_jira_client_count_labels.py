"""Regression tests for JiraClient.count_label_usage."""
import pytest
from unittest.mock import MagicMock, patch
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


class TestCountLabelUsage:

    def test_returns_counts(self, cfg):
        """Happy path: GET /rest/api/3/search returns total for each label."""
        client = JiraClient(cfg)
        ok = _make_response(200, {"total": 3})
        with patch.object(client, "_request", return_value=ok) as mock_req:
            results, err = client.count_label_usage(["alpha", "beta"])

        assert err is None
        assert results == [{"name": "alpha", "count": 3}, {"name": "beta", "count": 3}]
        for c in mock_req.call_args_list:
            assert c.args[0] == "GET"
            assert c.args[1].endswith("/search/jql")

    def test_uses_search_endpoint(self, cfg):
        """Must call /rest/api/3/search, not /rest/api/3/issue/search."""
        client = JiraClient(cfg)
        ok = _make_response(200, {"total": 0})
        with patch.object(client, "_request", return_value=ok) as mock_req:
            client.count_label_usage(["foo"])

        url = mock_req.call_args_list[0].args[1]
        assert url.endswith("/search/jql")
        assert "issue/search" not in url

    def test_special_char_labels(self, cfg):
        """Labels with hyphens/underscores must work via GET query params."""
        client = JiraClient(cfg)
        ok = _make_response(200, {"total": 5})
        with patch.object(client, "_request", return_value=ok) as mock_req:
            results, err = client.count_label_usage(["CIS-Infra_Eng_SAN"])

        assert err is None
        assert results == [{"name": "CIS-Infra_Eng_SAN", "count": 5}]
        call = mock_req.call_args_list[0]
        assert call.args[0] == "GET"
        assert '"CIS-Infra_Eng_SAN"' in call.kwargs["params"]["jql"]

    def test_non_200_counts_as_zero(self, cfg):
        """Non-200 responses count as 0 but don't abort the batch."""
        client = JiraClient(cfg)
        resp_404 = _make_response(404, {})
        with patch.object(client, "_request", return_value=resp_404):
            results, err = client.count_label_usage(["foo", "bar"])

        assert err is None
        assert all(r["count"] == 0 for r in results)

    def test_maxresults_zero(self, cfg):
        """maxResults=0 must be passed so Jira skips returning issue bodies."""
        client = JiraClient(cfg)
        ok = _make_response(200, {"total": 1})
        with patch.object(client, "_request", return_value=ok) as mock_req:
            client.count_label_usage(["x"])

        params = mock_req.call_args_list[0].kwargs["params"]
        assert params["maxResults"] == 0
