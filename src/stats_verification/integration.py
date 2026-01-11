"""
Integration of Delayed Verification with existing prop system
"""

import sys
from pathlib import Path
from typing import Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.stats_verification.delayed_verification import (
    DelayedVerificationSystem, ConfidenceLevel,
)

# Global verification system instance
_VERIFICATION_SYSTEM = None


def get_verification_system() -> DelayedVerificationSystem:
    """Get or create the global verification system"""
    global _VERIFICATION_SYSTEM
    if _VERIFICATION_SYSTEM is None:
        _VERIFICATION_SYSTEM = DelayedVerificationSystem()
        # Start background verification
        _VERIFICATION_SYSTEM.start_background_verification()
    return _VERIFICATION_SYSTEM


# ==================== INTEGRATION WITH CHEATSHEET GENERATION ====================


def integrate_with_cheatsheet():
    """Placeholder docstring for integrating with generate_cheatsheet.py.

    See delayed_verification system docs for how to wire this into probability
    calculation. This function is intentionally not executed; it serves as
    inline guidance.
    """
    pass


# ==================== INTEGRATION WITH LEARNING SYSTEM ====================


def integrate_with_learning():
    """Placeholder docstring for integrating with the learning gate.

    In your learning/verification modules, prefer checking verification_system
    .verified_stats before treating a game as learnable.
    """
    pass


# ==================== DEGRADED MODE INTEGRATION ====================


def integrate_degraded_with_verification():
    """Placeholder for combining degraded mode with verification system.

    In degraded mode, you can call verification_system.get_player_stats(...,
    immediate_only=True) and then apply extra conservative caps when the
    returned confidence is 'conservative'.
    """
    pass


# ==================== UTILITY FUNCTIONS ====================


def wait_for_verification(request_id: str, timeout_minutes: int = 30):
    """Wait for verification to complete (blocking helper).

    Useful for critical picks that need fully verified stats.
    """
    verification_system = get_verification_system()

    import time as _time

    start_time = _time.time()
    timeout_seconds = timeout_minutes * 60

    while _time.time() - start_time < timeout_seconds:
        # Check request status
        with verification_system.lock:
            if request_id in verification_system.active_requests:
                request = verification_system.active_requests[request_id]
                if request.status.value in ['verified', 'failed', 'timeout']:
                    return request

        _time.sleep(5)  # Check every 5 seconds

    return None  # Timeout


def get_verified_stats_for_date(game_date: str) -> Dict:
    """Get all verified stats for a specific date.

    Useful for end-of-day reconciliation.
    """
    verification_system = get_verification_system()

    verified_stats: Dict[str, Dict] = {}
    with verification_system.lock:
        for key, stats in verification_system.verified_stats.items():
            if game_date in key:
                verified_stats[key] = stats

    return verified_stats


def reconcile_pending_verifications() -> int:
    """Manually trigger reconciliation of all pending verifications.

    Forces all pending requests to the front of the queue. The background
    worker will then attempt verification.
    """
    verification_system = get_verification_system()

    # Force verify all pending requests
    with verification_system.lock:
        pending_requests = [
            r for r in verification_system.active_requests.values()
            if r.status.value == 'pending'
        ]

    for request in pending_requests:
        verification_system.force_verify_request(request.request_id)

    return len(pending_requests)
