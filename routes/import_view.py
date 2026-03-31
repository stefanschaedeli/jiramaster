import uuid
from pathlib import Path

from flask import Blueprint, render_template, request, flash, redirect, url_for, session

from parser import parse_copilot_output
from config import load_config
from work_store import load_epics, save_epics, set_session_work_id, get_session_work_id

bp = Blueprint("import_view", __name__, url_prefix="/import")

_ALLOWED_UPLOAD_EXTENSIONS = {".yaml", ".yml", ".json", ".txt"}


@bp.route("/", methods=["GET"])
def index():
    return render_template("import/index.html")


@bp.route("/parse", methods=["POST"])
def parse():
    text = ""
    # File upload takes priority over textarea
    if "copilot_file" in request.files and request.files["copilot_file"].filename:
        f = request.files["copilot_file"]
        ext = Path(f.filename).suffix.lower()
        if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
            flash("Invalid file type. Allowed: .yaml, .yml, .json, .txt", "danger")
            return redirect(url_for("import_view.index"))
        text = f.read().decode("utf-8", errors="replace")
    else:
        text = request.form.get("copilot_output", "").strip()

    if not text:
        flash("Please paste Copilot output or upload a file.", "warning")
        return redirect(url_for("import_view.index"))

    try:
        epics = parse_copilot_output(text)
    except ValueError as exc:
        flash(f"Parse error: {exc}", "danger")
        return redirect(url_for("import_view.index"))

    work_id = str(uuid.uuid4())
    set_session_work_id(work_id)
    save_epics(work_id, epics)

    return redirect(url_for("import_view.view"))


@bp.route("/view", methods=["GET"])
def view():
    work_id = get_session_work_id()
    if not work_id:
        flash("No parsed data found. Please import first.", "warning")
        return redirect(url_for("import_view.index"))
    epics = load_epics(work_id)
    if not epics:
        flash("No epics found. Please re-import.", "warning")
        return redirect(url_for("import_view.index"))
    default_project_key = load_config().project_key
    return render_template("import/view.html", epics=epics, enumerate=enumerate,
                           default_project_key=default_project_key)


@bp.route("/confirm", methods=["POST"])
def confirm():
    work_id = get_session_work_id()
    if not work_id:
        flash("Session expired. Please re-import.", "warning")
        return redirect(url_for("import_view.index"))

    epics = load_epics(work_id)
    if not epics:
        flash("No data found. Please re-import.", "warning")
        return redirect(url_for("import_view.index"))

    # Process form checkboxes and initiative IDs
    for i, epic in enumerate(epics):
        epic.include = f"epic_{i}" in request.form
        epic.initiative_id = request.form.get(f"initiative_{i}", "").strip() or None
        epic.project_key = request.form.get(f"project_key_{i}", "").strip().upper() or None
        for j, story in enumerate(epic.stories):
            story.include = f"story_{i}_{j}" in request.form

    save_epics(work_id, epics)
    flash("Selections saved. Review and edit your epics below.", "success")
    return redirect(url_for("edit.index"))
