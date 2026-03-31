# Cache Management & Assignee Filter Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate runtime JSON caches into `cache/`, add project scope caching, add Atlassian Teams as a filter type, and build a Cache Manager page for viewing/deleting cached data.

**Architecture:** A `cache/` directory holds all runtime JSON (assignees, labels, projects). Each cache module (`assignees.py`, `labels.py`, new `projects.py`) wraps entries in `{"updated_at": "...", "items": [...]}` metadata. A new `cache_manager` blueprint at `/cache` exposes read/delete routes. The Atlassian Teams filter is added alongside the existing Group filter; it requires a new `org_id` field in `JiraConfig`.

**Tech Stack:** Python 3 / Flask 3, Jinja2, Bootstrap 5.3, `requests`, no new dependencies.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `cache/` | Create dir | Runtime JSON storage |
| `.gitignore` | Modify | Ignore `cache/*.json` |
| `assignees.py` | Modify | Update path → `cache/assignees.json`, add metadata wrapper |
| `labels.py` | Modify | Update path → `cache/labels.json`, add metadata wrapper |
| `projects.py` | Create | Load/save `cache/projects.json` |
| `models.py` | Modify | Add `org_id: str = ""` to `JiraConfig` |
| `config.py` | Modify | Include `org_id` in `to_dict` / `from_dict` |
| `jira_client.py` | Modify | Add `fetch_teams()` and `fetch_team_members()` |
| `routes/tools.py` | Modify | Save project cache; add `/fetch-teams`; add team filter in `refresh_assignees` |
| `routes/cache_manager.py` | Create | Blueprint for `/cache` — view, delete-one, clear-all |
| `routes/__init__.py` | Modify | Register `cache_manager` blueprint |
| `templates/base.html` | Modify | Add "Cache" nav item between "Jira Tools" and settings icon |
| `templates/tools/index.html` | Modify | Pre-populate projects dropdown; add Atlassian Team filter row |
| `templates/settings/index.html` | Modify | Add "Atlassian Org ID" field |
| `templates/cache_manager/index.html` | Create | Cache Manager page |

---

## Task 1: Create `cache/` directory and update `.gitignore`

**Files:**
- Create: `cache/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create the cache directory with a gitkeep**

```bash
mkdir -p cache && touch cache/.gitkeep
```

- [ ] **Step 2: Update `.gitignore` to ignore cache JSON files**

In `.gitignore`, after the line `assignees.json` / `labels.json` (currently there aren't explicit entries — they're just not committed). Add these lines after the `# JiraMaster runtime files` comment:

Current `.gitignore` (relevant section):
```
# JiraMaster runtime files
config.json
.secret_key
.work/
logs/
venv/
__pycache__/
*.pyc
*.pyo
.env
```

New `.gitignore`:
```
# JiraMaster runtime files
config.json
.secret_key
.work/
logs/
cache/
venv/
__pycache__/
*.pyc
*.pyo
.env
```

Note: We ignore the whole `cache/` directory (not just `*.json`) so the gitkeep is also excluded. Add `cache/.gitkeep` to the ignore pattern instead if you want the directory tracked — but since Flask/start scripts can create it, ignoring the whole directory is fine. Actually, to keep the directory in git (so it exists on clone), track the gitkeep:

```
# JiraMaster runtime files
config.json
.secret_key
.work/
logs/
cache/*.json
venv/
__pycache__/
*.pyc
*.pyo
.env
```

- [ ] **Step 3: Commit**

```bash
git add cache/.gitkeep .gitignore
git commit -m "chore: add cache/ directory for runtime JSON storage"
```

---

## Task 2: Update `assignees.py` — new path and metadata wrapper

**Files:**
- Modify: `assignees.py`

The module must store `{"updated_at": "...", "items": [...]}` and expose the same `load_assignees() -> List[Dict]` / `save_assignees(users)` signatures so all callers are unchanged. A new `load_assignees_meta() -> dict` function returns the full wrapper (for the Cache Manager).

- [ ] **Step 1: Replace `assignees.py` with the updated version**

```python
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

_CACHE_FILE = Path(__file__).parent / "cache" / "assignees.json"


def load_assignees() -> List[Dict]:
    """Return cached assignee list, or [] if file missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception:
        return []


def load_assignees_meta() -> dict:
    """Return full cache wrapper {updated_at, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"updated_at": None, "items": []}


def save_assignees(users: List[Dict]) -> None:
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "items": users}, f, indent=2)
```

- [ ] **Step 2: Verify app still starts and loads assignees correctly**

Start the app:
```bash
FLASK_DEBUG=1 ./scripts/start.sh
```
Visit `/tools/` — should show assignee count or "No cache" with no errors in terminal.

- [ ] **Step 3: Commit**

```bash
git add assignees.py
git commit -m "refactor: move assignee cache to cache/ with metadata wrapper"
```

---

## Task 3: Update `labels.py` — new path and metadata wrapper

**Files:**
- Modify: `labels.py`

Same pattern as Task 2.

- [ ] **Step 1: Replace `labels.py` with the updated version**

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

_CACHE_FILE = Path(__file__).parent / "cache" / "labels.json"


def load_label_cache() -> List[str]:
    """Return cached label list, or [] if file missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception:
        return []


def load_label_cache_meta() -> dict:
    """Return full cache wrapper {updated_at, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"updated_at": None, "items": []}


def save_label_cache(labels: List[str]) -> None:
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "items": labels}, f, indent=2)
```

- [ ] **Step 2: Commit**

```bash
git add labels.py
git commit -m "refactor: move label cache to cache/ with metadata wrapper"
```

---

## Task 4: Create `projects.py` — project list cache

**Files:**
- Create: `projects.py`

- [ ] **Step 1: Create `projects.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

_CACHE_FILE = Path(__file__).parent / "cache" / "projects.json"


def load_projects() -> List[Dict]:
    """Return cached project list [{key, name}], or [] if file missing/corrupt."""
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception:
        return []


def load_projects_meta() -> dict:
    """Return full cache wrapper {updated_at, items}, or defaults if missing."""
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"updated_at": None, "items": []}


def save_projects(projects: List[Dict]) -> None:
    _CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "items": projects}, f, indent=2)
```

- [ ] **Step 2: Commit**

```bash
git add projects.py
git commit -m "feat: add projects cache module (cache/projects.json)"
```

---

## Task 5: Add `org_id` to `JiraConfig`

**Files:**
- Modify: `models.py`
- Modify: `config.py`

- [ ] **Step 1: Add `org_id` field to `JiraConfig` in `models.py`**

In `models.py`, the `JiraConfig` dataclass currently ends at `labels`. Add `org_id` after `proxy_url`:

Find:
```python
    proxy_url: str = ""
    labels: List[str] = field(default_factory=list)
```

Replace with:
```python
    proxy_url: str = ""
    org_id: str = ""
    labels: List[str] = field(default_factory=list)
```

In `JiraConfig.to_dict()`, find:
```python
            "proxy_url": self.proxy_url,
            "labels": self.labels,
```
Replace with:
```python
            "proxy_url": self.proxy_url,
            "org_id": self.org_id,
            "labels": self.labels,
```

In `JiraConfig.from_dict()`, find:
```python
            proxy_url=d.get("proxy_url", ""),
            labels=raw_labels,
```
Replace with:
```python
            proxy_url=d.get("proxy_url", ""),
            org_id=d.get("org_id", ""),
            labels=raw_labels,
```

- [ ] **Step 2: Commit**

```bash
git add models.py
git commit -m "feat: add org_id field to JiraConfig for Atlassian Teams API"
```

---

## Task 6: Add Atlassian Teams methods to `JiraClient`

**Files:**
- Modify: `jira_client.py`

The Atlassian Teams API is at `/gateway/api/public/teams/v1/org/{orgId}/teams` (not under `/rest/api/3`). It uses the same Basic auth credentials as the Jira API.

- [ ] **Step 1: Add `fetch_teams()` method to `JiraClient`**

In `jira_client.py`, add these two methods after `fetch_groups()` (around line 242):

```python
    def fetch_teams(self, query: str = "") -> Tuple[List[dict], Optional[str]]:
        """Search Atlassian Teams via GET /gateway/api/public/teams/v1/org/{orgId}/teams.

        Requires org_id to be set in JiraConfig. Returns ({teamId, displayName}, error).
        """
        if not self._org_id:
            return [], "Atlassian Org ID not configured — set it in Settings"
        try:
            resp = self.session.get(
                f"{self._teams_base}/teams",
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

    def fetch_team_members(self, team_id: str) -> Tuple[List[dict], Optional[str]]:
        """Fetch members of an Atlassian Team.

        GET /gateway/api/public/teams/v1/org/{orgId}/teams/{teamId}/members
        Returns [{accountId}] list. Members not in the assignee base pool are
        filtered out by the caller (intersection logic).
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
                resp = self.session.get(
                    f"{self._teams_base}/teams/{team_id}/members",
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
                if not cursor or not data.get("results"):
                    break
            log.info("fetch_team_members: team_id=%r → %d members", team_id, len(members))
            return members, None
        except requests.RequestException as exc:
            log.error("fetch_team_members exception: %s", exc)
            return [], str(exc)
```

- [ ] **Step 2: Add `_org_id` and `_teams_base` to `JiraClient.__init__`**

In `JiraClient.__init__`, after `self.api_base = ...`, add:

```python
        self._org_id: str = cfg.org_id
        self._teams_base = f"https://api.atlassian.com/gateway/api/public/teams/v1/org/{self._org_id}"
```

- [ ] **Step 3: Commit**

```bash
git add jira_client.py
git commit -m "feat: add fetch_teams and fetch_team_members to JiraClient"
```

---

## Task 7: Update `routes/tools.py` — project caching, teams endpoint, teams filter

**Files:**
- Modify: `routes/tools.py`

- [ ] **Step 1: Add `projects` import at the top of `routes/tools.py`**

Find:
```python
from assignees import load_assignees, save_assignees
from labels import load_label_cache, save_label_cache
```
Replace with:
```python
from assignees import load_assignees, save_assignees
from labels import load_label_cache, save_label_cache
from projects import load_projects, save_projects
```

- [ ] **Step 2: Pass `projects_cache` to the tools index template**

Find:
```python
def index():
    cfg = load_config()
    assignees = load_assignees()
    label_cache = load_label_cache()
    return render_template("tools/index.html", assignees=assignees, label_cache=label_cache, cfg=cfg)
```
Replace with:
```python
def index():
    cfg = load_config()
    assignees = load_assignees()
    label_cache = load_label_cache()
    projects_cache = load_projects()
    return render_template(
        "tools/index.html",
        assignees=assignees,
        label_cache=label_cache,
        projects_cache=projects_cache,
        cfg=cfg,
    )
```

- [ ] **Step 3: Save projects to cache in `/fetch-projects`**

Find:
```python
@bp.route("/fetch-projects", methods=["POST"])
def fetch_projects():
    """Return JSON list of {key, name} for all accessible Jira projects."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    client = JiraClient(cfg)
    projects, err = client.fetch_projects()
    if err:
        return jsonify({"error": err}), 502
    return jsonify(projects)
```
Replace with:
```python
@bp.route("/fetch-projects", methods=["POST"])
def fetch_projects():
    """Return JSON list of {key, name} for all accessible Jira projects."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    client = JiraClient(cfg)
    projects, err = client.fetch_projects()
    if err:
        return jsonify({"error": err}), 502
    save_projects(projects)
    log.info("fetch_projects: saved %d projects to cache", len(projects))
    return jsonify(projects)
```

- [ ] **Step 4: Add `/fetch-teams` endpoint**

After the `fetch_groups` route, add:

```python
@bp.route("/fetch-teams", methods=["POST"])
def fetch_teams():
    """Return JSON list of {teamId, displayName} for Atlassian Teams."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    if not cfg.org_id:
        return jsonify({"error": "Atlassian Org ID not configured — set it in Settings"}), 400
    query = request.form.get("query", "").strip()
    client = JiraClient(cfg)
    teams, err = client.fetch_teams(query=query)
    if err:
        return jsonify({"error": err}), 502
    return jsonify(teams)
```

- [ ] **Step 5: Add team filter step in `refresh_assignees`**

In `refresh_assignees`, after the group filter block (after line `log.info("refresh_assignees: after group filter → %d users"...)`), add:

```python
    # Step 4: intersect with Atlassian Team members if team selected
    team_id = request.form.get("filter_team_id", "").strip()
    if team_id:
        team_members, team_err = client.fetch_team_members(team_id)
        if team_err:
            flash(f"Warning: Could not fetch team members ({team_err}). Team filter skipped.", "warning")
        else:
            team_account_ids = {m["accountId"] for m in team_members}
            users = [u for u in users if u["accountId"] in team_account_ids]
            filters_applied = True
            log.info("refresh_assignees: after team filter → %d users", len(users))
```

- [ ] **Step 6: Commit**

```bash
git add routes/tools.py
git commit -m "feat: cache project list; add fetch-teams endpoint; add team filter to refresh-assignees"
```

---

## Task 8: Update `templates/tools/index.html` — pre-populated projects and Teams filter

**Files:**
- Modify: `templates/tools/index.html`

- [ ] **Step 1: Pre-populate project scope dropdown from cache**

Find the project scope select (the static `<select>` with a single default option):
```html
              <select id="project-scope-select" class="form-select form-select-sm">
                <option value="{{ cfg.project_key if cfg else '' }}" selected>
                  {{ cfg.project_key if cfg else '(not configured)' }} — configured default
                </option>
              </select>
```
Replace with:
```html
              <select id="project-scope-select" class="form-select form-select-sm">
                <option value="{{ cfg.project_key if cfg else '' }}" selected>
                  {{ cfg.project_key if cfg else '(not configured)' }} — configured default
                </option>
                {% for p in projects_cache %}
                  {% if p.key != (cfg.project_key if cfg else '') %}
                    <option value="{{ p.key }}">{{ p.key }} — {{ p.name }}</option>
                  {% endif %}
                {% endfor %}
              </select>
```

- [ ] **Step 2: Add Atlassian Team filter row after the Group filter**

Find the closing `</div>` of the group filter block (after `groups-load-error`):
```html
                <!-- Name/email query -->
```
Insert the team filter before it:
```html
                <!-- Atlassian Team filter -->
                <div class="mb-2">
                  <label class="form-label small fw-semibold mb-1">Atlassian Team</label>
                  {% if cfg and cfg.org_id %}
                  <div class="d-flex gap-2">
                    <select name="filter_team_id" id="team-select" class="form-select form-select-sm">
                      <option value="">— no team filter —</option>
                    </select>
                    <button type="button" id="load-teams-btn" class="btn btn-sm btn-outline-secondary text-nowrap">
                      Load Teams
                    </button>
                  </div>
                  <div id="teams-load-error" class="text-danger small mt-1" style="display:none;"></div>
                  {% else %}
                  <div class="text-muted small">
                    Requires <a href="{{ url_for('settings.index') }}">Atlassian Org ID</a> in Settings.
                  </div>
                  <input type="hidden" name="filter_team_id" value="">
                  {% endif %}
                </div>

                <!-- Name/email query -->
```

- [ ] **Step 3: Add Load Teams JS in the `{% block scripts %}` section**

In the `<script>` block at the bottom, after the `loadGroupsBtn` handler's closing `});`, add:

```javascript
  {% if cfg and cfg.org_id %}
  const teamSelect = document.getElementById('team-select');
  const loadTeamsBtn = document.getElementById('load-teams-btn');
  const teamsErrorDiv = document.getElementById('teams-load-error');

  loadTeamsBtn.addEventListener('click', function () {
    loadTeamsBtn.disabled = true;
    loadTeamsBtn.textContent = 'Loading\u2026';
    teamsErrorDiv.style.display = 'none';

    const body = new FormData();

    fetch('{{ url_for("tools.fetch_teams") }}', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: body,
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || r.statusText); });
        return r.json();
      })
      .then(function (teams) {
        if (teams.length === 0) {
          teamSelect.innerHTML = '<option value="">— no teams found —</option>';
        } else {
          teamSelect.innerHTML = '<option value="">— no team filter —</option>';
          teams.forEach(function (t) {
            const opt = document.createElement('option');
            opt.value = t.teamId;
            opt.textContent = t.displayName;
            teamSelect.appendChild(opt);
          });
        }
        loadTeamsBtn.textContent = 'Reload Teams';
      })
      .catch(function (err) {
        teamsErrorDiv.textContent = 'Failed to load teams: ' + err.message;
        teamsErrorDiv.style.display = 'block';
        loadTeamsBtn.textContent = 'Load Teams';
      })
      .finally(function () { loadTeamsBtn.disabled = false; });
  });
  {% endif %}
```

- [ ] **Step 4: Commit**

```bash
git add templates/tools/index.html
git commit -m "feat: pre-populate project dropdown from cache; add Atlassian Team filter UI"
```

---

## Task 9: Add Org ID field to Settings page

**Files:**
- Modify: `routes/settings.py`
- Modify: `templates/settings/index.html`

- [ ] **Step 1: Add `org_id` to the settings save route**

In `routes/settings.py`, in the `save()` function, find where `JiraConfig` is constructed from form fields (look for `proxy_url=request.form.get("proxy_url"...)`):

```python
        proxy_url=request.form.get("proxy_url", "").strip(),
```
Add `org_id` after it:
```python
        proxy_url=request.form.get("proxy_url", "").strip(),
        org_id=request.form.get("org_id", "").strip(),
```

Do the same in the `test_connection()` function where it also constructs a `JiraConfig` from form fields.

- [ ] **Step 2: Add `org_id` hidden field to the test form**

In `templates/settings/index.html`, the hidden test form has fields like `<input type="hidden" name="proxy_url" id="test_proxy_url">`. Add:
```html
          <input type="hidden" name="org_id" id="test_org_id">
```
And in the JS mirror block at the bottom:
```javascript
  document.getElementById('test_org_id').value = document.getElementById('org_id').value;
```

- [ ] **Step 3: Add Org ID input field to the settings form**

In `templates/settings/index.html`, after the proxy URL field (`<div class="mb-3">` block containing `proxy_url`), add:

```html
          <div class="mb-3">
            <label for="org_id" class="form-label fw-semibold">
              Atlassian Org ID <span class="text-muted fw-normal">(optional)</span>
            </label>
            <input type="text" name="org_id" id="org_id" class="form-control"
                   value="{{ cfg.org_id }}" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                   style="width:360px" maxlength="64">
            <div class="form-text">
              Required for the Atlassian Teams filter. Find it in
              <strong>admin.atlassian.com → Settings → Organization</strong> — the UUID in the URL.
            </div>
          </div>
```

- [ ] **Step 4: Commit**

```bash
git add routes/settings.py templates/settings/index.html
git commit -m "feat: add Atlassian Org ID field to Settings"
```

---

## Task 10: Create `routes/cache_manager.py` blueprint

**Files:**
- Create: `routes/cache_manager.py`

- [ ] **Step 1: Create the blueprint**

```python
import logging

from flask import Blueprint, jsonify, render_template, request

from assignees import load_assignees_meta, save_assignees
from labels import load_label_cache_meta, save_label_cache
from projects import load_projects_meta, save_projects

log = logging.getLogger(__name__)

bp = Blueprint("cache_manager", __name__, url_prefix="/cache")

_CACHE_TYPES = {"assignees", "labels", "projects"}


def _load_all_meta() -> dict:
    return {
        "assignees": load_assignees_meta(),
        "labels": load_label_cache_meta(),
        "projects": load_projects_meta(),
    }


@bp.route("/")
def index():
    return render_template("cache_manager/index.html", caches=_load_all_meta())


@bp.route("/delete/<cache_type>/<path:item_id>", methods=["POST"])
def delete_item(cache_type: str, item_id: str):
    """Remove a single entry from a cache. Returns JSON {ok: true} or {error: ...}."""
    if cache_type not in _CACHE_TYPES:
        return jsonify({"error": "Unknown cache type"}), 400

    if cache_type == "assignees":
        meta = load_assignees_meta()
        meta["items"] = [u for u in meta.get("items", []) if u.get("accountId") != item_id]
        save_assignees(meta["items"])
    elif cache_type == "labels":
        meta = load_label_cache_meta()
        meta["items"] = [lbl for lbl in meta.get("items", []) if lbl != item_id]
        save_label_cache(meta["items"])
    elif cache_type == "projects":
        meta = load_projects_meta()
        meta["items"] = [p for p in meta.get("items", []) if p.get("key") != item_id]
        save_projects(meta["items"])

    log.info("cache_manager: deleted %s/%s", cache_type, item_id)
    return jsonify({"ok": True})


@bp.route("/clear/<cache_type>", methods=["POST"])
def clear_cache(cache_type: str):
    """Wipe an entire cache. Returns JSON {ok: true} or {error: ...}."""
    if cache_type not in _CACHE_TYPES:
        return jsonify({"error": "Unknown cache type"}), 400

    if cache_type == "assignees":
        save_assignees([])
    elif cache_type == "labels":
        save_label_cache([])
    elif cache_type == "projects":
        save_projects([])

    log.info("cache_manager: cleared %s", cache_type)
    return jsonify({"ok": True})
```

- [ ] **Step 2: Commit**

```bash
git add routes/cache_manager.py
git commit -m "feat: add cache_manager blueprint with delete and clear routes"
```

---

## Task 11: Register `cache_manager` blueprint and add navbar link

**Files:**
- Modify: `routes/__init__.py`
- Modify: `templates/base.html`

- [ ] **Step 1: Register the blueprint in `routes/__init__.py`**

Find:
```python
    from routes.settings import bp as settings_bp
    from routes.tools import bp as tools_bp
```
Add the import:
```python
    from routes.cache_manager import bp as cache_manager_bp
```
And register it:
```python
    app.register_blueprint(cache_manager_bp)
```

- [ ] **Step 2: Add "Cache" nav item to `templates/base.html`**

Find the existing "Jira Tools" nav item:
```html
        <li class="nav-item">
          <a class="nav-link {% if request.path.startswith('/tools') %}active{% endif %}"
             href="{{ url_for('tools.index') }}">Jira Tools</a>
        </li>
```
Add the Cache link immediately after it:
```html
        <li class="nav-item">
          <a class="nav-link {% if request.path.startswith('/cache') %}active{% endif %}"
             href="{{ url_for('cache_manager.index') }}">Cache</a>
        </li>
```

- [ ] **Step 3: Commit**

```bash
git add routes/__init__.py templates/base.html
git commit -m "feat: register cache_manager blueprint and add Cache nav link"
```

---

## Task 12: Create `templates/cache_manager/index.html`

**Files:**
- Create: `templates/cache_manager/index.html`

- [ ] **Step 1: Create the template directory and file**

```bash
mkdir -p templates/cache_manager
```

- [ ] **Step 2: Write the template**

```html
{% extends "base.html" %}
{% block title %}Cache Manager | JiraMaster{% endblock %}

{% block content %}
<h2 class="mb-1">Cache Manager</h2>
<p class="text-muted mb-4">View and manage locally cached data fetched from Jira.</p>

{% set cache_defs = [
  ('assignees', 'Assignees', caches.assignees, 'accountId', ['Display Name', 'Email', 'Account ID']),
  ('labels',    'Labels',    caches.labels,    None,         ['Label']),
  ('projects',  'Projects',  caches.projects,  'key',        ['Key', 'Name']),
] %}

{% for cache_type, title, meta, id_field, columns in cache_defs %}
<div class="card mb-3">
  <div class="card-header d-flex justify-content-between align-items-center">
    <button class="btn btn-link fw-semibold text-decoration-none p-0"
            data-bs-toggle="collapse" data-bs-target="#collapse-{{ cache_type }}">
      {{ title }}
      <span class="badge bg-secondary ms-2">{{ meta.items | length }}</span>
    </button>
    <div class="d-flex align-items-center gap-3">
      {% if meta.updated_at %}
        <span class="small text-muted">Updated: {{ meta.updated_at[:19] | replace('T', ' ') }} UTC</span>
      {% else %}
        <span class="small text-muted">No cache</span>
      {% endif %}
      <button class="btn btn-sm btn-outline-danger clear-all-btn" data-cache-type="{{ cache_type }}"
              {% if not meta.items %}disabled{% endif %}>
        Clear all
      </button>
    </div>
  </div>
  <div class="collapse show" id="collapse-{{ cache_type }}">
    <div class="card-body p-0">
      {% if meta.items %}
      <div class="table-responsive">
        <table class="table table-sm table-hover mb-0">
          <thead class="table-light">
            <tr>
              {% for col in columns %}<th class="ps-3">{{ col }}</th>{% endfor %}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {% if cache_type == 'assignees' %}
              {% for item in meta.items %}
              <tr data-item-id="{{ item.accountId }}">
                <td class="ps-3">{{ item.displayName or '—' }}</td>
                <td>{{ item.emailAddress or '—' }}</td>
                <td class="text-muted small">{{ item.accountId }}</td>
                <td class="text-end pe-3">
                  <button class="btn btn-sm btn-outline-danger delete-btn"
                          data-cache-type="{{ cache_type }}"
                          data-item-id="{{ item.accountId }}">Delete</button>
                </td>
              </tr>
              {% endfor %}
            {% elif cache_type == 'labels' %}
              {% for item in meta.items %}
              <tr data-item-id="{{ item }}">
                <td class="ps-3">{{ item }}</td>
                <td class="text-end pe-3">
                  <button class="btn btn-sm btn-outline-danger delete-btn"
                          data-cache-type="{{ cache_type }}"
                          data-item-id="{{ item }}">Delete</button>
                </td>
              </tr>
              {% endfor %}
            {% elif cache_type == 'projects' %}
              {% for item in meta.items %}
              <tr data-item-id="{{ item.key }}">
                <td class="ps-3 fw-semibold">{{ item.key }}</td>
                <td>{{ item.name }}</td>
                <td class="text-end pe-3">
                  <button class="btn btn-sm btn-outline-danger delete-btn"
                          data-cache-type="{{ cache_type }}"
                          data-item-id="{{ item.key }}">Delete</button>
                </td>
              </tr>
              {% endfor %}
            {% endif %}
          </tbody>
        </table>
      </div>
      {% else %}
        <p class="text-muted small p-3 mb-0">No cached data. Use <a href="{{ url_for('tools.index') }}">Jira Tools</a> to fetch from Jira.</p>
      {% endif %}
    </div>
  </div>
</div>
{% endfor %}
{% endblock %}

{% block scripts %}
<script>
(function () {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  // Flask-WTF doesn't inject a meta tag by default — grab it from any form on the page or use fetch with the cookie
  // We'll use the X-CSRFToken header pattern: get the token from a hidden input on a dummy form
  const csrfToken = '{{ csrf_token() }}';

  function fadeRemoveRow(row) {
    row.style.transition = 'opacity 0.3s';
    row.style.opacity = '0';
    setTimeout(function () { row.remove(); }, 320);
  }

  function showError(btn, msg) {
    const existing = btn.parentElement.querySelector('.inline-err');
    if (existing) existing.remove();
    const span = document.createElement('span');
    span.className = 'inline-err text-danger small ms-2';
    span.textContent = msg;
    btn.parentElement.appendChild(span);
  }

  document.querySelectorAll('.delete-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const cacheType = btn.dataset.cacheType;
      const itemId = btn.dataset.itemId;
      btn.disabled = true;

      fetch('/cache/delete/' + cacheType + '/' + encodeURIComponent(itemId), {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            const row = btn.closest('tr');
            fadeRemoveRow(row);
          } else {
            showError(btn, data.error || 'Failed');
            btn.disabled = false;
          }
        })
        .catch(function (err) {
          showError(btn, err.message);
          btn.disabled = false;
        });
    });
  });

  document.querySelectorAll('.clear-all-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const cacheType = btn.dataset.cacheType;
      if (!confirm('Clear all ' + cacheType + ' from cache?')) return;
      btn.disabled = true;

      fetch('/cache/clear/' + cacheType, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            const card = btn.closest('.card');
            const tbody = card.querySelector('tbody');
            if (tbody) {
              Array.from(tbody.querySelectorAll('tr')).forEach(function (row) {
                fadeRemoveRow(row);
              });
            }
            const badge = card.querySelector('.badge');
            if (badge) badge.textContent = '0';
          } else {
            btn.disabled = false;
          }
        })
        .catch(function () { btn.disabled = false; });
    });
  });
})();
</script>
{% endblock %}
```

- [ ] **Step 3: Verify the page renders correctly**

Start the app and visit `/cache/` — should show three sections (Assignees, Labels, Projects) with row counts and timestamps.

- [ ] **Step 4: Commit**

```bash
git add templates/cache_manager/
git commit -m "feat: add Cache Manager page with per-item and bulk delete"
```

---

## Task 13: Final smoke test and push

- [ ] **Step 1: Full manual smoke test**

1. Visit `/settings` — confirm "Atlassian Org ID" field is present, save with a test value
2. Visit `/tools` — confirm project dropdown is pre-populated if `cache/projects.json` exists
3. Click "Load Projects" — confirm dropdown populates and `cache/projects.json` is created
4. Click "Load Roles", select a role, click "Refresh Assignees" — confirm works as before
5. Click "Load Groups", select a group, click "Refresh Assignees" — confirm group filter works
6. If Org ID configured: click "Load Teams", select a team, click "Refresh Assignees"
7. Visit `/cache` — confirm all three sections show correct data
8. Delete an assignee entry — row should fade out
9. Clear all labels — all rows should fade out

- [ ] **Step 2: Confirm `cache/` files are NOT staged by git**

```bash
git status
```
Expected: no `cache/*.json` files in staged or unstaged changes.

- [ ] **Step 3: Push**

```bash
git push
```

---

## Self-Review Notes

- **Spec coverage:** All four spec sections are covered: cache dir (Tasks 1-4), project cache (Tasks 4, 7, 8), Atlassian Teams (Tasks 5-6, 8-9), Cache Manager (Tasks 10-12).
- **Type consistency:** `load_assignees_meta()`, `load_label_cache_meta()`, `load_projects_meta()` all return `{updated_at, items}`. `save_*` functions all accept the `items` list directly and wrap internally. Consistent across all tasks.
- **`save_assignees` in cache_manager.py**: The route calls `save_assignees(meta["items"])` after mutating — this correctly calls the module's `save_assignees(users: List[Dict])` defined in Task 2. ✓
- **CSRF on AJAX deletes**: The template injects `csrf_token()` directly into JS — matches pattern used in `tools/index.html`. ✓
- **Atlassian Teams API pagination**: Uses `nextCursor` pattern as documented; falls back gracefully if the field is missing. ✓
