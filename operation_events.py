"""Thread-safe event queue for bridging JiraClient callbacks to SSE streams."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from typing import Optional

log = logging.getLogger(__name__)

_operations: dict[str, dict] = {}  # op_id -> {"queue": Queue, "created": float, "aborted": bool}
_lock = threading.Lock()
_TTL_SECONDS = 300  # 5 minutes


def create_operation() -> str:
    """Create a new operation and return its ID."""
    _cleanup_stale()
    op_id = str(uuid.uuid4())
    with _lock:
        _operations[op_id] = {"queue": queue.Queue(), "created": time.time(), "aborted": False}
    return op_id


def abort_operation(op_id: str) -> bool:
    """Signal an operation to abort. Returns True if the operation existed."""
    with _lock:
        op = _operations.get(op_id)
        if op:
            op["aborted"] = True
            return True
    return False


def is_aborted(op_id: str) -> bool:
    """Return True if the operation has been aborted."""
    with _lock:
        op = _operations.get(op_id)
        return bool(op and op.get("aborted"))


def emit_event(op_id: str, event: dict) -> None:
    """Push an event to the operation's queue."""
    with _lock:
        op = _operations.get(op_id)
    if op:
        op["queue"].put(event)


def stream_events(op_id: str, timeout: float = 120.0):
    """Generator that yields SSE-formatted events. Ends on 'complete' or 'error' type."""
    with _lock:
        op = _operations.get(op_id)
    if not op:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Unknown operation'})}\n\n"
        return
    q = op["queue"]
    try:
        while True:
            try:
                event = q.get(timeout=30)
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") in ("complete", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
    finally:
        cleanup_operation(op_id)


def cleanup_operation(op_id: str) -> None:
    with _lock:
        _operations.pop(op_id, None)


def _cleanup_stale() -> None:
    """Remove operations older than TTL."""
    now = time.time()
    with _lock:
        stale = [oid for oid, op in _operations.items() if now - op["created"] > _TTL_SECONDS]
        for oid in stale:
            _operations.pop(oid, None)
    if stale:
        log.debug("Cleaned up %d stale operations", len(stale))
