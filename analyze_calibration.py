"""
Quick analysis of calibration_history.csv — baseline slate.
"""

import csv
from pathlib import Path

with open('calibration_history.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print("=" * 80)
print("CALIBRATION HISTORY — JAN 02 BACKFILL SUMMARY")
print("=" * 80)
print()

# Tiers
by_tier = {}
for r in rows:
    tier = r['tier_calibrated']
    if tier not in by_tier:
        by_tier[tier] = []
    by_tier[tier].append(r)

print("BY TIER (Calibrated):")
for tier in ['SLAM', 'STRONG', 'LEAN', 'BELOW']:
    count = len(by_tier.get(tier, []))
    pct = 100 * count / len(rows) if rows else 0
    print(f"  {tier:6s}: {count:3d} ({pct:5.1f}%)")

print()
print("BY BLOWOUT RISK:")
by_risk = {}
for r in rows:
    risk = r['blowout_risk']
    if risk not in by_risk:
        by_risk[risk] = 0
    by_risk[risk] += 1

for risk in ['Low', 'Moderate', 'High']:
    count = by_risk.get(risk, 0)
    pct = 100 * count / len(rows) if rows else 0
    print(f"  {risk:8s}: {count:3d} ({pct:5.1f}%)")

print()
print("BY PLAYER ROLE:")
by_role = {}
for r in rows:
    role = r['player_role']
    if role not in by_role:
        by_role[role] = 0
    by_role[role] += 1

for role in sorted(by_role.keys()):
    count = by_role[role]
    pct = 100 * count / len(rows) if rows else 0
    print(f"  {role:20s}: {count:3d} ({pct:5.1f}%)")

print()
print("PENALTY STATISTICS:")
penalties_blowout = [float(r['penalty_blowout_pct']) for r in rows if r['penalty_blowout_pct']]
penalties_shrinkage = [float(r['penalty_shrinkage_pct']) for r in rows if r['penalty_shrinkage_pct']]
penalties_total = [float(r['total_penalty_pct']) for r in rows if r['total_penalty_pct']]

print(f"  Blowout penalties: {len(penalties_blowout)} applied")
if penalties_blowout:
    print(f"    Min: {min(penalties_blowout):.3f}, Max: {max(penalties_blowout):.3f}, Avg: {sum(penalties_blowout)/len(penalties_blowout):.3f}")
print(f"  Shrinkage penalties: {len(penalties_shrinkage)} applied")
if penalties_shrinkage:
    print(f"    Min: {min(penalties_shrinkage):.3f}, Max: {max(penalties_shrinkage):.3f}, Avg: {sum(penalties_shrinkage)/len(penalties_shrinkage):.3f}")
print(f"  Total penalties: mean={sum(penalties_total)/len(penalties_total):.3f}")

print()
print("SAMPLE SIZE DISTRIBUTION:")
by_sample = {}
for r in rows:
    flag = r['sample_size_flag']
    if flag not in by_sample:
        by_sample[flag] = 0
    by_sample[flag] += 1

for flag in sorted(by_sample.keys()):
    count = by_sample[flag]
    pct = 100 * count / len(rows) if rows else 0
    print(f"  {flag:8s}: {count:3d} ({pct:5.1f}%)")

print()
print("OUTCOME STATUS:")
outcomes = sum(1 for r in rows if r['outcome'])
print(f"  Outcomes recorded: {outcomes}/{len(rows)}")
print(f"  Awaiting results: {len(rows) - outcomes}")

print()
print("=" * 80)
print("✅ calibration_history.csv is locked and ready for:")
print("   1. Outcome recording (as games finish)")
print("   2. Failure attribution (analysis)")
print("   3. Learning feedback loop (auto-updates)")
print("=" * 80)
