"""
JIGGY Mode Isolation
====================

When JIGGY (UNGOVERNED) mode is active:
- Probability lineage tracking is DISABLED
- Calibration updates are DISABLED
- All outputs are tagged as UNGOVERNED
- Learning/model updates are BLOCKED

This prevents manual/exploratory analysis from contaminating
the calibrated model.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(".analyzer_settings.json")


def is_jiggy_mode() -> bool:
    """Check if JIGGY (ungoverned) mode is currently active."""
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, 'r') as f:
                settings = json.load(f)
                return settings.get("jiggy", False)
    except Exception:
        pass
    return False


def tag_output_ungoverned(output: Dict[str, Any]) -> Dict[str, Any]:
    """Tag output as UNGOVERNED if JIGGY mode is active."""
    if is_jiggy_mode():
        output["_governance"] = {
            "mode": "UNGOVERNED",
            "jiggy_active": True,
            "lineage_tracked": False,
            "calibration_eligible": False,
            "warning": "This output was generated in JIGGY mode and should NOT be used for calibration or model learning."
        }
        logger.warning("Output tagged as UNGOVERNED (JIGGY mode active)")
    else:
        output["_governance"] = {
            "mode": "GOVERNED",
            "jiggy_active": False,
            "lineage_tracked": True,
            "calibration_eligible": True,
        }
    return output


def block_if_jiggy(func):
    """Decorator to block function execution if JIGGY mode is active."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_jiggy_mode():
            logger.warning(f"BLOCKED: {func.__name__} cannot run in JIGGY mode")
            return None
        return func(*args, **kwargs)
    return wrapper


def warn_if_jiggy(func):
    """Decorator to warn but allow execution if JIGGY mode is active."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_jiggy_mode():
            logger.warning(f"WARNING: {func.__name__} running in JIGGY mode - results are UNGOVERNED")
        return func(*args, **kwargs)
    return wrapper


class JiggyGuard:
    """
    Context manager for JIGGY-safe operations.
    
    Usage:
        with JiggyGuard() as guard:
            if guard.can_track_lineage:
                tracer.record_adjustment(...)
            if guard.can_update_calibration:
                calibration.update(...)
    """
    
    def __init__(self):
        self.is_jiggy = is_jiggy_mode()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    
    @property
    def can_track_lineage(self) -> bool:
        """Whether probability lineage tracking is allowed."""
        return not self.is_jiggy
    
    @property
    def can_update_calibration(self) -> bool:
        """Whether calibration updates are allowed."""
        return not self.is_jiggy
    
    @property
    def can_export_official(self) -> bool:
        """Whether outputs can be exported to official reports."""
        return not self.is_jiggy
    
    @property
    def mode_label(self) -> str:
        """Get the current mode label for outputs."""
        return "UNGOVERNED" if self.is_jiggy else "GOVERNED"


# Convenience functions for checking governance status
def get_governance_status() -> Dict[str, Any]:
    """Get full governance status for current session."""
    guard = JiggyGuard()
    return {
        "mode": guard.mode_label,
        "jiggy_active": guard.is_jiggy,
        "lineage_enabled": guard.can_track_lineage,
        "calibration_enabled": guard.can_update_calibration,
        "official_export_enabled": guard.can_export_official,
    }


def print_governance_banner():
    """Print governance status banner."""
    status = get_governance_status()
    if status["jiggy_active"]:
        print("\n⚠️  JIGGY MODE ACTIVE — UNGOVERNED OUTPUT")
        print("    Lineage: OFF | Calibration: OFF | Learning: BLOCKED")
    else:
        print("\n✓ Governance: FULL — All systems active")
