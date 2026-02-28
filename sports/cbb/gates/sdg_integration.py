"""
CBB SDG Integration — Wiring the SDG filter into the CBB pipeline

This module provides the integration point between:
1. cbb_sdg_filter.py (core SDG logic)
2. cbb_context_gates.py (context-based adjustments)
3. cbb_main.py (main pipeline)

Implementation Date: 2026-02-01
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
import yaml


# =============================================================================
# LOAD SDG CONFIG
# =============================================================================

def load_sdg_config() -> Dict:
    """Load SDG configuration from YAML file."""
    config_path = Path(__file__).parent.parent / "config" / "sdg_config.yaml"
    
    if config_path.exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[SDG] Warning: Could not load config: {e}")
    
    return {}


# =============================================================================
# MAIN INTEGRATION FUNCTION
# =============================================================================

def apply_sdg_to_edge(
    edge: Dict,
    player_stats: Optional[Dict] = None,
    game_context: Optional[Dict] = None,
    config: Optional[Dict] = None
) -> Dict:
    """
    Apply SDG filter and context gates to a single edge.
    
    This is the main integration point called from cbb_main.py.
    
    Order of operations:
    1. Load config if not provided
    2. Check blocked composites FIRST (before SDG)
    3. Build player_stats from edge if not provided
    4. Build game_context from edge if not provided
    5. Apply SDG filter
    6. Apply context gates
    7. Check composite SDG requirements (z, cv)
    8. Update edge with results
    
    Returns: Updated edge dict
    """
    from sports.cbb.gates.cbb_sdg_filter import apply_cbb_sdg_filter
    from sports.cbb.gates.cbb_context_gates import apply_all_context_gates
    
    if config is None:
        config = load_sdg_config()
    
    # Check if SDG is enabled
    sdg_config = config.get("sdg", {})
    if not sdg_config.get("enabled", True):
        edge["sdg_skipped"] = True
        edge["sdg_reason"] = "DISABLED"
        return edge
    
    # Check blocked composites FIRST (before SDG)
    edge = check_blocked_composites(edge)
    if edge.get("tier") == "SKIP":
        return edge
    
    # Build player_stats from edge if not provided
    if player_stats is None:
        player_stats = _extract_player_stats(edge)
    
    # Build game_context from edge if not provided
    if game_context is None:
        game_context = _extract_game_context(edge)
    
    # Apply SDG filter
    edge = apply_cbb_sdg_filter(edge, player_stats, game_context)
    
    # Apply context gates (if SDG passed)
    if edge.get("sdg_passed", True):
        edge = apply_all_context_gates(edge, player_stats, game_context)
    
    # Check composite SDG requirements AFTER SDG calculates z/cv
    edge = check_composite_sdg_requirements(edge)
    
    return edge


def apply_sdg_to_edges(
    edges: List[Dict],
    verbose: bool = True
) -> List[Dict]:
    """
    Apply SDG filter to all edges.
    
    This is the batch version called from score_cbb_edges().
    
    Returns: List of edges with SDG applied
    """
    config = load_sdg_config()
    
    sdg_config = config.get("sdg", {})
    if not sdg_config.get("enabled", True):
        if verbose:
            print("  [SDG] DISABLED — skipping")
        return edges
    
    if verbose:
        print("  [SDG] Applying Stat Deviation Gate...")
    
    passed = 0
    soft_penalized = 0
    penalized = 0
    
    # SDG v2.2: SOFT PENALTY MODE (replaces hard reject)
    # Instead of SKIP on z-fail, apply graduated confidence penalty.
    # This matches the filter's own doc: "SOFT Volatility Governor".
    # Only HARD reject when z < 0.15 (true zero-signal territory).
    HARD_REJECT_Z_FLOOR = 0.15  # Below this = genuinely no signal
    
    for edge in edges:
        # Skip already-gated edges
        if edge.get("tier") == "SKIP":
            continue
        
        edge = apply_sdg_to_edge(edge, config=config)
        
        if edge.get("sdg_passed", True):
            passed += 1
            if edge.get("sdg_penalty", 1.0) < 1.0:
                penalized += 1
        else:
            # v2.2: Convert hard fails to soft penalties instead of SKIP
            # Get the z-score to decide severity
            z_l10 = edge.get("sdg_details", {}).get("multi_window", {}).get("z_l10", 0)
            z_season = edge.get("sdg_details", {}).get("multi_window", {}).get("z_season", z_l10)
            best_z = max(z_l10, z_season)
            
            if best_z < HARD_REJECT_Z_FLOOR:
                # Genuinely no signal — keep as SKIP
                edge["tier"] = "SKIP"
                edge["skip_reason"] = f"SDG_HARD_REJECT: z={best_z:.2f} (no signal)"
                soft_penalized += 0  # counted below in verbose
            else:
                # Soft penalty: graduated based on how far below threshold
                # z=0.15-0.30 → -25%, z=0.30-0.45 → -15%, z=0.45+ → -8%
                if best_z < 0.30:
                    sdg_soft_penalty = 0.75
                elif best_z < 0.45:
                    sdg_soft_penalty = 0.85
                else:
                    sdg_soft_penalty = 0.92
                
                # Apply to probability instead of rejecting
                old_prob = edge.get("probability", 0.5)
                edge["probability"] = round(old_prob * sdg_soft_penalty, 4)
                edge["sdg_passed"] = True  # Override — let it through
                edge["sdg_soft_penalty"] = sdg_soft_penalty
                edge["sdg_reasons"] = edge.get("sdg_reasons", []) + [f"SOFT_PENALTY:{sdg_soft_penalty:.0%}"]
                soft_penalized += 1
                passed += 1
    
    # Count actual hard fails
    hard_failed = sum(1 for e in edges if e.get("tier") == "SKIP" and "SDG_HARD_REJECT" in e.get("skip_reason", ""))
    
    if verbose:
        print(f"      Passed: {passed}, Failed: {hard_failed}, Penalized: {penalized + soft_penalized}")
    
    return edges


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _extract_player_stats(edge: Dict) -> Dict:
    """Extract player stats from edge for SDG calculation."""
    # Try to get from decision_trace first (more complete)
    trace = edge.get("decision_trace", {})
    
    return {
        "l10_mu": trace.get("l10_mu") or edge.get("player_mean", 0),
        "l10_sigma": trace.get("l10_sigma") or edge.get("player_stddev", 2.0),
        "season_mu": trace.get("season_mu") or edge.get("player_mean", 0),
        "season_sigma": trace.get("season_sigma") or edge.get("player_stddev", 2.0),
        "games_played": trace.get("games_played") or edge.get("sample_n", 10),
        "usage_rate": trace.get("usage_rate"),
        "minutes_avg": trace.get("minutes_avg"),
        "team_baseline_mu": trace.get("team_baseline_mu"),
        "role": trace.get("player_role", "ROLE_PLAYER"),
    }


def _extract_game_context(edge: Dict) -> Dict:
    """Extract game context from edge for SDG calculation."""
    from datetime import datetime
    
    return {
        "opponent_def_rank": edge.get("opponent_def_rank"),
        "spread": edge.get("game_spread") or edge.get("spread"),
        "is_away": edge.get("is_away", False),
        "game_month": datetime.now().month,  # Default to current month
        "is_conference_game": edge.get("is_conference_game", True),
        "is_tournament": edge.get("is_tournament", False),
        "home_team": edge.get("home_team", ""),
        "away_team": edge.get("away_team", ""),
    }


# =============================================================================
# TIER ADJUSTMENT POST-SDG
# =============================================================================

def adjust_tiers_post_sdg(edges: List[Dict], verbose: bool = True) -> List[Dict]:
    """
    Re-evaluate tiers after SDG penalty is applied.
    
    CBB Tiers (post-SDG):
    - SLAM: DISABLED
    - STRONG: ≥70%
    - LEAN: ≥60%
    - SKIP: <60%
    """
    from sports.cbb.config import CBB_TIER_THRESHOLDS_V2
    
    tier_counts = {"STRONG": 0, "LEAN": 0, "SKIP": 0}
    
    for edge in edges:
        # Skip already-skipped edges
        if edge.get("tier") == "SKIP":
            tier_counts["SKIP"] = tier_counts.get("SKIP", 0) + 1
            continue
        
        prob = edge.get("probability", 0)
        
        # Apply post-SDG thresholds
        if prob >= CBB_TIER_THRESHOLDS_V2.get("STRONG", 0.70):
            edge["tier"] = "STRONG"
            tier_counts["STRONG"] += 1
        elif prob >= CBB_TIER_THRESHOLDS_V2.get("LEAN", 0.60):
            edge["tier"] = "LEAN"
            tier_counts["LEAN"] += 1
        else:
            edge["tier"] = "SKIP"
            edge["skip_reason"] = edge.get("skip_reason", "BELOW_THRESHOLD")
            tier_counts["SKIP"] += 1
        
        # Additional cap: FALLBACK/NO_DATA cannot be STRONG
        if edge.get("tier") == "STRONG":
            if edge.get("mean_source") == "FALLBACK" or edge.get("confidence_flag") in ("UNVERIFIED", "NO_DATA"):
                edge["tier"] = "LEAN"
                edge["tier_cap_reason"] = f"TIER_CAPPED ({edge.get('mean_source')}/{edge.get('confidence_flag')})"
                tier_counts["STRONG"] -= 1
                tier_counts["LEAN"] += 1
    
    if verbose:
        print("  [TIERS POST-SDG]")
        for tier, count in sorted(tier_counts.items()):
            print(f"      {tier}: {count}")
    
    return edges


# =============================================================================
# COMPOSITE STAT HANDLER
# =============================================================================

def check_blocked_composites(edge: Dict) -> Dict:
    """
    Check if composite stat is in the block list.
    
    This runs BEFORE SDG - just checks if the stat type is allowed.
    SDG requirements (z, cv) are checked AFTER SDG computes them.
    """
    from sports.cbb.config import ALLOWED_COMPOSITES
    
    stat = (edge.get("stat") or "").upper().replace(" ", "")
    
    # Check if it's a composite
    composite_patterns = ["PTS+", "REB+", "AST+", "PRA", "FANTASY"]
    is_composite = any(p in stat for p in composite_patterns)
    
    if not is_composite:
        return edge
    
    # Check if allowed
    if stat not in [c.upper().replace(" ", "") for c in ALLOWED_COMPOSITES]:
        edge["tier"] = "SKIP"
        edge["skip_reason"] = f"BLOCKED_COMPOSITE:{stat}"
    
    return edge


def check_composite_sdg_requirements(edge: Dict) -> Dict:
    """
    Check if composite stat meets SDG requirements.
    
    This runs AFTER SDG - checks z-score and cv requirements.
    Only for ALLOWED composites (blocked ones already filtered).
    """
    from sports.cbb.config import (
        ALLOWED_COMPOSITES,
        COMPOSITE_MAX_CONFIDENCE,
        COMPOSITE_MIN_Z,
        COMPOSITE_MAX_CV,
    )
    
    # Skip if already blocked
    if edge.get("tier") == "SKIP":
        return edge
    
    stat = (edge.get("stat") or "").upper().replace(" ", "")
    
    # Check if it's an allowed composite
    composite_patterns = ["PTS+", "REB+", "AST+", "PRA", "FANTASY"]
    is_composite = any(p in stat for p in composite_patterns)
    
    if not is_composite:
        return edge
    
    if stat not in [c.upper().replace(" ", "") for c in ALLOWED_COMPOSITES]:
        # Already blocked by check_blocked_composites
        return edge
    
    # Check SDG requirements
    sdg_details = edge.get("sdg_details", {})
    z_score = sdg_details.get("multi_window", {}).get("z_l10", 0)
    cv_ratio = sdg_details.get("cv", {}).get("cv_ratio", 1.0)
    
    if z_score < COMPOSITE_MIN_Z:
        edge["tier"] = "SKIP"
        edge["skip_reason"] = f"COMPOSITE_LOW_Z:{z_score:.2f}<{COMPOSITE_MIN_Z}"
        return edge
    
    if cv_ratio > COMPOSITE_MAX_CV:
        edge["tier"] = "SKIP"
        edge["skip_reason"] = f"COMPOSITE_HIGH_CV:{cv_ratio:.2f}>{COMPOSITE_MAX_CV}"
        return edge
    
    # Apply confidence cap
    if edge.get("probability", 0) > COMPOSITE_MAX_CONFIDENCE:
        edge["probability"] = COMPOSITE_MAX_CONFIDENCE
        edge["composite_capped"] = True
        edge["composite_cap_reason"] = f"CAPPED_AT_{COMPOSITE_MAX_CONFIDENCE:.0%}"
    
    # Never SLAM for composites
    if edge.get("tier") == "SLAM":
        edge["tier"] = "STRONG"
        edge["tier_cap_reason"] = "COMPOSITE_NO_SLAM"
    
    return edge


def check_and_apply_composite_rules(edge: Dict) -> Dict:
    """
    Legacy wrapper - calls both checks in order.
    Use check_blocked_composites and check_composite_sdg_requirements separately in pipeline.
    """
    edge = check_blocked_composites(edge)
    if edge.get("tier") != "SKIP":
        edge = check_composite_sdg_requirements(edge)
    return edge


# =============================================================================
# BINARY PROP HANDLER
# =============================================================================

def check_binary_prop_eligibility(edge: Dict) -> Dict:
    """
    Check if binary prop meets eligibility requirements.
    
    Binary props (O0.5, O1.5) have special handling.
    Only applies when there is an EXACT config match for the prop.
    
    v2.3: Fixed games_played extraction to check gate_status and decision_trace.
          Only match exact prop_key — do NOT fallback 1.5 → 0.5 config.
    """
    config = load_sdg_config()
    binary_config = config.get("binary_props", {})
    
    if not binary_config.get("enabled", True):
        return edge
    
    line = edge.get("line", 0)
    direction = (edge.get("direction") or "").lower()
    stat = (edge.get("stat") or "").upper()
    
    # Only for binary lines
    if line not in [0.5, 1.5]:
        return edge
    
    # Check for EXACT binary prop config match only
    # Do NOT fallback 3PM_OVER_1.5 → 3PM_OVER_0.5 (different bets)
    prop_key = f"{stat}_OVER_{line}".replace(".", "p")
    prop_config = binary_config.get(prop_key)
    
    if prop_config and prop_config.get("enabled", False):
        min_games = prop_config.get("min_games", 10)
        
        # v2.3: Robust games_played extraction
        games_played = (
            edge.get("sample_n")
            or edge.get("games_played")
            or edge.get("n")
            or (edge.get("decision_trace") or {}).get("games_played")
        )
        
        # Also try extracting from gate_status (set by edge_gates.py)
        if not games_played:
            for gs in (edge.get("gate_status") or []):
                if gs.get("gate") == "games" and gs.get("status") == "PASS":
                    reason = gs.get("reason", "")
                    # Parse "GP=25" format
                    if "GP=" in reason:
                        try:
                            games_played = int(reason.split("GP=")[1])
                        except (ValueError, IndexError):
                            pass
                    break
        
        # Default to None (unknown) — should NOT auto-fail
        if not games_played:
            # If GP is truly unknown but all other gates passed, 
            # let it through rather than auto-killing
            return edge
        
        if games_played < min_games:
            edge["tier"] = "SKIP"
            edge["skip_reason"] = f"BINARY_INSUFFICIENT_GAMES:{games_played}<{min_games}"
    
    return edge


# =============================================================================
# FULL SDG PIPELINE
# =============================================================================

def run_full_sdg_pipeline(edges: List[Dict], verbose: bool = True) -> List[Dict]:
    """
    Run the complete SDG pipeline on all edges.
    
    Order:
    1. Check blocked composites
    2. Apply SDG filter
    3. Apply context gates
    4. Check composite SDG requirements
    5. Check binary props
    6. Adjust tiers
    
    This replaces the simple scoring in score_cbb_edges().
    """
    if verbose:
        print("\n  [SDG PIPELINE] Running full SDG pipeline...")
    
    # 1. Check blocked composites first
    for edge in edges:
        edge = check_blocked_composites(edge)
    
    # 2. Apply SDG filter to all edges
    edges = apply_sdg_to_edges(edges, verbose=verbose)
    
    # 3. Check composite SDG requirements (z, cv)
    for edge in edges:
        edge = check_composite_sdg_requirements(edge)
    
    # 4. Check binary props
    for edge in edges:
        edge = check_binary_prop_eligibility(edge)
    
    # 5. Adjust tiers based on post-SDG probabilities
    edges = adjust_tiers_post_sdg(edges, verbose=verbose)
    
    return edges
