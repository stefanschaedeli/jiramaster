from flask import Blueprint, render_template, request, flash, redirect, url_for, session

from models import Epic, Story
from assignees import load_assignees
from labels import load_label_cache
from work_store import load_epics, save_epics, get_session_work_id

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
