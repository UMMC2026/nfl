"""
CBB Stat Rank Explainer - Top-5 picks per stat category
=========================================================
Based on: analysis/nba/stat_rank_explainer.py

Provides enhanced stat rankings for CBB props including:
- Top 5 picks per stat category
- Actionable insights (overs/unders to consider)
- By-category breakdown with delta percentages
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# CBB-specific stats (including Underdog combo stats)
STAT_ALIASES = {
    # Single stats
    "points": "PTS",
    "rebounds": "REB", 
    "assists": "AST",
    "3pm": "3PM",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TOV",
    # Combo stats
    "pra": "PRA",
    "pts+reb": "PR",
    "pts+ast": "PA",
    "reb+ast": "RA",
    "pts+reb+ast": "PRA",
}

# Required stats for CBB analysis
REQUIRED_STATS = ["PTS", "REB", "AST", "3PM", "PRA", "PA", "RA", "PR"]

# Stat display names
STAT_DISPLAY_NAMES = {
    "PTS": "Points",
    "REB": "Rebounds",
    "AST": "Assists",
    "3PM": "3-Pointers",
    "PRA": "PTS+REB+AST",
    "PA": "PTS+AST",
    "RA": "REB+AST",
    "PR": "PTS+REB",
    "STL": "Steals",
    "BLK": "Blocks",
    "TOV": "Turnovers",
}

# Reliability weights for CBB stats (lower than NBA due to variance)
RELIABILITY_WEIGHTS = {
    "PTS": 0.90,
    "REB": 0.85,
    "AST": 0.80,
    "3PM": 0.70,  # High variance in CBB
    "PRA": 0.88,
    "PA": 0.85,
    "RA": 0.82,
    "PR": 0.85,
    "STL": 0.65,
    "BLK": 0.65,
    "TOV": 0.70,
}


@dataclass
class RankedPick:
    """A single ranked pick with computed metrics."""
    player: str
    team: str
    stat: str
    line: float
    direction: str
    probability: float
    mean: float
    delta_pct: float
    edge_quality: str
    tier: str = "SKIP"  # LEAN, STRONG, SKIP from governance
    skip_reason: str = ""  # Why it was skipped
    opponent: str = ""  # Opponent code (for context gating)
    
    @property
    def is_actionable(self) -> bool:
        """Check if this pick is actionable under governance.

        Governance update: until schedule/opponent mapping is reliable,
        any pick without a real opponent ("", "UNK") is treated as
        non-actionable even if its tier is LEAN/STRONG/SLAM.
        """
        if self.tier not in ["LEAN", "STRONG", "SLAM"]:
            return False
        opp = (self.opponent or "").upper()
        return bool(opp) and opp != "UNK"
    
    def to_dict(self) -> dict:
        return {
            "player": self.player,
            "team": self.team,
            "stat": self.stat,
            "line": self.line,
            "direction": self.direction,
            "probability": self.probability,
            "mean": self.mean,
            "delta_pct": self.delta_pct,
            "edge_quality": self.edge_quality,
            "tier": self.tier,
            "skip_reason": self.skip_reason,
        }


@dataclass 
class StatRankingResult:
    """Result of stat ranking computation."""
    top_5_by_stat: Dict[str, List[RankedPick]]
    coverage_flags: Dict[str, str]
    total_picks_analyzed: int
    stats_with_data: int
    all_actionable: List[RankedPick] = field(default_factory=list)  # All LEAN/STRONG picks

    def to_dict(self) -> dict:
        return {
            "top_5_by_stat": {
                stat: [p.to_dict() for p in picks] 
                for stat, picks in self.top_5_by_stat.items()
            },
            "all_actionable": [p.to_dict() for p in self.all_actionable],
            "coverage_flags": self.coverage_flags,
            "total_picks_analyzed": self.total_picks_analyzed,
            "stats_with_data": self.stats_with_data,
        }


def normalize_stat(raw_stat: str) -> str:
    """Normalize a raw stat string to standard format."""
    if not raw_stat:
        return "UNK"
    
    clean = raw_stat.lower().strip()
    
    # Check direct alias
    if clean in STAT_ALIASES:
        return STAT_ALIASES[clean]
    
    # Check for combo patterns
    if "+" in clean:
        # Handle pts+ast, reb+ast, etc.
        if "pts" in clean and "ast" in clean and "reb" not in clean:
            return "PA"
        if "reb" in clean and "ast" in clean and "pts" not in clean:
            return "RA"
        if "pts" in clean and "reb" in clean and "ast" not in clean:
            return "PR"
        if "pts" in clean and "reb" in clean and "ast" in clean:
            return "PRA"
    
    # Fallback to uppercase
    return clean.upper()


def rank_picks_by_stat(picks: List[Dict], strict: bool = False) -> StatRankingResult:
    """
    Rank CBB picks by stat category, return top 5 per stat.
    
    Args:
        picks: List of pick dictionaries with player, stat, line, etc.
        strict: If True, only include stats in REQUIRED_STATS
        
    Returns:
        StatRankingResult with top 5 picks per stat category
    """
    stat_buckets: Dict[str, List[Dict]] = {}
    
    for pick in picks:
        raw_stat = (pick.get("stat") or "").strip()
        normalized = normalize_stat(raw_stat)
        
        if strict and normalized not in REQUIRED_STATS:
            continue
        
        if normalized not in stat_buckets:
            stat_buckets[normalized] = []
        stat_buckets[normalized].append(pick)
    
    top_5_by_stat = {}
    coverage_flags = {}
    all_actionable: List[RankedPick] = []  # Collect ALL LEAN/STRONG picks
    
    for stat, bucket in stat_buckets.items():
        if not bucket:
            coverage_flags[stat] = "NO_DATA"
            continue
            
        ranked = []
        for p in bucket:
            # Get mean from various possible fields
            mean = (
                p.get("player_mean") or 
                p.get("mu") or 
                p.get("mean") or
                p.get("estimated_mean") or
                0
            )
            line = float(p.get("line", 0) or 0)
            prob = float(p.get("probability", 0.5) or 0.5)
            opponent = (p.get("opponent") or "").strip()
            
            # Calculate delta percentage
            if mean > 0 and line > 0:
                delta_pct = ((mean - line) / line) * 100
            else:
                delta_pct = 0
            
            # Determine edge quality based on delta
            if abs(delta_pct) > 30:
                edge_quality = "STRONG"
            elif abs(delta_pct) > 15:
                edge_quality = "SOLID"
            else:
                edge_quality = "LEAN"
            
            ranked.append(RankedPick(
                player=p.get("player", "Unknown"),
                team=p.get("team", "UNK"),
                stat=stat,
                line=line,
                direction=p.get("direction", "higher"),
                probability=prob,
                mean=float(mean),
                delta_pct=delta_pct,
                edge_quality=edge_quality,
                tier=p.get("tier", "SKIP"),  # Get tier from governance
                skip_reason=p.get("skip_reason", ""),  # Get skip reason
                opponent=opponent,
            ))
        
        # Sort by absolute delta percentage (biggest edge first)
        ranked.sort(key=lambda x: abs(x.delta_pct), reverse=True)
        top_5_by_stat[stat] = ranked[:5]
        coverage_flags[stat] = "OK"
        
        # Also collect ALL actionable picks (not just top 5)
        all_actionable.extend([p for p in ranked if p.is_actionable])
    
    # Mark missing required stats
    for stat in REQUIRED_STATS:
        if stat not in coverage_flags:
            coverage_flags[stat] = "NO_DATA"
    
    stats_with_data = sum(1 for v in coverage_flags.values() if v == "OK")
    
    # Sort actionable by probability (best first)
    all_actionable.sort(key=lambda x: x.probability, reverse=True)
    
    return StatRankingResult(
        top_5_by_stat=top_5_by_stat,
        coverage_flags=coverage_flags,
        total_picks_analyzed=len(picks),
        stats_with_data=stats_with_data,
        all_actionable=all_actionable,
    )


def format_top5_for_display(rankings: StatRankingResult) -> str:
    """Format Top-5 rankings for simple console display."""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  CBB STAT RANKINGS — Top-5 by Category")
    lines.append("=" * 60)
    
    for stat, picks in sorted(rankings.top_5_by_stat.items()):
        if not picks:
            continue
        
        display_name = STAT_DISPLAY_NAMES.get(stat, stat)
        lines.append(f"\n  {stat} ({display_name}):")
        
        for i, p in enumerate(picks, 1):
            dir_sym = "▲" if p.direction.lower() in ["higher", "over"] else "▼"
            dir_word = "OVER" if p.direction.lower() in ["higher", "over"] else "UNDER"
            lines.append(
                f"    {i}. {p.player:<18} {dir_sym}{dir_word} {p.line:<5} "
                f"(μ={p.mean:.1f}, Δ={p.delta_pct:+.0f}%)"
            )
    
    # Summary
    no_data = [k for k, v in rankings.coverage_flags.items() if v == "NO_DATA"]
    if no_data:
        lines.append(f"\n  [NO DATA]: {', '.join(no_data)}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def format_enhanced_report(rankings: StatRankingResult) -> str:
    """Format CBB stat rankings as enhanced readable report."""
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("  🏀 CBB ENHANCED STAT RANKINGS REPORT")
    lines.append("  " + "-" * 40)
    lines.append(f"  📊 Total Picks Analyzed: {rankings.total_picks_analyzed}")
    lines.append(f"  ✅ Stats With Data: {rankings.stats_with_data}/{len(rankings.coverage_flags)}")
    lines.append(f"  🎯 Actionable Picks: {len(rankings.all_actionable)}")
    lines.append("=" * 70)
    
    # Use pre-computed actionable picks from rankings (v2.3)
    actionable_picks = rankings.all_actionable
    
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "🏆 ACTIONABLE PICKS (LEAN/STRONG Only)".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    lines.append("")
    
    if not actionable_picks:
        lines.append("  ⚠️  NO ACTIONABLE PICKS ON THIS SLATE")
        lines.append("      All picks failed gates (minutes, games, probability, context)")
        lines.append("")
    else:
        for i, pick in enumerate(actionable_picks[:7], 1):
            dir_sym = "▲" if pick.direction.lower() in ["higher", "over"] else "▼"
            dir_word = "OVER" if pick.direction.lower() in ["higher", "over"] else "UNDER"
            display_stat = STAT_DISPLAY_NAMES.get(pick.stat, pick.stat)
            tier_badge = f"[{pick.tier}]" if pick.tier else ""
            
            lines.append(f"  {i}. {pick.player} ({pick.team}) {tier_badge}")
            lines.append(f"     📊 {display_stat}: {dir_sym} {dir_word} {pick.line}")
            lines.append(f"     📈 Mean: {pick.mean:.1f} | Prob: {pick.probability:.1%} | Delta: {pick.delta_pct:+.1f}%")
            
            # Insight
            if pick.delta_pct > 20:
                lines.append(f"     💡 Line {abs(pick.delta_pct):.0f}% below mean — OVER value")
            elif pick.delta_pct < -20:
                lines.append(f"     💡 Line {abs(pick.delta_pct):.0f}% above mean — UNDER value")
            lines.append("")
    
    # Actionable Insights - ONLY LEAN/STRONG picks (v2.2)
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "💡 ACTIONABLE INSIGHTS (LEAN/STRONG Only)".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    lines.append("")
    
    # Overs to consider — only ACTIONABLE picks where direction=OVER AND delta > 0 (v2.2)
    overs = [p for p in actionable_picks 
             if p.direction.lower() in ["higher", "over"] and p.delta_pct > 5][:3]
    # Unders to consider — only ACTIONABLE picks where direction=UNDER AND delta < 0 (v2.2)
    unders = [p for p in actionable_picks 
              if p.direction.lower() in ["lower", "under"] and p.delta_pct < -5][:3]
    
    if overs:
        lines.append("  🔥 OVERS TO CONSIDER:")
        for p in overs:
            lines.append(f"     • {p.player} {p.stat} O{p.line} [{p.tier}] (Prob: {p.probability:.1%}, Mean: {p.mean:.1f})")
    else:
        lines.append("  🔥 OVERS TO CONSIDER: None passed gates")
    
    lines.append("")
    
    if unders:
        lines.append("  🔻 UNDERS TO CONSIDER:")
        for p in unders:
            lines.append(f"     • {p.player} {p.stat} U{p.line} [{p.tier}] (Prob: {p.probability:.1%}, Mean: {p.mean:.1f})")
    else:
        lines.append("  🔻 UNDERS TO CONSIDER: None passed gates")
    
    # Detailed By-Category Breakdown
    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + "📋 DETAILED BY-CATEGORY BREAKDOWN".center(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")
    
    for stat, picks in sorted(rankings.top_5_by_stat.items()):
        if not picks:
            continue
        
        display_name = STAT_DISPLAY_NAMES.get(stat, stat)
        lines.append("")
        lines.append(f"  ── {stat} ({display_name}) ──")
        
        for i, p in enumerate(picks, 1):
            dir_sym = "▲" if p.direction.lower() in ["higher", "over"] else "▼"
            dir_word = "OVER" if p.direction.lower() in ["higher", "over"] else "UNDER"
            tier_mark = "✓" if p.is_actionable else "✗"
            lines.append(
                f"     {i}. {p.player:<18} {dir_sym}{dir_word}  {p.line:<5} "
                f"{tier_mark}{p.tier:<6} (μ={p.mean:.1f}, Δ={p.delta_pct:+.0f}%)"
            )
    
    # No-data stats
    no_data = [k for k, v in rankings.coverage_flags.items() if v == "NO_DATA"]
    if no_data:
        lines.append("")
        lines.append(f"  [NO DATA in slate]: {', '.join(sorted(no_data))}")
    
    # Footer
    lines.append("")
    lines.append("=" * 70)
    lines.append("  Report generated by CBB Stat Rank Explainer v2.2")
    lines.append("  ✓ = LEAN/STRONG (actionable)  |  ✗ = SKIP (gate failed)")
    lines.append("  Note: Only ✓ picks should be used for entries")
    lines.append("=" * 70)
    
    return "\n".join(lines)


# =============================================================================
# CLI / STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    import json
    from pathlib import Path
    
    print("=" * 70)
    print("  CBB STAT RANK EXPLAINER — STANDALONE TEST")
    print("=" * 70)
    
    # Look for CBB analysis files
    cbb_outputs = Path(__file__).parent.parent / "outputs"
    
    if cbb_outputs.exists():
        json_files = sorted(cbb_outputs.glob("cbb_edges_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if json_files:
            latest = json_files[0]
            print(f"Loading: {latest.name}")
            
            with open(latest, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            edges = data if isinstance(data, list) else data.get("edges", [])
            print(f"Found {len(edges)} edges")
            
            result = rank_picks_by_stat(edges)
            print(format_enhanced_report(result))
        else:
            print("No CBB edge files found in outputs/")
    else:
        print(f"CBB outputs directory not found: {cbb_outputs}")
