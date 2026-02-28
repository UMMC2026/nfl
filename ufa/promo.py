"""Promo / trial logic.

Goal: allow a time-boxed "free month" where everyone is treated like a subscriber.

This module is intentionally dependency-light (no DB imports) so it can be used
from CLI scripts, FastAPI middleware, and Telegram bots.

Activation rules:
- Set env PROMO_FREE_MONTH=1 (or UFA_PROMO_FREE_MONTH=1)
- Optionally set PROMO_FREE_MONTH_DAYS (default: 30)
- Optionally set PROMO_FREE_MONTH_END_UTC (ISO 8601 date/datetime). If set, it
  overrides the computed end time.

If enabled and no explicit end is provided, the promo start timestamp is
persisted to runtime/promo_state.json so restarts do not extend the window.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "runtime"
_STATE_FILE = _RUNTIME_DIR / "promo_state.json"


def _env_truthy(name: str) -> bool:
    v = os.getenv(name)
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def promo_enabled() -> bool:
    return _env_truthy("PROMO_FREE_MONTH") or _env_truthy("UFA_PROMO_FREE_MONTH")


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_iso_datetime_utc(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        # Accept date-only (YYYY-MM-DD) or full ISO datetime.
        if len(raw) == 10:
            dt = datetime.fromisoformat(raw)
            return dt.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _load_or_init_start_utc(now_utc: datetime) -> datetime:
    """Return persisted start timestamp (UTC), initializing if missing."""
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            started_raw = str(data.get("started_utc") or "")
            started = _parse_iso_datetime_utc(started_raw)
            if started:
                return started
        except Exception:
            # Best-effort only; fall through to re-init.
            pass

    started = now_utc
    try:
        _STATE_FILE.write_text(
            json.dumps({"started_utc": started.isoformat().replace("+00:00", "Z")}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        # Best-effort only.
        pass

    return started


@dataclass(frozen=True)
class PromoWindow:
    enabled: bool
    started_utc: Optional[datetime]
    ends_utc: Optional[datetime]

    @property
    def active(self) -> bool:
        if not self.enabled:
            return False
        if not self.ends_utc:
            return False
        return datetime.now(timezone.utc) < self.ends_utc


def get_promo_window(now_utc: Optional[datetime] = None) -> PromoWindow:
    """Compute the promo window."""
    if not promo_enabled():
        return PromoWindow(enabled=False, started_utc=None, ends_utc=None)

    now_utc = now_utc or datetime.now(timezone.utc)

    explicit_end = _parse_iso_datetime_utc(
        os.getenv("PROMO_FREE_MONTH_END_UTC") or os.getenv("UFA_PROMO_FREE_MONTH_END_UTC") or ""
    )
    if explicit_end:
        started = None
        return PromoWindow(enabled=True, started_utc=started, ends_utc=explicit_end)

    days = _parse_int("PROMO_FREE_MONTH_DAYS", _parse_int("UFA_PROMO_FREE_MONTH_DAYS", 30))
    started = _load_or_init_start_utc(now_utc)
    ends = started + timedelta(days=max(days, 1))
    return PromoWindow(enabled=True, started_utc=started, ends_utc=ends)


def effective_tier(default_tier: str, promo_tier: str = "pro") -> str:
    """Return promo_tier if promo is active, else default_tier.

    This helper is intentionally string-based so it can work with both:
    - the lightweight Stripe sqlite tiering ("starter"/"pro"/"whale")
    - future enum-based tiers.
    """
    window = get_promo_window()
    return promo_tier if window.active else default_tier
