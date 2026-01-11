# engine/validation_guard.py

from pathlib import Path
from datetime import datetime, timedelta
import json
import csv

VALIDATED_PATH = Path("outputs/validated_primary_edges.json")
AUDIT_PATH = Path("outputs/audit_pipeline_failures.csv")

DEFAULT_TTL_MINUTES = 30


class ValidationError(RuntimeError):
    pass


def _now():
    return datetime.utcnow()


def ensure_validated_exists():
    if not VALIDATED_PATH.exists():
        raise ValidationError(
            "Validated output missing. Run daily_pipeline.py first."
        )


def ensure_fresh(ttl_minutes: int = DEFAULT_TTL_MINUTES):
    mtime = datetime.fromtimestamp(VALIDATED_PATH.stat().st_mtime)
    age = _now() - mtime

    if age > timedelta(minutes=ttl_minutes):
        raise ValidationError(
            f"Validated output is stale ({int(age.total_seconds() // 60)} min old). "
            f"TTL={ttl_minutes} minutes."
        )


def load_validated(ttl_minutes: int = DEFAULT_TTL_MINUTES):
    ensure_validated_exists()
    ensure_fresh(ttl_minutes)

    with open(VALIDATED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        raise ValidationError("Validated output is empty.")

    return data


def audit_pipeline_failure(reason: str, stage: str = "UNKNOWN"):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = AUDIT_PATH.exists()

    with open(AUDIT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp_utc", "stage", "reason"])
        writer.writerow([
            _now().isoformat(),
            stage,
            reason
        ])
