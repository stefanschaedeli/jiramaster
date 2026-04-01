import time

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify

from models import Epic, Story
from assignees import load_assignees
from labels import load_label_cache
from work_store import load_epics, save_epics, get_session_work_id
from config import load_config
from jira_client import JiraClient

# In-memory TTL cache for full Jira label name list (avoids repeated fetches during an edit session)
_label_names_cache: dict = {"timestamp": float("-inf"), "labels": []}
_LABEL_NAMES_TTL = 60.0  # seconds

bp = Blueprint("edit", __name__, url_prefix="/edit")


@bp.route("/", methods=["GET"])
def index():
    work_id = get_session_work_id()
    if not work_id:
        flash("No data found. Please import first.", "warning")
        return redirect(url_for("import_view.index"))
    epics = load_epics(work_id)
    included = [e for e in epics if e.include]
    if not included:
        flash("No epics selected. Please go back and select at least one epic.", "warning")
        return redirect(url_for("import_view.view"))
    assignees = load_assignees()
    label_cache = load_label_cache()
    return render_template("edit/index.html", epics=epics, enumerate=enumerate,
                           assignees=assignees, label_cache=label_cache)


@bp.route("/assignees")
def assignees_search():
    """Live assignee search — proxies Jira API with a query string.

    GET /edit/assignees?q=<term>
    Returns JSON [{accountId, displayName, emailAddress}].
    Falls back to cached list when Jira is not configured.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    cfg = load_config()
    if not cfg.is_configured():
        # Return cache filtered by query so the UI still works offline
        cached = load_assignees()
        term = q.lower()
        matches = [
            u for u in cached
            if term in u.get("displayName", "").lower() or term in u.get("emailAddress", "").lower()
        ]
        return jsonify(matches[:10])

    client = JiraClient(cfg)
    users, err = client.fetch_assignees(query=q, max_results=10)
    if err:
        # Degrade gracefully — return empty list rather than a 5xx
        return jsonify([])
    return jsonify(users)


@bp.route("/labels")
def labels_search():
    """Live label search — returns JSON list of label strings.

    GET /edit/labels?q=<term>
    Searches the cached label list first; falls back to a Jira API fetch
    (with a 60-second in-memory TTL) when cache results are insufficient.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    term = q.lower()
    cached = load_label_cache()
    matches = [lbl for lbl in cached if term in lbl.lower()]

    cfg = load_config()
    if cfg.is_configured() and len(matches) < 10:
        global _label_names_cache
        now = time.monotonic()
        if now - _label_names_cache["timestamp"] > _LABEL_NAMES_TTL:
            client = JiraClient(cfg)
            all_names, err = client.fetch_label_names()
            if not err:
                _label_names_cache = {"timestamp": now, "labels": all_names}
        for lbl in _label_names_cache["labels"]:
            if term in lbl.lower() and lbl not in matches:
                matches.append(lbl)
                if len(matches) >= 20:
                    break

    return jsonify(matches[:20])


@bp.route("/save", methods=["POST"])
def save():
    work_id = get_session_work_id()
    if not work_id:
        flash("Session expired. Please re-import.", "warning")
        return redirect(url_for("import_view.index"))

    epics = load_epics(work_id)

    for i, epic in enumerate(epics):
        if not epic.include:
            continue
        epic.title = request.form.get(f"epic_{i}_title", epic.title).strip()
        epic.description = request.form.get(f"epic_{i}_description", epic.description).strip()
        epic.acceptance_criteria = request.form.get(f"epic_{i}_ac", epic.acceptance_criteria).strip()
        epic.due_date = request.form.get(f"epic_{i}_due_date", epic.due_date).strip()
        epic.priority = request.form.get(f"epic_{i}_priority", epic.priority)
        epic.assignee = request.form.get(f"epic_{i}_assignee", epic.assignee).strip()
        epic.status = request.form.get(f"epic_{i}_status", epic.status).strip()
        epic.labels = request.form.getlist(f"epic_{i}_labels")
        epic.comment = request.form.get(f"epic_{i}_comment", epic.comment).strip()

        for j, story in enumerate(epic.stories):
            if not story.include:
                continue
            story.title = request.form.get(f"story_{i}_{j}_title", story.title).strip()
            story.description = request.form.get(f"story_{i}_{j}_description", story.description).strip()
            story.acceptance_criteria = request.form.get(f"story_{i}_{j}_ac", story.acceptance_criteria).strip()
            story.due_date = request.form.get(f"story_{i}_{j}_due_date", story.due_date).strip()
            story.priority = request.form.get(f"story_{i}_{j}_priority", story.priority)
            story.assignee = request.form.get(f"story_{i}_{j}_assignee", story.assignee).strip()
            if not story.assignee and epic.assignee:
                story.assignee = epic.assignee
            story.status = request.form.get(f"story_{i}_{j}_status", story.status).strip()
            story.labels = request.form.getlist(f"story_{i}_{j}_labels")
            story.comment = request.form.get(f"story_{i}_{j}_comment", story.comment).strip()

    save_epics(work_id, epics)
    flash("Changes saved.", "success")
    return redirect(url_for("upload.preview"))
