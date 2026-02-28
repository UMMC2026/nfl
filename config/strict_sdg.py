"""
STRICT SDG (Stat Deviation Gate) V2
====================================

Based on 97-pick backtest showing 48.5% hit rate (vs 55% expected),
the original SDG thresholds are TOO LENIENT.

This module implements stricter filtering:
1. Higher z-score thresholds (0.75 vs 0.60)
2. Minimum absolute edge requirements
3. Dual-gate system (must pass BOTH)
4. Sample size penalties

Key Finding:
- Original SDG let through marginal edges that looked like 55% but were coin flips
- New SDG requires STRONG statistical separation from the line

Usage:
    from config.strict_sdg import StrictSDG, sdg_gate_v2
    
    result = sdg_gate_v2(
        player_mean=15.2,
        player_std=4.1,
        line=13.5,
        stat_type='PTS',
        sample_size=12
    )
    
    if result.passed:
        # Process pick
    else:
        print(f"Blocked: {result.reason}")
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict
from enum import Enum


class SDGResult(Enum):
    """SDG Gate Results"""
    PASS = "PASS"
    FAIL_Z_SCORE = "FAIL_Z_SCORE"
    FAIL_MIN_EDGE = "FAIL_MIN_EDGE"
    FAIL_SAMPLE_SIZE = "FAIL_SAMPLE_SIZE"
    FAIL_VARIANCE = "FAIL_VARIANCE"
    FAIL_COMBINED = "FAIL_COMBINED"
    PENALIZED = "PENALIZED"


@dataclass
class SDGGateResult:
    """Result from SDG gate check"""
    passed: bool
    result: SDGResult
    reason: str
    z_score: float
    edge: float
    penalty: float = 1.0  # Multiplier (1.0 = no penalty)
    details: Optional[Dict] = None


# =============================================================================
# STRICT SDG THRESHOLDS (Calibrated from backtest)
# =============================================================================

# Original thresholds (TOO LENIENT - resulted in 48.5% hit rate)
ORIGINAL_SDG_THRESHOLDS = {
    'PTS': {'z': 0.60, 'edge': 1.5},
    'REB': {'z': 0.55, 'edge': 1.0},
    'AST': {'z': 0.55, 'edge': 0.8},
    '3PM': {'z': 0.45, 'edge': 0.5},
    'PRA': {'z': 0.60, 'edge': 2.0},
}

# NEW STRICT THRESHOLDS (Target: 57%+ hit rate)
STRICT_SDG_THRESHOLDS = {
    # Core stats - significantly raised
    'PTS': {
        'z': 0.75,          # Raised from 0.60 (25% stricter)
        'edge': 2.5,        # Raised from 1.5 (67% stricter)
        'max_cv': 0.45,     # Max coefficient of variation
        'min_games': 8,     # Minimum games required
    },
    'REB': {
        'z': 0.70,          # Raised from 0.55
        'edge': 1.5,        # Raised from 1.0
        'max_cv': 0.50,
        'min_games': 8,
    },
    'AST': {
        'z': 0.70,          # Raised from 0.55
        'edge': 1.2,        # Raised from 0.8
        'max_cv': 0.55,     # AST more variable
        'min_games': 8,
    },
    
    # Volatile stats - much stricter
    '3PM': {
        'z': 0.65,          # Raised from 0.45
        'edge': 0.8,        # Raised from 0.5
        'max_cv': 0.60,     # High variance stat
        'min_games': 10,    # Need more data
    },
    
    # Combo stats - stricter due to compounding variance
    'PRA': {
        'z': 0.80,          # Raised from 0.60 (33% stricter)
        'edge': 3.5,        # Raised from 2.0 (75% stricter)
        'max_cv': 0.40,     # Combo stats should be stable
        'min_games': 10,
    },
    'PTS+AST': {
        'z': 0.75,
        'edge': 2.5,
        'max_cv': 0.45,
        'min_games': 10,
    },
    'PTS+REB': {
        'z': 0.75,
        'edge': 2.5,
        'max_cv': 0.45,
        'min_games': 10,
    },
    'REB+AST': {
        'z': 0.70,
        'edge': 2.0,
        'max_cv': 0.50,
        'min_games': 10,
    },
    
    # Default for unknown stats
    'DEFAULT': {
        'z': 0.75,
        'edge': 2.0,
        'max_cv': 0.50,
        'min_games': 8,
    },
}

# CBB-specific overrides (even stricter due to higher variance)
CBB_SDG_THRESHOLDS = {
    'PTS': {
        'z': 0.80,          # CBB more volatile than NBA
        'edge': 3.0,
        'max_cv': 0.40,
        'min_games': 6,     # Less games available
    },
    'REB': {
        'z': 0.75,
        'edge': 2.0,
        'max_cv': 0.45,
        'min_games': 6,
    },
    'AST': {
        'z': 0.75,
        'edge': 1.5,
        'max_cv': 0.50,
        'min_games': 6,
    },
    '3PM': {
        'z': 0.70,
        'edge': 1.0,
        'max_cv': 0.55,
        'min_games': 8,
    },
    'PRA': {
        'z': 0.85,          # Very strict for CBB combos
        'edge': 4.0,
        'max_cv': 0.35,
        'min_games': 8,
    },
    'DEFAULT': {
        'z': 0.80,
        'edge': 2.5,
        'max_cv': 0.45,
        'min_games': 6,
    },
}


# =============================================================================
# SAMPLE SIZE PENALTIES
# =============================================================================

def get_sample_size_penalty(sample_size: int, min_required: int) -> float:
    """
    Apply penalty for small sample sizes.
    
    Returns multiplier (1.0 = no penalty, <1.0 = penalized)
    """
    if sample_size >= min_required * 2:
        return 1.0  # Large sample, no penalty
    elif sample_size >= min_required:
        return 0.95  # Adequate sample, small penalty
    elif sample_size >= min_required * 0.75:
        return 0.90  # Marginal sample
    elif sample_size >= min_required * 0.5:
        return 0.85  # Small sample
    else:
        return 0.0  # Insufficient data - block


def get_variance_penalty(cv: float, max_cv: float) -> float:
    """
    Apply penalty for high variance (coefficient of variation).
    
    CV = std / mean
    
    Returns multiplier (1.0 = no penalty, <1.0 = penalized)
    """
    if cv <= max_cv * 0.6:
        return 1.0  # Very stable
    elif cv <= max_cv * 0.8:
        return 0.97  # Somewhat stable
    elif cv <= max_cv:
        return 0.94  # Borderline
    elif cv <= max_cv * 1.2:
        return 0.88  # High variance penalty
    else:
        return 0.80  # Very high variance - heavy penalty


# =============================================================================
# STRICT SDG GATE FUNCTION
# =============================================================================

def sdg_gate_v2(
    player_mean: float,
    player_std: float,
    line: float,
    stat_type: str,
    sample_size: int = 10,
    sport: str = 'CBB',
    direction: Optional[str] = None
) -> SDGGateResult:
    """
    Strict SDG gate based on backtest calibration.
    
    Must pass ALL of:
    1. Z-score threshold
    2. Minimum absolute edge
    3. Sample size requirement
    4. Variance (CV) check
    
    Args:
        player_mean: Player's weighted average for stat
        player_std: Player's standard deviation
        line: Betting line
        stat_type: PTS, REB, AST, 3PM, PRA, etc.
        sample_size: Number of games in sample
        sport: CBB, NBA, etc.
        direction: OVER/UNDER (optional for directional penalties)
        
    Returns:
        SDGGateResult with pass/fail status and details
    """
    # Get sport-specific thresholds
    if sport.upper() == 'CBB':
        thresholds_map = CBB_SDG_THRESHOLDS
    else:
        thresholds_map = STRICT_SDG_THRESHOLDS
    
    # Normalize stat type
    stat_upper = stat_type.upper().replace('POINTS', 'PTS').replace('REBOUNDS', 'REB').replace('ASSISTS', 'AST')
    
    # Get thresholds for this stat
    thresholds = thresholds_map.get(stat_upper, thresholds_map['DEFAULT'])
    
    min_z = thresholds['z']
    min_edge = thresholds['edge']
    max_cv = thresholds['max_cv']
    min_games = thresholds['min_games']
    
    # Calculate metrics
    if player_std <= 0:
        player_std = player_mean * 0.3  # Default 30% CV if missing
    
    z_score = abs((line - player_mean) / player_std) if player_std > 0 else 0
    edge = abs(line - player_mean)
    cv = player_std / player_mean if player_mean > 0 else 1.0
    
    # Initialize penalty
    total_penalty = 1.0
    fail_reasons = []
    
    # Gate 1: Z-score check
    if z_score < min_z:
        fail_reasons.append(f"Z-score {z_score:.2f} < {min_z:.2f}")
    
    # Gate 2: Minimum edge check
    if edge < min_edge:
        fail_reasons.append(f"Edge {edge:.1f} < {min_edge:.1f}")
    
    # Gate 3: Sample size check
    sample_penalty = get_sample_size_penalty(sample_size, min_games)
    if sample_penalty == 0:
        fail_reasons.append(f"Sample size {sample_size} < {int(min_games * 0.5)} minimum")
    else:
        total_penalty *= sample_penalty
    
    # Gate 4: Variance check
    variance_penalty = get_variance_penalty(cv, max_cv)
    if cv > max_cv * 1.5:
        fail_reasons.append(f"CV {cv:.2f} >> {max_cv:.2f} max (too volatile)")
    else:
        total_penalty *= variance_penalty
    
    # Determine final result
    if fail_reasons:
        # Hard fail
        if len(fail_reasons) >= 2:
            result = SDGResult.FAIL_COMBINED
        elif 'Z-score' in fail_reasons[0]:
            result = SDGResult.FAIL_Z_SCORE
        elif 'Edge' in fail_reasons[0]:
            result = SDGResult.FAIL_MIN_EDGE
        elif 'Sample' in fail_reasons[0]:
            result = SDGResult.FAIL_SAMPLE_SIZE
        else:
            result = SDGResult.FAIL_VARIANCE
        
        return SDGGateResult(
            passed=False,
            result=result,
            reason='; '.join(fail_reasons),
            z_score=z_score,
            edge=edge,
            penalty=total_penalty,
            details={
                'cv': cv,
                'sample_size': sample_size,
                'thresholds': thresholds,
            }
        )
    
    elif total_penalty < 0.95:
        # Passed but penalized
        return SDGGateResult(
            passed=True,
            result=SDGResult.PENALIZED,
            reason=f"Passed with penalty ({total_penalty:.2f}x)",
            z_score=z_score,
            edge=edge,
            penalty=total_penalty,
            details={
                'cv': cv,
                'sample_size': sample_size,
                'sample_penalty': sample_penalty,
                'variance_penalty': variance_penalty,
            }
        )
    
    else:
        # Clean pass
        return SDGGateResult(
            passed=True,
            result=SDGResult.PASS,
            reason="Passed all gates",
            z_score=z_score,
            edge=edge,
            penalty=total_penalty,
            details={
                'cv': cv,
                'sample_size': sample_size,
            }
        )


# =============================================================================
# STRICT SDG CLASS (For integration)
# =============================================================================

class StrictSDG:
    """
    Strict Stat Deviation Gate v2.0
    
    Based on 97-pick backtest calibration.
    """
    
    def __init__(self, sport: str = 'CBB'):
        self.sport = sport.upper()
        self.thresholds = CBB_SDG_THRESHOLDS if self.sport == 'CBB' else STRICT_SDG_THRESHOLDS
        
        # Counters for reporting
        self.passed = 0
        self.failed = 0
        self.penalized = 0
        self.fail_reasons = {}
    
    def check(
        self,
        player_mean: float,
        player_std: float,
        line: float,
        stat_type: str,
        sample_size: int = 10,
        direction: Optional[str] = None
    ) -> SDGGateResult:
        """Check if pick passes SDG gate."""
        result = sdg_gate_v2(
            player_mean=player_mean,
            player_std=player_std,
            line=line,
            stat_type=stat_type,
            sample_size=sample_size,
            sport=self.sport,
            direction=direction
        )
        
        # Update counters
        if result.passed:
            if result.result == SDGResult.PENALIZED:
                self.penalized += 1
            else:
                self.passed += 1
        else:
            self.failed += 1
            reason_key = result.result.value
            self.fail_reasons[reason_key] = self.fail_reasons.get(reason_key, 0) + 1
        
        return result
    
    def get_summary(self) -> str:
        """Get summary of SDG gate results."""
        total = self.passed + self.failed + self.penalized
        if total == 0:
            return "No picks processed"
        
        summary = f"""
SDG V2 SUMMARY ({self.sport})
{'=' * 40}
Total processed: {total}
Passed:          {self.passed} ({self.passed/total*100:.1f}%)
Penalized:       {self.penalized} ({self.penalized/total*100:.1f}%)
Failed:          {self.failed} ({self.failed/total*100:.1f}%)

Failure Breakdown:
"""
        for reason, count in sorted(self.fail_reasons.items(), key=lambda x: -x[1]):
            summary += f"  {reason}: {count}\n"
        
        return summary
    
    def reset(self):
        """Reset counters."""
        self.passed = 0
        self.failed = 0
        self.penalized = 0
        self.fail_reasons = {}


# =============================================================================
# DEMO
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  STRICT SDG V2 - DEMO")
    print("=" * 60)
    
    sdg = StrictSDG(sport='CBB')
    
    # Test cases from your typical CBB data
    test_cases = [
        # (mean, std, line, stat, sample, description)
        (15.2, 4.1, 13.5, 'PTS', 12, "Borderline edge"),
        (15.2, 4.1, 11.5, 'PTS', 12, "Strong edge"),
        (15.2, 4.1, 14.5, 'PTS', 12, "Weak edge"),
        (8.5, 3.2, 7.5, 'REB', 10, "Decent REB edge"),
        (8.5, 3.2, 8.0, 'REB', 10, "Marginal REB edge"),
        (3.2, 1.8, 2.5, 'AST', 8, "High variance AST"),
        (25.0, 6.0, 22.5, 'PRA', 12, "Borderline PRA"),
        (25.0, 6.0, 20.0, 'PRA', 12, "Strong PRA edge"),
        (12.0, 5.5, 10.5, 'PTS', 5, "Small sample"),
    ]
    
    print("\nTEST CASES:")
    print("-" * 80)
    print(f"{'Stat':<6} {'Mean':>6} {'Line':>6} {'Edge':>6} {'Z':>6} {'n':>4} {'Result':<12} {'Reason'}")
    print("-" * 80)
    
    for mean, std, line, stat, sample, desc in test_cases:
        result = sdg.check(mean, std, line, stat, sample)
        edge = abs(line - mean)
        z = abs((line - mean) / std)
        status = "✓ PASS" if result.passed else "✗ FAIL"
        if result.result == SDGResult.PENALIZED:
            status = "⚠ PENALTY"
        print(f"{stat:<6} {mean:>6.1f} {line:>6.1f} {edge:>6.1f} {z:>6.2f} {sample:>4} {status:<12} {result.reason[:35]}")
    
    print("\n" + sdg.get_summary())
