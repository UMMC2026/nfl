"""
Matchup Gates - Sample Size and Variance Quality Gates
======================================================

Hard gates that prevent matchup adjustments from being applied when
data quality is insufficient. These gates enforce discipline and
prevent false precision.

GATE TYPES:
1. Sample Size Gate: Minimum games required
2. Variance Gate: Rejects high-variance matchups
3. Recency Gate: Discounts stale data
4. Confidence Gate: Overall quality threshold
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Gate evaluation result status."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class MatchupGateResult:
    """Result of gate evaluation with audit trail."""
    gate_name: str
    status: GateStatus
    value: float
    threshold: float
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }


@dataclass
class MatchupGateSummary:
    """Aggregate gate result used by interactive tools/menus."""

    status: GateStatus
    message: str = ""
    can_apply: bool = False
    results: Dict[str, MatchupGateResult] = None  # type: ignore[assignment]


class MatchupGate:
    """
    Configurable gate system for matchup data quality.
    
    Default thresholds are conservative to prevent false precision.
    """
    
    # Default thresholds
    MIN_GAMES_HARD = 3      # Absolute minimum for any adjustment
    MIN_GAMES_FULL = 10     # Games needed for full confidence
    MAX_CV_WARN = 0.5       # Coefficient of variation warning threshold
    MAX_CV_FAIL = 0.8       # CV rejection threshold
    MAX_STALENESS_DAYS = 365  # Data older than this gets discounted
    RECENCY_DECAY = 0.1     # Daily decay rate for stale data
    MIN_CONFIDENCE = 0.3    # Minimum confidence to apply adjustment
    
    def __init__(
        self,
        min_games: int = 3,
        min_games_full: int = 10,
        max_cv: float = 0.8,
        max_staleness_days: int = 365,
        min_confidence: float = 0.3,
        max_weight: Optional[float] = None,
    ):
        self.min_games = min_games
        self.min_games_full = min_games_full
        self.max_cv = max_cv
        self.max_staleness_days = max_staleness_days
        self.min_confidence = min_confidence

        # NOTE: Some call sites historically passed `max_weight` here.
        # Weight clamping is handled by MatchupIntegration (see matchup_integration.py),
        # not by MatchupGate. We accept the argument to avoid runtime crashes.
        self.max_weight = max_weight
    
    def check_sample_size(self, games_played: int) -> MatchupGateResult:
        """
        Gate 1: Sample size check.
        
        FAIL if < min_games
        WARN if < min_games_full
        PASS otherwise
        """
        if games_played < self.min_games:
            return MatchupGateResult(
                gate_name="sample_size",
                status=GateStatus.FAIL,
                value=float(games_played),
                threshold=float(self.min_games),
                message=f"Insufficient sample: {games_played} games < {self.min_games} minimum"
            )
        
        if games_played < self.min_games_full:
            return MatchupGateResult(
                gate_name="sample_size",
                status=GateStatus.WARN,
                value=float(games_played),
                threshold=float(self.min_games_full),
                message=f"Limited sample: {games_played} games < {self.min_games_full} for full confidence"
            )
        
        return MatchupGateResult(
            gate_name="sample_size",
            status=GateStatus.PASS,
            value=float(games_played),
            threshold=float(self.min_games),
            message=f"Adequate sample: {games_played} games"
        )
    
    def check_variance(self, mean: float, std_dev: float) -> MatchupGateResult:
        """
        Gate 2: Variance stability check using coefficient of variation.
        
        CV = std_dev / mean
        High CV indicates unreliable matchup pattern.
        """
        if mean <= 0:
            return MatchupGateResult(
                gate_name="variance",
                status=GateStatus.FAIL,
                value=float('inf'),
                threshold=self.max_cv,
                message="Invalid mean <= 0"
            )
        
        cv = std_dev / mean
        
        if cv > self.max_cv:
            return MatchupGateResult(
                gate_name="variance",
                status=GateStatus.FAIL,
                value=cv,
                threshold=self.max_cv,
                message=f"High variance: CV={cv:.2f} > {self.max_cv} threshold"
            )
        
        if cv > self.MAX_CV_WARN:
            return MatchupGateResult(
                gate_name="variance",
                status=GateStatus.WARN,
                value=cv,
                threshold=self.MAX_CV_WARN,
                message=f"Elevated variance: CV={cv:.2f}"
            )
        
        return MatchupGateResult(
            gate_name="variance",
            status=GateStatus.PASS,
            value=cv,
            threshold=self.max_cv,
            message=f"Stable variance: CV={cv:.2f}"
        )
    
    def check_recency(self, last_game_date: Optional[datetime]) -> MatchupGateResult:
        """
        Gate 3: Data recency check.
        
        Matchup data gets stale over time due to:
        - Roster changes
        - Scheme changes
        - Player development
        """
        if last_game_date is None:
            return MatchupGateResult(
                gate_name="recency",
                status=GateStatus.WARN,
                value=float('inf'),
                threshold=float(self.max_staleness_days),
                message="No date information available"
            )
        
        days_old = (datetime.now() - last_game_date).days
        
        if days_old > self.max_staleness_days:
            return MatchupGateResult(
                gate_name="recency",
                status=GateStatus.FAIL,
                value=float(days_old),
                threshold=float(self.max_staleness_days),
                message=f"Stale data: {days_old} days old > {self.max_staleness_days} limit"
            )
        
        if days_old > self.max_staleness_days // 2:
            return MatchupGateResult(
                gate_name="recency",
                status=GateStatus.WARN,
                value=float(days_old),
                threshold=float(self.max_staleness_days // 2),
                message=f"Aging data: {days_old} days old"
            )
        
        return MatchupGateResult(
            gate_name="recency",
            status=GateStatus.PASS,
            value=float(days_old),
            threshold=float(self.max_staleness_days),
            message=f"Recent data: {days_old} days old"
        )
    
    def check_confidence(self, confidence: float) -> MatchupGateResult:
        """
        Gate 4: Overall confidence check.
        
        Confidence is computed by the matchup stats class based on
        sample size and variance.
        """
        if confidence < self.min_confidence:
            return MatchupGateResult(
                gate_name="confidence",
                status=GateStatus.FAIL,
                value=confidence,
                threshold=self.min_confidence,
                message=f"Low confidence: {confidence:.2f} < {self.min_confidence} minimum"
            )
        
        if confidence < 0.5:
            return MatchupGateResult(
                gate_name="confidence",
                status=GateStatus.WARN,
                value=confidence,
                threshold=0.5,
                message=f"Moderate confidence: {confidence:.2f}"
            )
        
        return MatchupGateResult(
            gate_name="confidence",
            status=GateStatus.PASS,
            value=confidence,
            threshold=self.min_confidence,
            message=f"Good confidence: {confidence:.2f}"
        )
    
    def evaluate_all(
        self,
        games_played: int,
        mean: float,
        std_dev: float,
        last_game_date: Optional[datetime],
        confidence: float,
    ) -> Tuple[bool, Dict[str, MatchupGateResult]]:
        """
        Run all gates and return aggregate result.
        
        Returns:
            (can_apply, results_dict)
            - can_apply: True if no FAIL gates
            - results_dict: Individual gate results
        """
        results = {
            "sample_size": self.check_sample_size(games_played),
            "variance": self.check_variance(mean, std_dev),
            "recency": self.check_recency(last_game_date),
            "confidence": self.check_confidence(confidence),
        }
        
        # Any FAIL = cannot apply adjustment
        can_apply = all(r.status != GateStatus.FAIL for r in results.values())
        
        return (can_apply, results)

    def evaluate(self, matchup_stats: Any) -> MatchupGateSummary:
        """
        Backward-compatible convenience method.

        The interactive menu (`menu.py`) calls `gate.evaluate(matchup_stats)` and
        expects an object with `.status` and `.message`.

        Args:
            matchup_stats: Typically a PlayerVsOpponentStats instance.

        Returns:
            MatchupGateSummary
        """
        games_played = int(getattr(matchup_stats, "games_played", 0) or 0)
        mean = float(getattr(matchup_stats, "mean", 0.0) or 0.0)
        std_dev = float(getattr(matchup_stats, "std_dev", 0.0) or 0.0)
        last_game_date = getattr(matchup_stats, "last_game_date", None)
        confidence = float(getattr(matchup_stats, "confidence", 0.0) or 0.0)

        can_apply, results = self.evaluate_all(
            games_played=games_played,
            mean=mean,
            std_dev=std_dev,
            last_game_date=last_game_date,
            confidence=confidence,
        )

        statuses = [r.status for r in results.values()]
        if any(s == GateStatus.FAIL for s in statuses):
            status = GateStatus.FAIL
            msgs = [r.message for r in results.values() if r.status == GateStatus.FAIL and r.message]
            message = "; ".join(msgs) if msgs else "One or more gates failed"
        elif any(s == GateStatus.WARN for s in statuses):
            status = GateStatus.WARN
            msgs = [r.message for r in results.values() if r.status == GateStatus.WARN and r.message]
            message = "; ".join(msgs) if msgs else "One or more gates warned"
        else:
            status = GateStatus.PASS
            message = "All gates passed"

        return MatchupGateSummary(status=status, message=message, can_apply=can_apply, results=results)


def validate_matchup_sample(
    games_played: int,
    mean: float,
    std_dev: float,
    last_game_date: Optional[datetime] = None,
    confidence: float = 0.5,
    gate: Optional[MatchupGate] = None,
) -> Tuple[bool, float, Dict[str, Any]]:
    """
    Convenience function to validate matchup data quality.
    
    Returns:
        (is_valid, discount_factor, audit_trail)
        - is_valid: Whether adjustment can be applied
        - discount_factor: 0.0-1.0 multiplier for adjustment strength
        - audit_trail: Dict with gate results for lineage
    """
    if gate is None:
        gate = MatchupGate()
    
    can_apply, results = gate.evaluate_all(
        games_played, mean, std_dev, last_game_date, confidence
    )
    
    # Compute discount factor based on warnings
    discount = 1.0
    warn_count = sum(1 for r in results.values() if r.status == GateStatus.WARN)
    
    # Each warning reduces confidence by 15%
    discount *= (0.85 ** warn_count)
    
    # Additional discount for small samples
    if games_played < gate.min_games_full:
        sample_discount = games_played / gate.min_games_full
        discount *= sample_discount
    
    # Additional discount for stale data
    if last_game_date:
        days_old = (datetime.now() - last_game_date).days
        if days_old > 90:
            recency_discount = max(0.5, 1.0 - (days_old - 90) / 365)
            discount *= recency_discount
    
    audit_trail = {
        "gates": {k: v.to_dict() for k, v in results.items()},
        "can_apply": can_apply,
        "discount_factor": discount,
        "warn_count": warn_count,
    }
    
    return (can_apply, discount, audit_trail)


def compute_shrinkage_weight(
    sample_size: int,
    sample_variance: float,
    prior_variance: float,
    prior_strength: float = 5.0,
) -> float:
    """
    Compute Bayesian shrinkage weight.
    
    w = n / (n + k) where k depends on variance ratio
    
    Returns value between 0 (full prior) and 1 (full sample).
    """
    if sample_size <= 0:
        return 0.0
    
    if prior_variance <= 0:
        prior_variance = sample_variance or 1.0
    
    variance_ratio = sample_variance / prior_variance if prior_variance > 0 else 1.0
    k = prior_strength * min(variance_ratio, 3.0)  # Cap at 3x
    
    weight = sample_size / (sample_size + k)
    
    return weight


# Stat-specific gate configurations
STAT_GATE_CONFIGS = {
    # High-volume stats: more lenient
    "PTS": MatchupGate(min_games=3, min_games_full=8, max_cv=0.6),
    "REB": MatchupGate(min_games=3, min_games_full=8, max_cv=0.6),
    
    # Medium-volume: default config
    "AST": MatchupGate(min_games=3, min_games_full=10, max_cv=0.7),
    
    # Low-volume stats: stricter requirements
    "STL": MatchupGate(min_games=5, min_games_full=12, max_cv=0.8),
    "BLK": MatchupGate(min_games=5, min_games_full=12, max_cv=0.9),
    "3PM": MatchupGate(min_games=5, min_games_full=12, max_cv=0.8),
    
    # Composites: moderate
    "PRA": MatchupGate(min_games=3, min_games_full=8, max_cv=0.5),
    "PR": MatchupGate(min_games=3, min_games_full=8, max_cv=0.5),
    "PA": MatchupGate(min_games=3, min_games_full=8, max_cv=0.5),
    "RA": MatchupGate(min_games=3, min_games_full=10, max_cv=0.6),
}


def get_gate_for_stat(stat_type: str) -> MatchupGate:
    """Get appropriate gate configuration for a stat type."""
    return STAT_GATE_CONFIGS.get(stat_type.upper(), MatchupGate())
