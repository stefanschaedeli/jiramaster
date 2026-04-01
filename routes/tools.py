import threading

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, Response
import logging

from config import load_config
from jira_client import JiraClient
from assignees import load_assignees, save_assignees
from labels import load_label_cache, save_label_cache
from projects import load_projects, save_projects
from operation_events import create_operation, emit_event, stream_events

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

    client = JiraClient(cfg, verbose=cfg.verbose_logging)

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
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
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
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
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
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
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
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
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
    client = JiraClient(cfg, verbose=cfg.verbose_logging)
    fetched, err = client.fetch_labels()
    if err:
        flash(f"Failed to fetch labels: {err}", "danger")
    else:
        save_label_cache(fetched)
        flash(f"Saved top {len(fetched)} most-used labels to labels.json.", "success")
    return redirect(url_for("tools.index"))


# ── SSE overlay endpoints ──

@bp.route("/events/<op_id>")
def operation_events_stream(op_id):
    """SSE stream for a running operation."""
    return Response(
        stream_events(op_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/start-refresh-assignees", methods=["POST"])
def start_refresh_assignees():
    """Start assignee refresh in a background thread; return operation_id for SSE."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400

    op_id = create_operation()
    params = {
        "project_scope": request.form.get("project_scope", "").strip().upper() or None,
        "role_id_raw": request.form.get("filter_role_id", "").strip(),
        "group_name": request.form.get("filter_group_name", "").strip(),
        "query": request.form.get("filter_query", "").strip() or None,
        "max_results_raw": request.form.get("filter_max_results", "50").strip(),
        "team_id": request.form.get("filter_team_id", "").strip(),
    }
    thread = threading.Thread(
        target=_run_refresh_assignees, args=(cfg, op_id, params), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


def _run_refresh_assignees(cfg, op_id, params):
    """Background worker for assignee refresh with event emission."""
    try:
        project_scope = params["project_scope"]
        role_id_raw = params["role_id_raw"]
        group_name = params["group_name"]
        query = params["query"]
        team_id = params["team_id"]

        try:
            max_results = max(10, min(200, int(params["max_results_raw"])))
        except ValueError:
            max_results = 50

        callback = lambda evt: emit_event(op_id, evt)
        client = JiraClient(cfg, verbose=True, event_callback=callback)

        # Step 1: fetch base pool
        emit_event(op_id, {"type": "status", "message": "Fetching assignable users from Jira..."})
        users, err = client.fetch_assignees(project_key=project_scope, query=query, max_results=max_results)
        if err:
            emit_event(op_id, {"type": "error", "message": f"Failed to fetch assignees: {err}"})
            return

        filters_applied = bool(query)
        emit_event(op_id, {"type": "status", "message": f"Found {len(users)} base users, applying filters..."})

        # Step 2: role filter
        if role_id_raw:
            try:
                role_id = int(role_id_raw)
            except ValueError:
                role_id = None
            if role_id is not None:
                emit_event(op_id, {"type": "status", "message": "Filtering by project role..."})
                role_ids, role_err = client.fetch_role_members(role_id, project_key=project_scope)
                if not role_err:
                    role_set = set(role_ids)
                    users = [u for u in users if u["accountId"] in role_set]
                    filters_applied = True

        # Step 3: group filter
        if group_name:
            emit_event(op_id, {"type": "status", "message": f"Filtering by group '{group_name}'..."})
            group_users, group_err = client.fetch_group_members(group_name)
            if not group_err:
                group_ids = {u["accountId"] for u in group_users}
                users = [u for u in users if u["accountId"] in group_ids]
                filters_applied = True

        # Step 4: team filter
        if team_id:
            emit_event(op_id, {"type": "status", "message": "Filtering by Atlassian Team..."})
            team_members, team_err = client.fetch_team_members(team_id)
            if not team_err:
                team_account_ids = {m["accountId"] for m in team_members}
                users = [u for u in users if u["accountId"] in team_account_ids]
                filters_applied = True

        # Guard
        if not users and filters_applied:
            emit_event(op_id, {
                "type": "error",
                "message": "All filters combined returned 0 users — cache not updated.",
            })
            return

        label = project_scope or cfg.project_key
        save_assignees(users)
        emit_event(op_id, {
            "type": "complete",
            "message": "Assignee refresh complete",
            "summary": f"Fetched {len(users)} assignees from {label}",
        })
    except Exception as exc:
        log.exception("_run_refresh_assignees failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})


@bp.route("/start-refresh-labels", methods=["POST"])
def start_refresh_labels():
    """Start label refresh in a background thread; return operation_id for SSE."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400

    op_id = create_operation()
    thread = threading.Thread(
        target=_run_refresh_labels, args=(cfg, op_id), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


def _run_refresh_labels(cfg, op_id):
    """Background worker for label refresh with event emission."""
    try:
        callback = lambda evt: emit_event(op_id, evt)
        client = JiraClient(cfg, verbose=True, event_callback=callback)

        emit_event(op_id, {"type": "status", "message": "Fetching labels from Jira..."})
        fetched, err = client.fetch_labels()
        if err:
            emit_event(op_id, {"type": "error", "message": f"Failed to fetch labels: {err}"})
            return

        save_label_cache(fetched)
        emit_event(op_id, {
            "type": "complete",
            "message": "Label refresh complete",
            "summary": f"Saved top {len(fetched)} most-used labels",
        })
    except Exception as exc:
        log.exception("_run_refresh_labels failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})
