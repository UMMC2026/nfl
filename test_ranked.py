#!/usr/bin/env python3

from send_telegram_ranked import load_ranked_picks

picks = load_ranked_picks()
print(f"✅ Loaded {len(picks)} ranked picks\n")

# Count by tier
tiers = {}
for p in picks:
    tier = p.get("tier", "FADE")
    tiers[tier] = tiers.get(tier, 0) + 1

print("Picks by tier:")
for tier, count in sorted(tiers.items()):
    print(f"  {tier}: {count}")

# Show top 5
print(f"\nTop 5 picks:")
for i, p in enumerate(picks[:5], 1):
    player = p.get("player", "Unknown")
    line = p.get("line", 0)
    prob = p.get("display_prob", 0.5) * 100
    tier = p.get("tier", "N/A")
    direction = "O" if p.get("direction") == "higher" else "U"
    stat = p.get("stat", "")
    
    print(f"{i}. {player} {direction} {line} {stat} [{prob:.0f}%] ({tier})")
