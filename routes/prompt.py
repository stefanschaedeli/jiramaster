from flask import Blueprint, render_template, request, Response

from prompt_builder import build_prompt

bp = Blueprint("prompt", __name__, url_prefix="/prompt")

DEFAULT_TUNING = {
    "aggressiveness": 2,
    "stories_min": 2,
    "stories_max": 6,
    "detail_level": "Standard",
    "include_subtasks": False,
}


def _tuning_from_form(form) -> dict:
    return {
        "aggressiveness": int(form.get("aggressiveness", 2)),
        "stories_min": int(form.get("stories_min", 2)),
        "stories_max": int(form.get("stories_max", 6)),
        "detail_level": form.get("detail_level", "Standard"),
        "include_subtasks": form.get("include_subtasks") == "1",
    }


@bp.route("/", methods=["GET"])
def index():
    generated = build_prompt("", DEFAULT_TUNING)
    return render_template("prompt/index.html", generated_prompt=generated, tuning=DEFAULT_TUNING)


@bp.route("/generate", methods=["POST"])
def generate():
    meeting_notes = request.form.get("meeting_notes", "").strip()
    tuning = _tuning_from_form(request.form)
    generated = build_prompt(meeting_notes, tuning)
    return render_template(
        "prompt/index.html",
        generated_prompt=generated,
        meeting_notes=meeting_notes,
        tuning=tuning,
    )


@bp.route("/download", methods=["POST"])
def download():
    """Serve the generated prompt as a downloadable .txt file."""
    meeting_notes = request.form.get("meeting_notes", "").strip()
    tuning = _tuning_from_form(request.form)
    generated = build_prompt(meeting_notes, tuning)
    return Response(
        generated,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=jiramaster_prompt.txt"},
    )
