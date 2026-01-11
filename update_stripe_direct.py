"""Direct SQLite update for Stripe Price IDs."""
import sqlite3

conn = sqlite3.connect('ufa.db')
cursor = conn.cursor()

# Update plans with Stripe Price IDs
updates = [
    ("Starter", "price_1Sk9MJAmdkLb1k5vCHpMiiPj", 1999),
    ("Pro", "price_1Sk9LlAmdkLb1k5vQgCjNglj", 4900),
    ("Whale", "price_1Sk9LCAmdkLb1k5viXrT4NfB", 19900),
]

for name, price_id, price_cents in updates:
    cursor.execute(
        "UPDATE plans SET stripe_price_id = ?, price_cents = ? WHERE name = ?",
        (price_id, price_cents, name)
    )
    print(f"✓ {name}: {price_id}")

conn.commit()
conn.close()
print("\n✓ All plans updated!")
