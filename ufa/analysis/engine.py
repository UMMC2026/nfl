"""
UNDERDOG FANTASY ANALYSIS v2.0 - Core Module
=============================================
Strategic Intelligence Engine

This module provides the core analysis functionality that can be 
integrated with the CLI or used standalone.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import statistics


class Priority(Enum):
    SLAM = "SLAM"
    STRONG = "STRONG"
    LEAN = "LEAN"
    SKIP = "SKIP"


class PlayDirection(Enum):
    OVER = "OVER"
    UNDER = "UNDER"
    HOLD = "HOLD"


@dataclass
class DefenseRanking:
    """Defensive rankings for a team (1-32, lower = better)"""
    rush: int
    passing: int  # renamed from 'pass' to avoid reserved word
    overall: int
    red_zone: int
    sacks_allowed: int


@dataclass
class PropBet:
    """A single prop bet with associated data"""
    stat: str
    line: float
    prop_type: str
    game_logs: List[float]


@dataclass
class PlayerContext:
    """Player-level context and flags"""
    injury: Optional[str] = None
    role_change: Optional[str] = None
    snap_pct: float = 100.0
    # Live/in-game context (optional)
    game_status: Optional[str] = None  # 'pre', 'in', 'post'
    quarter: Optional[int] = None
    elapsed_minutes: Optional[float] = None
    remaining_minutes: Optional[float] = None
    score_diff: Optional[int] = None
    # Live stat snapshot keyed by normalized stat names
    live_stats: Dict[str, float] = field(default_factory=dict)


@dataclass
class Player:
    """Player with all associated props and context"""
    name: str
    team: str
    opponent: str
    position: str
    props: List[PropBet]
    context: PlayerContext = field(default_factory=PlayerContext)


@dataclass 
class VolatilityMetrics:
    """Volatility and consistency metrics for a prop"""
    std_dev: float
    over_rate: float   # % of games OVER line
    under_rate: float  # % of games UNDER line
    trend: str
    consistency: str
    cv: float  # Coefficient of variation
    recent_avg: float
    season_avg: float


@dataclass
class AnalyzedProp:
    """Complete analysis of a single prop bet"""
    player: str
    team: str
    opponent: str
    stat: str
    line: float
    season_avg: float
    recent_avg: float
    weighted_avg: float
    matchup_mult: float
    adjusted_proj: float
    edge: float
    edge_pct: float
    hit_rate: float
    std_dev: float
    trend: str
    consistency: str
    value_score: float
    play: PlayDirection
    priority: Priority
    risk_flags: List[str] = field(default_factory=list)


@dataclass
class CorrelationGroup:
    """A group of correlated picks"""
    name: str
    players: List[str]
    props: List[str]
    dependency: str


class AnalysisEngine:
    """Core analysis engine implementing the v2.0 methodology"""
    
    def __init__(
        self,
        defense_rankings: Dict[str, DefenseRanking],
        correlation_groups: List[CorrelationGroup]
    ):
        self.defense_rankings = defense_rankings
        self.correlation_groups = correlation_groups
    
    def calculate_matchup_adjustment(
        self, 
        opponent: str, 
        prop_type: str
    ) -> float:
        """
        Apply matchup adjustment based on opponent defensive rankings.
        Returns multiplier (0.85 - 1.15)
        """
        opp_def = self.defense_rankings.get(opponent)
        if not opp_def:
            return 1.0
        
        # Map prop type to defensive ranking
        if prop_type in ["rush", "rush_rec", "rush_att"]:
            rank = opp_def.rush
        elif prop_type in ["pass", "rec", "rec_count"]:
            rank = opp_def.passing
        elif prop_type == "sack":
            # More sacks allowed = easier for pass rusher
            rank = 33 - (opp_def.sacks_allowed / 2)
        elif prop_type in ["td", "pass_td"]:
            rank = opp_def.red_zone
        elif prop_type == "int":
            return 1.15  # Interception-prone QBs vs good D
        elif prop_type == "tackles":
            return 1.0
        else:
            rank = opp_def.overall
        
        # Convert rank to multiplier
        # Rank 1 = 0.855, Rank 16 = 1.0, Rank 32 = 1.145
        if rank <= 10:
            return 0.85 + (rank * 0.005)
        elif rank >= 25:
            return 1.10 + ((rank - 25) * 0.015)
        else:
            return 1.0 + ((rank - 16) * 0.01)

    # ================================
    # Adjusted expectation helpers
    # ================================
    @staticmethod
    def detect_regime(game_status: Optional[str], quarter: Optional[int] = None, time_remaining: Optional[float] = None) -> str:
        """Return 'PREGAME' | 'INGAME' | 'CLOSED' based on status/clock."""
        s = (game_status or "pre").lower()
        if s in ("final", "post"):
            return "CLOSED"
        if s in ("in", "live"):
            return "INGAME"
        if quarter is not None:
            return "INGAME"
        return "PREGAME"

    @staticmethod
    def regime_weights(regime: str) -> Dict[str, float]:
        if regime == "PREGAME":
            return {"prior": 0.70, "state": 0.30}
        if regime == "INGAME":
            return {"prior": 0.25, "state": 0.75}
        return {"prior": 0.70, "state": 0.30}

    @staticmethod
    def projected_remaining_yards(current_yards: float, elapsed: float, remaining: float) -> float:
        if (elapsed or 0) <= 0:
            return 0.0
        pace = current_yards / max(elapsed, 1e-6)
        return pace * max(remaining or 0, 0)

    @staticmethod
    def adjusted_yard_expectation(prior_mean: float, state_yards: float, elapsed: float, remaining: float, w_prior: float, w_state: float) -> float:
        state_proj = state_yards + AnalysisEngine.projected_remaining_yards(state_yards, elapsed, remaining)
        return (w_prior * prior_mean) + (w_state * state_proj)

    @staticmethod
    def adjusted_reception_expectation(prior_receptions: float, current_receptions: float, current_targets: float, elapsed: float, remaining: float, w_prior: float, w_state: float) -> float:
        # If no targets by halftime, collapse state projection
        if (elapsed or 0) >= 20 and (current_targets or 0) == 0:
            state_proj = current_receptions
        else:
            target_rate = (current_targets or 0) / max(elapsed or 1.0, 1.0)
            state_proj = current_receptions + target_rate * max(remaining or 0, 0) * 0.75
        return (w_prior * prior_receptions) + (w_state * state_proj)

    @staticmethod
    def adjusted_td_expectation(prior_td_rate: float, red_zone_touches: float, w_prior: float, w_state: float) -> float:
        # Cap state weight when no RZ usage
        if (red_zone_touches or 0) == 0:
            w_state = min(w_state, 0.30)
        state_td = 0.25 if (red_zone_touches or 0) > 0 else 0.05
        return (w_prior * prior_td_rate) + (w_state * state_td)
    
    def calculate_recency_weighted_avg(
        self, 
        game_logs: List[float],
        season_weight: float = 0.4,
        recent_weight: float = 0.6
    ) -> float:
        """
        Calculate weighted average: default 40% season, 60% last 4 games.
        """
        if len(game_logs) < 4:
            return sum(game_logs) / len(game_logs)
        
        season_avg = sum(game_logs) / len(game_logs)
        recent_avg = sum(game_logs[-4:]) / 4
        
        return (season_avg * season_weight) + (recent_avg * recent_weight)
    
    def calculate_volatility_metrics(
        self, 
        game_logs: List[float], 
        line: float
    ) -> VolatilityMetrics:
        """
        Calculate volatility, over/under rates, trend, and consistency.
        """
        if len(game_logs) < 3:
            return VolatilityMetrics(
                std_dev=0, over_rate=50, under_rate=50, trend="STABLE",
                consistency="UNKNOWN", cv=0,
                recent_avg=game_logs[0] if game_logs else 0,
                season_avg=game_logs[0] if game_logs else 0
            )
        
        std_dev = statistics.stdev(game_logs)
        mean = statistics.mean(game_logs)
        cv = (std_dev / mean) * 100 if mean > 0 else 0
        
        # Over/Under rates - FIXED: track both independently
        overs = sum(1 for g in game_logs if g > line)
        unders = sum(1 for g in game_logs if g < line)
        over_rate = (overs / len(game_logs)) * 100
        under_rate = (unders / len(game_logs)) * 100
        
        # Trend
        season_avg = sum(game_logs) / len(game_logs)
        recent_avg = sum(game_logs[-4:]) / 4 if len(game_logs) >= 4 else season_avg
        
        if recent_avg > season_avg * 1.10:
            trend = "HOT"
        elif recent_avg > season_avg * 1.05:
            trend = "UP"
        elif recent_avg < season_avg * 0.90:
            trend = "DOWN"
        elif recent_avg < season_avg * 0.95:
            trend = "COOLING"
        else:
            trend = "STABLE"
        
        # Consistency
        if cv < 20:
            consistency = "HIGH"
        elif cv < 35:
            consistency = "MODERATE"
        else:
            consistency = "LOW"
        
        return VolatilityMetrics(
            std_dev=std_dev,
            over_rate=over_rate,
            under_rate=under_rate,
            trend=trend,
            consistency=consistency,
            cv=cv,
            recent_avg=recent_avg,
            season_avg=season_avg
        )
    
    def calculate_value_score(
        self,
        edge_pct: float,
        hit_rate: float,
        consistency: str,
        matchup_boost: float,
        volatility_penalty: float
    ) -> float:
        """
        Value Score = 
          (Edge Size × 2.0) +
          (Hit Rate × 0.5) +
          (Consistency Score × 3.0) -
          (Volatility Penalty × 4.0) +
          (Matchup Boost × 1.5)
        """
        consistency_score = {
            "HIGH": 10, 
            "MODERATE": 5, 
            "LOW": 0, 
            "UNKNOWN": 3
        }.get(consistency, 3)
        
        value = (
            (edge_pct * 2.0) +
            (hit_rate * 0.5) +
            (consistency_score * 3.0) -
            (volatility_penalty * 4.0) +
            (matchup_boost * 1.5)
        )
        
        return max(0, min(100, value))
    
    def determine_play(
        self, 
        edge_pct: float, 
        over_rate: float,
        under_rate: float
    ) -> Tuple[PlayDirection, Priority]:
        """Determine play direction and priority based on edge and hit rates."""
        
        # OVER plays - use over_rate
        if edge_pct > 20 and over_rate >= 70:
            return PlayDirection.OVER, Priority.SLAM
        elif edge_pct > 12 and over_rate >= 60:
            return PlayDirection.OVER, Priority.STRONG
        # UNDER plays - use under_rate (FIXED!)
        elif edge_pct < -20 and under_rate >= 70:
            return PlayDirection.UNDER, Priority.SLAM
        elif edge_pct < -12 and under_rate >= 60:
            return PlayDirection.UNDER, Priority.STRONG
        elif edge_pct > 8:
            return PlayDirection.OVER, Priority.LEAN
        elif edge_pct < -8:
            return PlayDirection.UNDER, Priority.LEAN
        else:
            return PlayDirection.HOLD, Priority.SKIP
    
    def analyze_prop(
        self, 
        player: Player, 
        prop: PropBet
    ) -> AnalyzedProp:
        """Complete analysis of a single prop bet."""
        
        game_logs = prop.game_logs
        line = prop.line
        
        # Basic averages
        season_avg = sum(game_logs) / len(game_logs)
        recent_avg = sum(game_logs[-4:]) / 4 if len(game_logs) >= 4 else season_avg
        weighted_avg = self.calculate_recency_weighted_avg(game_logs)
        
        # Matchup adjustment
        matchup_mult = self.calculate_matchup_adjustment(player.opponent, prop.prop_type)

        # Prior/State adjusted expectation wiring
        regime = self.detect_regime(player.context.game_status, player.context.quarter, player.context.remaining_minutes)
        weights = self.regime_weights(regime)

        # If no live context/stats, fall back to weighted_avg
        adjusted_base = None
        if player.context.live_stats or player.context.elapsed_minutes is not None:
            elapsed = float(player.context.elapsed_minutes or 0.0)
            remaining = float(player.context.remaining_minutes or 0.0)
            ls = player.context.live_stats
            if prop.prop_type in ("rush", "pass", "rec"):
                key = {"rush": "rush_yds", "pass": "pass_yds", "rec": "rec_yds"}[prop.prop_type]
                state_yards = float(ls.get(key, 0.0))
                adjusted_base = self.adjusted_yard_expectation(weighted_avg, state_yards, elapsed, remaining, weights["prior"], weights["state"])
            elif prop.prop_type == "rec_count":
                current_rec = float(ls.get("receptions", 0.0))
                current_tgt = float(ls.get("targets", 0.0))
                # Use per-game recent average of receptions as prior
                prior_rec = weighted_avg
                adjusted_base = self.adjusted_reception_expectation(prior_rec, current_rec, current_tgt, elapsed, remaining, weights["prior"], weights["state"])

        adjusted_proj = (adjusted_base if adjusted_base is not None else weighted_avg) * matchup_mult
        
        # Volatility metrics (now has over_rate AND under_rate)
        vol_metrics = self.calculate_volatility_metrics(game_logs, line)
        
        # Edge calculation
        edge = adjusted_proj - line
        edge_pct = (edge / line) * 100 if line > 0 else 0
        
        # Determine play direction FIRST (needed for correct hit rate)
        play, priority = self.determine_play(edge_pct, vol_metrics.over_rate, vol_metrics.under_rate)
        
        # FIXED: Use correct hit rate based on play direction
        if play == PlayDirection.UNDER:
            hit_rate = vol_metrics.under_rate
        else:
            hit_rate = vol_metrics.over_rate
        
        # Value score components
        matchup_boost = (matchup_mult - 1.0) * 100
        vol_penalty = vol_metrics.cv / 10 if vol_metrics.cv > 25 else 0
        
        value_score = self.calculate_value_score(
            abs(edge_pct),  # Use absolute edge for value calc
            hit_rate,
            vol_metrics.consistency,
            matchup_boost,
            vol_penalty
        )
        
        # Risk flags
        risk_flags = []
        if player.context.injury:
            risk_flags.append(f"INJURY: {player.context.injury}")
        if player.context.role_change:
            risk_flags.append(f"ROLE: {player.context.role_change}")
        
        return AnalyzedProp(
            player=player.name,
            team=player.team,
            opponent=player.opponent,
            stat=prop.stat,
            line=line,
            season_avg=season_avg,
            recent_avg=recent_avg,
            weighted_avg=weighted_avg,
            matchup_mult=matchup_mult,
            adjusted_proj=adjusted_proj,
            edge=edge,
            edge_pct=edge_pct,
            hit_rate=hit_rate,  # FIXED: Now uses correct rate based on play direction
            std_dev=vol_metrics.std_dev,
            trend=vol_metrics.trend,
            consistency=vol_metrics.consistency,
            value_score=value_score,
            play=play,
            priority=priority,
            risk_flags=risk_flags
        )
    
    def analyze_player(self, player: Player) -> List[AnalyzedProp]:
        """Analyze all props for a player."""
        return [self.analyze_prop(player, prop) for prop in player.props]
    
    def detect_correlations(
        self, 
        picks: List[AnalyzedProp]
    ) -> List[Dict]:
        """Detect correlated picks and return warnings."""
        warnings = []
        
        for group in self.correlation_groups:
            matched = []
            for pick in picks:
                if (pick.player in group.players and 
                    pick.priority in [Priority.SLAM, Priority.STRONG, Priority.LEAN]):
                    matched.append(pick)
            
            if len(matched) >= 2:
                warnings.append({
                    "group_name": group.name,
                    "players": [(p.player, p.stat) for p in matched],
                    "dependency": group.dependency,
                    "count": len(matched)
                })
        
        return warnings
    
    def analyze_all(
        self, 
        players: List[Player]
    ) -> Tuple[List[AnalyzedProp], List[Dict]]:
        """
        Analyze all players and return:
        1. All analyzed props sorted by value score
        2. Correlation warnings
        """
        all_results = []
        for player in players:
            results = self.analyze_player(player)
            all_results.extend(results)
        
        # Sort by value score
        all_results.sort(key=lambda x: x.value_score, reverse=True)
        
        # Detect correlations
        correlations = self.detect_correlations(all_results)
        
        return all_results, correlations


# ============================================================================
# HELPER FUNCTIONS FOR DISPLAY
# ============================================================================

def get_trend_icon(trend: str) -> str:
    """Get emoji icon for trend."""
    icons = {
        "HOT": "🔥",
        "UP": "📈",
        "DOWN": "📉",
        "COOLING": "❄️",
        "STABLE": "➡️"
    }
    return icons.get(trend, "➡️")


def get_consistency_icon(consistency: str) -> str:
    """Get emoji icon for consistency."""
    if consistency == "HIGH":
        return "🔒🔒🔒"
    elif consistency == "MODERATE":
        return "🔒🔒"
    else:
        return "⚡"


def get_recommendation(value_score: float) -> str:
    """Get betting recommendation based on value score."""
    if value_score >= 80:
        return "MAX PLAY (3-4 units)"
    elif value_score >= 65:
        return "STRONG PLAY (2-3 units)"
    elif value_score >= 50:
        return "MODERATE PLAY (1-2 units)"
    else:
        return "SMALL PLAY (0.5-1 unit)"


def format_play_string(prop: AnalyzedProp) -> str:
    """Format a complete play string for display."""
    direction = prop.play.value
    return (
        f"{prop.player} {prop.stat} {direction} {prop.line} "
        f"(Proj: {prop.adjusted_proj:.1f}, Edge: {prop.edge:+.1f}, "
        f"Hit: {prop.hit_rate:.0f}%, Value: {prop.value_score:.0f})"
    )
