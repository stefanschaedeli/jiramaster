from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
import logging

from config import load_config
from jira_client import JiraClient
from assignees import load_assignees, save_assignees
from labels import load_label_cache, save_label_cache
from projects import load_projects, save_projects

log = logging.getLogger(__name__)

bp = Blueprint("tools", __name__, url_prefix="/tools")


@bp.route("/", methods=["GET"])
def index():
    cfg = load_config()
    assignees = load_assignees()
    label_cache = load_label_cache()
    projects_cache = load_projects()
    selected_project = session.get("tools_last_project")
    return render_template(
        "tools/index.html",
        assignees=assignees,
        label_cache=label_cache,
        projects_cache=projects_cache,
        cfg=cfg,
        selected_project=selected_project,
    )


@bp.route("/refresh-assignees", methods=["POST"])
def refresh_assignees():
    cfg = load_config()
    if not cfg.is_configured():
        flash("Configure Jira settings first.", "warning")
        return redirect(url_for("settings.index"))

    project_scope = request.form.get("project_scope", "").strip().upper() or None
    session["tools_last_project"] = project_scope or cfg.project_key
    role_id_raw = request.form.get("filter_role_id", "").strip()
    group_name = request.form.get("filter_group_name", "").strip()
    query = request.form.get("filter_query", "").strip() or None
    max_results_raw = request.form.get("filter_max_results", "50").strip()

    try:
        max_results = max(10, min(200, int(max_results_raw)))
    except ValueError:
        max_results = 50

    client = JiraClient(cfg)

    # Step 1: base pool from assignable search
    users, err = client.fetch_assignees(project_key=project_scope, query=query, max_results=max_results)
    if err:
        flash(f"Failed to fetch assignees: {err}", "danger")
        return redirect(url_for("tools.index"))

    filters_applied = bool(query)

    # Step 2: intersect with role members if role selected
    if role_id_raw:
        try:
            role_id = int(role_id_raw)
        except ValueError:
            log.warning("refresh_assignees: invalid role_id_raw=%r, role filter skipped", role_id_raw)
            role_id = None
        if role_id is not None:
            role_ids, role_err = client.fetch_role_members(role_id, project_key=project_scope)
            if role_err:
                flash(f"Warning: Could not fetch role members ({role_err}). Role filter skipped.", "warning")
            else:
                role_set = set(role_ids)
                users = [u for u in users if u["accountId"] in role_set]
                filters_applied = True
                log.info("refresh_assignees: after role filter → %d users", len(users))

    # Step 3: intersect with group members if group provided
    if group_name:
        group_users, group_err = client.fetch_group_members(group_name)
        if group_err:
            flash(f"Warning: Could not fetch group '{group_name}' ({group_err}). Group filter skipped.", "warning")
        else:
            group_ids = {u["accountId"] for u in group_users}
            users = [u for u in users if u["accountId"] in group_ids]
            filters_applied = True
            log.info("refresh_assignees: after group filter → %d users", len(users))

    # Step 4: intersect with Atlassian Team members if team selected
    team_id = request.form.get("filter_team_id", "").strip()
    if team_id:
        team_members, team_err = client.fetch_team_members(team_id)
        if team_err:
            flash(f"Warning: Could not fetch team members ({team_err}). Team filter skipped.", "warning")
        else:
            team_account_ids = {m["accountId"] for m in team_members}
            users = [u for u in users if u["accountId"] in team_account_ids]
            filters_applied = True
            log.info("refresh_assignees: after team filter → %d users", len(users))

    # Guard: don't wipe cache if filters were applied but yielded nothing
    if not users and filters_applied:
        flash("All filters combined returned 0 users — cache not updated. Relax your filters and try again.", "warning")
        return redirect(url_for("tools.index"))

    label = project_scope or cfg.project_key
    save_assignees(users)
    flash(f"Fetched {len(users)} assignees from {label} and saved to assignees.json.", "success")
    return redirect(url_for("tools.index"))


@bp.route("/fetch-roles", methods=["POST"])
def fetch_roles():
    """Return JSON list of {id, name} for all roles in the given project."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    project_scope = request.form.get("project_scope", "").strip().upper() or None
    client = JiraClient(cfg)
    roles, err = client.fetch_project_roles(project_key=project_scope)
    if err:
        return jsonify({"error": err}), 502
    return jsonify(roles)


@bp.route("/fetch-groups", methods=["POST"])
def fetch_groups():
    """Return JSON list of {name} for groups matching an optional query."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    query = request.form.get("query", "").strip()
    client = JiraClient(cfg)
    groups, err = client.fetch_groups(query=query)
    if err:
        return jsonify({"error": err}), 502
    return jsonify(groups)


@bp.route("/fetch-teams", methods=["POST"])
def fetch_teams():
    """Return JSON list of {teamId, displayName} for Atlassian Teams."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400
    if not cfg.org_id:
        return jsonify({"error": "Atlassian Org ID not configured — set it in Settings"}), 400
    query = request.form.get("query", "").strip()
    client = JiraClient(cfg)
    teams, err = client.fetch_teams(query=query)
    if err:
        return jsonify({"error": err}), 502
    return jsonify(teams)


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
    save_projects(projects)
    log.info("fetch_projects: saved %d projects to cache", len(projects))
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
