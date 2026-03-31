from __future__ import annotations

import json
import logging
from typing import List, Optional, Tuple

import certifi
import requests
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)


def _resolve_ca_bundle():
    """Determine the CA bundle for SSL verification.

    Priority: REQUESTS_CA_BUNDLE env var > SSL_CERT_FILE env var > certifi default.
    Both start.sh (macOS) and start.ps1 (Windows) export these env vars after
    merging system/corporate CA certificates into the certifi bundle.
    """
    import os
    for var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        path = os.environ.get(var)
        if path and os.path.isfile(path):
            log.info("Using CA bundle from %s: %s", var, path)
            return path
    default = certifi.where()
    log.info("Using default certifi CA bundle: %s", default)
    return default


_CA_BUNDLE = _resolve_ca_bundle()

from models import Epic, Story, JiraConfig, UploadResult
from assignees import load_assignees


def _resolve_assignee(name: str) -> Optional[str]:
    """Match displayName or emailAddress (case-insensitive) → accountId."""
    if not name:
        return None
    name_lower = name.lower()
    for u in load_assignees():
        if name_lower in (u.get("displayName", "").lower(), u.get("emailAddress", "").lower()):
            return u["accountId"]
    return None


def _adf(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format v3."""
    if not text:
        return {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": " "}],
                }
            ],
        }
    paragraphs = []
    for line in text.splitlines():
        paragraphs.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line or " "}],
            }
        )
    return {"version": 1, "type": "doc", "content": paragraphs}


class JiraClient:
    def __init__(self, cfg: JiraConfig):
        self.base_url = cfg.base_url.rstrip("/")
        self.project_key = cfg.project_key
        self.ac_field_id = cfg.ac_field_id or ""
        self.api_base = f"{self.base_url}/rest/api/3"

        self.labels: List[str] = cfg.labels or []

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(cfg.username, cfg.api_token)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        self.session.verify = _CA_BUNDLE
        if cfg.proxy_url:
            self.session.proxies = {"http": cfg.proxy_url, "https": cfg.proxy_url}

    def _url(self, path: str) -> str:
        return f"{self.api_base}/{path.lstrip('/')}"

    def _log_error(self, label: str, resp: requests.Response) -> str:
        """Log full response details to terminal and return a UI-safe summary."""
        try:
            body = resp.json()
            pretty = json.dumps(body, indent=2)
        except Exception:
            body = {}
            pretty = resp.text
        log.error("%s — HTTP %s\n%s", label, resp.status_code, pretty)
        # Extract Jira's human-readable error messages
        messages = body.get("errorMessages", [])
        errors = body.get("errors", {})
        parts = list(messages) + [f"{k}: {v}" for k, v in errors.items()]
        detail = "; ".join(parts) if parts else resp.text[:300] or "no detail"
        return f"HTTP {resp.status_code} — {detail}"

    def detect_ac_field(self) -> Tuple[Optional[str], Optional[str]]:
        """Find the Acceptance Criteria custom field ID via GET /rest/api/3/field.

        Returns (field_id, field_name) on success, or (None, error_message) on failure.
        """
        try:
            resp = self.session.get(self._url("field"), timeout=10)
            if resp.status_code != 200:
                return None, self._log_error("detect_ac_field", resp)
            fields = resp.json()
            log.info("All Jira fields:")
            for f in fields:
                log.info("  %s = %s", f["id"], f.get("name", ""))
            for f in fields:
                if "acceptance" in f.get("name", "").lower():
                    log.info("Detected AC field: %s = %s", f["id"], f["name"])
                    return f["id"], f["name"]
            return None, "No field containing 'acceptance' found. Check terminal logs for full field list."
        except requests.RequestException as exc:
            log.error("detect_ac_field exception: %s", exc)
            return None, str(exc)

    def fetch_assignees(self, max_results: int = 20, project_key: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
        """Fetch top assignable users for the project.

        Args:
            max_results: Maximum number of users to return.
            project_key: Override the configured project key. Falls back to self.project_key.

        Returns (users, error_message). users is [] on failure.
        """
        effective_project = project_key or self.project_key
        try:
            resp = self.session.get(
                self._url("user/assignable/search"),
                params={"project": effective_project, "maxResults": max_results},
                timeout=10,
            )
            if resp.status_code != 200:
                return [], self._log_error("fetch_assignees", resp)
            users = [
                {
                    "accountId": u["accountId"],
                    "displayName": u.get("displayName", ""),
                    "emailAddress": u.get("emailAddress", ""),
                }
                for u in resp.json()
                if not u.get("accountType", "").startswith("app")
            ]
            return users[:max_results], None
        except requests.RequestException as exc:
            log.error("fetch_assignees exception: %s", exc)
            return [], str(exc)

    def fetch_projects(self) -> Tuple[List[dict], Optional[str]]:
        """Fetch all accessible projects via GET /rest/api/3/project/search (paginated).

        Returns (projects, error_message). projects is a list of {key, name} dicts.
        """
        try:
            projects: List[dict] = []
            start_at = 0
            while True:
                resp = self.session.get(
                    self._url("project/search"),
                    params={"startAt": start_at, "maxResults": 50},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return [], self._log_error("fetch_projects", resp)
                data = resp.json()
                page = data.get("values", [])
                for p in page:
                    projects.append({"key": p["key"], "name": p.get("name", p["key"])})
                if not page or len(projects) >= data.get("total", 0):
                    break
                start_at += len(page)
            log.info("fetch_projects: %d projects found", len(projects))
            return projects, None
        except requests.RequestException as exc:
            log.error("fetch_projects exception: %s", exc)
            return [], str(exc)

    def fetch_labels(self, top_n: int = 40) -> Tuple[List[str], Optional[str]]:
        """Return the top_n most-used labels from the Jira instance.

        Fetches all known labels via GET /rest/api/3/label (paginated), then
        for each label queries how many issues use it and ranks by frequency.
        Returns (label_list, error_message). label_list is [] on failure.
        """
        from collections import Counter
        try:
            # Step 1: collect all label names
            all_labels: List[str] = []
            start_at = 0
            while True:
                resp = self.session.get(
                    self._url("label"),
                    params={"startAt": start_at, "maxResults": 200},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return [], self._log_error("fetch_labels", resp)
                data = resp.json()
                page = data.get("values", [])
                all_labels.extend(page)
                if not page or len(all_labels) >= data.get("total", 0):
                    break
                start_at += len(page)

            log.info("fetch_labels: %d total labels found, sampling frequency", len(all_labels))

            # Step 2: count usage per label via issue/search
            counts: Counter = Counter()
            for lbl in all_labels:
                resp = self.session.get(
                    self._url("issue/search"),
                    params={
                        "jql": f"labels = \"{lbl}\"",
                        "fields": "summary",
                        "maxResults": 1,
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    counts[lbl] = resp.json().get("total", 0)
                    log.debug("fetch_labels: %r → %d issues", lbl, counts[lbl])
                else:
                    counts[lbl] = 0

            labels = [lbl for lbl, _ in counts.most_common(top_n)]
            log.info("fetch_labels: returning top %d by usage", len(labels))
            return labels, None
        except requests.RequestException as exc:
            log.error("fetch_labels exception: %s", exc)
            return [], str(exc)

    def test_connection(self) -> Tuple[bool, str]:
        try:
            resp = self.session.get(self._url("myself"), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                display = data.get("displayName", data.get("emailAddress", "Unknown"))
                log.info("Connection OK — %s", display)
                return True, f"Connected as {display}"
            return False, self._log_error("test_connection", resp)
        except requests.RequestException as exc:
            log.error("test_connection exception: %s", exc)
            return False, str(exc)

    def _set_ac_field(self, fields: dict, ac: str) -> None:
        """Inject the AC value into a fields dict using the configured field ID.

        Tries plain text first (most AC custom fields are string type).
        If ac_field_id is not configured, logs a warning but does not raise.
        """
        if not self.ac_field_id:
            log.warning(
                "ac_field_id not configured — AC will not be sent as a field. "
                "Go to Settings and click 'Detect Fields'."
            )
            return
        if not ac:
            return
        fields[self.ac_field_id] = ac  # plain text (string field type)

    def _post_issue(self, payload: dict, label: str) -> Tuple[Optional[str], Optional[str]]:
        """POST to /issue. On 400 caused by AC field type mismatch, retry with ADF."""
        log.debug("%s payload: %s", label, json.dumps(payload, indent=2))
        try:
            resp = self.session.post(self._url("issue"), json=payload, timeout=15)
            if resp.status_code in (200, 201):
                return resp.json().get("key"), None

            # If it failed and we sent AC as plain text, retry with ADF in case
            # this instance uses a rich-text AC field.
            if resp.status_code == 400 and self.ac_field_id in payload.get("fields", {}):
                ac_val = payload["fields"][self.ac_field_id]
                if isinstance(ac_val, str):
                    log.info("%s: plain-text AC rejected, retrying with ADF", label)
                    payload["fields"][self.ac_field_id] = _adf(ac_val)
                    resp2 = self.session.post(self._url("issue"), json=payload, timeout=15)
                    if resp2.status_code in (200, 201):
                        return resp2.json().get("key"), None
                    return None, self._log_error(label, resp2)

            return None, self._log_error(label, resp)
        except requests.RequestException as exc:
            log.error("%s exception: %s", label, exc)
            return None, str(exc)

    def create_epic(self, epic: Epic) -> Tuple[Optional[str], Optional[str]]:
        """Returns (jira_key, error_message)."""
        fields: dict = {
            "project": {"key": epic.project_key or self.project_key},
            "issuetype": {"name": "Epic"},
            "summary": epic.title,
            "description": _adf(epic.description),
            "priority": {"name": epic.priority or "Medium"},
        }
        if epic.due_date:
            fields["duedate"] = epic.due_date
        if epic.initiative_id:
            fields["parent"] = {"key": epic.initiative_id}
        combined_labels = list(dict.fromkeys(self.labels + epic.labels))
        if combined_labels:
            fields["labels"] = combined_labels
        assignee_id = _resolve_assignee(epic.assignee)
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}
        self._set_ac_field(fields, epic.acceptance_criteria)
        return self._post_issue({"fields": fields}, f"create_epic({epic.title!r})")

    def create_story(self, story: Story, epic_key: str, project_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Returns (jira_key, error_message)."""
        fields: dict = {
            "project": {"key": project_key or self.project_key},
            "issuetype": {"name": "Story"},
            "summary": story.title,
            "description": _adf(story.description),
            "priority": {"name": story.priority or "Medium"},
            "parent": {"key": epic_key},
        }
        if story.due_date:
            fields["duedate"] = story.due_date
        combined_labels = list(dict.fromkeys(self.labels + story.labels))
        if combined_labels:
            fields["labels"] = combined_labels
        assignee_id = _resolve_assignee(story.assignee)
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}
        self._set_ac_field(fields, story.acceptance_criteria)
        return self._post_issue({"fields": fields}, f"create_story({story.title!r})")

    def transition_issue(self, issue_key: str, target_status: str) -> None:
        """Transition an issue to the named status by matching available transitions.

        Fetches available transitions for the issue and performs the first one whose
        name matches target_status (case-insensitive). Logs a warning if not found.
        """
        if not target_status:
            return
        try:
            resp = self.session.get(
                self._url(f"issue/{issue_key}/transitions"),
                timeout=10,
            )
            if resp.status_code != 200:
                log.warning("transition_issue(%s): could not fetch transitions — %s", issue_key, resp.status_code)
                return
            transitions = resp.json().get("transitions", [])
            target_lower = target_status.lower()
            match = next(
                (t for t in transitions if t.get("name", "").lower() == target_lower),
                None,
            )
            if not match:
                available = [t.get("name") for t in transitions]
                log.warning(
                    "transition_issue(%s): status %r not found; available: %s",
                    issue_key, target_status, available,
                )
                return
            self.session.post(
                self._url(f"issue/{issue_key}/transitions"),
                json={"transition": {"id": match["id"]}},
                timeout=10,
            )
            log.info("transition_issue(%s): → %r (id=%s)", issue_key, target_status, match["id"])
        except requests.RequestException as exc:
            log.error("transition_issue(%s) exception: %s", issue_key, exc)

    def add_comment(self, issue_key: str, text: str) -> None:
        if not text:
            return
        payload = {"body": _adf(text)}
        try:
            self.session.post(self._url(f"issue/{issue_key}/comment"), json=payload, timeout=10)
        except requests.RequestException:
            pass

    def add_acceptance_criteria_comment(self, issue_key: str, ac: str) -> None:
        if not ac:
            return
        self.add_comment(issue_key, f"Acceptance Criteria:\n{ac}")


    def upload_epics(self, epics: List[Epic]) -> List[UploadResult]:
        log.info("upload_epics: ac_field_id=%r", self.ac_field_id or "(not set — AC will not be sent as a field)")
        results: List[UploadResult] = []
        for epic in epics:
            if not epic.include:
                continue
            key, err = self.create_epic(epic)
            if key:
                epic.jira_key = key
                url = f"{self.base_url}/browse/{key}"
                results.append(
                    UploadResult(
                        title=epic.title,
                        issue_type="Epic",
                        success=True,
                        jira_key=key,
                        jira_url=url,
                    )
                )
                # Transition epic to chosen status
                self.transition_issue(key, epic.status)
                # Post acceptance criteria as comment
                self.add_acceptance_criteria_comment(key, epic.acceptance_criteria)
                # Post additional comment
                if epic.comment:
                    self.add_comment(key, epic.comment)
                # Create child stories
                for story in epic.stories:
                    if not story.include:
                        continue
                    s_key, s_err = self.create_story(story, key, epic.project_key)
                    if s_key:
                        story.jira_key = s_key
                        s_url = f"{self.base_url}/browse/{s_key}"
                        results.append(
                            UploadResult(
                                title=story.title,
                                issue_type="Story",
                                success=True,
                                jira_key=s_key,
                                jira_url=s_url,
                            )
                        )
                        # Transition story to chosen status
                        self.transition_issue(s_key, story.status)
                        self.add_acceptance_criteria_comment(s_key, story.acceptance_criteria)
                        if story.comment:
                            self.add_comment(s_key, story.comment)
                    else:
                        results.append(
                            UploadResult(
                                title=story.title,
                                issue_type="Story",
                                success=False,
                                error_message=s_err,
                            )
                        )
            else:
                results.append(
                    UploadResult(
                        title=epic.title,
                        issue_type="Epic",
                        success=False,
                        error_message=err,
                    )
                )
        return results
