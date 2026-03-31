from flask import Blueprint, render_template, request, flash, redirect, url_for

from config import load_config, save_config
from models import JiraConfig
from jira_client import JiraClient
from assignees import load_assignees
from labels import load_label_cache

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET"])
def index():
    cfg = load_config()
    assignees = load_assignees()
    label_cache = load_label_cache()
    return render_template("settings/index.html", cfg=cfg, assignees=assignees,
                           label_cache=label_cache)


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
    existing = load_config()
    labels = request.form.getlist("labels")
    cfg = JiraConfig(
        base_url=base_url,
        username=request.form.get("username", "").strip(),
        api_token=request.form.get("api_token", "").strip(),
        project_key=request.form.get("project_key", "").strip().upper(),
        ac_field_id=request.form.get("ac_field_id", existing.ac_field_id).strip(),
        proxy_url=proxy_url,
        labels=labels,
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


@bp.route("/test", methods=["POST"])
def test_connection():
    base_url = request.form.get("base_url", "").strip().rstrip("/")
    if base_url and not base_url.startswith("https://"):
        flash("Jira Base URL must start with https://", "danger")
        cfg = JiraConfig()
        return render_template("settings/index.html", cfg=cfg)
    proxy_url = request.form.get("proxy_url", "").strip()
    if proxy_url and not (proxy_url.startswith("http://") or proxy_url.startswith("https://")):
        flash("Proxy URL must start with http:// or https://", "danger")
        cfg = JiraConfig()
        return render_template("settings/index.html", cfg=cfg)
    cfg = JiraConfig(
        base_url=base_url,
        username=request.form.get("username", "").strip(),
        api_token=request.form.get("api_token", "").strip(),
        project_key=request.form.get("project_key", "").strip().upper(),
        proxy_url=proxy_url,
    )
    client = JiraClient(cfg)
    ok, msg = client.test_connection()
    if ok:
        flash(f"Connection successful: {msg}", "success")
    else:
        flash(f"Connection failed: {msg}", "danger")
    return render_template("settings/index.html", cfg=cfg,
                           assignees=load_assignees(), label_cache=load_label_cache())
