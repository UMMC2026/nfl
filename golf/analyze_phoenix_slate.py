"""
WM Phoenix Open Slate Analyzer
Quick analysis of tourney finishing position props
"""

import json
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load player database
DB_PATH = Path(__file__).parent / "data" / "player_database.json"
with open(DB_PATH) as f:
    PLAYER_DB = json.load(f)

# Your Phoenix Open slate - parsed from the pasted data
PHOENIX_PROPS = [
    # Format: (player, line, direction, odds)
    ("Kevin Roy", 20.5, "better", 3.16),
    ("Christiaan Bezuidenhout", 20.5, "better", 1.34),
    ("Ryo Hisatsune", 20.5, "better", 1.91),
    ("Patton Kizzire", 20.5, "better", 4.39),
    ("Max Greyserman", 20.5, "better", 1.65),
    ("Michael Thorbjornsen", 20.5, "better", 1.28),
    ("Vince Whaley", 20.5, "better", 2.09),
    ("Mark Hubbard", 20.5, "better", 3.11),
    ("Michael Kim", 20.5, "better", 1.61),
    ("Chris Kirk", 20.5, "better", 1.87),
    ("Sam Burns", 20.5, "better", 1.05),
    ("Sahith Theegala", 20.5, "better", 1.35),
    ("Wyndham Clark", 20.5, "better", 1.25),
    ("Sepp Straka", 20.5, "better", 1.36),
    ("Ben Griffin", 20.5, "better", None),  # Missing odds
    ("Brian Harman", 20.5, "better", 1.83),
    ("Harris English", 20.5, "better", 1.08),
    ("Chris Gotterup", 20.5, "better", 1.13),
    ("Michael Brennan", 20.5, "better", 2.75),
    ("Karl Vilips", 20.5, "better", 3.43),
    ("Tony Finau", 20.5, "better", 2.00),
    ("Alex Smalley", 20.5, "better", 1.98),
    ("Patrick Rodgers", 20.5, "better", 1.67),
    ("Adam Schenk", 20.5, "better", 4.58),
    ("John VanDerLaan", 20.5, "better", 5.31),
    ("Tom Hoge", 20.5, "better", 2.79),
    ("Seung-taek Lee", 20.5, "better", 4.99),
    ("Keita Nakajima", 20.5, "better", 3.34),
    ("Daniel Brown", 20.5, "better", 2.00),
    ("Takumi Kanaya", 20.5, "better", 2.97),
    ("Emiliano Grillo", 20.5, "better", 2.27),
    ("Corey Conners", 20.5, "better", 1.27),
    ("Thorbjorn Olesen", 20.5, "better", 1.36),
    ("Tom Kim", 20.5, "better", 2.75),
    ("Seonghyeon Kim", 20.5, "better", 2.31),
    ("Matthieu Pavon", 20.5, "better", 3.70),
    ("Keith Mitchell", 20.5, "better", 1.25),
    ("Joel Dahmen", 20.5, "better", 2.22),
    ("J.T. Poston", 20.5, "better", 1.36),
    ("Collin Morikawa", 20.5, "better", 1.12),
    ("Hideki Matsuyama", 20.5, "better", 0.88),
    ("Akshay Bhatia", 20.5, "better", 1.87),
    ("Xander Schauffele", 20.5, "better", 0.86),
    ("Brooks Koepka", 20.5, "better", 1.30),
    ("Cam Davis", 20.5, "better", 5.31),
    ("Min Woo Lee", 20.5, "better", 1.26),
    ("Si Woo Kim", 20.5, "better", None),  # Missing odds
    ("Nico Echavarria", 20.5, "better", 2.44),
    ("Billy Horschel", 20.5, "better", 2.38),
    ("Maverick McNealy", 20.5, "better", 1.06),
    ("Hank Lebioda", 20.5, "better", 5.20),
    ("Austin Eckroat", 20.5, "better", 2.63),
    ("John Keefer", 20.5, "better", 2.02),
    ("Emilio Gonzalez", 20.5, "better", 4.58),
    ("Zachary Bauchou", 20.5, "better", 4.85),
    ("Christo Lamprecht", 20.5, "better", 7.63),
    ("Adrien Dumont De Chassart", 20.5, "better", 3.16),
    ("Neal Shipley", 20.5, "better", 3.52),
    ("Adrien Saddier", 20.5, "better", 3.70),
    ("Mackenzie Hughes", 20.5, "better", 2.31),
    ("Max McGreevy", 20.5, "better", 1.61),
    ("Rasmus Hojgaard", 20.5, "better", 1.36),
    ("Danny Walker", 20.5, "better", 8.25),
    ("Nicolai Hojgaard", 20.5, "better", 1.41),
    ("Pierceson Coody", 20.5, "better", 1.27),
    ("Brice Garnett", 20.5, "better", 4.71),
    ("Bud Cauley", 20.5, "better", 1.76),
    ("Daniel Berger", 20.5, "better", 1.34),
    ("Webb Simpson", 20.5, "better", 2.09),
    ("Jake Knapp", 20.5, "better", 1.17),
    ("Ryan Fox", 20.5, "better", 2.49),
    ("Matt Fitzpatrick", 20.5, "better", 1.11),
    ("Nick Taylor", 20.5, "better", 1.32),
    ("Scottie Scheffler", 4.5, "worse", 1.04),  # DIFFERENT LINE
    ("Scottie Scheffler", 4.5, "better", 0.82),  # DIFFERENT LINE
    ("Davis Thompson", 20.5, "better", 1.45),
    ("Jordan Spieth", 20.5, "better", 1.20),
    ("William Mouw", 20.5, "better", 2.47),
    ("Joe Highsmith", 20.5, "better", 9.76),
    ("Kurt Kitayama", 20.5, "better", 1.30),
    ("Peter Malnati", 20.5, "better", 10.51),
    ("Gary Woodland", 20.5, "better", 2.42),
    ("Jacob Bridgeman", 20.5, "better", 1.65),
    ("Zecheng Dou", 20.5, "better", 3.57),
    ("Marco Penge", 20.5, "better", 1.76),
    ("Eric Cole", 20.5, "better", 1.87),
    ("Kensei Hirata", 20.5, "better", 6.01),
    ("Davis Chatfield", 20.5, "better", 5.66),
    ("Rico Hoey", 20.5, "better", 1.51),
    ("Chandler Phillips", 20.5, "better", 3.07),
    ("Rafael Campos", 20.5, "better", 16.01),
    ("Kristoffer Reitan", 20.5, "better", 1.87),
    ("Mac Meissner", 20.5, "better", 1.74),
    ("Rasmus Neergaard-Petersen", 20.5, "better", 1.59),
    ("Chad Ramey", 20.5, "better", 2.79),
    ("Sam Stevens", 20.5, "better", 1.39),
    ("Max Homa", 20.5, "better", 1.74),
    ("Davis Riley", 20.5, "better", 3.79),
    ("Stephan Jaeger", 20.5, "better", 1.83),
    ("Viktor Hovland", 20.5, "better", 1.09),
    ("Harry Hall", 20.5, "better", 1.14),
    ("Andrew Novak", 20.5, "better", 1.74),
    ("Cameron Young", 20.5, "better", None),  # Missing odds
    ("Brian Campbell", 20.5, "better", 10.01),
    ("Aldrich Potgieter", 20.5, "better", 3.43),
    ("Rickie Fowler", 20.5, "better", 1.04),
    ("Garrick Higgo", 20.5, "better", 1.43),
    ("Sami Valimaki", 20.5, "better", 2.25),
    ("Matt McCarty", 20.5, "better", 1.29),
    ("Erik Van Rooyen", 20.5, "better", 4.44),
    ("Matti Schmid", 20.5, "better", 2.31),
    ("Charley Hoffman", 20.5, "better", 5.78),
    ("Jordan Smith", 20.5, "better", 1.91),
    ("Chandler Blanchet", 20.5, "better", 3.43),
    ("Sudarshan Yellamaraju", 20.5, "better", 4.71),
    ("John Parry", 20.5, "better", 1.89),
    ("Austin Smotherman", 20.5, "better", 2.84),
    ("HaoTong Li", 20.5, "better", 1.49),
    ("Jeffrey Kang", 20.5, "better", 9.76),
]


def implied_probability(odds: float) -> float:
    """Convert decimal odds to implied probability"""
    if odds is None or odds <= 0:
        return 0.0
    return 1.0 / odds


def find_player_in_db(name: str):
    """Find player in database (fuzzy match)"""
    name_lower = name.lower().strip()
    if name_lower in PLAYER_DB:
        return PLAYER_DB[name_lower]
    # Try partial match
    for key, val in PLAYER_DB.items():
        if name_lower in key or key in name_lower:
            return val
    return None


def analyze_slate():
    """Analyze the Phoenix Open slate"""
    print("=" * 70)
    print("⛳ WM PHOENIX OPEN R1 — TOURNEY FINISHING POSITION ANALYSIS")
    print("=" * 70)
    print(f"Total Props: {len(PHOENIX_PROPS)}")
    print()
    
    # Check database coverage
    in_db = []
    not_in_db = []
    for player, line, direction, odds in PHOENIX_PROPS:
        db_entry = find_player_in_db(player)
        if db_entry:
            in_db.append((player, line, direction, odds, db_entry))
        else:
            not_in_db.append((player, line, direction, odds))
    
    print(f"Players in database: {len(in_db)}")
    print(f"Players NOT in database: {len(not_in_db)}")
    print()
    
    # Show players in database with implied probs
    print("-" * 70)
    print("🟢 PLAYERS WITH STATS (Can Run Full Model)")
    print("-" * 70)
    for player, line, direction, odds, db_entry in sorted(in_db, key=lambda x: implied_probability(x[3]) if x[3] else 0, reverse=True):
        impl_prob = implied_probability(odds) if odds else 0
        tier = db_entry.get("tier", "?")
        sg_total = db_entry.get("sg_total", 0)
        
        direction_str = "TOP 20" if direction == "better" else "OUTSIDE 20"
        if line == 4.5:
            direction_str = "TOP 4" if direction == "better" else "OUTSIDE 4"
        
        # Simple edge calculation (implied vs expected based on SG)
        # Higher SG = more likely to finish top 20
        expected_top20 = 0.50 + (sg_total * 0.10)  # Rough model
        expected_top20 = min(0.95, max(0.10, expected_top20))
        
        edge = expected_top20 - impl_prob if direction == "better" else (1 - expected_top20) - impl_prob
        
        edge_emoji = "✅" if edge > 0.05 else "⚠️" if edge > 0 else "❌"
        
        print(f"{edge_emoji} {player:<25} | {direction_str:<12} @ {odds or 'N/A':<5} | Implied: {impl_prob:.1%} | SG: {sg_total:+.1f} | Edge: {edge:+.1%}")
    
    print()
    print("-" * 70)
    print("⚠️ PLAYERS WITHOUT STATS (Odds-Only Analysis)")
    print("-" * 70)
    
    # Sort by implied probability (best value = higher implied prob that may be undervalued)
    sorted_missing = sorted(not_in_db, key=lambda x: implied_probability(x[3]) if x[3] else 0, reverse=False)
    
    for player, line, direction, odds in sorted_missing[:30]:  # Show top 30
        impl_prob = implied_probability(odds) if odds else 0
        direction_str = "TOP 20" if direction == "better" else "OUTSIDE 20"
        if line == 4.5:
            direction_str = "TOP 4" if direction == "better" else "OUTSIDE 4"
        
        # Flag extreme longshots (high odds = low implied prob = potential value)
        if odds and odds > 3.0:
            print(f"🎯 {player:<25} | {direction_str:<12} @ {odds:<5} | Implied: {impl_prob:.1%} | LONGSHOT")
        elif odds and odds < 1.2:
            print(f"🔒 {player:<25} | {direction_str:<12} @ {odds:<5} | Implied: {impl_prob:.1%} | HEAVY FAV")
        else:
            print(f"   {player:<25} | {direction_str:<12} @ {odds or 'N/A':<5} | Implied: {impl_prob:.1%}")
    
    if len(sorted_missing) > 30:
        print(f"   ... and {len(sorted_missing) - 30} more players without stats")
    
    print()
    print("=" * 70)
    print("📊 BEST VALUE PLAYS (Based on Available Data)")
    print("=" * 70)
    
    # Find best edges from players in DB
    best_plays = []
    for player, line, direction, odds, db_entry in in_db:
        if not odds:
            continue
        impl_prob = implied_probability(odds)
        sg_total = db_entry.get("sg_total", 0)
        expected_top20 = 0.50 + (sg_total * 0.12)
        expected_top20 = min(0.95, max(0.10, expected_top20))
        
        if direction == "better":
            model_prob = expected_top20
        else:
            model_prob = 1 - expected_top20
        
        edge = model_prob - impl_prob
        if edge > 0.05:  # Only show if edge > 5%
            best_plays.append((player, line, direction, odds, impl_prob, model_prob, edge, db_entry))
    
    best_plays.sort(key=lambda x: x[6], reverse=True)
    
    for i, (player, line, direction, odds, impl_prob, model_prob, edge, db_entry) in enumerate(best_plays[:10], 1):
        tier = db_entry.get("tier", "?").upper()
        direction_str = "TOP 20" if direction == "better" else "OUTSIDE 20"
        if line == 4.5:
            direction_str = "TOP 4" if direction == "better" else "OUTSIDE 4"
        
        print(f"{i}. {player} [{tier}]")
        print(f"   {direction_str} @ {odds} | Model: {model_prob:.1%} vs Implied: {impl_prob:.1%} | Edge: {edge:+.1%}")
        print()
    
    if not best_plays:
        print("No edges found > 5% with current database coverage.")
        print("Consider adding more player stats to golf/data/player_database.json")
    
    # Save top picks to cross-sport database
    save_to_cross_sport_db(best_plays[:5])


def save_to_cross_sport_db(best_plays):
    """Save top 5 Golf picks to cross-sport parlay database."""
    if not best_plays:
        print("\n  ⚠️ No plays to save to cross-sport DB")
        return
    
    try:
        from engine.daily_picks_db import save_top_picks
        
        golf_edges = []
        for player, line, direction, odds, impl_prob, model_prob, edge, db_entry in best_plays:
            # Assign tier based on model probability
            if model_prob >= 0.65:
                tier = "STRONG"
            elif model_prob >= 0.55:
                tier = "LEAN"
            else:
                tier = "SPEC"
            
            golf_edges.append({
                'player': player,
                'stat': 'finishing_position',
                'market': 'finishing_position',
                'line': line,
                'direction': direction,
                'probability': model_prob,
                'tier': tier,
                'pick_state': 'VETTED',  # Finishing position = RESEARCH_ONLY
            })
        
        save_top_picks(golf_edges, "GOLF", top_n=5)
        print(f"\n  ✓ Saved {len(golf_edges)} Golf picks to cross-sport database!")
        print(f"    Now accessible in [XP] Cross-Sport Parlays menu")
        
    except ImportError as e:
        print(f"\n  ⚠️ Could not import daily_picks_db: {e}")
    except Exception as e:
        print(f"\n  ⚠️ Failed to save to cross-sport DB: {e}")


if __name__ == "__main__":
    analyze_slate()
