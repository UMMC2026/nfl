"""
Tennis Edge Generator
=====================
Generates edges for match winner market.

EDGE = unique(player, opponent, surface, round, tour)
One EDGE → one line → one bet

No Monte Carlo. Deterministic probability calculation.

GOVERNANCE: Tier thresholds imported from config/thresholds.py (single source of truth).
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add tennis directory and project root for imports
TENNIS_DIR = Path(__file__).parent
PROJECT_ROOT = TENNIS_DIR.parent
sys.path.insert(0, str(TENNIS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from config.thresholds import get_all_thresholds, implied_tier

from tennis_elo import elo_probability, get_player_elo, load_elo_ratings
from ingest_tennis import load_latest_slate, moneyline_to_implied_prob

CONFIG_FILE = TENNIS_DIR / "tennis_config.json"
OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# Load config
CONFIG = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}


def load_player_stats() -> Dict:
    """Load player statistics (serve %, return %, etc.)."""
    stats_file = TENNIS_DIR / "player_stats.json"
    if stats_file.exists():
        return json.loads(stats_file.read_text())
    return {}


def get_serve_hold_pct(player: str, surface: str, stats: Dict) -> float:
    """Get serve hold percentage for player on surface."""
    player_stats = stats.get(player, {})
    surface_key = f"serve_hold_{surface.lower()}"
    
    # Try surface-specific, then overall, then default
    return player_stats.get(surface_key, player_stats.get("serve_hold", 0.80))


def get_return_win_pct(player: str, surface: str, stats: Dict) -> float:
    """Get return points won percentage for player on surface."""
    player_stats = stats.get(player, {})
    surface_key = f"return_win_{surface.lower()}"
    
    return player_stats.get(surface_key, player_stats.get("return_win", 0.35))


def get_fatigue_penalty(player: str, stats: Dict) -> float:
    """Calculate fatigue penalty based on recent match load."""
    player_stats = stats.get(player, {})
    matches_7d = player_stats.get("matches_last_7d", 0)
    
    # Graduated penalty
    if matches_7d >= 4:
        return 0.08  # Heavy fatigue
    elif matches_7d >= 3:
        return 0.04  # Moderate fatigue
    elif matches_7d >= 2:
        return 0.02  # Light fatigue
    return 0.0


def run_risk_gates(player: str, opponent: str, surface: str, stats: Dict) -> tuple:
    """
    Run mandatory risk gates.
    
    Returns: (passed: bool, block_reason: str or None)
    """
    gates = CONFIG.get("risk_gates", {})
    player_stats = stats.get(player, {})
    
    # Gate 1: Retired last match
    if gates.get("block_if_retired_last", True):
        if player_stats.get("retired_last_match", False):
            return False, "RETIRED_LAST_MATCH"
    
    # Gate 2: Minimum rest
    min_rest = gates.get("min_rest_hours", 24)
    rest_hours = player_stats.get("rest_hours", 48)
    if rest_hours < min_rest:
        return False, f"INSUFFICIENT_REST ({rest_hours}h < {min_rest}h)"
    
    # Gate 3: Match load
    max_matches = gates.get("max_matches_7d", 4)
    matches_7d = player_stats.get("matches_last_7d", 0)
    if matches_7d >= max_matches:
        return False, f"MATCH_OVERLOAD ({matches_7d} >= {max_matches})"
    
    # Gate 4: Surface experience
    min_surface = gates.get("min_surface_matches_90d", 2)
    surface_matches = player_stats.get(f"matches_{surface.lower()}_90d", 5)
    if surface_matches < min_surface:
        return False, f"LOW_SURFACE_EXPERIENCE ({surface_matches} < {min_surface})"
    
    # Gate 5: Unknown opponent
    if gates.get("block_unknown_opponent", True):
        if opponent.upper() in ["TBD", "QUALIFIER", "UNKNOWN", "?"]:
            return False, "UNKNOWN_OPPONENT"
    
    return True, None


def calculate_probability(
    player: str,
    opponent: str,
    surface: str,
    stats: Dict
) -> tuple:
    """
    Calculate match win probability.
    
    Returns: (probability, prob_details)
    """
    prob_config = CONFIG.get("probability", {})
    
    # 1. Base probability from Elo
    elo_prob_a, _ = elo_probability(player, opponent, surface)
    
    # 2. Serve edge
    serve_a = get_serve_hold_pct(player, surface, stats)
    serve_b = get_serve_hold_pct(opponent, surface, stats)
    serve_edge = (serve_a - serve_b) * 0.5  # Scale to probability adjustment
    
    # 3. Return edge
    return_a = get_return_win_pct(player, surface, stats)
    return_b = get_return_win_pct(opponent, surface, stats)
    return_edge = (return_a - return_b) * 0.3  # Scale to probability adjustment
    
    # 4. Fatigue penalty
    fatigue_a = get_fatigue_penalty(player, stats)
    fatigue_b = get_fatigue_penalty(opponent, stats)
    fatigue_adj = fatigue_b - fatigue_a  # Opponent more fatigued = bonus
    
    # 5. Combine with weights
    elo_weight = prob_config.get("elo_weight", 0.50)
    serve_weight = prob_config.get("serve_weight", 0.25)
    return_weight = prob_config.get("return_weight", 0.15)
    fatigue_weight = prob_config.get("fatigue_weight", 0.10)
    
    # Final probability
    adjustments = (
        serve_edge * serve_weight +
        return_edge * return_weight +
        fatigue_adj * fatigue_weight
    )
    
    # Blend Elo with adjustments
    raw_prob = elo_prob_a * elo_weight + (0.50 + adjustments) * (1 - elo_weight)
    
    # Clamp to configured bounds
    min_prob = prob_config.get("min_probability", 0.50)
    max_prob = prob_config.get("max_probability", 0.80)
    final_prob = max(min_prob, min(max_prob, raw_prob))
    
    details = {
        "elo_prob": round(elo_prob_a, 4),
        "serve_edge": round(serve_edge, 4),
        "return_edge": round(return_edge, 4),
        "fatigue_adj": round(fatigue_adj, 4),
        "raw_prob": round(raw_prob, 4),
        "clamped_prob": round(final_prob, 4),
    }
    
    return final_prob, details


def calculate_edge(probability: float, implied_prob: float) -> float:
    """Calculate betting edge: model prob - implied prob."""
    return probability - implied_prob


def assign_tier(probability: float, tournament_name: str = None) -> str:
    """Assign confidence tier based on probability.
    
    GOVERNANCE: Uses canonical thresholds from config/thresholds.py
    Phase 5B: Uses tournament-specific thresholds when tournament_name provided.
    
    Args:
        probability: Model probability (0.0-1.0)
        tournament_name: Optional tournament name for tier-specific thresholds
    
    Returns:
        Tier string (SLAM, STRONG, LEAN, AVOID)
    """
    if tournament_name:
        # Phase 5B: Use tournament-aware thresholds
        try:
            from tennis.tournament_tier import implied_tier_for_tennis
            return implied_tier_for_tennis(probability, tournament_name)
        except ImportError:
            pass
    
    # Fallback to base TENNIS thresholds
    return implied_tier(probability, "TENNIS")


def generate_edge(match: Dict, stats: Dict) -> Dict:
    """Generate edge for a single match."""
    player_a = match["player_a"]
    player_b = match["player_b"]
    surface = match["surface"]
    tournament_name = match.get("tournament", match.get("event", None))
    
    # Run risk gates for player A
    passed_a, block_a = run_risk_gates(player_a, player_b, surface, stats)
    
    # Run risk gates for player B
    passed_b, block_b = run_risk_gates(player_b, player_a, surface, stats)
    
    edges = []
    
    # Generate edge for player A (if gates pass)
    if passed_a:
        prob_a, details_a = calculate_probability(player_a, player_b, surface, stats)
        implied_a = moneyline_to_implied_prob(match.get("line_a"))
        edge_a = calculate_edge(prob_a, implied_a)
        tier_a = assign_tier(prob_a, tournament_name)
        
        edges.append({
            "sport": "TENNIS",
            "tour": match.get("tour", "ATP"),
            "match_id": match["match_id"],
            "player": player_a,
            "opponent": player_b,
            "surface": surface,
            "round": match.get("round", "R1"),
            "market": "match_winner",
            "direction": player_a,
            "line": match.get("line_a"),
            "implied_prob": round(implied_a, 4),
            "probability": round(prob_a, 4),
            "tier": tier_a,
            "edge": round(edge_a, 4),
            "prob_details": details_a,
            "risk_tag": "SINGLES_ONLY",
            "blocked": False,
            "block_reason": None,
            "generated_at": datetime.now().isoformat(),
        })
    else:
        # Blocked edge for player A
        edges.append({
            "sport": "TENNIS",
            "tour": match.get("tour", "ATP"),
            "match_id": match["match_id"],
            "player": player_a,
            "opponent": player_b,
            "surface": surface,
            "round": match.get("round", "R1"),
            "market": "match_winner",
            "direction": player_a,
            "line": match.get("line_a"),
            "probability": None,
            "tier": "BLOCKED",
            "edge": None,
            "blocked": True,
            "block_reason": block_a,
            "generated_at": datetime.now().isoformat(),
        })
    
    # Generate edge for player B (if gates pass)
    if passed_b:
        prob_b, details_b = calculate_probability(player_b, player_a, surface, stats)
        implied_b = moneyline_to_implied_prob(match.get("line_b"))
        edge_b = calculate_edge(prob_b, implied_b)
        tier_b = assign_tier(prob_b, tournament_name)
        
        edges.append({
            "sport": "TENNIS",
            "tour": match.get("tour", "ATP"),
            "match_id": match["match_id"],
            "player": player_b,
            "opponent": player_a,
            "surface": surface,
            "round": match.get("round", "R1"),
            "market": "match_winner",
            "direction": player_b,
            "line": match.get("line_b"),
            "implied_prob": round(implied_b, 4),
            "probability": round(prob_b, 4),
            "tier": tier_b,
            "edge": round(edge_b, 4),
            "prob_details": details_b,
            "risk_tag": "SINGLES_ONLY",
            "blocked": False,
            "block_reason": None,
            "generated_at": datetime.now().isoformat(),
        })
    else:
        # Blocked edge for player B
        edges.append({
            "sport": "TENNIS",
            "tour": match.get("tour", "ATP"),
            "match_id": match["match_id"],
            "player": player_b,
            "opponent": player_a,
            "surface": surface,
            "round": match.get("round", "R1"),
            "market": "match_winner",
            "direction": player_b,
            "line": match.get("line_b"),
            "probability": None,
            "tier": "BLOCKED",
            "edge": None,
            "blocked": True,
            "block_reason": block_b,
            "generated_at": datetime.now().isoformat(),
        })
    
    return edges


def generate_all_edges(slate_file: Path = None) -> List[Dict]:
    """Generate edges for all matches in a slate."""
    
    # Load slate
    if slate_file:
        try:
            print(f"  Using slate file: {slate_file}")
        except Exception:
            pass
        slate = json.loads(slate_file.read_text())
    else:
        slate = load_latest_slate()
    
    if not slate:
        print("✗ No slate found")
        return []
    
    matches = slate.get("matches", [])
    stats = load_player_stats()
    
    all_edges = []
    for match in matches:
        edges = generate_edge(match, stats)
        all_edges.extend(edges)
    
    # Save edges
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = OUTPUTS_DIR / f"tennis_edges_{timestamp}.json"
    
    output = {
        "sport": "TENNIS",
        "generated_at": datetime.now().isoformat(),
        "slate_matches": len(matches),
        "total_edges": len(all_edges),
        "blocked_count": sum(1 for e in all_edges if e.get("blocked")),
        "edges": all_edges,
    }
    
    output_file.write_text(json.dumps(output, indent=2))
    
    # Also save as latest
    latest_file = OUTPUTS_DIR / "tennis_edges_latest.json"
    latest_file.write_text(json.dumps(output, indent=2))
    
    print(f"✓ Generated {len(all_edges)} edges ({output['blocked_count']} blocked)")
    print(f"  → {output_file}")
    
    return all_edges


def print_edges_summary(edges: List[Dict]):
    """Print summary of generated edges."""
    print("\n" + "=" * 60)
    print("TENNIS EDGES SUMMARY")
    print("=" * 60)
    
    playable = [e for e in edges if not e.get("blocked") and e.get("tier") != "NO_PLAY"]
    blocked = [e for e in edges if e.get("blocked")]
    no_play = [e for e in edges if e.get("tier") == "NO_PLAY"]
    
    if playable:
        print(f"\n✅ PLAYABLE ({len(playable)})")
        print("-" * 40)
        
        # Sort by edge descending
        playable.sort(key=lambda x: x.get("edge", 0), reverse=True)
        
        for e in playable:
            tier_emoji = "🔥" if e["tier"] == "STRONG" else "📊"
            print(f"  {tier_emoji} {e['player']} vs {e['opponent']}")
            print(f"     {e['surface']} {e['round']} | P={e['probability']:.1%} | Edge={e['edge']:+.1%} | {e['tier']}")
    
    if blocked:
        print(f"\n❌ BLOCKED ({len(blocked)})")
        print("-" * 40)
        for e in blocked:
            print(f"  • {e['player']} vs {e['opponent']}: {e['block_reason']}")
    
    if no_play:
        print(f"\n⚪ NO PLAY ({len(no_play)})")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    edges = generate_all_edges()
    print_edges_summary(edges)
