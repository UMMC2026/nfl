"""
NBA Role & Scheme Normalization Layer
======================================
Adjusts probability parameters BEFORE Monte Carlo simulation based on:
- Player archetype (7 types: PRIMARY_USAGE_SCORER → BENCH_MICROWAVE)
- Coach rotation style (TIGHT, MODERATE, LOOSE)
- Blowout risk (spread-based)
- Confidence governance (6 automatic penalties)

Author: UNDERDOG ANALYSIS
Version: 1.0
"""

import json
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class PlayerArchetype(Enum):
    """7 player archetypes with distinct volatility profiles."""
    PRIMARY_USAGE_SCORER = "PRIMARY_USAGE_SCORER"  # Luka, Giannis, SGA
    SECONDARY_CREATOR = "SECONDARY_CREATOR"  # Kyrie, Jaylen Brown
    CONNECTOR_STARTER = "CONNECTOR_STARTER"  # Jrue Holiday, Mikal Bridges
    STRETCH_BIG = "STRETCH_BIG"  # Brook Lopez, KAT
    RIM_RUNNER = "RIM_RUNNER"  # Capela, Hartenstein
    DEFENSIVE_SPECIALIST = "DEFENSIVE_SPECIALIST"  # Herb Jones, Alex Caruso
    BENCH_MICROWAVE = "BENCH_MICROWAVE"  # Jordan Clarkson, Immanuel Quickley


class RotationStyle(Enum):
    """Coach rotation philosophy."""
    TIGHT = "TIGHT"  # 7-8 man rotation (Thibs, Spo)
    MODERATE = "MODERATE"  # 9-10 man rotation (most coaches)
    LOOSE = "LOOSE"  # 10-11+ man rotation (Pop, Kerr)


class BlowoutBehavior(Enum):
    """How coach handles blowouts."""
    EARLY = "EARLY"  # Pulls starters at 15+ point lead
    STANDARD = "STANDARD"  # Pulls at 20+ point lead
    LATE = "LATE"  # Keeps starters in until 25+ point lead


class VolatilityLevel(Enum):
    """Usage/role volatility levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MinutesElasticity(Enum):
    """How minutes fluctuate game-to-game."""
    FIXED = "FIXED"  # ±2 minutes
    MODERATE = "MODERATE"  # ±5 minutes
    ELASTIC = "ELASTIC"  # ±10 minutes


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ArchetypeProfile:
    """Complete archetype definition."""
    archetype: PlayerArchetype
    usage_mean: float  # Expected usage rate
    volatility: VolatilityLevel
    elasticity: MinutesElasticity
    blowout_sensitivity: float  # 0.0-1.0 (how much blowouts affect them)
    bench_risk: float  # 0.0-1.0 (probability of DNP-CD or garbage time only)
    distribution_hint: str  # "NORMAL", "NEGATIVE_BINOMIAL", "POISSON"
    confidence_cap: float  # Max confidence percentage (62%-72%)


@dataclass
class CoachProfile:
    """Coach behavioral model."""
    coach_name: str
    team: str
    rotation_style: RotationStyle
    blowout_behavior: BlowoutBehavior
    variance_multiplier: float  # Applied to minutes variance


@dataclass
class RoleNormalizationResult:
    """Output of normalization process."""
    player_name: str
    archetype: PlayerArchetype
    confidence_cap_adjustment: float  # Applied to base cap (e.g., -10%)
    minutes_adjustment: float  # Multiplier (0.90-1.10)
    variance_adjustment: float  # Multiplier (0.60-1.40)
    usage_adjustment: float  # Multiplier (0.95-1.05)
    flags: List[str]  # Governance warnings
    metadata: Dict  # Full audit trail


# ============================================================================
# ARCHETYPE LIBRARY
# ============================================================================

ARCHETYPE_LIBRARY: Dict[PlayerArchetype, ArchetypeProfile] = {
    PlayerArchetype.PRIMARY_USAGE_SCORER: ArchetypeProfile(
        archetype=PlayerArchetype.PRIMARY_USAGE_SCORER,
        usage_mean=32.0,
        volatility=VolatilityLevel.HIGH,
        elasticity=MinutesElasticity.MODERATE,
        blowout_sensitivity=0.70,
        bench_risk=0.05,
        distribution_hint="NORMAL",
        confidence_cap=0.72
    ),
    PlayerArchetype.SECONDARY_CREATOR: ArchetypeProfile(
        archetype=PlayerArchetype.SECONDARY_CREATOR,
        usage_mean=24.0,
        volatility=VolatilityLevel.MEDIUM,
        elasticity=MinutesElasticity.MODERATE,
        blowout_sensitivity=0.65,
        bench_risk=0.08,
        distribution_hint="NORMAL",
        confidence_cap=0.70
    ),
    PlayerArchetype.CONNECTOR_STARTER: ArchetypeProfile(
        archetype=PlayerArchetype.CONNECTOR_STARTER,
        usage_mean=18.0,
        volatility=VolatilityLevel.LOW,
        elasticity=MinutesElasticity.FIXED,
        blowout_sensitivity=0.50,
        bench_risk=0.05,
        distribution_hint="NORMAL",
        confidence_cap=0.68
    ),
    PlayerArchetype.STRETCH_BIG: ArchetypeProfile(
        archetype=PlayerArchetype.STRETCH_BIG,
        usage_mean=20.0,
        volatility=VolatilityLevel.MEDIUM,
        elasticity=MinutesElasticity.MODERATE,
        blowout_sensitivity=0.60,
        bench_risk=0.10,
        distribution_hint="NEGATIVE_BINOMIAL",
        confidence_cap=0.68
    ),
    PlayerArchetype.RIM_RUNNER: ArchetypeProfile(
        archetype=PlayerArchetype.RIM_RUNNER,
        usage_mean=14.0,
        volatility=VolatilityLevel.LOW,
        elasticity=MinutesElasticity.MODERATE,
        blowout_sensitivity=0.55,
        bench_risk=0.12,
        distribution_hint="POISSON",
        confidence_cap=0.66
    ),
    PlayerArchetype.DEFENSIVE_SPECIALIST: ArchetypeProfile(
        archetype=PlayerArchetype.DEFENSIVE_SPECIALIST,
        usage_mean=12.0,
        volatility=VolatilityLevel.LOW,
        elasticity=MinutesElasticity.FIXED,
        blowout_sensitivity=0.40,
        bench_risk=0.15,
        distribution_hint="POISSON",
        confidence_cap=0.65
    ),
    PlayerArchetype.BENCH_MICROWAVE: ArchetypeProfile(
        archetype=PlayerArchetype.BENCH_MICROWAVE,
        usage_mean=22.0,
        volatility=VolatilityLevel.HIGH,
        elasticity=MinutesElasticity.ELASTIC,
        blowout_sensitivity=0.80,
        bench_risk=0.25,
        distribution_hint="NORMAL",
        confidence_cap=0.62
    )
}


# ============================================================================
# CORE NORMALIZER
# ============================================================================

class RoleSchemeNormalizer:
    """
    NBA Role & Scheme Normalization Engine
    
    Workflow:
    1. Classify player archetype (heuristic or manual override)
    2. Load coach profile
    3. Calculate parameter adjustments (minutes, variance, usage)
    4. Apply confidence governance (6 automatic penalties)
    5. Return RoleNormalizationResult
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self.role_mapping = self._load_role_mapping()
        self.coach_profiles = self._load_coach_profiles()
    
    def _load_role_mapping(self) -> Dict[str, str]:
        """Load manual player → archetype overrides."""
        mapping_file = self.config_dir / "nba_role_mapping.json"
        if mapping_file.exists():
            with open(mapping_file, 'r') as f:
                data = json.load(f)
                return data.get("players", {})
        return {}
    
    def _load_coach_profiles(self) -> Dict[str, CoachProfile]:
        """Load coach behavioral profiles."""
        # Default profiles (can be overridden by YAML)
        return {
            "DEFAULT": CoachProfile(
                coach_name="DEFAULT",
                team="GENERIC",
                rotation_style=RotationStyle.MODERATE,
                blowout_behavior=BlowoutBehavior.STANDARD,
                variance_multiplier=1.0
            )
        }
    
    def _classify_archetype(
        self,
        player_name: str,
        minutes_l10_avg: float,
        usage_rate_l10: float
    ) -> PlayerArchetype:
        """
        Classify player archetype using heuristic or manual override.
        
        Heuristic rules:
        - PRIMARY_USAGE_SCORER: usage ≥28%, minutes ≥32
        - SECONDARY_CREATOR: usage 22-28%, minutes ≥28
        - CONNECTOR_STARTER: usage 15-22%, minutes ≥28
        - STRETCH_BIG: usage 18-25%, minutes 20-30 (position=C/PF assumed)
        - RIM_RUNNER: usage <18%, minutes 18-28 (position=C assumed)
        - DEFENSIVE_SPECIALIST: usage <15%, minutes 24-30
        - BENCH_MICROWAVE: usage ≥20%, minutes <28
        """
        # Check manual override
        if player_name in self.role_mapping:
            return PlayerArchetype(self.role_mapping[player_name])
        
        # Heuristic classification
        if usage_rate_l10 >= 28.0 and minutes_l10_avg >= 32.0:
            return PlayerArchetype.PRIMARY_USAGE_SCORER
        elif 22.0 <= usage_rate_l10 < 28.0 and minutes_l10_avg >= 28.0:
            return PlayerArchetype.SECONDARY_CREATOR
        elif 15.0 <= usage_rate_l10 < 22.0 and minutes_l10_avg >= 28.0:
            return PlayerArchetype.CONNECTOR_STARTER
        elif usage_rate_l10 < 18.0 and 18.0 <= minutes_l10_avg < 28.0:
            return PlayerArchetype.RIM_RUNNER
        elif usage_rate_l10 < 15.0 and 24.0 <= minutes_l10_avg < 30.0:
            return PlayerArchetype.DEFENSIVE_SPECIALIST
        elif usage_rate_l10 >= 20.0 and minutes_l10_avg < 28.0:
            return PlayerArchetype.BENCH_MICROWAVE
        else:
            # Default to CONNECTOR_STARTER for edge cases
            return PlayerArchetype.CONNECTOR_STARTER
    
    def _get_coach_profile(self, team: str) -> CoachProfile:
        """Get coach profile for team."""
        return self.coach_profiles.get(team, self.coach_profiles["DEFAULT"])
    
    def _calculate_minutes_adjustment(
        self,
        archetype_profile: ArchetypeProfile,
        coach_profile: CoachProfile,
        game_context: Optional[Dict] = None
    ) -> float:
        """
        Calculate minutes parameter adjustment (multiplier).
        
        Range: 0.90-1.10
        - TIGHT rotation: +5% minutes for starters
        - LOOSE rotation: -10% minutes for starters (more distribution)
        - Blowout risk: -5% to -10% if high spread
        """
        adjustment = 1.0
        
        # Rotation style effect
        if coach_profile.rotation_style == RotationStyle.TIGHT:
            if archetype_profile.archetype in [
                PlayerArchetype.PRIMARY_USAGE_SCORER,
                PlayerArchetype.SECONDARY_CREATOR,
                PlayerArchetype.CONNECTOR_STARTER
            ]:
                adjustment += 0.05
        elif coach_profile.rotation_style == RotationStyle.LOOSE:
            if archetype_profile.archetype in [
                PlayerArchetype.PRIMARY_USAGE_SCORER,
                PlayerArchetype.SECONDARY_CREATOR
            ]:
                adjustment -= 0.05
            else:
                adjustment -= 0.10
        
        # Blowout risk adjustment
        if game_context:
            spread = abs(game_context.get("spread", 0.0))
            if spread >= 10.0:
                blowout_factor = archetype_profile.blowout_sensitivity
                adjustment -= 0.05 * blowout_factor
        
        # Clamp to safe range
        return max(0.90, min(1.10, adjustment))
    
    def _calculate_variance_adjustment(
        self,
        archetype_profile: ArchetypeProfile,
        coach_profile: CoachProfile
    ) -> float:
        """
        Calculate variance parameter adjustment (multiplier).
        
        Range: 0.60-1.40
        - ELASTIC minutes: +40% variance
        - LOOSE rotation: +30% variance
        - FIXED minutes + TIGHT rotation: -40% variance
        """
        adjustment = 1.0
        
        # Elasticity effect
        if archetype_profile.elasticity == MinutesElasticity.ELASTIC:
            adjustment += 0.40
        elif archetype_profile.elasticity == MinutesElasticity.FIXED:
            adjustment -= 0.20
        
        # Rotation style effect
        if coach_profile.rotation_style == RotationStyle.LOOSE:
            adjustment += 0.30
        elif coach_profile.rotation_style == RotationStyle.TIGHT:
            adjustment -= 0.20
        
        # Coach variance multiplier
        adjustment *= coach_profile.variance_multiplier
        
        # Clamp to safe range
        return max(0.60, min(1.40, adjustment))
    
    def _calculate_usage_adjustment(
        self,
        archetype_profile: ArchetypeProfile,
        game_context: Optional[Dict] = None
    ) -> float:
        """
        Calculate usage parameter adjustment (multiplier).
        
        Range: 0.95-1.05
        - Blowout games: -5% usage for high-volatility scorers
        """
        adjustment = 1.0
        
        if game_context:
            spread = abs(game_context.get("spread", 0.0))
            if spread >= 10.0 and archetype_profile.volatility == VolatilityLevel.HIGH:
                adjustment -= 0.05
        
        return max(0.95, min(1.05, adjustment))
    
    def _apply_confidence_governance(
        self,
        archetype_profile: ArchetypeProfile,
        coach_profile: CoachProfile,
        minutes_l10_std: float,
        game_context: Optional[Dict] = None
    ) -> Tuple[float, List[str]]:
        """
        Apply 6 automatic confidence penalties.
        
        Returns:
            (total_adjustment, flags)
            
        Penalties:
        1. High usage volatility: -5%
        2. Blowout game risk: -5%
        3. High minutes variance (L10 std > 8): -5%
        4. Loose rotation: -8%
        5. High bench risk (>20%): -3%
        6. Game script uncertainty (back-to-back): -3%
        """
        adjustment = 0.0
        flags = []
        
        # 1. Usage volatility
        if archetype_profile.volatility == VolatilityLevel.HIGH:
            adjustment -= 5.0
            flags.append("HIGH_USAGE_VOLATILITY")
        
        # 2. Blowout risk
        if game_context:
            spread = abs(game_context.get("spread", 0.0))
            if spread >= 10.0 and archetype_profile.blowout_sensitivity >= 0.60:
                adjustment -= 5.0
                flags.append("BLOWOUT_GAME_RISK")
        
        # 3. Minutes variance
        if minutes_l10_std > 8.0:
            adjustment -= 5.0
            flags.append("HIGH_MINUTES_VARIANCE")
        
        # 4. Loose rotation
        if coach_profile.rotation_style == RotationStyle.LOOSE:
            adjustment -= 8.0
            flags.append("LOOSE_ROTATION")
        
        # 5. Bench risk
        if archetype_profile.bench_risk > 0.20:
            adjustment -= 3.0
            flags.append("HIGH_BENCH_RISK")
        
        # 6. Game script (back-to-back check)
        if game_context and game_context.get("is_back_to_back", False):
            adjustment -= 3.0
            flags.append("BACK_TO_BACK_GAME")
        
        return (adjustment, flags)
    
    def normalize(
        self,
        player_name: str,
        team: str,
        opponent: str,
        minutes_l10_avg: float,
        minutes_l10_std: float,
        usage_rate_l10: float,
        game_context: Optional[Dict] = None
    ) -> RoleNormalizationResult:
        """
        Main normalization entry point.
        
        Args:
            player_name: Player full name
            team: Team abbreviation
            opponent: Opponent abbreviation
            minutes_l10_avg: L10 minutes average
            minutes_l10_std: L10 minutes standard deviation
            usage_rate_l10: L10 usage rate
            game_context: Optional dict with {spread, is_back_to_back, ...}
        
        Returns:
            RoleNormalizationResult with all adjustments
        """
        # Step 1: Classify archetype
        archetype = self._classify_archetype(player_name, minutes_l10_avg, usage_rate_l10)
        archetype_profile = ARCHETYPE_LIBRARY[archetype]
        
        # Step 2: Get coach profile
        coach_profile = self._get_coach_profile(team)
        
        # Step 3: Calculate parameter adjustments
        minutes_adj = self._calculate_minutes_adjustment(
            archetype_profile, coach_profile, game_context
        )
        variance_adj = self._calculate_variance_adjustment(
            archetype_profile, coach_profile
        )
        usage_adj = self._calculate_usage_adjustment(
            archetype_profile, game_context
        )
        
        # Step 4: Apply confidence governance
        confidence_cap_adj, flags = self._apply_confidence_governance(
            archetype_profile, coach_profile, minutes_l10_std, game_context
        )
        
        # Step 5: Build metadata
        metadata = {
            "archetype": archetype.value,
            "archetype_base_cap": archetype_profile.confidence_cap,
            "coach_rotation_style": coach_profile.rotation_style.value,
            "blowout_behavior": coach_profile.blowout_behavior.value,
            "volatility": archetype_profile.volatility.value,
            "elasticity": archetype_profile.elasticity.value,
            "blowout_sensitivity": archetype_profile.blowout_sensitivity,
            "bench_risk": archetype_profile.bench_risk,
            "game_context": game_context or {}
        }
        
        return RoleNormalizationResult(
            player_name=player_name,
            archetype=archetype,
            confidence_cap_adjustment=confidence_cap_adj,
            minutes_adjustment=minutes_adj,
            variance_adjustment=variance_adj,
            usage_adjustment=usage_adj,
            flags=flags,
            metadata=metadata
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_normalization_report(result: RoleNormalizationResult) -> str:
    """
    Format normalization result for client reports.
    
    Example:
        Jordan Clarkson (BENCH_MICROWAVE)
        • Confidence Cap: 62% → 47% (-15% from volatility flags)
        • Flags: HIGH_USAGE_VOLATILITY, BLOWOUT_GAME_RISK, LOOSE_ROTATION
        • Minutes Adjustment: -10% (loose rotation)
    """
    lines = [
        f"{result.player_name} ({result.archetype.value})",
        f"• Confidence Cap Adjustment: {result.confidence_cap_adjustment:+.0f}%",
        f"• Flags: {', '.join(result.flags) if result.flags else 'None'}",
        f"• Minutes Adjustment: {(result.minutes_adjustment - 1.0) * 100:+.0f}%",
        f"• Variance Adjustment: {(result.variance_adjustment - 1.0) * 100:+.0f}%"
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    normalizer = RoleSchemeNormalizer()
    
    result = normalizer.normalize(
        player_name="Jordan Clarkson",
        team="UTA",
        opponent="LAL",
        minutes_l10_avg=24.5,
        minutes_l10_std=9.2,
        usage_rate_l10=26.8,
        game_context={"spread": 12.0, "is_back_to_back": False}
    )
    
    print(format_normalization_report(result))
