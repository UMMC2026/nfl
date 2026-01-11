# utils/freshness.py
from pathlib import Path
from datetime import datetime, timedelta

TTL_MINUTES = 30


def assert_fresh(path: str, max_age: int | None = None):
    """Assert that a file exists and is not older than `max_age` minutes.

    If max_age is None, uses the module TTL_MINUTES default.
    """
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"Required output missing: {path}")

    if max_age is None:
        max_age = TTL_MINUTES

    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    if age > timedelta(minutes=max_age):
        raise RuntimeError(
            f"Output stale: {path} is {age.seconds // 60} minutes old (max {max_age} min)"
        )
