from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
import logging

from config import load_config
from jira_client import JiraClient
from assignees import load_assignees, save_assignees
from labels import load_label_cache, save_label_cache

log = logging.getLogger(__name__)

bp = Blueprint("tools", __name__, url_prefix="/tools")


@bp.route("/", methods=["GET"])
def index():
    cfg = load_config()
    assignees = load_assignees()
    label_cache = load_label_cache()
    return render_template("tools/index.html", assignees=assignees, label_cache=label_cache, cfg=cfg)


@bp.route("/refresh-assignees", methods=["POST"])
def refresh_assignees():
    cfg = load_config()
    if not cfg.is_configured():
        flash("Configure Jira settings first.", "warning")
        return redirect(url_for("settings.index"))
    project_scope = request.form.get("project_scope", "").strip().upper() or None
    client = JiraClient(cfg)
    users, err = client.fetch_assignees(project_key=project_scope)
    if err:
        flash(f"Failed to fetch assignees: {err}", "danger")
    else:
        label = project_scope or cfg.project_key
        save_assignees(users)
        flash(f"Fetched {len(users)} assignees from {label} and saved to assignees.json.", "success")
    return redirect(url_for("tools.index"))


@bp.route("/fetch-projects", methods=["POST"])
def fetch_projects():
    """Return JSON list of {key, name} for all accessible Jira projects."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    client = JiraClient(cfg)
    projects, err = client.fetch_projects()
    if err:
        return jsonify({"error": err}), 502
    return jsonify(projects)


@bp.route("/refresh-labels", methods=["POST"])
def refresh_labels():
    cfg = load_config()
    if not cfg.is_configured():
        flash("Configure Jira settings first.", "warning")
        return redirect(url_for("settings.index"))
    client = JiraClient(cfg)
    fetched, err = client.fetch_labels()
    if err:
        flash(f"Failed to fetch labels: {err}", "danger")
    else:
        save_label_cache(fetched)
        flash(f"Saved top {len(fetched)} most-used labels to labels.json.", "success")
    return redirect(url_for("tools.index"))
