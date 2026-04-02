# Copilot Prompt Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize the JiraMaster prompt generation page for Microsoft Teams Copilot by fixing the copy button, rewriting aggressiveness levels to filter for Jira-worthiness, and adding two platform-specific prompt modes (In-Meeting and Post-Recap).

**Architecture:** Three sequential workstreams. WS3 (copy button) is independent. WS1 (prompt rewrite) modifies `prompt_builder.py` and `data/prompt_template.txt`. WS2 (platform modes) extends both files WS1 changed plus the route and template. Execute in order: WS3 → WS1 → WS2.

**Tech Stack:** Python/Flask, Jinja2, Bootstrap 5.3, vanilla JS, pytest

---

## File Map

| File | Change |
|------|--------|
| `static/app.js` | WS3: add error feedback to `copyToClipboard()` |
| `templates/prompt/index.html` | WS3: move buttons outside form; WS1: update JS labels; WS2: add mode dropdown + dynamic how-to |
| `data/prompt_template.txt` | WS1: rewrite body + add `{{COPILOT_MODE_INSTRUCTIONS}}` placeholder |
| `prompt_builder.py` | WS1: rewrite `AGGRESSIVENESS_MAP`; WS2: add `COPILOT_MODE_MAP`, update `build_prompt()` signature |
| `routes/prompt.py` | WS2: read `copilot_mode` from form, pass to `build_prompt()` |
| `tests/test_prompt_builder.py` | WS1+WS2: update/add tests for new text and mode parameter |

---

## Workstream 3: Copy Button Fix

### Task 1: Fix silent clipboard failure in app.js

**Files:**
- Modify: `static/app.js:7-45`

- [ ] **Step 1: Update `copyToClipboard` and `showCopyFeedback` with error state**

Replace the entire clipboard section (lines 7–45) in `static/app.js` with:

```javascript
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(el.value).then(() => {
      showCopyFeedback(elementId, true);
    }).catch(() => {
      fallbackCopy(el);
    });
  } else {
    fallbackCopy(el);
  }
}

function fallbackCopy(el) {
  el.select();
  el.setSelectionRange(0, 99999);
  try {
    const ok = document.execCommand('copy');
    showCopyFeedback(el.id, ok);
  } catch (e) {
    showCopyFeedback(el.id, false);
  }
}

function showCopyFeedback(elementId, success) {
  const btn = document.querySelector(`button[onclick="copyToClipboard('${elementId}')"]`);
  if (!btn) return;
  const original = btn.textContent;
  const originalClass = btn.classList.contains('btn-outline-secondary') ? 'btn-outline-secondary' : 'btn-outline-primary';

  if (success) {
    btn.textContent = 'Copied!';
    btn.classList.add('btn-success');
    btn.classList.remove(originalClass);
    setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove('btn-success');
      btn.classList.add(originalClass);
    }, 2000);
  } else {
    btn.textContent = 'Copy failed — use Ctrl+C';
    btn.classList.add('btn-danger');
    btn.classList.remove(originalClass);
    setTimeout(() => {
      btn.textContent = original;
      btn.classList.remove('btn-danger');
      btn.classList.add(originalClass);
    }, 3000);
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add static/app.js
git commit -m "fix: show error feedback when clipboard copy fails"
```

### Task 2: Move Copy/Download buttons outside the form

The Copy and Download buttons currently live inside the main `<form>` element. The Download button submits `downloadForm` (a separate hidden form), but the Copy button's `type="button"` may still be affected by form context in some browsers. Moving both outside the form eliminates any ambiguity.

**Files:**
- Modify: `templates/prompt/index.html`

- [ ] **Step 1: Restructure the card header**

In `templates/prompt/index.html`, find the card header section (around lines 86–98):

```html
        <div class="card-header d-flex justify-content-between align-items-center fw-semibold">
          Generated Prompt
          {% if generated_prompt %}
            <div class="d-flex gap-1">
              <button type="button" class="btn btn-sm btn-outline-secondary" onclick="copyToClipboard('generatedPrompt')">
                Copy
              </button>
              <button type="submit" form="downloadForm" class="btn btn-sm btn-outline-primary">
                Download .txt
              </button>
            </div>
          {% endif %}
        </div>
```

Replace it with (buttons moved outside the `<form>` closing tag is handled by placing them after `</form>`, but the card header stays visual — use `form=""` attribute to detach from any form):

```html
        <div class="card-header d-flex justify-content-between align-items-center fw-semibold">
          Generated Prompt
          {% if generated_prompt %}
            <div class="d-flex gap-1">
              <button type="button" class="btn btn-sm btn-outline-secondary" onclick="copyToClipboard('generatedPrompt')">
                Copy
              </button>
              <button type="button" class="btn btn-sm btn-outline-primary" onclick="document.getElementById('downloadForm').submit()">
                Download .txt
              </button>
            </div>
          {% endif %}
        </div>
```

The key change: the Download button changes from `type="submit" form="downloadForm"` to `type="button"` with an explicit `onclick` that submits the download form. Both buttons are now `type="button"` — neither can accidentally submit the main form.

- [ ] **Step 2: Commit**

```bash
git add templates/prompt/index.html
git commit -m "fix: decouple copy/download buttons from main form"
```

---

## Workstream 1: Base Prompt Rewrite

### Task 3: Rewrite AGGRESSIVENESS_MAP to be Jira-centric

**Files:**
- Modify: `prompt_builder.py:11-15`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests for the new aggressiveness text**

In `tests/test_prompt_builder.py`, replace the three aggressiveness test functions:

```python
def test_tuning_defaults():
    result = build_tuning_instructions({})
    assert "2 and 6 Stories" in result
    assert "RULES:" in result
    # Default aggressiveness is 2 — Jira-centric Standard
    assert "committed work items" in result


def test_tuning_aggressiveness_1():
    result = build_tuning_instructions({"aggressiveness": 1})
    assert "explicitly agreed initiatives" in result
    assert "NOT an epic" in result


def test_tuning_aggressiveness_2():
    result = build_tuning_instructions({"aggressiveness": 2})
    assert "committed work items" in result
    assert "at least 2 stories" in result


def test_tuning_aggressiveness_3():
    result = build_tuning_instructions({"aggressiveness": 3})
    assert "every identifiable stream of work" in result
    assert "single-story epics" in result


def test_tuning_invalid_aggressiveness_defaults_to_2():
    result = build_tuning_instructions({"aggressiveness": 99})
    assert "committed work items" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python3 -m pytest tests/test_prompt_builder.py::test_tuning_defaults tests/test_prompt_builder.py::test_tuning_aggressiveness_1 tests/test_prompt_builder.py::test_tuning_aggressiveness_2 tests/test_prompt_builder.py::test_tuning_aggressiveness_3 tests/test_prompt_builder.py::test_tuning_invalid_aggressiveness_defaults_to_2 -v
```

Expected: FAIL (old text doesn't contain "committed work items", "NOT an epic", etc.)

- [ ] **Step 3: Rewrite `AGGRESSIVENESS_MAP` in `prompt_builder.py`**

Replace lines 11–15:

```python
AGGRESSIVENESS_MAP = {
    1: (
        "Only create epics for explicitly agreed initiatives with clear ownership and "
        "multi-story scope. A single task, vague idea, or minor follow-up is NOT an epic — skip it."
    ),
    2: (
        "Create epics for committed work items that need structured tracking. "
        "Each epic must justify at least 2 stories. Skip discussion points, "
        "parking-lot items, and tasks someone can do in a day."
    ),
    3: (
        "Create epics for every identifiable stream of work, including tentative items. "
        "Still require that each epic has enough substance for multiple stories — "
        "don't create single-story epics."
    ),
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python3 -m pytest tests/test_prompt_builder.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add prompt_builder.py tests/test_prompt_builder.py
git commit -m "refactor: rewrite aggressiveness levels to filter for Jira-worthiness"
```

### Task 4: Update aggressiveness slider labels in the template

**Files:**
- Modify: `templates/prompt/index.html:138-142`

- [ ] **Step 1: Update the JS label map to match the new Jira-centric descriptions**

In `templates/prompt/index.html`, find the `aggressivenessLabels` object in the inline `<script>` block (around line 138):

```javascript
  const aggressivenessLabels = {
    1: "Conservative — explicit decisions only",
    2: "Standard — significant actions and deliverables",
    3: "Aggressive — all action items, even tentative ones",
  };
```

Replace it with:

```javascript
  const aggressivenessLabels = {
    1: "Conservative — major initiatives only, skip small tasks",
    2: "Standard — committed work needing multi-story tracking",
    3: "Aggressive — all work streams, even tentative ones",
  };
```

- [ ] **Step 2: Commit**

```bash
git add templates/prompt/index.html
git commit -m "fix: update aggressiveness labels to reflect Jira-centric filtering"
```

### Task 5: Rewrite prompt_template.txt

**Files:**
- Modify: `data/prompt_template.txt`

The rewrite must:
1. Reinforce YAML-only output (critical for Teams Copilot which wraps in markdown)
2. Add Jira-worthiness framing to the role description
3. Add explicit anti-patterns ("a single task is NOT an epic")
4. Add `{{COPILOT_MODE_INSTRUCTIONS}}` placeholder between tuning block and meeting notes

- [ ] **Step 1: Overwrite `data/prompt_template.txt`**

Write the following content to `data/prompt_template.txt` exactly:

```
IMPORTANT: Your entire response must be a single valid YAML document. Do not write any text before or after the YAML. Do not use markdown code fences (no ```). Do not explain anything. Do not add headers, bullet points, or prose. Output ONLY the raw YAML starting with "epics:".

You are a Jira project manager. Convert the meeting content at the end of this prompt into a structured YAML document representing Jira Epics and Stories. Only create epics for work that justifies structured multi-story tracking in Jira. A single task, a brief follow-up, a vague idea, or something one person can complete in a day is NOT an epic — skip it entirely.

{{TUNING_INSTRUCTIONS}}

{{COPILOT_MODE_INSTRUCTIONS}}

REQUIRED OUTPUT STRUCTURE — follow this exactly:
epics:
  - title: "Epic title"
    description: "What this epic covers and why it matters."
    acceptance_criteria: "1. Feature behaves correctly under normal load. 2. Edge cases handled with clear error messages. 3. Reviewed and approved by QA."
    due_date: "YYYY-MM-DD"
    priority: "High"
    assignee: ""
    comment: ""
    stories:
      - title: "Story title"
        description: "What to build and why."
        acceptance_criteria: "1. Given valid input, when submitted, then the expected result appears. 2. Unit tests pass. 3. No regressions in related features."
        due_date: "YYYY-MM-DD"
        priority: "Medium"
        assignee: ""
        comment: ""

REMINDER: Output ONLY the YAML above — no explanations, no markdown, no extra text of any kind.

MEETING NOTES:
{{MEETING_NOTES}}
```

- [ ] **Step 2: Also update the `DEFAULT_PROMPT_TEMPLATE` constant in `config.py` to match**

In `config.py`, find `DEFAULT_PROMPT_TEMPLATE` (a multi-line string constant). Update it to match the new `data/prompt_template.txt` content exactly. This is the fallback used when the file doesn't exist.

Find this section in `config.py`:

```python
DEFAULT_PROMPT_TEMPLATE = """\
IMPORTANT: Your entire response must be a single valid YAML document. ...
```

Replace the entire `DEFAULT_PROMPT_TEMPLATE` value with:

```python
DEFAULT_PROMPT_TEMPLATE = """\
IMPORTANT: Your entire response must be a single valid YAML document. Do not write any text before or after the YAML. Do not use markdown code fences (no ```). Do not explain anything. Do not add headers, bullet points, or prose. Output ONLY the raw YAML starting with "epics:".

You are a Jira project manager. Convert the meeting content at the end of this prompt into a structured YAML document representing Jira Epics and Stories. Only create epics for work that justifies structured multi-story tracking in Jira. A single task, a brief follow-up, a vague idea, or something one person can complete in a day is NOT an epic — skip it entirely.

{{TUNING_INSTRUCTIONS}}

{{COPILOT_MODE_INSTRUCTIONS}}

REQUIRED OUTPUT STRUCTURE — follow this exactly:
epics:
  - title: "Epic title"
    description: "What this epic covers and why it matters."
    acceptance_criteria: "1. Feature behaves correctly under normal load. 2. Edge cases handled with clear error messages. 3. Reviewed and approved by QA."
    due_date: "YYYY-MM-DD"
    priority: "High"
    assignee: ""
    comment: ""
    stories:
      - title: "Story title"
        description: "What to build and why."
        acceptance_criteria: "1. Given valid input, when submitted, then the expected result appears. 2. Unit tests pass. 3. No regressions in related features."
        due_date: "YYYY-MM-DD"
        priority: "Medium"
        assignee: ""
        comment: ""

REMINDER: Output ONLY the YAML above — no explanations, no markdown, no extra text of any kind.

MEETING NOTES:
{{MEETING_NOTES}}
"""
```

- [ ] **Step 3: Verify tests still pass (template changes don't break unit tests since they mock `load_prompt_template`)**

```bash
venv/bin/python3 -m pytest tests/test_prompt_builder.py -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add data/prompt_template.txt config.py
git commit -m "refactor: rewrite prompt template for Teams Copilot compatibility and Jira-worthiness"
```

---

## Workstream 2: Copilot-in-Teams Platform Modes

### Task 6: Add COPILOT_MODE_MAP and update build_prompt() in prompt_builder.py

**Files:**
- Modify: `prompt_builder.py`
- Test: `tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests for the new copilot mode parameter**

Add these tests to the end of `tests/test_prompt_builder.py`:

```python
# ---------------------------------------------------------------------------
# build_prompt copilot_mode
# ---------------------------------------------------------------------------

def test_build_prompt_default_mode_has_no_mode_instructions(monkeypatch):
    """Default (no mode) leaves {{COPILOT_MODE_INSTRUCTIONS}} replaced with empty string."""
    import prompt_builder
    template = "{{TUNING_INSTRUCTIONS}}\n\n{{COPILOT_MODE_INSTRUCTIONS}}\n\n{{MEETING_NOTES}}"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template)
    result = build_prompt("notes", {})
    assert "{{COPILOT_MODE_INSTRUCTIONS}}" not in result
    assert "Analyze the transcript" not in result


def test_build_prompt_in_meeting_mode(monkeypatch):
    import prompt_builder
    template = "{{TUNING_INSTRUCTIONS}}\n\n{{COPILOT_MODE_INSTRUCTIONS}}\n\n{{MEETING_NOTES}}"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template)
    result = build_prompt("notes", {}, copilot_mode="in_meeting")
    assert "transcript" in result.lower()
    assert "downloadable .yaml" in result.lower()


def test_build_prompt_post_recap_mode(monkeypatch):
    import prompt_builder
    template = "{{TUNING_INSTRUCTIONS}}\n\n{{COPILOT_MODE_INSTRUCTIONS}}\n\n{{MEETING_NOTES}}"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template)
    result = build_prompt("notes", {}, copilot_mode="post_recap")
    assert "meeting recap" in result.lower()
    assert "downloadable .yaml" in result.lower()


def test_build_prompt_in_meeting_mode_replaces_meeting_notes_section(monkeypatch):
    """In-meeting mode: MEETING NOTES section replaced, not appended."""
    import prompt_builder
    template = "{{TUNING_INSTRUCTIONS}}\n\n{{COPILOT_MODE_INSTRUCTIONS}}\n\nMEETING NOTES:\n{{MEETING_NOTES}}"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template)
    result = build_prompt("", {}, copilot_mode="in_meeting")
    # The sample instruction should NOT appear — transcript instruction replaces the notes section
    assert prompt_builder.SAMPLE_INSTRUCTION not in result


def test_build_prompt_unknown_mode_treated_as_no_mode(monkeypatch):
    import prompt_builder
    template = "{{TUNING_INSTRUCTIONS}}\n\n{{COPILOT_MODE_INSTRUCTIONS}}\n\n{{MEETING_NOTES}}"
    monkeypatch.setattr(prompt_builder, "load_prompt_template", lambda: template)
    result = build_prompt("notes", {}, copilot_mode="unknown_xyz")
    assert "{{COPILOT_MODE_INSTRUCTIONS}}" not in result
    assert "transcript" not in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python3 -m pytest tests/test_prompt_builder.py::test_build_prompt_default_mode_has_no_mode_instructions tests/test_prompt_builder.py::test_build_prompt_in_meeting_mode tests/test_prompt_builder.py::test_build_prompt_post_recap_mode -v
```

Expected: FAIL — `build_prompt` doesn't accept `copilot_mode` yet

- [ ] **Step 3: Add `COPILOT_MODE_PLACEHOLDER`, `COPILOT_MODE_MAP`, and update `build_prompt()` in `prompt_builder.py`**

Add after the existing placeholder constants at the top of `prompt_builder.py` (after line 4):

```python
COPILOT_MODE_PLACEHOLDER = "{{COPILOT_MODE_INSTRUCTIONS}}"
```

Add `COPILOT_MODE_MAP` after `DETAIL_LEVEL_MAP` (after line 21):

```python
COPILOT_MODE_MAP = {
    "in_meeting": (
        "COPILOT INSTRUCTIONS:\n"
        "You have access to this meeting's live transcript. Analyze it directly — do NOT ask for meeting notes.\n"
        "Focus on: decisions made, action items assigned, and deliverables committed to.\n"
        "Provide your complete response as a single downloadable .yaml file attachment.\n"
        "Do NOT format it as inline text, code blocks, or chat messages."
    ),
    "post_recap": (
        "COPILOT INSTRUCTIONS:\n"
        "The text in the MEETING NOTES section below is a meeting recap generated by Microsoft Teams Copilot.\n"
        "Convert it into the YAML structure specified above.\n"
        "Provide your complete response as a single downloadable .yaml file attachment.\n"
        "Do NOT format it as inline text, code blocks, or chat messages."
    ),
}
```

Update `build_prompt()` signature and body. Replace the entire function (lines 54–73):

```python
def build_prompt(meeting_notes: str, tuning: dict = None, copilot_mode: str = None) -> str:
    if tuning is None:
        tuning = {}

    template = load_prompt_template()
    tuning_block = build_tuning_instructions(tuning)

    if TUNING_PLACEHOLDER in template:
        template = template.replace(TUNING_PLACEHOLDER, tuning_block)
    else:
        # Legacy template without tuning placeholder — prepend tuning block
        template = tuning_block + "\n\n" + template

    # Inject copilot mode instructions
    mode_block = COPILOT_MODE_MAP.get(copilot_mode, "")
    if COPILOT_MODE_PLACEHOLDER in template:
        template = template.replace(COPILOT_MODE_PLACEHOLDER, mode_block)

    # In-meeting mode: Copilot reads the transcript directly — skip the meeting notes section
    if copilot_mode == "in_meeting":
        if MEETING_NOTES_PLACEHOLDER in template:
            template = template.replace(
                "MEETING NOTES:\n" + MEETING_NOTES_PLACEHOLDER,
                ""
            )
            # Fallback: if the "MEETING NOTES:" header wasn't present, just remove the placeholder
            template = template.replace(MEETING_NOTES_PLACEHOLDER, "")
        return template.rstrip()

    # All other modes: inject meeting notes (or sample)
    notes_content = meeting_notes.strip() if meeting_notes else ""
    if not notes_content:
        notes_content = SAMPLE_INSTRUCTION

    if MEETING_NOTES_PLACEHOLDER in template:
        return template.replace(MEETING_NOTES_PLACEHOLDER, notes_content)
    return template + "\n\n" + notes_content
```

- [ ] **Step 4: Run all tests**

```bash
venv/bin/python3 -m pytest tests/test_prompt_builder.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add prompt_builder.py tests/test_prompt_builder.py
git commit -m "feat: add copilot_mode parameter to build_prompt with in_meeting/post_recap modes"
```

### Task 7: Update routes/prompt.py to read copilot_mode from form

**Files:**
- Modify: `routes/prompt.py`

- [ ] **Step 1: Add `copilot_mode` to `DEFAULT_TUNING`, `_tuning_from_form()`, and all three route handlers**

Replace the full content of `routes/prompt.py`:

```python
from flask import Blueprint, render_template, request, Response

from prompt_builder import build_prompt

bp = Blueprint("prompt", __name__, url_prefix="/prompt")

DEFAULT_TUNING = {
    "aggressiveness": 2,
    "stories_min": 2,
    "stories_max": 6,
    "detail_level": "Standard",
    "include_subtasks": False,
    "copilot_mode": "post_recap",
}


def _tuning_from_form(form) -> dict:
    return {
        "aggressiveness": int(form.get("aggressiveness", 2)),
        "stories_min": int(form.get("stories_min", 2)),
        "stories_max": int(form.get("stories_max", 6)),
        "detail_level": form.get("detail_level", "Standard"),
        "include_subtasks": form.get("include_subtasks") == "1",
        "copilot_mode": form.get("copilot_mode", "post_recap"),
    }


@bp.route("/", methods=["GET"])
def index():
    generated = build_prompt("", DEFAULT_TUNING, copilot_mode=DEFAULT_TUNING["copilot_mode"])
    return render_template("prompt/index.html", generated_prompt=generated, tuning=DEFAULT_TUNING)


@bp.route("/generate", methods=["POST"])
def generate():
    tuning = _tuning_from_form(request.form)
    generated = build_prompt("", tuning, copilot_mode=tuning["copilot_mode"])
    return render_template("prompt/index.html", generated_prompt=generated, tuning=tuning)


@bp.route("/download", methods=["POST"])
def download():
    """Serve the generated prompt as a downloadable .txt file."""
    tuning = _tuning_from_form(request.form)
    generated = build_prompt("", tuning, copilot_mode=tuning["copilot_mode"])
    return Response(
        generated,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=jiramaster_prompt.txt"},
    )
```

- [ ] **Step 2: Run full test suite**

```bash
venv/bin/python3 -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add routes/prompt.py
git commit -m "feat: pass copilot_mode from form to build_prompt"
```

### Task 8: Add Copilot Mode dropdown and dynamic How-to-use in the template

**Files:**
- Modify: `templates/prompt/index.html`

This task touches several areas of the template. Make changes in order.

- [ ] **Step 1: Add the Copilot Mode dropdown to the sidebar (after the form's hidden fields, before the controls)**

In `templates/prompt/index.html`, after the last hidden field (line 15, `h_include_subtasks`) and before the `<div class="row g-4">` (line 17), add a hidden field for `copilot_mode`:

```html
  <input type="hidden" name="copilot_mode" id="h_copilot_mode" value="{{ tuning.copilot_mode }}">
```

Also add the matching field to the download form (after `dl_include_subtasks`, around line 133):

```html
  <input type="hidden" name="copilot_mode" id="dl_copilot_mode" value="{{ tuning.copilot_mode }}">
```

- [ ] **Step 2: Add the Copilot Mode dropdown as the first control in the sidebar card body**

In the sidebar card body (`<div class="card-body d-flex flex-column gap-4">`), insert this as the FIRST child (before the Aggressiveness block):

```html
          <!-- Copilot Mode -->
          <div>
            <label class="form-label fw-semibold mb-1">Copilot Mode</label>
            <select class="form-select form-select-sm" id="copilot_mode">
              <option value="post_recap" {% if tuning.copilot_mode == 'post_recap' %}selected{% endif %}>
                Post-Recap (paste meeting recap)
              </option>
              <option value="in_meeting" {% if tuning.copilot_mode == 'in_meeting' %}selected{% endif %}>
                In-Meeting (live transcript)
              </option>
            </select>
            <p class="text-muted small mt-1 mb-0" id="copilot_mode_label"></p>
          </div>
```

- [ ] **Step 3: Replace the static "How to use" section with a dynamic one**

Find the static how-to-use block (around lines 103–110):

```html
            <div class="mt-2 p-2 bg-light border rounded small text-muted">
              <strong>How to use:</strong>
              <ol class="mb-0 ps-3 mt-1">
                <li>Click <strong>Download .txt</strong> to save this prompt as a file.</li>
                <li>In GitHub Copilot Chat, attach the file (paperclip icon) and send it — or paste the text directly.</li>
                <li>Copilot will reply with a YAML file. Save the raw YAML (no extra text) and upload it on the <a href="{{ url_for('import_view.index') }}">Import page</a>.</li>
              </ol>
            </div>
```

Replace it with:

```html
            <div class="mt-2 p-2 bg-light border rounded small text-muted" id="howToUseBox">
              <strong>How to use:</strong>
              <ol class="mb-0 ps-3 mt-1" id="howToUseSteps">
                <!-- Populated by JS based on selected Copilot Mode -->
              </ol>
            </div>
```

- [ ] **Step 4: Update the inline JavaScript block**

In the `<script nonce="{{ csp_nonce }}">` block at the bottom of the template, make the following changes:

**a) Add `copilot_mode` to `syncHidden()`** — find the `syncHidden` function and add:

```javascript
    const mode = document.getElementById('copilot_mode').value;
    document.getElementById('h_copilot_mode').value  = mode;
    document.getElementById('dl_copilot_mode').value = mode;
```

at the end of the function body (before the closing `}`), and update the how-to-use content by calling `updateCopilotModeUI()` from `syncHidden()`.

**b) Add `updateCopilotModeUI()` function** that updates both the description label and the how-to-use steps:

```javascript
  const copilotModeDescriptions = {
    'post_recap': 'Use after the meeting: paste the Teams Copilot meeting recap into the prompt.',
    'in_meeting': 'Use during a live meeting: Copilot reads the transcript directly — no pasting needed.',
  };

  // importUrl is rendered server-side so it's available as a JS variable
  const importUrl = "{{ url_for('import_view.index') }}";
  const copilotModeSteps = {
    'post_recap': [
      'Generate the prompt using the controls above.',
      'In your Teams meeting, ask Copilot to <strong>summarize the meeting</strong> and copy the recap.',
      'Click <strong>Copy</strong> to copy this prompt, then paste it to Copilot in Teams and replace the MEETING NOTES section with the recap.',
      'Ask Copilot to provide the result as a <strong>downloadable .yaml file</strong>.',
      'Upload the .yaml file on the <a href="' + importUrl + '">Import page</a>.',
    ],
    'in_meeting': [
      'Generate the prompt using the controls above.',
      'Click <strong>Copy</strong> or <strong>Download .txt</strong>.',
      'In your Teams meeting, paste the prompt into the <strong>Copilot chat panel</strong> (Copilot has access to the live transcript — no pasting of notes needed).',
      'Ask Copilot to provide the result as a <strong>downloadable .yaml file</strong>.',
      'Upload the .yaml file on the <a href="' + importUrl + '">Import page</a>.',
    ],
  };

  function updateCopilotModeUI() {
    const mode = document.getElementById('copilot_mode').value;
    const label = document.getElementById('copilot_mode_label');
    const stepsList = document.getElementById('howToUseSteps');
    if (label) label.textContent = copilotModeDescriptions[mode] || '';
    if (stepsList) {
      const steps = copilotModeSteps[mode] || [];
      stepsList.innerHTML = steps.map(s => `<li>${s}</li>`).join('');
    }
  }
```

**c) Wire `copilot_mode` into the event listeners array:**

Find:
```javascript
  ['aggressiveness', 'stories_min', 'stories_max', 'detail_level', 'include_subtasks'].forEach(function (id) {
```

Replace with:
```javascript
  ['aggressiveness', 'stories_min', 'stories_max', 'detail_level', 'include_subtasks', 'copilot_mode'].forEach(function (id) {
```

**d) Update the init call at the bottom** to also call `updateCopilotModeUI()`:

Find:
```javascript
  // Init label on page load
  updateAggressivenessLabel();
```

Replace with:
```javascript
  // Init labels on page load
  updateAggressivenessLabel();
  updateCopilotModeUI();
```

**e) Update `syncHidden()` to also call `updateCopilotModeUI()`** — in the event listeners, update both functions:

Find the event listener body:
```javascript
      el.addEventListener('input', function () { syncHidden(); updateAggressivenessLabel(); });
      el.addEventListener('change', function () { syncHidden(); updateAggressivenessLabel(); });
```

Replace with:
```javascript
      el.addEventListener('input', function () { syncHidden(); updateAggressivenessLabel(); updateCopilotModeUI(); });
      el.addEventListener('change', function () { syncHidden(); updateAggressivenessLabel(); updateCopilotModeUI(); });
```

- [ ] **Step 5: Run full test suite**

```bash
venv/bin/python3 -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add templates/prompt/index.html
git commit -m "feat: add Copilot Mode dropdown with dynamic how-to-use instructions"
```

---

## Final: Version Bump and Release

- [ ] **Step 1: Determine version bump**

This is a feature release (new Copilot Mode control) with bug fixes. Current latest tag is `v2.2.18`. Bump minor: `v2.3.0`.

- [ ] **Step 2: Tag and push**

```bash
git tag -a v2.3.0 -m "Add Teams Copilot mode, rewrite prompt for Jira-worthiness, fix copy button"
git push origin HEAD v2.3.0
gh release create v2.3.0 --title "v2.3.0 — Teams Copilot optimization" --notes "- Two Copilot modes: In-Meeting (live transcript) and Post-Recap (paste recap)\n- Rewritten aggressiveness levels to filter for Jira-worthy epics\n- Updated prompt template for Teams Copilot compatibility (no markdown wrapping)\n- Fixed copy button silent failure — now shows error feedback"
```

---

## Verification Checklist

- [ ] All 120+ tests pass: `venv/bin/python3 -m pytest tests/ -v`
- [ ] Visit `/prompt/` — Copilot Mode dropdown is first control in sidebar
- [ ] Switch mode to "In-Meeting" — generated prompt contains "Analyze the transcript", no MEETING NOTES section
- [ ] Switch mode to "Post-Recap" — generated prompt contains MEETING NOTES placeholder area
- [ ] How-to-use steps update correctly when switching modes
- [ ] Aggressiveness level 1 prompt contains "NOT an epic" language
- [ ] Copy button shows "Copied!" on success, "Copy failed — use Ctrl+C" on error
- [ ] Download .txt works for both modes
- [ ] No regressions on Import/Edit/Upload pages
