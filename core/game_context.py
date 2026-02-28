"""
core/game_context.py — Shared Game-Level Market Context Engine
================================================================

Provides GameContext for all sports: spread, total, moneyline → player prop
adjustments.  Binary market signals (DK Predictions, ML/Spread/Total) inform:

1. BLOWOUT RISK    — Large spread → star sits Q4/garbage time → OVERs risky
2. PACE SIGNAL     — High total → fast game → counting stats inflate
3. GAME SCRIPT     — Trailing team → stars play more, shoot more → UNDERs -EV
4. IMPLIED TEAM TOTAL — Spread + Total → per-team scoring environment

Usage
-----
    from core.game_context import GameContext, analyze_game_impact

    ctx = GameContext(
        spread=-8.5,          # Home spread (neg = home fav)
        total=225.5,          # Over/under
        player_team="BOS",
        opponent="PHI",
        is_home=True,
    )
    impact = analyze_game_impact(ctx, stat="PTS", direction="HIGHER")
    # impact.lambda_mult, impact.confidence_adj, impact.flags, impact.report_line

Cross-Sport Support
-------------------
- NBA: spread + total + pace
- CBB: spread + total (already has game_script_gate — this COMPLEMENTS)
- NHL: spread + total → SOG/Saves adjustments
- Soccer: goal line + total goals → shots/assists
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# =============================================================================
# DATA MODEL
# =============================================================================

@dataclass
class GameContext:
    """Game-level market context for a single matchup."""

    spread: Optional[float] = None        # Home team spread (neg = home fav)
    total: Optional[float] = None         # Over/under line
    moneyline_home: Optional[int] = None  # American ML (e.g., -180)
    moneyline_away: Optional[int] = None  # American ML (e.g., +155)
    player_team: str = ""                 # Team abbreviation for the player
    opponent: str = ""                    # Opponent abbreviation
    is_home: bool = True                  # Is the player's team at home?
    sport: str = "NBA"                    # NBA, CBB, NHL, Soccer

    @property
    def team_spread(self) -> float:
        """Spread from the player's team perspective (positive = underdog)."""
        if self.spread is None:
            return 0.0
        if self.is_home:
            return self.spread  # Home spread as-is
        return -self.spread     # Flip for away team

    @property
    def abs_spread(self) -> float:
        return abs(self.team_spread)

    @property
    def is_favorite(self) -> bool:
        return self.team_spread < 0

    @property
    def is_underdog(self) -> bool:
        return self.team_spread > 0

    @property
    def implied_team_total(self) -> Optional[float]:
        """Implied team total = (total + spread) / 2 for away, (total - spread) / 2 for home."""
        if self.total is None or self.spread is None:
            return None
        # Home implied = (Total - Spread) / 2
        home_implied = (self.total - self.spread) / 2
        away_implied = (self.total + self.spread) / 2
        return home_implied if self.is_home else away_implied

    @property
    def opponent_implied_total(self) -> Optional[float]:
        """Implied total for the opponent."""
        if self.total is None or self.spread is None:
            return None
        home_implied = (self.total - self.spread) / 2
        away_implied = (self.total + self.spread) / 2
        return away_implied if self.is_home else home_implied

    @property
    def blowout_tier(self) -> str:
        """Classify blowout risk from spread magnitude."""
        s = self.abs_spread
        if s >= 15:
            return "EXTREME"
        elif s >= 10:
            return "HIGH"
        elif s >= 7:
            return "MODERATE"
        elif s >= 4:
            return "LOW"
        return "NONE"

    @property
    def pace_tier(self) -> str:
        """Classify pace environment from total."""
        if self.total is None:
            return "UNKNOWN"
        sport = self.sport.upper()
        if sport == "NBA":
            if self.total >= 235:
                return "FAST"
            elif self.total >= 220:
                return "ABOVE_AVG"
            elif self.total >= 210:
                return "AVERAGE"
            elif self.total >= 200:
                return "SLOW"
            return "CRAWL"
        elif sport == "CBB":
            if self.total >= 155:
                return "FAST"
            elif self.total >= 145:
                return "ABOVE_AVG"
            elif self.total >= 135:
                return "AVERAGE"
            elif self.total >= 125:
                return "SLOW"
            return "CRAWL"
        elif sport == "NHL":
            if self.total >= 6.5:
                return "HIGH_SCORING"
            elif self.total >= 5.5:
                return "AVERAGE"
            return "LOW_SCORING"
        return "UNKNOWN"


# =============================================================================
# IMPACT ANALYSIS
# =============================================================================

@dataclass
class GameImpact:
    """Result of analyzing game context impact on a player prop."""

    lambda_mult: float = 1.0          # Multiplier on player's projected mean
    confidence_adj: float = 0.0       # Additive adjustment to confidence (%)
    flags: List[str] = field(default_factory=list)
    report_line: str = ""             # Single-line summary for report
    blowout_tier: str = "NONE"
    pace_tier: str = "UNKNOWN"
    implied_team_total: Optional[float] = None
    should_block: bool = False        # Hard block this prop?
    block_reason: str = ""


# --- Sport-specific thresholds ---

_NBA_THRESHOLDS = {
    # Blowout: spread → lambda multiplier for favorite stars (OVER)
    "blowout_fav_over": {10: 0.94, 12: 0.90, 15: 0.85},
    # Blowout: spread → lambda multiplier for underdog stars (UNDER)
    "blowout_dog_under_block": 8,       # Block under at this spread
    # Pace: total → lambda multiplier
    "pace_fast_over_boost": {230: 1.04, 235: 1.06, 240: 1.08},
    "pace_slow_under_boost": {205: 1.03, 200: 1.05, 195: 1.07},
    # Confidence caps in blowout
    "blowout_confidence_cap": {10: 0.68, 12: 0.63, 15: 0.58},
}

_CBB_THRESHOLDS = {
    "blowout_fav_over": {12: 0.92, 15: 0.88, 20: 0.82},
    "blowout_dog_under_block": 6,
    "pace_fast_over_boost": {155: 1.04, 160: 1.06, 170: 1.08},
    "pace_slow_under_boost": {130: 1.03, 125: 1.05, 120: 1.07},
    "blowout_confidence_cap": {12: 0.65, 15: 0.60, 20: 0.55},
}

_NHL_THRESHOLDS = {
    "blowout_fav_over": {2.0: 0.96, 2.5: 0.93},       # Puck line scale
    "blowout_dog_under_block": 3.0,
    "pace_fast_sog_boost": {6.5: 1.04, 7.0: 1.06},
    "pace_slow_saves_boost": {5.0: 1.04, 4.5: 1.06},
    "blowout_confidence_cap": {2.0: 0.64, 2.5: 0.60},
}


def _get_thresholds(sport: str) -> dict:
    sport = sport.upper()
    if sport == "CBB":
        return _CBB_THRESHOLDS
    elif sport == "NHL":
        return _NHL_THRESHOLDS
    return _NBA_THRESHOLDS


# Stat categories that are most affected by game script
_COUNTING_STATS = {
    "pts", "points", "reb", "rebounds", "ast", "assists",
    "pra", "pts+reb+ast", "pr", "pts+reb", "pa", "pts+ast",
    "ra", "reb+ast", "3pm", "three_pointers", "blk", "stl",
    "stocks", "stl+blk", "fantasy_score",
}

# Stats less affected by blowout (survive garbage time)
_BLOWOUT_RESILIENT = {"reb", "rebounds", "blk", "blocks"}

# NHL-specific
_NHL_COUNTING = {"sog", "shots_on_goal", "saves", "goalie_saves", "points", "assists"}


def analyze_game_impact(
    ctx: GameContext,
    stat: str,
    direction: str,
    player_role: str = "STARTER",
) -> GameImpact:
    """
    Analyze how game-level market signals affect a player prop.

    Parameters
    ----------
    ctx : GameContext
        Game-level market data.
    stat : str
        Player stat type (PTS, REB, SOG, etc.).
    direction : str
        "HIGHER"/"OVER" or "LOWER"/"UNDER".
    player_role : str
        "STAR", "STARTER", "BENCH", "ROLE_PLAYER".

    Returns
    -------
    GameImpact with multipliers, flags, and report annotation.
    """
    impact = GameImpact(
        blowout_tier=ctx.blowout_tier,
        pace_tier=ctx.pace_tier,
        implied_team_total=ctx.implied_team_total,
    )

    stat_lower = stat.lower()
    is_over = direction.upper() in ("HIGHER", "OVER")
    is_under = not is_over
    sport = ctx.sport.upper()
    thresholds = _get_thresholds(sport)
    flags = []

    # No spread/total → no adjustment, just flag
    if ctx.spread is None and ctx.total is None:
        impact.report_line = "[GAME] No market data available"
        return impact

    # =================================================================
    # 1. BLOWOUT RISK ADJUSTMENT (from spread)
    # =================================================================
    if ctx.spread is not None:
        abs_sp = ctx.abs_spread

        # --- Favorite star OVER in blowout: Stars sit early ---
        if ctx.is_favorite and is_over and abs_sp >= 7:
            if stat_lower in _COUNTING_STATS or (sport == "NHL" and stat_lower in _NHL_COUNTING):
                # Graduated multiplier
                fav_over = thresholds.get("blowout_fav_over", {})
                mult = 1.0
                for threshold_spread, factor in sorted(fav_over.items()):
                    if abs_sp >= threshold_spread:
                        mult = factor
                impact.lambda_mult *= mult

                # Blowout-resilient stats get relief
                if stat_lower in _BLOWOUT_RESILIENT:
                    impact.lambda_mult = min(1.0, impact.lambda_mult + 0.03)

                if mult < 1.0:
                    flags.append(f"BLOWOUT_RISK: Fav by {abs_sp:.1f}, star may rest (x{mult:.2f})")

                # Confidence cap for big spreads
                caps = thresholds.get("blowout_confidence_cap", {})
                for threshold_spread, cap in sorted(caps.items()):
                    if abs_sp >= threshold_spread:
                        impact.confidence_adj = min(impact.confidence_adj, -(100 - cap * 100))

        # --- Underdog star UNDER: Game script inflation ---
        if ctx.is_underdog and is_under:
            block_threshold = thresholds.get("blowout_dog_under_block", 8)
            if abs_sp >= block_threshold and stat_lower in _COUNTING_STATS:
                if player_role in ("STAR", "STARTER"):
                    impact.should_block = True
                    impact.block_reason = (
                        f"GAME_SCRIPT: Team is +{abs_sp:.1f} dog — "
                        f"star stats will inflate. UNDER structurally -EV."
                    )
                    flags.append(f"GAME_SCRIPT_BLOCK: +{abs_sp:.1f} underdog, UNDER blocked")
                else:
                    # Role players: just penalize
                    impact.lambda_mult *= 1.10
                    flags.append(f"GAME_SCRIPT_WARN: +{abs_sp:.1f} underdog, UNDER risky")

        # --- Underdog star OVER: Trailing = more volume ---
        if ctx.is_underdog and is_over and abs_sp >= 4:
            if stat_lower in _COUNTING_STATS:
                # Trailing teams shoot more → slight boost to star OVERs
                boost = min(1.08, 1.0 + (abs_sp - 4) * 0.01)
                impact.lambda_mult *= boost
                flags.append(f"TRAILING_BOOST: +{abs_sp:.1f} dog, more volume (x{boost:.2f})")

        # --- Close game: Both sides play full minutes ---
        if abs_sp <= 3:
            flags.append(f"COMPETITIVE: Spread {abs_sp:.1f}, full minutes expected")

    # =================================================================
    # 2. PACE / TOTAL ADJUSTMENT
    # =================================================================
    if ctx.total is not None:
        itt = ctx.implied_team_total

        if sport in ("NBA", "CBB"):
            if is_over and stat_lower in _COUNTING_STATS:
                pace_boosts = thresholds.get("pace_fast_over_boost", {})
                for threshold_total, factor in sorted(pace_boosts.items()):
                    if ctx.total >= threshold_total:
                        impact.lambda_mult *= factor
                        flags.append(f"PACE_UP: Total {ctx.total}, fast game (x{factor:.2f})")
                        break  # Take highest qualifying

            if is_under and stat_lower in _COUNTING_STATS:
                pace_unders = thresholds.get("pace_slow_under_boost", {})
                for threshold_total, factor in sorted(pace_unders.items(), reverse=True):
                    if ctx.total <= threshold_total:
                        impact.lambda_mult *= factor
                        flags.append(f"PACE_DOWN: Total {ctx.total}, slow game (x{factor:.2f})")
                        break

        elif sport == "NHL":
            if stat_lower in ("sog", "shots_on_goal") and is_over:
                sog_boosts = thresholds.get("pace_fast_sog_boost", {})
                for threshold_total, factor in sorted(sog_boosts.items()):
                    if ctx.total >= threshold_total:
                        impact.lambda_mult *= factor
                        flags.append(f"HIGH_TOTAL: {ctx.total} → more SOG (x{factor:.2f})")
                        break

            if stat_lower in ("saves", "goalie_saves") and is_over:
                saves_boosts = thresholds.get("pace_slow_saves_boost", {})
                for threshold_total, factor in sorted(saves_boosts.items(), reverse=True):
                    if ctx.total <= threshold_total:
                        impact.lambda_mult *= factor
                        flags.append(f"LOW_TOTAL: {ctx.total} → fewer saves needed (x{factor:.2f})")
                        break

        # Implied team total annotation
        if itt is not None:
            flags.append(f"IMPLIED_TEAM_TOTAL: {itt:.1f}")

    # =================================================================
    # 3. BUILD REPORT LINE
    # =================================================================
    impact.flags = flags

    # Compact single-line for report output
    parts = []
    if ctx.spread is not None:
        side = "FAV" if ctx.is_favorite else "DOG"
        parts.append(f"Spread: {side} {ctx.abs_spread:.1f}")
    if ctx.total is not None:
        parts.append(f"O/U: {ctx.total:.1f}")
    if ctx.implied_team_total is not None:
        parts.append(f"ITT: {ctx.implied_team_total:.1f}")
    if impact.blowout_tier not in ("NONE", ""):
        parts.append(f"Blowout: {impact.blowout_tier}")
    if impact.lambda_mult != 1.0:
        parts.append(f"Adj: x{impact.lambda_mult:.2f}")
    if impact.should_block:
        parts.append("** BLOCKED **")

    impact.report_line = "[GAME] " + " | ".join(parts) if parts else ""

    return impact


# =============================================================================
# REPORT SECTION GENERATOR
# =============================================================================

def format_game_context_section(
    ctx: GameContext,
    edges: Optional[list] = None,
) -> List[str]:
    """
    Generate a report section summarizing game context for a matchup.

    Returns list of lines for the report.
    """
    lines = []
    if ctx.spread is None and ctx.total is None:
        return lines

    lines.append("  [GAME CONTEXT]")

    # Matchup header
    matchup = f"  {ctx.player_team} vs {ctx.opponent}" if ctx.player_team else ""
    if matchup:
        lines.append(matchup)

    # Spread
    if ctx.spread is not None:
        home_side = ctx.player_team if ctx.is_home else ctx.opponent
        away_side = ctx.opponent if ctx.is_home else ctx.player_team
        if ctx.spread < 0:
            lines.append(f"    Spread: {home_side} {ctx.spread} (FAV)")
        elif ctx.spread > 0:
            lines.append(f"    Spread: {home_side} +{ctx.spread} (DOG)")
        else:
            lines.append(f"    Spread: PICK'EM")

    # Total
    if ctx.total is not None:
        lines.append(f"    Total: {ctx.total} ({ctx.pace_tier})")

    # Implied team totals
    itt = ctx.implied_team_total
    oitt = ctx.opponent_implied_total
    if itt is not None and oitt is not None:
        lines.append(f"    Implied: {ctx.player_team} {itt:.1f} — {ctx.opponent} {oitt:.1f}")

    # Blowout warning
    bt = ctx.blowout_tier
    if bt in ("HIGH", "EXTREME"):
        lines.append(f"    *** BLOWOUT RISK: {bt} — star minutes at risk ***")
    elif bt == "MODERATE":
        lines.append(f"    * Blowout risk: MODERATE — monitor minutes *")

    # Edge-level impact summary
    if edges:
        blocked = [e for e in edges if e.get("game_impact", {}).get("should_block")]
        adjusted = [e for e in edges if e.get("game_impact", {}).get("lambda_mult", 1.0) != 1.0]
        if blocked:
            lines.append(f"    BLOCKED by game script: {len(blocked)} props")
        if adjusted:
            lines.append(f"    Game-adjusted: {len(adjusted)} props")

    lines.append("")
    return lines


# =============================================================================
# CONVENIENCE: BUILD FROM ESPN / API DATA
# =============================================================================

def build_game_context(
    player_team: str,
    opponent: str,
    spread: Optional[float] = None,
    total: Optional[float] = None,
    is_home: bool = True,
    sport: str = "NBA",
    moneyline_home: Optional[int] = None,
    moneyline_away: Optional[int] = None,
) -> GameContext:
    """Factory function for building GameContext from various sources."""
    return GameContext(
        spread=spread,
        total=total,
        moneyline_home=moneyline_home,
        moneyline_away=moneyline_away,
        player_team=player_team,
        opponent=opponent,
        is_home=is_home,
        sport=sport,
    )
