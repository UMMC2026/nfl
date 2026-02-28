"""Dashboard auth utilities.

Phase 5D: lightweight protection for API endpoints.

This is intentionally simple:
- If DASHBOARD_PUBLIC=1 -> allow all.
- Else if DASHBOARD_API_KEY is set -> require X-API-Key header match.

No external deps.
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Callable, TypeVar, Any

from flask import request, jsonify


F = TypeVar("F", bound=Callable[..., Any])


def _truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def require_api_key(fn: F) -> F:
    """Flask decorator to guard API endpoints."""

    @wraps(fn)
    def _wrapped(*args, **kwargs):
        if _truthy(os.getenv("DASHBOARD_PUBLIC")):
            return fn(*args, **kwargs)

        expected = (os.getenv("DASHBOARD_API_KEY") or "").strip()
        if not expected:
            # No key configured -> behave like public mode, but explicit.
            return fn(*args, **kwargs)

        provided = (request.headers.get("X-API-Key") or "").strip()
        if provided != expected:
            return jsonify({"error": "unauthorized"}), 401

        return fn(*args, **kwargs)

    return _wrapped  # type: ignore[return-value]
