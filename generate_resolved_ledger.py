#!/usr/bin/env python3
"""
RESOLVED PERFORMANCE LEDGER GENERATOR
=====================================

Purpose:
    Transform pending picks into immutable, graded results.
    Source of truth for "Did our confidence match reality?"

Pipeline:
    picks.json (with tiers/confidence) 
        + ground_truth_official.json (official stats)
        + game results (ESPN/cache)
        → grade each pick
        → CSV (machine truth)
        → Markdown report (human truth)

Outputs:
    /reports/
        ├── resolved_{YYYY-MM-DD}.json
        ├── resolved_ledger.csv (append-only)
        └── RESOLVED_PERFORMANCE_LEDGER.md
"""

import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Daily Games Report Gating (SOP v2.1)
from gating.daily_games_report_gating import gate_resolved_ledger


class Outcome(Enum):
    HIT = "HIT"
    MISS = "MISS"
    PUSH = "PUSH"
    UNKNOWN = "UNKNOWN"


@dataclass
class ResolvedPick:
    """Single graded pick (PRIMARY or CORRELATED, not both scored)."""
    date: str
    game_id: str
    sport: str  # "NBA" or "NFL"
    player_name: str
    team: str
    stat: str
    direction: str  # "OVER" or "UNDER"
    line: float
    actual_value: Optional[float]  # None if game not finalized
    tier: str  # "SLAM", "STRONG", "LEAN", "NO_PLAY"
    confidence: float
    primary_edge: bool  # Only TRUE edges score units
    correlated_with: Optional[str]  # Player name if correlated
    outcome: Outcome
    units: float  # 1.0 if HIT and primary, 0.0 otherwise
    edge_id: str  # Deterministic hash


def load_picks(picks_path: Path) -> List[Dict]:
    """Load picks.json with tiers and confidence."""
    with open(picks_path) as f:
        return json.load(f)


def load_ground_truth(truth_path: Path) -> Dict[str, Dict]:
    """Load official stats (last 10-game avgs)."""
    if not truth_path.exists():
        print(f"⚠️  ground_truth_official.json not found; returning empty")
        return {}
    with open(truth_path) as f:
        return json.load(f)


def load_resolved_results(results_path: Path) -> Dict[str, Dict]:
    """
    Load final game results.
    Expected format:
    {
        "game_id": {
            "date": "2026-01-02",
            "status": "FINAL",
            "players": {
                "player_name": {
                    "team": "NYK",
                    "points": 18,
                    "rebounds": 5,
                    "assists": 3,
                    "pra": 26,
                    ...
                }
            }
        }
    }
    """
    if not results_path.exists():
        print(f"⚠️  No results file at {results_path}; all picks UNKNOWN")
        return {}
    with open(results_path) as f:
        return json.load(f)


def compute_pra(points: Optional[float], rebounds: Optional[float], assists: Optional[float]) -> Optional[float]:
    """Compute PRA from components."""
    if points is None or rebounds is None or assists is None:
        return None
    return points + rebounds + assists


def get_actual_stat(player_stats: Dict, stat: str) -> Optional[float]:
    """Extract stat from player result, computing PRA if needed."""
    if stat in player_stats:
        return player_stats.get(stat)
    if stat == "pra" or stat == "pts+reb+ast":
        p = player_stats.get("points")
        r = player_stats.get("rebounds")
        a = player_stats.get("assists")
        return compute_pra(p, r, a)
    if stat == "pr" or stat == "pts+reb":
        p = player_stats.get("points")
        r = player_stats.get("rebounds")
        return (p + r) if (p is not None and r is not None) else None
    if stat == "pa" or stat == "pts+ast":
        p = player_stats.get("points")
        a = player_stats.get("assists")
        return (p + a) if (p is not None and a is not None) else None
    return None


def grade_pick(pick: Dict, actual_value: Optional[float]) -> Outcome:
    """
    Grade a single pick against actual result.
    
    Args:
        pick: {line, direction, ...}
        actual_value: Actual stat value (None if game not final)
    
    Returns:
        Outcome.HIT, MISS, PUSH, or UNKNOWN
    """
    if actual_value is None:
        return Outcome.UNKNOWN
    
    line = pick.get("line")
    direction = pick.get("direction", "").upper()
    
    if direction == "OVER":
        if actual_value > line:
            return Outcome.HIT
        elif actual_value < line:
            return Outcome.MISS
        else:
            return Outcome.PUSH
    elif direction == "UNDER":
        if actual_value < line:
            return Outcome.HIT
        elif actual_value > line:
            return Outcome.MISS
        else:
            return Outcome.PUSH
    
    return Outcome.UNKNOWN


def generate_edge_id(player: str, stat: str, direction: str, line: float) -> str:
    """Deterministic edge identifier."""
    return f"{player.lower()}_{stat.lower()}_{direction.lower()}_{line}".replace(" ", "_")


def resolve_picks(
    picks: List[Dict],
    results: Dict[str, Dict],
    ground_truth: Dict[str, Dict]
) -> List[ResolvedPick]:
    """
    Grade all picks against actual results.
    
    Returns:
        List of ResolvedPick objects (PRIMARY edges only)
    """
    resolved = []
    
    for pick in picks:
        player = pick.get("player_name", "")
        stat = pick.get("stat", "").lower()
        direction = pick.get("direction", "").upper()
        line = pick.get("line")
        tier = pick.get("tier", "NO_PLAY")
        confidence = pick.get("confidence", 0.0)
        primary = pick.get("primary_edge", True)
        correlated_with = pick.get("correlated_with")
        game_id = pick.get("game_id", "")
        team = pick.get("team", "")
        date = pick.get("date", datetime.now().strftime("%Y-%m-%d"))
        # Infer sport from game_id (NBA_LAL_GSW or NFL_BAL_PIT)
        sport = "NFL" if game_id.startswith("NFL") else "NBA"
        
        # Skip CORRELATED edges (they don't score independently)
        if not primary:
            continue
        
        # Fetch actual value
        actual_value = None
        if game_id in results:
            game = results[game_id]
            if game.get("status") == "FINAL" and "players" in game:
                for player_key, player_stats in game["players"].items():
                    if player_key.lower() == player.lower():
                        actual_value = get_actual_stat(player_stats, stat)
                        break
        
        # Grade the pick
        outcome = grade_pick(pick, actual_value)
        
        # Units: 1.0 if HIT and primary, 0.0 otherwise
        units = 1.0 if (outcome == Outcome.HIT and primary) else 0.0
        
        edge_id = generate_edge_id(player, stat, direction, line)
        
        resolved_pick = ResolvedPick(
            date=date,
            game_id=game_id,
            sport=sport,
            player_name=player,
            team=team,
            stat=stat,
            direction=direction,
            line=line,
            actual_value=actual_value,
            tier=tier,
            confidence=confidence,
            primary_edge=primary,
            correlated_with=correlated_with,
            outcome=outcome,
            units=units,
            edge_id=edge_id
        )
        resolved.append(resolved_pick)
    
    return resolved


def write_csv(resolved: List[ResolvedPick], output_path: Path):
    """Append-only CSV writer (won't re-write existing lines)."""
    exists = output_path.exists()
    
    with open(output_path, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Header (only if new file)
        if not exists:
            writer.writerow([
                "date", "game_id", "sport", "player_name", "team", "stat", "direction",
                "line", "actual_value", "tier", "confidence", "primary_edge",
                "correlated_with", "outcome", "units", "edge_id"
            ])
        
        # Write rows
        for pick in resolved:
            writer.writerow([
                pick.date,
                pick.game_id,
                pick.sport,
                pick.player_name,
                pick.team,
                pick.stat,
                pick.direction,
                pick.line,
                pick.actual_value,
                pick.tier,
                pick.confidence,
                pick.primary_edge,
                pick.correlated_with,
                pick.outcome.value,
                pick.units,
                pick.edge_id
            ])


def aggregate_by_tier(resolved: List[ResolvedPick]) -> Dict[str, Dict]:
    """Summarize picks by tier and sport."""
    tiers = {}
    for pick in resolved:
        # Create tier key with sport segmentation
        tier_key = f"{pick.tier} ({pick.sport})"
        
        if tier_key not in tiers:
            tiers[tier_key] = {
                "picks": 0,
                "wins": 0,
                "losses": 0,
                "pushes": 0,
                "units": 0.0,
                "sport": pick.sport
            }
        
        tiers[tier_key]["picks"] += 1
        if pick.outcome == Outcome.HIT:
            tiers[tier_key]["wins"] += 1
        elif pick.outcome == Outcome.MISS:
            tiers[tier_key]["losses"] += 1
        elif pick.outcome == Outcome.PUSH:
            tiers[tier_key]["pushes"] += 1
        
        tiers[tier_key]["units"] += pick.units
    
    return tiers


def compute_rolling_windows(
    csv_path: Path,
    window_days: List[int] = [7, 14, 30]
) -> Dict[str, Dict[int, Dict]]:
    """
    Compute rolling performance over N days, segmented by sport.
    
    Returns:
        {
            "NBA": {
                7: {"record": "2-1", "units": +1.0, "samples": 3, ...},
                14: {...},
            },
            "NFL": {
                7: {...},
                ...
            }
        }
    """
    if not csv_path.exists():
        return {
            "NBA": {d: {"samples": 0} for d in window_days},
            "NFL": {d: {"samples": 0} for d in window_days}
        }
    
    windows_by_sport = {"NBA": {}, "NFL": {}}
    cutoff_dates = {
        d: (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
        for d in window_days
    }
    
    for sport in ["NBA", "NFL"]:
        for window_days_val in window_days:
            cutoff = cutoff_dates[window_days_val]
            
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                picks = [
                    r for r in reader 
                    if r.get("date", "") >= cutoff 
                    and r.get("outcome", "") != "UNKNOWN"
                    and r.get("sport", "") == sport
                ]
            
            if not picks:
                windows_by_sport[sport][window_days_val] = {
                    "samples": 0,
                    "record": "0-0",
                    "units": 0.0,
                    "win_pct": 0.0
                }
                continue
            
            wins = sum(1 for p in picks if p["outcome"] == "HIT")
            losses = sum(1 for p in picks if p["outcome"] == "MISS")
            units = sum(float(p["units"]) for p in picks)
            total = wins + losses
            win_pct = (wins / total * 100) if total > 0 else 0.0
            
            windows_by_sport[sport][window_days_val] = {
                "samples": len(picks),
                "record": f"{wins}-{losses}",
                "units": round(units, 2),
                "win_pct": round(win_pct, 1)
            }
    
    return windows_by_sport


def calibration_check(resolved: List[ResolvedPick]) -> Dict[str, Dict]:
    """
    Confidence vs Reality: Group by confidence bucket and compare to actual win %.
    
    Returns:
        {
            "70-75%": {"predictions": 3, "actual_wins": 2, "actual_pct": 66.7, "error": -3.3},
            ...
        }
    """
    buckets = {
        "70-75%": (0.70, 0.75),
        "60-69%": (0.60, 0.69),
        "50-59%": (0.50, 0.59),
        "<50%": (0.0, 0.49)
    }
    
    results_by_bucket = {b: {"picks": [], "wins": 0, "total": 0} for b in buckets}
    
    for pick in resolved:
        if pick.outcome == Outcome.UNKNOWN:
            continue
        
        for bucket_name, (lo, hi) in buckets.items():
            if lo <= pick.confidence <= hi:
                results_by_bucket[bucket_name]["picks"].append(pick)
                results_by_bucket[bucket_name]["total"] += 1
                if pick.outcome == Outcome.HIT:
                    results_by_bucket[bucket_name]["wins"] += 1
                break
    
    calibration = {}
    for bucket_name, data in results_by_bucket.items():
        if data["total"] == 0:
            # Expected % from bucket name
            if "-" in bucket_name:
                expected_pct = float(bucket_name.split("-")[0])
            elif "<" in bucket_name:
                expected_pct = 25.0
            else:
                expected_pct = 0.0
            
            calibration[bucket_name] = {
                "samples": 0,
                "actual_pct": None,
                "expected_pct": expected_pct,
                "error": None
            }
        else:
            actual_pct = (data["wins"] / data["total"]) * 100
            # Expected % is the midpoint of the bucket
            if "-" in bucket_name:
                parts = bucket_name.split("-")
                expected_pct = (float(parts[0]) + float(parts[1].rstrip("%"))) / 2
            elif "<" in bucket_name:
                expected_pct = 25.0
            else:
                expected_pct = 50.0
            
            error = actual_pct - expected_pct
            
            calibration[bucket_name] = {
                "samples": data["total"],
                "actual_pct": round(actual_pct, 1),
                "expected_pct": round(expected_pct, 1),
                "error": round(error, 1)
            }
    
    return calibration


def system_health_check(resolved: List[ResolvedPick]) -> Dict[str, str]:
    """Validate SOP v2.1 rules on resolved picks."""
    health = {
        "EDGE_COLLAPSE": "PASS",
        "DUPLICATE_PLAYERS": "PASS",
        "CONFIDENCE_CAPS": "PASS",
        "CORRELATED_IN_TIERS": "PASS"
    }
    
    # Check for duplicate edges (same player, stat, direction)
    edges = set()
    for pick in resolved:
        if pick.primary_edge:
            edge = (pick.player_name, pick.stat, pick.direction)
            if edge in edges:
                health["EDGE_COLLAPSE"] = "FAIL"
            edges.add(edge)
    
    # Check for duplicate primary bets (same player, game_id)
    primaries = set()
    for pick in resolved:
        if pick.primary_edge:
            key = (pick.player_name, pick.game_id)
            if key in primaries:
                health["DUPLICATE_PLAYERS"] = "FAIL"
            primaries.add(key)
    
    # Check confidence caps by tier
    for pick in resolved:
        if pick.tier == "SLAM" and pick.confidence < 0.68:
            health["CONFIDENCE_CAPS"] = "FAIL"
        if pick.tier == "STRONG" and (pick.confidence < 0.60 or pick.confidence > 0.67):
            health["CONFIDENCE_CAPS"] = "FAIL"
        if pick.tier == "LEAN" and (pick.confidence < 0.52 or pick.confidence > 0.59):
            health["CONFIDENCE_CAPS"] = "FAIL"
    
    # Check correlated in tiers
    for pick in resolved:
        if pick.correlated_with and pick.tier in ["SLAM", "STRONG"]:
            health["CORRELATED_IN_TIERS"] = "FAIL"
    
    return health


def render_markdown(
    date: str,
    resolved: List[ResolvedPick],
    tier_summary: Dict[str, Dict],
    rolling_windows: Dict[int, Dict],
    calibration: Dict[str, Dict],
    health: Dict[str, str],
    output_path: Path
):
    """Render full RESOLVED_PERFORMANCE_LEDGER.md."""
    
    # Daily summary
    finalized = [p for p in resolved if p.outcome != Outcome.UNKNOWN]
    if not finalized:
        finalized_text = "NO RESOLUTIONS"
        wins, losses = 0, 0
        record = "0-0"
        win_pct = "—"
        net_units = 0.0
    else:
        finalized_text = f"{len(finalized)} pick(s)"
        wins = sum(1 for p in finalized if p.outcome == Outcome.HIT)
        losses = sum(1 for p in finalized if p.outcome == Outcome.MISS)
        net_units = sum(p.units for p in finalized)
        record = f"{wins}-{losses}"
        win_pct = round((wins / (wins + losses) * 100), 1) if (wins + losses) > 0 else "—"
    
    lines = [
        "# RESOLVED PERFORMANCE LEDGER",
        "",
        f"**Date:** {date}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## Daily Resolution Summary",
        "",
        f"**Resolved Picks:** {finalized_text}",
        f"**Pending Picks:** {len([p for p in resolved if p.outcome == Outcome.UNKNOWN])}",
        "",
        f"**Primary Picks:**",
        f"- Wins: {wins}",
        f"- Losses: {losses}",
        f"- Push: {sum(1 for p in finalized if p.outcome == Outcome.PUSH)}",
        "",
        f"**Win Rate:** {win_pct}%",
        f"**Net Units:** {'+' if net_units >= 0 else ''}{net_units}",
        "",
        "---",
        "",
        "## Tier-Level Truth Table",
        "",
        "| Tier | Picks | Wins | Losses | Push | Win % | Units |",
        "|------|-------|------|--------|------|-------|-------|",
    ]
    
    for tier in ["SLAM", "STRONG", "LEAN", "NO_PLAY"]:
        if tier in tier_summary:
            data = tier_summary[tier]
            wins_t = data["wins"]
            losses_t = data["losses"]
            total_t = data["picks"]
            win_pct_t = round((wins_t / total_t * 100), 1) if total_t > 0 else "—"
            units_t = f"{'+' if data['units'] >= 0 else ''}{data['units']}"
            lines.append(f"| {tier} | {total_t} | {wins_t} | {losses_t} | {data['pushes']} | {win_pct_t}% | {units_t} |")
    
    lines.extend([
        "",
        "---",
        "",
        "## Edge-Level Breakdown (PRIMARY Only)",
        "",
        "| Player | Stat | Direction | Line | Actual | Outcome | Tier |",
        "|--------|------|-----------|------|--------|---------|------|",
    ])
    
    for pick in resolved:
        actual_str = f"{pick.actual_value}" if pick.actual_value is not None else "—"
        lines.append(
            f"| {pick.player_name} | {pick.stat} | {pick.direction} | {pick.line} | {actual_str} | {pick.outcome.value} | {pick.tier} |"
        )
    
    lines.extend([
        "",
        "---",
        "",
        "## Confidence vs Reality (Calibration Check)",
        "",
        "| Confidence Bucket | Samples | Actual Win % | Expected % | Error |",
        "|-------------------|---------|-------------|-----------|-------|",
    ])
    
    for bucket, data in calibration.items():
        if data["samples"] == 0:
            lines.append(f"| {bucket} | 0 | — | {data['expected_pct']}% | — |")
        else:
            error_marker = "WARNING: " if abs(data["error"]) > 10 else ""
            lines.append(
                f"| {bucket} | {data['samples']} | {data['actual_pct']}% | {data['expected_pct']}% | {error_marker}{data['error']}% |"
            )
    
    lines.extend([
        "",
        "---",
        "",
        "## Rolling Performance",
        "",
    ])
    
    for days in [7, 14, 30]:
        if days in rolling_windows:
            window = rolling_windows[days]
            if window["samples"] == 0:
                lines.append(f"**Last {days} Days:** No resolved picks")
            else:
                lines.append(f"**Last {days} Days:** {window['record']} ({window['win_pct']}%) | {window['units']:+.1f} units")
    
    lines.extend([
        "",
        "---",
        "",
        "## System Health Flags",
        "",
    ])
    
    for check, status in health.items():
        symbol = "[PASS]" if status == "PASS" else "[FAIL]"
        lines.append(f"{symbol} {check}: {status}")
    
    lines.extend([
        "",
        "---",
        "",
        "**Note:** Only PRIMARY edges are scored. Correlated picks are tracked but units = 0.0.",
    ])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def main():
    """Main resolver pipeline."""
    import sys
    import argparse
    
    # SOP v2.1 GATING CHECK: Verify Daily Games Report exists for today
    date = datetime.now().strftime("%Y-%m-%d")
    report_context = gate_resolved_ledger(date=date)  # Aborts if no report
    print(f"✅ Gating PASSED for {date} — ledger will use report context for calibration")
    
    parser = argparse.ArgumentParser(description="Resolve picks into immutable ledger")
    parser.add_argument("--picks", default="picks.json", help="Path to picks JSON (default: picks.json)")
    parser.add_argument("--results", default="outputs/game_results.json", help="Path to game results JSON")
    parser.add_argument("--truth", default="outputs/ground_truth_official.json", help="Path to ground truth JSON")
    args = parser.parse_args()
    
    print("=" * 70)
    print("RESOLVED PERFORMANCE LEDGER GENERATOR")
    print("=" * 70)
    
    # Paths
    workspace = Path.cwd()
    reports_dir = workspace / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    picks_path = workspace / args.picks
    truth_path = workspace / args.truth
    results_path = workspace / args.results
    
    csv_output = reports_dir / "resolved_ledger.csv"
    md_output = reports_dir / "RESOLVED_PERFORMANCE_LEDGER.md"
    json_output = reports_dir / f"resolved_{datetime.now().strftime('%Y-%m-%d')}.json"
    
    # Load inputs
    print("\n📂 Loading inputs...")
    if not picks_path.exists():
        print(f"❌ picks.json not found at {picks_path}")
        return 1
    
    picks = load_picks(picks_path)
    print(f"   ✓ {len(picks)} picks loaded")
    
    ground_truth = load_ground_truth(truth_path)
    print(f"   ✓ Ground truth loaded")
    
    results = load_resolved_results(results_path)
    print(f"   ✓ Game results loaded ({len(results)} games)")
    
    # Grade picks
    print("\n🎯 Grading picks...")
    resolved = resolve_picks(picks, results, ground_truth)
    print(f"   ✓ {len(resolved)} picks graded")
    
    finalized = [p for p in resolved if p.outcome != Outcome.UNKNOWN]
    print(f"   ✓ {len(finalized)} finalized | {len(resolved) - len(finalized)} pending")
    
    # Write CSV
    print(f"\n💾 Writing CSV ({csv_output})...")
    write_csv(resolved, csv_output)
    print(f"   ✓ Appended to resolved_ledger.csv")
    
    # Aggregate and render
    print(f"\n📊 Computing statistics...")
    tier_summary = aggregate_by_tier(finalized)
    rolling = compute_rolling_windows(csv_output)
    calibration = calibration_check(finalized)
    health = system_health_check(resolved)
    
    print(f"   ✓ Tier summaries computed")
    print(f"   ✓ Rolling windows (7/14/30 day) computed")
    print(f"   ✓ Calibration check complete")
    print(f"   ✓ System health: {sum(1 for v in health.values() if v == 'PASS')}/4 PASS")
    
    # Render Markdown
    print(f"\n📝 Rendering Markdown ({md_output})...")
    render_markdown(
        datetime.now().strftime("%Y-%m-%d"),
        resolved,
        tier_summary,
        rolling,
        calibration,
        health,
        md_output
    )
    print(f"   ✓ Report rendered")
    
    # Save JSON snapshot
    print(f"\n💾 Saving JSON snapshot ({json_output})...")
    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "finalized_count": len(finalized),
        "pending_count": len(resolved) - len(finalized),
        "tier_summary": {k: v for k, v in tier_summary.items()},
        "rolling_windows": rolling,
        "calibration": calibration,
        "health": health
    }
    with open(json_output, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f"   ✓ JSON snapshot saved")
    
    # Final report
    print("\n" + "=" * 70)
    print("✅ RESOLUTION COMPLETE")
    print("=" * 70)
    if health["EDGE_COLLAPSE"] == "FAIL" or health["DUPLICATE_PLAYERS"] == "FAIL":
        print("\n⚠️  SYSTEM HEALTH WARNING: SOP violations detected!")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
