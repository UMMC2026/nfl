import json
from datetime import datetime

with open('data/telegram_sent_history.json', 'r') as f:
    data = json.load(f)

# Get last 5 entries by sent_at timestamp
entries = sorted(data.items(), key=lambda x: x[1]['sent_at'], reverse=True)[:5]

print('📤 LAST 5 SIGNALS SENT TO TELEGRAM:')
print('=' * 80)
for key, entry in entries:
    pick = entry['pick']
    sent_at = entry['sent_at']
    print(f"{pick['player']} ({pick['team']}) - {pick['stat'].upper()} O {pick['line']}")
    print(f"   Tier: {pick['tier']} ({pick['display_prob']}%) | Sent: {sent_at}")
    print()

print('=' * 80)
print(f"Total signals tracked: {len(data)}")
print(f"Last signal: {entries[0][1]['sent_at']}")
