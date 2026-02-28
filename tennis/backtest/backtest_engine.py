"""
Tennis Backtest Engine
======================
Truth-checker for historical predictions.
Measures actual win rates by engine and tier.

Minimum acceptable metrics:
    TOTAL_SETS:  ≥58%
    PLAYER_ACES: ≥56%
    TOTAL_GAMES: ≥55%
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class BacktestResult:
    engine: str
    total: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    roi: float
    by_tier: Dict[str, Dict]
    
    def to_dict(self) -> Dict:
        return {
            "engine": self.engine,
            "total": self.total,
            "wins": self.wins,
            "losses": self.losses,
            "pushes": self.pushes,
            "win_rate": round(self.win_rate, 4),
            "roi": round(self.roi, 4),
            "by_tier": self.by_tier,
        }


def match_prediction_to_result(pred: Dict, results: Dict) -> Optional[str]:
    """
    Match a prediction to its result.
    
    Returns: "WIN", "LOSS", "PUSH", or None if no match
    """
    # Build match key
    if "players" in pred:
        players = tuple(sorted(p.lower() for p in pred["players"]))
    elif "player" in pred:
        players = (pred["player"].lower(), pred.get("opponent", "").lower())
    else:
        return None
    
    line = pred.get("line")
    direction = pred.get("direction", "").upper()
    
    # Find matching result
    for match_id, res in results.items():
        res_players = tuple(sorted(p.lower() for p in res.get("players", [])))
        
        if players != res_players:
            continue
        
        actual = res.get("actual_total")
        if actual is None:
            continue
        
        # Determine outcome
        if direction == "OVER":
            if actual > line:
                return "WIN"
            elif actual < line:
                return "LOSS"
            else:
                return "PUSH"
        elif direction == "UNDER":
            if actual < line:
                return "WIN"
            elif actual > line:
                return "LOSS"
            else:
                return "PUSH"
    
    return None


def backtest(predictions: List[Dict], results: Dict) -> Dict[str, BacktestResult]:
    """
    Run backtest on historical predictions.
    
    Args:
        predictions: List of edge predictions
        results: Dict of match_id -> result data
    
    Returns:
        Dict of engine -> BacktestResult
    """
    # Group by engine
    by_engine = defaultdict(list)
    for p in predictions:
        engine = p.get("engine", "UNKNOWN")
        by_engine[engine].append(p)
    
    engine_results = {}
    
    for engine, preds in by_engine.items():
        wins = 0
        losses = 0
        pushes = 0
        
        tier_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0})
        
        for p in preds:
            outcome = match_prediction_to_result(p, results)
            tier = p.get("tier", "UNKNOWN")
            
            if outcome == "WIN":
                wins += 1
                tier_stats[tier]["wins"] += 1
            elif outcome == "LOSS":
                losses += 1
                tier_stats[tier]["losses"] += 1
            elif outcome == "PUSH":
                pushes += 1
            
            if outcome in ("WIN", "LOSS"):
                tier_stats[tier]["total"] += 1
        
        total = wins + losses
        win_rate = wins / max(1, total)
        
        # ROI assuming -110 lines (1.91 decimal)
        # Win: +0.91 unit, Loss: -1.0 unit
        roi = (wins * 0.91 - losses) / max(1, total)
        
        # Calculate tier win rates
        by_tier = {}
        for tier, stats in tier_stats.items():
            t_total = stats["total"]
            t_wr = stats["wins"] / max(1, t_total)
            by_tier[tier] = {
                "wins": stats["wins"],
                "losses": stats["losses"],
                "total": t_total,
                "win_rate": round(t_wr, 4),
            }
        
        engine_results[engine] = BacktestResult(
            engine=engine,
            total=total,
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=win_rate,
            roi=roi,
            by_tier=by_tier,
        )
    
    return engine_results


def check_thresholds(results: Dict[str, BacktestResult]) -> Tuple[bool, List[str]]:
    """
    Check if engines meet minimum acceptable thresholds.
    
    Returns: (passed, list of violations)
    """
    thresholds = {
        "TOTAL_SETS_ENGINE": 0.58,
        "PLAYER_ACES_ENGINE": 0.56,
        "TOTAL_GAMES_ENGINE": 0.55,
    }
    
    violations = []
    
    for engine, threshold in thresholds.items():
        if engine in results:
            res = results[engine]
            if res.total >= 20 and res.win_rate < threshold:  # Min sample size
                violations.append(
                    f"{engine}: {res.win_rate:.1%} < {threshold:.0%} threshold "
                    f"(n={res.total})"
                )
    
    return len(violations) == 0, violations


def print_backtest_report(results: Dict[str, BacktestResult]):
    """Print formatted backtest report."""
    
    print("=" * 60)
    print("TENNIS BACKTEST REPORT")
    print("=" * 60)
    
    for engine, res in sorted(results.items()):
        print(f"\n{engine}")
        print("-" * 40)
        print(f"  Record: {res.wins}W - {res.losses}L - {res.pushes}P")
        print(f"  Win Rate: {res.win_rate:.1%}")
        print(f"  ROI: {res.roi:+.1%}")
        
        if res.by_tier:
            print("  By Tier:")
            for tier, stats in sorted(res.by_tier.items()):
                print(f"    {tier}: {stats['wins']}W-{stats['losses']}L ({stats['win_rate']:.1%})")
    
    # Threshold check
    passed, violations = check_thresholds(results)
    
    print("\n" + "=" * 60)
    if passed:
        print("✅ ALL THRESHOLDS MET")
    else:
        print("❌ THRESHOLD VIOLATIONS:")
        for v in violations:
            print(f"   • {v}")
    print("=" * 60)
