import os
import secrets
from pathlib import Path

from flask import Flask, session
from flask_wtf.csrf import CSRFProtect

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

# Ensure .work directory exists
WORK_DIR = Path(__file__).parent / ".work"
WORK_DIR.mkdir(exist_ok=True)

from routes import register_blueprints
register_blueprints(app)


@app.route("/")
def root():
    from flask import redirect, url_for
    return redirect(url_for("prompt.index"))


@app.context_processor
def inject_globals():
    from config import load_config
    cfg = load_config()
    return {"jira_configured": cfg.is_configured(), "project_key": cfg.project_key}


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print("Starting JiraMaster on http://127.0.0.1:5000")
    app.run(debug=debug, port=5000)
