"""
Compare Underdog lines vs market consensus
Currently uses static values - TODO: integrate odds API
"""
import pandas as pd

DATE = "2026-01-07"
FILE = f"data/features/props_clean_{DATE}.csv"

# Market consensus lines (TODO: fetch from OddsAPI, Pinnacle, or DraftKings)
# Format: (player, stat): market_line
MARKET = {
    # Example entries - replace with real data
    ("LeBron James", "points"): 24.5,
    ("LeBron James", "assists"): 8.5,
    ("Giannis Antetokounmpo", "points"): 29.5,
    ("Stephen Curry", "points"): 27.5,
    ("Stephen Curry", "3pm"): 4.5,
}

print(f"📉 Comparing lines vs market: {FILE}")
df = pd.read_csv(FILE)

def market_diff(row):
    """Calculate line differential vs market"""
    key = (row["player"], row["stat"])
    market_line = MARKET.get(key)
    
    if market_line is None:
        return 0.0  # No market data
    
    return row["line"] - market_line

df["line_vs_market"] = df.apply(market_diff, axis=1)

# Count soft/sharp lines
soft_lines = (df["line_vs_market"] > 0.5).sum()  # Underdog higher than market
sharp_lines = (df["line_vs_market"] < -0.5).sum()  # Underdog lower than market

print(f"   Market comparisons: {len(df[df['line_vs_market'] != 0])}/{len(df)}")
print(f"   Soft lines (UD high): {soft_lines}")
print(f"   Sharp lines (UD low): {sharp_lines}")

df.to_csv(FILE, index=False)
print(f"✅ Line comparison complete")
