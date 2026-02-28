#!/usr/bin/env python3
"""
MULTI_WINDOW_PROJECTION.PY — SOP v2.1 QUANT FRAMEWORK
=====================================================
Implements professional-grade weighted multi-window projections.

THIS WAS MISSING FROM YOUR SYSTEM.

Your system only used L10. Professional quants use:
- L3:  10% weight (hot hand detection)
- L5:  25% weight (recent form)
- L10: 30% weight (stable trend)
- L20: 20% weight (baseline)
- Season: 15% weight (anchor)

Version: 2.1.0
Author: SOP v2.1 Integration
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics
import math


# ============================================================================
# CONFIGURATION
# ============================================================================

WINDOW_WEIGHTS = {
    "L3": 0.10,     # Last 3 games — hot hand detection
    "L5": 0.25,     # Last 5 games — recent form
    "L10": 0.30,    # Last 10 games — stable trend
    "L20": 0.20,    # Last 20 games — baseline
    "season": 0.15  # Season average — anchor
}

# Minimum games required for each window to be valid
WINDOW_MINIMUMS = {
    "L3": 3,
    "L5": 5,
    "L10": 8,      # Allow 8+ for L10
    "L20": 15,     # Allow 15+ for L20
    "season": 10   # Need at least 10 for season
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class WindowStats:
    """Statistics for a single time window"""
    window_name: str
    games_available: int
    average: float
    std_dev: float
    min_value: float
    max_value: float
    hit_rate_vs_line: Optional[float] = None  # % of games that hit OVER
    is_valid: bool = True
    weight_used: float = 0.0


@dataclass
class MultiWindowProjection:
    """Complete multi-window projection output"""
    player_id: str
    player_name: str
    stat_type: str
    line: float
    
    # Individual windows
    windows: Dict[str, WindowStats]
    
    # Final outputs
    weighted_projection: float
    combined_std_dev: float
    z_score: float
    
    # Weights actually used (may differ if some windows invalid)
    weights_used: Dict[str, float]
    total_weight: float


# ============================================================================
# PROJECTION ENGINE
# ============================================================================

class MultiWindowProjectionEngine:
    """
    Professional quant-grade projection engine using weighted multi-window averages.
    
    Key features:
    - 5 time windows with calibrated weights
    - Automatic weight redistribution if windows are missing
    - Combined standard deviation calculation
    - Z-score calculation vs line
    """
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or WINDOW_WEIGHTS
        
    def calculate_projection(
        self,
        player_id: str,
        player_name: str,
        stat_type: str,
        game_log: List[float],
        line: float
    ) -> MultiWindowProjection:
        """
        Calculate weighted multi-window projection.
        
        Args:
            player_id: Unique player identifier
            player_name: Display name
            stat_type: points, assists, rebounds, etc.
            game_log: List of stat values, most recent first [game_1, game_2, ...]
            line: The betting line to compare against
            
        Returns:
            MultiWindowProjection with all calculations
        """
        
        # Calculate each window
        windows = {}
        
        windows["L3"] = self._calculate_window("L3", game_log, 3, line)
        windows["L5"] = self._calculate_window("L5", game_log, 5, line)
        windows["L10"] = self._calculate_window("L10", game_log, 10, line)
        windows["L20"] = self._calculate_window("L20", game_log, 20, line)
        windows["season"] = self._calculate_window("season", game_log, len(game_log), line)
        
        # Calculate weighted projection with weight redistribution
        weighted_projection, weights_used, total_weight = self._calculate_weighted_average(windows)
        
        # Calculate combined standard deviation
        combined_std = self._calculate_combined_std(windows, weights_used)
        
        # Calculate z-score vs line
        z_score = (weighted_projection - line) / combined_std if combined_std > 0 else 0
        
        return MultiWindowProjection(
            player_id=player_id,
            player_name=player_name,
            stat_type=stat_type,
            line=line,
            windows=windows,
            weighted_projection=round(weighted_projection, 2),
            combined_std_dev=round(combined_std, 2),
            z_score=round(z_score, 3),
            weights_used=weights_used,
            total_weight=round(total_weight, 3)
        )
    
    def _calculate_window(
        self,
        window_name: str,
        game_log: List[float],
        num_games: int,
        line: float
    ) -> WindowStats:
        """Calculate statistics for a single window"""
        
        min_required = WINDOW_MINIMUMS.get(window_name, num_games)
        
        # Get the games for this window
        window_games = game_log[:num_games]
        games_available = len(window_games)
        
        # Check if valid
        is_valid = games_available >= min_required
        
        if not is_valid or games_available == 0:
            return WindowStats(
                window_name=window_name,
                games_available=games_available,
                average=0.0,
                std_dev=0.0,
                min_value=0.0,
                max_value=0.0,
                hit_rate_vs_line=None,
                is_valid=False,
                weight_used=0.0
            )
        
        # Calculate stats
        avg = statistics.mean(window_games)
        std = statistics.stdev(window_games) if len(window_games) > 1 else avg * 0.15
        
        # Hit rate vs line
        hits = sum(1 for g in window_games if g > line)
        hit_rate = hits / len(window_games)
        
        return WindowStats(
            window_name=window_name,
            games_available=games_available,
            average=round(avg, 2),
            std_dev=round(std, 2),
            min_value=min(window_games),
            max_value=max(window_games),
            hit_rate_vs_line=round(hit_rate, 3),
            is_valid=True,
            weight_used=0.0  # Set later
        )
    
    def _calculate_weighted_average(
        self,
        windows: Dict[str, WindowStats]
    ) -> Tuple[float, Dict[str, float], float]:
        """
        Calculate weighted average with automatic weight redistribution.
        
        If a window is invalid, its weight is redistributed proportionally
        to the remaining valid windows.
        """
        
        # Find valid windows
        valid_windows = {k: v for k, v in windows.items() if v.is_valid}
        
        if not valid_windows:
            return 0.0, {}, 0.0
        
        # Get original weights for valid windows
        original_weights = {k: self.weights[k] for k in valid_windows}
        total_original = sum(original_weights.values())
        
        # Redistribute to sum to 1.0
        weights_used = {k: w / total_original for k, w in original_weights.items()}
        
        # Calculate weighted average
        weighted_sum = sum(
            windows[k].average * weights_used[k]
            for k in weights_used
        )
        
        # Update window objects with weights used
        for k, w in weights_used.items():
            windows[k].weight_used = round(w, 3)
        
        return weighted_sum, weights_used, sum(weights_used.values())
    
    def _calculate_combined_std(
        self,
        windows: Dict[str, WindowStats],
        weights_used: Dict[str, float]
    ) -> float:
        """
        Calculate combined standard deviation using weighted average of variances.
        
        Formula: sqrt(sum(w_i * σ_i²))
        """
        
        if not weights_used:
            return 0.0
        
        weighted_variance = sum(
            weights_used[k] * (windows[k].std_dev ** 2)
            for k in weights_used
            if windows[k].is_valid
        )
        
        return math.sqrt(weighted_variance)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_player_specific_weights(player_name: str) -> Dict[str, float]:
    """
    Get player-specific window weights from player_configs.py.
    
    Returns default weights if player not configured.
    """
    try:
        from config.player_configs import get_player_config_manager
        manager = get_player_config_manager()
        config = manager.get_config(player_name)
        
        if config and config.window_weights:
            return config.window_weights.to_dict()
    except ImportError:
        pass
    
    return WINDOW_WEIGHTS


def project_player_stat(
    player_id: str,
    player_name: str,
    stat_type: str,
    game_log: List[float],
    line: float,
    use_player_weights: bool = True
) -> MultiWindowProjection:
    """
    Convenience function for single-player projection.
    
    If use_player_weights=True, looks up player-specific window weights
    from player_configs.py (e.g., Jokic uses longer windows, ANT uses shorter).
    
    Example:
        game_log = [8, 7, 9, 6, 8, 7, 10, 5, 8, 9]  # Last 10 games, most recent first
        result = project_player_stat("thompson_001", "Amen Thompson", "assists", game_log, 5.5)
        print(f"Projection: {result.weighted_projection}")
        print(f"Z-score: {result.z_score}")
    """
    if use_player_weights:
        weights = get_player_specific_weights(player_name)
    else:
        weights = WINDOW_WEIGHTS
    
    engine = MultiWindowProjectionEngine(weights=weights)
    return engine.calculate_projection(player_id, player_name, stat_type, game_log, line)


def format_projection_report(projection: MultiWindowProjection) -> str:
    """Format projection as readable report"""
    
    lines = []
    lines.append(f"┌─ MULTI-WINDOW PROJECTION ─────────────────────────────────")
    lines.append(f"│  {projection.player_name}")
    lines.append(f"│  {projection.stat_type.upper()} vs Line {projection.line}")
    lines.append(f"│")
    lines.append(f"│  Windows:")
    
    for name in ["L3", "L5", "L10", "L20", "season"]:
        w = projection.windows.get(name)
        if w and w.is_valid:
            hit_pct = f"{w.hit_rate_vs_line:.0%}" if w.hit_rate_vs_line else "N/A"
            lines.append(
                f"│    {name:6s}: {w.average:5.1f} (σ={w.std_dev:.1f}, n={w.games_available:2d}, "
                f"hit={hit_pct}, wt={w.weight_used:.0%})"
            )
        else:
            lines.append(f"│    {name:6s}: INSUFFICIENT DATA")
    
    lines.append(f"│")
    lines.append(f"│  Weighted Projection: {projection.weighted_projection}")
    lines.append(f"│  Combined Std Dev:    {projection.combined_std_dev}")
    lines.append(f"│  Z-Score vs Line:     {projection.z_score:+.2f}σ")
    
    # Interpretation
    if projection.z_score > 0.5:
        interp = "→ Line is BELOW projection (favors OVER)"
    elif projection.z_score < -0.5:
        interp = "→ Line is ABOVE projection (favors UNDER)"
    else:
        interp = "→ Line is NEAR projection (coin flip)"
    lines.append(f"│  {interp}")
    
    lines.append(f"└───────────────────────────────────────────────────────────")
    
    return "\n".join(lines)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test with Amen Thompson example
    # His last 10 games assists (made up for demo, most recent first)
    game_log = [8, 9, 7, 10, 6, 8, 5, 9, 7, 8, 6, 7, 5, 8, 9, 7, 6, 8, 5, 7]
    
    result = project_player_stat(
        player_id="thompson_001",
        player_name="Amen Thompson",
        stat_type="assists",
        game_log=game_log,
        line=5.5
    )
    
    print(format_projection_report(result))
    print()
    print(f"JSON Output Preview:")
    print(f"  weighted_projection: {result.weighted_projection}")
    print(f"  z_score: {result.z_score}")
    print(f"  weights_used: {result.weights_used}")
