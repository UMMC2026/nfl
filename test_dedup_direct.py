#!/usr/bin/env python3
"""
Direct deduplication test - bypasses menu system.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from ufa.ingest.telegram_tracker import TelegramSentTracker
from pathlib import Path
import json

async def test_dedup():
    """Test deduplication logic."""
    
    tracker = TelegramSentTracker()
    
    # Load picks
    with open('picks_hydrated.json') as f:
        all_picks = json.load(f)
    
    # Filter to SLAM/STRONG
    slam_strong = [p for p in all_picks if p.get('tier') in ['SLAM', 'STRONG']]
    
    print(f"📊 Loaded {len(slam_strong)} SLAM/STRONG picks")
    
    # Test dedup
    new_picks, already_sent = tracker.filter_new_picks(slam_strong)
    
    print(f"\n🔍 Deduplication Check:")
    print(f"  ✅ New picks: {len(new_picks)}")
    print(f"  ⏭️  Already sent: {len(already_sent)}")
    
    if already_sent:
        print(f"\n📋 Already sent (will be skipped):")
        for pick in already_sent[:3]:
            print(f"   • {pick['player']} | {pick['stat']} | {pick['line']}")
        if len(already_sent) > 3:
            print(f"   ... and {len(already_sent) - 3} more")
    
    if new_picks:
        print(f"\n🆕 New picks (would be sent):")
        for pick in new_picks[:3]:
            print(f"   • {pick['player']} | {pick['stat']} | {pick['line']}")
        if len(new_picks) > 3:
            print(f"   ... and {len(new_picks) - 3} more")
    else:
        print(f"\n✅ No NEW picks to send - all {len(already_sent)} already sent!")

if __name__ == '__main__':
    asyncio.run(test_dedup())
