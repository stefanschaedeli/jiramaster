import logging

from flask import Blueprint, jsonify, render_template, request

from assignees import load_assignees_meta, save_assignees
from labels import load_label_cache_meta, save_label_cache
from projects import load_projects_meta, save_projects

log = logging.getLogger(__name__)

bp = Blueprint("cache_manager", __name__, url_prefix="/cache")

_CACHE_TYPES = {"assignees", "labels", "projects"}


def _load_all_meta() -> dict:
    return {
        "assignees": load_assignees_meta(),
        "labels": load_label_cache_meta(),
        "projects": load_projects_meta(),
    }


@bp.route("/")
def index():
    return render_template("cache_manager/index.html", caches=_load_all_meta())


@bp.route("/delete/<cache_type>/<path:item_id>", methods=["POST"])
def delete_item(cache_type: str, item_id: str):
    """Remove a single entry from a cache. Returns JSON {ok: true} or {error: ...}."""
    if cache_type not in _CACHE_TYPES:
        return jsonify({"error": "Unknown cache type"}), 400

    if cache_type == "assignees":
        meta = load_assignees_meta()
        meta["items"] = [u for u in meta.get("items", []) if u.get("accountId") != item_id]
        save_assignees(meta["items"])
    elif cache_type == "labels":
        meta = load_label_cache_meta()
        meta["items"] = [lbl for lbl in meta.get("items", []) if lbl.get("name") != item_id]
        save_label_cache(meta["items"])
    elif cache_type == "projects":
        meta = load_projects_meta()
        meta["items"] = [p for p in meta.get("items", []) if p.get("key") != item_id]
        save_projects(meta["items"])

    log.info("cache_manager: deleted %s/%s", cache_type, item_id)
    return jsonify({"ok": True})


@bp.route("/clear/<cache_type>", methods=["POST"])
def clear_cache(cache_type: str):
    """Wipe an entire cache. Returns JSON {ok: true} or {error: ...}."""
    if cache_type not in _CACHE_TYPES:
        return jsonify({"error": "Unknown cache type"}), 400

    if cache_type == "assignees":
        save_assignees([])
    elif cache_type == "labels":
        save_label_cache([])
    elif cache_type == "projects":
        save_projects([])

    log.info("cache_manager: cleared %s", cache_type)
    return jsonify({"ok": True})
