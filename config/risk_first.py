from __future__ import annotations

from pathlib import Path
import json

_CONFIG_PATH = Path("config") / "risk_first_config.json"


def is_risk_first_enabled() -> bool:
    """Return whether risk-first governance is enabled.

    Fail-safe behavior: if the config file is missing or invalid,
    default to True so we never accidentally run in ungoverned mode.
    """
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("risk_first_enabled", True))
    except Exception:
        return True


def set_risk_first_enabled(enabled: bool) -> None:
    """Persist the risk-first flag to the config file.

    This is the single writer for ``risk_first_config.json`` so that
    CLI helpers and the pipeline share the same source of truth.
    """
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {"risk_first_enabled": bool(enabled)}
        with _CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        # Writing the config should never break the pipeline/menu.
        # Fail silently; callers can still rely on the fail-safe
        # behaviour of ``is_risk_first_enabled``.
        pass


def toggle_risk_first() -> bool:
    """Flip the risk-first flag and return the new value.

    If the config file is missing/invalid, we assume the current
    value is ``True`` (governed by default) and flip it to ``False``.
    """
    current = is_risk_first_enabled()
    new_value = not current
    set_risk_first_enabled(new_value)
    return new_value
