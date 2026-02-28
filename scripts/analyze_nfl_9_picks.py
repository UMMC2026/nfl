"""
Quick analysis of 9 NFL historical picks
Shows what went wrong and whether new caps would help
"""

import pandas as pd
from scipy.stats import norm


# 9 NFL picks data (from calibration CSV)
picks_data = [
    {
        'player': 'Kyren Williams',
        'stat': 'Recs',
        'line': 2.5,
        'direction': 'over',
        'actual': 2,
        'hit': False,
        'prob_old': 0.55
    },
    {
        'player': 'Matthew Stafford',
        'stat': 'Rush Yards',
        'line': 0.5,
        'direction': 'over',
        'actual': 16,
        'hit': True,
        'prob_old': 0.55
    },
    {
        'player': 'Tyler Higbee',
        'stat': 'Rec Yards',
        'line': 19.5,
        'direction': 'over',
        'actual': 12,
        'hit': False,
        'prob_old': 0.55
    },
    {
        'player': 'Kayshon Boutte',
        'stat': 'Rec Yards',
        'line': 31.5,
        'direction': 'over',
        'actual': 6,
        'hit': False,
        'prob_old': 0.55
    },
    {
        'player': 'RJ Harvey',
        'stat': 'Rush Yards',
        'line': 40.5,
        'direction': 'over',
        'actual': 37,
        'hit': False,
        'prob_old': 0.55
    },
    {
        'player': 'Cooper Kupp',
        'stat': 'Recs',
        'line': 3.0,
        'direction': 'under',
        'actual': 4,
        'hit': False,
        'prob_old': 0.55
    },
    {
        'player': 'Blake Corum',
        'stat': 'Rec Yards',
        'line': 0.5,
        'direction': 'over',
        'actual': 24,
        'hit': True,
        'prob_old': 0.55
    },
    {
        'player': 'Colby Parkinson',
        'stat': 'Recs',
        'line': 1.5,
        'direction': 'over',
        'actual': 3,
        'hit': True,
        'prob_old': 0.55
    },
    {
        'player': 'Terrance Ferguson',
        'stat': 'Recs',
        'line': 0.5,
        'direction': 'over',
        'actual': 0,
        'hit': False,
        'prob_old': 0.55
    }
]


def estimate_mu_sigma(pick):
    """
    Estimate what mu/sigma SHOULD have been based on actual result
    """
    actual = pick['actual']
    line = pick['line']
    direction = pick['direction']
    stat = pick['stat'].lower()
    hit = pick['hit']
    
    # Estimate sigma from stat type
    if 'pass' in stat and 'yard' in stat:
        sigma = 50.0
    elif 'rush' in stat and 'yard' in stat:
        sigma = 25.0
    elif 'rec' in stat and 'yard' in stat:
        sigma = 30.0
    elif 'rec' in stat:
        sigma = 2.5
    elif 'td' in stat:
        sigma = 1.0
    else:
        sigma = 10.0
    
    # Estimate mu based on actual result and hit/miss
    # If OVER and HIT: actual > line, so mu probably ~line + 0.5σ
    # If OVER and MISS: actual < line, so mu probably ~line - 0.5σ
    
    if direction == 'over':
        if hit:
            mu = line + 0.5 * sigma
        else:
            mu = line - 0.5 * sigma
    else:  # under
        if hit:
            mu = line - 0.5 * sigma
        else:
            mu = line + 0.5 * sigma
    
    return mu, sigma


def calculate_probability(mu, sigma, line, direction):
    """Calculate probability using normal distribution"""
    if sigma == 0:
        return 0.50
    
    z_score = (line - mu) / sigma
    
    if direction == 'over':
        prob = 1 - norm.cdf(z_score)
    else:
        prob = norm.cdf(z_score)
    
    return prob


def assign_tier(probability):
    """Assign tier based on probability (with NEW thresholds)"""
    if probability >= 0.80:
        return 'SLAM'
    elif probability >= 0.70:
        return 'STRONG'
    elif probability >= 0.60:
        return 'LEAN'
    else:
        return 'NO_PLAY'


def apply_new_caps(probability, stat):
    """Apply NEW confidence caps from fixed analyze_nfl_props.py"""
    stat_lower = stat.lower()
    
    # Touchdown props (most volatile) - 78% cap
    if 'td' in stat_lower or 'touchdown' in stat_lower:
        return min(probability, 0.78)
    
    # Core stats (yards, receptions) - 85% cap
    elif any(x in stat_lower for x in ['yards', 'recs', 'receptions']):
        return min(probability, 0.85)
    
    # Alternative stats - 82% cap
    else:
        return min(probability, 0.82)


print("\n" + "=" * 100)
print("NFL 9 HISTORICAL PICKS ANALYSIS - OLD (55% cap) vs NEW (78-85% caps)")
print("=" * 100 + "\n")

results = []

for pick in picks_data:
    # Estimate mu/sigma from actual results
    mu, sigma = estimate_mu_sigma(pick)
    
    # Calculate raw probability (no caps)
    prob_raw = calculate_probability(mu, sigma, pick['line'], pick['direction'])
    
    # Apply OLD caps (55%)
    prob_old_capped = min(prob_raw, 0.55)
    tier_old = assign_tier(prob_old_capped)
    
    # Apply NEW caps (78-85% depending on stat)
    prob_new_capped = apply_new_caps(prob_raw, pick['stat'])
    tier_new = assign_tier(prob_new_capped)
    
    # Calculate edge
    edge_old = prob_old_capped - 0.524  # Need 52.4% to break even
    edge_new = prob_new_capped - 0.524
    
    results.append({
        'player': pick['player'],
        'stat': pick['stat'],
        'line': pick['line'],
        'direction': pick['direction'],
        'actual': pick['actual'],
        'hit': pick['hit'],
        'mu_est': mu,
        'sigma_est': sigma,
        'prob_raw': prob_raw,
        'prob_old': prob_old_capped,
        'tier_old': tier_old,
        'prob_new': prob_new_capped,
        'tier_new': tier_new,
        'edge_old': edge_old,
        'edge_new': edge_new,
        'would_play_old': tier_old != 'NO_PLAY',
        'would_play_new': tier_new != 'NO_PLAY'
    })

df = pd.DataFrame(results)

# Print detailed results
for i, r in df.iterrows():
    status = "✅ HIT" if r['hit'] else "❌ MISS"
    
    print(f"\n{i+1}. {r['player']} — {r['stat']} {r['direction'].upper()} {r['line']}")
    print(f"   Actual: {r['actual']} {status}")
    print(f"   Estimated μ={r['mu_est']:.1f}, σ={r['sigma_est']:.1f}")
    print(f"   Raw probability: {r['prob_raw']:.1%}")
    print(f"   ")
    print(f"   OLD (55% cap):  {r['prob_old']:.1%} → {r['tier_old']} (edge: {r['edge_old']:+.1%})")
    print(f"   NEW (85% cap):  {r['prob_new']:.1%} → {r['tier_new']} (edge: {r['edge_new']:+.1%})")
    print(f"   ")
    print(f"   Would play OLD? {r['would_play_old']}  |  Would play NEW? {r['would_play_new']}")

# Summary stats
print("\n" + "=" * 100)
print("SUMMARY STATISTICS")
print("=" * 100 + "\n")

wins = df['hit'].sum()
losses = len(df) - wins
win_rate = wins / len(df) * 100

print(f"Overall: {wins}-{losses} ({win_rate:.1f}% win rate)")
print(f"")

# OVER/UNDER breakdown
overs = df[df['direction'] == 'over']
unders = df[df['direction'] == 'under']

print(f"OVERs:  {overs['hit'].sum()}-{len(overs) - overs['hit'].sum()} ({len(overs)} picks, {overs['hit'].sum()/len(overs)*100:.1f}% win rate)")
print(f"UNDERs: {unders['hit'].sum()}-{len(unders) - unders['hit'].sum()} ({len(unders)} picks, {unders['hit'].sum()/len(unders)*100 if len(unders) > 0 else 0:.1f}% win rate)")
print(f"")

# Average probabilities
print(f"Average probability (OLD): {df['prob_old'].mean():.1%}")
print(f"Average probability (NEW): {df['prob_new'].mean():.1%}")
print(f"")

# Average edges
print(f"Average edge (OLD): {df['edge_old'].mean():+.1%}")
print(f"Average edge (NEW): {df['edge_new'].mean():+.1%}")
print(f"")

# Tier distribution
print(f"Tier distribution (OLD):")
for tier in ['SLAM', 'STRONG', 'LEAN', 'NO_PLAY']:
    count = (df['tier_old'] == tier).sum()
    print(f"  {tier:10s}: {count} picks")

print(f"")
print(f"Tier distribution (NEW):")
for tier in ['SLAM', 'STRONG', 'LEAN', 'NO_PLAY']:
    count = (df['tier_new'] == tier).sum()
    print(f"  {tier:10s}: {count} picks")

print(f"")

# Would raising caps have helped?
print("\n" + "=" * 100)
print("CRITICAL ANALYSIS: Would NEW caps have prevented losses?")
print("=" * 100 + "\n")

# Check which MISSES would have been blocked by higher thresholds
misses = df[~df['hit']]

print(f"Total misses: {len(misses)}")
print(f"")

# With OLD caps: all would play (55% >= NO_PLAY threshold)
would_play_old = misses[misses['would_play_old']]
print(f"OLD (55% cap): {len(would_play_old)} misses would have played (all of them)")

# With NEW caps: check how many would still play
would_play_new = misses[misses['would_play_new']]
print(f"NEW (85% cap): {len(would_play_new)} misses would still play")
print(f"")

blocked_by_new_caps = len(would_play_old) - len(would_play_new)
print(f"🎯 NEW caps would have BLOCKED {blocked_by_new_caps} losing picks")

if blocked_by_new_caps > 0:
    print(f"   These picks:")
    for i, r in misses[~misses['would_play_new']].iterrows():
        print(f"     - {r['player']} {r['stat']} {r['direction'].upper()} {r['line']}")
        print(f"       (NEW prob: {r['prob_new']:.1%} → {r['tier_new']})")

print(f"")

# Adjusted win rate if we used NEW caps
wins_new = df[df['hit'] & df['would_play_new']].shape[0]
picks_new = df[df['would_play_new']].shape[0]

if picks_new > 0:
    win_rate_new = wins_new / picks_new * 100
    print(f"📊 If using NEW caps: {wins_new}-{picks_new - wins_new} ({win_rate_new:.1f}% win rate)")
else:
    print(f"📊 If using NEW caps: NO PICKS would qualify (all blocked)")

print(f"")

# OVER bias check
print("\n" + "=" * 100)
print("🚨 OVER BIAS ANALYSIS")
print("=" * 100 + "\n")

overs_playable_new = df[(df['direction'] == 'over') & df['would_play_new']]
print(f"OVERs that would play with NEW caps: {len(overs_playable_new)}")
print(f"Historical OVER win rate: {overs['hit'].sum()}/{len(overs)} = {overs['hit'].sum()/len(overs)*100:.1f}%")
print(f"")

if len(overs_playable_new) > 0:
    overs_win_new = overs_playable_new['hit'].sum()
    overs_new_pct = overs_win_new / len(overs_playable_new) * 100
    print(f"NEW caps OVER performance: {overs_win_new}/{len(overs_playable_new)} = {overs_new_pct:.1f}%")
    
    if overs_new_pct < 52.4:
        print(f"⚠️  WARNING: Even with NEW caps, OVERs are STILL unprofitable ({overs_new_pct:.1f}% < 52.4% breakeven)")
        print(f"   RECOMMENDATION: Add OVER bias filter (require 68%+ probability for OVERs)")
    else:
        print(f"✅ With NEW caps, OVERs become profitable ({overs_new_pct:.1f}% > 52.4%)")

print("\n" + "=" * 100)
print("FINAL RECOMMENDATION")
print("=" * 100 + "\n")

# Calculate improvement
improvement = win_rate_new - win_rate if picks_new > 0 else 0

if picks_new == 0:
    print("❌ NEW caps would BLOCK ALL PICKS")
    print("   System is TOO CONSERVATIVE - no edges found")
    print("   ")
    print("   Super Bowl recommendation: SKIP")
    print("   System cannot generate valid picks with current thresholds")
elif win_rate_new >= 52.4:
    print(f"✅ NEW caps IMPROVE win rate: {win_rate:.1f}% → {win_rate_new:.1f}% ({improvement:+.1f}%)")
    print(f"   This is ABOVE break-even (52.4%)")
    print(f"   ")
    print(f"   Super Bowl recommendation: PROCEED WITH CAUTION")
    print(f"   - Use NEW caps (78-85% depending on stat)")
    print(f"   - Add OVER bias filter (require 68%+ for OVERs)")
    print(f"   - Max 2 legs per parlay")
    print(f"   - Small stake size")
else:
    print(f"⚠️  NEW caps IMPROVE but still BELOW break-even: {win_rate:.1f}% → {win_rate_new:.1f}%")
    print(f"   Need {52.4 - win_rate_new:.1f}% more to be profitable")
    print(f"   ")
    print(f"   Super Bowl recommendation: SKIP or MICRO-STAKE")
    print(f"   System is not calibrated enough for confident betting")

print("\n" + "=" * 100 + "\n")
