"""
API Health Monitoring & Confidence Scaling
SOP v2.2: API failures → explicit confidence compression (not silent)
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ========== API HEALTH STATE ==========

_API_HEALTH_STATE = {
    "nba_api_failures": 0,
    "nba_api_successes": 0,
    "last_failure_time": None,
    "degradation_reason": None,
}


@dataclass
class APIHealthResult:
    """Machine-readable API health assessment."""
    health: float  # 0.0-1.0
    status: str  # HEALTHY, DEGRADED, CRITICAL
    failures: int
    successes: int
    degradation_reason: Optional[str]
    confidence_multiplier: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_health": round(self.health, 3),
            "api_status": self.status,
            "api_failures": self.failures,
            "api_successes": self.successes,
            "degradation_reason": self.degradation_reason,
            "confidence_multiplier": round(self.confidence_multiplier, 3)
        }


def record_api_success():
    """Record a successful API call."""
    _API_HEALTH_STATE["nba_api_successes"] += 1


def record_api_failure(reason: str = "Unknown"):
    """Record a failed API call."""
    _API_HEALTH_STATE["nba_api_failures"] += 1
    _API_HEALTH_STATE["last_failure_time"] = datetime.now()
    _API_HEALTH_STATE["degradation_reason"] = reason


def reset_api_health():
    """Reset API health counters (call at start of each slate)."""
    global _API_HEALTH_STATE
    _API_HEALTH_STATE = {
        "nba_api_failures": 0,
        "nba_api_successes": 0,
        "last_failure_time": None,
        "degradation_reason": None,
    }


def compute_api_health(
    nba_api_failures: Optional[int] = None,
    max_failures: int = 10
) -> APIHealthResult:
    """
    Compute API health score and confidence multiplier.
    
    Health calculation:
        health = 1.0 - (failures / max_failures)
        Floor at 0.5 to prevent total confidence collapse
    
    Confidence multiplier:
        - Health >= 0.9: 1.0 (no penalty)
        - Health 0.7-0.9: 0.9-1.0 (mild penalty)
        - Health 0.5-0.7: 0.75-0.9 (significant penalty)
        - Health < 0.5: 0.75 floor
    """
    if nba_api_failures is None:
        nba_api_failures = _API_HEALTH_STATE["nba_api_failures"]
    
    successes = _API_HEALTH_STATE["nba_api_successes"]
    degradation_reason = _API_HEALTH_STATE["degradation_reason"]
    
    # Compute raw health
    health = 1.0 - (nba_api_failures / max_failures)
    health = max(0.5, min(1.0, health))  # Floor at 0.5
    
    # Determine status
    if health >= 0.9:
        status = "HEALTHY"
    elif health >= 0.7:
        status = "DEGRADED"
    else:
        status = "CRITICAL"
    
    # Compute confidence multiplier
    if health >= 0.9:
        confidence_multiplier = 1.0
    elif health >= 0.7:
        # Linear scale from 0.9 to 1.0
        confidence_multiplier = 0.9 + (health - 0.7) * 0.5
    else:
        # Linear scale from 0.75 to 0.9
        confidence_multiplier = 0.75 + (health - 0.5) * 0.75
    
    result = APIHealthResult(
        health=health,
        status=status,
        failures=nba_api_failures,
        successes=successes,
        degradation_reason=degradation_reason,
        confidence_multiplier=confidence_multiplier
    )
    
    if status != "HEALTHY":
        logger.warning(f"API Health: {status} ({health:.0%}) | Confidence multiplier: {confidence_multiplier:.2f}")
    
    return result


def scale_confidence(raw_confidence: float, api_health: float) -> float:
    """
    Scale confidence by API health.
    
    Args:
        raw_confidence: Original confidence (0-100 or 0-1)
        api_health: API health score (0-1)
    
    Returns:
        Scaled confidence in same unit as input
    """
    # Detect unit (0-1 vs 0-100)
    if raw_confidence > 1:
        # Percentage (0-100)
        return round(raw_confidence * api_health, 3)
    else:
        # Decimal (0-1)
        return round(raw_confidence * api_health, 5)


def get_api_health_context() -> Dict[str, Any]:
    """Get current API health context for reporting."""
    result = compute_api_health()
    return result.to_dict()
