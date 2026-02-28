"""
Unified Decision Governance
===========================

SYSTEM FIX: Forces all reports to communicate through authority, not opinion.
Introduces a SINGLE DECISION SPINE that governs eligibility BEFORE optimization or rendering.

CORE RULE (NON-NEGOTIABLE):
    NO pick may enter Monte Carlo or be rendered unless it passes the Eligibility Gate.
    Probability alone is insufficient.

REQUIRED PIPELINE (LOCKED ORDER):
    1. Base Distribution (μ, σ)
    2. Raw Probability (math only)
    3. Structural Adjustments (archetype, role volatility, usage instability, matchup sample size)
    4. Final Probability
    5. ELIGIBILITY GATE ← THIS MODULE (MANDATORY)
    6. Monte Carlo (OPTIMIZABLE ONLY)
    7. Render Reports

SKIPPING STEP 5 IS A SYSTEM FAILURE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Import stat specialist engine for rejection rules
try:
    from core.stat_specialist_engine import (
        StatSpecialist,
        classify_stat_specialist,
        should_reject_pick as engine_should_reject,
        is_flex_banned,
        get_max_legs,
    )
    HAS_SPECIALIST_ENGINE = True
except ImportError:
    HAS_SPECIALIST_ENGINE = False


# =============================================================================
# PICK STATE MACHINE (SINGLE SOURCE OF TRUTH)
# =============================================================================

class PickState(Enum):
    """
    Every pick MUST have exactly one state.
    
    State transitions are ONE-WAY:
        RAW → ADJUSTED → VETTED → OPTIMIZABLE
                           ↓           ↓
                      REJECTED     REJECTED
    
    Once REJECTED, a pick cannot be resurrected.
    """
    RAW = "RAW"               # Parsed, not analyzed
    ADJUSTED = "ADJUSTED"     # Probability computed
    VETTED = "VETTED"         # Structurally reviewed, visible but NOT optimizable
    OPTIMIZABLE = "OPTIMIZABLE"  # Allowed into Monte Carlo
    REJECTED = "REJECTED"     # Dead — cannot appear anywhere in decisions


class RejectionReason(Enum):
    """Canonical rejection reasons for audit trail."""
    LOW_PROBABILITY = "LOW_PROBABILITY"           # < 55%
    HIGH_USAGE_VOLATILITY = "HIGH_USAGE_VOLATILITY"
    BENCH_MICROWAVE_FRAGILE = "BENCH_MICROWAVE_FRAGILE"
    SPECIALIST_OFF_DRIBBLE_LOW_CONFIDENCE = "SPECIALIST_OFF_DRIBBLE_LOW_CONFIDENCE"
    SPECIALIST_BIG_MAN_3PM_LINE_TOO_HIGH = "SPECIALIST_BIG_MAN_3PM_LINE_TOO_HIGH"
    INSUFFICIENT_EDGE = "INSUFFICIENT_EDGE"
    MINUTES_VOLATILITY = "MINUTES_VOLATILITY"
    SMALL_SAMPLE = "SMALL_SAMPLE"
    MANUAL_BAN = "MANUAL_BAN"
    STRUCTURAL_RISK = "STRUCTURAL_RISK"


class VettedReason(Enum):
    """Reasons a pick is VETTED (visible, not optimizable)."""
    FRAGILE_FLAG = "FRAGILE_FLAG"
    MATCHUP_DECAY = "MATCHUP_DECAY"
    COMPOSITE_STAT = "COMPOSITE_STAT"
    THIN_SLATE_CONTEXT = "THIN_SLATE_CONTEXT"


# =============================================================================
# ELIGIBILITY GATE RESULT
# =============================================================================

@dataclass
class EligibilityResult:
    """
    Result of the Eligibility Gate evaluation.
    
    This is the SINGLE SOURCE OF TRUTH for pick eligibility.
    """
    pick_id: str
    state: PickState
    
    # Original values
    original_probability: float
    final_probability: float
    
    # Adjustments applied
    adjustments: List[str] = field(default_factory=list)
    
    # Rejection/vetting details
    rejection_reason: Optional[RejectionReason] = None
    vetted_reason: Optional[VettedReason] = None
    
    # Flags detected
    flags_detected: List[str] = field(default_factory=list)
    
    # Audit trail
    gate_sequence: List[str] = field(default_factory=list)
    
    @property
    def is_optimizable(self) -> bool:
        """Can this pick enter Monte Carlo?"""
        return self.state == PickState.OPTIMIZABLE
    
    @property
    def is_visible(self) -> bool:
        """Can this pick be shown in reports?"""
        return self.state in (PickState.OPTIMIZABLE, PickState.VETTED)
    
    @property
    def is_rejected(self) -> bool:
        """Is this pick dead?"""
        return self.state == PickState.REJECTED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pick_id": self.pick_id,
            "state": self.state.value,
            "original_probability": self.original_probability,
            "final_probability": self.final_probability,
            "adjustments": self.adjustments,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "vetted_reason": self.vetted_reason.value if self.vetted_reason else None,
            "flags_detected": self.flags_detected,
            "gate_sequence": self.gate_sequence,
            "is_optimizable": self.is_optimizable,
            "is_visible": self.is_visible,
        }


# =============================================================================
# ELIGIBILITY GATE (THE FIX)
# =============================================================================

class EligibilityGate:
    """
    The Eligibility Gate is the SINGLE CHECKPOINT between probability calculation
    and Monte Carlo optimization.
    
    Hard rules (apply in this order):
    1. final_probability < 55% → REJECTED
    2. HIGH_USAGE_VOLATILITY flag → REJECTED
    3. Specialist rejects (e.g., BENCH_MICROWAVE on fragile stats; BIG_MAN_3PM at 3.5+)
    4. FRAGILE flag → VETTED (visible, NOT optimizable)
    5. matchup_games < 3 → final_probability *= 0.85, state = VETTED
    6. Otherwise → OPTIMIZABLE
    """
    
    # Configurable thresholds
    MIN_PROBABILITY = 55.0
    MATCHUP_DECAY_FACTOR = 0.85
    MIN_MATCHUP_GAMES = 3
    
    # Stats that are fragile for bench microwave players
    # Production lock-in: bench microwave is rejected on PTS and 3PM.
    BENCH_FRAGILE_STATS = {
        "PTS", "POINTS", "P",
        "3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS",
        "pts", "points", "p", "3pm", "3pt", "3pts", "threes", "three_pointers",
    }
    
    def __init__(
        self,
        min_probability: float = 55.0,
        matchup_decay: float = 0.85,
        min_matchup_games: int = 3,
    ):
        self.min_probability = min_probability
        self.matchup_decay = matchup_decay
        self.min_matchup_games = min_matchup_games
    
    def evaluate(self, pick: Dict[str, Any]) -> EligibilityResult:
        """
        Evaluate a pick through the Eligibility Gate.
        
        This is the MANDATORY checkpoint. No pick proceeds without this.
        
        Args:
            pick: Pick dictionary with probability, flags, archetype, etc.
        
        Returns:
            EligibilityResult with final state and audit trail
        """
        # Extract pick identity
        player = pick.get("player", "Unknown")
        stat = pick.get("stat", pick.get("stat_type", pick.get("market", "?"))).upper()
        line = pick.get("line", 0)
        direction = pick.get("direction", "?")
        pick_id = f"{player}_{stat}_{direction}_{line}"
        
        # Get probability
        prob = self._get_probability(pick)
        original_prob = prob
        
        # Initialize result
        result = EligibilityResult(
            pick_id=pick_id,
            state=PickState.ADJUSTED,  # Start as ADJUSTED
            original_probability=original_prob,
            final_probability=prob,
        )
        
        # Extract flags
        flags = self._extract_flags(pick)
        result.flags_detected = flags
        
        # Get archetype
        archetype = pick.get("archetype", pick.get("role_layer", {}).get("archetype", ""))

        # Stat specialist axis (string, already enum-like). Prefer canonical alias, then NBA-specific.
        specialist = str(pick.get("stat_specialist_type") or pick.get("nba_stat_specialist_type") or "").upper()
        
        # Get matchup data
        matchup_games = pick.get("matchup_games_vs", pick.get("matchup_sample_size", 99))
        
        # =================================================================
        # GATE SEQUENCE (APPLY IN ORDER)
        # =================================================================
        
        # GATE 0: STAT DEVIATION GATE (SDG)
        # Applied BEFORE probability thresholds — modifies raw prob if player
        # is expected to perform at baseline (z_stat too small)
        result.gate_sequence.append("GATE_0_STAT_DEVIATION")
        try:
            from core.stat_deviation_gate import apply_sdg_to_pick
            
            # Only apply SDG if we have mu/sigma data
            mu = pick.get("mu", pick.get("recent_avg", pick.get("player_avg")))
            sigma = pick.get("sigma", pick.get("stddev", pick.get("player_stddev")))
            
            if mu is not None and sigma is not None and sigma > 0:
                # Apply SDG — modifies pick in-place and returns details
                pick_modified, sdg_details = apply_sdg_to_pick(pick, mode="soft")
                
                # Copy SDG results to our pick reference
                for key, val in pick_modified.items():
                    if key.startswith("sdg_"):
                        pick[key] = val
                
                # Update probability if SDG applied a penalty
                sdg_mult = sdg_details.get("multiplier", 1.0)
                if sdg_mult < 1.0:
                    prob = prob * sdg_mult
                    result.final_probability = prob
                    result.adjustments.append(
                        f"SDG_{sdg_details.get('penalty', 'unknown').upper()}: "
                        f"×{sdg_mult:.2f} (z_stat={sdg_details.get('z_stat', 0):+.3f})"
                    )
                    result.gate_sequence.append(
                        f"SDG_PENALTY: z_stat={sdg_details.get('z_stat', 0):+.3f}, mult={sdg_mult:.2f}"
                    )
                else:
                    result.gate_sequence.append("SDG_PASS")
            else:
                result.gate_sequence.append("SDG_SKIP: no mu/sigma data")
                
        except ImportError as e:
            result.gate_sequence.append(f"SDG_SKIP: module not available ({e})")
        except Exception as e:
            logger.warning(f"SDG error for {pick_id}: {e}")
            result.gate_sequence.append(f"SDG_ERROR: {e}")
        
        # GATE 1: Minimum probability
        result.gate_sequence.append("GATE_1_MIN_PROB")
        if prob < self.min_probability:
            result.state = PickState.REJECTED
            result.rejection_reason = RejectionReason.LOW_PROBABILITY
            result.gate_sequence.append(f"REJECTED: prob {prob:.1f}% < {self.min_probability}%")
            return result
        
        # GATE 2: High usage volatility
        result.gate_sequence.append("GATE_2_USAGE_VOLATILITY")
        if "HIGH_USAGE_VOLATILITY" in flags:
            result.state = PickState.REJECTED
            result.rejection_reason = RejectionReason.HIGH_USAGE_VOLATILITY
            result.gate_sequence.append("REJECTED: HIGH_USAGE_VOLATILITY flag")
            return result
        
        # GATE 3: Specialist structural rejects
        result.gate_sequence.append("GATE_3_SPECIALIST_REJECTS")

        # 3A) Bench microwave on fragile stats (specialist OR role-layer archetype)
        if (specialist == "BENCH_MICROWAVE" or archetype == "BENCH_MICROWAVE") and stat in self.BENCH_FRAGILE_STATS:
            result.state = PickState.REJECTED
            result.rejection_reason = RejectionReason.BENCH_MICROWAVE_FRAGILE
            result.gate_sequence.append(f"REJECTED: BENCH_MICROWAVE + {stat}")
            return result

        # 3B) Off-dribble scorer confidence floor (production lock-in)
        if specialist == "OFF_DRIBBLE_SCORER" and prob < 58.0:
            result.state = PickState.REJECTED
            result.rejection_reason = RejectionReason.SPECIALIST_OFF_DRIBBLE_LOW_CONFIDENCE
            result.gate_sequence.append(f"REJECTED: OFF_DRIBBLE_SCORER prob {prob:.1f}% < 58.0%")
            return result

        # 3C) Big-man 3PM at 3.5+ (production lock-in)
        if specialist == "BIG_MAN_3PM":
            try:
                line_f = float(line)
            except Exception:
                line_f = None
            if isinstance(line_f, (int, float)) and line_f >= 3.5:
                result.state = PickState.REJECTED
                result.rejection_reason = RejectionReason.SPECIALIST_BIG_MAN_3PM_LINE_TOO_HIGH
                result.gate_sequence.append(f"REJECTED: BIG_MAN_3PM line {line_f} >= 3.5")
                return result

        # 3D) NEW: Use stat_specialist_engine rejection rules if available
        if HAS_SPECIALIST_ENGINE:
            # Classify using the engine if not already classified
            engine_specialist_str = pick.get("stat_specialist_engine") or pick.get("stat_specialist")
            if engine_specialist_str:
                try:
                    engine_specialist = StatSpecialist(engine_specialist_str)
                except (ValueError, KeyError):
                    engine_specialist = StatSpecialist.GENERIC
            else:
                # Classify on the fly
                engine_specialist = classify_stat_specialist(pick, stat)
            
            reject, reason = engine_should_reject(
                engine_specialist, stat, float(line), prob, use_percent_scale=True
            )
            if reject:
                result.state = PickState.REJECTED
                # Map reason to RejectionReason enum
                if "BENCH_MICROWAVE" in (reason or ""):
                    result.rejection_reason = RejectionReason.BENCH_MICROWAVE_FRAGILE
                elif "OFF_DRIBBLE" in (reason or ""):
                    result.rejection_reason = RejectionReason.SPECIALIST_OFF_DRIBBLE_LOW_CONFIDENCE
                elif "BIG_MAN_3PM" in (reason or ""):
                    result.rejection_reason = RejectionReason.SPECIALIST_BIG_MAN_3PM_LINE_TOO_HIGH
                else:
                    result.rejection_reason = RejectionReason.STRUCTURAL_RISK
                result.gate_sequence.append(f"REJECTED: stat_specialist_engine: {reason}")
                return result
        
        # GATE 4: FRAGILE flag
        result.gate_sequence.append("GATE_4_FRAGILE")
        if "FRAGILE" in flags or pick.get("is_fragile", False):
            result.state = PickState.VETTED
            result.vetted_reason = VettedReason.FRAGILE_FLAG
            result.gate_sequence.append("VETTED: FRAGILE flag (visible, not optimizable)")
            return result
        
        # GATE 5: Matchup sample decay
        result.gate_sequence.append("GATE_5_MATCHUP_DECAY")
        if matchup_games < self.min_matchup_games:
            # Apply decay to probability
            prob = prob * self.matchup_decay
            result.final_probability = prob
            result.adjustments.append(f"matchup_decay: ×{self.matchup_decay} (only {matchup_games} games)")
            result.state = PickState.VETTED
            result.vetted_reason = VettedReason.MATCHUP_DECAY
            result.gate_sequence.append(f"VETTED: matchup_games={matchup_games} < {self.min_matchup_games}")
            return result
        
        # GATE 6: Composite stat check (optional degradation)
        result.gate_sequence.append("GATE_6_COMPOSITE")
        composite_stats = {"PRA", "PR", "PA", "RA", "PTS+REB+AST", "PTS+REB", "PTS+AST", "REB+AST", "STOCKS"}
        if stat in composite_stats:
            result.adjustments.append("composite_stat: marked for scrutiny")
            # Could optionally downgrade to VETTED, but for now just note it
        
        # PASSED ALL GATES
        result.gate_sequence.append("PASSED_ALL_GATES")
        result.state = PickState.OPTIMIZABLE
        return result
    
    def _get_probability(self, pick: Dict[str, Any]) -> float:
        """Extract probability from pick, checking multiple possible fields."""
        prob_fields = [
            "final_probability",
            "effective_confidence", 
            "model_confidence",
            "display_prob",
            "probability",
            "confidence",
            "p_hit",
        ]
        
        for field in prob_fields:
            val = pick.get(field)
            if val is not None:
                # Handle both 0-1 and 0-100 scales
                if isinstance(val, (int, float)):
                    return val if val > 1 else val * 100
        
        return 0.0
    
    def _extract_flags(self, pick: Dict[str, Any]) -> List[str]:
        """Extract all flags from a pick."""
        flags = []
        
        # Check role_layer flags
        role_layer = pick.get("role_layer", {})
        if isinstance(role_layer, dict):
            role_flags = role_layer.get("flags", [])
            if isinstance(role_flags, list):
                flags.extend(role_flags)
        
        # Check direct flags
        if pick.get("high_usage_volatility"):
            flags.append("HIGH_USAGE_VOLATILITY")
        if pick.get("is_fragile") or pick.get("fragile"):
            flags.append("FRAGILE")
        if pick.get("high_bench_variance"):
            flags.append("HIGH_BENCH_VARIANCE")
        
        # Check leg_type
        leg_type = pick.get("leg_type", "")
        if "FRAGILE" in str(leg_type).upper():
            flags.append("FRAGILE")
        
        return list(set(flags))  # Dedupe


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def run_eligibility_gate(
    picks: List[Dict[str, Any]],
    gate: Optional[EligibilityGate] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Run all picks through the Eligibility Gate.
    
    This is the REQUIRED entry point before Monte Carlo or rendering.
    
    Args:
        picks: List of pick dictionaries
        gate: Optional custom gate configuration
    
    Returns:
        (processed_picks, stats) where each pick has 'eligibility' field added
    """
    if gate is None:
        gate = EligibilityGate()
    
    stats = {
        "total": len(picks),
        "optimizable": 0,
        "vetted": 0,
        "rejected": 0,
    }
    
    processed = []
    for pick in picks:
        result = gate.evaluate(pick)
        
        # Enrich pick with eligibility data
        pick["eligibility"] = result.to_dict()
        pick["pick_state"] = result.state.value
        pick["is_optimizable"] = result.is_optimizable
        pick["is_visible"] = result.is_visible
        
        # Update final probability if adjusted
        if result.final_probability != result.original_probability:
            pick["gated_probability"] = result.final_probability
        
        # Count stats
        if result.state == PickState.OPTIMIZABLE:
            stats["optimizable"] += 1
        elif result.state == PickState.VETTED:
            stats["vetted"] += 1
        else:
            stats["rejected"] += 1
        
        processed.append(pick)
    
    logger.info(
        f"Eligibility Gate: {stats['optimizable']} OPTIMIZABLE, "
        f"{stats['vetted']} VETTED, {stats['rejected']} REJECTED "
        f"(of {stats['total']} total)"
    )
    
    return processed, stats


def get_optimizable_picks(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get only OPTIMIZABLE picks for Monte Carlo.
    
    CRITICAL: Monte Carlo MUST use this function. Direct access is forbidden.
    """
    return [p for p in picks if p.get("pick_state") == PickState.OPTIMIZABLE.value]


def get_visible_picks(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get visible picks for report rendering.
    
    Includes OPTIMIZABLE and VETTED. Excludes REJECTED.
    """
    visible_states = {PickState.OPTIMIZABLE.value, PickState.VETTED.value}
    return [p for p in picks if p.get("pick_state") in visible_states]


def get_rejected_picks(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get rejected picks for the Risky Picks report."""
    return [p for p in picks if p.get("pick_state") == PickState.REJECTED.value]


# =============================================================================
# MONTE CARLO CONSTRAINT ENFORCEMENT
# =============================================================================

@dataclass
class MonteCarloConstraints:
    """
    Enforcement rules for Monte Carlo optimization.
    
    These constraints are NON-NEGOTIABLE.
    """
    # Entry composition rules
    max_fragile_legs: int = 0         # FRAGILE picks blocked from entries
    max_vetted_legs: int = 0          # VETTED picks blocked from entries
    fragile_max_legs: int = 2         # If fragile somehow included, cap at 2-leg
    
    # Fallback mode adjustments
    fallback_kelly_reduction: float = 0.50  # Reduce Kelly stake by 50% in fallback
    
    # Entry type restrictions
    allow_fragile_in_flex: bool = False
    allow_fragile_in_power: bool = False
    
    def validate_entry(self, legs: List[Dict[str, Any]], entry_type: str = "power") -> Tuple[bool, List[str]]:
        """
        Validate a Monte Carlo entry against constraints.
        
        Args:
            legs: List of picks in the entry
            entry_type: "power" or "flex"
        
        Returns:
            (is_valid, rejection_reasons)
        """
        reasons = []
        
        # Check for non-optimizable picks
        for leg in legs:
            state = leg.get("pick_state", "")
            if state == PickState.REJECTED.value:
                reasons.append(f"REJECTED pick in entry: {leg.get('player', '?')}")
            elif state == PickState.VETTED.value:
                reasons.append(f"VETTED pick in entry (not optimizable): {leg.get('player', '?')}")
        
        # Check FRAGILE count
        fragile_count = sum(1 for leg in legs if "FRAGILE" in leg.get("eligibility", {}).get("flags_detected", []))
        if fragile_count > self.max_fragile_legs:
            reasons.append(f"Too many FRAGILE legs: {fragile_count} > {self.max_fragile_legs}")
        
        # If fragile present, enforce leg cap
        if fragile_count > 0 and len(legs) > self.fragile_max_legs:
            reasons.append(f"FRAGILE present but entry has {len(legs)} legs > {self.fragile_max_legs} max")
        
        # NEW: Specialist-based entry type restrictions (production lock-in)
        if HAS_SPECIALIST_ENGINE:
            for leg in legs:
                specialist_str = leg.get("stat_specialist_engine") or leg.get("stat_specialist") or leg.get("stat_specialist_type")
                if specialist_str:
                    try:
                        specialist = StatSpecialist(specialist_str)
                    except (ValueError, KeyError):
                        specialist = StatSpecialist.GENERIC
                    
                    # FLEX ban for volatile specialists
                    if entry_type.lower() == "flex" and is_flex_banned(specialist):
                        reasons.append(f"FLEX banned for {specialist.value}: {leg.get('player', '?')}")
                    
                    # Max legs constraint (e.g., BIG_MAN_3PM max 2)
                    max_legs = get_max_legs(specialist)
                    if max_legs is not None and len(legs) > max_legs:
                        reasons.append(f"{specialist.value} max {max_legs} legs, entry has {len(legs)}: {leg.get('player', '?')}")
        
        return len(reasons) == 0, reasons
    
    def adjust_kelly_stake(self, base_stake: float, is_fallback: bool) -> float:
        """Adjust Kelly stake based on mode."""
        if is_fallback:
            return base_stake * (1 - self.fallback_kelly_reduction)
        return base_stake


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def enforce_governance(picks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Main entry point: Enforce complete decision governance on picks.
    
    This function:
    1. Runs 3PM governance (if applicable)
    2. Runs Eligibility Gate
    3. Returns organized pick lists
    4. Provides governance stats
    
    Returns:
        {
            "all_picks": [...],  # All picks with eligibility data
            "optimizable": [...],  # For Monte Carlo
            "visible": [...],  # For reports
            "rejected": [...],  # For Risky Picks report
            "stats": {...}
        }
    """
    # Run 3PM governance first (applies confidence ceilings for 3PM picks)
    try:
        from core.shot_profile_archetypes import run_3pm_governance
        picks, threepm_stats = run_3pm_governance(picks)
        logger.info(f"3PM governance: {threepm_stats.get('ceilings_applied', 0)} ceilings applied")
    except ImportError:
        logger.warning("3PM governance module not found, skipping")
        threepm_stats = {}
    
    # Run eligibility gate
    processed, stats = run_eligibility_gate(picks)

    # Merge 3PM stats (keep typing sane: run_eligibility_gate() returns Dict[str, int])
    merged_stats: Dict[str, Any] = dict(stats)
    merged_stats["3pm"] = threepm_stats
    
    return {
        "all_picks": processed,
        "optimizable": get_optimizable_picks(processed),
        "visible": get_visible_picks(processed),
        "rejected": get_rejected_picks(processed),
        "stats": merged_stats,
    }


def require_governance_check(picks: List[Dict[str, Any]]) -> None:
    """
    Assert that picks have been through governance.
    
    Call this before Monte Carlo to ensure the pipeline was followed.
    Raises AssertionError if governance was bypassed.
    """
    if not picks:
        return
    
    sample = picks[0]
    if "pick_state" not in sample or "eligibility" not in sample:
        raise AssertionError(
            "GOVERNANCE VIOLATION: Picks have not passed through Eligibility Gate. "
            "Call enforce_governance() before Monte Carlo or rendering."
        )
