# Rule: Code Organization

## Project Layout

This is a Flask app run directly via scripts — NOT a pip-installable package.

```
app.py + *.py          # Python modules stay in root (importable from project dir)
routes/                # Flask blueprints — one file per route group
templates/             # Jinja2 templates — subdirectory per blueprint
static/                # CSS and JS assets
scripts/               # Launch and update scripts (start.sh, start.ps1, etc.)
data/                  # Non-code assets (prompt_template.txt)
docs/                  # Documentation, diagrams, screenshots
.claude/               # Claude Code config: hooks, rules, settings
```

## Rules

- **Do NOT** create a `src/jiramaster/` package — it would break all imports
- **Do NOT** move `.py` files out of the root into subdirectories like `core/` or `lib/`
- **Routes** are Flask blueprints in `routes/` — each has a matching `templates/{name}/` directory
- **New blueprints** must be registered in `routes/__init__.py`
- **Work data** lives in `.work/{uuid}.json` — no database, no migrations
- **Runtime config** (`config.json`, `assignees.json`, `labels.json`, `.secret_key`) lives in the root and is gitignored
- **Scripts** live in `scripts/` and use `cd ..` / `Split-Path -Parent` to run from the project root
