"""Shared sanitization for request data before storage."""
from typing import Any, Dict

SENSITIVE_HEADERS = [
    "authorization",
    "cookie",
    "x-api-key",
    "x-auth-token",
    "set-cookie",
]


def sanitize_request(data: dict) -> dict:
    """Redact sensitive headers in request and response."""
    data = dict(data)
    for key in ("request_headers", "response_headers"):
        headers = data.get(key) or {}
        if isinstance(headers, dict):
            headers = dict(headers)
            for h in list(headers.keys()):
                if h.lower() in SENSITIVE_HEADERS:
                    headers[h] = "***REDACTED***"
            data[key] = headers
    return data
