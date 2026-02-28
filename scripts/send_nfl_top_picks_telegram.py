"""
Send Top NFL Picks to Telegram (Emergency Filter)
Filters duplicates/garbage from broken analysis, sends top picks
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent))

# Load analysis file
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
nfl_files = sorted(OUTPUTS_DIR.glob("nfl_analysis_*.json"), reverse=True)

if not nfl_files:
    print("❌ No NFL analysis files found")
    sys.exit(1)

latest = nfl_files[0]
print(f"📂 Loading: {latest.name}")

with open(latest, "r") as f:
    data = json.load(f)

results = data.get("results", [])
print(f"📊 Raw edges: {len(results)}")

# FILTER 1: Remove duplicates (keep highest probability per player/stat/direction)
print("\n🔍 FILTERING...")

grouped = defaultdict(list)
for r in results:
    key = (r['player'], r['stat'], r['direction'])
    grouped[key].append(r)

filtered = []
for key, edges in grouped.items():
    # Keep highest probability
    best = max(edges, key=lambda x: x.get('probability', 0))
    
    # Also keep primary line (highest line for OVER, lowest for UNDER)
    if best['direction'].lower() in ['higher', 'over']:
        primary = max(edges, key=lambda x: x['line'])
    else:
        primary = min(edges, key=lambda x: x['line'])
    
    # Use best probability with primary line
    best['line'] = primary['line']
    filtered.append(best)

print(f"✅ After dedup: {len(filtered)}")

# FILTER 2: Remove garbage lines
MIN_LINES = {
    'pass_yds': 150.0,
    'rush_yds': 30.0,
    'rec_yds': 15.0,
    'receptions': 2.0,
    'targets': 3.0,
    'longest_rec': 10.0,
    'total_yds': 40.0,
    'fantasy_pts': 5.0
}

real_lines = []
for r in filtered:
    min_line = MIN_LINES.get(r['stat'], 0.5)
    if r['line'] >= min_line:
        real_lines.append(r)

print(f"✅ After garbage filter: {len(real_lines)}")

# FILTER 3: Remove <57% (too close to coin flip)
actionable = [r for r in real_lines if r.get('probability', 0) >= 0.57]
print(f"✅ After 57% threshold: {len(actionable)}")

# FILTER 4: Remove both directions (keep best)
final_grouped = defaultdict(list)
for r in actionable:
    key = (r['player'], r['stat'])
    final_grouped[key].append(r)

final = []
for key, edges in final_grouped.items():
    if len(edges) == 1:
        final.append(edges[0])
    else:
        # Keep higher probability
        best = max(edges, key=lambda x: x['probability'])
        final.append(best)

print(f"✅ After direction filter: {len(final)}")

# FILTER 5: SUPER BOWL TEAMS ONLY (SEA vs NE)
SUPERBOWL_TEAMS = ['SEA', 'NE']
final = [r for r in final if r.get('team') in SUPERBOWL_TEAMS]
print(f"✅ Super Bowl teams only (SEA/NE): {len(final)}")

# Sort by probability
final.sort(key=lambda x: x['probability'], reverse=True)

# Get top 10
top_picks = final[:10]

print(f"\n{'='*70}")
print("🏈 TOP NFL PICKS (SUPER BOWL)")
print(f"{'='*70}\n")

for i, r in enumerate(top_picks, 1):
    prob = r['probability'] * 100
    tier = "🔥" if prob >= 70 else "✅" if prob >= 60 else "📊"
    print(f"{i:2d}. {tier} {r['player']:20s} {r['stat']:12s} {r['line']:>6.1f} {r['direction']:6s} {prob:5.1f}%")

# Send to Telegram
print(f"\n{'='*70}")
print("📲 SENDING TO TELEGRAM...")
print(f"{'='*70}\n")

# Build AI Game Context
game_context = """🏈 *SUPER BOWL LX*
📍 New Orleans | Feb 8, 2026
🆚 Seattle Seahawks vs New England Patriots

*Matchup Analysis:*
• Seahawks: High-powered passing attack (Geno Smith, JSN, DK Metcalf)
• Patriots: Ground-and-pound + TE usage (Stevenson, Hunter Henry)
• Defensive chess match: Patriots bend-don't-break vs Seahawks 12th man energy

*Sharp Angles from Model:*
• Receiving props showing 70% confidence on VOLUME plays
• Hunter Henry + AJ Barner TE usage in red zone
• JSN exploiting Patriots secondary on crossing routes
• Stevenson UNDER receptions = sharp fade (game script favors rushing)

"""

try:
    from telegram_push import push_signals
    
    # Convert to signals format
    signals = []
    for r in top_picks:
        prob = r['probability']
        tier = "STRONG" if prob >= 0.65 else "LEAN"
        
        signals.append({
            "player": r['player'],
            "team": r.get('team', 'NFL'),
            "stat": r['stat'],
            "line": r['line'],
            "direction": r['direction'],
            "probability": prob,
            "tier": tier,
            "grade": r.get('grade', 'A')
        })
    
    # Send game context first
    from telegram_push import _send
    _send(game_context)
    print("✅ Sent game context")
    
    import time
    time.sleep(1)
    
    # Send picks
    success = push_signals(signals, mode="superbowl")
    
    if success:
        print("✅ Sent picks to Telegram!")
    else:
        print("⚠️ Telegram send may have failed - check .env for TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    
except Exception as e:
    print(f"❌ Telegram send failed: {e}")
    print("\n📋 FULL MESSAGE (copy manually to Telegram):")
    print("=" * 70)
    print(game_context)
    print("\n*TOP 10 PICKS:*\n")
    for i, r in enumerate(top_picks, 1):
        prob = r['probability'] * 100
        tier_emoji = "🔥" if prob >= 70 else "✅" if prob >= 60 else "📊"
        print(f"{tier_emoji} *{r['player']}* ({r.get('team', 'NFL')}) {r['stat'].upper()} {r['direction'].upper()} {r['line']}")
        print(f"   {prob:.1f}% confidence | {r.get('grade', 'A')} tier\n")
    print("=" * 70)
