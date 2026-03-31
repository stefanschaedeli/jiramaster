import re
from flask import Flask

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def is_valid_work_id(work_id: str) -> bool:
    """Return True only if work_id is a canonical UUID4 hex string."""
    return bool(work_id and _UUID_RE.match(work_id))


def register_blueprints(app: Flask) -> None:
    from routes.settings import bp as settings_bp
    from routes.tools import bp as tools_bp
    from routes.cache_manager import bp as cache_manager_bp
    from routes.prompt import bp as prompt_bp
    from routes.import_view import bp as import_bp
    from routes.edit import bp as edit_bp
    from routes.upload import bp as upload_bp

    app.register_blueprint(settings_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(cache_manager_bp)
    app.register_blueprint(prompt_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(edit_bp)
    app.register_blueprint(upload_bp)
