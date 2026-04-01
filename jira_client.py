from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple

import certifi
import requests
from requests.auth import HTTPBasicAuth

from security_utils import sanitize_request, sanitize_response

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


class OperationAbortedError(Exception):
    """Raised by JiraClient._request() when the operation's abort flag is set."""


class JiraClient:
    def __init__(self, cfg: JiraConfig, verbose: bool = False,
                 event_callback: Optional[Callable[[dict], None]] = None,
                 abort_check: Optional[Callable[[], bool]] = None):
        self.base_url = cfg.base_url.rstrip("/")
        self.project_key = cfg.project_key
        self.ac_field_id = cfg.ac_field_id or ""
        self.api_base = f"{self.base_url}/rest/api/3"
        self._org_id: str = cfg.org_id
        self._teams_base = f"https://api.atlassian.com/gateway/api/public/teams/v1/org/{self._org_id}"
        self._verbose = verbose
        self._event_callback = event_callback
        self._abort_check = abort_check

        self.labels: List[str] = cfg.labels or []

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(cfg.username, cfg.api_token)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        # Prevent urllib3 from logging Authorization headers at DEBUG level
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        self.session.verify = _CA_BUNDLE
        if cfg.proxy_url:
            self.session.proxies = {"http": cfg.proxy_url, "https": cfg.proxy_url}

    def _url(self, path: str) -> str:
        return f"{self.api_base}/{path.lstrip('/')}"

    def _emit(self, event: dict) -> None:
        """Send an event to the registered callback (used by SSE overlay)."""
        if self._event_callback:
            event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            self._event_callback(event)

    def _request(self, method: str, url: str, label: str = "", **kwargs) -> requests.Response:
        """Central wrapper around session.request with verbose logging and event emission."""
        if self._abort_check and self._abort_check():
            raise OperationAbortedError("Operation aborted")
        body = kwargs.get("json")
        params = kwargs.get("params")

        if self._verbose:
            req_info = sanitize_request(method, url, body=body)
            if params:
                req_info["params"] = params
            log.debug("VERBOSE %s → %s %s", label, method, json.dumps(req_info, default=str))

        self._emit({
            "type": "api_call",
            "label": label,
            "method": method.upper(),
            "url": sanitize_request(method, url)["url"],
            "params": params,
        })

        resp = self.session.request(method, url, **kwargs)

        if self._verbose:
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = resp.text[:500] if resp.text else None
            resp_info = sanitize_response(resp.status_code, body=resp_body)
            log.debug("VERBOSE %s ← %s", label, json.dumps(resp_info, default=str))

        self._emit({
            "type": "api_response",
            "label": label,
            "status": resp.status_code,
        })

        return resp

    def _log_error(self, label: str, resp: requests.Response) -> str:
        """Log full response details to file and return a UI-safe summary."""
        try:
            body = resp.json()
            pretty = json.dumps(body, indent=2)
        except Exception:
            body = {}
            pretty = resp.text
        log.error("%s — HTTP %s\n%s", label, resp.status_code, pretty)
        # Return generic messages for common auth/permission errors
        if resp.status_code == 401:
            return "HTTP 401 — Authentication failed. Check your API token."
        if resp.status_code == 403:
            return "HTTP 403 — Permission denied. Check your project access."
        if resp.status_code == 404:
            return "HTTP 404 — Resource not found. Check your Jira URL and project key."
        # For other errors, return Jira's structured error fields (field-level validation feedback)
        messages = body.get("errorMessages", [])
        errors = body.get("errors", {})
        # errors may be a dict (standard Jira) or a list of dicts (Teams API)
        if isinstance(errors, dict):
            error_parts = [f"{k}: {v}" for k, v in errors.items()]
        elif isinstance(errors, list):
            error_parts = [e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in errors]
        else:
            error_parts = []
        parts = list(messages) + error_parts
        detail = "; ".join(parts) if parts else "See logs for details"
        return f"HTTP {resp.status_code} — {detail}"

    def detect_ac_field(self) -> Tuple[Optional[str], Optional[str]]:
        """Find the Acceptance Criteria custom field ID via GET /rest/api/3/field.

        Returns (field_id, field_name) on success, or (None, error_message) on failure.
        """
        try:
            resp = self._request("GET", self._url("field"), label="detect_ac_field", timeout=10)
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

    def fetch_org_id(self) -> Tuple[Optional[str], Optional[str]]:
        """Fetch the Atlassian Organization ID via GET /admin/v1/orgs.

        This returns the actual org ID needed for the Teams API, which is
        distinct from the Cloud/Site ID returned by fetch_cloud_id().
        Requires admin API access or the read:org:jira OAuth scope.

        Returns (org_id, error_message). org_id is None on failure.
        """
        url = "https://api.atlassian.com/admin/v1/orgs"
        try:
            resp = self._request("GET", url, label="fetch_org_id", timeout=10)
            if resp.status_code != 200:
                return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
            data = resp.json()
            orgs = data.get("data", [])
            if not orgs:
                return None, "No organizations found. Admin API access or read:org:jira scope may be required."
            org_id = orgs[0].get("id")
            if not org_id:
                return None, "Organization entry found but missing 'id' field."
            log.info("fetch_org_id: orgId=%s (name=%s)", org_id, orgs[0].get("attributes", {}).get("name", ""))
            return org_id, None
        except requests.RequestException as exc:
            log.error("fetch_org_id exception: %s", exc)
            return None, str(exc)

    def fetch_cloud_id(self) -> Tuple[Optional[str], Optional[str]]:
        """Fetch the Atlassian Cloud/Site ID via GET /_edge/tenant_info.

        NOTE: This returns the Cloud/Site ID, NOT the Organization ID needed
        for the Teams API. Use fetch_org_id() for Teams API calls.

        Returns (cloud_id, error_message). cloud_id is None on failure.
        """
        url = self.base_url + "/_edge/tenant_info"
        try:
            resp = self._request("GET", url, label="fetch_cloud_id", timeout=10)
            if resp.status_code != 200:
                return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
            cloud_id = resp.json().get("cloudId")
            if not cloud_id:
                return None, "Response did not contain cloudId"
            log.info("fetch_cloud_id: cloudId=%s", cloud_id)
            return cloud_id, None
        except requests.RequestException as exc:
            log.error("fetch_cloud_id exception: %s", exc)
            return None, str(exc)

    def fetch_assignees(self, max_results: int = 50, project_key: Optional[str] = None, query: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
        """Fetch top assignable users for the project.

        Args:
            max_results: Maximum number of users to return (default 50).
            project_key: Override the configured project key. Falls back to self.project_key.
            query: Optional text search against displayName/emailAddress (passed to Jira API).

        Returns (users, error_message). users is [] on failure.
        """
        effective_project = project_key or self.project_key
        params: dict = {"project": effective_project, "maxResults": max_results}
        if query:
            params["query"] = query
        try:
            resp = self._request(
                "GET", self._url("user/assignable/search"),
                label="fetch_assignees",
                params=params,
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
            log.info("fetch_assignees: %d users (project=%s, query=%r)", len(users), effective_project, query)
            return users[:max_results], None
        except requests.RequestException as exc:
            log.error("fetch_assignees exception: %s", exc)
            return [], str(exc)

    def fetch_project_roles(self, project_key: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
        """Fetch all roles for a project via GET /project/{key}/role.

        Returns (roles, error_message). roles is a list of {id: int, name: str}.
        """
        effective_project = project_key or self.project_key
        try:
            resp = self._request(
                "GET", self._url(f"project/{effective_project}/role"),
                label="fetch_project_roles",
                timeout=10,
            )
            if resp.status_code != 200:
                return [], self._log_error("fetch_project_roles", resp)
            data = resp.json()
            # Response is a dict of {roleName: roleUrl}; extract id from URL
            roles = []
            for name, url in data.items():
                # URL format: .../project/{key}/role/{id}
                try:
                    role_id = int(url.rstrip("/").split("/")[-1])
                    roles.append({"id": role_id, "name": name})
                except (ValueError, IndexError):
                    log.warning("fetch_project_roles: could not parse role id from %r", url)
            roles.sort(key=lambda r: r["name"])
            log.info("fetch_project_roles: %d roles for project %s", len(roles), effective_project)
            return roles, None
        except requests.RequestException as exc:
            log.error("fetch_project_roles exception: %s", exc)
            return [], str(exc)

    def fetch_role_members(self, role_id: int, project_key: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
        """Fetch all members of a project role as full user dicts.

        GET /project/{key}/role/{id} returns actors; extracts {accountId, displayName, emailAddress}
        for each user actor. Group actors are resolved via fetch_group_members (uncapped).
        Returns (users, error_message). users is [] on failure.
        """
        effective_project = project_key or self.project_key
        try:
            resp = self._request(
                "GET", self._url(f"project/{effective_project}/role/{role_id}"),
                label="fetch_role_members",
                timeout=10,
            )
            if resp.status_code != 200:
                return [], self._log_error("fetch_role_members", resp)
            actors = resp.json().get("actors", [])
            users: List[dict] = []
            for a in actors:
                if a.get("type") == "atlassian-user-role-actor":
                    account_id = (a.get("actorUser") or {}).get("accountId")
                    if account_id:
                        users.append({
                            "accountId": account_id,
                            "displayName": a.get("displayName", ""),
                            "emailAddress": "",
                        })
            # Also resolve group actors — roles commonly have groups rather than individual users
            group_actors = [a for a in actors if a.get("type") == "atlassian-group-role-actor"]
            if group_actors:
                log.info("fetch_role_members: role_id=%d has %d group actor(s), resolving members", role_id, len(group_actors))
            for ga in group_actors:
                group_name = ga.get("name")
                if not group_name:
                    continue
                members, group_err = self.fetch_group_members(group_name, max_results=0)
                if group_err:
                    log.warning("fetch_role_members: could not resolve group %r: %s", group_name, group_err)
                    continue
                users.extend(members)
            # Deduplicate by accountId while preserving order
            seen: set = set()
            unique: List[dict] = []
            for u in users:
                aid = u["accountId"]
                if aid not in seen:
                    seen.add(aid)
                    unique.append(u)
            log.info("fetch_role_members: role_id=%d → %d members (incl. group-resolved)", role_id, len(unique))
            return unique, None
        except requests.RequestException as exc:
            log.error("fetch_role_members exception: %s", exc)
            return [], str(exc)

    def fetch_groups(self, query: str = "") -> Tuple[List[dict], Optional[str]]:
        """Search Jira groups by name via GET /groups/picker.

        Returns (groups, error_message). groups is a list of {name} dicts.
        """
        try:
            resp = self._request(
                "GET", self._url("groups/picker"),
                label="fetch_groups",
                params={"query": query, "maxResults": 50},
                timeout=10,
            )
            if resp.status_code != 200:
                return [], self._log_error("fetch_groups", resp)
            data = resp.json()
            groups = [{"name": g["name"]} for g in data.get("groups", [])]
            log.info("fetch_groups: query=%r → %d groups", query, len(groups))
            return groups, None
        except requests.RequestException as exc:
            log.error("fetch_groups exception: %s", exc)
            return [], str(exc)

    def fetch_teams(self, query: str = "") -> Tuple[List[dict], Optional[str]]:
        """Search Atlassian Teams via GET /gateway/api/public/teams/v1/org/{orgId}/teams.

        Requires org_id to be set in JiraConfig. Returns ([{teamId, displayName}], error).
        """
        if not self._org_id:
            return [], "Atlassian Org ID not configured — set it in Settings"
        try:
            resp = self._request(
                "GET", f"{self._teams_base}/teams",
                label="fetch_teams",
                params={"query": query, "maxResults": 50},
                timeout=10,
            )
            if resp.status_code != 200:
                return [], self._log_error("fetch_teams", resp)
            data = resp.json()
            teams = [
                {"teamId": t.get("teamId") or t.get("id", ""), "displayName": t.get("displayName", "")}
                for t in data.get("values", [])
                if t.get("teamId") or t.get("id")
            ]
            log.info("fetch_teams: query=%r → %d teams", query, len(teams))
            return teams, None
        except requests.RequestException as exc:
            log.error("fetch_teams exception: %s", exc)
            return [], str(exc)

    def fetch_team_members(self, team_id: str, max_results: int = 0) -> Tuple[List[dict], Optional[str]]:
        """Fetch members of an Atlassian Team.

        GET /gateway/api/public/teams/v1/org/{orgId}/teams/{teamId}/members
        Returns [{accountId}] list. Paginates via nextCursor until all members fetched.
        Pass max_results > 0 to cap the total.
        """
        if not self._org_id:
            return [], "Atlassian Org ID not configured — set it in Settings"
        try:
            members: List[dict] = []
            cursor = None
            while True:
                params: dict = {"maxResults": 50}
                if cursor:
                    params["cursor"] = cursor
                resp = self._request(
                    "GET", f"{self._teams_base}/teams/{team_id}/members",
                    label="fetch_team_members",
                    params=params,
                    timeout=10,
                )
                if resp.status_code != 200:
                    return [], self._log_error("fetch_team_members", resp)
                data = resp.json()
                for m in data.get("results", []):
                    account_id = m.get("accountId") or (m.get("member", {}) or {}).get("accountId")
                    if account_id:
                        members.append({"accountId": account_id})
                cursor = data.get("nextCursor")
                if not cursor or not data.get("results") or (max_results > 0 and len(members) >= max_results):
                    break
            result = members[:max_results] if max_results > 0 else members
            log.info("fetch_team_members: team_id=%r → %d members", team_id, len(result))
            return result, None
        except requests.RequestException as exc:
            log.error("fetch_team_members exception: %s", exc)
            return [], str(exc)

    def fetch_group_members(self, group_name: str, max_results: int = 0) -> Tuple[List[dict], Optional[str]]:
        """Fetch members of a Jira group via GET /group/member.

        Returns (users, error_message). users is [{accountId, displayName, emailAddress}].
        Paginates until all members are fetched. Pass max_results > 0 to cap the total.
        """
        try:
            users: List[dict] = []
            start_at = 0
            while True:
                resp = self._request(
                    "GET", self._url("group/member"),
                    label="fetch_group_members",
                    params={
                        "groupname": group_name,
                        "startAt": start_at,
                        "maxResults": 50,
                        "includeInactiveUsers": False,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    return [], self._log_error("fetch_group_members", resp)
                data = resp.json()
                page = data.get("values", [])
                for u in page:
                    if not u.get("accountType", "").startswith("app"):
                        users.append({
                            "accountId": u["accountId"],
                            "displayName": u.get("displayName", ""),
                            "emailAddress": u.get("emailAddress", ""),
                        })
                if not page or data.get("isLast", False) or (max_results > 0 and len(users) >= max_results):
                    break
                start_at += len(page)
            result = users[:max_results] if max_results > 0 else users
            log.info("fetch_group_members: group=%r → %d members", group_name, len(result))
            return result, None
        except requests.RequestException as exc:
            log.error("fetch_group_members exception: %s", exc)
            return [], str(exc)

    def resolve_users_bulk(self, account_ids: List[str]) -> Tuple[List[dict], Optional[str]]:
        """Resolve a list of accountIds to full user dicts via GET /rest/api/3/user/bulk.

        Processes in batches of 200. Returns [{accountId, displayName, emailAddress}].
        If the bulk endpoint is unavailable (permissions), falls back to individual lookups.
        """
        if not account_ids:
            return [], None
        try:
            resolved: List[dict] = []
            batch_size = 200
            for i in range(0, len(account_ids), batch_size):
                batch = account_ids[i:i + batch_size]
                params = [("accountId", aid) for aid in batch]
                params.append(("maxResults", batch_size))
                resp = self._request(
                    "GET", self._url("user/bulk"),
                    label="resolve_users_bulk",
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 403:
                    log.warning("resolve_users_bulk: permission denied for bulk lookup — returning partial data")
                    for aid in account_ids:
                        resolved.append({"accountId": aid, "displayName": aid, "emailAddress": ""})
                    return resolved, None
                if resp.status_code != 200:
                    return [], self._log_error("resolve_users_bulk", resp)
                data = resp.json()
                for u in data.get("values", []):
                    if not u.get("accountType", "").startswith("app"):
                        resolved.append({
                            "accountId": u["accountId"],
                            "displayName": u.get("displayName", ""),
                            "emailAddress": u.get("emailAddress", ""),
                        })
            log.info("resolve_users_bulk: resolved %d of %d account IDs", len(resolved), len(account_ids))
            return resolved, None
        except requests.RequestException as exc:
            log.error("resolve_users_bulk exception: %s", exc)
            return [], str(exc)

    def fetch_projects(self) -> Tuple[List[dict], Optional[str]]:
        """Fetch all accessible projects via GET /rest/api/3/project/search (paginated).

        Returns (projects, error_message). projects is a list of {key, name} dicts.
        """
        try:
            projects: List[dict] = []
            start_at = 0
            while True:
                resp = self._request(
                    "GET", self._url("project/search"),
                    label="fetch_projects",
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

    def fetch_label_names(self) -> Tuple[List[str], Optional[str]]:
        """Return all label names from the Jira instance (no usage counting).

        Paginates through GET /rest/api/3/label and returns a flat list of strings.
        Fast — suitable for live search. Returns (label_list, error_message).
        """
        try:
            all_labels: List[str] = []
            start_at = 0
            while True:
                resp = self._request(
                    "GET", self._url("label"),
                    label="fetch_label_names",
                    params={"startAt": start_at, "maxResults": 200},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return [], self._log_error("fetch_label_names", resp)
                data = resp.json()
                page = data.get("values", [])
                all_labels.extend(page)
                if not page or len(all_labels) >= data.get("total", 0):
                    break
                start_at += len(page)
            log.info("fetch_label_names: %d labels found", len(all_labels))
            return all_labels, None
        except requests.RequestException as exc:
            log.error("fetch_label_names exception: %s", exc)
            return [], str(exc)

    def fetch_label_suggestions(self, prefix: str) -> Tuple[List[str], Optional[str]]:
        """Return label names matching a prefix via Jira's JQL autocomplete API.

        Uses GET /rest/api/3/jql/autocompletedata/suggestions?fieldName=labels&fieldValue=<prefix>
        for server-side prefix matching — single API call, no pagination needed.
        Returns (label_list, error_message).
        """
        try:
            resp = self._request(
                "GET", self._url("jql/autocompletedata/suggestions"),
                label="fetch_label_suggestions",
                params={"fieldName": "labels", "fieldValue": prefix},
                timeout=10,
            )
            if resp.status_code != 200:
                return [], self._log_error("fetch_label_suggestions", resp)
            results = resp.json().get("results", [])
            # Strip surrounding quotes that Jira adds for labels containing spaces
            labels = [r["value"].strip('"') for r in results if r.get("value")]
            log.info("fetch_label_suggestions: prefix=%r → %d matches", prefix, len(labels))
            return labels, None
        except requests.RequestException as exc:
            log.error("fetch_label_suggestions exception: %s", exc)
            return [], str(exc)

    def fetch_labels(
        self,
        top_n: int = 40,
        project_key: Optional[str] = None,
        name_filter: Optional[str] = None,
        emit: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[dict], Optional[str]]:
        """Return the top_n labels as [{name, count}] dicts, with optional filtering.

        When project_key is set: scans issues via JQL to count label frequency
        (efficient — single paginated query, returns counts).
        When project_key is None and name_filter is set: uses the JQL autocomplete
        suggestions API for server-side prefix matching (single API call, no counts).
        When project_key is None and no filter: fetches all label names alphabetically
        (paginated, no counts).

        name_filter: prefix filter on label name (server-side when no project scope).
        emit: optional callable(str) for progress status messages.

        Returns (label_list, error_message). label_list is [] on failure.
        Each item is {"name": str, "count": int | None}.
        """
        from collections import Counter

        def _emit(msg: str) -> None:
            if emit:
                emit(msg)

        try:
            if project_key:
                # Project-scoped path: scan issues with labels in this project,
                # count frequency from issue.fields.labels — single paginated query.
                counts: Counter = Counter()
                _emit(f"Fetching labels used in project {project_key}...")
                jql = f'project = "{project_key}" AND labels is not EMPTY'
                start_at = 0
                page_size = 100
                issues_scanned = 0
                max_issues = 2000  # safety cap to avoid runaway scans
                while issues_scanned < max_issues:
                    resp = self._request(
                        "GET", self._url("issue/search"),
                        label="fetch_labels:project_scan",
                        params={
                            "jql": jql,
                            "fields": "labels",
                            "startAt": start_at,
                            "maxResults": page_size,
                        },
                        timeout=15,
                    )
                    if resp.status_code != 200:
                        return [], self._log_error("fetch_labels:project_scan", resp)
                    data = resp.json()
                    issues = data.get("issues", [])
                    if not issues:
                        break
                    for issue in issues:
                        for lbl in issue.get("fields", {}).get("labels", []):
                            counts[lbl] += 1
                    issues_scanned += len(issues)
                    if issues_scanned >= data.get("total", 0):
                        break
                    start_at += len(issues)
                    _emit(f"Scanned {issues_scanned} issues, found {len(counts)} unique labels so far...")
                log.info("fetch_labels: project=%r scanned %d issues, %d unique labels",
                         project_key, issues_scanned, len(counts))

                # Apply name filter client-side for project-scoped path
                if name_filter:
                    nf = name_filter.lower()
                    counts = Counter({lbl: n for lbl, n in counts.items() if lbl.lower().startswith(nf)})
                    log.info("fetch_labels: after name_filter=%r → %d labels", name_filter, len(counts))

                labels = [{"name": lbl, "count": n} for lbl, n in counts.most_common(top_n)]
                log.info("fetch_labels: returning %d labels (project-scoped, with counts)", len(labels))
                return labels, None

            elif name_filter:
                # Global path with prefix filter: use autocomplete suggestions API
                _emit(f"Fetching labels with prefix '{name_filter}' from Jira...")
                names, err = self.fetch_label_suggestions(name_filter)
                if err:
                    return [], err
                labels = [{"name": lbl, "count": None} for lbl in names[:top_n]]
                log.info("fetch_labels: returning %d labels (global prefix filter)", len(labels))
                return labels, None

            else:
                # Global path without filter: fetch all label names alphabetically
                _emit("Fetching all labels from Jira...")
                all_names, err = self.fetch_label_names()
                if err:
                    return [], err
                labels = [{"name": lbl, "count": None} for lbl in all_names[:top_n]]
                log.info("fetch_labels: returning %d of %d labels (global, no counts)",
                         len(labels), len(all_names))
                return labels, None

        except requests.RequestException as exc:
            log.error("fetch_labels exception: %s", exc)
            return [], str(exc)

    def count_label_usage(
        self,
        labels: List[str],
        project_key: Optional[str] = None,
        emit: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[dict], Optional[str]]:
        """Count how many issues use each label and return [{name, count}] list.

        Makes one API call per label (POST /rest/api/3/issue/search with maxResults=0
        to read the `total` field without fetching issue bodies). Uses POST to avoid
        Jira Cloud returning 404 for GET requests with label values containing special
        characters. Intentionally bounded by the cached label set (typically 5–200 labels).

        project_key: if set, scopes the JQL to that project only.
        emit: optional callable(str) for progress status messages.
        Returns (label_list, error_message).
        """
        def _emit(msg: str) -> None:
            if emit:
                emit(msg)

        results: List[dict] = []
        try:
            total = len(labels)
            for i, lbl in enumerate(labels, 1):
                if self._abort_check and self._abort_check():
                    raise OperationAbortedError()
                if project_key:
                    jql = f'project = "{project_key}" AND labels = "{lbl}"'
                else:
                    jql = f'labels = "{lbl}"'
                # Use POST to avoid Jira Cloud returning 404 for GET requests with
                # label values containing special characters (hyphens, underscores).
                # maxResults=0 is sufficient — we only need the `total` field.
                resp = self._request(
                    "POST", self._url("issue/search"),
                    label="count_label_usage",
                    json={"jql": jql, "maxResults": 0, "fields": []},
                    timeout=10,
                )
                if resp.status_code == 200:
                    count = resp.json().get("total", 0)
                else:
                    count = 0
                    log.warning("count_label_usage: %r → HTTP %d", lbl, resp.status_code)
                results.append({"name": lbl, "count": count})
                log.debug("count_label_usage: %r → %d issues", lbl, count)
                if i % 5 == 0 or i == total:
                    _emit(f"Counted {i}/{total} labels\u2026")
            log.info("count_label_usage: counted %d labels", len(results))
            return results, None
        except OperationAbortedError:
            raise
        except requests.RequestException as exc:
            log.error("count_label_usage exception: %s", exc)
            return [], str(exc)

    def test_connection(self) -> Tuple[bool, str]:
        try:
            resp = self._request("GET", self._url("myself"), label="test_connection", timeout=10)
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
            resp = self._request("POST", self._url("issue"), label=label, json=payload, timeout=15)
            if resp.status_code in (200, 201):
                return resp.json().get("key"), None

            # If it failed and we sent AC as plain text, retry with ADF in case
            # this instance uses a rich-text AC field.
            if resp.status_code == 400 and self.ac_field_id in payload.get("fields", {}):
                ac_val = payload["fields"][self.ac_field_id]
                if isinstance(ac_val, str):
                    log.info("%s: plain-text AC rejected, retrying with ADF", label)
                    payload["fields"][self.ac_field_id] = _adf(ac_val)
                    resp2 = self._request("POST", self._url("issue"), label=label + ":adf_retry", json=payload, timeout=15)
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
            resp = self._request(
                "GET", self._url(f"issue/{issue_key}/transitions"),
                label="transition_issue:get",
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
            self._request(
                "POST", self._url(f"issue/{issue_key}/transitions"),
                label="transition_issue:post",
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
            self._request("POST", self._url(f"issue/{issue_key}/comment"), label="add_comment", json=payload, timeout=10)
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
