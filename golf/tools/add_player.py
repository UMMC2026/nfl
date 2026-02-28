"""
Golf Player Manual Entry Tool
=============================
Quickly add players to the database with stats from free sources.

Usage:
    python golf/tools/add_player.py

Free Stat Sources:
    1. PGA Tour Stats: https://www.pgatour.com/stats
       - Scoring Average: Stats > Scoring > Scoring Average
       - Birdies/Round: Stats > Scoring > Birdie Average
       - SG Total: Stats > Strokes Gained > Total
       
    2. ESPN Golf: https://www.espn.com/golf/statistics
       - Quick overview of scoring, birdies, eagles
       
    3. Golf Stats Pro: https://www.golfstatspro.com
       - Detailed strokes gained breakdowns
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from golf.data.player_database import PlayerDatabase, KNOWN_PLAYERS


def print_header():
    print("=" * 60)
    print("⛳ GOLF PLAYER MANUAL ENTRY")
    print("=" * 60)
    print()
    print("📊 FREE STAT SOURCES:")
    print("   • PGA Tour: pgatour.com/stats")
    print("   • ESPN:     espn.com/golf/statistics")
    print("   • DataGolf: datagolf.com (rankings are free)")
    print()


def get_float_input(prompt: str, default: float = None) -> float:
    """Get float input with optional default."""
    if default is not None:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    
    while True:
        val = input(prompt).strip()
        if not val and default is not None:
            return default
        try:
            return float(val)
        except ValueError:
            print("   ⚠️  Please enter a valid number")


def get_tier_from_sg(sg_total: float) -> str:
    """Determine tier based on SG Total."""
    if sg_total >= 2.0:
        return "elite"
    elif sg_total >= 1.0:
        return "top"
    elif sg_total >= 0.5:
        return "mid"
    elif sg_total >= 0.0:
        return "average"
    else:
        return "below_average"


def add_player_interactive():
    """Interactive player entry."""
    print_header()
    
    # Get player name
    name = input("Player Name: ").strip()
    if not name:
        print("❌ Name required")
        return
    
    # Check if exists
    if name in KNOWN_PLAYERS:
        print(f"\n⚠️  {name} already exists in database!")
        existing = KNOWN_PLAYERS[name]
        print(f"   Current SG Total: {existing.get('sg_total', 'N/A')}")
        overwrite = input("   Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            return
    
    print(f"\n📝 Enter stats for {name}:")
    print("   (Press Enter for PGA Tour average defaults)")
    print()
    
    # Core stats
    scoring_avg = get_float_input("   Scoring Average", 70.8)
    scoring_stddev = get_float_input("   Scoring Std Dev", 3.0)
    birdies = get_float_input("   Birdies per Round", 4.2)
    
    # Strokes Gained (most important for matchups)
    print()
    print("   📊 STROKES GAINED (from pgatour.com/stats > Strokes Gained)")
    sg_total = get_float_input("   SG Total", 0.0)
    
    # Optional SG breakdown
    print()
    print("   📊 SG BREAKDOWN (optional, press Enter to skip)")
    sg_ott = get_float_input("   SG Off-the-Tee", 0.0)
    sg_app = get_float_input("   SG Approach", 0.0)
    sg_arg = get_float_input("   SG Around Green", 0.0)
    sg_putt = get_float_input("   SG Putting", 0.0)
    
    # Sample size
    print()
    sample_size = int(get_float_input("   Rounds in sample (est.)", 40))
    
    # Auto-determine tier
    tier = get_tier_from_sg(sg_total)
    
    # Build player dict
    player_data = {
        "scoring_avg": scoring_avg,
        "scoring_stddev": scoring_stddev,
        "birdies_per_round": birdies,
        "sg_total": sg_total,
        "sg_ott": sg_ott,
        "sg_app": sg_app,
        "sg_arg": sg_arg,
        "sg_putt": sg_putt,
        "tier": tier,
        "sample_size": sample_size,
    }
    
    # Preview
    print()
    print("=" * 60)
    print(f"📋 PLAYER PROFILE: {name}")
    print("=" * 60)
    print(f"   Scoring: {scoring_avg} ± {scoring_stddev}")
    print(f"   Birdies: {birdies}/round")
    print(f"   SG Total: {sg_total:+.2f} ({tier.upper()} tier)")
    print(f"   SG Breakdown: OTT {sg_ott:+.2f} | APP {sg_app:+.2f} | ARG {sg_arg:+.2f} | PUTT {sg_putt:+.2f}")
    print(f"   Sample: {sample_size} rounds")
    print()
    
    # Confirm
    confirm = input("Save this player? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled")
        return
    
    # Save to database
    db = PlayerDatabase()
    db.add_player(name, player_data)
    db.save()
    
    print(f"\n✅ {name} added to database!")
    print(f"   Total players: {len(db)}")


def bulk_add_players():
    """Add multiple players at once."""
    print_header()
    print("📋 BULK ADD MODE")
    print("   Enter player data in format:")
    print("   NAME, SCORING_AVG, BIRDIES, SG_TOTAL")
    print()
    print("   Example:")
    print("   Collin Morikawa, 69.5, 4.3, 1.5")
    print("   Tony Finau, 69.8, 4.1, 1.2")
    print()
    print("   Type 'done' when finished")
    print()
    
    db = PlayerDatabase()
    added = 0
    
    while True:
        line = input(">> ").strip()
        if line.lower() == 'done':
            break
        if not line:
            continue
        
        try:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                print("   ⚠️  Need: NAME, SCORING_AVG, BIRDIES, SG_TOTAL")
                continue
            
            name = parts[0]
            scoring_avg = float(parts[1])
            birdies = float(parts[2])
            sg_total = float(parts[3])
            
            player_data = {
                "scoring_avg": scoring_avg,
                "scoring_stddev": 3.0,  # Default
                "birdies_per_round": birdies,
                "sg_total": sg_total,
                "tier": get_tier_from_sg(sg_total),
                "sample_size": 40,
            }
            
            db.add_player(name, player_data)
            print(f"   ✓ Added {name} (SG: {sg_total:+.2f})")
            added += 1
            
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    if added > 0:
        db.save()
        print(f"\n✅ Added {added} players to database!")
        print(f"   Total players: {len(db)}")


def list_players():
    """List all players in database."""
    print_header()
    print("📋 CURRENT DATABASE")
    print()
    
    db = PlayerDatabase()
    players = db.list_players()
    
    # Group by tier
    by_tier = {"elite": [], "top": [], "mid": [], "average": [], "below_average": [], "unknown": []}
    
    for name in players:
        stats = db.get_player(name)
        if stats:
            tier = stats.get("tier", "unknown")
            sg = stats.get("sg_total", 0)
            by_tier.get(tier, by_tier["unknown"]).append((name, sg))
    
    for tier, tier_players in by_tier.items():
        if tier_players:
            print(f"\n🏆 {tier.upper()} TIER:")
            for name, sg in sorted(tier_players, key=lambda x: -x[1]):
                print(f"   • {name}: SG {sg:+.2f}")
    
    print(f"\n📊 Total: {len(players)} players")


def main():
    print()
    print("=" * 60)
    print("⛳ GOLF PLAYER DATABASE TOOL")
    print("=" * 60)
    print()
    print("Options:")
    print("  [1] Add single player (interactive)")
    print("  [2] Bulk add players (CSV-style)")
    print("  [3] List all players")
    print("  [0] Exit")
    print()
    
    choice = input("Select: ").strip()
    
    if choice == "1":
        add_player_interactive()
    elif choice == "2":
        bulk_add_players()
    elif choice == "3":
        list_players()
    else:
        print("Goodbye!")


if __name__ == "__main__":
    main()
