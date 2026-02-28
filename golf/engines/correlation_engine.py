"""
Golf Correlation Engine
=======================
Detects and penalizes correlated bets within same-player props.

QUANT RATIONALE:
If the engine suggests Justin Rose LOWER (Strokes) and Justin Rose HIGHER (Birdies),
those are HIGHLY correlated. If you bet both, you aren't diversified - you're
effectively double-betting on "Justin Rose has a good day."

This module:
1. Detects stat correlation groups (strokes↔birdies, eagles↔birdies)
2. Applies diversification penalty to correlated legs
3. Suggests unit sizing for portfolio construction
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, field

# Ensure project root is in path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# CORRELATION MATRIX
# =============================================================================
# 1.0 = perfect correlation, 0.0 = independent, -1.0 = inverse correlation

STAT_CORRELATIONS = {
    # Strokes and scoring stats
    ("strokes", "birdies"): -0.75,       # Lower strokes → more birdies (inverse)
    ("strokes", "pars"): -0.30,          # Weak inverse (more pars = fewer bad holes)
    ("strokes", "bogeys"): 0.80,         # Higher strokes → more bogeys
    
    # Birdies correlations
    ("birdies", "eagles"): 0.60,         # Both indicate aggressive scoring
    ("birdies", "bogeys"): -0.50,        # Players either birdie or bogey a lot
    ("birdies", "pars"): -0.65,          # More birdies = fewer pars
    
    # Score-based correlations
    ("bogeys", "pars"): -0.40,           # Inverse relationship
    ("eagles", "bogeys"): 0.25,          # Risk-takers get both
    
    # Fantasy point correlations (PGA Fantasy)
    ("fantasy_score", "birdies"): 0.85,  # Birdies drive fantasy
    ("fantasy_score", "strokes"): -0.70, # Lower strokes = higher fantasy
}

# Direction correlation - when betting opposite directions, correlation sign flips
# e.g., LOWER strokes + HIGHER birdies = same underlying bet (good round)
DIRECTION_ALIGNMENT = {
    ("higher", "higher"): "same",
    ("lower", "lower"): "same",
    ("higher", "lower"): "opposite",
    ("lower", "higher"): "opposite",
}


def get_stat_correlation(stat1: str, stat2: str) -> float:
    """
    Get correlation coefficient between two stats.
    
    Args:
        stat1: First stat type
        stat2: Second stat type
        
    Returns:
        Correlation coefficient (-1.0 to 1.0)
    """
    stat1_lower = stat1.lower()
    stat2_lower = stat2.lower()
    
    # Check direct key
    key = (stat1_lower, stat2_lower)
    if key in STAT_CORRELATIONS:
        return STAT_CORRELATIONS[key]
    
    # Check reversed key
    key_rev = (stat2_lower, stat1_lower)
    if key_rev in STAT_CORRELATIONS:
        return STAT_CORRELATIONS[key_rev]
    
    # No correlation data - assume moderate positive
    return 0.30  # Default assumption: mild positive


@dataclass
class CorrelatedGroup:
    """A group of edges that are correlated."""
    player: str
    edges: List[Dict] = field(default_factory=list)
    effective_correlation: float = 0.0
    diversification_penalty: float = 0.0
    recommended_sizing: str = "1x"  # "1x", "0.5x", "0.25x"
    warning: str = ""


def calculate_direction_adjusted_correlation(
    corr: float, dir1: str, dir2: str
) -> float:
    """
    Adjust correlation based on bet directions.
    
    If betting LOWER strokes and HIGHER birdies, the underlying correlation
    is POSITIVE (both bets win if player has good round), even though the
    stat correlation is negative.
    
    Args:
        corr: Raw stat correlation
        dir1: Direction of first bet ("higher" or "lower")
        dir2: Direction of second bet
        
    Returns:
        Direction-adjusted correlation
    """
    alignment = DIRECTION_ALIGNMENT.get(
        (dir1.lower(), dir2.lower()), "same"
    )
    
    if alignment == "opposite":
        # Opposite directions on inversely correlated stats = SAME BET
        # e.g., LOWER strokes + HIGHER birdies both win if player scores well
        return -corr
    else:
        return corr


def detect_correlated_groups(edges: List[Dict]) -> List[CorrelatedGroup]:
    """
    Detect groups of correlated edges (same-player, correlated stats).
    
    Args:
        edges: List of edge dictionaries with player, stat, direction
        
    Returns:
        List of CorrelatedGroup objects
    """
    # Group by player first
    player_edges = defaultdict(list)
    for edge in edges:
        player = edge.get("player", edge.get("entity", ""))
        player_edges[player.lower()].append(edge)
    
    groups = []
    
    for player, p_edges in player_edges.items():
        if len(p_edges) < 2:
            continue  # No correlation possible with single edge
        
        # Calculate pairwise correlations
        max_correlation = 0.0
        total_correlation = 0.0
        pairs = 0
        
        for i, edge1 in enumerate(p_edges):
            for edge2 in p_edges[i + 1:]:
                stat1 = edge1.get("stat", edge1.get("market", ""))
                stat2 = edge2.get("stat", edge2.get("market", ""))
                dir1 = edge1.get("direction", "higher")
                dir2 = edge2.get("direction", "higher")
                
                raw_corr = get_stat_correlation(stat1, stat2)
                adj_corr = calculate_direction_adjusted_correlation(
                    raw_corr, dir1, dir2
                )
                
                total_correlation += abs(adj_corr)
                max_correlation = max(max_correlation, abs(adj_corr))
                pairs += 1
        
        avg_correlation = total_correlation / pairs if pairs > 0 else 0
        
        # Only flag if correlation is meaningful
        if max_correlation > 0.50:
            group = CorrelatedGroup(
                player=player.title(),
                edges=p_edges,
                effective_correlation=max_correlation,
            )
            
            # Calculate penalty and sizing recommendation
            if max_correlation > 0.75:
                group.diversification_penalty = 0.50
                group.recommended_sizing = "0.5x"
                group.warning = (
                    f"⚠️ HIGHLY CORRELATED: {len(p_edges)} props on {player.title()} "
                    f"are {max_correlation:.0%} correlated. Consider betting only 1."
                )
            elif max_correlation > 0.50:
                group.diversification_penalty = 0.25
                group.recommended_sizing = "0.75x"
                group.warning = (
                    f"⚡ MODERATE CORRELATION: {len(p_edges)} props on {player.title()} "
                    f"share {max_correlation:.0%} correlation. Reduce unit size."
                )
            
            groups.append(group)
    
    return groups


def apply_correlation_penalties(edges: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """
    Apply correlation penalties to edge probabilities and generate warnings.
    
    Args:
        edges: List of edge dictionaries
        
    Returns:
        Tuple of (modified edges, list of warning strings)
    """
    groups = detect_correlated_groups(edges)
    warnings = []
    
    # Build player-to-penalty map
    player_penalties = {}
    for group in groups:
        player_penalties[group.player.lower()] = group.diversification_penalty
        warnings.append(group.warning)
    
    # Apply penalties
    modified_edges = []
    for edge in edges:
        edge_copy = edge.copy()
        player = edge.get("player", edge.get("entity", "")).lower()
        
        if player in player_penalties:
            penalty = player_penalties[player]
            if "probability" in edge_copy:
                orig_prob = edge_copy["probability"]
                # Correlation penalty reduces effective edge
                edge_copy["probability"] = orig_prob * (1 - penalty * 0.5)
                edge_copy["correlation_penalty"] = penalty
                edge_copy["original_probability"] = orig_prob
        
        modified_edges.append(edge_copy)
    
    return modified_edges, warnings


def get_correlation_report(edges: List[Dict]) -> str:
    """
    Generate human-readable correlation report.
    
    Args:
        edges: List of edges to analyze
        
    Returns:
        Formatted report string
    """
    groups = detect_correlated_groups(edges)
    
    if not groups:
        return "✅ No significant correlations detected - portfolio is diversified."
    
    lines = [
        "=" * 60,
        "CORRELATION ANALYSIS REPORT",
        "=" * 60,
    ]
    
    for group in groups:
        lines.append(f"\n🔗 {group.player.upper()}")
        lines.append(f"   Correlation: {group.effective_correlation:.0%}")
        lines.append(f"   Sizing: {group.recommended_sizing} per leg")
        lines.append(f"   Props:")
        for edge in group.edges:
            stat = edge.get("stat", edge.get("market", "?"))
            direction = edge.get("direction", "?").upper()
            line = edge.get("line", "?")
            lines.append(f"      • {stat} {direction} {line}")
        if group.warning:
            lines.append(f"   {group.warning}")
    
    lines.append("\n" + "=" * 60)
    lines.append("RECOMMENDATION: Avoid stacking correlated props in same parlay")
    lines.append("=" * 60)
    
    return "\n".join(lines)


# =============================================================================
# TEST / DEMO
# =============================================================================

if __name__ == "__main__":
    # Test with sample edges
    test_edges = [
        {"player": "Justin Rose", "stat": "Strokes", "direction": "lower", "line": 70.5, "probability": 0.62},
        {"player": "Justin Rose", "stat": "Birdies", "direction": "higher", "line": 3.5, "probability": 0.58},
        {"player": "Hideki Matsuyama", "stat": "Strokes", "direction": "lower", "line": 69.5, "probability": 0.61},
        {"player": "Jason Day", "stat": "Bogeys", "direction": "lower", "line": 2.5, "probability": 0.55},
    ]
    
    print("Testing correlation detection...")
    report = get_correlation_report(test_edges)
    print(report)
    
    print("\n\nTesting penalty application...")
    modified, warnings = apply_correlation_penalties(test_edges)
    for edge in modified:
        player = edge["player"]
        if "correlation_penalty" in edge:
            print(f"{player}: {edge['original_probability']:.0%} → {edge['probability']:.0%} (penalty: {edge['correlation_penalty']:.0%})")
        else:
            print(f"{player}: {edge['probability']:.0%} (no penalty)")
