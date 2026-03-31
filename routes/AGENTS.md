# Routes Directory

Flask blueprints for JiraMaster's web interface. Each file is one blueprint.

## Blueprint Pattern

```python
bp = Blueprint("name", __name__, url_prefix="/name")
```

Blueprints are registered in `routes/__init__.py` via `register_blueprints(app)`.
Templates live in `templates/{blueprint_name}/`.

## Import Conventions

```python
from models import Epic, Story, JiraConfig
from config import load_config
from jira_client import JiraClient
from assignees import load_assignees, save_assignees
from routes import is_valid_work_id   # UUID validation helper
```

NEVER import `requests` directly — use `JiraClient`.

## Work Data Pattern

Each session has a UUID stored in `flask.session["work_id"]`. Work data is stored as:
```
.work/{uuid}.json  →  list of Epic dicts (each with nested stories list)
```

The helper functions `_work_path()`, `_load_epics()`, `_save_epics()` are currently duplicated
across `edit.py`, `import_view.py`, and `upload.py` — known tech debt, should be extracted
to a shared `work_store.py` module.

## Adding a New Blueprint

1. Create `routes/new_feature.py` with a `bp = Blueprint(...)` and route handlers
2. Create `templates/new_feature/index.html` extending `base.html`
3. Register in `routes/__init__.py`: `app.register_blueprint(new_feature.bp)`

## AJAX / JSON Endpoints

For AJAX endpoints that return JSON, use `jsonify()` and return `(data, status_code)`:
```python
@bp.route("/fetch-something", methods=["POST"])
def fetch_something():
    ...
    if err:
        return jsonify({"error": err}), 502
    return jsonify(results)
```
