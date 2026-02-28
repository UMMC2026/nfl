#!/usr/bin/env python3
"""
Fetch REAL last 10 game stats for OKC @ HOU players from NBA API
"""
from nba_api.stats.endpoints import leaguedashplayerstats
import pandas as pd

print("🏀 Fetching official NBA Last 10 Games stats from NBA API...")

try:
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2025-26",
        per_mode_detailed="PerGame",
        last_n_games=10,
    )
    df = stats.get_data_frames()[0]
    
    # Filter for OKC and HOU players
    okc_hou = df[df['TEAM_ABBREVIATION'].isin(['OKC', 'HOU'])].copy()
    
    # Sort by team and points
    okc_hou = okc_hou.sort_values(['TEAM_ABBREVIATION', 'PTS'], ascending=[True, False])
    
    print(f"\n✅ Found {len(okc_hou)} OKC/HOU players with Last 10 Games data\n")
    print("="*100)
    
    for _, row in okc_hou.iterrows():
        name = row['PLAYER_NAME']
        team = row['TEAM_ABBREVIATION']
        gp = int(row['GP'])
        pts = float(row['PTS'])
        reb = float(row['REB'])
        ast = float(row['AST'])
        fg3m = float(row['FG3M'])
        stl = float(row['STL'])
        blk = float(row['BLK'])
        tov = float(row['TOV'])
        
        print(f"{name} ({team}) - {gp} games:")
        print(f"  PTS: {pts:.1f} | REB: {reb:.1f} | AST: {ast:.1f} | 3PM: {fg3m:.1f}")
        print(f"  STL: {stl:.1f} | BLK: {blk:.1f} | TOV: {tov:.1f}")
        print(f"  PRA: {pts+reb+ast:.1f} | PA: {pts+ast:.1f} | RA: {reb+ast:.1f}")
        print()
    
    print("\n" + "="*100)
    print("💾 Now compare these REAL stats to the placeholder values in extended_stats_dict.py")
    print("   If they differ significantly, that's why Houston lines looked 'unbeatable'\n")
    
except Exception as e:
    print(f"❌ Error fetching NBA stats: {e}")
    print("\nNote: NBA API may be rate-limited or unavailable.")
    print("Ensure nba_api is installed: pip install nba_api")
