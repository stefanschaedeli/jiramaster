# Rule: Centralised Logging Only

NEVER use `print()` for diagnostic output anywhere in this project.
NEVER call `logging.basicConfig()` in any module.

Every module must declare its logger at the top:
```python
import logging
log = logging.getLogger(__name__)
```

`setup_logging()` in `logging_config.py` is called once by `app.py` and configures all handlers.
Adding `basicConfig()` anywhere else will interfere with it.

Use `log.exception()` inside `except` blocks — it automatically captures the stack trace:
```python
except Exception as exc:
    log.exception("Something failed: %s", exc)
```
