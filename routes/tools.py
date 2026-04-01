import os
import subprocess
import sys
import threading

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, Response
import logging

from config import load_config
from jira_client import JiraClient, OperationAbortedError
from assignees import load_assignees, save_assignees
from labels import load_label_cache, load_label_cache_rich, save_label_cache
from projects import load_projects, save_projects
from operation_events import create_operation, emit_event, stream_events, abort_operation, is_aborted

log = logging.getLogger(__name__)

bp = Blueprint("tools", __name__, url_prefix="/tools")


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


@bp.route("/", methods=["GET"])
def index():
    cfg = load_config()
    assignees = load_assignees()
    label_cache = load_label_cache()
    projects_cache = load_projects()
    selected_project = session.get("tools_last_project")
    selected_label_project = session.get("tools_last_label_project")
    return render_template(
        "tools/index.html",
        assignees=assignees,
        label_cache=label_cache,
        projects_cache=projects_cache,
        cfg=cfg,
        selected_project=selected_project,
        selected_label_project=selected_label_project,
        git_version=_git_version(),
    )


def _build_assignee_list(client, project_scope, role_id_raw, group_name, team_id, query, max_results, emit=None):
    """Build the assignee list using a source-based pipeline.

    When a role, group, or team is selected, those are used as the PRIMARY source of members
    (all members fetched, no cap). Multiple sources are unioned then deduplicated; if multiple
    sources are selected, only members present in ALL sources are kept (AND semantics).
    When no source is selected, falls back to Jira's assignable search (capped at max_results).

    emit: optional callable(str) for progress messages.
    Returns (users, error_message).
    """
    def _emit(msg):
        if emit:
            emit(msg)

    role_id = None
    if role_id_raw:
        try:
            role_id = int(role_id_raw)
        except ValueError:
            log.warning("_build_assignee_list: invalid role_id_raw=%r, role source skipped", role_id_raw)

    has_source = bool(role_id or group_name or team_id)

    if has_source:
        # Collect full user dicts from each selected source
        source_sets: list = []  # list of sets of accountIds per source
        all_users: dict = {}    # accountId -> user dict (last write wins for displayName/email)

        if role_id:
            _emit("Fetching role members from Jira...")
            role_users, role_err = client.fetch_role_members(role_id, project_key=project_scope)
            if role_err:
                return [], f"Failed to fetch role members: {role_err}"
            _emit(f"Found {len(role_users)} members in role")
            for u in role_users:
                all_users[u["accountId"]] = u
            source_sets.append({u["accountId"] for u in role_users})

        if group_name:
            _emit(f"Fetching all members of group '{group_name}'...")
            group_users, group_err = client.fetch_group_members(group_name, max_results=0)
            if group_err:
                return [], f"Failed to fetch group members: {group_err}"
            _emit(f"Found {len(group_users)} members in group")
            for u in group_users:
                all_users[u["accountId"]] = u
            source_sets.append({u["accountId"] for u in group_users})

        if team_id:
            _emit("Fetching all Atlassian Team members...")
            team_members, team_err = client.fetch_team_members(team_id, max_results=0)
            if team_err:
                return [], f"Failed to fetch team members: {team_err}"
            _emit(f"Found {len(team_members)} members in team, resolving user details...")
            team_ids = [m["accountId"] for m in team_members]
            resolved, res_err = client.resolve_users_bulk(team_ids)
            if res_err:
                return [], f"Failed to resolve team member details: {res_err}"
            for u in resolved:
                all_users[u["accountId"]] = u
            source_sets.append({u["accountId"] for u in team_members})

        # If multiple sources, keep only users present in ALL sources (AND intersection)
        if len(source_sets) > 1:
            _emit("Intersecting sources...")
            common_ids = source_sets[0].intersection(*source_sets[1:])
            users = [all_users[aid] for aid in common_ids if aid in all_users]
            log.info("_build_assignee_list: intersection of %d sources → %d users", len(source_sets), len(users))
        else:
            users = list(all_users.values())

        # Deduplicate by accountId (preserve first occurrence)
        seen: set = set()
        unique = []
        for u in users:
            if u["accountId"] not in seen:
                seen.add(u["accountId"])
                unique.append(u)
        users = unique

        # Apply optional name/email post-filter
        if query:
            q = query.lower()
            users = [u for u in users if q in u.get("displayName", "").lower() or q in u.get("emailAddress", "").lower()]
            log.info("_build_assignee_list: after name/email filter=%r → %d users", query, len(users))

    else:
        # No sources selected — use Jira's assignable search (legacy behaviour)
        _emit("Fetching assignable users from Jira...")
        users, err = client.fetch_assignees(project_key=project_scope, query=query, max_results=max_results)
        if err:
            return [], f"Failed to fetch assignees: {err}"

    return users, None


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
    team_id = request.form.get("filter_team_id", "").strip()
    query = request.form.get("filter_query", "").strip() or None
    max_results_raw = request.form.get("filter_max_results", "50").strip()

    try:
        max_results = max(10, min(200, int(max_results_raw)))
    except ValueError:
        max_results = 50

    client = JiraClient(cfg, verbose=cfg.verbose_logging)
    users, err = _build_assignee_list(client, project_scope, role_id_raw, group_name, team_id, query, max_results)
    if err:
        flash(err, "danger")
        return redirect(url_for("tools.index"))

    if not users:
        flash("No users found — cache not updated. Check your source selection and try again.", "warning")
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


@bp.route("/add-label", methods=["POST"])
def add_label():
    label = request.form.get("label", "").strip()
    if not label:
        flash("Label cannot be empty.", "warning")
        return redirect(url_for("tools.index"))
    current = load_label_cache_rich()
    existing_names = [item["name"] for item in current]
    if label not in existing_names:
        current.append({"name": label, "count": None})
        current.sort(key=lambda x: x["name"].lower())
        save_label_cache(current)
        flash(f"Label '{label}' added to cache.", "success")
    else:
        flash(f"Label '{label}' is already in the cache.", "info")
    return redirect(url_for("tools.index"))


@bp.route("/remove-label", methods=["POST"])
def remove_label():
    label = request.form.get("label", "").strip()
    current = load_label_cache_rich()
    filtered = [item for item in current if item["name"] != label]
    if len(filtered) < len(current):
        save_label_cache(filtered)
        flash(f"Label '{label}' removed from cache.", "success")
    else:
        flash(f"Label '{label}' not found in cache.", "warning")
    return redirect(url_for("tools.index"))


@bp.route("/refresh-labels", methods=["POST"])
def refresh_labels():
    cfg = load_config()
    if not cfg.is_configured():
        flash("Configure Jira settings first.", "warning")
        return redirect(url_for("settings.index"))

    project_scope = request.form.get("label_project_scope", "").strip().upper() or None
    session["tools_last_label_project"] = project_scope or cfg.project_key
    name_filter = request.form.get("label_name_filter", "").strip() or None
    top_n_raw = request.form.get("label_top_n", "40").strip()
    try:
        top_n = max(5, min(200, int(top_n_raw)))
    except ValueError:
        top_n = 40

    client = JiraClient(cfg, verbose=cfg.verbose_logging)
    fetched, err = client.fetch_labels(
        top_n=top_n,
        project_key=project_scope,
        name_filter=name_filter,
    )
    if err:
        flash(f"Failed to fetch labels: {err}", "danger")
    else:
        save_label_cache(fetched)
        flash(f"Saved {len(fetched)} labels to cache.", "success")
    return redirect(url_for("tools.index"))


# ── Update & restart ──

@bp.route("/update-and-restart", methods=["POST"])
def update_and_restart():
    """Spawn the platform update script detached, then return so the browser gets a response."""
    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira not configured"}), 400

    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")

    try:
        if sys.platform == "win32":
            # Launch update.bat detached — it owns everything: killing this process,
            # git pull, and restarting the app. No coordination needed from our side.
            bat = os.path.join(scripts_dir, "update.bat")
            subprocess.Popen(
                ["cmd", "/c", bat],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            script = os.path.join(scripts_dir, "update.sh")
            subprocess.Popen(
                ["bash", script],
                start_new_session=True,
                close_fds=True,
            )
    except Exception as exc:
        log.exception("update_and_restart: failed to spawn update script: %s", exc)
        return jsonify({"error": str(exc)}), 500

    log.info("update_and_restart: update script launched, shutting down in 1s")

    def _shutdown():
        import time
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()
    return jsonify({"ok": True})


# ── SSE overlay endpoints ──

@bp.route("/abort/<op_id>", methods=["POST"])
def abort_operation_route(op_id):
    """Signal a running operation to abort."""
    found = abort_operation(op_id)
    return jsonify({"aborted": found})


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
        client = JiraClient(cfg, verbose=True, event_callback=callback,
                            abort_check=lambda: is_aborted(op_id))

        def emit_status(msg):
            emit_event(op_id, {"type": "status", "message": msg})

        if is_aborted(op_id):
            emit_event(op_id, {"type": "error", "message": "Operation aborted"})
            return

        try:
            users, err = _build_assignee_list(
                client, project_scope, role_id_raw, group_name, team_id, query, max_results,
                emit=emit_status,
            )
        except OperationAbortedError:
            emit_event(op_id, {"type": "error", "message": "Operation aborted"})
            return

        if err:
            emit_event(op_id, {"type": "error", "message": err})
            return

        if not users:
            emit_event(op_id, {
                "type": "error",
                "message": "No users found — cache not updated. Check your source selection.",
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

    project_scope = request.form.get("label_project_scope", "").strip().upper() or None
    session["tools_last_label_project"] = project_scope or cfg.project_key
    name_filter = request.form.get("label_name_filter", "").strip() or None
    top_n_raw = request.form.get("label_top_n", "40").strip()
    try:
        top_n = max(5, min(200, int(top_n_raw)))
    except ValueError:
        top_n = 40

    op_id = create_operation()
    params = {
        "project_scope": project_scope,
        "name_filter": name_filter,
        "top_n": top_n,
    }
    thread = threading.Thread(
        target=_run_refresh_labels, args=(cfg, op_id, params), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


def _run_refresh_labels(cfg, op_id, params):
    """Background worker for label refresh with event emission."""
    try:
        callback = lambda evt: emit_event(op_id, evt)
        client = JiraClient(cfg, verbose=True, event_callback=callback,
                            abort_check=lambda: is_aborted(op_id))

        def emit_status(msg):
            emit_event(op_id, {"type": "status", "message": msg})

        try:
            fetched, err = client.fetch_labels(
                top_n=params["top_n"],
                project_key=params["project_scope"],
                name_filter=params["name_filter"],
                emit=emit_status,
            )
        except OperationAbortedError:
            emit_event(op_id, {"type": "error", "message": "Operation aborted"})
            return
        if err:
            emit_event(op_id, {"type": "error", "message": f"Failed to fetch labels: {err}"})
            return

        save_label_cache(fetched)
        emit_event(op_id, {
            "type": "complete",
            "message": "Label refresh complete",
            "summary": f"Saved {len(fetched)} labels to cache",
        })
    except Exception as exc:
        log.exception("_run_refresh_labels failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})
