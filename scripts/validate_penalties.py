"""Validate all penalty multipliers"""
import sys
sys.path.insert(0, '.')
from config.data_driven_penalties import get_data_driven_multiplier

tests = [
    ('pra', 'lower'),
    ('pra', 'higher'),
    ('ast', 'higher'),
    ('ast', 'lower'),
    ('pts', 'higher'),
    ('pts', 'lower'),
    ('reb', 'higher'),
    ('reb', 'lower'),
    ('3pm', 'higher'),
    ('3pm', 'lower'),
    ('rebounds', 'lower'),
    ('pts+ast', 'higher'),
    ('points', 'higher'),
    ('points', 'lower'),
]

print(f"{'Stat':15s} {'Dir':8s} {'Mult':>6s}  Effect")
print('-' * 50)
for stat, direction in tests:
    mult = get_data_driven_multiplier(stat, direction, "nba")
    if mult > 1.05:
        effect = "BOOST"
    elif mult < 0.95:
        effect = "PENALTY"
    else:
        effect = "Neutral"
    print(f"{stat:15s} {direction:8s} {mult:6.2f}  {effect}")

# Show what happens to a 60% pick
print()
print("Impact on a 60% probability pick:")
print('-' * 50)
for stat, direction in tests:
    mult = get_data_driven_multiplier(stat, direction, "nba")
    adj = 60.0 * mult
    status = "PASS" if adj >= 55.0 else "REJECTED"
    print(f"{stat:15s} {direction:8s} -> {adj:5.1f}% [{status}]")
