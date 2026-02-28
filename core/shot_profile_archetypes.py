"""
Shot Profile Archetypes — 3PM-Specific Role Intelligence
=========================================================

Modern NBA 3PM analysis requires a SECOND archetype axis beyond usage/minutes.
This module provides shot-diet classification specifically for three-point props.

SHOT PROFILE ARCHETYPES (for 3PM):
    1. CATCH_AND_SHOOT_SPECIALIST  — Elite 3PM role, 70%+ C&S, tight variance
    2. VOLUME_OFF_BALL_SHOOTER     — High 3PA, mix of relocation + secondary
    3. PRIMARY_CREATOR_3PT_OVERLAY — Pull-up 3s, high σ, volatile
    4. CORNER_ONLY_ROLE_PLAYER     — Low volume, high efficiency, fragile

CONFIDENCE CEILINGS BY 3PM ARCHETYPE:
    | Shot Archetype              | Max Conf |
    |-----------------------------|----------|
    | CATCH_AND_SHOOT_SPECIALIST  | 70%      |
    | VOLUME_OFF_BALL_SHOOTER     | 65%      |
    | PRIMARY_CREATOR_3PT_OVERLAY | 58%      |
    | CORNER_ONLY_ROLE_PLAYER     | 55%      |
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SHOT PROFILE ARCHETYPES
# =============================================================================

class ShotProfileArchetype(Enum):
    """
    3PM-specific archetype classification.
    
    This is a SECOND axis that works alongside role archetypes
    (PRIMARY_USAGE_SCORER, BENCH_MICROWAVE, etc.)
    """
    CATCH_AND_SHOOT_SPECIALIST = "CATCH_AND_SHOOT_SPECIALIST"
    VOLUME_OFF_BALL_SHOOTER = "VOLUME_OFF_BALL_SHOOTER"
    PRIMARY_CREATOR_3PT_OVERLAY = "PRIMARY_CREATOR_3PT_OVERLAY"
    CORNER_ONLY_ROLE_PLAYER = "CORNER_ONLY_ROLE_PLAYER"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# CONFIDENCE CEILINGS BY 3PM ARCHETYPE
# =============================================================================

SHOT_PROFILE_CONFIDENCE_CEILINGS = {
    ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST: 70.0,
    ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER: 65.0,
    ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY: 58.0,
    ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER: 55.0,
    ShotProfileArchetype.UNKNOWN: 60.0,  # Conservative default
}


# =============================================================================
# PLAYER DATABASE — Known 3PM Shot Profiles
# =============================================================================

# This maps player names to their shot profile archetype
# Format: "Player Name": ShotProfileArchetype
KNOWN_SHOT_PROFILES: Dict[str, ShotProfileArchetype] = {
    # ===== CATCH_AND_SHOOT_SPECIALIST =====
    # 70%+ of 3PA are catch-and-shoot, low dribble count, 3-5 3PM typical
    "Klay Thompson": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Luke Kennard": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Duncan Robinson": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Grayson Allen": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Buddy Hield": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Bojan Bogdanovic": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Joe Harris": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Seth Curry": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Doug McDermott": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Davis Bertans": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Max Strus": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Malik Beasley": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Patty Mills": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Corey Kispert": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Tim Hardaway Jr.": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Kevin Huerter": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Bogdan Bogdanovic": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "AJ Green": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Quentin Grimes": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    "Sam Hauser": ShotProfileArchetype.CATCH_AND_SHOOT_SPECIALIST,
    
    # ===== VOLUME_OFF_BALL_SHOOTER =====
    # High 3PA, mix of relocation + secondary actions, 2.5-4.5 3PM typical
    "Michael Porter Jr.": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Gary Trent Jr.": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Norman Powell": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "CJ McCollum": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Desmond Bane": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Khris Middleton": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Andrew Wiggins": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Miles Bridges": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Brandon Miller": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Jalen Green": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Donte DiVincenzo": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Aaron Gordon": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Mikal Bridges": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Herbert Jones": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Malik Monk": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Bobby Portis": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Coby White": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Dillon Brooks": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Josh Giddey": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    "Jabari Smith Jr.": ShotProfileArchetype.VOLUME_OFF_BALL_SHOOTER,
    
    # ===== PRIMARY_CREATOR_3PT_OVERLAY =====
    # Pull-up 3s, high σ, shot quality fluctuates, 2-4 3PM but volatile
    "Stephen Curry": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Damian Lillard": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Trae Young": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Luka Doncic": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Kyrie Irving": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "LaMelo Ball": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Tyrese Maxey": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Tyrese Haliburton": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Jamal Murray": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Anthony Edwards": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Shai Gilgeous-Alexander": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "De'Aaron Fox": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Cade Cunningham": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Devin Booker": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Kevin Durant": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Jayson Tatum": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Paul George": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Donovan Mitchell": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Jalen Brunson": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Zach LaVine": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "DeMar DeRozan": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    "Cole Anthony": ShotProfileArchetype.PRIMARY_CREATOR_3PT_OVERLAY,
    
    # ===== CORNER_ONLY_ROLE_PLAYER =====
    # Low volume, high efficiency, dependent on minutes, 1-2 3PM typical
    "Royce O'Neale": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "PJ Tucker": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Caleb Martin": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Jae Crowder": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Torrey Craig": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Bruce Brown": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Aaron Wiggins": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Dyson Daniels": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Isaac Okoro": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Terance Mann": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Josh Okogie": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Kenrich Williams": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Cason Wallace": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Amen Thompson": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Ausar Thompson": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
    "Bilal Coulibaly": ShotProfileArchetype.CORNER_ONLY_ROLE_PLAYER,
}


# =============================================================================
# SHOT PROFILE RESULT
# =============================================================================

@dataclass
class ShotProfileResult:
    """Result of shot profile classification."""
    player: str
    archetype: ShotProfileArchetype
    confidence_ceiling: float
    confidence_adjusted: bool = False
    original_confidence: Optional[float] = None
    final_confidence: Optional[float] = None
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "player": self.player,
            "shot_profile": self.archetype.value,
            "confidence_ceiling": self.confidence_ceiling,
            "confidence_adjusted": self.confidence_adjusted,
            "original_confidence": self.original_confidence,
            "final_confidence": self.final_confidence,
            "reasoning": self.reasoning,
        }


# =============================================================================
# SHOT PROFILE CLASSIFIER
# =============================================================================

class ShotProfileClassifier:
    """
    Classifies players into 3PM-specific shot profile archetypes
    and enforces confidence ceilings.
    """
    
    def __init__(
        self,
        known_profiles: Optional[Dict[str, ShotProfileArchetype]] = None,
        confidence_ceilings: Optional[Dict[ShotProfileArchetype, float]] = None,
    ):
        self.known_profiles = known_profiles or KNOWN_SHOT_PROFILES
        self.confidence_ceilings = confidence_ceilings or SHOT_PROFILE_CONFIDENCE_CEILINGS
    
    def classify(self, player: str) -> ShotProfileArchetype:
        """
        Get the shot profile archetype for a player.
        Returns UNKNOWN if not in database.
        """
        # Normalize name for lookup
        normalized = self._normalize_name(player)
        
        # Direct lookup
        if normalized in self.known_profiles:
            return self.known_profiles[normalized]
        
        # Fuzzy match
        for known_name, archetype in self.known_profiles.items():
            if self._fuzzy_match(normalized, known_name):
                return archetype
        
        return ShotProfileArchetype.UNKNOWN
    
    def get_confidence_ceiling(self, archetype: ShotProfileArchetype) -> float:
        """Get the maximum confidence allowed for an archetype."""
        return self.confidence_ceilings.get(archetype, 60.0)
    
    def apply_ceiling(
        self,
        player: str,
        confidence: float,
        stat: str = "3PM",
    ) -> ShotProfileResult:
        """
        Apply confidence ceiling based on shot profile.
        Only applies to 3PM-related stats.
        
        Args:
            player: Player name
            confidence: Current confidence (0-100 scale)
            stat: Stat type (only applies ceiling for 3PM stats)
        
        Returns:
            ShotProfileResult with potentially adjusted confidence
        """
        # Only apply to 3PM stats
        THREE_POINT_STATS = {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS", "threes", "3pm"}
        
        archetype = self.classify(player)
        ceiling = self.get_confidence_ceiling(archetype)
        
        result = ShotProfileResult(
            player=player,
            archetype=archetype,
            confidence_ceiling=ceiling,
            original_confidence=confidence,
        )
        
        if stat.upper() not in THREE_POINT_STATS and stat.lower() not in THREE_POINT_STATS:
            # Not a 3PM stat, don't apply ceiling
            result.final_confidence = confidence
            result.reasoning = f"Non-3PM stat ({stat}); ceiling not applied"
            return result
        
        # Apply ceiling
        if confidence > ceiling:
            result.confidence_adjusted = True
            result.final_confidence = ceiling
            result.reasoning = (
                f"{archetype.value} has max conf {ceiling}%; "
                f"reduced from {confidence:.1f}%"
            )
            logger.info(
                f"3PM ceiling applied: {player} ({archetype.value}) "
                f"{confidence:.1f}% → {ceiling:.1f}%"
            )
        else:
            result.final_confidence = confidence
            result.reasoning = f"{archetype.value}; within ceiling ({ceiling}%)"
        
        return result
    
    def _normalize_name(self, name: str) -> str:
        """Normalize player name for lookup."""
        # Handle common variations
        name = name.strip()
        # Handle special characters
        name = name.replace("'", "'")
        return name
    
    def _fuzzy_match(self, name1: str, name2: str) -> bool:
        """Check if two names are similar enough."""
        # Simple contains check for partial matches
        n1 = name1.lower()
        n2 = name2.lower()
        
        # Check if last name matches (most common variation)
        parts1 = n1.split()
        parts2 = n2.split()
        
        if len(parts1) >= 2 and len(parts2) >= 2:
            # Compare last names
            if parts1[-1] == parts2[-1]:
                # Check first initial
                if parts1[0][0] == parts2[0][0]:
                    return True
        
        return False


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def apply_3pm_ceilings(
    picks: List[Dict[str, Any]],
    classifier: Optional[ShotProfileClassifier] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Apply 3PM confidence ceilings to a batch of picks.
    
    Args:
        picks: List of pick dictionaries
        classifier: Optional custom classifier
    
    Returns:
        (processed_picks, stats)
    """
    if classifier is None:
        classifier = ShotProfileClassifier()
    
    stats = {
        "total": len(picks),
        "3pm_picks": 0,
        "ceilings_applied": 0,
        "by_archetype": {a.value: 0 for a in ShotProfileArchetype},
    }
    
    processed = []
    for pick in picks:
        stat = pick.get("stat", pick.get("stat_type", pick.get("market", ""))).upper()
        
        # Check if this is a 3PM stat
        THREE_POINT_STATS = {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"}
        
        if stat in THREE_POINT_STATS:
            stats["3pm_picks"] += 1
            
            player = pick.get("player", "Unknown")
            confidence = pick.get("final_probability", pick.get("probability", 0))
            
            # Handle 0-1 vs 0-100 scale
            if confidence <= 1:
                confidence *= 100
            
            result = classifier.apply_ceiling(player, confidence, stat)
            
            # Update pick with shot profile data
            pick["shot_profile"] = result.to_dict()
            pick["shot_profile_archetype"] = result.archetype.value
            
            if result.confidence_adjusted:
                stats["ceilings_applied"] += 1
                # Update the confidence in the pick
                pick["3pm_adjusted_confidence"] = result.final_confidence
                pick["3pm_ceiling_applied"] = True
            
            stats["by_archetype"][result.archetype.value] += 1
        
        processed.append(pick)
    
    logger.info(
        f"3PM ceilings: {stats['ceilings_applied']} adjusted "
        f"(of {stats['3pm_picks']} 3PM picks)"
    )
    
    return processed, stats


# =============================================================================
# ROUTING FUNCTION — Stat-specific archetype routing
# =============================================================================

def get_effective_archetype_for_stat(
    pick: Dict[str, Any],
    classifier: Optional[ShotProfileClassifier] = None,
) -> str:
    """
    Get the effective archetype to use based on the stat type.
    
    For 3PM stats: Use shot profile archetype (ignore role archetype bias)
    For other stats: Use standard role archetype
    
    This implements the routing rule:
        When stat == threes:
            - Ignore PRIMARY_USAGE_SCORER bias
            - Weight CATCH_AND_SHOOT and VOLUME_OFF_BALL higher
            - Downweight creators automatically
    """
    stat = pick.get("stat", pick.get("stat_type", pick.get("market", ""))).upper()
    THREE_POINT_STATS = {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"}
    
    if stat in THREE_POINT_STATS:
        # Use shot profile for 3PM
        if classifier is None:
            classifier = ShotProfileClassifier()
        
        player = pick.get("player", "Unknown")
        shot_profile = classifier.classify(player)
        return shot_profile.value
    else:
        # Use standard role archetype
        return pick.get("archetype", pick.get("role_layer", {}).get("archetype", "UNKNOWN"))


# =============================================================================
# GOVERNOR — 3PM Confidence Governor
# =============================================================================

class ThreePointGovernor:
    """
    3PM-specific governance layer that enforces:
    1. Shot profile classification
    2. Confidence ceilings
    3. Matchup weight adjustments
    """
    
    def __init__(self):
        self.classifier = ShotProfileClassifier()
    
    def govern(self, pick: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply full 3PM governance to a pick.
        """
        stat = pick.get("stat", pick.get("stat_type", pick.get("market", ""))).upper()
        THREE_POINT_STATS = {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"}
        
        if stat not in THREE_POINT_STATS:
            return pick
        
        player = pick.get("player", "Unknown")
        confidence = pick.get("final_probability", pick.get("probability", 0))
        
        # Handle 0-1 vs 0-100 scale
        if confidence <= 1:
            confidence *= 100
        
        # Apply shot profile
        archetype = self.classifier.classify(player)
        ceiling = self.classifier.get_confidence_ceiling(archetype)
        
        # Enforce ceiling
        governed_confidence = min(confidence, ceiling)
        
        # Add governance data
        pick["3pm_governed"] = True
        pick["shot_profile_archetype"] = archetype.value
        pick["3pm_confidence_ceiling"] = ceiling
        pick["3pm_original_confidence"] = confidence
        pick["3pm_governed_confidence"] = governed_confidence
        
        if governed_confidence < confidence:
            pick["3pm_ceiling_applied"] = True
            # Update the actual confidence used
            pick["governed_final_probability"] = governed_confidence
            logger.info(
                f"3PM Governor: {player} {archetype.value} "
                f"{confidence:.1f}% → {governed_confidence:.1f}%"
            )
        
        return pick
    
    def govern_batch(self, picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply governance to all picks."""
        return [self.govern(pick) for pick in picks]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_3pm_governance(
    picks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Main entry point for 3PM governance.
    
    Call this BEFORE the main eligibility gate for 3PM picks
    to ensure confidence ceilings are applied.
    
    Args:
        picks: List of pick dictionaries
    
    Returns:
        (governed_picks, governance_stats)
    """
    governor = ThreePointGovernor()
    governed = governor.govern_batch(picks)
    
    # Collect stats
    stats = {
        "total_picks": len(picks),
        "3pm_picks": 0,
        "ceilings_applied": 0,
        "by_archetype": {a.value: 0 for a in ShotProfileArchetype},
    }
    
    for pick in governed:
        if pick.get("3pm_governed"):
            stats["3pm_picks"] += 1
            archetype = pick.get("shot_profile_archetype", "UNKNOWN")
            stats["by_archetype"][archetype] = stats["by_archetype"].get(archetype, 0) + 1
            if pick.get("3pm_ceiling_applied"):
                stats["ceilings_applied"] += 1
    
    return governed, stats


if __name__ == "__main__":
    # Quick test
    test_picks = [
        {"player": "Klay Thompson", "stat": "3PM", "probability": 75},
        {"player": "Anthony Edwards", "stat": "3PM", "probability": 65},
        {"player": "Royce O'Neale", "stat": "3PM", "probability": 58},
        {"player": "Unknown Player", "stat": "3PM", "probability": 62},
        {"player": "LeBron James", "stat": "PTS", "probability": 72},  # Not 3PM
    ]
    
    governed, stats = run_3pm_governance(test_picks)
    
    print("\n3PM GOVERNANCE TEST")
    print("=" * 50)
    for pick in governed:
        if pick.get("3pm_governed"):
            print(f"{pick['player']}: {pick.get('shot_profile_archetype')}")
            print(f"  Original: {pick.get('3pm_original_confidence'):.1f}%")
            print(f"  Ceiling: {pick.get('3pm_confidence_ceiling'):.1f}%")
            print(f"  Final: {pick.get('3pm_governed_confidence'):.1f}%")
            print(f"  Adjusted: {pick.get('3pm_ceiling_applied', False)}")
    
    print(f"\nStats: {stats}")
