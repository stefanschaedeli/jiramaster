# Design: README End-to-End Update (v1.8.0)

**Date:** 2026-03-31
**Status:** Approved
**Approach:** Parallel — scripts + README updated together, then scripts run to produce assets, all land in one commit.

---

## Context

JiraMaster has grown significantly since the README and docs were last updated. Two new pages exist (Landing Page `/`, Cache Manager `/cache`), a new module (`work_store.py`) was added, the cache storage structure moved to a `cache/` subdirectory, and major security hardening was shipped in v1.8.0. The README still references v1.7.0 and has no mention of the landing page or cache manager. Screenshots and architecture diagrams need to be regenerated to match the current UI.

---

## 1. Screenshot Filenames

Renumber to insert `00_home` at the front and add `08_cache` at the end. Existing `01`–`07` slots are unchanged.

| Filename | Page | Notes |
|---|---|---|
| `00_home.png` | Landing page (`/`) | New |
| `01_prompt.png` | Step 1 — Prompt Builder | Existing, retake |
| `02_import.png` | Step 2a — Import | Existing, retake |
| `03_import_view.png` | Step 2b — Review Import | Existing, retake |
| `04_edit.png` | Step 3 — Edit | Existing, retake |
| `05_upload_preview.png` | Step 4 — Upload Preview | Existing, retake |
| `06_settings.png` | Settings | Existing, retake |
| `07_tools.png` | Jira Tools | Existing, retake |
| `08_cache.png` | Cache Manager | New |

Old files not in this list are deleted (none — all existing files are retaken under same names).

---

## 2. `docs/take_screenshots.py` Changes

### New pages to add
- `("00_home", f"{base}/", "Home — Landing Page")` — no session needed, simple GET
- `("08_cache", f"{base}/cache/", "Cache Manager")` — needs fake cache data to render with content

### Fake cache data
Write minimal `cache/assignees.json` and `cache/labels.json` so the Cache Manager page shows populated content instead of empty state:

```python
FAKE_CACHE_ASSIGNEES = '''{
  "updated_at": "2026-03-31T10:00:00+00:00",
  "items": [
    {"account_id": "abc1", "display_name": "Alice Johnson", "emailAddress": "alice@example.com"},
    {"account_id": "abc2", "display_name": "Bob Smith", "emailAddress": "bob@example.com"}
  ]
}'''

FAKE_CACHE_LABELS = '''{
  "updated_at": "2026-03-31T10:00:00+00:00",
  "items": ["backend", "frontend", "urgent"]
}'''
```

Write to `root / "cache" / "assignees.json"` and `root / "cache" / "labels.json"`, clean up after run (same pattern as fake `config.json`).

### Full updated `pages_to_shot` list
```python
pages_to_shot = [
    ("00_home",           f"{base}/",               "Home — Landing Page"),
    ("01_prompt",         f"{base}/prompt/",         "Step 1 — Prompt Builder"),
    ("02_import",         f"{base}/import/",         "Step 2a — Import"),
    ("03_import_view",    f"{base}/import/view",     "Step 2b — Import View"),
    ("04_edit",           f"{base}/edit/",           "Step 3 — Edit"),
    ("05_upload_preview", f"{base}/upload/preview",  "Step 4 — Upload Preview"),
    ("06_settings",       f"{base}/settings/",       "Settings"),
    ("07_tools",          f"{base}/tools/",          "Jira Tools"),
    ("08_cache",          f"{base}/cache/",          "Cache Manager"),
]
```

### Session flow
The existing CSRF-aware session flow (import YAML → view → edit → upload preview) retakes `03_import_view`, `04_edit`, `05_upload_preview` with real data. No change needed to that logic.

Also update `FAKE_CONFIG` to add `"org_id": ""` field (new field added to JiraConfig).

---

## 3. `docs/generate_diagrams.py` Changes

### `diagram_architecture()` — full redraw

**Canvas:** keep 1400×820, same color palette.

**Application layer — route boxes (8 total):**
```
/ (home)  /prompt  /import  /edit  /upload  /settings  /tools  /cache
```
Reduce each box width slightly (from 100px to 88px) so 8 fit in the same horizontal space. Add security annotation below route boxes: `"CSRF · Security Headers · Session Fingerprinting"` in small italic text.

**Core modules (7 total):**
```
parser.py        prompt_builder.py   jira_client.py    config.py
models.py        work_store.py       logging_config.py
```
Replace old `assignees.py` + `labels.py` (now thin wrappers, less important architecturally) with `work_store.py`.

**File storage (6 total):**
```
.work/{uuid}.json    config.json    cache/assignees.json
cache/labels.json    cache/projects.json    logs/
```

**External services (3 boxes):**
- `Jira Cloud` (REST API v3)  — orange, existing
- `Atlassian Teams API` — orange, new
- `OS Keyring` (macOS/Windows) — orange, new

**Launch scripts:** add `start.bat` alongside `start.sh / start.ps1`.

### `diagram_dataflow()` — minor update

Add a third box at the bottom row alongside `.work/{uuid}.json` and `Jira Cloud`:
- `Jira Tools + Cache` (teal) — label: "Fetch roles/groups/teams → cache/"

Connect `/tools` and `/cache` steps to it with light arrows.

---

## 4. README Changes

### Version badge
```
![Version](https://img.shields.io/badge/version-1.8.0-orange)
```

### Table of Contents — add entries
- After "Overview": add `[Landing Page](#landing-page)`
- After "Jira Tools": add `[Cache Manager](#cache-manager)`

### Overview section
Add a fifth bullet: "**Browse** a landing page that surfaces all modules with quick-access links."

### Architecture section
Update the architecture table:

| Layer | Components |
|---|---|
| **Client** | Browser — interacts with the Flask web UI |
| **Application** | Flask 3.x app (`app.py`) with 8 route blueprints: `/` (home), `/prompt`, `/import`, `/edit`, `/upload`, `/settings`, `/tools`, `/cache` |
| **Core Modules** | `parser.py`, `prompt_builder.py`, `jira_client.py`, `config.py`, `models.py`, `work_store.py`, `logging_config.py` |
| **File Storage** | `.work/{uuid}.json` per session; `cache/` directory for assignees, labels, projects; `config.json` — no database |
| **External** | Jira Cloud (REST API v3), Atlassian Teams API, OS Keyring (macOS Keychain / Windows Credential Manager), and your LLM of choice |
| **Launch Scripts** | `scripts/start.sh` (macOS/Linux) and `scripts/start.ps1` + `scripts/start.bat` (Windows) |

Add to Key Design Decisions:
- **Security hardening** — all responses carry CSP, X-Frame-Options, and X-Content-Type-Options headers; session cookies are HttpOnly, SameSite=Lax, 8-hour lifetime; work-file access is validated against a session fingerprint.

### New section "Landing Page" — insert before "Usage — 4-Step Workflow"

```markdown
## Landing Page

![Home](docs/images/00_home.png)

Navigate to **http://127.0.0.1:5000** to reach the landing page. It provides quick access to all modules:

- **Meeting to Jira** — start the 4-step wizard
- **Jira Tools** — refresh cached project data
- **Cache Manager** — inspect and clear local caches
- **Settings** — configure your Jira connection

The navbar's home icon (🏠 JiraMaster) returns to this page from anywhere in the app.
```

### Settings screenshot reference
Update `docs/images/06_settings.png` reference — filename unchanged, but screenshot is regenerated.

### New section "Cache Manager" — insert after "Jira Tools"

```markdown
## Cache Manager

![Cache Manager](docs/images/08_cache.png)

Navigate to **Cache** in the top nav (or **http://127.0.0.1:5000/cache**).

The Cache Manager shows the current state of all locally cached Jira data:

| Cache | Contents | Source |
|---|---|---|
| **Assignees** | Jira assignable users (display name, email, account ID) | Jira Tools → Refresh Assignees |
| **Labels** | Top 40 most-used project labels | Jira Tools → Refresh Labels |
| **Projects** | Accessible Jira project list | Jira Tools → Load Projects |

For each cache you can:
- View item count and last-fetched timestamp
- **Delete** individual entries
- **Clear all** entries in a cache

Caches are stored in the `cache/` directory as JSON files with metadata headers.
```

### Project Structure tree — update

```
├── work_store.py           # Centralized session work-file access with fingerprint validation
├── assignees.py            # Assignee cache helpers (reads/writes cache/assignees.json)
├── labels.py               # Label cache helpers (reads/writes cache/labels.json)
│
├── routes/
│   ├── prompt.py
│   ├── import_view.py
│   ├── edit.py
│   ├── upload.py
│   ├── settings.py
│   ├── tools.py
│   └── cache_manager.py    # /cache — view and manage local caches
│
├── templates/
│   ├── home/               # Landing page
│   ├── prompt/
│   ├── import/
│   ├── edit/
│   ├── upload/
│   ├── settings/
│   ├── tools/
│   └── cache_manager/
```

Runtime files table — add `cache/` row:

| Path | Purpose |
|---|---|
| `cache/assignees.json` | Cached Jira assignable users |
| `cache/labels.json` | Cached Jira labels |
| `cache/projects.json` | Cached Jira project list |

Remove old `assignees.json` and `labels.json` root entries.

### Troubleshooting — add entry

```markdown
### Cache Manager shows empty caches
Go to **Jira Tools** and run **Refresh Assignees** and **Refresh Labels** first. The Cache Manager only shows data that has been fetched at least once.
```

---

## 5. Execution Order

1. Update `docs/take_screenshots.py` (new pages, fake cache data, updated page list)
2. Update `docs/generate_diagrams.py` (full architecture redraw, dataflow minor update)
3. Update `README.md` (version, TOC, sections, image refs, project structure)
4. Run `python3 docs/generate_diagrams.py` → regenerates `architecture.png` + `dataflow.png`
5. Run `python3 docs/take_screenshots.py` → regenerates all 9 screenshots
6. Verify all `docs/images/` files updated, spot-check images visually
7. Commit everything together

---

## 6. Files Changed

| File | Change |
|---|---|
| `docs/take_screenshots.py` | Add 00_home + 08_cache, fake cache data, update page list, add org_id to fake config |
| `docs/generate_diagrams.py` | Full architecture redraw, minor dataflow update |
| `README.md` | Version bump, new sections (Landing Page, Cache Manager), updated tables, project structure |
| `docs/images/architecture.png` | Regenerated |
| `docs/images/dataflow.png` | Regenerated |
| `docs/images/00_home.png` | New |
| `docs/images/01_prompt.png` through `07_tools.png` | Retaken |
| `docs/images/08_cache.png` | New |
| `.gitignore` | Already updated (`.superpowers/` added) |
