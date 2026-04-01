# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What This Project Is

**JiraMaster** is a Flask web application that converts AI/LLM-generated meeting note summaries into structured Jira Epics and Stories, then uploads them to Jira Cloud via REST API v3.

It provides a 4-step wizard:
1. **Prompt** — Paste meeting notes, tune parameters, generate a prompt for your LLM (Copilot, ChatGPT, etc.)
2. **Import** — Paste the LLM's YAML/JSON output or upload a file; parse into Epic/Story objects
3. **Edit** — Refine titles, descriptions, acceptance criteria, priorities, assignees, labels, dates
4. **Upload** — Preview and push epics/stories to Jira Cloud

## Tech Stack

- Python 3 / Flask 3.x with Flask-WTF (CSRF protection)
- Jinja2 templates + Bootstrap 5.3
- Jira Cloud REST API v3 via `requests`
- PyYAML for parsing LLM output
- No database — session-keyed `.work/{uuid}.json` file storage

## Project Structure

```
app.py               Flask app factory, CSRF, secret key, blueprint registration
config.py            JiraConfig load/save (config.json), prompt template management
models.py            Dataclasses: Epic, Story, JiraConfig, UploadResult, Priority enum
jira_client.py       JiraClient class — all Jira API calls (create, transitions, comments)
parser.py            Parse YAML/JSON LLM output into Epic/Story objects
prompt_builder.py    Build tunable prompts (aggressiveness, detail, story count)
logging_config.py    Centralised logging setup (file + console, rotation)
assignees.py         Load/save assignees.json cache from Jira
labels.py            Load/save labels.json cache from Jira

routes/              Flask blueprints — see routes/AGENTS.md for conventions
  __init__.py        Blueprint registration, UUID validation helper
  prompt.py          /prompt — generate/download prompt
  import_view.py     /import — paste/upload and parse LLM output
  edit.py            /edit — edit all epic/story fields
  upload.py          /upload — preview and push to Jira
  settings.py        /settings — Jira credentials and field configuration
  tools.py           /tools — Jira utility tools (refresh assignees, labels)

templates/           Jinja2 templates organized by blueprint — see templates/AGENTS.md
static/
  style.css          Bootstrap overrides
  app.js             Clipboard copy, story toggles, cascade checkbox logic

scripts/             Launch and update scripts for all platforms
  start.sh           macOS/Linux: venv, deps, CA certs, startup log
  start.ps1          Windows PowerShell: equivalent of start.sh
  start.bat          Windows: batch wrapper for start.ps1
  update.ps1         Windows: git pull + restart
  update.bat         Windows: batch wrapper for update.ps1

data/                Non-code assets
  prompt_template.txt  Default LLM prompt template

docs/                Documentation, diagrams, screenshots
  images/            Architecture and UI screenshots
  superpowers/       AI-assisted planning documents

.claude/             Claude Code configuration
  hooks/             Auto-commit and major-release confirmation hooks
  rules/             Enforced development rules (loaded automatically by Claude Code)
  settings.json      Project permissions and hook wiring

.work/               Runtime JSON storage for in-progress work (gitignored)
logs/                Runtime logs: jiramaster.log + startup.log (gitignored)
```

## How to Run

```bash
./scripts/start.sh
```

Opens at **http://127.0.0.1:5000**. Requires Python 3.

## Workflow Details

- Each session gets a `work_id` (UUID) stored in the Flask session
- Parsed epics are saved as `.work/{uuid}.json` and read/written by each step
- Jira credentials are stored in `config.json` (gitignored, plaintext)
- Atlassian Document Format (ADF) is used for description/AC fields
- The AC field ID is auto-detected or manually set in Settings

## Configuration Files

| File | Contents | Committed? |
|------|----------|-----------|
| `config.json` | Jira URL, email, API token, project key, AC field ID, proxy | No (gitignored) |
| `.secret_key` | Flask session secret (auto-generated on first run) | No (gitignored) |
| `assignees.json` | Cached Jira assignable users | No (gitignored) |
| `labels.json` | Cached Jira labels (top 40 by usage) | No (gitignored) |
| `.mcp.json` | MCP server config — GitHub token MUST use `${GITHUB_TOKEN}` | No (gitignored) |

## Key Architecture Decisions

- Work data lives entirely in `.work/{uuid}.json` — no DB, no migrations
- `Epic.include` and `Story.include` booleans let users exclude items from upload
- The `initiative_id` field links epics to a parent Jira initiative/epic
- TLS inspection proxies are supported via `start.sh` CA cert merging + `REQUESTS_CA_BUNDLE`

## Logging Convention

All logging is centralised in `logging_config.py`. Every module must use:
```python
import logging
log = logging.getLogger(__name__)
```

See `.claude/rules/02-no-print-or-basicconfig.md` and `.claude/rules/04-logging-conventions.md` for full details.

## Known Technical Debt

- `_work_path`, `_load_epics`, `_save_epics` are duplicated across `routes/edit.py`, `routes/import_view.py`, and `routes/upload.py` — should be extracted to `work_store.py`
- `fetch_labels()` in `jira_client.py` makes one API call per label (N+1 problem)
- `SUBTASKS_FORMAT` in `prompt_builder.py` is defined but never used

## Development Notes

- All Jira API calls go through `JiraClient` in `jira_client.py`
- Run the app with `FLASK_DEBUG=1 ./scripts/start.sh` for debug mode (enables DEBUG console output)
- On Windows: `$env:FLASK_DEBUG="1"; .\scripts\start.ps1`
- The `.work/` directory accumulates files — there is no automatic cleanup
- `assignees.json` and `labels.json` are refreshed from Tools → "Refresh" buttons
- SSL: `scripts/start.sh` (macOS) and `scripts/start.ps1` (Windows) merge system CA certs into certifi bundle; `jira_client.py` auto-detects via `REQUESTS_CA_BUNDLE` env var

## Test Suite

Tests live in `tests/` and use pytest. Run them with:

```bash
venv/bin/python3 -m pytest tests/ -v
venv/bin/python3 -m pytest tests/ --cov=. --cov-report=term-missing
```

### Test file map

| File | Module under test |
|------|------------------|
| `tests/test_models.py` | `models.py` — dataclass serialization, `is_configured()` |
| `tests/test_parser.py` | `parser.py` — YAML/JSON parsing, fence stripping, priority normalization |
| `tests/test_security_utils.py` | `security_utils.py` — all mask/sanitize functions |
| `tests/test_config.py` | `config.py` — load/save with mock keyring and temp files |
| `tests/test_work_store.py` | `work_store.py` — path validation, epic save/load, stale file cleanup |
| `tests/test_prompt_builder.py` | `prompt_builder.py` — tuning instructions, build_prompt |
| `tests/test_settings_route.py` | `routes/settings.py` — Flask integration: validation, form preservation, security headers |

### Rules for maintaining the test suite

1. **Tests run before every commit.** The `PreToolUse` hook in `.claude/settings.json` blocks `git commit` if pytest fails. Fix failing tests before committing.

2. **Extend tests when you change code.** Any change to a tested module must include corresponding test updates:
   - Bug fix → add a regression test that would have caught the bug
   - New function or route → add tests covering the happy path and key error cases
   - Changed validation logic → update/add tests for the new rules

3. **New modules need a new test file.** If you add a new `.py` module with non-trivial logic, create `tests/test_<module>.py` for it.

4. **Test isolation is mandatory.** Tests must never touch real `config.json`, the OS keyring, `.work/` files, or make network calls. Use `tmp_path` + `monkeypatch` for file I/O; use `unittest.mock.patch` for external services.

5. **Test config lives in `pyproject.toml`** (`[tool.pytest.ini_options]`). The `pythonpath = ["."]` setting is required because all imports are flat (e.g. `from config import load_config`).

## Git Workflow

**Every completed step must be committed, tagged, and pushed immediately** — not batched until session end.

After finishing any logical unit of work (a fix, a feature, a refactor):

1. `git add <files>` — stage the relevant files
2. `git commit -m "type: description"` — commit with a conventional message
3. Determine the version bump:
   - Patch fix → bump Z (e.g. v1.8.4 → v1.8.5)
   - New feature → bump Y (e.g. v1.8.x → v1.9.0)
   - Breaking change → bump X
4. `git tag -a vX.Y.Z -m "description"`
5. `git push origin HEAD vX.Y.Z` — push branch AND tag together

**Never push without the tag. Never tag without pushing it.**

> **CRITICAL — this has been missed repeatedly.** Steps 4 and 5 are NOT optional. Every single `git push` must be preceded by a `git tag` and must include the tag in the push command. The exact command is:
> ```bash
> git tag -a vX.Y.Z -m "short description"
> git push origin HEAD vX.Y.Z
> ```
> A bare `git push` or `git push origin HEAD` without the tag name is WRONG.

The `auto-commit.sh` Stop hook handles this automatically at session end — but for mid-task manual commits, you must do steps 3–5 yourself. The hook does not run between steps.

## Rules

See `.claude/rules/` for all enforced development rules:
- `01-no-credentials-in-git.md` — credential and secret handling
- `02-no-print-or-basicconfig.md` — centralised logging only
- `03-jira-api-through-client.md` — all API calls via JiraClient
- `04-logging-conventions.md` — log levels and output destinations
- `05-code-organization.md` — project layout and import conventions
