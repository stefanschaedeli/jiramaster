# Assignee Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add role/group/query/maxResults filters to the Tools page assignee refresh, plus live search in the Edit step dropdowns.

**Architecture:** Three new `JiraClient` methods fetch project roles, role members, and group members; the `refresh_assignees` route applies AND-intersection logic across active filters before saving to cache; the Edit step gets a vanilla JS search input above each assignee dropdown.

**Tech Stack:** Python/Flask, Jinja2, Bootstrap 5.3, vanilla JS, Jira Cloud REST API v3

---

## File Map

| File | What changes |
|------|-------------|
| `jira_client.py` | Add `fetch_project_roles()`, `fetch_role_members()`, `fetch_group_members()`; add `query` param to `fetch_assignees()` |
| `routes/tools.py` | Update `refresh_assignees` to read + apply filters; add `fetch_roles` AJAX endpoint |
| `templates/tools/index.html` | Add collapsible Filter Options section + Load Roles JS |
| `templates/edit/index.html` | Add search input above each assignee `<select>` + JS filter function |

---

## Task 1: Add `query` param to `fetch_assignees()` in `jira_client.py`

**Files:**
- Modify: `jira_client.py:130-160`

- [ ] **Step 1: Update the method signature and params dict**

Replace the `fetch_assignees` method (lines 130–160) with:

```python
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
        resp = self.session.get(
            self._url("user/assignable/search"),
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
```

- [ ] **Step 2: Commit**

```bash
git add jira_client.py
git commit -m "feat: add query param to fetch_assignees, raise default max_results to 50"
```

---

## Task 2: Add `fetch_project_roles()` to `jira_client.py`

**Files:**
- Modify: `jira_client.py` (add after `fetch_assignees`)

- [ ] **Step 1: Add the method**

Insert after the `fetch_assignees` method (after line ~160):

```python
def fetch_project_roles(self, project_key: Optional[str] = None) -> Tuple[List[dict], Optional[str]]:
    """Fetch all roles for a project via GET /project/{key}/role.

    Returns (roles, error_message). roles is a list of {id: int, name: str}.
    """
    effective_project = project_key or self.project_key
    try:
        resp = self.session.get(
            self._url(f"project/{effective_project}/role"),
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
```

- [ ] **Step 2: Commit**

```bash
git add jira_client.py
git commit -m "feat: add fetch_project_roles() to JiraClient"
```

---

## Task 3: Add `fetch_role_members()` to `jira_client.py`

**Files:**
- Modify: `jira_client.py` (add after `fetch_project_roles`)

- [ ] **Step 1: Add the method**

```python
def fetch_role_members(self, role_id: int, project_key: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
    """Fetch accountIds of all members in a project role.

    GET /project/{key}/role/{id} returns actors; extracts accountId for each user actor.
    Returns (account_ids, error_message). account_ids is [] on failure.
    """
    effective_project = project_key or self.project_key
    try:
        resp = self.session.get(
            self._url(f"project/{effective_project}/role/{role_id}"),
            timeout=10,
        )
        if resp.status_code != 200:
            return [], self._log_error("fetch_role_members", resp)
        actors = resp.json().get("actors", [])
        account_ids = [
            a["actorUser"]["accountId"]
            for a in actors
            if a.get("type") == "atlassian-user-role-actor" and a.get("actorUser", {}).get("accountId")
        ]
        log.info("fetch_role_members: role_id=%d → %d members", role_id, len(account_ids))
        return account_ids, None
    except requests.RequestException as exc:
        log.error("fetch_role_members exception: %s", exc)
        return [], str(exc)
```

- [ ] **Step 2: Commit**

```bash
git add jira_client.py
git commit -m "feat: add fetch_role_members() to JiraClient"
```

---

## Task 4: Add `fetch_group_members()` to `jira_client.py`

**Files:**
- Modify: `jira_client.py` (add after `fetch_role_members`)

- [ ] **Step 1: Add the method**

```python
def fetch_group_members(self, group_name: str, max_results: int = 200) -> Tuple[List[dict], Optional[str]]:
    """Fetch members of a Jira group via GET /group/member.

    Returns (users, error_message). users is [{accountId, displayName, emailAddress}].
    Paginates automatically up to max_results total members.
    """
    try:
        users: List[dict] = []
        start_at = 0
        while True:
            resp = self.session.get(
                self._url("group/member"),
                params={
                    "groupname": group_name,
                    "startAt": start_at,
                    "maxResults": min(50, max_results - len(users)),
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
            if not page or data.get("isLast", True) or len(users) >= max_results:
                break
            start_at += len(page)
        log.info("fetch_group_members: group=%r → %d members", group_name, len(users))
        return users[:max_results], None
    except requests.RequestException as exc:
        log.error("fetch_group_members exception: %s", exc)
        return [], str(exc)
```

- [ ] **Step 2: Commit**

```bash
git add jira_client.py
git commit -m "feat: add fetch_group_members() to JiraClient"
```

---

## Task 5: Add `fetch_roles` AJAX endpoint to `routes/tools.py`

**Files:**
- Modify: `routes/tools.py`

- [ ] **Step 1: Add the endpoint after `fetch_projects`**

Insert after the `fetch_projects` route (after line 50):

```python
@bp.route("/fetch-roles", methods=["POST"])
def fetch_roles():
    """Return JSON list of {id, name} for all roles in the given project."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    project_scope = request.form.get("project_scope", "").strip().upper() or None
    client = JiraClient(cfg)
    roles, err = client.fetch_project_roles(project_key=project_scope)
    if err:
        return jsonify({"error": err}), 502
    return jsonify(roles)
```

- [ ] **Step 2: Commit**

```bash
git add routes/tools.py
git commit -m "feat: add /tools/fetch-roles AJAX endpoint"
```

---

## Task 6: Update `refresh_assignees` route to apply filters

**Files:**
- Modify: `routes/tools.py:22-37`

- [ ] **Step 1: Replace the `refresh_assignees` handler**

Replace the entire `refresh_assignees` function:

```python
@bp.route("/refresh-assignees", methods=["POST"])
def refresh_assignees():
    cfg = load_config()
    if not cfg.is_configured():
        flash("Configure Jira settings first.", "warning")
        return redirect(url_for("settings.index"))

    project_scope = request.form.get("project_scope", "").strip().upper() or None
    role_id_raw = request.form.get("filter_role_id", "").strip()
    group_name = request.form.get("filter_group_name", "").strip()
    query = request.form.get("filter_query", "").strip() or None
    max_results_raw = request.form.get("filter_max_results", "50").strip()

    try:
        max_results = max(10, min(200, int(max_results_raw)))
    except ValueError:
        max_results = 50

    client = JiraClient(cfg)

    # Step 1: base pool from assignable search
    users, err = client.fetch_assignees(project_key=project_scope, query=query, max_results=max_results)
    if err:
        flash(f"Failed to fetch assignees: {err}", "danger")
        return redirect(url_for("tools.index"))

    # Step 2: intersect with role members if role selected
    if role_id_raw:
        try:
            role_id = int(role_id_raw)
        except ValueError:
            role_id = None
        if role_id is not None:
            role_ids, role_err = client.fetch_role_members(role_id, project_key=project_scope)
            if role_err:
                flash(f"Warning: Could not fetch role members ({role_err}). Role filter skipped.", "warning")
            else:
                role_set = set(role_ids)
                users = [u for u in users if u["accountId"] in role_set]
                log.info("refresh_assignees: after role filter → %d users", len(users))

    # Step 3: intersect with group members if group provided
    if group_name:
        group_users, group_err = client.fetch_group_members(group_name)
        if group_err:
            flash(f"Warning: Could not fetch group '{group_name}' ({group_err}). Group filter skipped.", "warning")
        else:
            group_ids = {u["accountId"] for u in group_users}
            users = [u for u in users if u["accountId"] in group_ids]
            log.info("refresh_assignees: after group filter → %d users", len(users))

    # Guard: don't wipe cache if all filters combined yielded nothing
    if not users and (role_id_raw or group_name or query):
        flash("All filters combined returned 0 users — cache not updated. Relax your filters and try again.", "warning")
        return redirect(url_for("tools.index"))

    save_assignees(users)
    label = project_scope or cfg.project_key
    flash(f"Fetched {len(users)} assignees from {label} and saved to assignees.json.", "success")
    return redirect(url_for("tools.index"))
```

- [ ] **Step 2: Commit**

```bash
git add routes/tools.py
git commit -m "feat: apply role/group/query/maxResults filters in refresh_assignees route"
```

---

## Task 7: Add Filter Options UI to `templates/tools/index.html`

**Files:**
- Modify: `templates/tools/index.html`

- [ ] **Step 1: Replace the entire file**

```html
{% extends "base.html" %}
{% block title %}Jira Tools | JiraMaster{% endblock %}

{% block content %}
<h2 class="mb-1">Jira Tools</h2>
<p class="text-muted mb-4">Useful utilities for managing your Jira project data.</p>

<div class="row g-4">
  <div class="col-md-6">
    <div class="card h-100">
      <div class="card-header fw-semibold">Refresh Assignees</div>
      <div class="card-body d-flex flex-column">
        <p class="card-text">Download and cache the list of assignable users from a Jira project. Use the scope selector to fetch from a different project.</p>
        <div class="mb-3">
          {% if assignees %}
            <span class="text-success">✓</span>
            <span class="small text-muted">{{ assignees|length }} users cached</span>
          {% else %}
            <span class="text-muted small">No cache — click Refresh to fetch from Jira</span>
          {% endif %}
        </div>

        <form method="POST" action="{{ url_for('tools.refresh_assignees') }}" id="refresh-assignees-form">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <input type="hidden" name="project_scope" id="project-scope-hidden" value="">

          <!-- Project scope -->
          <div class="mb-3">
            <label for="project-scope-select" class="form-label small fw-semibold">Fetch scope</label>
            <div class="d-flex gap-2">
              <select id="project-scope-select" class="form-select form-select-sm">
                <option value="{{ cfg.project_key if cfg else '' }}" selected>
                  {{ cfg.project_key if cfg else '(not configured)' }} — configured default
                </option>
              </select>
              <button type="button" id="load-projects-btn" class="btn btn-sm btn-outline-secondary text-nowrap">
                Load Projects
              </button>
            </div>
            <div id="projects-load-error" class="text-danger small mt-1" style="display:none;"></div>
          </div>

          <!-- Filter Options (collapsible) -->
          <div class="mb-3">
            <a class="small text-muted text-decoration-none" data-bs-toggle="collapse" href="#assignee-filters" role="button" aria-expanded="false" aria-controls="assignee-filters">
              ▶ Filter Options
            </a>
            <div class="collapse mt-2" id="assignee-filters">
              <div class="border rounded p-3 bg-light">

                <!-- Role filter -->
                <div class="mb-2">
                  <label class="form-label small fw-semibold mb-1">Project Role</label>
                  <div class="d-flex gap-2">
                    <select name="filter_role_id" id="role-select" class="form-select form-select-sm">
                      <option value="">— no role filter —</option>
                    </select>
                    <button type="button" id="load-roles-btn" class="btn btn-sm btn-outline-secondary text-nowrap">
                      Load Roles
                    </button>
                  </div>
                  <div id="roles-load-error" class="text-danger small mt-1" style="display:none;"></div>
                </div>

                <!-- Group filter -->
                <div class="mb-2">
                  <label class="form-label small fw-semibold mb-1">Group Name</label>
                  <input type="text" name="filter_group_name" class="form-control form-control-sm"
                         placeholder="Exact Jira group name (case-sensitive)">
                </div>

                <!-- Name/email query -->
                <div class="mb-2">
                  <label class="form-label small fw-semibold mb-1">Name / Email Filter</label>
                  <input type="text" name="filter_query" class="form-control form-control-sm"
                         placeholder="Partial name or email address">
                </div>

                <!-- Max results -->
                <div>
                  <label class="form-label small fw-semibold mb-1">Max Results</label>
                  <input type="number" name="filter_max_results" class="form-control form-control-sm"
                         value="50" min="10" max="200" style="width:90px;">
                  <div class="form-text">10–200. Filters apply AND logic — all active filters must match.</div>
                </div>

              </div>
            </div>
          </div>

          <div class="mt-auto">
            <button type="submit" class="btn btn-outline-primary">Refresh Assignees</button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <div class="col-md-6">
    <div class="card h-100">
      <div class="card-header fw-semibold">Refresh Labels</div>
      <div class="card-body d-flex flex-column">
        <p class="card-text">Download and cache the most-used labels from your Jira project. Used to populate the label selector when editing issues.</p>
        <div class="mb-3">
          {% if label_cache %}
            <span class="text-success">✓</span>
            <span class="small text-muted">{{ label_cache|length }} labels cached</span>
          {% else %}
            <span class="text-muted small">No cache — click Refresh to fetch from Jira</span>
          {% endif %}
        </div>
        <form method="POST" action="{{ url_for('tools.refresh_labels') }}" class="mt-auto">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <button type="submit" class="btn btn-outline-primary">Refresh Labels</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
(function () {
  const projectSelect = document.getElementById('project-scope-select');
  const loadProjectsBtn = document.getElementById('load-projects-btn');
  const projectHidden = document.getElementById('project-scope-hidden');
  const projectsErrorDiv = document.getElementById('projects-load-error');

  const roleSelect = document.getElementById('role-select');
  const loadRolesBtn = document.getElementById('load-roles-btn');
  const rolesErrorDiv = document.getElementById('roles-load-error');

  const csrfToken = document.querySelector('#refresh-assignees-form input[name="csrf_token"]').value;

  projectSelect.addEventListener('change', function () {
    projectHidden.value = projectSelect.value;
    // Reset roles when project changes
    roleSelect.innerHTML = '<option value="">— no role filter —</option>';
  });

  loadProjectsBtn.addEventListener('click', function () {
    loadProjectsBtn.disabled = true;
    loadProjectsBtn.textContent = 'Loading\u2026';
    projectsErrorDiv.style.display = 'none';

    fetch('{{ url_for("tools.fetch_projects") }}', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || r.statusText); });
        return r.json();
      })
      .then(function (projects) {
        projectSelect.innerHTML = '';
        if (projects.length === 0) {
          projectSelect.innerHTML = '<option value="">No accessible projects found</option>';
        } else {
          projects.forEach(function (p) {
            const opt = document.createElement('option');
            opt.value = p.key;
            opt.textContent = p.key + ' \u2014 ' + p.name;
            projectSelect.appendChild(opt);
          });
          projectHidden.value = projectSelect.value;
        }
        loadProjectsBtn.textContent = 'Reload Projects';
        // Reset roles when projects reload
        roleSelect.innerHTML = '<option value="">— no role filter —</option>';
      })
      .catch(function (err) {
        projectsErrorDiv.textContent = 'Failed to load projects: ' + err.message;
        projectsErrorDiv.style.display = 'block';
        loadProjectsBtn.textContent = 'Load Projects';
      })
      .finally(function () { loadProjectsBtn.disabled = false; });
  });

  loadRolesBtn.addEventListener('click', function () {
    loadRolesBtn.disabled = true;
    loadRolesBtn.textContent = 'Loading\u2026';
    rolesErrorDiv.style.display = 'none';

    const body = new FormData();
    body.append('project_scope', projectHidden.value || projectSelect.value);

    fetch('{{ url_for("tools.fetch_roles") }}', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: body,
    })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || r.statusText); });
        return r.json();
      })
      .then(function (roles) {
        roleSelect.innerHTML = '<option value="">— no role filter —</option>';
        if (roles.length === 0) {
          rolesErrorDiv.textContent = 'No roles found for this project.';
          rolesErrorDiv.style.display = 'block';
        } else {
          roles.forEach(function (role) {
            const opt = document.createElement('option');
            opt.value = role.id;
            opt.textContent = role.name;
            roleSelect.appendChild(opt);
          });
        }
        loadRolesBtn.textContent = 'Reload Roles';
      })
      .catch(function (err) {
        rolesErrorDiv.textContent = 'Failed to load roles: ' + err.message;
        rolesErrorDiv.style.display = 'block';
        loadRolesBtn.textContent = 'Load Roles';
      })
      .finally(function () { loadRolesBtn.disabled = false; });
  });
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/tools/index.html
git commit -m "feat: add collapsible Filter Options UI with role/group/query/maxResults to Tools page"
```

---

## Task 8: Add live search above assignee dropdowns in `templates/edit/index.html`

**Files:**
- Modify: `templates/edit/index.html`

- [ ] **Step 1: Add search input above the epic assignee `<select>`**

In the epic assignee block (around line 54-68), replace:

```html
            <div class="col-md-4">
              <label class="form-label fw-semibold">Assignee</label>
              <select name="epic_{{ i }}_assignee" class="form-select">
                <option value="">— unassigned —</option>
                {% for u in assignees %}
                  <option value="{{ u.displayName }}"
                    {% if epic.assignee == u.displayName or epic.assignee == u.emailAddress %}selected{% endif %}>
                    {{ u.displayName }}{% if u.emailAddress %} ({{ u.emailAddress }}){% endif %}
                  </option>
                {% endfor %}
              </select>
              {% if not assignees %}
              <div class="form-text text-warning">No assignees cached — go to Settings → Refresh Assignees</div>
              {% endif %}
            </div>
```

With:

```html
            <div class="col-md-4">
              <label class="form-label fw-semibold">Assignee</label>
              {% if assignees %}
              <input type="text" class="form-control form-control-sm mb-1 assignee-search"
                     placeholder="Search assignees…" autocomplete="off">
              {% endif %}
              <select name="epic_{{ i }}_assignee" class="form-select assignee-select">
                <option value="">— unassigned —</option>
                {% for u in assignees %}
                  <option value="{{ u.displayName }}"
                    {% if epic.assignee == u.displayName or epic.assignee == u.emailAddress %}selected{% endif %}>
                    {{ u.displayName }}{% if u.emailAddress %} ({{ u.emailAddress }}){% endif %}
                  </option>
                {% endfor %}
              </select>
              {% if not assignees %}
              <div class="form-text text-warning">No assignees cached — go to <a href="{{ url_for('tools.index') }}">Jira Tools</a> → Refresh Assignees</div>
              {% endif %}
            </div>
```

- [ ] **Step 2: Add search input above the story assignee `<select>`**

In the story assignee block (around line 133-147), replace:

```html
              <div class="col-md-4">
                <label class="form-label small fw-semibold">Assignee</label>
                <select name="story_{{ i }}_{{ j }}_assignee" class="form-select form-select-sm">
                  <option value="">— unassigned —</option>
                  {% for u in assignees %}
                    <option value="{{ u.displayName }}"
                      {% if story.assignee == u.displayName or story.assignee == u.emailAddress %}selected{% endif %}>
                      {{ u.displayName }}{% if u.emailAddress %} ({{ u.emailAddress }}){% endif %}
                    </option>
                  {% endfor %}
                </select>
                {% if not assignees %}
                <div class="form-text text-warning">No assignees cached — go to Settings → Refresh Assignees</div>
                {% endif %}
              </div>
```

With:

```html
              <div class="col-md-4">
                <label class="form-label small fw-semibold">Assignee</label>
                {% if assignees %}
                <input type="text" class="form-control form-control-sm mb-1 assignee-search"
                       placeholder="Search assignees…" autocomplete="off">
                {% endif %}
                <select name="story_{{ i }}_{{ j }}_assignee" class="form-select form-select-sm assignee-select">
                  <option value="">— unassigned —</option>
                  {% for u in assignees %}
                    <option value="{{ u.displayName }}"
                      {% if story.assignee == u.displayName or story.assignee == u.emailAddress %}selected{% endif %}>
                      {{ u.displayName }}{% if u.emailAddress %} ({{ u.emailAddress }}){% endif %}
                    </option>
                  {% endfor %}
                </select>
                {% if not assignees %}
                <div class="form-text text-warning">No assignees cached — go to <a href="{{ url_for('tools.index') }}">Jira Tools</a> → Refresh Assignees</div>
                {% endif %}
              </div>
```

- [ ] **Step 3: Add the JS search function in the `{% block scripts %}` section**

In `{% block scripts %}`, add after the closing `});` of the existing `epicSelect.addEventListener` block, before the final `})();`:

```javascript
  // Live search filter for assignee dropdowns
  function initAssigneeSearch(searchInput) {
    var select = searchInput.nextElementSibling;
    searchInput.addEventListener('input', function () {
      var term = searchInput.value.toLowerCase();
      Array.prototype.forEach.call(select.options, function (opt) {
        if (opt.value === '') { return; } // always show "— unassigned —"
        opt.style.display = opt.textContent.toLowerCase().indexOf(term) !== -1 ? '' : 'none';
      });
    });
  }
  document.querySelectorAll('.assignee-search').forEach(initAssigneeSearch);
```

- [ ] **Step 4: Commit**

```bash
git add templates/edit/index.html
git commit -m "feat: add live search input above assignee dropdowns in Edit step"
```

---

## Task 9: Final verification

- [ ] **Step 1: Start the app**

```bash
./start.sh
```

Open http://127.0.0.1:5000

- [ ] **Step 2: Verify Tools page filter UI**

Navigate to Jira Tools. Confirm:
- "Filter Options" link is visible, collapsed by default
- Expanding shows Role dropdown, Group Name input, Name/Email filter, Max Results input
- "Load Roles" button works (requires configured Jira) — populates role dropdown
- Role dropdown resets when project scope changes

- [ ] **Step 3: Verify role filter at fetch time**

Select a project role, click Refresh Assignees. Confirm:
- Flash message shows reduced count
- `cat assignees.json | python3 -m json.tool | grep accountId | wc -l` shows fewer entries than without filter

- [ ] **Step 4: Verify empty-result guard**

Select a role that has no members (or a nonexistent group name), click Refresh. Confirm:
- Warning flash: "All filters combined returned 0 users — cache not updated"
- `assignees.json` is unchanged

- [ ] **Step 5: Verify no-filter behavior**

Submit refresh with all filter fields empty. Confirm:
- Behavior identical to before this feature — no regressions

- [ ] **Step 6: Verify live search in Edit step**

Go to Edit step (requires a parsed work item). Confirm:
- Search input appears above each assignee `<select>`
- Typing partial name hides non-matching options in real time
- "— unassigned —" option is always visible regardless of search term
- Cascade (epic assignee → stories) still works

- [ ] **Step 7: Push**

```bash
git push
```
