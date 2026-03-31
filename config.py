import json
import logging
import os
from pathlib import Path
from models import JiraConfig

try:
    import keyring
    import keyring.errors
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

KEYRING_SERVICE = "jiramaster"
KEYRING_USERNAME_KEY = "username"
KEYRING_TOKEN_KEY = "api_token"

log = logging.getLogger(__name__)

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
    cfg = JiraConfig()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            cfg = JiraConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            pass
    # Overlay sensitive fields from OS keyring if available
    if _KEYRING_AVAILABLE:
        try:
            username = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
            api_token = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
            if username is not None:
                cfg.username = username
            if api_token is not None:
                cfg.api_token = api_token
        except Exception as e:
            log.warning("Could not read from keyring (%s) — using config.json values", e)
    return cfg


def save_config(cfg: JiraConfig) -> None:
    # Attempt to store sensitive fields in OS keyring
    if _KEYRING_AVAILABLE:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, cfg.username)
            keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, cfg.api_token)
            # Write config.json without sensitive fields
            data = cfg.to_dict()
            data["username"] = ""
            data["api_token"] = ""
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=2)
            log.info("Credentials stored securely in OS keyring")
            return
        except Exception as e:
            log.warning("Keyring unavailable (%s) — falling back to config.json", e)
    # Fallback: plaintext (keyring unavailable)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg.to_dict(), f, indent=2)
    log.warning("Credentials stored in plaintext config.json (keyring unavailable)")


def get_security_status() -> dict:
    """Return a snapshot of the current security posture for display in the UI."""
    import os

    # Credential storage
    keyring_ok = False
    keyring_error = None
    if _KEYRING_AVAILABLE:
        try:
            # A lightweight probe — just check we can call get_password without error
            keyring.get_password(KEYRING_SERVICE, "__probe__")
            keyring_ok = True
        except Exception as e:
            keyring_error = str(e)

    # Check whether credentials are actually in the keyring vs config.json
    creds_in_keyring = False
    if keyring_ok:
        try:
            token = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
            creds_in_keyring = bool(token)
        except Exception:
            pass

    # SSL / CA bundle
    ca_bundle = None
    ca_source = "certifi default"
    for var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        path = os.environ.get(var)
        if path and os.path.isfile(path):
            ca_bundle = path
            ca_source = f"{var} ({path})"
            break
    if ca_bundle is None:
        try:
            import certifi
            ca_bundle = certifi.where()
        except Exception:
            ca_bundle = None

    # API token loaded (from either source)
    cfg = load_config()
    api_token_loaded = bool(cfg.api_token)

    return {
        "keyring_available": _KEYRING_AVAILABLE,
        "keyring_functional": keyring_ok,
        "keyring_error": keyring_error,
        "creds_in_keyring": creds_in_keyring,
        "api_token_loaded": api_token_loaded,
        "ssl_ca_source": ca_source,
        "ssl_ca_bundle": ca_bundle,
    }


def load_prompt_template() -> str:
    if PROMPT_TEMPLATE_FILE.exists():
        return PROMPT_TEMPLATE_FILE.read_text(encoding="utf-8")
    # Write default on first access
    PROMPT_TEMPLATE_FILE.write_text(DEFAULT_PROMPT_TEMPLATE, encoding="utf-8")
    return DEFAULT_PROMPT_TEMPLATE


def save_prompt_template(text: str) -> None:
    PROMPT_TEMPLATE_FILE.write_text(text, encoding="utf-8")
