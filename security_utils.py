"""Security masking utilities for safe logging and display of API details."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


_SENSITIVE_HEADER_KEYS = {"authorization", "cookie", "x-atlassian-token", "set-cookie"}
_SENSITIVE_PARAM_PATTERN = re.compile(
    r"(token|secret|password|key|auth|credential)", re.IGNORECASE
)


def mask_token(value: str) -> str:
    """Mask a token, showing only the first 4 characters."""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return value[:4] + "****"


def mask_email(value: str) -> str:
    """Mask an email address: first char + *** @ domain."""
    if not value or "@" not in value:
        return "****"
    local, domain = value.rsplit("@", 1)
    return local[0] + "***@" + domain if local else "***@" + domain


def mask_url(url: str) -> str:
    """Mask sensitive query parameters in a URL."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = parse_qs(parsed.query, keep_blank_values=True)
    masked = {}
    for k, values in params.items():
        if _SENSITIVE_PARAM_PATTERN.search(k):
            masked[k] = ["****"]
        else:
            masked[k] = values
    cleaned = urlencode(masked, doseq=True)
    return urlunparse(parsed._replace(query=cleaned))


def mask_headers(headers: dict) -> dict:
    """Return a copy of headers with sensitive values replaced."""
    if not headers:
        return {}
    masked = {}
    for k, v in headers.items():
        if k.lower() in _SENSITIVE_HEADER_KEYS:
            masked[k] = "****"
        else:
            masked[k] = v
    return masked


def mask_payload(payload: Any, depth: int = 0) -> Any:
    """Deep-mask sensitive keys in a dict/list payload."""
    if depth > 10:
        return "..."
    if isinstance(payload, dict):
        result = {}
        for k, v in payload.items():
            if _SENSITIVE_PARAM_PATTERN.search(str(k)):
                result[k] = "****"
            else:
                result[k] = mask_payload(v, depth + 1)
        return result
    if isinstance(payload, (list, tuple)):
        return [mask_payload(item, depth + 1) for item in payload]
    return payload


def sanitize_request(method: str, url: str,
                     headers: Optional[dict] = None,
                     body: Optional[Any] = None) -> Dict[str, Any]:
    """Build a sanitized request summary for logging/display."""
    result: Dict[str, Any] = {
        "method": method.upper(),
        "url": mask_url(url),
    }
    if headers:
        result["headers"] = mask_headers(headers)
    if body is not None:
        result["body"] = mask_payload(body)
    return result


def sanitize_response(status_code: int,
                      body: Optional[Any] = None,
                      summary: str = "",
                      truncate_body: int = 500) -> Dict[str, Any]:
    """Build a sanitized response summary for logging/display."""
    result: Dict[str, Any] = {
        "status": status_code,
    }
    if summary:
        result["summary"] = summary
    if body is not None:
        if isinstance(body, dict):
            result["body"] = mask_payload(body)
        elif isinstance(body, str):
            result["body"] = body[:truncate_body]
        else:
            result["body"] = str(body)[:truncate_body]
    return result
