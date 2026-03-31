# Cache Management & Assignee Filter Improvements — Design Spec

**Date:** 2026-03-31
**Status:** Approved

## Overview

Four focused improvements to JiraMaster's local data storage and assignee refresh workflow:

1. Consolidate all runtime JSON caches into a `cache/` directory
2. Persist the project list so it doesn't need to be re-fetched on every page load
3. Add Atlassian Teams as a proper filter type (separate from Jira groups)
4. Add a Cache Manager page for viewing and deleting cached data

---

## 1. Cache Directory Consolidation

### Problem
`assignees.json` and `labels.json` currently live at the project root alongside source code. There is no `projects.json` cache yet. The root is already cluttered with `config.json`, `.secret_key`, and other runtime files.

### Solution
Create a `cache/` directory for all runtime JSON caches. Add `cache/*.json` to `.gitignore`.

**Files moved:**
- `assignees.json` → `cache/assignees.json`
- `labels.json` → `cache/labels.json`

**New files:**
- `cache/projects.json` — project list cache (see Section 2)

**Module changes:**
- `assignees.py`: update `ASSIGNEES_FILE` path to `cache/assignees.json`
- `labels.py`: update `LABELS_FILE` path to `cache/labels.json`
- New `projects.py`: same load/save pattern, path `cache/projects.json`

**Cache file format** (all three types use a wrapper for metadata):
```json
{
  "updated_at": "2026-03-31T14:00:00Z",
  "items": [ ... ]
}
```

The `load_*` functions return only `items`; callers are unaware of the wrapper. The `save_*` functions write the wrapper with current UTC timestamp.

**`data/` directory is unchanged** — `prompt_template.txt` stays there. `data/` is for static assets; `cache/` is for runtime data.

---

## 2. Project Scope Cache

### Problem
The project scope dropdown on the Tools page starts empty. Users must click "Load Projects" on every visit, triggering a Jira API call each time.

### Solution
- New `projects.py` module with `load_projects() → List[dict]` and `save_projects(projects)`.
- The `/fetch-projects` endpoint in `routes/tools.py` saves the fetched list to `cache/projects.json` after a successful call.
- On `GET /tools/`, `load_projects()` is called and passed to the template as `projects_cache`.
- The template pre-populates the project scope dropdown from `projects_cache` if available. The configured default project key is always shown first.
- "Load Projects" button still triggers a fresh Jira fetch and updates the cache.

---

## 3. Atlassian Teams Filter

### Problem
The existing "Group / Team" filter calls `/rest/api/2/groups/picker` — Jira internal groups only. Atlassian Teams (`/people/team/xxx` URLs) live under a separate API (`/gateway/api/public/teams/v1/org/{orgId}/teams`) and are invisible to the group filter.

### Solution

**Config change:**
- Add `org_id: str = ""` to `JiraConfig` in `models.py`
- Add `org_id` to `config.json` load/save in `config.py`
- Add "Atlassian Org ID" field to the Settings page

**JiraClient additions:**
- `fetch_teams(query: str = "") -> Tuple[List[dict], Optional[str]]`
  - Calls `GET /gateway/api/public/teams/v1/org/{org_id}/teams`
  - Returns `[{teamId, displayName}]`
- `fetch_team_members(team_id: str) -> Tuple[List[dict], Optional[str]]`
  - Calls `GET /gateway/api/public/teams/v1/org/{org_id}/teams/{teamId}/members`
  - Returns `[{accountId}]`, then enriches with displayName/email from the assignee base pool

**New endpoint:** `POST /tools/fetch-teams` in `routes/tools.py` — returns JSON list of `{teamId, displayName}`.

**Filter UI (tools/index.html):**
- Add a 4th filter row: "Atlassian Team" — dropdown + "Load Teams" button
- If `org_id` is not configured, "Load Teams" shows an inline warning with a link to Settings instead of making an API call
- Selecting a team intersects the base user pool with team members (same AND logic as role/group)

**Backend (refresh_assignees):**
- New optional form field: `filter_team_id`
- Step 4 (after group): if `filter_team_id` provided, fetch team members and intersect

The existing Group filter is unchanged. Teams and Groups are independent filters.

---

## 4. Cache Manager Page (`/cache`)

### New blueprint: `routes/cache_manager.py`

Registered at `/cache`. Added to the navbar between "Tools" and "Settings".

### Page layout

Three collapsible sections, one per cache type. Each section shows:
- Row count and `updated_at` timestamp (from cache file metadata)
- A "Clear all" button
- A table of entries with a per-row delete button

| Cache | Table columns | Delete key |
|-------|--------------|------------|
| Assignees | Display name, Email, Account ID | `accountId` |
| Labels | Label name | label string |
| Projects | Key, Name | `key` |

### Routes

| Method | Path | Action |
|--------|------|--------|
| GET | `/cache/` | Render the management page |
| POST | `/cache/delete/<type>/<item_id>` | Delete one entry; returns JSON `{ok: true}` |
| POST | `/cache/clear/<type>` | Delete entire cache file; returns JSON `{ok: true}` |

`<type>` is one of: `assignees`, `labels`, `projects`.

### Interaction

All deletes are AJAX — the row fades out on success, no full page reload. CSRF token is sent as `X-CSRFToken` header. On error, an inline alert appears.

### Template

`templates/cache_manager/index.html` — extends `base.html`. One Bootstrap card per cache type, collapsible with `data-bs-toggle="collapse"`.

---

## Component Summary

| Component | File(s) changed/created |
|-----------|------------------------|
| Cache dir | `cache/` (new), `.gitignore` |
| Assignee cache path | `assignees.py` |
| Label cache path | `labels.py` |
| Project cache | `projects.py` (new) |
| Atlassian Teams API | `jira_client.py` |
| Org ID config | `models.py`, `config.py` |
| Settings page | `templates/settings/index.html` |
| Tools routes | `routes/tools.py` |
| Tools template | `templates/tools/index.html` |
| Cache Manager blueprint | `routes/cache_manager.py` (new) |
| Cache Manager template | `templates/cache_manager/index.html` (new) |
| Blueprint registration | `routes/__init__.py` |
| Navbar | `templates/base.html` |

---

## Out of Scope

- No change to `.work/` session storage
- No change to `config.json` storage location
- No automatic cache expiry / TTL — manual refresh only
- No search/filter on the Cache Manager page
