# JiraMaster

**Turn AI-summarised meeting notes into structured Jira Epics & Stories — in four steps.**

JiraMaster is a Flask web application that bridges the gap between your AI assistant (GitHub Copilot, ChatGPT, etc.) and Jira Cloud. Paste meeting notes, generate a tuned prompt, feed it to your LLM, then import, review, and push the resulting Epics and Stories directly to Jira — no coding required.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)
![Jira Cloud](https://img.shields.io/badge/Jira-Cloud%20REST%20v3-0052CC)
![License](https://img.shields.io/badge/License-GPLv3-green)
![Version](https://img.shields.io/badge/version-1.1.0-orange)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Data Flow](#data-flow)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage — 4-Step Workflow](#usage--4-step-workflow)
  - [Step 1: Generate a Prompt](#step-1-generate-a-prompt)
  - [Step 2: Import LLM Output](#step-2-import-llm-output)
  - [Step 3: Edit Epics & Stories](#step-3-edit-epics--stories)
  - [Step 4: Upload to Jira](#step-4-upload-to-jira)
- [Jira Tools](#jira-tools)
- [Advanced Topics](#advanced-topics)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

JiraMaster solves a common pain point: after a meeting, you have Copilot or ChatGPT produce a structured YAML summary of decisions and action items, but getting that into Jira as properly-linked Epics and Stories is tedious. JiraMaster automates the last mile:

1. **Generate** a tunable prompt tailored to your meeting notes
2. **Import** the YAML/JSON output your LLM produces
3. **Edit** every field — titles, acceptance criteria, assignees, labels, priorities, due dates
4. **Upload** directly to Jira Cloud via REST API v3

No database. No migrations. Works out of the box with `./start.sh`.

---

## Architecture

![System Architecture](docs/images/architecture.png)

| Layer | Components |
|-------|-----------|
| **Client** | Browser — interacts with the Flask web UI |
| **Application** | Flask 3.x app (`app.py`) with 6 route blueprints: `/prompt`, `/import`, `/edit`, `/upload`, `/settings`, `/tools` |
| **Core Modules** | `parser.py`, `prompt_builder.py`, `jira_client.py`, `config.py`, `models.py`, `logging_config.py` |
| **File Storage** | `.work/{uuid}.json` per session, `config.json`, `assignees.json`, `labels.json` — no database |
| **External** | Jira Cloud (REST API v3), and your LLM of choice (manual copy/paste) |
| **Launch Scripts** | `start.sh` (macOS/Linux) and `start.ps1` (Windows) — manage venv, deps, TLS cert merging |

### Key Design Decisions

- **No database** — each session is a UUID-keyed JSON file in `.work/`. Zero migrations, trivially portable.
- **Include flags** — `Epic.include` and `Story.include` booleans let you exclude any item before upload.
- **ADF dual-mode** — acceptance criteria are written in Atlassian Document Format (ADF); falls back to plain text if the field doesn't support ADF.
- **TLS proxy support** — `start.sh`/`start.ps1` merge your system CA certificates into the certifi bundle automatically, so corporate TLS-inspection proxies work without admin rights.
- **Centralised logging** — all modules use `logging.getLogger(__name__)`; a single `setup_logging()` call in `app.py` routes everything to a rotating file log and console.

---

## Data Flow

![4-Step Workflow](docs/images/dataflow.png)

```
Meeting Notes (optional)
        │
        ▼
┌───────────────────┐
│  Step 1: Prompt   │  ← Tune aggressiveness, story count, detail level
│  /prompt          │  → Download .txt or copy to clipboard
└────────┬──────────┘
         │ (manual: paste into Copilot / ChatGPT)
         ▼
    LLM produces YAML
         │
         ▼
┌───────────────────┐
│  Step 2: Import   │  ← Paste YAML/JSON or upload file
│  /import          │  → Select epics, set initiative IDs
└────────┬──────────┘
         │ saved to .work/{uuid}.json
         ▼
┌───────────────────┐
│  Step 3: Edit     │  ← Edit all fields: titles, AC, assignees, labels
│  /edit            │  → Updated in .work/{uuid}.json
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Step 4: Upload   │  ← Preview counts, then push
│  /upload          │  → Jira Cloud REST API v3
└───────────────────┘
         │
         ▼
  Jira Epics & Stories created
```

---

## Installation

### Prerequisites

- **Python 3.9+**
- A **Jira Cloud** instance with API access
- A Jira **API token** (see [Configuration](#configuration))

### macOS / Linux

```bash
git clone https://github.com/your-username/JiraMaster.git
cd JiraMaster
./start.sh
```

`start.sh` will:
1. Create a Python virtual environment (`venv/`)
2. Install all dependencies from `requirements.txt`
3. Merge system CA certificates into the certifi bundle (for TLS-inspection proxies)
4. Start the app at **http://127.0.0.1:5000**

### Windows

```bat
git clone https://github.com/your-username/JiraMaster.git
cd JiraMaster
start.bat
```

`start.bat` launches `start.ps1` with `-ExecutionPolicy Bypass`, so it works on corporate machines without admin rights or policy changes. CA certs are merged from `Cert:\CurrentUser\Root`, `Cert:\LocalMachine\Root`, and `Cert:\LocalMachine\CA`.

> **Advanced:** If you have already configured your own PowerShell execution policy, you can run `.\start.ps1` directly instead.

### Manual Installation

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `Flask >= 3.0` | Web framework |
| `Flask-WTF >= 1.2` | CSRF protection |
| `PyYAML >= 6.0.1` | Parse LLM YAML output |
| `requests >= 2.31` | Jira REST API calls |
| `certifi >= 2024` | CA certificate bundle |

---

## Configuration

On first run, open **http://127.0.0.1:5000/settings** to enter your Jira credentials.

![Settings Page](docs/images/06_settings.png)

| Field | Description |
|-------|-------------|
| **Jira Base URL** | Your Atlassian Cloud URL, e.g. `https://yourcompany.atlassian.net` |
| **Email / Username** | The email address of your Atlassian account |
| **API Token** | Generate at [id.atlassian.com](https://id.atlassian.com) → Security → API tokens |
| **Project Key** | The short key for your Jira project (e.g. `PROJ`, `DEV`) |
| **Acceptance Criteria Field ID** | Custom field ID for AC (e.g. `customfield_11401`). Use **Detect Fields** to find it automatically. |
| **HTTP Proxy URL** | Optional. For corporate proxies: `http://proxy.company.com:8080` |

Credentials are saved to `config.json` in the project directory. This file is **gitignored and never committed**.

### Getting a Jira API Token

1. Go to **https://id.atlassian.com** → Security → API tokens
2. Click **Create API token**
3. Give it a name (e.g. `JiraMaster`) and copy the token
4. Paste it into the **API Token** field in Settings

### Detecting the Acceptance Criteria Field

If your Jira project uses a custom AC field, click **Detect Fields** in Settings. JiraMaster will inspect your project's issue create metadata and find fields whose name contains "acceptance" or "criteria".

---

## Usage — 4-Step Workflow

### Step 1: Generate a Prompt

![Prompt Builder](docs/images/01_prompt.png)

Navigate to **Meeting to Jira** in the top nav (or **http://127.0.0.1:5000/prompt**).

**Controls:**

| Control | Options | Effect |
|---------|---------|--------|
| **Aggressiveness** | Conservative / Standard / Aggressive | How many action items to extract. Conservative = explicit decisions only; Aggressive = all action items including tentative ones. |
| **Stories per Epic** | Min / Max (numbers) | Tells the LLM how many stories to generate per epic. |
| **Story Detail Level** | Brief / Standard / Detailed | Brief = title + description only; Standard = all fields; Detailed = rich acceptance criteria with examples. |
| **Include Sub-tasks** | Checkbox | Adds 2–4 sub-task title suggestions per story. |

**Steps:**
1. Paste your meeting notes into the **Meeting Notes** textarea (or leave blank for a sample prompt)
2. Adjust the controls
3. Click **Generate Prompt** — the right panel updates with the tailored prompt
4. Click **Copy** to copy to clipboard, or **Download .txt** to save
5. Paste the prompt into GitHub Copilot, ChatGPT, or any LLM

---

### Step 2: Import LLM Output

#### 2a — Paste or Upload

![Import Page](docs/images/02_import.png)

Paste the YAML/JSON your LLM produced, or upload a `.yaml`/`.json`/`.txt` file.

**Expected YAML structure:**

```yaml
epics:
  - title: "User Authentication System"
    description: "Implement secure login with SSO support"
    acceptance_criteria: "Users can log in. Sessions expire after 8 hours."
    due_date: "2026-06-30"
    priority: "High"          # Low | Medium | High | Critical
    assignee: "Alice Johnson"
    comment: "From sprint planning"
    stories:
      - title: "Login page UI"
        description: "Build the login form with validation"
        acceptance_criteria: "Form validates email format."
        due_date: "2026-05-15"
        priority: "High"
        assignee: "Bob Smith"
```

Click **Parse →** to import.

#### 2b — Review & Select

![Import View](docs/images/03_import_view.png)

After parsing, you see a list of epics with checkboxes. Here you can:

- **Check/uncheck** epics and stories to include or exclude them from upload
- Set an **Initiative ID** (the Jira key of a parent epic, e.g. `PROJ-42`) to link epics
- Override the **Project Key** per epic if you're targeting multiple projects

Click **Confirm & Edit →** to proceed.

---

### Step 3: Edit Epics & Stories

![Edit Page](docs/images/04_edit.png)

Fine-tune every field before upload. Each epic is an expandable card showing:

| Field | Notes |
|-------|-------|
| **Title** | Free text |
| **Description** | Free text |
| **Acceptance Criteria** | Posted as a Jira comment in ADF format |
| **Assignee** | Autocomplete from cached Jira users (refresh in Jira Tools) |
| **Status** | Target status after creation (e.g. "In Progress") |
| **Priority** | Low / Medium / High / Critical |
| **Due Date** | YYYY-MM-DD |
| **Labels** | Multi-select from cached Jira labels |
| **Comment** | Optional additional comment posted to the issue |

Stories are nested under their parent epic. Assignee inherits from the epic if left blank on the story.

Click **Save & Continue →** when done.

---

### Step 4: Upload to Jira

#### 4a — Preview

![Upload Preview](docs/images/05_upload_preview.png)

Review the summary before pushing: epic count, story count, total issues, and target project. Each epic is listed with its included stories, priorities, due dates, and initiative links.

Click **Upload to Jira** when ready.

#### 4b — Results

After upload, each issue is shown with:
- ✓ **Success** — with a clickable Jira issue key link
- ✗ **Failure** — with the error message from the API

For each epic/story, JiraMaster:
1. Creates the Jira issue (Epic or Story with parent link)
2. Transitions it to the requested status (if set)
3. Posts acceptance criteria as a comment (ADF format, with plain-text fallback)
4. Posts the optional extra comment

---

## Jira Tools

![Jira Tools](docs/images/07_tools.png)

Navigate to **Jira Tools** in the top nav.

| Tool | What it does |
|------|-------------|
| **Refresh Assignees** | Fetches all assignable users from Jira and caches them to `assignees.json`. Use the scope selector to fetch from a specific project. |
| **Refresh Labels** | Fetches the top 40 most-used labels from Jira and caches them to `labels.json`. |
| **Load Projects** | Loads a dropdown of accessible Jira projects for scope selection. |

Run **Refresh Assignees** and **Refresh Labels** once after setup, and again whenever your team membership or label set changes.

---

## Advanced Topics

### Debug Mode

```bash
FLASK_DEBUG=1 ./start.sh
```

Enables:
- Flask debug toolbar and auto-reload
- `DEBUG`-level console logging (normally only `INFO`)

Windows:
```powershell
$env:FLASK_DEBUG="1"; .\start.ps1
```

### Corporate TLS Proxy

If your organisation uses TLS inspection, the start scripts automatically merge your system's CA certificates into the certifi bundle so `requests` trusts your proxy's certificate.

You can also set the proxy URL in **Settings → HTTP Proxy URL**.

If you need to set it manually:
```bash
export REQUESTS_CA_BUNDLE=/path/to/your/ca-bundle.crt
```

### Acceptance Criteria Field

JiraMaster auto-detects your AC custom field. If auto-detection fails:

1. Go to **Settings → Detect Fields** to try again
2. Or find the field ID manually: in Jira, open an issue, right-click the AC field → Inspect → look for `customfield_NNNNN`
3. Enter it directly in **Settings → Acceptance Criteria Field ID**

### Multiple Sessions

Each browser session gets its own UUID, so multiple users can work independently at the same time. Work files accumulate in `.work/` — clean them up periodically with:

```bash
rm .work/*.json
```

### Logging

Logs are written to `logs/jiramaster.log` (rotating, 5 MB max, 3 backups) and `logs/startup.log`. Both are gitignored.

---

## Project Structure

```
JiraMaster/
├── app.py                  # Flask app factory, CSRF, blueprint registration
├── config.py               # Load/save config.json; prompt template management
├── models.py               # Dataclasses: Epic, Story, JiraConfig, UploadResult, Priority
├── jira_client.py          # All Jira REST API v3 calls (create, transition, comment)
├── parser.py               # Parse YAML/JSON LLM output → Epic/Story objects
├── prompt_builder.py       # Build tunable prompts (aggressiveness, detail, story count)
├── logging_config.py       # Centralised logging (rotating file + console)
├── assignees.py            # Load/save assignees.json cache
├── labels.py               # Load/save labels.json cache
│
├── routes/
│   ├── prompt.py           # /prompt — generate & download prompt
│   ├── import_view.py      # /import — paste/upload and parse LLM output
│   ├── edit.py             # /edit — edit all epic/story fields
│   ├── upload.py           # /upload — preview and push to Jira
│   ├── settings.py         # /settings — Jira credentials and field config
│   └── tools.py            # /tools — refresh assignees/labels, fetch projects
│
├── templates/              # Jinja2 templates (one subdirectory per blueprint)
├── static/
│   ├── style.css           # Bootstrap 5.3 overrides
│   └── app.js              # Clipboard copy, story toggles, cascade checkbox logic
│
├── docs/
│   └── images/             # Architecture diagrams and app screenshots
│
├── start.sh                # Launch script: macOS/Linux
├── start.ps1               # Launch script: Windows
├── requirements.txt        # Python dependencies
└── VERSION                 # Current version string
```

**Runtime files (gitignored):**

| Path | Purpose |
|------|---------|
| `config.json` | Jira credentials and settings |
| `.secret_key` | Flask session secret (auto-generated) |
| `assignees.json` | Cached Jira assignable users |
| `labels.json` | Cached Jira labels |
| `.work/{uuid}.json` | In-progress session work files |
| `logs/jiramaster.log` | Rotating application log |
| `logs/startup.log` | Startup diagnostics |

---

## Troubleshooting

### "Jira is not configured"
Go to **Settings** and enter your Jira URL, email, API token, and project key. Click **Test Connection** to verify.

### SSL / Certificate errors
Your network may use TLS inspection. The start scripts handle this automatically, but if you see `SSL: CERTIFICATE_VERIFY_FAILED`:
1. Re-run `./start.sh` — it merges system CA certs on every start
2. Or set `REQUESTS_CA_BUNDLE=/path/to/bundle.crt` manually before running

### "Field not found" / AC not posting
The acceptance criteria field ID may be wrong or missing. Go to **Settings → Detect Fields** to auto-detect it. If detection fails, find the field ID in Jira's issue create screen source and enter it manually.

### No assignees in autocomplete
Go to **Jira Tools → Refresh Assignees**. If the list is empty, ensure your API token has permission to browse users in the target project.

### Parse errors on import
- Ensure your LLM output starts with `epics:` (YAML) or `{"epics":` (JSON)
- Strip any preamble text before pasting — the LLM sometimes adds "Here is the YAML:" before the content
- Try **Detail Level: Standard** in Step 1 if the LLM keeps adding extra fields

---

## License

This project is licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE) for details.
