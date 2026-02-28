"""
Golf Edge Exporter for Phoenix Open
Outputs edges in standard format for cheatsheet generator
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load player database
DB_PATH = Path(__file__).parent / "data" / "player_database.json"
with open(DB_PATH) as f:
    PLAYER_DB = json.load(f)


def implied_probability(odds: float) -> float:
    """Convert decimal odds to implied probability"""
    if odds is None or odds <= 0:
        return 0.0
    return 1.0 / odds


def find_player_in_db(name: str):
    """Find player in database"""
    name_lower = name.lower().strip()
    if name_lower in PLAYER_DB:
        return PLAYER_DB[name_lower]
    for key, val in PLAYER_DB.items():
        if name_lower in key or key in name_lower:
            return val
    return None


# ============================================================
# FAIRWAYS HIT PROPS (BEST VALUE MARKET)
# ============================================================
FAIRWAYS_PROPS = [
    ("Max Greyserman", 7.5, "higher", 1.05),
    ("Max Greyserman", 7.5, "lower", 0.81),
    ("Jake Knapp", 7.5, "higher", 1.05),
    ("Jake Knapp", 7.5, "lower", 0.86),
    ("Matt Fitzpatrick", 8.5, "higher", 1.03),
    ("Matt Fitzpatrick", 8.5, "lower", 0.82),
    ("Scottie Scheffler", 8.5, "higher", 0.82),
    ("Scottie Scheffler", 8.5, "lower", 1.03),
    ("Chris Gotterup", 7.5, "higher", 1.08),
    ("Chris Gotterup", 7.5, "lower", 0.84),
    ("Marco Penge", 7.5, "higher", 1.07),
    ("Marco Penge", 7.5, "lower", 0.84),
    ("Kristoffer Reitan", 8.5, "higher", 1.05),
    ("Kristoffer Reitan", 8.5, "lower", 0.81),
    ("Si Woo Kim", 9.5, "higher", 1.08),
    ("Si Woo Kim", 9.5, "lower", 0.79),
    ("Matt McCarty", 8.5, "higher", 1.05),
    ("Matt McCarty", 8.5, "lower", 0.85),
    ("Sam Burns", 8.5, "higher", 1.04),
    ("Sam Burns", 8.5, "lower", 0.81),
    ("Sepp Straka", 8.5, "higher", 0.84),
    ("Sepp Straka", 8.5, "lower", 1.08),
    ("Ben Griffin", 7.5, "higher", 0.82),
    ("Ben Griffin", 7.5, "lower", 1.03),
    ("Michael Brennan", 8.5, "higher", 1.03),
    ("Michael Brennan", 8.5, "lower", 0.88),
    ("Corey Conners", 8.5, "higher", 0.81),
    ("Corey Conners", 8.5, "lower", 1.05),
    ("Sam Stevens", 7.5, "higher", 0.81),
    ("Sam Stevens", 7.5, "lower", 1.04),
    ("Hideki Matsuyama", 8.5, "higher", 1.09),
    ("Hideki Matsuyama", 8.5, "lower", 0.79),
    ("Xander Schauffele", 7.5, "higher", 1.05),
    ("Xander Schauffele", 7.5, "lower", 0.85),
    ("Andrew Novak", 7.5, "higher", 0.94),
    ("Andrew Novak", 7.5, "lower", 1.03),
    ("Maverick McNealy", 7.5, "higher", 0.81),
    ("Maverick McNealy", 7.5, "lower", 1.04),
]

# ============================================================
# BIRDIES PROPS (BEST UNDERS)
# ============================================================
BIRDIES_PROPS = [
    ("Jacob Bridgeman", 3.5, "lower", 1.10),
    ("Rico Hoey", 3.5, "lower", 1.08),
    ("Rasmus Neergaard-Petersen", 3.5, "lower", 1.08),
    ("Ryan Fox", 3.5, "lower", 1.06),
    ("Max McGreevy", 3.5, "lower", 1.07),
    ("Bud Cauley", 3.5, "lower", 1.05),
    ("Nick Taylor", 3.5, "lower", 1.05),
    ("Brian Harman", 3.5, "lower", 1.06),
    ("Michael Brennan", 3.5, "lower", 1.03),
    ("Billy Horschel", 3.5, "lower", 1.07),
    ("Nico Echavarria", 3.5, "lower", 1.06),
    ("J.T. Poston", 3.5, "lower", 1.03),
    ("Sami Valimaki", 3.5, "lower", 1.06),
]

# ============================================================
# MADE CUTS PROPS (LONGSHOTS WITH VALUE)
# ============================================================
MADE_CUTS_PROPS = [
    ("Peter Malnati", 0.5, "higher", 1.22),
    ("Joe Highsmith", 0.5, "higher", 1.20),
    ("Brian Campbell", 0.5, "higher", 1.16),
    ("Christo Lamprecht", 0.5, "higher", 1.11),
    ("Danny Walker", 0.5, "higher", 1.12),
    ("Rafael Campos", 0.5, "higher", 1.32),
]


def generate_edges() -> list:
    """Generate edges from all props"""
    edges = []
    edge_id = 1
    
    # Process Fairways props
    for player, line, direction, odds in FAIRWAYS_PROPS:
        impl_prob = implied_probability(odds)
        db_entry = find_player_in_db(player)
        
        # Model probability based on direction and player style
        if db_entry:
            sg = db_entry.get("sg_total", 0)
            # Higher SG players tend to be more accurate
            # But bombers (high SG OTT) often miss fairways
            base_prob = 0.52 + (sg * 0.03)
        else:
            base_prob = 0.50
        
        # Adjust for direction
        if direction == "lower":
            model_prob = 1 - base_prob
        else:
            model_prob = base_prob
        
        model_prob = max(0.45, min(0.65, model_prob))
        edge = model_prob - impl_prob
        
        # Assign tier
        if model_prob >= 0.65:
            tier = "STRONG"
        elif model_prob >= 0.55:
            tier = "LEAN"
        else:
            tier = "AVOID"
        
        # Only include positive edge plays
        if edge > 0.02:
            edges.append({
                "edge_id": f"GOLF-FW-{edge_id:03d}",
                "sport": "GOLF",
                "entity": player,
                "market": "Fairways Hit",
                "line": line,
                "direction": direction.upper(),
                "probability": round(model_prob, 3),
                "implied_prob": round(impl_prob, 3),
                "edge": round(edge, 3),
                "odds": odds,
                "tier": tier,
                "pick_state": "OPTIMIZABLE" if tier in ["STRONG", "LEAN"] else "VETTED",
                "tournament": "WM Phoenix Open",
                "round": "R1"
            })
            edge_id += 1
    
    # Process Birdies props
    for player, line, direction, odds in BIRDIES_PROPS:
        impl_prob = implied_probability(odds)
        db_entry = find_player_in_db(player)
        
        if db_entry:
            birdies_avg = db_entry.get("birdies_per_round", 3.5)
            sg = db_entry.get("sg_total", 0)
        else:
            birdies_avg = 3.5
            sg = 0
        
        # Model for UNDER birdies
        if direction == "lower":
            if birdies_avg < line:
                model_prob = 0.55 + (line - birdies_avg) * 0.05
            else:
                model_prob = 0.48
        else:
            if birdies_avg > line:
                model_prob = 0.55 + (birdies_avg - line) * 0.05
            else:
                model_prob = 0.48
        
        model_prob = max(0.45, min(0.65, model_prob))
        edge = model_prob - impl_prob
        
        if model_prob >= 0.65:
            tier = "STRONG"
        elif model_prob >= 0.55:
            tier = "LEAN"
        else:
            tier = "AVOID"
        
        if edge > 0.02:
            edges.append({
                "edge_id": f"GOLF-BIRD-{edge_id:03d}",
                "sport": "GOLF",
                "entity": player,
                "market": "Birdies or Better",
                "line": line,
                "direction": direction.upper(),
                "probability": round(model_prob, 3),
                "implied_prob": round(impl_prob, 3),
                "edge": round(edge, 3),
                "odds": odds,
                "tier": tier,
                "pick_state": "OPTIMIZABLE" if tier in ["STRONG", "LEAN"] else "VETTED",
                "tournament": "WM Phoenix Open",
                "round": "R1"
            })
            edge_id += 1
    
    # Process Made Cuts props
    for player, line, direction, odds in MADE_CUTS_PROPS:
        impl_prob = implied_probability(odds)
        db_entry = find_player_in_db(player)
        
        if db_entry:
            sg = db_entry.get("sg_total", 0)
            # Positive SG = higher make cut probability
            if sg >= 1.0:
                model_prob = 0.80
            elif sg >= 0.5:
                model_prob = 0.70
            elif sg >= 0:
                model_prob = 0.60
            else:
                model_prob = 0.50
        else:
            model_prob = impl_prob  # No edge without data
        
        edge = model_prob - impl_prob
        
        if model_prob >= 0.65:
            tier = "STRONG"
        elif model_prob >= 0.55:
            tier = "LEAN"
        else:
            tier = "AVOID"
        
        # Made cuts longshots are high variance
        edges.append({
            "edge_id": f"GOLF-CUT-{edge_id:03d}",
            "sport": "GOLF",
            "entity": player,
            "market": "Made Cuts",
            "line": line,
            "direction": direction.upper(),
            "probability": round(model_prob, 3),
            "implied_prob": round(impl_prob, 3),
            "edge": round(edge, 3),
            "odds": odds,
            "tier": tier,
            "pick_state": "VETTED",  # Always VETTED for made cuts (high variance)
            "tournament": "WM Phoenix Open",
            "round": "R1",
            "risk_flag": "HIGH_VARIANCE"
        })
        edge_id += 1
    
    return edges


def main():
    print("=" * 70)
    print("⛳ GOLF EDGE EXPORTER — WM Phoenix Open R1")
    print("=" * 70)
    
    edges = generate_edges()
    
    # Output file
    output_path = Path("outputs") / f"golf_phoenix_edges_{datetime.now().strftime('%Y%m%d')}.json"
    output_path.parent.mkdir(exist_ok=True)
    
    output_data = {
        "tournament": "WM Phoenix Open",
        "round": "R1",
        "generated": datetime.now().isoformat(),
        "sport": "GOLF",
        "total_edges": len(edges),
        "edges": edges
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✅ Exported {len(edges)} edges to {output_path}")
    
    # Summary by tier
    tier_counts = {}
    for e in edges:
        tier = e["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print("\n📊 Edges by Tier:")
    for tier in ["STRONG", "LEAN", "AVOID"]:
        if tier in tier_counts:
            print(f"   {tier}: {tier_counts[tier]}")
    
    # Summary by market
    market_counts = {}
    for e in edges:
        market = e["market"]
        market_counts[market] = market_counts.get(market, 0) + 1
    
    print("\n📊 Edges by Market:")
    for market, count in sorted(market_counts.items(), key=lambda x: -x[1]):
        print(f"   {market}: {count}")


if __name__ == "__main__":
    main()
