"""
Matchup Memory Integration Layer
================================

Integrates player-vs-opponent matchup data into the probability pipeline.
Respects feature flags and JIGGY isolation mode.

IMPORTANT: This module respects the feature flag `nba.matchup_memory_enabled`.
When disabled (default), no matchup adjustments are applied.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from features.nba.player_vs_opponent import (
    PlayerVsOpponentStats, MatchupIndex, compute_matchup_adjustment as compute_adjustment
)
from features.nba.matchup_gates import MatchupGate, MatchupGateResult, GateStatus

logger = logging.getLogger(__name__)

FEATURE_FLAGS_PATH = Path("config/feature_flags.json")


def is_matchup_memory_enabled() -> bool:
    """Check if matchup memory feature is enabled."""
    try:
        if FEATURE_FLAGS_PATH.exists():
            with open(FEATURE_FLAGS_PATH, 'r') as f:
                flags = json.load(f)
                return flags.get("nba", {}).get("matchup_memory_enabled", False)
    except Exception:
        pass
    return False


def is_jiggy_mode() -> bool:
    """Check if JIGGY (ungoverned) mode is active."""
    try:
        settings_path = Path(".analyzer_settings.json")
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return settings.get("jiggy", False)
    except Exception:
        pass
    return False


@dataclass
class MatchupResult:
    """Result of matchup memory lookup and adjustment.
    
    Uses simple types to avoid dependency on non-existent classes.
    """
    found: bool
    adjustment_factor: float = 1.0  # Multiplicative factor (1.0 = no change)
    confidence: float = 0.0  # 0.0-1.0 confidence in adjustment
    gate_passed: bool = False  # Whether quality gates passed
    gate_status: str = "not_checked"  # Gate status string
    applied: bool = False
    reason: str = ""
    lineage: Dict[str, Any] = field(default_factory=dict)  # Full audit trail
    
    @property
    def adjusted_mu(self) -> Optional[float]:
        """Get adjustment factor if applied (for compatibility)."""
        if self.applied:
            return self.adjustment_factor
        return None


class MatchupMemoryIntegrator:
    """
    Integrates matchup memory into probability calculations.
    
    This class:
    1. Checks if matchup memory is enabled
    2. Looks up player-vs-opponent history
    3. Computes Bayesian-shrunk adjustments
    4. Applies gates to prevent over-reliance on small samples
    5. Returns adjustments for mu/sigma modification
    """
    
    def __init__(
        self,
        min_games: int = 3,
        max_weight: float = 0.30,
        shrinkage_games: int = 10,
    ):
        self.min_games = min_games
        self.max_weight = max_weight
        self.shrinkage_games = shrinkage_games
        self.gate = MatchupGate(min_games=min_games)  # MatchupGate doesn't use max_weight
        self._cache: Dict[str, PlayerVsOpponentStats] = {}
        self._matchup_index: Optional[MatchupIndex] = None
    
    def get_matchup_adjustment(
        self,
        player: str,
        opponent: str,
        stat_category: str,
        baseline: float = 0.0,
    ) -> MatchupResult:
        """
        Get matchup-based adjustment for a player vs opponent.
        
        Args:
            player: Player name or ID
            opponent: Opponent team abbreviation
            stat_category: Stat category (e.g., "PTS", "REB")
            baseline: Baseline projection for adjustment calculation
        
        Returns:
            MatchupResult with adjustment details
        """
        # Check if feature is enabled
        if not is_matchup_memory_enabled():
            return MatchupResult(
                found=False,
                applied=False,
                reason="matchup_memory_disabled"
            )
        
        # Check JIGGY mode - still calculate but mark as ungoverned
        jiggy_active = is_jiggy_mode()
        
        # Use the compute_adjustment function which returns (adj_value, confidence, lineage)
        try:
            adjusted_value, confidence, lineage = compute_adjustment(
                player_id=player,
                opponent_team=opponent,
                stat_type=stat_category,
                baseline_projection=baseline,
                matchup_index=self._matchup_index,
                min_games=self.min_games,
            )
        except Exception as e:
            logger.debug(f"Matchup lookup failed for {player} vs {opponent}: {e}")
            return MatchupResult(
                found=False,
                applied=False,
                reason=f"lookup_error: {str(e)}"
            )
        
        # Check if adjustment was applied
        if not lineage.get("adjustment_applied", False):
            return MatchupResult(
                found=False,
                confidence=0.0,
                applied=False,
                reason=lineage.get("reason", "insufficient_data"),
                lineage=lineage
            )
        
        # Calculate adjustment factor (ratio of adjusted to baseline)
        if baseline > 0:
            adjustment_factor = adjusted_value / baseline
        else:
            adjustment_factor = 1.0
        
        # Apply gate check
        games_vs = lineage.get("games_vs_opponent", 0)
        gate_passed = games_vs >= self.min_games and confidence > 0
        gate_status = "pass" if gate_passed else f"fail_games_{games_vs}"
        
        # Determine if we should apply
        should_apply = gate_passed
        
        if not should_apply:
            reason = f"gate_blocked: {gate_status}"
        elif jiggy_active:
            reason = "applied_ungoverned"
        else:
            reason = "applied_governed"
        
        return MatchupResult(
            found=True,
            adjustment_factor=adjustment_factor,
            confidence=confidence,
            gate_passed=gate_passed,
            gate_status=gate_status,
            applied=should_apply,
            reason=reason,
            lineage=lineage
        )
    
    def adjust_mu_sigma(
        self,
        mu: float,
        sigma: float,
        player: str,
        opponent: str,
        stat_category: str,
    ) -> Tuple[float, float, MatchupResult]:
        """
        Adjust mu/sigma based on matchup memory.
        
        Returns:
            Tuple of (adjusted_mu, adjusted_sigma, matchup_result)
        """
        result = self.get_matchup_adjustment(
            player, opponent, stat_category, baseline=mu
        )
        
        if not result.applied:
            return mu, sigma, result
        
        # Apply adjustment factor with weight limiting
        # Factor is clamped to max_weight deviation from 1.0
        factor = result.adjustment_factor
        clamped_factor = max(1.0 - self.max_weight, min(1.0 + self.max_weight, factor))
        
        adjusted_mu = mu * clamped_factor
        
        # Keep sigma unchanged for now (could adjust based on matchup variance)
        adjusted_sigma = sigma
        
        return adjusted_mu, adjusted_sigma, result
    
    def set_matchup_index(self, index: MatchupIndex):
        """Set the matchup index to use for lookups."""
        self._matchup_index = index
    
    def clear_cache(self):
        """Clear any internal caches."""
        self._cache.clear()


# Singleton instance for easy access
_integrator: Optional[MatchupMemoryIntegrator] = None


def get_integrator() -> MatchupMemoryIntegrator:
    """Get or create the matchup memory integrator singleton."""
    global _integrator
    if _integrator is None:
        _integrator = MatchupMemoryIntegrator()
    return _integrator


def adjust_for_matchup(
    mu: float,
    sigma: float,
    player: str,
    opponent: str,
    stat_category: str,
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Convenience function to adjust mu/sigma for matchup effects.
    
    Returns:
        Tuple of (adjusted_mu, adjusted_sigma, metadata_dict)
    """
    integrator = get_integrator()
    adj_mu, adj_sigma, result = integrator.adjust_mu_sigma(
        mu, sigma, player, opponent, stat_category
    )
    
    metadata = {
        "matchup_found": result.found,
        "matchup_applied": result.applied,
        "matchup_reason": result.reason,
        "matchup_confidence": result.confidence,
        "matchup_adjustment_factor": result.adjustment_factor,
    }
    
    if result.lineage:
        metadata["matchup_lineage"] = result.lineage
    
    return adj_mu, adj_sigma, metadata
