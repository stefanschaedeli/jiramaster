import json
from pathlib import Path

from flask import Blueprint, render_template, request, flash, redirect, url_for, session

from config import load_config
from jira_client import JiraClient
from models import Epic
from routes import is_valid_work_id

bp = Blueprint("upload", __name__, url_prefix="/upload")

WORK_DIR = Path(__file__).parent.parent / ".work"


def _work_path(work_id: str) -> Path:
    return WORK_DIR / f"{work_id}.json"


def _load_epics(work_id: str) -> list:
    path = _work_path(work_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Epic.from_dict(d) for d in data]


def _save_epics(work_id: str, epics: list) -> None:
    data = [e.to_dict() for e in epics]
    _work_path(work_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


@bp.route("/preview", methods=["GET"])
def preview():
    work_id = session.get("work_id")
    if not work_id or not is_valid_work_id(work_id):
        flash("No data found. Please import first.", "warning")
        return redirect(url_for("import_view.index"))
    epics = _load_epics(work_id)
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
    work_id = session.get("work_id")
    if not work_id or not is_valid_work_id(work_id):
        flash("Session expired. Please re-import.", "warning")
        return redirect(url_for("import_view.index"))

    cfg = load_config()
    if not cfg.is_configured():
        flash("Jira is not configured. Please visit Settings first.", "danger")
        return redirect(url_for("settings.index"))

    epics = _load_epics(work_id)
    client = JiraClient(cfg)
    results = client.upload_epics(epics)

    # Save updated epics (with jira_keys) back
    _save_epics(work_id, epics)

    return render_template(
        "upload/results.html",
        results=results,
        base_url=cfg.base_url,
    )
