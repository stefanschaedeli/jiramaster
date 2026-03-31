from flask import Blueprint, render_template, request, flash, redirect, url_for, session

from config import load_config
from jira_client import JiraClient
from work_store import load_epics, save_epics, get_session_work_id

bp = Blueprint("upload", __name__, url_prefix="/upload")


@bp.route("/preview", methods=["GET"])
def preview():
    work_id = get_session_work_id()
    if not work_id:
        flash("No data found. Please import first.", "warning")
        return redirect(url_for("import_view.index"))
    epics = load_epics(work_id)
    cfg = load_config()

    included_epics = [e for e in epics if e.include]
    epic_count = len(included_epics)
    story_count = sum(
        len([s for s in e.stories if s.include]) for e in included_epics
    )
    return render_template(
        "upload/preview.html",
        epics=epics,
        epic_count=epic_count,
        story_count=story_count,
        cfg=cfg,
    )


@bp.route("/run", methods=["POST"])
def run():
    work_id = get_session_work_id()
    if not work_id:
        flash("Session expired. Please re-import.", "warning")
        return redirect(url_for("import_view.index"))

    cfg = load_config()
    if not cfg.is_configured():
        flash("Jira is not configured. Please visit Settings first.", "danger")
        return redirect(url_for("settings.index"))

    epics = load_epics(work_id)
    client = JiraClient(cfg)
    results = client.upload_epics(epics)

    # Save updated epics (with jira_keys) back
    save_epics(work_id, epics)

    return render_template(
        "upload/results.html",
        results=results,
        base_url=cfg.base_url,
    )
