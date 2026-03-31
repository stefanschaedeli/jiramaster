# Windows start.bat Shim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `start.bat` so Windows users on corporate (no-admin) machines can launch JiraMaster without hitting the PowerShell execution policy error.

**Architecture:** A one-line `.bat` shim calls `start.ps1` with `-ExecutionPolicy Bypass`, bypassing the unsigned-script restriction per-invocation without any system changes. README is updated to direct Windows users to `start.bat`.

**Tech Stack:** Windows Batch (`.bat`), PowerShell (existing `start.ps1` unchanged)

---

### Task 1: Create start.bat

**Files:**
- Create: `start.bat`

- [ ] **Step 1: Create the file**

Create `start.bat` at the repo root with this exact content:

```bat
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1"
```

- `@echo off` — keeps output clean (no command echo)
- `%~dp0` — expands to the directory containing the `.bat` file, so it works regardless of the caller's working directory
- `-ExecutionPolicy Bypass` — overrides policy for this invocation only; no admin rights required, no permanent change

- [ ] **Step 2: Verify the file content**

Read back `start.bat` and confirm it contains exactly those two lines.

- [ ] **Step 3: Commit**

```bash
git add start.bat
git commit -m "feat: add start.bat shim for Windows no-admin environments"
```

---

### Task 2: Update README.md

**Files:**
- Modify: `README.md` (Windows installation section, ~lines 133–141)

- [ ] **Step 1: Replace the Windows installation block**

Find this section in `README.md`:

```markdown
### Windows

```powershell
git clone https://github.com/your-username/JiraMaster.git
cd JiraMaster
.\start.ps1
```

`start.ps1` does the same as `start.sh` — no admin rights required. CA certs are merged from `Cert:\CurrentUser\Root`, `Cert:\LocalMachine\Root`, and `Cert:\LocalMachine\CA`.
```

Replace with:

```markdown
### Windows

```bat
git clone https://github.com/your-username/JiraMaster.git
cd JiraMaster
start.bat
```

`start.bat` launches `start.ps1` with `-ExecutionPolicy Bypass`, so it works on corporate machines without admin rights or policy changes. CA certs are merged from `Cert:\CurrentUser\Root`, `Cert:\LocalMachine\Root`, and `Cert:\LocalMachine\CA`.

> **Advanced:** If you have already configured your own PowerShell execution policy, you can run `.\start.ps1` directly instead.
```

- [ ] **Step 2: Verify the README renders correctly**

Read back the Windows section of `README.md` and confirm:
- Primary command is `start.bat`
- The `-ExecutionPolicy Bypass` explanation is present
- The `.\start.ps1` fallback note is present

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update Windows launch instructions to use start.bat"
```

---

### Task 3: Close GitHub Issue #1

- [ ] **Step 1: Comment and close issue #1**

```bash
gh issue comment 1 --repo stefanschaedeli/jiramaster --body "Fixed in the latest commit: added \`start.bat\` which calls \`start.ps1\` with \`-ExecutionPolicy Bypass\`. Windows users on corporate (no-admin) machines can now just run \`start.bat\` — no policy changes required."
gh issue close 1 --repo stefanschaedeli/jiramaster
```
