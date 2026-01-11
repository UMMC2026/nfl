#!/usr/bin/env python3
"""
Check historical performance of picks - hits and misses from previous games
"""

import csv
from pathlib import Path
from collections import defaultdict
import sys

def load_calibration_history():
    """Load all historical picks with outcomes"""
    history_file = Path("calibration_history.csv")
    if not history_file.exists():
        print("❌ No calibration_history.csv found")
        return []
    
    with open(history_file, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)

def analyze_results(picks, date_filter=None):
    """Analyze hit rate by various dimensions"""
    
    # Filter by date if specified
    if date_filter:
        picks = [p for p in picks if p.get('slate_date') == date_filter]
    
    # Filter only picks with outcomes
    resulted = [p for p in picks if p.get('outcome') in ['HIT', 'MISS']]
    
    if not resulted:
        print(f"⚠️  No resolved picks found" + (f" for {date_filter}" if date_filter else ""))
        return
    
    hits = [p for p in resulted if p['outcome'] == 'HIT']
    misses = [p for p in resulted if p['outcome'] == 'MISS']
    
    total = len(resulted)
    hit_count = len(hits)
    hit_rate = 100 * hit_count / total if total > 0 else 0
    
    print("\n" + "="*80)
    print(f"📊 RESULTS SUMMARY" + (f" - {date_filter}" if date_filter else " - ALL TIME"))
    print("="*80)
    print(f"\n✅ HITS: {hit_count}/{total} ({hit_rate:.1f}%)")
    print(f"❌ MISSES: {len(misses)}/{total} ({100-hit_rate:.1f}%)")
    
    # By tier
    print("\n📈 BY CONFIDENCE TIER:")
    by_tier = defaultdict(lambda: {'hit': 0, 'miss': 0})
    for p in resulted:
        tier = p.get('tier_calibrated', 'UNKNOWN')
        if p['outcome'] == 'HIT':
            by_tier[tier]['hit'] += 1
        else:
            by_tier[tier]['miss'] += 1
    
    for tier in ['SLAM', 'STRONG', 'LEAN', 'BELOW']:
        if tier in by_tier:
            h = by_tier[tier]['hit']
            m = by_tier[tier]['miss']
            total_tier = h + m
            rate = 100 * h / total_tier if total_tier > 0 else 0
            print(f"   {tier:8s}: {h:3d}/{total_tier:3d} hits ({rate:5.1f}%)")
    
    # By direction
    print("\n📊 BY DIRECTION:")
    by_dir = defaultdict(lambda: {'hit': 0, 'miss': 0})
    for p in resulted:
        direction = p.get('direction', 'UNKNOWN')
        if p['outcome'] == 'HIT':
            by_dir[direction]['hit'] += 1
        else:
            by_dir[direction]['miss'] += 1
    
    for direction in ['HIGHER', 'LOWER']:
        if direction in by_dir:
            h = by_dir[direction]['hit']
            m = by_dir[direction]['miss']
            total_dir = h + m
            rate = 100 * h / total_dir if total_dir > 0 else 0
            print(f"   {direction:8s}: {h:3d}/{total_dir:3d} hits ({rate:5.1f}%)")
    
    # Top performers
    print("\n🏆 TOP PERFORMING PICKS:")
    sorted_hits = sorted(hits, key=lambda x: float(x.get('prob_calibrated', 0)), reverse=True)
    for i, pick in enumerate(sorted_hits[:10], 1):
        player = pick.get('player_name', 'Unknown')
        stat = pick.get('stat_category', '?')
        direction = pick.get('direction', '?')
        line = pick.get('line', '?')
        prob = float(pick.get('prob_calibrated', 0)) * 100
        actual = pick.get('actual_value', '?')
        print(f"   [{i:2d}] {player:25s} {stat:12s} {direction:6s} {line:5s} ({prob:5.1f}%) → {actual}")
    
    # Biggest misses
    print("\n💔 BIGGEST MISSES (High Confidence):")
    sorted_misses = sorted(misses, key=lambda x: float(x.get('prob_calibrated', 0)), reverse=True)
    for i, pick in enumerate(sorted_misses[:10], 1):
        player = pick.get('player_name', 'Unknown')
        stat = pick.get('stat_category', '?')
        direction = pick.get('direction', '?')
        line = pick.get('line', '?')
        prob = float(pick.get('prob_calibrated', 0)) * 100
        actual = pick.get('actual_value', '?')
        cause = pick.get('failure_primary_cause', 'Unknown')
        print(f"   [{i:2d}] {player:25s} {stat:12s} {direction:6s} {line:5s} ({prob:5.1f}%) → {actual}")
        print(f"        Cause: {cause}")
    
    print("\n" + "="*80)

def list_available_dates(picks):
    """Show available dates with pick counts"""
    by_date = defaultdict(int)
    by_date_resolved = defaultdict(int)
    
    for p in picks:
        date = p.get('slate_date', 'Unknown')
        by_date[date] += 1
        if p.get('outcome') in ['HIT', 'MISS']:
            by_date_resolved[date] += 1
    
    print("\n📅 AVAILABLE DATES:")
    for date in sorted(by_date.keys(), reverse=True):
        total = by_date[date]
        resolved = by_date_resolved.get(date, 0)
        print(f"   {date}: {resolved:3d}/{total:3d} picks resolved")

def main():
    picks = load_calibration_history()
    
    if not picks:
        return
    
    print(f"\n📦 Loaded {len(picks)} total picks from calibration_history.csv")
    
    # Show available dates
    list_available_dates(picks)
    
    # If date argument provided, filter to that date
    if len(sys.argv) > 1:
        date_filter = sys.argv[1]
        analyze_results(picks, date_filter=date_filter)
    else:
        # Show all-time results
        analyze_results(picks)
        
        print("\n💡 TIP: Run with date to see specific slate:")
        print("   python check_results.py 2026-01-02")

if __name__ == "__main__":
    main()
