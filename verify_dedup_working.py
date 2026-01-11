#!/usr/bin/env python3
"""
Simple deduplication verification test.
"""

from ufa.ingest.telegram_tracker import TelegramSentTracker
import json

# Create tracker
tracker = TelegramSentTracker()

# Print current history
history = tracker.history
print(f"✅ History file loaded with {len(history)} entries")

if history:
    print(f"\n📋 Currently tracked (will be skipped):")
    for key in list(history.keys())[:5]:
        pick = history[key].get('pick', {})
        player = pick.get('player', 'Unknown')
        stat = pick.get('stat', 'Unknown')
        line = pick.get('line', '?')
        sent_at = history[key]['sent_at'][:19]
        print(f"  • {player} | {stat} | {line} (sent {sent_at})")
    
    if len(history) > 5:
        print(f"  ... and {len(history) - 5} more")

# Create test picks (same as what was sent)
test_picks = []
for key in list(history.keys())[:2]:
    parts = key.split('|')
    if len(parts) == 4:
        test_picks.append({
            'date': parts[0],
            'player': parts[1],
            'stat': parts[2],
            'line': float(parts[3])
        })

if test_picks:
    print(f"\n🔍 Testing dedup with {len(test_picks)} existing picks...")
    new, already_sent = tracker.filter_new_picks(test_picks)
    print(f"  → New: {len(new)} | Already sent: {len(already_sent)}")
    
    if already_sent == len(test_picks):
        print(f"  ✅ DEDUP WORKING: All {len(test_picks)} picks correctly identified as duplicates")
    else:
        print(f"  ❌ ISSUE: Expected {len(test_picks)} duplicates, got {len(already_sent)}")
