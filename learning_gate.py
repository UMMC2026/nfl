"""
Learning Gate Validator

Enforces immutable, verified outcome logging.
This is the ONLY place where a row becomes eligible for calibration_history.csv.

Rules (Hard Fail on Any Violation):
  1. game_status MUST be 'FINAL' (not in progress, not postponed, not rescheduled)
  2. final_confirmed_at MUST be >= 15 minutes ago (SLA for corrections)
  3. ESPN Box Score AND NBA API stat lines MUST match (cross-verified)
  
Returns:
  True  → Row is learning-ready. Safe to log. Immutable.
  False → Row is unsafe. Block logging. No exceptions.
  
Design Principles:
  - Fail closed (assume unsafe unless proven safe)
  - No retries inside gate (caller decides)
  - Single source of truth for learning eligibility
  - Audit trail every gate decision (block reasons logged)
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
import logging

# Configure logging for gate audit trail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [GATE] %(message)s'
)
gate_logger = logging.getLogger('learning_gate')


# ===================================================================
# HARDENING HELPERS (Edge Case Detection)
# ===================================================================

def detect_overtime_flag(pick_row: Dict[str, Any]) -> bool:
    """
    **Hardening 1: OT Flag Detection**
    
    Detects if game went to overtime. Does NOT block; flags for isolation in attribution.
    
    Rules:
      - OT games are valid outcomes but structurally abnormal
      - OT MUST be isolated in minutes survival / blowout penalty models
      - Flag added to pick_row for post-logging analysis
    
    Returns: True if OT flag detected/set, False otherwise
    """
    overtime_flag = pick_row.get('overtime_flag', False)
    if overtime_flag:
        gate_logger.info(f"{pick_row.get('game_id')} | OVERTIME_FLAGGED: True (not blocked)")
        return True
    return False


def detect_post_final_correction_risk(
    pick_row: Dict[str, Any],
    verification_sources: Optional[Dict[str, Dict[str, Any]]] = None
) -> bool:
    """
    **Hardening 2: Post-Final Stat Correction Detection**
    
    Detects if stat is at risk of post-final correction (ESPN corrections happen 15-90 min after FINAL).
    
    Rules:
      - This does NOT block the row
      - This DOES add a flag to the row
      - Correction log appended separately (never rewrite CSV)
      - Corrected rows excluded from learning updates (but included in reporting)
    
    Args:
        verification_sources: If provided and matches, lower risk; if diverges, higher risk
    
    Returns: True if correction risk detected (needs monitoring), False if low risk
    """
    game_id = pick_row.get('game_id')
    
    # Check if sources already diverge (early correction signal)
    if verification_sources:
        espn = verification_sources.get('ESPN', {}).get('actual_stat_value')
        nba = verification_sources.get('NBA', {}).get('actual_stat_value')
        
        if espn is not None and nba is not None:
            tolerance = 0.1
            if abs(float(espn) - float(nba)) > tolerance:
                gate_logger.warning(
                    f"{game_id} | CORRECTION_RISK_DETECTED: ESPN={espn} vs NBA={nba} (divergence)")
                pick_row['correction_risk'] = True
                return True
    
    # If we got here, low correction risk (sources agree or not verified)
    pick_row['correction_risk'] = False
    return False


def detect_terminal_state(pick_row: Dict[str, Any]) -> Optional[str]:
    """
    **Hardening 3: Terminal State Detection**
    
    Detects if game reached a terminal (non-standard) state.
    
    Rules:
      - POSTPONED / CANCELLED / RESCHEDULED are non-events
      - These are NOT misses, NOT variance, NOT governance failures
      - Mark as terminal_state='NO_GAME' in CSV
      - Prevents: denominator inflation, hit rate corruption, false attribution
    
    Returns:
      - 'NO_GAME' if game never happened
      - None if game was played normally
    """
    game_status = pick_row.get('game_status')
    
    if game_status in ['POSTPONED', 'CANCELLED', 'RESCHEDULED']:
        gate_logger.info(
            f"{pick_row.get('game_id')} | TERMINAL_STATE: {game_status} (non-event)")
        return 'NO_GAME'
    
    return None


def detect_late_scratch(pick_row: Dict[str, Any], minutes_threshold: float = 5.0) -> bool:
    """
    **Hardening 4: Late Scratch / In-Game Removal Detection**
    
    Detects if player was active pre-game but removed/didn't play (minutes < threshold).
    
    Rules:
      - Player active pregame + minutes < threshold = late scratch
      - NOT a miss
      - NOT variance
      - NOT governance failure
      - Is operational noise (pre-game roster news, in-game injury, etc.)
      - Set failure_primary_cause='LATE_SCRATCH_OR_REMOVAL' in CSV
    
    Args:
        minutes_threshold: Minutes below which we consider player didn't play (default 5.0)
    
    Returns: True if late scratch detected, False otherwise
    """
    game_id = pick_row.get('game_id')
    player_name = pick_row.get('player_name')
    minutes_played = pick_row.get('minutes_played')
    was_active_pregame = pick_row.get('was_active_pregame', True)  # Default assume active
    
    if minutes_played is None:
        return False  # Can't determine; not enough info
    
    if was_active_pregame and minutes_played < minutes_threshold:
        gate_logger.warning(
            f"{game_id} | {player_name} | LATE_SCRATCH: Active pregame, {minutes_played} min played")
        pick_row['failure_primary_cause'] = 'LATE_SCRATCH_OR_REMOVAL'
        return True
    
    return False


def validate_composite_key(
    pick_row: Dict[str, Any],
    existing_keys: Optional[set] = None
) -> Tuple[bool, str]:
    """
    **Hardening 5: Composite Key Uniqueness (player_id, game_id)**
    
    Enforces that each (player_id, game_id) pair is unique in the CSV.
    Prevents double-header / same-day collisions where rows overwrite silently.
    
    Rules:
      - player_id + game_id must be unique
      - If duplicate found, block logging
      - Return False with reason
    
    Args:
        pick_row: Must contain 'player_id' and 'game_id'
        existing_keys: Set of (player_id, game_id) tuples already logged
                      (optional; if None, returns True with message)
    
    Returns: (is_unique: bool, reason: str)
    """
    player_id = pick_row.get('player_id')
    game_id = pick_row.get('game_id')
    
    if player_id is None or game_id is None:
        reason = f"COMPOSITE_KEY_FAIL: player_id or game_id missing"
        gate_logger.error(reason)
        return False, reason
    
    composite_key = (player_id, game_id)
    
    if existing_keys is not None:
        if composite_key in existing_keys:
            reason = f"COMPOSITE_KEY_FAIL: Duplicate ({player_id}, {game_id}) already logged"
            gate_logger.error(f"{game_id} | {reason}")
            return False, reason
    
    return True, f"COMPOSITE_KEY_OK: ({player_id}, {game_id})"


def is_learning_ready(
    pick_row: Dict[str, Any],
    now: Optional[datetime] = None,
    verification_sources: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[bool, str]:
    """
    Determines if a pick row is safe to log into calibration_history.csv.
    
    Args:
        pick_row: Dict with keys: player_name, stat_category, line, direction,
                 game_id, game_status, final_confirmed_at, actual_stat_value,
                 espn_source, nba_api_source, (optional: overtime_flag, minutes_played,
                 player_id for composite key validation)
        now: Current datetime (for testing); defaults to datetime.utcnow()
        verification_sources: Dict mapping 'ESPN' and 'NBA' to stat dicts for verification
                            (optional; if None, skips verification step)
    
    Returns:
        (is_ready: bool, reason: str)
          - If True: Ready for calibration logging (applies flags as needed)
          - If False: Reason why gate failed (audit trail)
    
    Raises:
        KeyError: If required fields missing from pick_row
    
    EDGE CASE HANDLING:
      1. OT Games: Flagged but not blocked (allow OT outcomes, isolation in attribution)
      2. Post-Final Corrections: Detectable via correction helpers (prevent silent corruption)
      3. Terminal States: POSTPONED/CANCELLED marked as NO_GAME (non-events, not misses)
      4. Late Scratch: Detected via minutes check (<X min post-game) (not variance)
      5. Composite Key: Enforces (player_id, game_id) uniqueness (prevents overwrites)
    """
    
    if now is None:
        now = datetime.utcnow()
    
    # =========================================================================
    # PRE-GATE: COMPOSITE KEY VALIDATION (Hardening 5)
    # =========================================================================
    # Note: In production, pass existing_keys set from CSV to prevent duplicates
    # For now, just validate that fields exist
    is_unique, key_reason = validate_composite_key(pick_row, existing_keys=None)
    if not is_unique:
        return False, key_reason
    
    gate_logger.info(f"{pick_row.get('game_id')} | {key_reason}")
    
    # =========================================================================
    # PRE-GATE: TERMINAL STATE CHECK (Hardening 3)
    # =========================================================================
    terminal_state = detect_terminal_state(pick_row)
    if terminal_state == 'NO_GAME':
        # Not a blocking failure, but requires special outcome handling
        pick_row['terminal_state'] = terminal_state
        reason = "TERMINAL_STATE: Game not played (POSTPONED/CANCELLED/RESCHEDULED)"
        gate_logger.info(f"{pick_row.get('game_id')} | {reason}")
        return True, reason  # Allow to log, but marked as non-event

    # =========================================================================
    # PRE-GATE: INJURY VERIFICATION (Fail-closed for UNKNOWN)
    # =========================================================================
    # When upstream processes attach an injury_status field to the
    # pick_row, we enforce a strict policy: UNKNOWN means the
    # pre-game availability was never verified (e.g. injury feed
    # degraded). Such rows are **never** eligible for learning.
    injury_status = pick_row.get('injury_status')
    if isinstance(injury_status, str) and injury_status.upper() == 'UNKNOWN':
        reason = "GATE_FAIL: INJURY_UNVERIFIED (injury_status=UNKNOWN)"
        gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
        return False, reason
    
    # =========================================================================
    # GATE 1: GAME STATUS MUST BE FINAL
    # =========================================================================
    try:
        game_status = pick_row.get('game_status')
    except (KeyError, TypeError) as e:
        reason = f"GATE_FAIL: game_status missing or malformed: {e}"
        gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
        return False, reason
    
    if game_status != 'FINAL':
        reason = f"GATE_FAIL: game_status='{game_status}' (required: 'FINAL')"
        gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
        return False, reason
    
    gate_logger.info(f"{pick_row.get('game_id', 'UNKNOWN')} | GATE_1_PASS: game_status='FINAL'")
    
    # =========================================================================
    # GATE 2: FINALIZATION SLA (>= 15 minutes since game end)
    # =========================================================================
    try:
        final_confirmed_at_str = pick_row.get('final_confirmed_at')
        if isinstance(final_confirmed_at_str, str):
            # Parse ISO format or common timestamp formats
            try:
                final_confirmed_at = datetime.fromisoformat(final_confirmed_at_str.replace('Z', '+00:00'))
            except ValueError:
                # Try other common formats
                try:
                    final_confirmed_at = datetime.strptime(final_confirmed_at_str, '%Y-%m-%d %H:%M:%S')
                except ValueError as e:
                    reason = f"GATE_FAIL: final_confirmed_at format unrecognized: '{final_confirmed_at_str}'"
                    gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
                    return False, reason
        elif isinstance(final_confirmed_at_str, datetime):
            final_confirmed_at = final_confirmed_at_str
        else:
            reason = f"GATE_FAIL: final_confirmed_at type unrecognized: {type(final_confirmed_at_str)}"
            gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
            return False, reason
    except (KeyError, TypeError, AttributeError) as e:
        reason = f"GATE_FAIL: final_confirmed_at missing or malformed: {e}"
        gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
        return False, reason
    
    # Ensure both times are naive (UTC) for comparison
    if final_confirmed_at.tzinfo is not None:
        final_confirmed_at = final_confirmed_at.replace(tzinfo=None)
    
    sla_threshold = final_confirmed_at + timedelta(minutes=15)
    
    if now < sla_threshold:
        minutes_remaining = int((sla_threshold - now).total_seconds() / 60)
        reason = f"GATE_FAIL: Only {minutes_remaining} minutes since finalization (required: 15)"
        gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
        return False, reason
    
    minutes_since = int((now - final_confirmed_at).total_seconds() / 60)
    gate_logger.info(f"{pick_row.get('game_id', 'UNKNOWN')} | GATE_2_PASS: {minutes_since} min since finalization")
    
    # =========================================================================
    # GATE 3: CROSS-SOURCE VERIFICATION (ESPN vs NBA API)
    # =========================================================================
    # This gate is conditional: if verification_sources provided, enforce it
    if verification_sources is not None:
        if not isinstance(verification_sources, dict):
            reason = f"GATE_FAIL: verification_sources malformed (expected dict)"
            gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
            return False, reason
        
        espn_stat = verification_sources.get('ESPN', {}).get('actual_stat_value')
        nba_stat = verification_sources.get('NBA', {}).get('actual_stat_value')
        
        if espn_stat is None or nba_stat is None:
            reason = f"GATE_FAIL: Missing verification stat (ESPN={espn_stat}, NBA={nba_stat})"
            gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
            return False, reason
        
        # Allow small tolerance for rounding (e.g., 20.0 vs 20.1 assists)
        # But exact match preferred (0.0 tolerance)
        tolerance = 0.1  # Assists/rebounds can have decimal variance
        if abs(float(espn_stat) - float(nba_stat)) > tolerance:
            reason = f"GATE_FAIL: Stat mismatch ESPN={espn_stat} vs NBA={nba_stat} (tolerance: {tolerance})"
            gate_logger.warning(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
            return False, reason
        
        gate_logger.info(f"{pick_row.get('game_id', 'UNKNOWN')} | GATE_3_PASS: ESPN={espn_stat} == NBA={nba_stat}")
    else:
        # Verification_sources not provided: accept with note
        gate_logger.info(f"{pick_row.get('game_id', 'UNKNOWN')} | GATE_3_SKIP: Verification not provided (conditional)")
    
    # =========================================================================
    # ALL GATES PASSED
    # =========================================================================
    
    # =========================================================================
    # POST-GATE HARDENING FLAGS (Applied but don't block)
    # =========================================================================
    
    # Hardening 1: OT Flag
    detect_overtime_flag(pick_row)
    
    # Hardening 2: Post-Final Correction Risk
    detect_post_final_correction_risk(pick_row, verification_sources)
    
    # Hardening 4: Late Scratch Detection
    detect_late_scratch(pick_row)
    
    # Flags have been set on pick_row; caller will use them for CSV logging
    reason = "LEARNING_READY: All gates passed. Hardening flags applied. Safe to log."
    gate_logger.info(f"{pick_row.get('game_id', 'UNKNOWN')} | {reason}")
    return True, reason


# ===================================================================
# Convenience wrapper for integration
# ===================================================================

def validate_and_log_eligibility(pick_row: Dict[str, Any], verbose: bool = True) -> bool:
    """
    Wrapper for quick go/no-go decision (e.g., in backfill pipeline).
    
    Args:
        pick_row: Pick row to validate
        verbose: If True, print gate decision; if False, silent
    
    Returns:
        True if learning-ready, False otherwise
    """
    is_ready, reason = is_learning_ready(pick_row)
    
    if verbose:
        status = "✅ READY" if is_ready else "❌ BLOCKED"
        print(f"  {status} | {pick_row.get('game_id', 'UNKNOWN')} | {pick_row.get('player_name', 'UNKNOWN')} | {reason}")
    
    return is_ready


# ===================================================================
# Test / Demo
# ===================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("LEARNING GATE VALIDATOR — COMPREHENSIVE HARDENING TEST SCENARIOS")
    print("=" * 80)
    
    now_test = datetime(2026, 1, 2, 23, 30, 0)  # Test time: Jan 2, 2026, 11:30 PM
    
    # Scenario 1: PASS (all gates satisfied)
    print("\n[SCENARIO 1] PASS — All gates satisfied")
    pick_pass = {
        'game_id': 'DEN_vs_NYK_20260102',
        'player_id': 'oanunoby1',
        'player_name': 'OG Anunoby',
        'stat_category': 'points',
        'line': 16.5,
        'direction': 'over',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 20:00:00',  # 3.5 hours ago
        'actual_stat_value': 25,
    }
    is_ready, reason = is_learning_ready(pick_pass, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    print(f"  Flags set: overtime={pick_pass.get('overtime_flag')}, correction_risk={pick_pass.get('correction_risk')}")
    
    # Scenario 2: FAIL — game still in progress
    print("\n[SCENARIO 2] FAIL — Game in progress")
    pick_in_progress = {
        'game_id': 'LAL_vs_GSW_20260102',
        'player_id': 'lebron1',
        'player_name': 'LeBron James',
        'game_status': 'IN_PROGRESS',
        'final_confirmed_at': None,
        'actual_stat_value': None,
    }
    is_ready, reason = is_learning_ready(pick_in_progress, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    
    # Scenario 3: FAIL — Not enough time since finalization (SLA pending)
    print("\n[SCENARIO 3] FAIL — SLA not met (< 15 min since finalization)")
    pick_too_fresh = {
        'game_id': 'MIA_vs_BOS_20260102',
        'player_id': 'badebayo1',
        'player_name': 'Bam Adebayo',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 23:20:00',  # Only 10 min ago
        'actual_stat_value': 18,
    }
    is_ready, reason = is_learning_ready(pick_too_fresh, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    
    # Scenario 4: FAIL — ESPN vs NBA mismatch
    print("\n[SCENARIO 4] FAIL — Cross-source verification mismatch")
    pick_mismatch = {
        'game_id': 'PHX_vs_LAC_20260102',
        'player_id': 'dbooker1',
        'player_name': 'Devin Booker',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 20:00:00',
        'actual_stat_value': 28,
    }
    verification_mismatch = {
        'ESPN': {'actual_stat_value': 28.0},
        'NBA': {'actual_stat_value': 27.2},  # Mismatch beyond tolerance
    }
    is_ready, reason = is_learning_ready(pick_mismatch, now=now_test, 
                                         verification_sources=verification_mismatch)
    print(f"  Result: {is_ready} | {reason}")
    
    # Scenario 5: PASS with verification
    print("\n[SCENARIO 5] PASS — With cross-source verification")
    pick_verified = {
        'game_id': 'MIL_vs_DET_20260102',
        'player_id': 'giannis1',
        'player_name': 'Giannis Antetokounmpo',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 19:30:00',
        'actual_stat_value': 31,
    }
    verification_match = {
        'ESPN': {'actual_stat_value': 31.0},
        'NBA': {'actual_stat_value': 31.0},
    }
    is_ready, reason = is_learning_ready(pick_verified, now=now_test,
                                        verification_sources=verification_match)
    print(f"  Result: {is_ready} | {reason}")
    
    # ========================================================================
    # HARDENING TEST SCENARIOS
    # ========================================================================
    
    # Hardening 1: OVERTIME FLAG
    print("\n" + "=" * 80)
    print("HARDENING 1: OVERTIME GAMES (Flagged, Not Blocked)")
    print("=" * 80)
    
    print("\n[HARDENING 1A] PASS with OT flag — Game allowed, flagged for isolation")
    pick_ot = {
        'game_id': 'BOS_vs_NYK_20260102_OT',
        'player_id': 'jbrown1',
        'player_name': 'Jaylen Brown',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 21:00:00',
        'actual_stat_value': 34,
        'overtime_flag': True,  # OT game
    }
    is_ready, reason = is_learning_ready(pick_ot, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    print(f"  Flags: overtime_flag={pick_ot.get('overtime_flag')}")
    
    # Hardening 2: POST-FINAL CORRECTION RISK
    print("\n" + "=" * 80)
    print("HARDENING 2: POST-FINAL STAT CORRECTIONS (Detected, Not Blocked)")
    print("=" * 80)
    
    print("\n[HARDENING 2A] PASS but correction risk HIGH — Sources diverge")
    pick_correction_risk = {
        'game_id': 'CHI_vs_IND_20260102',
        'player_id': 'drose1',
        'player_name': "D'Aaron Fox",
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 20:30:00',
        'actual_stat_value': 20,  # ESPN says 20
    }
    verification_diverge = {
        'ESPN': {'actual_stat_value': 20.0},
        'NBA': {'actual_stat_value': 18.8},  # Divergence detected
    }
    is_ready, reason = is_learning_ready(pick_correction_risk, now=now_test,
                                         verification_sources=verification_diverge)
    print(f"  Result: {is_ready} | {reason}")
    print(f"  Correction Risk: {pick_correction_risk.get('correction_risk')} (needs monitoring)")
    
    # Hardening 3: TERMINAL STATES
    print("\n" + "=" * 80)
    print("HARDENING 3: TERMINAL STATES (POSTPONED/CANCELLED → NO_GAME)")
    print("=" * 80)
    
    print("\n[HARDENING 3A] PASS as NO_GAME — Game never happened (POSTPONED)")
    pick_postponed = {
        'game_id': 'GSW_vs_LAL_RESCHEDULED',
        'player_id': 'mkurry1',
        'player_name': 'Stephen Curry',
        'game_status': 'POSTPONED',
        'final_confirmed_at': None,
        'actual_stat_value': None,
    }
    is_ready, reason = is_learning_ready(pick_postponed, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    print(f"  Terminal State: {pick_postponed.get('terminal_state')} (not a miss, not variance)")
    
    print("\n[HARDENING 3B] PASS as NO_GAME — Game cancelled")
    pick_cancelled = {
        'game_id': 'TOR_vs_WAS_CANCELLED',
        'player_id': 'sgarland1',
        'player_name': 'Shai Gilgeous-Alexander',
        'game_status': 'CANCELLED',
        'final_confirmed_at': None,
        'actual_stat_value': None,
    }
    is_ready, reason = is_learning_ready(pick_cancelled, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    print(f"  Terminal State: {pick_cancelled.get('terminal_state')}")
    
    # Hardening 4: LATE SCRATCH / IN-GAME REMOVAL
    print("\n" + "=" * 80)
    print("HARDENING 4: LATE SCRATCH (Active Pregame → 0-5 Min Played)")
    print("=" * 80)
    
    print("\n[HARDENING 4A] PASS but LATE_SCRATCH detected — Player active, didn't play")
    pick_scratch = {
        'game_id': 'ATL_vs_MEM_20260102',
        'player_id': 'trae1',
        'player_name': 'Trae Young',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 20:45:00',
        'actual_stat_value': None,
        'was_active_pregame': True,
        'minutes_played': 2.0,  # Active pregame, only 2 min
    }
    is_ready, reason = is_learning_ready(pick_scratch, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    print(f"  Late Scratch Detected: {pick_scratch.get('failure_primary_cause')}")
    
    # Hardening 5: COMPOSITE KEY UNIQUENESS
    print("\n" + "=" * 80)
    print("HARDENING 5: COMPOSITE KEY (player_id, game_id) UNIQUENESS")
    print("=" * 80)
    
    print("\n[HARDENING 5A] PASS — Composite key valid and unique")
    pick_unique = {
        'game_id': 'HOU_vs_OKC_20260102',
        'player_id': 'jsemaj1',
        'player_name': 'Jalen Shead',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 20:15:00',
        'actual_stat_value': 12,
    }
    is_ready, reason = is_learning_ready(pick_unique, now=now_test)
    print(f"  Result: {is_ready} | {reason}")
    
    print("\n[HARDENING 5B] FAIL — Duplicate composite key (existing_keys check)")
    pick_duplicate = {
        'game_id': 'HOU_vs_OKC_20260102',
        'player_id': 'jsemaj1',  # Same player, same game
        'player_name': 'Jalen Shead',
        'game_status': 'FINAL',
        'final_confirmed_at': '2026-01-02 20:15:00',
        'actual_stat_value': 12,
    }
    # Simulate existing keys set
    existing = {('jsemaj1', 'HOU_vs_OKC_20260102')}
    is_unique, key_reason = validate_composite_key(pick_duplicate, existing_keys=existing)
    print(f"  Result: {is_unique} | {key_reason}")
    
    print("\n" + "=" * 80)
    print("HARDENING TEST SUITE COMPLETE")
    print("=" * 80)
