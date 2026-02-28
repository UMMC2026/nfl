"""
CBB Live Controls — Lock Unders Trigger
----------------------------------------
In-game momentum detection to lock unders when game pace collapses.

Triggers:
1. Pace Ratio drops below threshold
2. Fouls per minute spike
3. Shot clock violations exceed threshold
4. Combined momentum score breaches lock threshold

This is NOT automatic switching — it surfaces alerts for manual confirmation.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class LiveGameState:
    """Real-time game state for lock-unders detection."""
    game_id: str
    elapsed_minutes: float
    home_score: int
    away_score: int
    home_fouls: int
    away_fouls: int
    home_shot_clock_violations: int
    away_shot_clock_violations: int
    home_possessions: int
    away_possessions: int
    timestamp: datetime


@dataclass
class LockUndersThresholds:
    """Configurable thresholds for lock-unders trigger."""
    pace_ratio_floor: float = 0.85       # Below this = pace collapse
    fouls_per_minute_ceiling: float = 0.6  # Above this = foul fest
    shot_clock_violations_trigger: int = 3  # Combined violations
    momentum_lock_score: float = 2.0     # Sum of signals to trigger
    min_elapsed_minutes: float = 10.0    # Don't trigger too early


@dataclass
class LockUndersSignal:
    """Output signal when lock-unders conditions are met."""
    triggered: bool
    momentum_score: float
    signals: dict
    recommendation: str
    timestamp: datetime


class LockUndersDetector:
    """Detects when game conditions favor locking in unders."""
    
    def __init__(self, thresholds: Optional[LockUndersThresholds] = None):
        self.thresholds = thresholds or LockUndersThresholds()
    
    def compute_pace_ratio(self, state: LiveGameState) -> float:
        """
        Compute actual pace vs expected pace.
        Uses possessions per minute as proxy.
        """
        if state.elapsed_minutes < 1:
            return 1.0
        
        total_possessions = state.home_possessions + state.away_possessions
        possessions_per_minute = total_possessions / state.elapsed_minutes
        
        # Expected CBB pace: ~70 possessions per team per 40 min = ~3.5 per minute combined
        expected_pace = 3.5
        pace_ratio = possessions_per_minute / expected_pace
        
        return pace_ratio
    
    def compute_fouls_per_minute(self, state: LiveGameState) -> float:
        """Compute combined fouls per minute."""
        if state.elapsed_minutes < 1:
            return 0.0
        
        total_fouls = state.home_fouls + state.away_fouls
        return total_fouls / state.elapsed_minutes
    
    def compute_shot_clock_violations(self, state: LiveGameState) -> int:
        """Total shot clock violations."""
        return state.home_shot_clock_violations + state.away_shot_clock_violations
    
    def compute_momentum_score(self, state: LiveGameState) -> tuple[float, dict]:
        """
        Compute composite momentum score for lock-unders.
        Returns (score, signal_breakdown).
        """
        signals = {}
        score = 0.0
        
        # Signal 1: Pace collapse
        pace_ratio = self.compute_pace_ratio(state)
        if pace_ratio < self.thresholds.pace_ratio_floor:
            pace_signal = (self.thresholds.pace_ratio_floor - pace_ratio) * 5
            signals['pace_collapse'] = {
                'value': pace_ratio,
                'threshold': self.thresholds.pace_ratio_floor,
                'contribution': pace_signal
            }
            score += pace_signal
        
        # Signal 2: Foul rate spike
        fpm = self.compute_fouls_per_minute(state)
        if fpm > self.thresholds.fouls_per_minute_ceiling:
            foul_signal = (fpm - self.thresholds.fouls_per_minute_ceiling) * 3
            signals['foul_spike'] = {
                'value': fpm,
                'threshold': self.thresholds.fouls_per_minute_ceiling,
                'contribution': foul_signal
            }
            score += foul_signal
        
        # Signal 3: Shot clock violations
        scv = self.compute_shot_clock_violations(state)
        if scv >= self.thresholds.shot_clock_violations_trigger:
            scv_signal = (scv - self.thresholds.shot_clock_violations_trigger + 1) * 0.5
            signals['shot_clock_violations'] = {
                'value': scv,
                'threshold': self.thresholds.shot_clock_violations_trigger,
                'contribution': scv_signal
            }
            score += scv_signal
        
        return score, signals
    
    def detect(self, state: LiveGameState) -> LockUndersSignal:
        """
        Analyze game state and return lock-unders signal.
        """
        # Don't trigger too early
        if state.elapsed_minutes < self.thresholds.min_elapsed_minutes:
            return LockUndersSignal(
                triggered=False,
                momentum_score=0.0,
                signals={},
                recommendation="TOO_EARLY",
                timestamp=datetime.now()
            )
        
        momentum_score, signals = self.compute_momentum_score(state)
        triggered = momentum_score >= self.thresholds.momentum_lock_score
        
        if triggered:
            recommendation = "LOCK_UNDERS_ALERT"
        elif momentum_score > self.thresholds.momentum_lock_score * 0.7:
            recommendation = "WATCH_FOR_UNDERS"
        else:
            recommendation = "NO_ACTION"
        
        return LockUndersSignal(
            triggered=triggered,
            momentum_score=momentum_score,
            signals=signals,
            recommendation=recommendation,
            timestamp=datetime.now()
        )


# Utility functions for external use
def check_lock_unders(
    game_id: str,
    elapsed_minutes: float,
    home_score: int,
    away_score: int,
    home_fouls: int,
    away_fouls: int,
    home_scv: int = 0,
    away_scv: int = 0,
    home_poss: int = 0,
    away_poss: int = 0
) -> LockUndersSignal:
    """
    Convenience function to check lock-unders conditions.
    
    Args:
        game_id: Unique game identifier
        elapsed_minutes: Minutes elapsed in game
        home_score: Home team score
        away_score: Away team score  
        home_fouls: Home team fouls
        away_fouls: Away team fouls
        home_scv: Home shot clock violations
        away_scv: Away shot clock violations
        home_poss: Home possessions (estimate if unknown)
        away_poss: Away possessions (estimate if unknown)
    
    Returns:
        LockUndersSignal with triggered status and details
    """
    # Estimate possessions from score if not provided
    if home_poss == 0:
        home_poss = int(home_score / 1.0)  # ~1 point per possession estimate
    if away_poss == 0:
        away_poss = int(away_score / 1.0)
    
    state = LiveGameState(
        game_id=game_id,
        elapsed_minutes=elapsed_minutes,
        home_score=home_score,
        away_score=away_score,
        home_fouls=home_fouls,
        away_fouls=away_fouls,
        home_shot_clock_violations=home_scv,
        away_shot_clock_violations=away_scv,
        home_possessions=home_poss,
        away_possessions=away_poss,
        timestamp=datetime.now()
    )
    
    detector = LockUndersDetector()
    return detector.detect(state)
