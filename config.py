import json
import os
from pathlib import Path
from models import JiraConfig

CONFIG_FILE = Path(__file__).parent / "config.json"
PROMPT_TEMPLATE_FILE = Path(__file__).parent / "prompt_template.txt"

DEFAULT_PROMPT_TEMPLATE = """\
IMPORTANT: Your entire response must be a single valid YAML document. Do not write any text before or after the YAML. Do not use markdown code fences (no ```). Do not explain anything. Do not add headers, bullet points, or prose. Output ONLY the raw YAML starting with "epics:".

You are a senior product manager. Convert the meeting notes at the end of this prompt into a structured YAML document representing Jira Epics and Stories.

{{TUNING_INSTRUCTIONS}}

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


def load_config() -> JiraConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            return JiraConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            pass
    return JiraConfig()


def save_config(cfg: JiraConfig) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg.to_dict(), f, indent=2)


def load_prompt_template() -> str:
    if PROMPT_TEMPLATE_FILE.exists():
        return PROMPT_TEMPLATE_FILE.read_text(encoding="utf-8")
    # Write default on first access
    PROMPT_TEMPLATE_FILE.write_text(DEFAULT_PROMPT_TEMPLATE, encoding="utf-8")
    return DEFAULT_PROMPT_TEMPLATE


def save_prompt_template(text: str) -> None:
    PROMPT_TEMPLATE_FILE.write_text(text, encoding="utf-8")
