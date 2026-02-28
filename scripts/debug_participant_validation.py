#!/usr/bin/env python3
"""scripts/debug_participant_validation.py

Debug participant validation to see why props are being filtered.
"""

import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sources.odds_api import OddsApiClient

def main():
    client = OddsApiClient.from_env()
    if not client:
        print("❌ ODDS_API_KEY not set")
        return
    
    sport_key = "basketball_nba"
    
    # Fetch participants
    print(f"Fetching participants for {sport_key}...")
    participants, quota = client.get_participants(sport_key=sport_key)
    
    print(f"\n✓ Received {len(participants)} participants")
    print(f"  Quota: {quota.remaining} remaining, {quota.last_cost} cost")
    
    if participants:
        print("\nFirst 10 participants:")
        for p in participants[:10]:
            print(f"  - {p.get('name')} (team: {p.get('team', 'N/A')})")
    else:
        print("\n⚠️  Participant list is EMPTY")
        print("This is why props are being filtered out!")
    
    # Fetch one event to see raw prop player names
    print(f"\n\nFetching events...")
    events, _ = client.get_events(sport_key=sport_key)
    
    if events:
        event_id = events[0].get("id")
        print(f"\nFetching odds for event: {event_id}")
        
        odds_json, _ = client.get_event_odds(
            sport_key=sport_key,
            event_id=event_id,
            regions="us_dfs",
            markets="player_points",
            bookmakers="prizepicks,underdog"
        )
        
        # Extract player names from props
        player_names = set()
        for bookmaker in odds_json.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    desc = outcome.get("description", "")
                    name = outcome.get("name", "")
                    # Player name is typically in description
                    if desc:
                        player_names.add(desc)
        
        print(f"\nFound {len(player_names)} unique player names in props:")
        for name in list(player_names)[:10]:
            print(f"  - {name}")
        
        # Compare
        participant_names = {p.get('name', '').strip().lower() for p in participants if p.get('name')}
        prop_names = {name.strip().lower() for name in player_names}
        
        matches = prop_names & participant_names
        mismatches = prop_names - participant_names
        
        print(f"\n{'='*60}")
        print(f"MATCHING: {len(matches)}/{len(prop_names)} player names match participants")
        print(f"MISMATCHES: {len(mismatches)} player names NOT in participants list")
        
        if mismatches:
            print("\nMismatched players:")
            for name in list(mismatches)[:5]:
                print(f"  - {name}")

if __name__ == "__main__":
    main()
