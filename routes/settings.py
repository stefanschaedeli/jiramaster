import re

from flask import Blueprint, render_template, request, flash, redirect, url_for

from config import load_config, save_config, get_security_status
from models import JiraConfig
from jira_client import JiraClient
from assignees import load_assignees

bp = Blueprint("settings", __name__, url_prefix="/settings")

_PROJECT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
_CUSTOM_FIELD_RE = re.compile(r"^customfield_\d+$")


def _validate_settings(form) -> list:
    """Return a list of error messages for invalid settings form fields."""
    errors = []
    username = form.get("username", "").strip()
    if username and "@" not in username:
        errors.append("Username should be an email address.")
    project_key = form.get("project_key", "").strip().upper()
    if project_key and not _PROJECT_KEY_RE.match(project_key):
        errors.append("Project key must be 2–10 uppercase letters/digits starting with a letter.")
    ac_field = form.get("ac_field_id", "").strip()
    if ac_field and not _CUSTOM_FIELD_RE.match(ac_field):
        errors.append("AC Field ID must be in the format customfield_NNNNN.")
    return errors


@bp.route("/", methods=["GET"])
def index():
    cfg = load_config()
    assignees = load_assignees()
    security = get_security_status()
    return render_template("settings/index.html", cfg=cfg, assignees=assignees,
                           security=security)


@bp.route("/save", methods=["POST"])
def save():
    base_url = request.form.get("base_url", "").strip().rstrip("/")
    if base_url and not base_url.startswith("https://"):
        flash("Jira Base URL must start with https://", "danger")
        return redirect(url_for("settings.index"))
    proxy_url = request.form.get("proxy_url", "").strip()
    if proxy_url and not (proxy_url.startswith("http://") or proxy_url.startswith("https://")):
        flash("Proxy URL must start with http:// or https://", "danger")
        return redirect(url_for("settings.index"))
    for err in _validate_settings(request.form):
        flash(err, "danger")
        return redirect(url_for("settings.index"))
    existing = load_config()
    cfg = JiraConfig(
        base_url=base_url,
        username=request.form.get("username", "").strip(),
        api_token=request.form.get("api_token", "").strip(),
        project_key=request.form.get("project_key", "").strip().upper(),
        ac_field_id=request.form.get("ac_field_id", existing.ac_field_id).strip(),
        proxy_url=proxy_url,
        org_id=request.form.get("org_id", "").strip(),
        labels=existing.labels,
    )
    save_config(cfg)
    flash("Settings saved.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/detect-fields", methods=["POST"])
def detect_fields():
    cfg = load_config()
    client = JiraClient(cfg)
    field_id, result = client.detect_ac_field()
    if field_id:
        cfg.ac_field_id = field_id
        save_config(cfg)
        flash(f"Detected Acceptance Criteria field: {result} ({field_id}). Saved to config.", "success")
    else:
        flash(f"Field detection failed: {result}", "danger")
    return redirect(url_for("settings.index"))


@bp.route("/detect-org-id", methods=["POST"])
def detect_org_id():
    cfg = load_config()
    client = JiraClient(cfg)
    org_id, err = client.fetch_org_id()
    if org_id:
        cfg.org_id = org_id
        save_config(cfg)
        flash(f"Detected Org ID: {org_id}. Saved to config.", "success")
    else:
        flash(f"Could not auto-detect Org ID: {err}. Enter it manually from admin.atlassian.com.", "warning")
    return redirect(url_for("settings.index"))


@bp.route("/test", methods=["POST"])
def test_connection():
    base_url = request.form.get("base_url", "").strip().rstrip("/")
    if base_url and not base_url.startswith("https://"):
        flash("Jira Base URL must start with https://", "danger")
        cfg = JiraConfig()
        return render_template("settings/index.html", cfg=cfg,
                               assignees=load_assignees(),
                               security=get_security_status())
    proxy_url = request.form.get("proxy_url", "").strip()
    if proxy_url and not (proxy_url.startswith("http://") or proxy_url.startswith("https://")):
        flash("Proxy URL must start with http:// or https://", "danger")
        cfg = JiraConfig()
        return render_template("settings/index.html", cfg=cfg,
                               assignees=load_assignees(),
                               security=get_security_status())
    for err in _validate_settings(request.form):
        flash(err, "danger")
        return redirect(url_for("settings.index"))
    cfg = JiraConfig(
        base_url=base_url,
        username=request.form.get("username", "").strip(),
        api_token=request.form.get("api_token", "").strip(),
        project_key=request.form.get("project_key", "").strip().upper(),
        proxy_url=proxy_url,
        org_id=request.form.get("org_id", "").strip(),
    )
    client = JiraClient(cfg)
    ok, msg = client.test_connection()
    if ok:
        flash(f"Connection successful: {msg}", "success")
    else:
        flash(f"Connection failed: {msg}", "danger")
    return render_template("settings/index.html", cfg=cfg,
                           assignees=load_assignees(),
                           security=get_security_status())
