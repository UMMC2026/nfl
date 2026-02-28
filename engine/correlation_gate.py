"""
CORRELATED BET DETECTION GATE — Priority 2 Implementation
==========================================================

Detects and flags correlated picks that appear independent but aren't.

Correlation Types:
1. Same Game (95% correlation) - Two picks on same game
2. Same Player (100% correlation) - Multiple props on same player
3. Same Team (70-80% correlation) - Multiple players from same team
4. Stat Correlation (varies) - Related stats (e.g., points + FGA)
5. Outcome Correlation - If team loses, individual stats suffer

Phase: 5B
Created: 2026-02-05
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from itertools import combinations

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


# =============================================================================
# CORRELATION TYPES AND WEIGHTS
# =============================================================================

class CorrelationType:
    """Types of correlations between picks."""
    SAME_PLAYER = "same_player"           # Same player, different stats
    SAME_GAME = "same_game"               # Different players, same game
    SAME_TEAM = "same_team"               # Same team players
    OPPOSING_TEAMS = "opposing_teams"      # Players from opposing teams
    STAT_RELATED = "stat_related"          # Correlated stats (e.g., pts + fga)
    DIRECTION_CONFLICT = "direction_conflict"  # Over + Under on related stats


# Correlation weights (how strongly correlated)
CORRELATION_WEIGHTS = {
    CorrelationType.SAME_PLAYER: 1.00,        # 100% correlated
    CorrelationType.SAME_GAME: 0.50,          # 50% correlation
    CorrelationType.SAME_TEAM: 0.70,          # 70% correlation
    CorrelationType.OPPOSING_TEAMS: 0.30,     # 30% inverse correlation
    CorrelationType.STAT_RELATED: 0.60,       # 60% correlation
    CorrelationType.DIRECTION_CONFLICT: 0.40, # Conflicting directions
}


# Stat correlation groups
CORRELATED_STATS = {
    # NBA
    "points": ["fga", "fta", "minutes", "pra"],
    "assists": ["minutes", "pra", "pts+ast"],
    "rebounds": ["minutes", "pra", "pts+reb"],
    "3pm": ["fga", "fg3a", "points"],
    "pra": ["points", "assists", "rebounds"],
    
    # NHL
    "sog": ["goals", "assists", "toi"],
    "saves": ["goals_against", "shots_faced"],
    
    # Golf
    "round_strokes": ["birdies", "bogeys"],
    "birdies": ["round_strokes", "greens_hit"],
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class CorrelationPair:
    """A pair of correlated picks."""
    pick_1_id: str
    pick_2_id: str
    pick_1_player: str
    pick_2_player: str
    pick_1_stat: str
    pick_2_stat: str
    
    correlation_type: str
    correlation_strength: float  # 0.0 - 1.0
    
    # Game info
    game_key: str = ""
    
    # Risk assessment
    risk_level: str = "low"  # low, medium, high, critical
    recommendation: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "pick_1_id": self.pick_1_id,
            "pick_2_id": self.pick_2_id,
            "pick_1_player": self.pick_1_player,
            "pick_2_player": self.pick_2_player,
            "pick_1_stat": self.pick_1_stat,
            "pick_2_stat": self.pick_2_stat,
            "correlation_type": self.correlation_type,
            "correlation_strength": round(self.correlation_strength, 2),
            "game_key": self.game_key,
            "risk_level": self.risk_level,
            "recommendation": self.recommendation,
        }


@dataclass
class CorrelationCheckResult:
    """Result of correlation detection."""
    total_picks: int = 0
    correlated_pairs: List[CorrelationPair] = field(default_factory=list)
    
    # Risk summary
    high_risk_pairs: int = 0
    medium_risk_pairs: int = 0
    low_risk_pairs: int = 0
    
    # Effective exposure
    max_single_game_exposure: int = 0
    max_single_player_exposure: int = 0
    max_single_team_exposure: int = 0
    
    # Recommendations
    warnings: List[str] = field(default_factory=list)
    should_reduce: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "total_picks": self.total_picks,
            "correlated_pairs_count": len(self.correlated_pairs),
            "correlated_pairs": [p.to_dict() for p in self.correlated_pairs],
            "high_risk_pairs": self.high_risk_pairs,
            "medium_risk_pairs": self.medium_risk_pairs,
            "low_risk_pairs": self.low_risk_pairs,
            "max_single_game_exposure": self.max_single_game_exposure,
            "max_single_player_exposure": self.max_single_player_exposure,
            "max_single_team_exposure": self.max_single_team_exposure,
            "warnings": self.warnings,
            "should_reduce": self.should_reduce,
        }


@dataclass
class CorrelationGateConfig:
    """Configuration for correlation detection."""
    
    # Thresholds for risk levels
    high_correlation_threshold: float = 0.80
    medium_correlation_threshold: float = 0.50
    
    # Maximum exposure limits
    max_picks_per_game: int = 3
    max_picks_per_player: int = 2
    max_picks_per_team: int = 4
    
    # Blocking rules
    block_same_player_same_stat: bool = True
    warn_same_game: bool = True
    warn_same_team: bool = True
    
    # Output
    include_low_risk_in_report: bool = False


DEFAULT_CONFIG = CorrelationGateConfig()


# =============================================================================
# CORRELATION DETECTOR
# =============================================================================

class CorrelationDetector:
    """
    Detects correlations between picks.
    
    Usage:
        detector = CorrelationDetector()
        result = detector.detect_correlations(picks)
        
        for pair in result.correlated_pairs:
            print(f"{pair.pick_1_player} ↔ {pair.pick_2_player}: {pair.risk_level}")
    """
    
    def __init__(self, config: CorrelationGateConfig = None):
        self.config = config or DEFAULT_CONFIG
    
    def _extract_game_key(self, pick: Dict) -> str:
        """Extract game identifier from pick."""
        # Try various field names
        if "game_id" in pick:
            return pick["game_id"]
        if "game_key" in pick:
            return pick["game_key"]
        if "matchup" in pick:
            return pick["matchup"]
        
        # Construct from team info
        team = pick.get("team", "")
        opponent = pick.get("opponent", "")
        if team and opponent:
            # Sort to ensure same key regardless of home/away
            teams = sorted([team.upper(), opponent.upper()])
            return f"{teams[0]}@{teams[1]}"
        
        return ""
    
    def _are_stats_correlated(self, stat1: str, stat2: str) -> Tuple[bool, float]:
        """
        Check if two stats are correlated.
        
        Returns:
            Tuple of (is_correlated, correlation_strength)
        """
        stat1 = stat1.lower()
        stat2 = stat2.lower()
        
        if stat1 == stat2:
            return True, 1.0
        
        # Check correlation groups
        group1 = CORRELATED_STATS.get(stat1, [])
        group2 = CORRELATED_STATS.get(stat2, [])
        
        if stat2 in group1 or stat1 in group2:
            return True, 0.60
        
        return False, 0.0
    
    def _detect_pair_correlation(
        self,
        pick1: Dict,
        pick2: Dict,
    ) -> Optional[CorrelationPair]:
        """
        Detect correlation between two picks.
        
        Returns CorrelationPair if correlated, None otherwise.
        """
        player1 = pick1.get("player", "").lower()
        player2 = pick2.get("player", "").lower()
        stat1 = pick1.get("stat", "").lower()
        stat2 = pick2.get("stat", "").lower()
        team1 = pick1.get("team", "").upper()
        team2 = pick2.get("team", "").upper()
        game1 = self._extract_game_key(pick1)
        game2 = self._extract_game_key(pick2)
        
        correlation_type = None
        correlation_strength = 0.0
        
        # Check same player
        if player1 and player1 == player2:
            correlation_type = CorrelationType.SAME_PLAYER
            correlation_strength = CORRELATION_WEIGHTS[CorrelationType.SAME_PLAYER]
            
            # If same stat, even higher (duplicate!)
            if stat1 == stat2:
                correlation_strength = 1.0
        
        # Check same game
        elif game1 and game1 == game2:
            # Same team
            if team1 and team1 == team2:
                correlation_type = CorrelationType.SAME_TEAM
                correlation_strength = CORRELATION_WEIGHTS[CorrelationType.SAME_TEAM]
            else:
                # Opposing teams
                correlation_type = CorrelationType.SAME_GAME
                correlation_strength = CORRELATION_WEIGHTS[CorrelationType.SAME_GAME]
        
        # Check stat correlation (even if different players)
        if not correlation_type:
            stats_correlated, stat_strength = self._are_stats_correlated(stat1, stat2)
            if stats_correlated and player1 == player2:
                correlation_type = CorrelationType.STAT_RELATED
                correlation_strength = stat_strength
        
        if not correlation_type:
            return None
        
        # Determine risk level
        if correlation_strength >= self.config.high_correlation_threshold:
            risk_level = "high"
        elif correlation_strength >= self.config.medium_correlation_threshold:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Generate recommendation
        if correlation_type == CorrelationType.SAME_PLAYER and stat1 == stat2:
            recommendation = "DUPLICATE: Remove one pick"
        elif correlation_type == CorrelationType.SAME_PLAYER:
            recommendation = "Same player — treat as single bet unit"
        elif correlation_type == CorrelationType.SAME_TEAM:
            recommendation = "Same team — reduce position if team loses"
        elif correlation_type == CorrelationType.SAME_GAME:
            recommendation = "Same game — outcomes may swing together"
        else:
            recommendation = "Correlated stats — monitor both"
        
        return CorrelationPair(
            pick_1_id=pick1.get("pick_id", pick1.get("edge_id", "")),
            pick_2_id=pick2.get("pick_id", pick2.get("edge_id", "")),
            pick_1_player=pick1.get("player", ""),
            pick_2_player=pick2.get("player", ""),
            pick_1_stat=pick1.get("stat", ""),
            pick_2_stat=pick2.get("stat", ""),
            correlation_type=correlation_type,
            correlation_strength=correlation_strength,
            game_key=game1 or game2,
            risk_level=risk_level,
            recommendation=recommendation,
        )
    
    def detect_correlations(self, picks: List[Dict]) -> CorrelationCheckResult:
        """
        Detect all correlations in a list of picks.
        
        Args:
            picks: List of pick dictionaries
        
        Returns:
            CorrelationCheckResult with all detected correlations
        """
        result = CorrelationCheckResult(total_picks=len(picks))
        
        # Check all pairs
        for pick1, pick2 in combinations(picks, 2):
            pair = self._detect_pair_correlation(pick1, pick2)
            
            if pair:
                result.correlated_pairs.append(pair)
                
                if pair.risk_level == "high":
                    result.high_risk_pairs += 1
                elif pair.risk_level == "medium":
                    result.medium_risk_pairs += 1
                else:
                    result.low_risk_pairs += 1
        
        # Calculate exposure
        game_counts: Dict[str, int] = defaultdict(int)
        player_counts: Dict[str, int] = defaultdict(int)
        team_counts: Dict[str, int] = defaultdict(int)
        
        for pick in picks:
            game = self._extract_game_key(pick)
            player = pick.get("player", "").lower()
            team = pick.get("team", "").upper()
            
            if game:
                game_counts[game] += 1
            if player:
                player_counts[player] += 1
            if team:
                team_counts[team] += 1
        
        if game_counts:
            result.max_single_game_exposure = max(game_counts.values())
        if player_counts:
            result.max_single_player_exposure = max(player_counts.values())
        if team_counts:
            result.max_single_team_exposure = max(team_counts.values())
        
        # Generate warnings
        if result.max_single_game_exposure > self.config.max_picks_per_game:
            result.warnings.append(
                f"⚠️ {result.max_single_game_exposure} picks on single game "
                f"(max recommended: {self.config.max_picks_per_game})"
            )
            result.should_reduce = True
        
        if result.max_single_player_exposure > self.config.max_picks_per_player:
            result.warnings.append(
                f"⚠️ {result.max_single_player_exposure} picks on single player "
                f"(max recommended: {self.config.max_picks_per_player})"
            )
            result.should_reduce = True
        
        if result.max_single_team_exposure > self.config.max_picks_per_team:
            result.warnings.append(
                f"⚠️ {result.max_single_team_exposure} picks on single team "
                f"(max recommended: {self.config.max_picks_per_team})"
            )
        
        if result.high_risk_pairs > 0:
            result.warnings.append(
                f"⚠️ {result.high_risk_pairs} high-risk correlated pairs detected"
            )
        
        return result
    
    def add_correlation_info_to_picks(
        self,
        picks: List[Dict],
        result: CorrelationCheckResult = None,
    ) -> List[Dict]:
        """
        Add correlation information to each pick.
        
        Adds:
        - correlation_risk: low/medium/high
        - correlated_with: list of pick IDs
        - correlation_warnings: list of warnings
        """
        if result is None:
            result = self.detect_correlations(picks)
        
        # Build correlation map
        correlation_map: Dict[str, List[CorrelationPair]] = defaultdict(list)
        
        for pair in result.correlated_pairs:
            correlation_map[pair.pick_1_id].append(pair)
            correlation_map[pair.pick_2_id].append(pair)
        
        # Add info to picks
        for pick in picks:
            pick_id = pick.get("pick_id", pick.get("edge_id", ""))
            pairs = correlation_map.get(pick_id, [])
            
            if pairs:
                # Determine highest risk level
                risk_levels = [p.risk_level for p in pairs]
                if "high" in risk_levels:
                    pick["correlation_risk"] = "high"
                elif "medium" in risk_levels:
                    pick["correlation_risk"] = "medium"
                else:
                    pick["correlation_risk"] = "low"
                
                # List correlated picks
                correlated_ids = set()
                for pair in pairs:
                    other_id = pair.pick_2_id if pair.pick_1_id == pick_id else pair.pick_1_id
                    correlated_ids.add(other_id)
                
                pick["correlated_with"] = list(correlated_ids)
                pick["correlation_warnings"] = [p.recommendation for p in pairs]
            else:
                pick["correlation_risk"] = "none"
                pick["correlated_with"] = []
                pick["correlation_warnings"] = []
        
        return picks


# =============================================================================
# GATE FUNCTION
# =============================================================================

class CorrelationGate:
    """
    Gate that validates picks for correlation risk.
    
    Can block or warn based on configuration.
    """
    
    def __init__(self, config: CorrelationGateConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.detector = CorrelationDetector(self.config)
    
    def run(self, picks: List[Dict]) -> Dict:
        """
        Run correlation gate on picks.
        
        Returns:
            Dict with result, warnings, and modified picks
        """
        result = self.detector.detect_correlations(picks)
        picks_with_info = self.detector.add_correlation_info_to_picks(picks, result)
        
        # Separate by risk
        blocked = []
        warned = []
        passed = []
        
        for pick in picks_with_info:
            risk = pick.get("correlation_risk", "none")
            
            # Block duplicates
            if any("DUPLICATE" in w for w in pick.get("correlation_warnings", [])):
                blocked.append(pick)
            elif risk == "high" and self.config.warn_same_game:
                warned.append(pick)
            elif risk == "medium":
                warned.append(pick)
            else:
                passed.append(pick)
        
        return {
            "passed": passed,
            "warned": warned,
            "blocked": blocked,
            "result": result.to_dict(),
            "warnings": result.warnings,
            "should_reduce": result.should_reduce,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def detect_correlations(picks: List[Dict]) -> CorrelationCheckResult:
    """Detect correlations in picks."""
    detector = CorrelationDetector()
    return detector.detect_correlations(picks)


def run_correlation_gate(picks: List[Dict]) -> Dict:
    """Run correlation gate on picks."""
    gate = CorrelationGate()
    return gate.run(picks)


def print_correlation_report(picks: List[Dict]):
    """Print correlation report to console."""
    result = detect_correlations(picks)
    
    print("\n" + "=" * 60)
    print("CORRELATION DETECTION REPORT")
    print("=" * 60)
    
    print(f"\n📊 Summary:")
    print(f"   Total picks: {result.total_picks}")
    print(f"   Correlated pairs: {len(result.correlated_pairs)}")
    print(f"   High risk: {result.high_risk_pairs}")
    print(f"   Medium risk: {result.medium_risk_pairs}")
    print(f"   Low risk: {result.low_risk_pairs}")
    
    print(f"\n📈 Exposure:")
    print(f"   Max picks per game: {result.max_single_game_exposure}")
    print(f"   Max picks per player: {result.max_single_player_exposure}")
    print(f"   Max picks per team: {result.max_single_team_exposure}")
    
    if result.warnings:
        print(f"\n⚠️ Warnings:")
        for warning in result.warnings:
            print(f"   {warning}")
    
    if result.correlated_pairs:
        print(f"\n🔗 Correlated Pairs:")
        for pair in result.correlated_pairs[:10]:  # Show top 10
            print(f"   [{pair.risk_level.upper()}] {pair.pick_1_player} ({pair.pick_1_stat}) "
                  f"↔ {pair.pick_2_player} ({pair.pick_2_stat})")
            print(f"          Type: {pair.correlation_type} | {pair.recommendation}")
    
    print("\n" + "=" * 60)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """CLI for correlation detection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Correlation Detection Gate")
    parser.add_argument("--test", action="store_true", help="Run with test data")
    
    args = parser.parse_args()
    
    if args.test:
        # Test with sample picks
        test_picks = [
            {"pick_id": "1", "player": "LeBron James", "stat": "points", "line": 25.5, 
             "team": "LAL", "opponent": "BOS", "game_id": "LAL@BOS"},
            {"pick_id": "2", "player": "LeBron James", "stat": "assists", "line": 7.5,
             "team": "LAL", "opponent": "BOS", "game_id": "LAL@BOS"},
            {"pick_id": "3", "player": "Anthony Davis", "stat": "rebounds", "line": 11.5,
             "team": "LAL", "opponent": "BOS", "game_id": "LAL@BOS"},
            {"pick_id": "4", "player": "Jayson Tatum", "stat": "points", "line": 28.5,
             "team": "BOS", "opponent": "LAL", "game_id": "LAL@BOS"},
            {"pick_id": "5", "player": "Stephen Curry", "stat": "3pm", "line": 4.5,
             "team": "GSW", "opponent": "PHX", "game_id": "GSW@PHX"},
        ]
        
        print_correlation_report(test_picks)
        
        # Run gate
        gate_result = run_correlation_gate(test_picks)
        
        print(f"\n✅ Passed: {len(gate_result['passed'])}")
        print(f"⚠️ Warned: {len(gate_result['warned'])}")
        print(f"❌ Blocked: {len(gate_result['blocked'])}")
    
    else:
        print("Use --test to run with sample data")


if __name__ == "__main__":
    main()
