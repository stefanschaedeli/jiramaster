import json
import logging
import threading
from pathlib import Path

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, Response

from config import load_config
from jira_client import JiraClient, OperationAbortedError
from work_store import load_epics, save_epics, get_session_work_id, WORK_DIR
from operation_events import create_operation, emit_event, stream_events, abort_operation, is_aborted
from run_counter import build_run_label

log = logging.getLogger(__name__)

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
    run_label = build_run_label(cfg.username)
    client = JiraClient(cfg, verbose=cfg.verbose_logging, run_label=run_label)
    results = client.upload_epics(epics)

    # Save updated epics (with jira_keys) back
    save_epics(work_id, epics)

    return render_template(
        "upload/results.html",
        results=results,
        base_url=cfg.base_url,
    )


# ── SSE-powered upload ──

@bp.route("/start", methods=["POST"])
def start_upload():
    """Start Jira upload in a background thread; return operation_id for SSE."""
    work_id = get_session_work_id()
    if not work_id:
        return jsonify({"error": "Session expired. Please re-import."}), 400

    cfg = load_config()
    if not cfg.is_configured():
        return jsonify({"error": "Jira is not configured."}), 400

    op_id = create_operation()
    thread = threading.Thread(
        target=_run_upload, args=(cfg, work_id, op_id), daemon=True
    )
    thread.start()
    return jsonify({"operation_id": op_id})


@bp.route("/abort/<op_id>", methods=["POST"])
def abort_upload(op_id):
    """Signal a running upload to abort."""
    found = abort_operation(op_id)
    return jsonify({"aborted": found})


@bp.route("/events/<op_id>")
def upload_events(op_id):
    """SSE stream for a running upload."""
    return Response(
        stream_events(op_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/results", methods=["GET"])
def results_page():
    """Show upload results from the saved results file."""
    work_id = get_session_work_id()
    if not work_id:
        flash("No data found.", "warning")
        return redirect(url_for("import_view.index"))

    results_file = WORK_DIR / f"{work_id}_results.json"
    if not results_file.exists():
        flash("No upload results found. Please upload first.", "warning")
        return redirect(url_for("upload.preview"))

    data = json.loads(results_file.read_text())
    cfg = load_config()

    # Convert dicts back to UploadResult-like objects for the template
    from types import SimpleNamespace
    results = [SimpleNamespace(**r) for r in data["results"]]

    return render_template(
        "upload/results.html",
        results=results,
        base_url=data.get("base_url", cfg.base_url),
    )


def _run_upload(cfg, work_id, op_id):
    """Background worker: upload epics to Jira with SSE event emission."""
    try:
        callback = lambda evt: emit_event(op_id, evt)
        run_label = build_run_label(cfg.username)
        client = JiraClient(cfg, verbose=True, event_callback=callback,
                            abort_check=lambda: is_aborted(op_id), run_label=run_label)

        def emit_status(msg):
            emit_event(op_id, {"type": "status", "message": msg})

        epics = load_epics(work_id)
        if not epics:
            emit_event(op_id, {"type": "error", "message": "No epics found"})
            return

        emit_status("Starting upload…")

        try:
            results = client.upload_epics(epics)
        except OperationAbortedError:
            emit_event(op_id, {"type": "error", "message": "Upload aborted"})
            return

        # Save updated epics (with jira_keys) back
        save_epics(work_id, epics)

        success = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        # Save results to file for the results page
        results_data = []
        for r in results:
            results_data.append({
                "title": r.title,
                "issue_type": r.issue_type,
                "success": r.success,
                "jira_key": r.jira_key,
                "jira_url": r.jira_url,
                "error_message": r.error_message,
            })

        results_file = WORK_DIR / f"{work_id}_results.json"
        results_file.write_text(json.dumps({"results": results_data, "base_url": cfg.base_url}, indent=2))

        emit_event(op_id, {
            "type": "complete",
            "message": "Upload complete",
            "summary": f"{success} created, {failed} failed" if failed else f"{success} issues created successfully",
        })
    except Exception as exc:
        log.exception("_run_upload failed: %s", exc)
        emit_event(op_id, {"type": "error", "message": str(exc)})
