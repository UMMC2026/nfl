"""
Bulk Add Players to Golf Database
==================================
Adds missing players with estimated stats based on odds-implied tier.

Usage:
    python golf/scripts/bulk_add_players.py --dry-run  # Preview only
    python golf/scripts/bulk_add_players.py            # Actually update
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_PATH = Path(__file__).parent.parent / "data" / "player_database.json"
BACKUP_PATH = Path(__file__).parent.parent / "data" / "backups"

# Players to add from WM Phoenix Open 2026
# Format: (name, finishing_position_line, direction, odds)
PHOENIX_MISSING_PLAYERS = [
    ("Kevin Roy", 20.5, "better", 3.16),
    ("Christiaan Bezuidenhout", 20.5, "better", 1.34),
    ("Patton Kizzire", 20.5, "better", 4.39),
    ("Max Greyserman", 20.5, "better", 1.65),
    ("Michael Thorbjornsen", 20.5, "better", 1.28),
    ("Vince Whaley", 20.5, "better", 2.09),
    ("Mark Hubbard", 20.5, "better", 3.11),
    ("Michael Kim", 20.5, "better", 1.61),
    ("Chris Kirk", 20.5, "better", 1.87),
    ("Ben Griffin", 20.5, "better", 1.50),  # Estimated
    ("Michael Brennan", 20.5, "better", 2.75),
    ("Karl Vilips", 20.5, "better", 3.43),
    ("Alex Smalley", 20.5, "better", 1.98),
    ("Patrick Rodgers", 20.5, "better", 1.67),
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
    ("J.T. Poston", 20.5, "better", 1.36),
    ("Akshay Bhatia", 20.5, "better", 1.87),
    ("Cam Davis", 20.5, "better", 5.31),
    ("Min Woo Lee", 20.5, "better", 1.26),
    ("Nico Echavarria", 20.5, "better", 2.44),
    ("Billy Horschel", 20.5, "better", 2.38),
    ("Hank Lebioda", 20.5, "better", 5.20),
    ("John Keefer", 20.5, "better", 2.02),
    ("Emilio Gonzalez", 20.5, "better", 4.58),
    ("Zachary Bauchou", 20.5, "better", 4.85),
    ("Christo Lamprecht", 20.5, "better", 7.63),
    ("Adrien Dumont De Chassart", 20.5, "better", 3.16),
    ("Neal Shipley", 20.5, "better", 3.52),
    ("Adrien Saddier", 20.5, "better", 3.70),
    ("Max McGreevy", 20.5, "better", 1.61),
    ("Rasmus Hojgaard", 20.5, "better", 1.36),
    ("Danny Walker", 20.5, "better", 8.25),
    ("Nicolai Hojgaard", 20.5, "better", 1.41),
    ("Brice Garnett", 20.5, "better", 4.71),
    ("Bud Cauley", 20.5, "better", 1.76),
    ("Daniel Berger", 20.5, "better", 1.34),
    ("Webb Simpson", 20.5, "better", 2.09),
    ("Ryan Fox", 20.5, "better", 2.49),
    ("Matt Fitzpatrick", 20.5, "better", 1.11),
    ("Nick Taylor", 20.5, "better", 1.32),
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
    ("Davis Riley", 20.5, "better", 3.79),
    ("Harry Hall", 20.5, "better", 1.14),
    ("Andrew Novak", 20.5, "better", 1.74),
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


def implied_prob(odds: float) -> float:
    """Convert decimal odds to implied probability"""
    if not odds or odds <= 0:
        return 0.5
    return 1.0 / odds


def estimate_stats_from_odds(odds: float) -> dict:
    """
    Estimate player stats based on odds for Top 20 finish.
    
    Logic:
    - Odds < 1.2 = Elite player (SG ~1.5-2.0)
    - Odds 1.2-1.5 = Top tier (SG ~1.0-1.5)
    - Odds 1.5-2.0 = Strong mid (SG ~0.5-1.0)
    - Odds 2.0-3.0 = Mid tier (SG ~0.2-0.5)
    - Odds 3.0-5.0 = Low mid (SG ~0-0.2)
    - Odds > 5.0 = Longshot (SG ~-0.3 to 0)
    """
    impl = implied_prob(odds)
    
    if odds < 1.15:
        tier = "elite"
        sg_total = 1.8
        scoring_avg = 69.0
        birdies = 4.5
    elif odds < 1.3:
        tier = "top"
        sg_total = 1.4
        scoring_avg = 69.5
        birdies = 4.2
    elif odds < 1.5:
        tier = "top"
        sg_total = 1.1
        scoring_avg = 69.8
        birdies = 4.0
    elif odds < 2.0:
        tier = "mid"
        sg_total = 0.7
        scoring_avg = 70.2
        birdies = 3.8
    elif odds < 3.0:
        tier = "mid"
        sg_total = 0.4
        scoring_avg = 70.5
        birdies = 3.5
    elif odds < 5.0:
        tier = "low"
        sg_total = 0.1
        scoring_avg = 71.0
        birdies = 3.2
    else:
        tier = "longshot"
        sg_total = -0.2
        scoring_avg = 71.5
        birdies = 2.8
    
    # Distribute SG across categories (rough approximation)
    sg_ott = sg_total * 0.25  # Off the tee
    sg_app = sg_total * 0.40  # Approach
    sg_arg = sg_total * 0.15  # Around green
    sg_putt = sg_total * 0.20  # Putting
    
    return {
        "tier": tier,
        "scoring_avg": round(scoring_avg, 1),
        "scoring_stddev": round(2.5 + (1 - impl) * 1.5, 1),  # Higher variance for longshots
        "birdies_per_round": round(birdies, 1),
        "sg_total": round(sg_total, 2),
        "sg_ott": round(sg_ott, 2),
        "sg_app": round(sg_app, 2),
        "sg_arg": round(sg_arg, 2),
        "sg_putt": round(sg_putt, 2),
        "sample_size": 20,  # Estimated
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bulk add golf players")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't update")
    args = parser.parse_args()
    
    # Load existing database
    with open(DB_PATH) as f:
        db = json.load(f)
    
    existing_count = len(db)
    print(f"Current database: {existing_count} players")
    print()
    
    # Track additions
    added = []
    skipped = []
    
    for name, line, direction, odds in PHOENIX_MISSING_PLAYERS:
        key = name.lower().strip()
        
        if key in db:
            skipped.append(name)
            continue
        
        stats = estimate_stats_from_odds(odds)
        
        db[key] = {
            "name": name,
            "source": "odds_estimated",
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "odds_reference": odds,
            **stats
        }
        added.append((name, odds, stats["tier"], stats["sg_total"]))
    
    print(f"Players to ADD: {len(added)}")
    print(f"Players SKIPPED (already exist): {len(skipped)}")
    print()
    
    if added:
        print("-" * 70)
        print("NEW PLAYERS:")
        print("-" * 70)
        for name, odds, tier, sg in sorted(added, key=lambda x: x[3], reverse=True):
            print(f"  {name:<30} | {tier:<8} | SG: {sg:+.2f} | Odds: {odds}")
    
    if skipped:
        print()
        print(f"Skipped (already in DB): {', '.join(skipped[:10])}" + ("..." if len(skipped) > 10 else ""))
    
    if args.dry_run:
        print()
        print("🔸 DRY RUN - No changes made")
        print("   Run without --dry-run to apply changes")
    else:
        # Backup first
        BACKUP_PATH.mkdir(exist_ok=True)
        backup_file = BACKUP_PATH / f"player_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, "w") as f:
            json.dump(json.load(open(DB_PATH)), f, indent=2)
        print(f"\n✓ Backup saved to {backup_file.name}")
        
        # Save updated database
        with open(DB_PATH, "w") as f:
            json.dump(db, f, indent=2)
        
        print(f"✓ Database updated: {existing_count} → {len(db)} players (+{len(added)})")


if __name__ == "__main__":
    main()
