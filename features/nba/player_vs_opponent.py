"""
Player vs Opponent Stats - Matchup Memory Layer
================================================

Computes player-specific performance tendencies against specific teams/defenders.
Uses Bayesian shrinkage to blend matchup history with league-wide priors.

ARCHITECTURE:
- MatchupRecord: Single game matchup data point
- PlayerVsOpponentStats: Aggregated matchup statistics with uncertainty
- compute_matchup_adjustment(): Main entry point for probability adjustments

CRITICAL: This module NEVER overrides Monte Carlo probabilities.
It provides adjustment factors that can be optionally applied with shrinkage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class MatchupRecord:
    """
    Single game record of player performance vs specific opponent.
    
    Captures the raw data point before aggregation.
    """
    game_id: str
    game_date: datetime
    player_id: str
    player_name: str
    opponent_team: str
    stat_type: str
    stat_value: float
    line: Optional[float] = None  # Underdog line if known
    hit: Optional[bool] = None  # Did player exceed line?
    
    # Context factors
    home_away: str = "home"  # 'home' or 'away'
    minutes_played: float = 0.0
    pace: Optional[float] = None  # Game pace if available
    rest_days: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_date": self.game_date.isoformat() if self.game_date else None,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "opponent_team": self.opponent_team,
            "stat_type": self.stat_type,
            "stat_value": self.stat_value,
            "line": self.line,
            "hit": self.hit,
            "home_away": self.home_away,
            "minutes_played": self.minutes_played,
            "pace": self.pace,
            "rest_days": self.rest_days,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MatchupRecord":
        game_date = d.get("game_date")
        if isinstance(game_date, str):
            game_date = datetime.fromisoformat(game_date)
        return cls(
            game_id=d["game_id"],
            game_date=game_date,
            player_id=d["player_id"],
            player_name=d["player_name"],
            opponent_team=d["opponent_team"],
            stat_type=d["stat_type"],
            stat_value=d["stat_value"],
            line=d.get("line"),
            hit=d.get("hit"),
            home_away=d.get("home_away", "home"),
            minutes_played=d.get("minutes_played", 0.0),
            pace=d.get("pace"),
            rest_days=d.get("rest_days", 1),
        )


@dataclass
class PlayerVsOpponentStats:
    """
    Aggregated statistics for a player vs specific opponent team.
    
    Tracks both raw performance and Bayesian-adjusted estimates.
    """
    player_id: str
    player_name: str
    opponent_team: str
    stat_type: str
    
    # Raw matchup statistics
    games_played: int = 0
    total_value: float = 0.0
    mean: float = 0.0
    std_dev: float = 0.0
    min_value: float = float('inf')
    max_value: float = float('-inf')
    
    # Hit rate tracking (if lines available)
    lines_tracked: int = 0
    hits: int = 0
    hit_rate: Optional[float] = None
    
    # Bayesian-adjusted estimates
    shrunk_mean: Optional[float] = None
    shrinkage_weight: float = 0.0  # 0 = full prior, 1 = full sample
    confidence: float = 0.0  # 0.0-1.0 based on sample size and variance
    
    # Per-minute rates (for minutes adjustment)
    per_minute_rate: Optional[float] = None
    per_minute_std: Optional[float] = None
    
    # Recency weighting
    recency_weighted_mean: Optional[float] = None
    last_game_date: Optional[datetime] = None
    
    # Metadata
    records: List[MatchupRecord] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    
    def add_record(self, record: MatchupRecord):
        """Add a new matchup record and update aggregates."""
        self.records.append(record)
        self.games_played += 1
        self.total_value += record.stat_value
        
        # Update min/max
        self.min_value = min(self.min_value, record.stat_value)
        self.max_value = max(self.max_value, record.stat_value)
        
        # Update hit tracking
        if record.hit is not None:
            self.lines_tracked += 1
            if record.hit:
                self.hits += 1
            self.hit_rate = self.hits / self.lines_tracked if self.lines_tracked > 0 else None
        
        # Update date tracking
        if record.game_date:
            if self.last_game_date is None or record.game_date > self.last_game_date:
                self.last_game_date = record.game_date
        
        self.last_updated = datetime.now()
        self._recompute_stats()
    
    def _recompute_stats(self):
        """Recompute aggregate statistics from records."""
        if not self.records:
            return
            
        values = [r.stat_value for r in self.records]
        self.mean = sum(values) / len(values)
        
        if len(values) > 1:
            variance = sum((v - self.mean) ** 2 for v in values) / (len(values) - 1)
            self.std_dev = math.sqrt(variance)
        else:
            self.std_dev = 0.0
        
        # Compute per-minute rates if minutes available
        valid_minutes = [(r.stat_value, r.minutes_played) 
                         for r in self.records if r.minutes_played > 0]
        if valid_minutes:
            rates = [v / m for v, m in valid_minutes]
            self.per_minute_rate = sum(rates) / len(rates)
            if len(rates) > 1:
                rate_var = sum((r - self.per_minute_rate) ** 2 for r in rates) / (len(rates) - 1)
                self.per_minute_std = math.sqrt(rate_var)
        
        # Recency-weighted mean (exponential decay, lambda=0.9)
        self._compute_recency_weighted()
    
    def _compute_recency_weighted(self, decay: float = 0.9):
        """Compute recency-weighted mean with exponential decay."""
        if not self.records:
            return
            
        # Sort by date (most recent first)
        sorted_records = sorted(
            [r for r in self.records if r.game_date], 
            key=lambda x: x.game_date, 
            reverse=True
        )
        
        if not sorted_records:
            self.recency_weighted_mean = self.mean
            return
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for i, record in enumerate(sorted_records):
            weight = decay ** i
            weighted_sum += record.stat_value * weight
            total_weight += weight
        
        self.recency_weighted_mean = weighted_sum / total_weight if total_weight > 0 else self.mean
    
    def apply_bayesian_shrinkage(
        self,
        league_mean: float,
        league_std: float,
        min_games: int = 3,
        prior_strength: float = 5.0,
        confidence_games: int = 10,
    ):
        """
        Apply Bayesian shrinkage toward league average.
        
        With small samples, we shrink toward the league mean.
        As sample size grows, we trust the matchup-specific data more.
        
        prior_strength: Effective sample size of the prior (default 5 games worth)
        """
        if self.games_played == 0:
            self.shrunk_mean = league_mean
            self.shrinkage_weight = 0.0
            self.confidence = 0.0
            return
        
        # Compute shrinkage weight using Bayesian formula
        # w = n / (n + k) where k = prior_strength * (sample_var / prior_var)
        sample_var = self.std_dev ** 2 if self.std_dev > 0 else league_std ** 2
        prior_var = league_std ** 2 if league_std > 0 else 1.0
        
        # Adjust k based on variance ratio
        variance_ratio = sample_var / prior_var if prior_var > 0 else 1.0
        k = prior_strength * min(variance_ratio, 3.0)  # Cap adjustment at 3x
        
        self.shrinkage_weight = self.games_played / (self.games_played + k)
        
        # Shrunk estimate: blend of sample mean and prior mean
        self.shrunk_mean = (
            self.shrinkage_weight * self.mean + 
            (1 - self.shrinkage_weight) * league_mean
        )
        
        # Confidence based on sample size and variance stability
        # `confidence_games` controls how quickly confidence saturates.
        # Default remains 10 to preserve historical behavior.
        denom = float(confidence_games) if confidence_games and confidence_games > 0 else 10.0
        sample_confidence = min(1.0, self.games_played / denom)
        variance_confidence = 1.0 / (1.0 + variance_ratio) if variance_ratio > 1 else 1.0
        self.confidence = sample_confidence * variance_confidence


@dataclass
class MatchupAdjustment:
    """Human-facing matchup adjustment summary.

    This is intentionally a small, stable surface used by the interactive
    Matchup Memory menu.
    """

    raw_adjustment: float
    shrunk_adjustment: float
    weight: float
    confidence: float
    games_played: int
    matchup_mean: float
    baseline_mean: float


def compute_matchup_adjustment_from_stats(
    matchup_stats: PlayerVsOpponentStats,
    *,
    baseline_mean: float,
    baseline_std: float,
    shrinkage_games: int = 10,
    min_games: int = 3,
    prior_strength: float = 5.0,
) -> MatchupAdjustment:
    """Compute Bayesian-shrunk adjustment from pre-aggregated matchup stats.

    This is a convenience wrapper for interactive usage when we already have:
    - player overall mean/std (baseline)
    - matchup mean/std and sample size

    The shrinkage target is the *baseline_mean* (player overall), not a
    league-wide prior.
    """
    try:
        games = int(matchup_stats.games_played or 0)
    except Exception:
        games = 0

    raw_adj = float(matchup_stats.mean or 0.0) - float(baseline_mean or 0.0)

    if games < int(min_games or 3):
        return MatchupAdjustment(
            raw_adjustment=raw_adj,
            shrunk_adjustment=0.0,
            weight=0.0,
            confidence=0.0,
            games_played=games,
            matchup_mean=float(matchup_stats.mean or 0.0),
            baseline_mean=float(baseline_mean or 0.0),
        )

    # Re-use the shrinkage mechanics on the stats object, but point it at the
    # player's own baseline. This prevents small-sample matchup noise from
    # dominating.
    matchup_stats.apply_bayesian_shrinkage(
        float(baseline_mean or 0.0),
        float(baseline_std or 0.0),
        min_games=int(min_games or 3),
        prior_strength=float(prior_strength or 5.0),
        confidence_games=int(shrinkage_games or 10),
    )

    shrunk_mean = matchup_stats.shrunk_mean
    if shrunk_mean is None:
        shrunk_adj = 0.0
    else:
        shrunk_adj = float(shrunk_mean) - float(baseline_mean or 0.0)

    return MatchupAdjustment(
        raw_adjustment=raw_adj,
        shrunk_adjustment=shrunk_adj,
        weight=float(matchup_stats.shrinkage_weight or 0.0),
        confidence=float(matchup_stats.confidence or 0.0),
        games_played=games,
        matchup_mean=float(matchup_stats.mean or 0.0),
        baseline_mean=float(baseline_mean or 0.0),
    )
    
    def get_adjustment_factor(self, baseline_mean: float) -> Tuple[float, float]:
        """
        Get adjustment factor relative to baseline.
        
        Returns:
            (factor, confidence): Factor to multiply baseline by, and confidence 0-1
        """
        if self.shrunk_mean is None or baseline_mean <= 0:
            return (1.0, 0.0)
        
        factor = self.shrunk_mean / baseline_mean
        return (factor, self.confidence)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "opponent_team": self.opponent_team,
            "stat_type": self.stat_type,
            "games_played": self.games_played,
            "total_value": self.total_value,
            "mean": self.mean,
            "std_dev": self.std_dev,
            "min_value": self.min_value if self.min_value != float('inf') else None,
            "max_value": self.max_value if self.max_value != float('-inf') else None,
            "lines_tracked": self.lines_tracked,
            "hits": self.hits,
            "hit_rate": self.hit_rate,
            "shrunk_mean": self.shrunk_mean,
            "shrinkage_weight": self.shrinkage_weight,
            "confidence": self.confidence,
            "per_minute_rate": self.per_minute_rate,
            "per_minute_std": self.per_minute_std,
            "recency_weighted_mean": self.recency_weighted_mean,
            "last_game_date": self.last_game_date.isoformat() if self.last_game_date else None,
            "records": [r.to_dict() for r in self.records],
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlayerVsOpponentStats":
        records = [MatchupRecord.from_dict(r) for r in d.get("records", [])]
        last_game_date = d.get("last_game_date")
        if isinstance(last_game_date, str):
            last_game_date = datetime.fromisoformat(last_game_date)
        last_updated = d.get("last_updated")
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
            
        return cls(
            player_id=d["player_id"],
            player_name=d["player_name"],
            opponent_team=d["opponent_team"],
            stat_type=d["stat_type"],
            games_played=d.get("games_played", 0),
            total_value=d.get("total_value", 0.0),
            mean=d.get("mean", 0.0),
            std_dev=d.get("std_dev", 0.0),
            min_value=d.get("min_value") or float('inf'),
            max_value=d.get("max_value") or float('-inf'),
            lines_tracked=d.get("lines_tracked", 0),
            hits=d.get("hits", 0),
            hit_rate=d.get("hit_rate"),
            shrunk_mean=d.get("shrunk_mean"),
            shrinkage_weight=d.get("shrinkage_weight", 0.0),
            confidence=d.get("confidence", 0.0),
            per_minute_rate=d.get("per_minute_rate"),
            per_minute_std=d.get("per_minute_std"),
            recency_weighted_mean=d.get("recency_weighted_mean"),
            last_game_date=last_game_date,
            records=records,
            last_updated=last_updated,
        )


class MatchupIndex:
    """
    Index for fast lookup of player vs opponent matchup stats.
    
    Key format: "{player_id}:{opponent_team}:{stat_type}"
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("outputs/matchup_memory")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._index: Dict[str, PlayerVsOpponentStats] = {}
        self._load_index()
    
    def _make_key(self, player_id: str, opponent_team: str, stat_type: str) -> str:
        return f"{player_id}:{opponent_team.upper()}:{stat_type.upper()}"
    
    def _load_index(self):
        """Load existing index from disk."""
        index_path = self.storage_path / "matchup_index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)
                self._index = {
                    k: PlayerVsOpponentStats.from_dict(v) 
                    for k, v in data.items()
                }
                logger.info(f"Loaded matchup index with {len(self._index)} entries")
            except Exception as e:
                logger.warning(f"Failed to load matchup index: {e}")
    
    def save_index(self):
        """Persist index to disk."""
        index_path = self.storage_path / "matchup_index.json"
        data = {k: v.to_dict() for k, v in self._index.items()}
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved matchup index with {len(self._index)} entries")
    
    def add_record(self, record: MatchupRecord):
        """Add a matchup record to the index."""
        key = self._make_key(record.player_id, record.opponent_team, record.stat_type)
        
        if key not in self._index:
            self._index[key] = PlayerVsOpponentStats(
                player_id=record.player_id,
                player_name=record.player_name,
                opponent_team=record.opponent_team,
                stat_type=record.stat_type,
            )
        
        self._index[key].add_record(record)
    
    def get_stats(self, player_id: str, opponent_team: str, 
                  stat_type: str) -> Optional[PlayerVsOpponentStats]:
        """Retrieve matchup stats for a specific player/opponent/stat combination."""
        key = self._make_key(player_id, opponent_team, stat_type)
        return self._index.get(key)
    
    def get_player_matchups(self, player_id: str) -> Dict[str, PlayerVsOpponentStats]:
        """Get all matchup stats for a player."""
        prefix = f"{player_id}:"
        return {k: v for k, v in self._index.items() if k.startswith(prefix)}
    
    def apply_shrinkage_all(self, league_priors: Dict[str, Tuple[float, float]]):
        """
        Apply Bayesian shrinkage to all entries using league priors.
        
        league_priors: Dict mapping stat_type -> (mean, std_dev)
        """
        for key, stats in self._index.items():
            stat_type = stats.stat_type.upper()
            if stat_type in league_priors:
                league_mean, league_std = league_priors[stat_type]
                stats.apply_bayesian_shrinkage(league_mean, league_std)
            else:
                # Use fallback priors
                stats.apply_bayesian_shrinkage(10.0, 5.0)


def build_matchup_index(game_logs: List[Dict[str, Any]], 
                        player_id: str,
                        stat_types: List[str]) -> MatchupIndex:
    """
    Build a matchup index from game log data.
    
    Args:
        game_logs: List of game log dicts with stats
        player_id: Player ID to index
        stat_types: List of stat types to track (e.g., ['PTS', 'REB', 'AST'])
    
    Returns:
        Populated MatchupIndex
    """
    index = MatchupIndex()
    
    for game in game_logs:
        opponent = game.get("opponent") or game.get("vs_team") or game.get("opp")
        if not opponent:
            continue
        
        game_date = game.get("date") or game.get("game_date")
        if isinstance(game_date, str):
            try:
                game_date = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
            except:
                game_date = datetime.now()
        
        for stat_type in stat_types:
            stat_value = game.get(stat_type.lower()) or game.get(stat_type.upper())
            if stat_value is None:
                continue
            
            record = MatchupRecord(
                game_id=game.get("game_id", f"{game_date}_{opponent}"),
                game_date=game_date,
                player_id=player_id,
                player_name=game.get("player_name", player_id),
                opponent_team=opponent,
                stat_type=stat_type.upper(),
                stat_value=float(stat_value),
                home_away=game.get("home_away", "home"),
                minutes_played=float(game.get("minutes", 0) or game.get("min", 0) or 0),
                pace=game.get("pace"),
                rest_days=int(game.get("rest_days", 1) or 1),
            )
            index.add_record(record)
    
    return index


def compute_matchup_adjustment(
    player_id: str,
    opponent_team: str,
    stat_type: str,
    baseline_projection: float,
    matchup_index: Optional[MatchupIndex] = None,
    league_mean: float = 10.0,
    league_std: float = 5.0,
    min_games: int = 3,
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Compute adjusted projection based on matchup history.
    
    This is the main entry point for the matchup memory layer.
    
    Args:
        player_id: Player identifier
        opponent_team: Opponent team code (e.g., 'BOS', 'LAL')
        stat_type: Stat type (e.g., 'PTS', 'REB')
        baseline_projection: Base projection from Monte Carlo
        matchup_index: Optional pre-built index
        league_mean: League average for stat type
        league_std: League standard deviation for stat type
        min_games: Minimum games required for adjustment
    
    Returns:
        (adjusted_projection, confidence, lineage_dict)
        - adjusted_projection: Projection after matchup adjustment
        - confidence: 0.0-1.0 confidence in adjustment
        - lineage_dict: Audit trail for probability lineage
    """
    lineage = {
        "source": "matchup_memory",
        "player_id": player_id,
        "opponent_team": opponent_team,
        "stat_type": stat_type,
        "baseline_projection": baseline_projection,
        "adjustment_applied": False,
        "games_vs_opponent": 0,
        "matchup_mean": None,
        "shrunk_mean": None,
        "adjustment_factor": 1.0,
        "confidence": 0.0,
    }
    
    # Load or use provided index
    if matchup_index is None:
        matchup_index = MatchupIndex()
    
    # Look up matchup stats
    stats = matchup_index.get_stats(player_id, opponent_team, stat_type)
    
    if stats is None or stats.games_played < min_games:
        # Insufficient data - return baseline unchanged
        lineage["reason"] = f"insufficient_games ({stats.games_played if stats else 0} < {min_games})"
        return (baseline_projection, 0.0, lineage)
    
    # Apply Bayesian shrinkage
    stats.apply_bayesian_shrinkage(league_mean, league_std, min_games)
    
    # Get adjustment factor
    factor, confidence = stats.get_adjustment_factor(league_mean)
    
    # Apply conservative adjustment (blend with 1.0)
    # More conservative for lower confidence
    blended_factor = 1.0 + (factor - 1.0) * confidence
    
    adjusted = baseline_projection * blended_factor
    
    # Update lineage
    lineage.update({
        "adjustment_applied": True,
        "games_vs_opponent": stats.games_played,
        "matchup_mean": stats.mean,
        "shrunk_mean": stats.shrunk_mean,
        "shrinkage_weight": stats.shrinkage_weight,
        "adjustment_factor": blended_factor,
        "confidence": confidence,
        "recency_weighted_mean": stats.recency_weighted_mean,
    })
    
    logger.info(
        f"Matchup adjustment: {player_id} vs {opponent_team} {stat_type}: "
        f"{baseline_projection:.1f} -> {adjusted:.1f} (factor={blended_factor:.3f}, conf={confidence:.2f})"
    )
    
    return (adjusted, confidence, lineage)


# League-wide default priors (can be overridden)
NBA_LEAGUE_PRIORS = {
    "PTS": (15.0, 8.0),
    "REB": (5.0, 3.5),
    "AST": (4.0, 3.0),
    "STL": (1.0, 0.7),
    "BLK": (0.6, 0.6),
    "3PM": (1.5, 1.5),
    "TOV": (2.0, 1.2),
    "PRA": (24.0, 12.0),
    "PR": (20.0, 10.0),
    "PA": (19.0, 10.0),
    "RA": (9.0, 5.0),
    "STOCKS": (1.6, 1.0),
}
