import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path

from logging_config import setup_logging
setup_logging()

from flask import Flask, g, render_template, session
from flask_wtf.csrf import CSRFProtect

log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB upload limit

# Load secret key from environment; generate a stable one on disk as fallback.
# Never run with a hardcoded or ephemeral key in production.
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    _key_file = Path(__file__).parent / ".secret_key"
    if _key_file.exists():
        _secret_key = _key_file.read_text().strip()
    else:
        _secret_key = secrets.token_hex(32)
        _key_file.write_text(_secret_key)
        _key_file.chmod(0o600)
app.secret_key = _secret_key
csrf = CSRFProtect(app)

# Session cookie security
app.config["SESSION_COOKIE_HTTPONLY"] = True                               # explicit (Flask default)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"                             # prevent cross-site CSRF
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)             # 8h, not 31 days
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS", "") == "1"  # only when behind TLS


@app.before_request
def _make_session_permanent():
    session.permanent = True
    g.csp_nonce = secrets.token_urlsafe(16)


@app.after_request
def _set_security_headers(response):
    nonce = getattr(g, "csp_nonce", "")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return response


@app.errorhandler(500)
def _handle_500(error):
    log.exception("Internal server error: %s", error)
    return render_template("error.html", code=500,
                           message="Internal server error. Check logs for details."), 500


# Ensure .work directory exists; clean up stale files from previous runs
WORK_DIR = Path(__file__).parent / ".work"
WORK_DIR.mkdir(exist_ok=True)

from work_store import cleanup_stale_work_files
cleanup_stale_work_files(max_age_hours=24)

from routes import register_blueprints
register_blueprints(app)


@app.route("/")
def root():
    return render_template("home/index.html")


def _get_git_version():
    """Return the most recent git tag, or 'unknown' if not in a git repo."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"

_APP_VERSION = _get_git_version()
log.info("JiraMaster version: %s", _APP_VERSION)


@app.context_processor
def inject_globals():
    from config import load_config
    cfg = load_config()
    return {
        "jira_configured": cfg.is_configured(),
        "project_key": cfg.project_key,
        "app_version": _APP_VERSION,
        "csp_nonce": getattr(g, "csp_nonce", ""),
    }


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    log.info("Starting JiraMaster on http://127.0.0.1:5000")
    app.run(debug=debug, port=5000)
