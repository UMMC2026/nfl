"""
Context Flags Module

Provides contextual factors that affect player performance:
- Minutes projections
- Rest/fatigue indicators (B2B, days rest)
- Usage context (teammate injuries)
- Opponent defensive rankings
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import date, timedelta
import json
from pathlib import Path


class RestStatus(Enum):
    """Rest/fatigue indicator."""
    B2B = "B2B"           # Back-to-back game
    ONE_DAY = "1d"        # 1 day rest
    TWO_PLUS = "2d+"      # 2+ days rest
    UNKNOWN = "?"


class UsageContext(Enum):
    """Usage change due to teammate injuries/rest."""
    INCREASED = "+"       # Key teammate out → more usage
    NORMAL = "0"          # Normal rotation
    DECREASED = "-"       # Back from injury, minutes limit, etc.
    UNKNOWN = "?"


class MinutesTier(Enum):
    """Expected minutes tier."""
    ELITE = "34+"         # Star minutes
    STARTER = "28-33"     # Regular starter
    ROTATION = "20-27"    # Rotation player
    LIMITED = "15-19"     # Limited role
    SPOT = "<15"          # Spot minutes
    UNKNOWN = "?"
    
    @property
    def risk_marker(self) -> str:
        """Get risk marker for this minutes tier."""
        markers = {
            "34+": "🔒",      # Elite - locked in
            "28-33": "✅",    # Stable starter
            "20-27": "⚠️",    # Floor risk
            "15-19": "❌",    # High variance
            "<15": "💀",      # Avoid
            "?": ""
        }
        return markers.get(self.value, "")
    
    @property
    def risk_label(self) -> str:
        """Get risk label for display."""
        labels = {
            "34+": "elite",
            "28-33": "stable",
            "20-27": "floor risk",
            "15-19": "high variance",
            "<15": "avoid",
            "?": ""
        }
        return labels.get(self.value, "")


class MatchupRank(Enum):
    """Opponent defensive rank for relevant stat."""
    ELITE_D = "Top 5"     # Very tough matchup
    GOOD_D = "6-12"       # Above average defense
    AVERAGE_D = "13-18"   # Average defense
    WEAK_D = "19-25"      # Below average defense
    POOR_D = "26-30"      # Exploitable defense
    UNKNOWN = "?"


@dataclass
class InjuryImpact:
    """Impact of teammate injury on a player's usage."""
    injured_player: str
    injury_status: str  # OUT, DOUBTFUL, QUESTIONABLE, PROBABLE
    impact_on_usage: str  # Description of impact
    usage_change: float  # Estimated % change in usage rate


@dataclass
class ContextFlags:
    """Full context flags for a player/game."""
    player: str
    team: str
    opponent: str
    game_date: date
    
    # Core flags
    rest_status: RestStatus = RestStatus.UNKNOWN
    minutes_tier: MinutesTier = MinutesTier.UNKNOWN
    usage_context: UsageContext = UsageContext.UNKNOWN
    matchup_rank: MatchupRank = MatchupRank.UNKNOWN
    
    # Detailed context
    projected_minutes: Optional[float] = None
    days_rest: int = -1
    is_home: bool = True
    
    # Injury impacts
    injury_impacts: list[InjuryImpact] = field(default_factory=list)
    
    # Opponent specifics
    opp_def_rating: Optional[float] = None  # Defensive rating
    opp_pace: Optional[float] = None        # Pace factor
    # NFL-specific pressure/run-stuff (optional)
    opp_pass_rush_rank: Optional[int] = None
    opp_pass_rush_rate: Optional[float] = None
    opp_run_stop_rank: Optional[int] = None
    
    # Notes
    notes: list[str] = field(default_factory=list)


class ContextProvider:
    """
    Provides contextual flags for players and games.
    
    In production, this would pull from APIs. For now, we use cached/manual data.
    """
    
    def __init__(self, data_dir: str = "data_center"):
        self.data_dir = Path(data_dir)
        self._schedule_cache: dict = {}
        self._injury_cache: dict = {}
        self._defense_rankings: dict = {}
        self._load_static_data()
    
    def _load_static_data(self):
        """Load static reference data."""
        # Team defensive rankings (2024-25 season estimates)
        # These would normally come from an API
        self._defense_rankings = {
            # Points allowed rank (1 = best defense)
            "OKC": {"pts": 3, "reb": 8, "ast": 5, "def_rtg": 108.2},
            "CLE": {"pts": 1, "reb": 12, "ast": 3, "def_rtg": 106.1},
            "BOS": {"pts": 5, "reb": 6, "ast": 7, "def_rtg": 109.5},
            "MEM": {"pts": 8, "reb": 4, "ast": 12, "def_rtg": 110.3},
            "HOU": {"pts": 4, "reb": 2, "ast": 8, "def_rtg": 108.8},
            "NYK": {"pts": 12, "reb": 15, "ast": 10, "def_rtg": 111.2},
            "LAL": {"pts": 18, "reb": 20, "ast": 15, "def_rtg": 113.5},
            "DEN": {"pts": 15, "reb": 18, "ast": 14, "def_rtg": 112.8},
            "MIA": {"pts": 7, "reb": 10, "ast": 6, "def_rtg": 110.0},
            "PHX": {"pts": 22, "reb": 25, "ast": 20, "def_rtg": 115.2},
            "SAC": {"pts": 25, "reb": 22, "ast": 24, "def_rtg": 116.0},
            "POR": {"pts": 28, "reb": 26, "ast": 28, "def_rtg": 117.5},
            "TOR": {"pts": 20, "reb": 19, "ast": 18, "def_rtg": 114.0},
            "SAS": {"pts": 24, "reb": 23, "ast": 22, "def_rtg": 115.8},
            "UTA": {"pts": 27, "reb": 24, "ast": 26, "def_rtg": 117.0},
            "WAS": {"pts": 30, "reb": 29, "ast": 30, "def_rtg": 120.0},
        }
        
        # Pace rankings (possessions per game)
        self._pace_rankings = {
            "IND": 103.5, "SAC": 102.8, "ATL": 102.2, "POR": 101.5,
            "DEN": 101.0, "BOS": 100.5, "MIL": 100.2, "PHX": 100.0,
            "OKC": 99.5, "NYK": 98.0, "MIA": 97.5, "CLE": 97.0,
            "HOU": 96.5, "TOR": 98.5, "SAS": 99.0, "UTA": 97.8,
        }

        # NFL pass-rush / pressure metrics (sample conservative estimates)
        # Key: team abbreviation -> pressure rate (% of dropbacks) and pass-rush rank (1 best)
        self._nfl_pass_pressure = {
            "GB": {"pressure_rate": 0.185, "pr_rank": 6, "run_stop_rank": 8},
            "CHI": {"pressure_rate": 0.172, "pr_rank": 10, "run_stop_rank": 12},
            "KC": {"pressure_rate": 0.198, "pr_rank": 2, "run_stop_rank": 4},
            "BUF": {"pressure_rate": 0.190, "pr_rank": 4, "run_stop_rank": 6},
            "NE": {"pressure_rate": 0.162, "pr_rank": 18, "run_stop_rank": 20},
            # Add more as needed
        }
    
    def get_context(
        self,
        player: str,
        team: str,
        opponent: str,
        stat: str,
        game_date: Optional[date] = None,
    ) -> ContextFlags:
        """
        Get full context flags for a player/game.
        """
        game_date = game_date or date.today()
        
        ctx = ContextFlags(
            player=player,
            team=team,
            opponent=opponent,
            game_date=game_date,
        )
        
        # Set rest status (would come from schedule API)
        ctx.rest_status = self._estimate_rest_status(team, game_date)
        
        # Set minutes tier (would come from projections)
        ctx.minutes_tier = self._estimate_minutes_tier(player, team)
        
        # Set matchup rank
        ctx.matchup_rank = self._get_matchup_rank(opponent, stat)
        
        # Set opponent defensive rating
        if opponent in self._defense_rankings:
            ctx.opp_def_rating = self._defense_rankings[opponent].get("def_rtg")
        
        # Set pace
        if opponent in self._pace_rankings:
            ctx.opp_pace = self._pace_rankings.get(opponent)

        # NFL pass-rush / pressure fields (if available)
        if opponent in self._nfl_pass_pressure:
            pr = self._nfl_pass_pressure[opponent]
            ctx.opp_pass_rush_rate = pr.get("pressure_rate")
            ctx.opp_pass_rush_rank = pr.get("pr_rank")
            ctx.opp_run_stop_rank = pr.get("run_stop_rank")
        
        # Check for injury impacts
        ctx.injury_impacts = self._check_injury_impacts(player, team)
        ctx.usage_context = self._determine_usage_context(ctx.injury_impacts)
        
        # Add relevant notes
        ctx.notes = self._generate_notes(ctx, stat)
        
        return ctx
    
    def _estimate_rest_status(self, team: str, game_date: date) -> RestStatus:
        """Estimate rest status based on schedule."""
        # In production, check actual schedule
        # For now, assume normal rest
        return RestStatus.TWO_PLUS
    
    def _estimate_minutes_tier(self, player: str, team: str) -> MinutesTier:
        """Estimate minutes tier based on role."""
        # Star players
        stars = {
            "Victor Wembanyama": MinutesTier.ELITE,
            "Shai Gilgeous-Alexander": MinutesTier.ELITE,
            "Jalen Brunson": MinutesTier.ELITE,
            "OG Anunoby": MinutesTier.STARTER,
            "Karl-Anthony Towns": MinutesTier.ELITE,
            "Scottie Barnes": MinutesTier.ELITE,
            "Jalen Williams": MinutesTier.STARTER,
            "Jamal Murray": MinutesTier.STARTER,
            "Brandon Ingram": MinutesTier.STARTER,
            "Deni Avdija": MinutesTier.STARTER,
            "Chet Holmgren": MinutesTier.STARTER,
        }
        
        if player in stars:
            return stars[player]
        
        # Rotation players
        rotation = ["Jordan Clarkson", "Mikal Bridges", "Harrison Barnes", 
                    "RJ Barrett", "Immanuel Quickley", "Stephon Castle"]
        if player in rotation:
            return MinutesTier.ROTATION
        
        # Limited/bench
        limited = ["Luke Kornet", "Bruce Brown", "Alex Caruso", "Cason Wallace"]
        if player in limited:
            return MinutesTier.LIMITED
        
        return MinutesTier.UNKNOWN
    
    def _get_matchup_rank(self, opponent: str, stat: str) -> MatchupRank:
        """Get opponent's defensive rank for the relevant stat."""
        if opponent not in self._defense_rankings:
            return MatchupRank.UNKNOWN
        
        # Map stat to defensive category
        stat_map = {
            "points": "pts",
            "rebounds": "reb",
            "assists": "ast",
            "pts+reb+ast": "pts",  # Use points as proxy for PRA
            "3pm": "pts",
        }
        
        stat_key = stat_map.get(stat, "pts")
        rank = self._defense_rankings[opponent].get(stat_key, 15)
        
        if rank <= 5:
            return MatchupRank.ELITE_D
        elif rank <= 12:
            return MatchupRank.GOOD_D
        elif rank <= 18:
            return MatchupRank.AVERAGE_D
        elif rank <= 25:
            return MatchupRank.WEAK_D
        else:
            return MatchupRank.POOR_D
    
    def _check_injury_impacts(self, player: str, team: str) -> list[InjuryImpact]:
        """Check for teammate injuries that affect this player's usage."""
        # In production, pull from injury API
        # Example static data for demonstration
        impacts = []
        
        # NYK example: If Randle is out, Anunoby usage goes up
        if team == "NYK" and player == "OG Anunoby":
            # Check if Randle is listed as out (would come from API)
            pass
        
        return impacts
    
    def _determine_usage_context(self, impacts: list[InjuryImpact]) -> UsageContext:
        """Determine overall usage context from injury impacts."""
        if not impacts:
            return UsageContext.NORMAL
        
        total_change = sum(i.usage_change for i in impacts)
        
        if total_change > 5:
            return UsageContext.INCREASED
        elif total_change < -5:
            return UsageContext.DECREASED
        else:
            return UsageContext.NORMAL
    
    def _generate_notes(self, ctx: ContextFlags, stat: str) -> list[str]:
        """Generate contextual notes for display."""
        notes = []
        
        # Rest notes
        if ctx.rest_status == RestStatus.B2B:
            notes.append("⚠️ B2B - fatigue risk")
        
        # Matchup notes
        if ctx.matchup_rank == MatchupRank.ELITE_D:
            notes.append(f"🛡️ vs {ctx.opponent} ({ctx.matchup_rank.value} DEF)")
        elif ctx.matchup_rank == MatchupRank.POOR_D:
            notes.append(f"🎯 vs {ctx.opponent} ({ctx.matchup_rank.value} DEF)")
        
        # Pace notes
        if ctx.opp_pace:
            if ctx.opp_pace > 101:
                notes.append("⚡ High pace game")
            elif ctx.opp_pace < 97:
                notes.append("🐢 Slow pace game")

        # NFL defensive pressure notes (if present)
        if ctx.opp_pass_rush_rate is not None:
            # Interpret pressure rate: >18% considered high, <14% considered low
            pr = ctx.opp_pass_rush_rate
            if pr >= 0.18:
                notes.append(f"🧨 High pass-rush ({pr:.1%}) vs {ctx.opponent}")
            elif pr <= 0.14:
                notes.append(f"🫧 Low pass-rush ({pr:.1%}) vs {ctx.opponent}")

        # Run-stopping notes
        if ctx.opp_run_stop_rank is not None:
            if ctx.opp_run_stop_rank <= 8:
                notes.append(f"🛑 Strong run defense (rank {ctx.opp_run_stop_rank})")
            elif ctx.opp_run_stop_rank >= 20:
                notes.append(f"🐾 Weak run defense (rank {ctx.opp_run_stop_rank})")
        
        # Injury impact notes
        for impact in ctx.injury_impacts:
            notes.append(f"📈 {impact.injured_player} {impact.injury_status}: {impact.impact_on_usage}")
        
        return notes


def format_context_flags(ctx: ContextFlags, include_risk: bool = True) -> str:
    """
    Format context flags for display in cheat sheet.
    
    Example: "Min:28-33 ✅ | Rest:2d+ | Usage:+ | vs 6-12"
    """
    parts = []
    
    # Minutes with risk marker
    if ctx.minutes_tier != MinutesTier.UNKNOWN:
        min_str = f"Min:{ctx.minutes_tier.value}"
        if include_risk and ctx.minutes_tier.risk_marker:
            min_str += f" {ctx.minutes_tier.risk_marker}"
        parts.append(min_str)
    
    # Rest
    if ctx.rest_status != RestStatus.UNKNOWN:
        parts.append(f"Rest:{ctx.rest_status.value}")
    
    # Usage
    if ctx.usage_context != UsageContext.UNKNOWN:
        parts.append(f"Usage:{ctx.usage_context.value}")
    
    # Matchup
    if ctx.matchup_rank != MatchupRank.UNKNOWN:
        parts.append(f"vs {ctx.matchup_rank.value}")
    
    return " | ".join(parts) if parts else "No context"


# Test
if __name__ == "__main__":
    provider = ContextProvider()
    
    # Test OG Anunoby context
    ctx = provider.get_context(
        player="OG Anunoby",
        team="NYK",
        opponent="SAS",
        stat="points",
    )
    
    print(f"Context for OG Anunoby vs SAS:")
    print(f"  Minutes: {ctx.minutes_tier.value}")
    print(f"  Rest: {ctx.rest_status.value}")
    print(f"  Usage: {ctx.usage_context.value}")
    print(f"  Matchup: {ctx.matchup_rank.value}")
    print(f"  Opponent DEF RTG: {ctx.opp_def_rating}")
    print(f"  Notes: {ctx.notes}")
    print(f"  Formatted: {format_context_flags(ctx)}")
