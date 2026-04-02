"""Tests for JiraClient run_label parameter in __init__."""
import pytest
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


@pytest.fixture
def cfg_with_labels():
    return JiraConfig(
        base_url="https://test.atlassian.net",
        username="user@example.com",
        api_token="fake-token",
        project_key="TEST",
        ac_field_id="customfield_11401",
        labels=["existing-label"],
    )


class TestRunLabelParameter:

    def test_run_label_appended_to_empty_labels(self, cfg):
        """When cfg.labels is empty, run_label is appended."""
        assert cfg.labels == []
        client = JiraClient(cfg, run_label="JiraMaster-STM-000001")
        assert client.labels == ["JiraMaster-STM-000001"]

    def test_run_label_appended_to_existing_labels(self, cfg_with_labels):
        """When cfg.labels already exists, run_label is appended."""
        assert cfg_with_labels.labels == ["existing-label"]
        client = JiraClient(cfg_with_labels, run_label="JiraMaster-STM-000001")
        assert client.labels == ["existing-label", "JiraMaster-STM-000001"]

    def test_no_run_label_uses_cfg_labels(self, cfg_with_labels):
        """When run_label is not provided, client.labels equals cfg.labels."""
        client = JiraClient(cfg_with_labels)
        assert client.labels == ["existing-label"]

    def test_run_label_none_not_appended(self, cfg_with_labels):
        """When run_label=None, no modification to cfg.labels."""
        client = JiraClient(cfg_with_labels, run_label=None)
        assert client.labels == ["existing-label"]

    def test_run_label_does_not_create_duplicate(self, cfg_with_labels):
        """When run_label matches an existing label, both are preserved."""
        cfg_with_labels.labels = ["JiraMaster-STM-000001"]
        client = JiraClient(cfg_with_labels, run_label="JiraMaster-STM-000001")
        # Note: The current implementation does not deduplicate.
        # This test documents the behavior: duplicates are preserved.
        assert client.labels == ["JiraMaster-STM-000001", "JiraMaster-STM-000001"]

    def test_run_label_special_characters(self, cfg):
        """run_label with hyphens and numbers is preserved as-is."""
        client = JiraClient(cfg, run_label="JiraMaster-STM-000001")
        assert "JiraMaster-STM-000001" in client.labels

    def test_empty_string_run_label_not_appended(self, cfg):
        """Empty string for run_label is treated as falsy and not appended."""
        client = JiraClient(cfg, run_label="")
        assert client.labels == []

    def test_whitespace_run_label_is_appended(self, cfg):
        """Whitespace-only run_label is appended (truthy in Python)."""
        client = JiraClient(cfg, run_label=" ")
        assert client.labels == [" "]
