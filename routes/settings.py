import re
import subprocess
import threading

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response

from config import load_config, save_config, get_security_status
from models import JiraConfig
from jira_client import JiraClient
from assignees import load_assignees
from operation_events import create_operation, emit_event, stream_events

bp = Blueprint("settings", __name__, url_prefix="/settings")

import logging
log = logging.getLogger(__name__)


def _git_version() -> str:
    """Return the current short git commit hash, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


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


def _cfg_from_form(form, existing: JiraConfig = None) -> JiraConfig:
    """Build a JiraConfig from form data, preserving labels from existing config."""
    return JiraConfig(
        base_url=form.get("base_url", "").strip().rstrip("/"),
        username=form.get("username", "").strip(),
        api_token=form.get("api_token", "").strip(),
        project_key=form.get("project_key", "").strip().upper(),
        ac_field_id=form.get("ac_field_id", existing.ac_field_id if existing else "").strip(),
        proxy_url=form.get("proxy_url", "").strip(),
        org_id=form.get("org_id", "").strip(),
        labels=existing.labels if existing else [],
        verbose_logging=form.get("verbose_logging") == "on",
    )


def _render_settings(cfg: JiraConfig):
    return render_template("settings/index.html", cfg=cfg,
                           assignees=load_assignees(),
                           security=get_security_status(),
                           git_version=_git_version())


@bp.route("/", methods=["GET"])
def index():
    cfg = load_config()
    assignees = load_assignees()
    security = get_security_status()
    return render_template("settings/index.html", cfg=cfg, assignees=assignees,
                           security=security, git_version=_git_version())


@bp.route("/save", methods=["POST"])
def save():
    base_url = request.form.get("base_url", "").strip().rstrip("/")
    if base_url and not base_url.startswith("https://"):
        flash("Jira Base URL must start with https://", "danger")
        return _render_settings(_cfg_from_form(request.form, load_config()))
    proxy_url = request.form.get("proxy_url", "").strip()
    if proxy_url and not (proxy_url.startswith("http://") or proxy_url.startswith("https://")):
        flash("Proxy URL must start with http:// or https://", "danger")
        return _render_settings(_cfg_from_form(request.form, load_config()))
    errors = _validate_settings(request.form)
    if errors:
        for err in errors:
            flash(err, "danger")
        return _render_settings(_cfg_from_form(request.form, load_config()))
    existing = load_config()
    cfg = _cfg_from_form(request.form, existing)
    save_config(cfg)
    flash("Settings saved.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/detect-fields", methods=["POST"])
def detect_fields():
    cfg = load_config()
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
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
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
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
        return _render_settings(_cfg_from_form(request.form))
    proxy_url = request.form.get("proxy_url", "").strip()
    if proxy_url and not (proxy_url.startswith("http://") or proxy_url.startswith("https://")):
        flash("Proxy URL must start with http:// or https://", "danger")
        return _render_settings(_cfg_from_form(request.form))
    errors = _validate_settings(request.form)
    if errors:
        for err in errors:
            flash(err, "danger")
        return _render_settings(_cfg_from_form(request.form))
    cfg = _cfg_from_form(request.form)
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
    ok, msg = client.test_connection()
    if ok:
        flash(f"Connection successful: {msg}", "success")
    else:
        flash(f"Connection failed: {msg}", "danger")
    return _render_settings(cfg)


# ── SSE overlay endpoints ──

import logging
_log = logging.getLogger(__name__)


@bp.route("/events/<op_id>")
def settings_events_stream(op_id):
    """SSE stream for a running settings operation."""
    return Response(
        stream_events(op_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/start-test-connection", methods=["POST"])
def start_test_connection():
    """Start connection test in a background thread; return operation_id."""
    cfg = _cfg_from_form(request.form)
    op_id = create_operation()
    thread = threading.Thread(
        target=_run_test_connection, args=(cfg, op_id), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


def _run_test_connection(cfg, op_id):
    try:
        callback = lambda evt: emit_event(op_id, evt)
        client = JiraClient(cfg, verbose=True, event_callback=callback)
        emit_event(op_id, {"type": "status", "message": "Testing connection to Jira..."})
        ok, msg = client.test_connection()
        if ok:
            emit_event(op_id, {"type": "complete", "message": "Connection successful", "summary": msg})
        else:
            emit_event(op_id, {"type": "error", "message": f"Connection failed: {msg}"})
    except Exception as exc:
        _log.exception("_run_test_connection failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})


@bp.route("/start-detect-fields", methods=["POST"])
def start_detect_fields():
    """Start field detection in a background thread; return operation_id."""
    cfg = load_config()
    op_id = create_operation()
    thread = threading.Thread(
        target=_run_detect_fields, args=(cfg, op_id), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


def _run_detect_fields(cfg, op_id):
    try:
        callback = lambda evt: emit_event(op_id, evt)
        client = JiraClient(cfg, verbose=True, event_callback=callback)
        emit_event(op_id, {"type": "status", "message": "Detecting Acceptance Criteria field..."})
        field_id, result = client.detect_ac_field()
        if field_id:
            cfg.ac_field_id = field_id
            save_config(cfg)
            emit_event(op_id, {
                "type": "complete",
                "message": "Field detected",
                "summary": f"Detected: {result} ({field_id}). Saved to config.",
            })
        else:
            emit_event(op_id, {"type": "error", "message": f"Field detection failed: {result}"})
    except Exception as exc:
        _log.exception("_run_detect_fields failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})


@bp.route("/start-detect-org-id", methods=["POST"])
def start_detect_org_id():
    """Start org ID detection in a background thread; return operation_id."""
    cfg = load_config()
    op_id = create_operation()
    thread = threading.Thread(
        target=_run_detect_org_id, args=(cfg, op_id), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


def _run_detect_org_id(cfg, op_id):
    try:
        callback = lambda evt: emit_event(op_id, evt)
        client = JiraClient(cfg, verbose=True, event_callback=callback)
        emit_event(op_id, {"type": "status", "message": "Detecting Atlassian Organization ID..."})
        org_id, err = client.fetch_org_id()
        if org_id:
            cfg.org_id = org_id
            save_config(cfg)
            emit_event(op_id, {
                "type": "complete",
                "message": "Org ID detected",
                "summary": f"Detected Org ID: {org_id}. Saved to config.",
            })
        else:
            emit_event(op_id, {"type": "error", "message": f"Could not detect Org ID: {err}"})
    except Exception as exc:
        _log.exception("_run_detect_org_id failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})
