"""
NBA Team Context - Defensive/Offensive Rankings, Pace, Coaching Schemes
Updated: January 2026 (2025-26 Season)

Sources: NBA.com/stats, Basketball-Reference, Cleaning the Glass
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class CoachingStyle(Enum):
    UPTEMPO = "uptempo"           # Fast pace, high possessions, run-and-gun
    BALANCED = "balanced"         # Average pace, adaptable
    GRIND = "grind"              # Slow pace, half-court focused, defensive
    MOTION = "motion"            # Ball movement, cuts, off-ball action
    ISO_HEAVY = "iso_heavy"      # Star-driven isolation plays


@dataclass
class TeamContext:
    """Full context for an NBA team."""
    team: str
    def_rating: float          # Points allowed per 100 possessions (lower = better)
    off_rating: float          # Points scored per 100 possessions (higher = better)
    def_rank: int              # 1-30 defensive rank (1 = best)
    off_rank: int              # 1-30 offensive rank (1 = best)
    pace: float                # Possessions per 48 minutes
    pace_rank: int             # 1-30 pace rank (1 = fastest)
    style: CoachingStyle       # Coaching philosophy
    
    # Stat-specific defensive ranks (1 = best at limiting)
    pts_allowed_rank: int      # Points allowed rank
    reb_allowed_rank: int      # Opponent rebounds rank
    ast_allowed_rank: int      # Opponent assists rank
    three_allowed_rank: int    # Opponent 3PM rank
    
    # Context notes
    notes: str = ""


# Full 30-team NBA context (2025-26 Season estimates)
# Defensive Rating: Lower is better defense
# Offensive Rating: Higher is better offense
# Pace: Higher = more possessions = more counting stats opportunity

NBA_TEAM_CONTEXT: Dict[str, TeamContext] = {
    # === ELITE DEFENSES (Top 5) ===
    "CLE": TeamContext(
        team="CLE", def_rating=106.2, off_rating=118.5, def_rank=1, off_rank=3,
        pace=97.8, pace_rank=22, style=CoachingStyle.MOTION,
        pts_allowed_rank=1, reb_allowed_rank=3, ast_allowed_rank=2, three_allowed_rank=4,
        notes="Elite rim protection (Mobley/Allen). Slow pace limits counting stats. Mitchell iso-heavy."
    ),
    "BOS": TeamContext(
        team="BOS", def_rating=107.1, off_rating=120.2, def_rank=2, off_rank=1,
        pace=100.5, pace_rank=12, style=CoachingStyle.MOTION,
        pts_allowed_rank=2, reb_allowed_rank=5, ast_allowed_rank=1, three_allowed_rank=2,
        notes="Switch-everything defense. High 3PA rate. Elite ball movement on offense."
    ),
    "OKC": TeamContext(
        team="OKC", def_rating=107.8, off_rating=117.8, def_rank=3, off_rank=5,
        pace=99.2, pace_rank=15, style=CoachingStyle.BALANCED,
        pts_allowed_rank=3, reb_allowed_rank=2, ast_allowed_rank=4, three_allowed_rank=6,
        notes="Length disrupts passing lanes. SGA iso-heavy. Chet rim protection."
    ),
    "NYK": TeamContext(
        team="NYK", def_rating=108.2, off_rating=116.5, def_rank=4, off_rank=8,
        pace=98.0, pace_rank=20, style=CoachingStyle.GRIND,
        pts_allowed_rank=5, reb_allowed_rank=1, ast_allowed_rank=6, three_allowed_rank=8,
        notes="Physical, rebounding-focused. Brunson heavy usage. OG elite perimeter D."
    ),
    "MEM": TeamContext(
        team="MEM", def_rating=108.5, off_rating=115.2, def_rank=5, off_rank=12,
        pace=100.8, pace_rank=10, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=4, reb_allowed_rank=4, ast_allowed_rank=8, three_allowed_rank=5,
        notes="Athletic, transition-heavy. JJJ rim protection. Fast pace inflates stats."
    ),
    
    # === GOOD DEFENSES (6-10) ===
    "MIA": TeamContext(
        team="MIA", def_rating=109.0, off_rating=112.5, def_rank=6, off_rank=18,
        pace=96.5, pace_rank=26, style=CoachingStyle.GRIND,
        pts_allowed_rank=6, reb_allowed_rank=8, ast_allowed_rank=5, three_allowed_rank=3,
        notes="Zone defense specialist. Very slow pace suppresses counting stats."
    ),
    "HOU": TeamContext(
        team="HOU", def_rating=109.2, off_rating=114.8, def_rank=7, off_rank=14,
        pace=98.5, pace_rank=18, style=CoachingStyle.BALANCED,
        pts_allowed_rank=8, reb_allowed_rank=6, ast_allowed_rank=7, three_allowed_rank=10,
        notes="Young, athletic defense. Sengun facilitates. Thompson versatile."
    ),
    "PHI": TeamContext(
        team="PHI", def_rating=109.5, off_rating=116.0, def_rank=8, off_rank=10,
        pace=97.2, pace_rank=24, style=CoachingStyle.ISO_HEAVY,
        pts_allowed_rank=7, reb_allowed_rank=7, ast_allowed_rank=10, three_allowed_rank=12,
        notes="Embiid anchor when healthy. Maxey speed creates. Load management impacts."
    ),
    "LAC": TeamContext(
        team="LAC", def_rating=109.8, off_rating=115.5, def_rank=9, off_rank=11,
        pace=97.5, pace_rank=23, style=CoachingStyle.BALANCED,
        pts_allowed_rank=10, reb_allowed_rank=10, ast_allowed_rank=9, three_allowed_rank=7,
        notes="Switchable wings. Harden facilitates. Kawhi load management."
    ),
    "MIN": TeamContext(
        team="MIN", def_rating=110.0, off_rating=113.8, def_rank=10, off_rank=16,
        pace=97.0, pace_rank=25, style=CoachingStyle.GRIND,
        pts_allowed_rank=9, reb_allowed_rank=9, ast_allowed_rank=3, three_allowed_rank=9,
        notes="Gobert rim protection. Slow pace, defensive identity. Randle scoring focus."
    ),
    
    # === AVERAGE DEFENSES (11-20) ===
    "MIL": TeamContext(
        team="MIL", def_rating=110.5, off_rating=118.0, def_rank=11, off_rank=4,
        pace=100.2, pace_rank=13, style=CoachingStyle.BALANCED,
        pts_allowed_rank=11, reb_allowed_rank=11, ast_allowed_rank=12, three_allowed_rank=11,
        notes="Giannis one-man defense. Elite offense. Drop coverage vulnerabilities."
    ),
    "DEN": TeamContext(
        team="DEN", def_rating=111.0, off_rating=117.2, def_rank=12, off_rank=6,
        pace=99.5, pace_rank=14, style=CoachingStyle.MOTION,
        pts_allowed_rank=12, reb_allowed_rank=12, ast_allowed_rank=11, three_allowed_rank=14,
        notes="Jokic-centric offense. Average perimeter D. High assist rate."
    ),
    "ORL": TeamContext(
        team="ORL", def_rating=111.2, off_rating=112.0, def_rank=13, off_rank=20,
        pace=98.2, pace_rank=19, style=CoachingStyle.GRIND,
        pts_allowed_rank=13, reb_allowed_rank=13, ast_allowed_rank=13, three_allowed_rank=13,
        notes="Young, long defense. Paolo developing. Suggs/Franz versatile."
    ),
    "PHX": TeamContext(
        team="PHX", def_rating=111.5, off_rating=116.8, def_rank=14, off_rank=7,
        pace=100.0, pace_rank=14, style=CoachingStyle.ISO_HEAVY,
        pts_allowed_rank=14, reb_allowed_rank=15, ast_allowed_rank=16, three_allowed_rank=15,
        notes="Booker/KD iso-heavy. Average defense. High scoring potential."
    ),
    "DAL": TeamContext(
        team="DAL", def_rating=113.5, off_rating=110.0, def_rank=20, off_rank=22,
        pace=98.0, pace_rank=20, style=CoachingStyle.BALANCED,
        pts_allowed_rank=20, reb_allowed_rank=14, ast_allowed_rank=18, three_allowed_rank=16,
        notes="Post-Luka rebuild. PJ Washington, Naji Marshall key. Kyrie out for season."
    ),
    "LAL": TeamContext(
        team="LAL", def_rating=110.5, off_rating=120.0, def_rank=12, off_rank=2,
        pace=100.5, pace_rank=10, style=CoachingStyle.ISO_HEAVY,
        pts_allowed_rank=12, reb_allowed_rank=10, ast_allowed_rank=8, three_allowed_rank=14,
        notes="Luka + LeBron + AD. Elite offense. High usage top 3."
    ),
    "SAC": TeamContext(
        team="SAC", def_rating=112.5, off_rating=116.0, def_rank=17, off_rank=10,
        pace=102.0, pace_rank=5, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=18, reb_allowed_rank=17, ast_allowed_rank=17, three_allowed_rank=17,
        notes="Fast pace inflates stats. Fox/Sabonis P&R. Poor perimeter D."
    ),
    "IND": TeamContext(
        team="IND", def_rating=113.0, off_rating=118.5, def_rank=18, off_rank=2,
        pace=103.5, pace_rank=1, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=17, reb_allowed_rank=18, ast_allowed_rank=18, three_allowed_rank=19,
        notes="FASTEST pace in NBA. Haliburton facilitates. Stats inflated by possessions."
    ),
    "CHI": TeamContext(
        team="CHI", def_rating=113.2, off_rating=113.0, def_rank=19, off_rank=17,
        pace=97.8, pace_rank=21, style=CoachingStyle.BALANCED,
        pts_allowed_rank=19, reb_allowed_rank=19, ast_allowed_rank=19, three_allowed_rank=20,
        notes="LaVine scoring. Vucevic facilitating big. Middling both ends."
    ),
    "TOR": TeamContext(
        team="TOR", def_rating=113.5, off_rating=112.2, def_rank=20, off_rank=19,
        pace=98.5, pace_rank=18, style=CoachingStyle.BALANCED,
        pts_allowed_rank=20, reb_allowed_rank=20, ast_allowed_rank=20, three_allowed_rank=21,
        notes="Rebuilding. Scottie Barnes developing. Inconsistent."
    ),
    
    # === POOR DEFENSES (21-30) - GOOD FOR OVERS ===
    "ATL": TeamContext(
        team="ATL", def_rating=114.0, off_rating=115.0, def_rank=21, off_rank=13,
        pace=101.5, pace_rank=7, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=21, reb_allowed_rank=21, ast_allowed_rank=21, three_allowed_rank=22,
        notes="POST-TRAE: Jalen Johnson/NAW led offense. Fast pace. Poor perimeter D."
    ),
    "BKN": TeamContext(
        team="BKN", def_rating=114.5, off_rating=111.5, def_rank=22, off_rank=22,
        pace=99.0, pace_rank=16, style=CoachingStyle.BALANCED,
        pts_allowed_rank=22, reb_allowed_rank=22, ast_allowed_rank=22, three_allowed_rank=23,
        notes="Rebuilding. Cam Thomas scoring. Poor defense - target for overs."
    ),
    "NOP": TeamContext(
        team="NOP", def_rating=114.8, off_rating=111.0, def_rank=23, off_rank=23,
        pace=100.0, pace_rank=14, style=CoachingStyle.BALANCED,
        pts_allowed_rank=23, reb_allowed_rank=23, ast_allowed_rank=23, three_allowed_rank=24,
        notes="Injury-plagued. Zion when healthy. Inconsistent defense."
    ),
    "CHA": TeamContext(
        team="CHA", def_rating=115.0, off_rating=110.5, def_rank=24, off_rank=25,
        pace=101.0, pace_rank=8, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=24, reb_allowed_rank=24, ast_allowed_rank=24, three_allowed_rank=25,
        notes="Young team. LaMelo when healthy. Poor defense - target for overs."
    ),
    "SAS": TeamContext(
        team="SAS", def_rating=115.5, off_rating=111.2, def_rank=25, off_rank=21,
        pace=100.5, pace_rank=11, style=CoachingStyle.BALANCED,
        pts_allowed_rank=25, reb_allowed_rank=25, ast_allowed_rank=25, three_allowed_rank=26,
        notes="Wemby + Trae Young combo. High-volume offense. Poor defense."
    ),
    "POR": TeamContext(
        team="POR", def_rating=116.0, off_rating=110.0, def_rank=26, off_rank=26,
        pace=101.8, pace_rank=6, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=26, reb_allowed_rank=26, ast_allowed_rank=26, three_allowed_rank=27,
        notes="Rebuilding. Fast pace. Poor defense - GREAT for overs."
    ),
    "DET": TeamContext(
        team="DET", def_rating=116.5, off_rating=109.5, def_rank=27, off_rank=27,
        pace=100.8, pace_rank=9, style=CoachingStyle.BALANCED,
        pts_allowed_rank=27, reb_allowed_rank=27, ast_allowed_rank=27, three_allowed_rank=28,
        notes="Cade developing. Young roster. Poor defense - target for overs."
    ),
    "UTA": TeamContext(
        team="UTA", def_rating=117.0, off_rating=109.0, def_rank=28, off_rank=28,
        pace=99.8, pace_rank=15, style=CoachingStyle.BALANCED,
        pts_allowed_rank=28, reb_allowed_rank=28, ast_allowed_rank=28, three_allowed_rank=29,
        notes="Tanking. Keyonte George developing. Poor both ends."
    ),
    "GSW": TeamContext(
        team="GSW", def_rating=113.8, off_rating=114.0, def_rank=21, off_rank=15,
        pace=99.5, pace_rank=14, style=CoachingStyle.MOTION,
        pts_allowed_rank=21, reb_allowed_rank=20, ast_allowed_rank=15, three_allowed_rank=10,
        notes="Curry 3s. Motion offense. Aging roster. Inconsistent defense."
    ),
    "WAS": TeamContext(
        team="WAS", def_rating=118.0, off_rating=108.0, def_rank=30, off_rank=30,
        pace=101.2, pace_rank=8, style=CoachingStyle.UPTEMPO,
        pts_allowed_rank=30, reb_allowed_rank=30, ast_allowed_rank=30, three_allowed_rank=30,
        notes="WORST defense in NBA. Fast pace. PRIME target for overs."
    ),
}


def get_team_context(team: str) -> Optional[TeamContext]:
    """Get full context for a team."""
    return NBA_TEAM_CONTEXT.get(team.upper())


def get_pace_adjustment(team: str, opponent: str) -> float:
    """
    Calculate pace adjustment factor for a matchup.
    
    Returns multiplier to apply to counting stat projections:
    - >1.0 = expect higher stats (fast pace matchup)
    - <1.0 = expect lower stats (slow pace matchup)
    - 1.0 = league average
    """
    team_ctx = get_team_context(team)
    opp_ctx = get_team_context(opponent)
    
    if not team_ctx or not opp_ctx:
        return 1.0
    
    # League average pace ~99.5
    LEAGUE_AVG_PACE = 99.5
    
    # Matchup pace = average of both teams
    matchup_pace = (team_ctx.pace + opp_ctx.pace) / 2
    
    # Adjustment factor (capped at ±8%)
    adjustment = matchup_pace / LEAGUE_AVG_PACE
    return max(0.92, min(1.08, adjustment))


def get_defensive_matchup_factor(opponent: str, stat: str) -> float:
    """
    Get defensive matchup factor for a specific stat.
    
    Returns multiplier:
    - >1.0 = opponent weak at defending this stat (boost projection)
    - <1.0 = opponent strong at defending this stat (reduce projection)
    - 1.0 = average
    """
    opp_ctx = get_team_context(opponent)
    if not opp_ctx:
        return 1.0
    
    stat_lower = stat.lower()
    
    # Map stat to defensive rank
    if stat_lower in ("points", "pts"):
        rank = opp_ctx.pts_allowed_rank
    elif stat_lower in ("rebounds", "reb"):
        rank = opp_ctx.reb_allowed_rank
    elif stat_lower in ("assists", "ast"):
        rank = opp_ctx.ast_allowed_rank
    elif stat_lower in ("3pm", "threes", "3-pointers"):
        rank = opp_ctx.three_allowed_rank
    else:
        # For combos, use points rank as proxy
        rank = opp_ctx.pts_allowed_rank
    
    # Convert rank to factor (rank 1 = 0.92, rank 30 = 1.08)
    # Linear scale: factor = 0.92 + (rank - 1) * (0.16 / 29)
    factor = 0.92 + (rank - 1) * (0.16 / 29)
    return round(factor, 3)


def get_matchup_summary(team: str, opponent: str) -> str:
    """Generate a brief matchup summary for analysis reports."""
    team_ctx = get_team_context(team)
    opp_ctx = get_team_context(opponent)
    
    if not team_ctx or not opp_ctx:
        return "Matchup context unavailable."
    
    lines = []
    
    # Pace context
    pace_adj = get_pace_adjustment(team, opponent)
    if pace_adj > 1.03:
        lines.append(f"⚡ FAST PACE matchup ({team_ctx.pace:.1f} + {opp_ctx.pace:.1f} = high possessions)")
        lines.append("   → Counting stats likely INFLATED")
    elif pace_adj < 0.97:
        lines.append(f"🐢 SLOW PACE matchup ({team_ctx.pace:.1f} + {opp_ctx.pace:.1f} = limited possessions)")
        lines.append("   → Counting stats likely SUPPRESSED")
    
    # Defensive context
    if opp_ctx.def_rank <= 5:
        lines.append(f"🛡️ vs ELITE DEFENSE ({opponent} #{opp_ctx.def_rank})")
        lines.append("   → Overs risky, consider unders")
    elif opp_ctx.def_rank >= 25:
        lines.append(f"🎯 vs WEAK DEFENSE ({opponent} #{opp_ctx.def_rank})")
        lines.append("   → Overs favorable, stats should inflate")
    
    # Coaching style
    if opp_ctx.style == CoachingStyle.GRIND:
        lines.append(f"⏳ {opponent} plays GRIND style - expect low-scoring, half-court game")
    elif opp_ctx.style == CoachingStyle.UPTEMPO:
        lines.append(f"🏃 {opponent} plays UPTEMPO - expect run-and-gun, high possessions")
    
    # Team notes
    if team_ctx.notes:
        lines.append(f"📝 {team}: {team_ctx.notes}")
    if opp_ctx.notes:
        lines.append(f"📝 {opponent}: {opp_ctx.notes}")
    
    return "\n".join(lines) if lines else "Standard matchup, no significant adjustments."


def apply_context_to_projection(
    mu: float,
    team: str,
    opponent: str,
    stat: str,
) -> tuple[float, str]:
    """
    Apply pace and defensive context to a projection.
    
    Returns: (adjusted_mu, explanation)
    """
    pace_adj = get_pace_adjustment(team, opponent)
    def_adj = get_defensive_matchup_factor(opponent, stat)
    
    # Combined adjustment (multiplicative)
    total_adj = pace_adj * def_adj
    adjusted_mu = mu * total_adj
    
    # Build explanation
    parts = []
    if abs(pace_adj - 1.0) > 0.02:
        direction = "+" if pace_adj > 1.0 else ""
        parts.append(f"pace {direction}{(pace_adj-1)*100:.1f}%")
    if abs(def_adj - 1.0) > 0.02:
        direction = "+" if def_adj > 1.0 else ""
        parts.append(f"matchup {direction}{(def_adj-1)*100:.1f}%")
    
    if parts:
        explanation = f"Context adjustment: {', '.join(parts)} → {mu:.1f} → {adjusted_mu:.1f}"
    else:
        explanation = "No significant context adjustment"
    
    return adjusted_mu, explanation


# Quick lookup helpers
def is_elite_defense(team: str) -> bool:
    """Check if team is top-5 defense."""
    ctx = get_team_context(team)
    return ctx is not None and ctx.def_rank <= 5


def is_weak_defense(team: str) -> bool:
    """Check if team is bottom-5 defense."""
    ctx = get_team_context(team)
    return ctx is not None and ctx.def_rank >= 26


def is_fast_pace(team: str) -> bool:
    """Check if team is top-5 pace."""
    ctx = get_team_context(team)
    return ctx is not None and ctx.pace_rank <= 5


def is_slow_pace(team: str) -> bool:
    """Check if team is bottom-5 pace."""
    ctx = get_team_context(team)
    return ctx is not None and ctx.pace_rank >= 26


if __name__ == "__main__":
    # Demo
    print("=" * 60)
    print("NBA TEAM CONTEXT - 2025-26 SEASON")
    print("=" * 60)
    
    print("\n🛡️ TOP 5 DEFENSES:")
    for team in ["CLE", "BOS", "OKC", "NYK", "MEM"]:
        ctx = get_team_context(team)
        print(f"  {team}: DefRtg {ctx.def_rating} (#{ctx.def_rank}), Pace {ctx.pace}")
    
    print("\n🎯 BOTTOM 5 DEFENSES (target for overs):")
    for team in ["POR", "DET", "UTA", "GSW", "WAS"]:
        ctx = get_team_context(team)
        if ctx:
            print(f"  {team}: DefRtg {ctx.def_rating} (#{ctx.def_rank}), Pace {ctx.pace}")
    
    print("\n⚡ FASTEST PACE (stats inflate):")
    for team in ["IND", "SAC", "POR", "CHA", "ATL"]:
        ctx = get_team_context(team)
        if ctx:
            print(f"  {team}: Pace {ctx.pace} (#{ctx.pace_rank})")
    
    print("\n" + "=" * 60)
    print("MATCHUP EXAMPLE: MIN @ HOU")
    print("=" * 60)
    print(get_matchup_summary("MIN", "HOU"))
    
    print("\n" + "=" * 60)
    print("CONTEXT ADJUSTMENT EXAMPLE:")
    print("=" * 60)
    adj_mu, explanation = apply_context_to_projection(20.0, "MIN", "WAS", "points")
    print(f"  Julius Randle points vs WAS:")
    print(f"  {explanation}")
