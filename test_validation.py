"""Test the new validation logic"""

def validate_stat_value(stat, value):
    """Sanity check: reject impossible stat values"""
    sanity_limits = {
        'points': (0, 100),
        'rebounds': (0, 40),
        'assists': (0, 30),
        'steals': (0, 15),
        'blocks': (0, 15),
        'turnovers': (0, 15),
        '3pm': (0, 20),
        'pts+reb+ast': (0, 150)
    }
    
    if stat in sanity_limits:
        min_val, max_val = sanity_limits[stat]
        if value < min_val or value > max_val:
            print(f"  ⚠️  REJECTED: {stat}={value} is impossible (range: {min_val}-{max_val})")
            return False
    
    return True

# Test cases from Jan 6 bad data
test_cases = [
    ("assists", 70, "Marcus Smart - SHOULD REJECT"),
    ("turnovers", 26, "LeBron James - SHOULD REJECT"),
    ("points", 18, "Deandre Ayton - SHOULD ACCEPT"),
    ("rebounds", 8, "LeBron James - SHOULD ACCEPT"),
    ("assists", 6, "Trae Young - SHOULD ACCEPT"),
    ("points", 150, "Impossible - SHOULD REJECT"),
    ("assists", 29, "Realistic - SHOULD ACCEPT"),
    ("assists", 31, "Over limit - SHOULD REJECT"),
    ("rebounds", 40, "Boundary - SHOULD ACCEPT"),
    ("rebounds", 41, "Over limit - SHOULD REJECT"),
]

print("="*60)
print("VALIDATION TESTS")
print("="*60)

for stat, value, description in test_cases:
    print(f"\n{description}")
    result = validate_stat_value(stat, value)
    status = "✅ ACCEPTED" if result else "❌ REJECTED"
    print(f"  {status}")

print("\n" + "="*60)
print("Summary:")
print("- Old system would accept Marcus Smart 70 AST")
print("- New system rejects values outside realistic ranges")
print("- Prevents false MISSes from bad SerpApi data")
print("="*60)
