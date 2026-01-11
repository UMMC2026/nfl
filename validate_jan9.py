import json

with open('outputs/jan9_raw_lines.json', 'r') as f:
    data = json.load(f)

print(f"🏀 JANUARY 9, 2026 NBA SLATE")
print(f"📊 {len(data['games'])} games, {len(data['picks'])} total props")
print()
for game in data['games']:
    print(f"{game['matchup']} - {game['time']}")
print()
print("✅ Raw lines file validated")
print("⏭️  Next: Run comprehensive analysis")
