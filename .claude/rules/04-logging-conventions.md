# Rule: Logging Conventions

Log at the appropriate level:

| Level | When to use |
|-------|-------------|
| `DEBUG` | Detailed diagnostics: API payloads, field values, flow tracing |
| `INFO` | Key operations: startup, config loaded, issue created, connection tested |
| `WARNING` | Recoverable problems: missing field, fallback used, feature skipped |
| `ERROR` | Failures: API errors, parse failures, file I/O errors |

Log output destinations:
- **Console**: INFO by default; DEBUG when `FLASK_DEBUG=1`
- **File**: `logs/jiramaster.log` — always DEBUG, rotated at 5 MB, keeps 3 backups
- **Startup**: `logs/startup.log` — captured by `scripts/start.sh` / `scripts/start.ps1`

Always use `log.exception()` inside `except` blocks (not `log.error()`) to capture the full stack trace.
