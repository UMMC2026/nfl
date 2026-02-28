"""
STAT ADJUSTMENT DEPRECATION NOTICE
==================================

This module contains the HARDCODED stat adjustments that should be
DEPRECATED in favor of calibration-based adjustments.

PROBLEM:
The current system uses fixed multipliers like:
    "points": 0.85,           # 45.9% hit rate -> penalize 15%
    "3pm": 0.80,              # 43.8% hit rate -> penalize 20%
    "assists": 1.10,          # 77.8% hit rate -> boost 10%

These are:
1. Based on PAST backtest data that may not generalize
2. Applied UNIFORMLY regardless of player/context
3. Not updated as calibration data changes
4. Multiplicative hacks that compound with other adjustments

SOLUTION:
Use calibration_history.csv to compute ROLLING stat-specific hit rates,
and adjust thresholds (not probabilities) accordingly.

MIGRATION PATH:
1. Keep old multipliers but mark as DEPRECATED
2. Add new calibration-based adjustment calculation
3. Feature flag to switch between old/new
4. When new system proves accurate, remove old code
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import csv

logger = logging.getLogger(__name__)

# DEPRECATED: Hardcoded stat confidence multipliers
# These should NOT be used for new development
DEPRECATED_STAT_MULTIPLIERS = {
    "points": 0.85,
    "1q_pts": 0.85,
    "1h_points": 0.85,
    "3pm": 0.80,
    "assists": 1.10,
    "pts+reb+ast": 1.08,
    "pts+reb": 1.05,
    "pts+ast": 1.05,
    "reb+ast": 1.05,
    "rebounds": 1.02,
    "steals": 0.90,
    "blocks": 0.90,
    "turnovers": 0.95,
}


class CalibrationBasedAdjuster:
    """
    Compute stat adjustments from calibration history rather than hardcoded values.
    
    This replaces the deprecated STAT_CONFIDENCE_MULTIPLIERS with data-driven
    adjustments computed from actual historical hit rates.
    """
    
    def __init__(
        self,
        history_path: Path = Path("calibration_history.csv"),
        lookback_days: int = 30,
        min_samples: int = 20,
    ):
        self.history_path = history_path
        self.lookback_days = lookback_days
        self.min_samples = min_samples
        self._cache: Dict[str, Tuple[float, int, datetime]] = {}
        self._cache_ttl = timedelta(hours=1)
    
    def _load_recent_history(self) -> list:
        """Load calibration history from the last N days."""
        if not self.history_path.exists():
            return []
        
        cutoff = datetime.now() - timedelta(days=self.lookback_days)
        records = []
        
        try:
            with open(self.history_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        date_str = row.get('date', row.get('game_date', ''))
                        if date_str:
                            date = datetime.strptime(date_str[:10], '%Y-%m-%d')
                            if date >= cutoff:
                                records.append(row)
                    except (ValueError, KeyError):
                        continue
        except Exception as e:
            logger.error(f"Failed to load calibration history: {e}")
        
        return records
    
    def compute_stat_hit_rate(self, stat: str, sport: str = "NBA") -> Tuple[float, int]:
        """
        Compute rolling hit rate for a specific stat from calibration data.
        
        Returns:
            Tuple of (hit_rate, sample_size)
        """
        # Check cache
        cache_key = f"{sport}_{stat}"
        if cache_key in self._cache:
            rate, n, cached_at = self._cache[cache_key]
            if datetime.now() - cached_at < self._cache_ttl:
                return rate, n
        
        records = self._load_recent_history()
        
        # Filter by stat
        stat_lower = stat.lower().replace(" ", "").replace("+", "_")
        matching = [
            r for r in records 
            if r.get('stat', '').lower().replace(" ", "").replace("+", "_") == stat_lower
            and r.get('sport', 'NBA').upper() == sport.upper()
        ]
        
        if len(matching) < self.min_samples:
            # Not enough data, return neutral
            return 0.50, len(matching)
        
        # Calculate hit rate
        hits = sum(1 for r in matching if r.get('result', r.get('hit', '')).lower() in ('hit', 'true', '1', 'yes'))
        total = len(matching)
        hit_rate = hits / total if total > 0 else 0.50
        
        # Cache result
        self._cache[cache_key] = (hit_rate, total, datetime.now())
        
        return hit_rate, total
    
    def get_adjustment_multiplier(self, stat: str, sport: str = "NBA") -> float:
        """
        Get calibration-based adjustment multiplier for a stat.
        
        Instead of hardcoded 0.85 for points, compute from actual hit rates.
        
        Returns:
            Multiplier to apply to raw probability (0.8 to 1.2 range)
        """
        hit_rate, n = self.compute_stat_hit_rate(stat, sport)
        
        if n < self.min_samples:
            # Not enough data, use deprecated value if available
            stat_lower = stat.lower().replace(" ", "").replace("+", "_")
            if stat_lower in DEPRECATED_STAT_MULTIPLIERS:
                logger.warning(f"Using DEPRECATED multiplier for {stat} (only {n} samples)")
                return DEPRECATED_STAT_MULTIPLIERS[stat_lower]
            return 1.0
        
        # Compute multiplier based on deviation from 50%
        # If hit_rate = 0.45, we want multiplier < 1 to penalize
        # If hit_rate = 0.75, we want multiplier > 1 to boost
        
        # Scale: 50% -> 1.0, 40% -> 0.90, 60% -> 1.10
        # Clamped to [0.80, 1.20] range
        deviation = hit_rate - 0.50
        multiplier = 1.0 + (deviation * 0.5)  # 10% hit rate change = 5% multiplier change
        
        return max(0.80, min(1.20, multiplier))
    
    def get_minimum_edge_threshold(self, stat: str, sport: str = "NBA") -> float:
        """
        Get calibration-based minimum edge threshold for a stat.
        
        Stats with lower hit rates need HIGHER edges to qualify.
        
        Returns:
            Minimum Z-score edge required (typically 0.5 to 2.0)
        """
        hit_rate, n = self.compute_stat_hit_rate(stat, sport)
        
        if n < self.min_samples:
            return 1.0  # Default threshold
        
        # Inverse relationship: lower hit rate = higher required edge
        # hit_rate 0.45 -> threshold 1.5
        # hit_rate 0.75 -> threshold 0.5
        
        if hit_rate >= 0.70:
            return 0.5
        elif hit_rate >= 0.60:
            return 0.8
        elif hit_rate >= 0.50:
            return 1.0
        elif hit_rate >= 0.45:
            return 1.5
        else:
            return 2.0  # Very underwater stat, need big edge


# Singleton instance
_adjuster: Optional[CalibrationBasedAdjuster] = None


def get_adjuster() -> CalibrationBasedAdjuster:
    """Get or create the calibration-based adjuster singleton."""
    global _adjuster
    if _adjuster is None:
        _adjuster = CalibrationBasedAdjuster()
    return _adjuster


def get_stat_multiplier(stat: str, use_deprecated: bool = True) -> float:
    """
    Get stat adjustment multiplier.
    
    Args:
        stat: Stat category (e.g., "points", "assists")
        use_deprecated: If True (default), use hardcoded values. 
                       If False, use calibration-based calculation.
    
    Returns:
        Multiplier to apply to probability (0.80 to 1.20)
    """
    if use_deprecated:
        stat_lower = stat.lower().replace(" ", "").replace("+", "_")
        return DEPRECATED_STAT_MULTIPLIERS.get(stat_lower, 1.0)
    else:
        adjuster = get_adjuster()
        return adjuster.get_adjustment_multiplier(stat)
