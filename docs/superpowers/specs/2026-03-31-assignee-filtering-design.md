# Assignee Filtering Design

**Date:** 2026-03-31
**Status:** Approved
**Author:** Stefan (via brainstorming session)

---

## Problem

JiraMaster fetches assignable users from Jira using `GET /rest/api/3/user/assignable/search`. In organizations with large Jira installations and many read-only users, this returns far too many people, making the assignee dropdowns in the Edit step unusable.

---

## Goals

1. Let users filter which people get cached as assignees — by project role, group, and/or name/email query
2. Filter is applied at **fetch time** (smaller cache) AND a live search helps in the Edit dropdowns
3. Filters are configured on the **Tools page** next to the existing Refresh Assignees button
4. Multiple active filters combine with **AND logic** (intersection)

---

## Non-Goals

- No persistent filter settings saved to `config.json` (Tools page only, set per-refresh)
- No admin-level Jira API calls (e.g., listing all groups — users must know their group name)
- No third-party JS dependencies (vanilla JS + Bootstrap only)

---

## Architecture

### New Jira API Methods (`jira_client.py`)

Three new methods added to `JiraClient`:

```python
def fetch_project_roles(self, project_key: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
    """GET /project/{key}/role → [{id, name}, ...]"""

def fetch_role_members(self, role_id: int, project_key: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
    """GET /project/{key}/role/{id} → [accountId, ...]"""

def fetch_group_members(self, group_name: str, max_results: int = 200) -> Tuple[List[dict], Optional[str]]:
    """GET /group/member?groupname=... → [{accountId, displayName, emailAddress}, ...]"""
```

The existing `fetch_assignees()` gains an optional `query: str` parameter passed directly to the Jira API `query` field.

### Filter Logic (`routes/tools.py` — `refresh_assignees` handler)

```
1. Fetch base pool: user/assignable/search(project, query, maxResults)
   → list of {accountId, displayName, emailAddress}

2. If role_id provided:
   → fetch role member accountIds
   → intersect base pool: keep only users whose accountId is in role set

3. If group_name provided:
   → fetch group member accountIds
   → intersect current pool

4. Save final pool to assignees.json
```

All filters are optional and independent — using none gives current behavior.

### New AJAX Endpoint (`routes/tools.py`)

```
POST /tools/fetch-roles
  Body: (none — uses configured project or project_scope from form)
  Returns: JSON [{id: int, name: str}, ...]
```

---

## UI Changes

### Tools Page — Refresh Assignees Card (`templates/tools/index.html`)

The existing card gains a collapsible **"Filter Options"** section (Bootstrap `collapse`), collapsed by default to preserve current UX for users who don't need filtering.

```
[ Refresh Assignees Card ]
  Cache: 47 users cached

  Project scope: [dropdown ▼]  [Load Projects]

  ▶ Filter Options (collapsed by default)
    ┌─────────────────────────────────────────┐
    │ Role       [dropdown ▼]  [Load Roles]   │
    │ Group name [text input________________] │
    │ Name/email [text input________________] │
    │ Max results [50        ]               │
    └─────────────────────────────────────────┘

  [Refresh Assignees]
```

**Role dropdown behavior:**
- Populated via AJAX `POST /tools/fetch-roles` (same pattern as existing Load Projects)
- Reloads when project scope changes
- First option: `— no role filter —`

**Group name:**
- Free text input — user must know their Jira group name
- Helper text: "Exact Jira group name (case-sensitive)"

**Max results:**
- Number input, range 10–200, default 50 (raised from current 20)

### Edit Step — Searchable Dropdowns (`templates/edit/index.html`)

A small vanilla JS search input is added above each assignee `<select>` element. As the user types, non-matching `<option>` elements are hidden in real time.

```html
<input type="text" placeholder="Search assignees…" class="form-control form-control-sm mb-1 assignee-search">
<select name="epic_0_assignee" class="form-select assignee-select">…</select>
```

A single reusable JS function handles all assignee search inputs — no duplication.

---

## Data Flow

```
Tools page
  └─ User sets filters → POST /tools/refresh-assignees
       └─ fetch_assignees(query, maxResults)          → Jira API
       └─ [optional] fetch_role_members(role_id)      → Jira API
       └─ [optional] fetch_group_members(group_name)  → Jira API
       └─ intersect results → save to assignees.json

Edit page
  └─ load_assignees() reads assignees.json
  └─ Renders <select> dropdowns with filtered list
  └─ Vanilla JS search box narrows visible options further
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Role fetch fails | Flash warning; fall back to unfiltered assignee list |
| Group not found / fetch fails | Flash warning; fall back to current pool |
| Role filter returns empty set | Flash info: "No users matched the selected role" |
| Intersection yields empty set | Flash warning: "All filters combined returned 0 users — cache not updated" |

---

## Files Changed

| File | Change |
|------|--------|
| `jira_client.py` | Add `fetch_project_roles()`, `fetch_role_members()`, `fetch_group_members()`; update `fetch_assignees()` with `query` param |
| `routes/tools.py` | Update `refresh_assignees` to accept + apply filter params; add `fetch_roles` AJAX endpoint |
| `templates/tools/index.html` | Add collapsible Filter Options section with role/group/query/max fields + Load Roles JS |
| `templates/edit/index.html` | Add vanilla JS search input above each assignee `<select>` |

---

## Verification

1. **Tools page** — Load roles for a project; select a role; click Refresh Assignees; verify `assignees.json` only contains role members
2. **Group filter** — Enter a known group name; verify cache intersects correctly
3. **Name/email query** — Enter partial name; verify only matching users cached
4. **Combined filters** — Use role + query together; verify AND intersection
5. **Empty result guard** — Use a role with no members; verify cache is NOT cleared + warning shown
6. **Edit dropdowns** — Type in search box above assignee select; verify options filter live
7. **No filters** — Submit refresh with all filters empty; verify existing behavior unchanged
