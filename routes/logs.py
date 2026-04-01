from __future__ import annotations

import logging
import os
import re
from typing import List

from flask import Blueprint, render_template, request, jsonify

log = logging.getLogger(__name__)

bp = Blueprint("logs", __name__, url_prefix="/logs",
               template_folder="../templates")

_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "jiramaster.log")
_LEVEL_RE = re.compile(r"\[(\w+)\]")


def _tail_lines(path: str, max_lines: int = 200) -> List[str]:
    """Read the last max_lines from a file efficiently."""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            # For files under 2MB, just read all
            f.seek(0, 2)
            size = f.tell()
            if size <= 2 * 1024 * 1024:
                f.seek(0)
                lines = f.readlines()
                return lines[-max_lines:]
            # For larger files, seek back and read
            chunk_size = max_lines * 200  # ~200 bytes per line estimate
            f.seek(max(0, size - chunk_size))
            f.readline()  # skip partial first line
            lines = f.readlines()
            return lines[-max_lines:]
    except OSError:
        log.exception("Could not read log file: %s", path)
        return []


@bp.route("/", methods=["GET"])
def index():
    return render_template("logs/index.html")


@bp.route("/api/tail", methods=["GET"])
def tail():
    """Return the last N log lines, optionally filtered by level."""
    try:
        max_lines = min(1000, max(10, int(request.args.get("lines", "200"))))
    except ValueError:
        max_lines = 200

    level_filter = request.args.get("level", "").upper()
    # Read more than needed to account for filtering
    raw_lines = _tail_lines(_LOG_FILE, max_lines * 3 if level_filter else max_lines)

    if level_filter and level_filter != "ALL":
        filtered = []
        for line in raw_lines:
            m = _LEVEL_RE.search(line)
            if m and m.group(1) == level_filter:
                filtered.append(line)
        raw_lines = filtered[-max_lines:]

    # Strip trailing newlines
    lines = [line.rstrip("\n\r") for line in raw_lines]

    try:
        file_size = os.path.getsize(_LOG_FILE)
    except OSError:
        file_size = 0

    return jsonify({
        "lines": lines,
        "total_lines": len(lines),
        "file_size": file_size,
    })
