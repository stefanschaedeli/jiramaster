# Run Label Design Spec
**Date:** 2026-04-02
**Status:** Approved

## Overview

Every Jira issue created by JiraMaster via the API automatically receives a tracking label in the format `JiraMaster-BBB-XXXXXX`. This allows teams to identify which issues were created by JiraMaster and correlate them to a specific upload session.

## Label Format

```
JiraMaster-BBB-XXXXXX
```

- **BBB** — initials derived from the Jira username (email). First two letters of the first name + first letter of the last name, uppercased. The username is split on `.` before the `@` domain.
- **XXXXXX** — zero-padded 6-digit integer counter, incrementing once per upload session.

### Username Parsing Rules

| Input email | BBB |
|---|---|
| `stefan.mueller@company.com` | `STM` |
| `john.doe@company.com` | `JOD` |
| `john@company.com` (no last name) | `JOH` (first 3 chars of single name) |
| `a.b@company.com` (short parts) | use all available alpha chars, uppercase |
| Non-alpha characters | stripped; result is always uppercase alpha only |

### Examples

```
JiraMaster-STM-000001   ← Stefan Mueller, first upload session
JiraMaster-STM-000007   ← Stefan Mueller, seventh upload session
JiraMaster-JOD-000003   ← John Doe, third upload session
```

## Counter Storage

**File:** `cache/run_counter.json`
**Format:** `{"counter": 42}`

- Already covered by `cache/` gitignore pattern — never committed.
- File is created automatically on first upload if absent (starts at counter 0, increments to 1 before first use).
- Read-increment-write happens once per upload session, before any Jira API calls.
- No locking needed — JiraMaster runs as a single-process Flask app with no concurrent upload sessions.

## Component Changes

### 1. New `run_counter.py` (root module)

Three functions:

- `load_counter() -> int` — reads `cache/run_counter.json`, returns current value (0 if file absent or malformed).
- `increment_and_save() -> int` — increments by 1, writes back, returns new value.
- `build_run_label(username: str) -> str` — parses username into BBB initials, formats full label string.

### 2. `jira_client.py`

- `JiraClient.__init__` gains an optional `run_label: Optional[str] = None` parameter.
- If provided, `run_label` is appended to `self.labels` during `__init__`, before any issue creation.
- No changes required to `create_epic` or `create_story` — they already merge `self.labels` into `combined_labels`.

### 3. `routes/upload.py`

Both upload paths (synchronous fallback and SSE background worker):
1. Call `increment_and_save()` to get the new counter value.
2. Call `build_run_label(cfg.username)` to produce the label string.
3. Pass `run_label=` when constructing `JiraClient`.

## Tests

New file: `tests/test_run_counter.py`

Covers:
- `load_counter()` when file is absent → returns 0
- `load_counter()` when file is malformed → returns 0 (graceful fallback)
- `increment_and_save()` from 0 → returns 1, file contains `{"counter": 1}`
- `increment_and_save()` from 41 → returns 42
- `build_run_label("stefan.mueller@company.com")` → `"JiraMaster-STM-000042"`
- `build_run_label("john@company.com")` → `"JiraMaster-JOH-000001"` (single name)
- `build_run_label("a.b@company.com")` → handles short parts gracefully
- Label is injected into `JiraClient.labels` when `run_label` is passed

## Out of Scope

- Displaying the run label in the UI (upload results page already shows created Jira keys).
- Resetting the counter via the UI.
- Per-project counters.
