"""Verify the player profiler fixes:
1. New JSON stats entries load for previously missing players
2. Normalize strips ellipsis and time suffixes
3. Multi-match DB lookups prefer player with most match_stats
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tennis'))

from player_profiler import TennisPlayerProfiler

profiler = TennisPlayerProfiler()

print("=" * 60)
print("TEST 1: Previously missing players now have JSON stats")
print("=" * 60)
for name in ['Ilya Ivashka', 'Kinsey Crawford', 'Chukwumelije Clarke', 
             'Moise Kouame', 'Alexia Paula Bastos Sousa Betanzos']:
    profile = profiler.get_profile(name, surface='Hard')
    if profile:
        print(f"  ✅ {name}: n={profile.n_matches}, win_rate={profile.win_rate:.2f}, "
              f"avg_aces={profile.avg_aces:.1f}, confidence={profile.confidence:.2f}")
    else:
        print(f"  ❌ STILL MISSING: {name}")

print()
print("=" * 60)
print("TEST 2: _normalize_name strips junk")
print("=" * 60)
test_names = [
    ("Sakella…", "Expected: sakella"),
    ("Bouquier - Thu 5:00AM CST", "Expected: bouquier"),
    ("Anisimo… - Thu 5:10AM CST", "Expected: anisimo"),
    ("Tsitsipas - Thu 6:00AM CST", "Expected: tsitsipas"),
    ("Schwaerzl… - Thu 11:30AM CST", "Expected: schwaerzl"),
    ("Berretti… - Thu 1:30PM CST", "Expected: berretti"),
    ("Taylor Fritz", "Expected: taylor fritz (unchanged)"),
]
for raw, expected in test_names:
    normalized = profiler._normalize_name(raw)
    print(f"  '{raw}' → '{normalized}'  ({expected})")

print()
print("=" * 60)
print("TEST 3: Multi-match DB lookup (last-name only)")
print("=" * 60)
for name in ['Tsitsipas', 'Berrettini', 'Fonseca']:
    profile = profiler.get_profile(name, surface='Hard')
    if profile:
        print(f"  ✅ '{name}' → {profile.player_name} (n={profile.n_matches}, confidence={profile.confidence:.2f})")
    else:
        # Will still be "not found" if no match_stats even for best match
        print(f"  ⚠️ '{name}' → No profile (check if player has match_stats)")

profiler.close()
print("\n✅ Verification complete")
