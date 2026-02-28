"""Quick script to display available NFL markets"""
import sys
sys.path.insert(0, 'engines/nfl')

from nfl_markets import NFLMarket, MARKET_DISPLAY_NAMES

print("\n" + "=" * 60)
print("🏈 NFL PRIZEPICKS MARKETS AVAILABLE")
print("=" * 60)

# Categorize markets
categories = {
    'PASSING': [],
    'RUSHING': [],
    'RECEIVING': [],
    'COMBO': [],
    'DEFENSE': [],
    'SPECIAL TEAMS': []
}

for market in NFLMarket:
    if any(x in market.value for x in ['pass', 'completion', 'interception']):
        if 'pass_rush' not in market.value:
            categories['PASSING'].append(market)
    elif 'rush' in market.value and 'rush_rec' not in market.value and 'pass_rush' not in market.value:
        categories['RUSHING'].append(market)
    elif any(x in market.value for x in ['rec', 'reception', 'target']):
        if 'rush_rec' not in market.value:
            categories['RECEIVING'].append(market)
    elif any(x in market.value for x in ['rush_rec', 'pass_rush']):
        categories['COMBO'].append(market)
    elif any(x in market.value for x in ['sack', 'tackle', 'def_']):
        categories['DEFENSE'].append(market)
    elif any(x in market.value for x in ['fg', 'punt', 'pat']):
        categories['SPECIAL TEAMS'].append(market)

for cat_name, markets in categories.items():
    if markets:
        print(f"\n{cat_name} ({len(markets)} markets):")
        for market in markets:
            display_name = MARKET_DISPLAY_NAMES.get(market, market.value)
            print(f"  ✓ {display_name}")

print("\n" + "=" * 60)
print(f"TOTAL: {len(list(NFLMarket))} markets ready for simulation")
print("=" * 60 + "\n")
