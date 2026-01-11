"""
Correlation Tagging Module

Identifies correlated props that should not be stacked in parlays.
Uses badge system: 🔗 (highly correlated), ⚠️ (moderately correlated), ❌ (avoid stacking)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import itertools


class CorrelationLevel(Enum):
    """Correlation strength between two props."""
    HIGH = "🔗"        # Highly correlated - moves together
    MODERATE = "⚠️"    # Moderately correlated - some dependency
    NONE = ""          # No significant correlation
    NEGATIVE = "↔️"    # Negatively correlated - could hedge


@dataclass
class CorrelationTag:
    """Tag describing correlation between two props."""
    player1: str
    stat1: str
    player2: str
    stat2: str
    level: CorrelationLevel
    reason: str
    parlay_penalty: float  # % to reduce combined probability


class CorrelationTagger:
    """
    Identifies and tags correlations between props.
    
    Correlation types:
    1. Same player different stats (pts + PRA are highly correlated)
    2. Same team props (team scoring correlates)
    3. Opposing player props (if one team runs away, both affected)
    4. Position-based (two centers competing for rebounds)
    """
    
    # Known high correlations (same player)
    SAME_PLAYER_CORRELATIONS = {
        ("points", "pts+reb+ast"): (CorrelationLevel.HIGH, 0.15),
        ("rebounds", "pts+reb+ast"): (CorrelationLevel.HIGH, 0.12),
        ("assists", "pts+reb+ast"): (CorrelationLevel.HIGH, 0.12),
        ("points", "pts+reb"): (CorrelationLevel.HIGH, 0.12),
        ("rebounds", "pts+reb"): (CorrelationLevel.HIGH, 0.10),
        ("points", "pts+ast"): (CorrelationLevel.HIGH, 0.12),
        ("assists", "pts+ast"): (CorrelationLevel.HIGH, 0.10),
        ("rebounds", "reb+ast"): (CorrelationLevel.HIGH, 0.10),
        ("assists", "reb+ast"): (CorrelationLevel.HIGH, 0.10),
    }
    
    # Same team correlations
    SAME_TEAM_STAT_CORRELATIONS = {
        ("rebounds", "rebounds"): (CorrelationLevel.MODERATE, 0.05),  # Contested boards
        ("assists", "points"): (CorrelationLevel.MODERATE, 0.08),     # Assist = made shot
    }
    
    # Opposing team correlations
    OPPOSING_CORRELATIONS = {
        # If one team dominates, both suffer
        ("points", "points"): (CorrelationLevel.MODERATE, 0.05),
    }
    
    def __init__(self):
        self._correlation_cache: dict = {}
    
    def tag_correlations(self, picks: list[dict]) -> list[CorrelationTag]:
        """
        Find all correlations in a list of picks.
        
        Args:
            picks: List of pick dicts with player, team, stat, direction
            
        Returns:
            List of CorrelationTag objects
        """
        tags = []
        
        # Check all pairs
        for i, p1 in enumerate(picks):
            for p2 in picks[i+1:]:
                tag = self._check_correlation(p1, p2)
                if tag and tag.level != CorrelationLevel.NONE:
                    tags.append(tag)
        
        return tags
    
    def _check_correlation(self, p1: dict, p2: dict) -> Optional[CorrelationTag]:
        """Check correlation between two picks."""
        player1, team1, stat1 = p1.get("player"), p1.get("team"), p1.get("stat")
        player2, team2, stat2 = p2.get("player"), p2.get("team"), p2.get("stat")
        dir1, dir2 = p1.get("direction"), p2.get("direction")
        
        # Same player, different stats
        if player1 == player2 and stat1 != stat2:
            return self._check_same_player_correlation(
                player1, stat1, stat2, team1, dir1, dir2
            )
        
        # Same team, different players
        if team1 == team2 and player1 != player2:
            return self._check_same_team_correlation(
                player1, stat1, dir1, player2, stat2, dir2, team1
            )
        
        # Opposing teams
        # Note: We'd need opponent info to check this properly
        
        return None
    
    def _check_same_player_correlation(
        self, player: str, stat1: str, stat2: str, team: str, dir1: str, dir2: str
    ) -> CorrelationTag:
        """Check correlation for same player different stats."""
        
        # Normalize stat order for lookup
        key = tuple(sorted([stat1, stat2]))
        
        if key in self.SAME_PLAYER_CORRELATIONS:
            level, penalty = self.SAME_PLAYER_CORRELATIONS[key]
            
            # Same direction = positively correlated
            if dir1 == dir2:
                reason = f"{player}: {stat1} & {stat2} move together"
            else:
                # Opposite directions might hedge
                level = CorrelationLevel.NEGATIVE
                penalty = -0.02  # Slight boost for natural hedge
                reason = f"{player}: {stat1} & {stat2} hedge each other"
            
            return CorrelationTag(
                player1=player, stat1=stat1,
                player2=player, stat2=stat2,
                level=level, reason=reason, parlay_penalty=penalty
            )
        
        return CorrelationTag(
            player1=player, stat1=stat1,
            player2=player, stat2=stat2,
            level=CorrelationLevel.NONE, reason="", parlay_penalty=0.0
        )
    
    def _check_same_team_correlation(
        self, player1: str, stat1: str, dir1: str,
        player2: str, stat2: str, dir2: str, team: str
    ) -> Optional[CorrelationTag]:
        """Check correlation for same team different players."""
        
        # Assists + teammate points (positive correlation)
        if stat1 == "assists" and stat2 == "points":
            if dir1 == "higher" and dir2 == "higher":
                return CorrelationTag(
                    player1=player1, stat1=stat1,
                    player2=player2, stat2=stat2,
                    level=CorrelationLevel.MODERATE,
                    reason=f"{player1} assists → {player2} points",
                    parlay_penalty=0.05
                )
        
        # Two rebounders on same team (slight negative)
        if stat1 == "rebounds" and stat2 == "rebounds":
            if dir1 == "higher" and dir2 == "higher":
                return CorrelationTag(
                    player1=player1, stat1=stat1,
                    player2=player2, stat2=stat2,
                    level=CorrelationLevel.MODERATE,
                    reason=f"{player1} & {player2} compete for boards",
                    parlay_penalty=0.04
                )
        
        return None
    
    def get_parlay_penalty(self, parlay_picks: list[dict]) -> tuple[float, list[str]]:
        """
        Calculate total correlation penalty for a parlay.
        
        Returns:
            (total_penalty, list of warning messages)
        """
        tags = self.tag_correlations(parlay_picks)
        
        total_penalty = 0.0
        warnings = []
        
        for tag in tags:
            if tag.level in [CorrelationLevel.HIGH, CorrelationLevel.MODERATE]:
                total_penalty += tag.parlay_penalty
                warnings.append(f"{tag.level.value} {tag.reason}")
        
        return (total_penalty, warnings)
    
    def format_correlation_badges(self, picks: list[dict]) -> dict[str, list[str]]:
        """
        Generate correlation badges for each pick.
        
        Returns dict mapping "player|stat" to list of correlation badges.
        """
        tags = self.tag_correlations(picks)
        
        badges: dict[str, list[str]] = {}
        
        for tag in tags:
            if tag.level == CorrelationLevel.NONE:
                continue
            
            key1 = f"{tag.player1}|{tag.stat1}"
            key2 = f"{tag.player2}|{tag.stat2}"
            
            badge = f"{tag.level.value} w/{tag.player2 if tag.player1 != tag.player2 else tag.stat2}"
            
            if key1 not in badges:
                badges[key1] = []
            badges[key1].append(badge)
            
            if key1 != key2:
                badge2 = f"{tag.level.value} w/{tag.player1 if tag.player1 != tag.player2 else tag.stat1}"
                if key2 not in badges:
                    badges[key2] = []
                badges[key2].append(badge2)
        
        return badges


def check_parlay_correlations(parlay: list[dict]) -> tuple[float, list[str]]:
    """
    Convenience function to check correlations in a parlay.
    
    Returns (penalty_multiplier, warning_messages)
    """
    tagger = CorrelationTagger()
    penalty, warnings = tagger.get_parlay_penalty(parlay)
    return (1.0 - penalty, warnings)


# Test
if __name__ == "__main__":
    tagger = CorrelationTagger()
    
    # Test picks
    picks = [
        {"player": "OG Anunoby", "team": "NYK", "stat": "points", "direction": "higher"},
        {"player": "OG Anunoby", "team": "NYK", "stat": "pts+reb+ast", "direction": "higher"},
        {"player": "Jordan Clarkson", "team": "UTA", "stat": "points", "direction": "higher"},
        {"player": "Chet Holmgren", "team": "OKC", "stat": "rebounds", "direction": "lower"},
        {"player": "Jalen Williams", "team": "OKC", "stat": "assists", "direction": "lower"},
    ]
    
    # Check correlations
    tags = tagger.tag_correlations(picks)
    
    print("Correlation Tags Found:")
    print("-" * 60)
    for tag in tags:
        if tag.level != CorrelationLevel.NONE:
            print(f"  {tag.level.value} {tag.reason}")
            print(f"     Penalty: -{tag.parlay_penalty:.0%}")
    
    print("\n" + "=" * 60)
    print("Parlay Analysis:")
    print("=" * 60)
    
    # Full parlay check
    penalty, warnings = tagger.get_parlay_penalty(picks)
    print(f"  Total penalty: -{penalty:.0%}")
    print(f"  Warnings: {warnings}")
    
    # Badge format
    print("\n" + "=" * 60)
    print("Badges by Pick:")
    print("=" * 60)
    badges = tagger.format_correlation_badges(picks)
    for key, badge_list in badges.items():
        print(f"  {key}: {', '.join(badge_list)}")
