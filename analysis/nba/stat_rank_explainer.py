"""
Stat-Wise Top-5 Explanation Engine
==================================

PURPOSE: Compute, rank, explain, and export Top-5 players per stat category.

POSITION IN PIPELINE:
    Ingest → Features → Probability → Gates → MC (optional)
    → ✅ Stat-Wise Ranking + Explanation ← THIS MODULE
    → Report / Cheat Sheet / Export

NON-DESTRUCTIVE: This module does NOT change probabilities, gates, or picks.
It provides INTERPRETABILITY only.

Author: System
Version: 1.0.0
"""

import math
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS (GOVERNANCE-LOCKED)
# =============================================================================

REQUIRED_STATS = ["PTS", "REB", "AST", "3PM", "PRA", "STL", "BLK", "STOCKS", "TOV", "PA", "RA", "PR"]

# Stat aliases for normalization
STAT_ALIASES = {
    # Points
    "points": "PTS",
    "pts": "PTS",
    # Rebounds
    "rebounds": "REB",
    "rebs": "REB",
    "reb": "REB",
    # Assists
    "assists": "AST",
    "ast": "AST",
    # 3-Pointers
    "3pm": "3PM",
    "threes": "3PM",
    "3pt": "3PM",
    "three_pointers": "3PM",
    # Combined: PTS+REB+AST
    "pts+rebs+asts": "PRA",
    "pra": "PRA",
    "pts+reb+ast": "PRA",
    "pa": "PRA",  # Underdog uses PA for pts+reb+ast
    # Steals
    "steals": "STL",
    "stl": "STL",
    # Blocks
    "blocks": "BLK",
    "blk": "BLK",
    # Stocks (STL+BLK)
    "stocks": "STOCKS",
    "stl+blk": "STOCKS",
    # Turnovers
    "turnovers": "TOV",
    "tov": "TOV",
    "to": "TOV",
    # Combined stats - map to NEW categories or closest equivalent
    "pts+ast": "PA",    # Points + Assists combo  
    "reb+ast": "RA",    # Rebounds + Assists combo
    "pts+reb": "PR",    # Points + Rebounds combo
}

# Reliability weights per stat (prevents PTS bias)
RELIABILITY_WEIGHTS = {
    "REB": 1.15,      # Low variance, stable
    "AST": 1.15,      # Low variance, role-dependent
    "3PM": 1.10,      # Moderate variance
    "STOCKS": 1.10,   # Combined metric, stable
    "STL": 1.05,      # Low volume, noisy
    "BLK": 1.05,      # Low volume, noisy
    "PRA": 1.00,      # Combined, moderate variance
    "PTS": 0.90,      # High variance, usage-dependent
    "TOV": 0.85,      # Highly contextual
    # Underdog combo stats
    "PA": 1.05,       # Points + Assists - moderate
    "RA": 1.10,       # Rebounds + Assists - stable combo
    "PR": 1.00,       # Points + Rebounds - moderate
}

# League standard deviations (empirical estimates for penalty calc)
LEAGUE_STD_DEFAULTS = {
    "PTS": 8.5,
    "REB": 3.2,
    "AST": 2.8,
    "3PM": 1.2,
    "PRA": 10.5,
    "STL": 0.8,
    "BLK": 0.7,
    "STOCKS": 1.2,
    "TOV": 1.1,
    # Underdog combo stats
    "PA": 7.0,        # Points + Assists
    "RA": 4.5,        # Rebounds + Assists  
    "PR": 9.0,        # Points + Rebounds
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RankedPick:
    """A pick with computed ranking score and explanation."""
    player: str
    team: str
    opponent: str
    stat: str
    line: float
    prob_over: float
    prob_under: float
    mean: float
    std: float
    sample_size: int
    role_tag: str
    market_tax: float
    flags: List[str]
    
    # Computed fields
    ranking_score: float = 0.0
    side: str = ""  # "OVER" or "UNDER"
    best_prob: float = 0.0
    line_delta: float = 0.0
    line_delta_pct: float = 0.0
    explanation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Export to JSON-safe dict."""
        return {
            "player": self.player,
            "team": self.team,
            "opponent": self.opponent,
            "side": self.side,
            "probability": round(self.best_prob, 3),
            "line": self.line,
            "mean": round(self.mean, 1),
            "std": round(self.std, 2),
            "line_delta_pct": round(self.line_delta_pct, 1),
            "ranking_score": round(self.ranking_score, 4),
            "role": self.role_tag,
            "why": self.explanation,
            "flags": self.flags,
        }


@dataclass
class StatRankingResult:
    """Result container for all stat rankings."""
    top_5_by_stat: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    coverage_flags: Dict[str, str] = field(default_factory=dict)
    total_picks_analyzed: int = 0
    stats_with_data: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "top_5_by_stat": self.top_5_by_stat,
            "coverage_flags": self.coverage_flags,
            "meta": {
                "total_picks_analyzed": self.total_picks_analyzed,
                "stats_with_data": self.stats_with_data,
                "stats_missing": [s for s in REQUIRED_STATS if s not in self.top_5_by_stat],
            }
        }


# =============================================================================
# INPUT VALIDATION (STRICT)
# =============================================================================

class InputValidationError(Exception):
    """Raised when pick is missing required fields."""
    pass


def validate_pick(pick: Any, index: int) -> None:
    """
    Validate that a pick has all required fields.
    
    Raises InputValidationError if any field is missing.
    NO SILENT FALLBACK.
    """
    required_fields = [
        "player", "team", "stat", "line"
    ]
    
    # Check base required fields
    for field_name in required_fields:
        value = getattr(pick, field_name, None) or pick.get(field_name) if isinstance(pick, dict) else getattr(pick, field_name, None)
        if value is None:
            raise InputValidationError(
                f"Pick {index}: Missing required field '{field_name}'"
            )


def extract_pick_data(pick: Any) -> Dict[str, Any]:
    """
    Extract pick data from various formats (dict, object, dataclass).
    Returns normalized dict with all fields.
    """
    if isinstance(pick, dict):
        data = pick
    else:
        # Object/dataclass - extract attributes
        data = {}
        for attr in ["player", "team", "opponent", "stat", "line", "direction",
                     "prob_over", "prob_under", "probability", "confidence",
                     "mean", "mu", "std", "sigma", "sample_size", "games",
                     "role_tag", "role", "archetype", "market_tax", "flags"]:
            val = getattr(pick, attr, None)
            if val is not None:
                data[attr] = val
    
    # Normalize stat name
    raw_stat = data.get("stat", data.get("market", "")).lower()
    normalized_stat = STAT_ALIASES.get(raw_stat, raw_stat.upper())
    
    # Extract probabilities
    prob_over = data.get("prob_over")
    prob_under = data.get("prob_under")
    
    # If not explicit, derive from direction + probability
    if prob_over is None or prob_under is None:
        prob = data.get("probability") or data.get("confidence", 50) / 100
        direction = data.get("direction", "higher").lower()
        if direction in ("higher", "over"):
            prob_over = prob
            prob_under = 1 - prob
        else:
            prob_under = prob
            prob_over = 1 - prob
    
    return {
        "player": data.get("player", "Unknown"),
        "team": data.get("team", "UNK"),
        "opponent": data.get("opponent", "UNK"),
        "stat": normalized_stat,
        "line": float(data.get("line", 0)),
        "prob_over": float(prob_over or 0.5),
        "prob_under": float(prob_under or 0.5),
        "mean": float(data.get("mean") or data.get("mu") or data.get("line", 0)),
        "std": float(data.get("std") or data.get("sigma") or 3.0),
        "sample_size": int(data.get("sample_size") or data.get("games") or 10),
        "role_tag": data.get("role_tag") or data.get("role") or data.get("archetype") or "ROLE",
        "market_tax": float(data.get("market_tax") or 0.0),
        "flags": list(data.get("flags") or []),
    }


# =============================================================================
# RANKING CALCULATIONS
# =============================================================================

def compute_ranking_score(
    prob_over: float,
    prob_under: float,
    stat: str,
    std: float,
    sample_size: int,
    mean: float = 0.0,
    line: float = 0.0,
) -> Tuple[float, str, bool]:
    """
    Compute ranking score using the formula:
    
    ranking_score = max(prob_over, prob_under) 
                    × reliability_weight 
                    × variance_penalty 
                    × sample_penalty
                    × directional_consistency
    
    Returns: (score, best_side, is_directionally_consistent)
    
    IMPORTANT: When prob_over == prob_under (no probability data),
    we determine side based on mean vs line instead.
    
    DIRECTIONAL CONSISTENCY RULE (v2.1):
    - OVER picks MUST have mean >= line (positive delta)
    - UNDER picks MUST have mean <= line (negative delta)
    - Violations get heavy penalty (0.3x score) and flagged
    """
    # Best probability and side
    # FIX: When no probability data (both 0.5), use mean vs line to determine side
    if prob_over == prob_under == 0.5 and mean > 0 and line > 0:
        # No probability data - use mean vs line
        if mean > line:
            best_side = "OVER"
            # Estimate probability from delta (rough heuristic)
            delta_pct = (mean - line) / line if line > 0 else 0
            best_prob = min(0.75, 0.5 + delta_pct * 0.5)  # Cap at 75%
        else:
            best_side = "UNDER"
            delta_pct = (line - mean) / line if line > 0 else 0
            best_prob = min(0.75, 0.5 + delta_pct * 0.5)  # Cap at 75%
    elif prob_over >= prob_under:
        best_prob = prob_over
        best_side = "OVER"
    else:
        best_prob = prob_under
        best_side = "UNDER"
    
    # DIRECTIONAL CONSISTENCY CHECK (v2.1)
    # OVER requires mean >= line, UNDER requires mean <= line
    is_consistent = True
    directional_penalty = 1.0
    if mean > 0 and line > 0:
        if best_side == "OVER" and mean < line:
            is_consistent = False
            directional_penalty = 0.3  # Heavy penalty for directional mismatch
            logger.debug(f"Directional mismatch: OVER but mean({mean}) < line({line})")
        elif best_side == "UNDER" and mean > line:
            is_consistent = False
            directional_penalty = 0.3
            logger.debug(f"Directional mismatch: UNDER but mean({mean}) > line({line})")
    
    # Reliability weight (stat-specific)
    reliability_weight = RELIABILITY_WEIGHTS.get(stat.upper(), 1.0)
    
    # Variance penalty: min(1.0, league_std / pick.std)
    league_std = LEAGUE_STD_DEFAULTS.get(stat.upper(), 5.0)
    if std > 0:
        variance_penalty = min(1.0, league_std / std)
    else:
        variance_penalty = 1.0
    
    # Sample penalty: min(1.0, log(sample_size + 1) / log(30))
    if sample_size > 0:
        sample_penalty = min(1.0, math.log(sample_size + 1) / math.log(30))
    else:
        sample_penalty = 0.5  # Heavy penalty for no sample
    
    # Final score (includes directional consistency penalty)
    ranking_score = best_prob * reliability_weight * variance_penalty * sample_penalty * directional_penalty
    
    return ranking_score, best_side, is_consistent


def compute_line_deviation(mean: float, line: float) -> Tuple[float, float]:
    """
    Compute line deviation (absolute and percentage).
    
    Returns: (line_delta, line_delta_pct)
    
    Positive = mean ABOVE line
    Negative = mean BELOW line
    """
    line_delta = mean - line
    
    if line > 0:
        line_delta_pct = (line_delta / line) * 100
    else:
        line_delta_pct = 0.0
    
    return line_delta, line_delta_pct


# =============================================================================
# EXPLANATION GENERATOR (DETERMINISTIC - NO LLM)
# =============================================================================

def generate_explanation(
    stat: str,
    role_tag: str,
    line_delta_pct: float,
    market_tax: float,
    std: float,
    sample_size: int,
    flags: List[str],
) -> str:
    """
    Generate deterministic, template-based explanation.
    
    NO narratives, NO adjectives.
    EXPLAINABLE MATH ONLY.
    """
    reasons = []
    
    # Low variance stat bonus
    if stat.upper() in ["REB", "AST"]:
        reasons.append("Low variance stat")
    
    # Role security
    if role_tag.upper() in ["STAR", "HUB", "PRIMARY_CREATOR", "SECONDARY_CREATOR"]:
        reasons.append("Role-secure minutes")
    
    # Line misalignment
    if abs(line_delta_pct) > 10:
        direction = "above" if line_delta_pct > 0 else "below"
        reasons.append(f"Line {abs(line_delta_pct):.0f}% {direction} mean")
    
    # Market inflation
    if market_tax > 0.05:
        reasons.append(f"Market inflation +{market_tax*100:.0f}%")
    
    # High variance warning
    league_std = LEAGUE_STD_DEFAULTS.get(stat.upper(), 5.0)
    if std > league_std * 1.25:
        reasons.append("High variance — capped confidence")
    
    # Small sample warning
    if sample_size < 10:
        reasons.append(f"Small sample (n={sample_size})")
    
    # Gate flags
    critical_flags = [f for f in flags if any(x in f.upper() for x in ["VARIANCE", "VOLATILE", "B2B", "INJURY"])]
    if critical_flags:
        reasons.append(f"Flags: {', '.join(critical_flags[:2])}")
    
    return "; ".join(reasons) if reasons else "Standard edge"


# =============================================================================
# MAIN RANKING ENGINE
# =============================================================================

def rank_picks_by_stat(picks: List[Any], strict: bool = False) -> StatRankingResult:
    """
    Main entry point: Rank picks and return Top-5 per stat.
    
    Args:
        picks: List of Pick objects or dicts
        strict: If True, raise on validation errors. If False, skip bad picks.
    
    Returns:
        StatRankingResult with top_5_by_stat dict
    """
    result = StatRankingResult()
    stat_groups: Dict[str, List[RankedPick]] = defaultdict(list)
    
    # Process each pick
    for i, pick in enumerate(picks):
        try:
            # Extract and validate
            data = extract_pick_data(pick)
            stat = data["stat"]
            
            # Skip if stat not in our required list
            if stat not in REQUIRED_STATS:
                # Try to map combined stats
                if stat in ["POINTS", "REBOUNDS", "ASSISTS"]:
                    stat = stat[:3]  # PTS, REB, AST
                elif stat not in REQUIRED_STATS:
                    continue
            
            # Compute ranking score
            ranking_score, best_side, is_consistent = compute_ranking_score(
                prob_over=data["prob_over"],
                prob_under=data["prob_under"],
                stat=stat,
                std=data["std"],
                sample_size=data["sample_size"],
                mean=data["mean"],
                line=data["line"],
            )
            
            # Flag directional inconsistency
            if not is_consistent:
                data["flags"].append("DIRECTIONAL_MISMATCH")
            
            # Compute line deviation
            line_delta, line_delta_pct = compute_line_deviation(
                mean=data["mean"],
                line=data["line"],
            )
            
            # Generate explanation
            explanation = generate_explanation(
                stat=stat,
                role_tag=data["role_tag"],
                line_delta_pct=line_delta_pct,
                market_tax=data["market_tax"],
                std=data["std"],
                sample_size=data["sample_size"],
                flags=data["flags"],
            )
            
            # Create RankedPick
            ranked = RankedPick(
                player=data["player"],
                team=data["team"],
                opponent=data["opponent"],
                stat=stat,
                line=data["line"],
                prob_over=data["prob_over"],
                prob_under=data["prob_under"],
                mean=data["mean"],
                std=data["std"],
                sample_size=data["sample_size"],
                role_tag=data["role_tag"],
                market_tax=data["market_tax"],
                flags=data["flags"],
                ranking_score=ranking_score,
                side=best_side,
                best_prob=max(data["prob_over"], data["prob_under"]),
                line_delta=line_delta,
                line_delta_pct=line_delta_pct,
                explanation=explanation,
            )
            
            stat_groups[stat].append(ranked)
            result.total_picks_analyzed += 1
            
        except Exception as e:
            if strict:
                raise
            logger.debug(f"Skipping pick {i}: {e}")
            continue
    
    # Select Top-5 for each stat
    for stat in REQUIRED_STATS:
        picks_for_stat = stat_groups.get(stat, [])
        
        if not picks_for_stat:
            result.coverage_flags[stat] = "NO_DATA"
            continue
        
        # Sort by ranking score (descending)
        sorted_picks = sorted(
            picks_for_stat,
            key=lambda p: p.ranking_score,
            reverse=True
        )
        
        # Deduplicate: keep highest-ranked entry per player
        seen_players = set()
        unique_picks = []
        for p in sorted_picks:
            if p.player not in seen_players:
                unique_picks.append(p)
                seen_players.add(p.player)
        
        # Take Top 5
        top_5 = unique_picks[:5]
        
        # Flag low coverage
        if len(top_5) < 5:
            result.coverage_flags[stat] = f"LOW_COVERAGE ({len(top_5)}/5)"
        
        # Export to dict format
        result.top_5_by_stat[stat] = [p.to_dict() for p in top_5]
        result.stats_with_data += 1
    
    return result


# =============================================================================
# GOVERNANCE ENFORCEMENT
# =============================================================================

def validate_output_schema(result: StatRankingResult) -> bool:
    """
    Governance check: Ensure all required stats are present.
    
    Returns True if valid, raises AssertionError if not.
    """
    missing = [
        stat for stat in REQUIRED_STATS 
        if stat not in result.top_5_by_stat and result.coverage_flags.get(stat) != "NO_DATA"
    ]
    
    if missing:
        raise AssertionError(
            f"Stat ranking schema validation failed. Missing: {missing}"
        )
    
    return True


def is_ranking_enabled() -> bool:
    """Check if Enhanced Stat Rankings feature is enabled."""
    try:
        import json
        from pathlib import Path
        
        settings_path = Path(".analyzer_settings.json")
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return settings.get("enhanced_stat_rankings", True)  # Default ON
    except Exception:
        pass
    
    return True  # Default ON


# =============================================================================
# INTEGRATION FUNCTIONS
# =============================================================================

def inject_rankings_into_report(
    report_data: Dict[str, Any],
    picks: List[Any],
) -> Dict[str, Any]:
    """
    Inject stat rankings into existing report data.
    
    This is the main integration point for the report pipeline.
    """
    if not is_ranking_enabled():
        logger.info("Enhanced Stat Rankings disabled, skipping")
        return report_data
    
    try:
        # Compute rankings
        rankings = rank_picks_by_stat(picks, strict=False)
        
        # Validate schema (governance)
        try:
            validate_output_schema(rankings)
        except AssertionError as e:
            logger.warning(f"Schema validation warning: {e}")
            # Don't abort, just log
        
        # Inject into report
        report_data["top_5_by_stat"] = rankings.top_5_by_stat
        report_data["stat_ranking_meta"] = {
            "coverage_flags": rankings.coverage_flags,
            "total_analyzed": rankings.total_picks_analyzed,
            "stats_with_data": rankings.stats_with_data,
        }
        
        logger.info(
            f"Stat rankings injected: {rankings.stats_with_data} stats, "
            f"{rankings.total_picks_analyzed} picks analyzed"
        )
        
    except Exception as e:
        logger.error(f"Failed to compute stat rankings: {e}")
        # Non-destructive: don't break the pipeline
    
    return report_data


def format_top5_for_display(rankings: StatRankingResult, use_ascii: bool = True) -> str:
    """Format Top-5 rankings for console display.
    
    Args:
        rankings: The ranking result
        use_ascii: If True, use ASCII-safe characters instead of emoji
    """
    # Friendly stat names for display
    STAT_DISPLAY_NAMES = {
        "PTS": "Points",
        "REB": "Rebounds", 
        "AST": "Assists",
        "3PM": "3-Pointers",
        "PRA": "PTS+REB+AST",
        "STL": "Steals",
        "BLK": "Blocks",
        "STOCKS": "STL+BLK",
        "TOV": "Turnovers",
        "PA": "PTS+AST",
        "RA": "REB+AST",
        "PR": "PTS+REB",
    }
    
    lines = []
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "  🏀 TOP-5 PICKS BY STAT CATEGORY".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    
    # Separate stats with data vs no data
    stats_with_data = []
    stats_no_data = []
    
    for stat in REQUIRED_STATS:
        picks = rankings.top_5_by_stat.get(stat, [])
        if picks:
            stats_with_data.append(stat)
        else:
            stats_no_data.append(stat)
    
    # Show stats WITH data first (the important ones)
    for stat in stats_with_data:
        picks = rankings.top_5_by_stat.get(stat, [])
        display_name = STAT_DISPLAY_NAMES.get(stat, stat)
        
        lines.append("")
        lines.append("┌" + "─" * 68 + "┐")
        lines.append(f"│  📊 {stat} ({display_name})".ljust(69) + "│")
        lines.append("├" + "─" * 68 + "┤")
        
        for i, p in enumerate(picks, 1):
            side_icon = "▲" if p["side"] == "OVER" else "▼"
            side_color = "OVER" if p["side"] == "OVER" else "UNDER"
            
            # Determine edge quality
            prob = p['probability']
            delta = abs(p['line_delta_pct'])
            
            if prob >= 0.65 or delta >= 20:
                edge_tag = "🔥 STRONG"
            elif prob >= 0.55 or delta >= 10:
                edge_tag = "✅ SOLID"
            else:
                edge_tag = "➖ LEAN"
            
            # Format player line
            player_line = f"│  {i}. {p['player']:<22} {side_icon} {side_color:<5} {p['line']:<6}"
            lines.append(player_line.ljust(69) + "│")
            
            # Format stats line
            stats_line = f"│     📈 Mean: {p['mean']:<6.1f}  |  Line Delta: {p['line_delta_pct']:+.1f}%  |  {edge_tag}"
            lines.append(stats_line.ljust(69) + "│")
            
            # Format why line if available
            if p.get("why"):
                why_text = p['why'][:55] + "..." if len(p['why']) > 55 else p['why']
                why_line = f"│     💡 {why_text}"
                lines.append(why_line.ljust(69) + "│")
            
            if i < len(picks):
                lines.append("│" + " " * 68 + "│")
        
        lines.append("└" + "─" * 68 + "┘")
    
    # Show compact summary of stats with NO data
    if stats_no_data:
        lines.append("")
        lines.append("┌" + "─" * 68 + "┐")
        lines.append("│  ⚠️  STATS NOT IN TODAY'S SLATE:".ljust(69) + "│")
        
        # Group no-data stats in rows of 4
        no_data_display = [STAT_DISPLAY_NAMES.get(s, s) for s in stats_no_data]
        for i in range(0, len(no_data_display), 4):
            chunk = no_data_display[i:i+4]
            chunk_str = "  •  ".join(chunk)
            lines.append(f"│     {chunk_str}".ljust(69) + "│")
        
        lines.append("└" + "─" * 68 + "┘")
    
    return "\n".join(lines)


def format_enhanced_report(rankings: StatRankingResult) -> str:
    """
    Generate an enhanced, readable report with actionable insights.
    
    Returns a comprehensive report string suitable for display or export.
    """
    STAT_DISPLAY_NAMES = {
        "PTS": "Points", "REB": "Rebounds", "AST": "Assists",
        "3PM": "3-Pointers", "PRA": "PTS+REB+AST", "STL": "Steals",
        "BLK": "Blocks", "STOCKS": "STL+BLK", "TOV": "Turnovers",
        "PA": "PTS+AST", "RA": "REB+AST", "PR": "PTS+REB",
    }
    
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  🏀 ENHANCED STAT RANKINGS REPORT")
    lines.append("  " + "─" * 40)
    lines.append(f"  📊 Total Picks Analyzed: {rankings.total_picks_analyzed}")
    lines.append(f"  ✅ Stats With Data: {rankings.stats_with_data}/{len(REQUIRED_STATS)}")
    lines.append("=" * 70)
    
    # Collect all top picks across categories for "BEST OF THE BEST"
    all_top_picks = []
    for stat, picks in rankings.top_5_by_stat.items():
        for p in picks:
            p['_stat'] = stat
            all_top_picks.append(p)
    
    # CRITICAL FIX (v2.1): Filter out directionally-inconsistent picks
    # OVER picks must have positive delta (mean > line)
    # UNDER picks must have negative delta (mean < line)
    consistent_picks = [
        p for p in all_top_picks
        if (p['side'] == 'OVER' and p['line_delta_pct'] >= 0) or
           (p['side'] == 'UNDER' and p['line_delta_pct'] <= 0) or
           'DIRECTIONAL_MISMATCH' not in p.get('flags', [])
    ]
    
    # Sort by probability (descending) then by DIRECTIONAL delta (favor strong edges)
    # For OVERs: higher positive delta = better
    # For UNDERs: more negative delta = better  
    def directional_sort_key(x):
        prob = x['probability']
        delta = x['line_delta_pct']
        # For OVER: positive delta is good, negative is bad
        # For UNDER: negative delta is good, positive is bad
        if x['side'] == 'OVER':
            directional_value = delta  # Higher is better
        else:
            directional_value = -delta  # More negative (inverted to positive) is better
        return (prob, directional_value)
    
    consistent_picks.sort(key=directional_sort_key, reverse=True)
    
    # SECTION 1: BEST OVERALL PICKS (only directionally consistent)
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "  🏆 BEST OVERALL PICKS (Cross-Category Top 5)".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    
    seen_players = set()
    best_count = 0
    for p in consistent_picks:  # Use filtered list
        if p['player'] in seen_players:
            continue
        if best_count >= 5:
            break
        
        seen_players.add(p['player'])
        best_count += 1
        
        stat_name = STAT_DISPLAY_NAMES.get(p['_stat'], p['_stat'])
        side_icon = "▲" if p["side"] == "OVER" else "▼"
        
        lines.append("")
        lines.append(f"  {best_count}. {p['player']} ({p['team']})")
        lines.append(f"     📊 {stat_name}: {side_icon} {p['side']} {p['line']}")
        lines.append(f"     📈 Mean: {p['mean']:.1f} | Delta: {p['line_delta_pct']:+.1f}%")
        if p.get('why'):
            lines.append(f"     💡 {p['why']}")
    
    # SECTION 2: ACTIONABLE INSIGHTS
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "  💡 ACTIONABLE INSIGHTS".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    
    # Find big delta plays — ONLY directionally consistent (v2.1)
    # OVERs: positive delta (mean > line)
    # UNDERs: negative delta (mean < line)
    big_overs = [p for p in consistent_picks if p['side'] == 'OVER' and p['line_delta_pct'] > 15]
    big_unders = [p for p in consistent_picks if p['side'] == 'UNDER' and p['line_delta_pct'] < -15]
    
    if big_overs:
        lines.append("")
        lines.append("  🔥 OVERS TO CONSIDER (Mean >> Line):")
        for p in big_overs[:3]:
            stat_name = STAT_DISPLAY_NAMES.get(p['_stat'], p['_stat'])
            lines.append(f"     • {p['player']} {stat_name} O{p['line']} (Mean: {p['mean']:.1f}, +{p['line_delta_pct']:.0f}%)")
    
    if big_unders:
        lines.append("")
        lines.append("  🔻 UNDERS TO CONSIDER (Mean << Line):")
        for p in big_unders[:3]:
            stat_name = STAT_DISPLAY_NAMES.get(p['_stat'], p['_stat'])
            lines.append(f"     • {p['player']} {stat_name} U{p['line']} (Mean: {p['mean']:.1f}, {p['line_delta_pct']:.0f}%)")
    
    # SECTION 3: BY-CATEGORY BREAKDOWN
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "  📋 DETAILED BY-CATEGORY BREAKDOWN".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    
    for stat in REQUIRED_STATS:
        picks = rankings.top_5_by_stat.get(stat, [])
        if not picks:
            continue
        
        display_name = STAT_DISPLAY_NAMES.get(stat, stat)
        lines.append("")
        lines.append(f"  ── {stat} ({display_name}) ──")
        
        for i, p in enumerate(picks, 1):
            side_icon = "▲" if p["side"] == "OVER" else "▼"
            lines.append(f"     {i}. {p['player']:<20} {side_icon}{p['side']:<5} {p['line']:<5} (μ={p['mean']:.1f}, Δ={p['line_delta_pct']:+.0f}%)")
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("  Report generated by Stat Rank Explainer v2.0")
    lines.append("=" * 70)
    
    return "\n".join(lines)


# =============================================================================
# CLI / STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    import json
    from pathlib import Path
    
    print("=" * 70)
    print("  STAT RANK EXPLAINER — STANDALONE TEST")
    print("=" * 70)
    
    # Load latest analysis
    out_dir = Path("outputs")
    risk_files = sorted(out_dir.glob("*RISK_FIRST*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not risk_files:
        print("No analysis files found")
        exit(1)
    
    latest = risk_files[0]
    print(f"\nLoading: {latest.name}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    picks = data.get("results", [])
    print(f"Found {len(picks)} picks")
    
    # Run ranking
    result = rank_picks_by_stat(picks)
    
    # Display
    print(format_top5_for_display(result))
    
    # Summary
    print(f"\nTotal analyzed: {result.total_picks_analyzed}")
    print(f"Stats with data: {result.stats_with_data}/{len(REQUIRED_STATS)}")
    print(f"Coverage flags: {result.coverage_flags}")
