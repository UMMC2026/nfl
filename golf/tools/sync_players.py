"""
Golf Player Database Sync Tool
==============================
Syncs player stats from DataGolf API, manages backups, and provides
a complete data management workflow.

Usage:
    python golf/tools/sync_players.py --sync        # Sync from DataGolf API
    python golf/tools/sync_players.py --backup      # Create backup
    python golf/tools/sync_players.py --restore     # Restore from backup
    python golf/tools/sync_players.py --status      # Show database status
    python golf/tools/sync_players.py --tournament  # Pre-tournament field sync
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from golf.data.player_database import PlayerDatabase, DATABASE_FILE, KNOWN_PLAYERS

# Backup configuration
BACKUP_DIR = PROJECT_ROOT / "golf" / "data" / "backups"
MAX_BACKUPS = 10  # Keep last N backups


def create_backup() -> Path:
    """Create timestamped backup of player database."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    if not DATABASE_FILE.exists():
        print("⚠️  No database file to backup")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"player_database_{timestamp}.json"
    
    shutil.copy(DATABASE_FILE, backup_file)
    print(f"✅ Backup created: {backup_file.name}")
    
    # Cleanup old backups
    cleanup_old_backups()
    
    return backup_file


def cleanup_old_backups():
    """Keep only the most recent N backups."""
    backups = sorted(BACKUP_DIR.glob("player_database_*.json"), reverse=True)
    for old_backup in backups[MAX_BACKUPS:]:
        old_backup.unlink()
        print(f"  🗑️  Removed old backup: {old_backup.name}")


def list_backups() -> List[Path]:
    """List all available backups."""
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("player_database_*.json"), reverse=True)


def restore_backup(backup_path: Optional[Path] = None) -> bool:
    """Restore database from backup."""
    backups = list_backups()
    
    if not backups:
        print("❌ No backups available")
        return False
    
    if backup_path is None:
        print("\n📦 Available backups:")
        for i, bp in enumerate(backups, 1):
            stat = bp.stat()
            modified = datetime.fromtimestamp(stat.st_mtime)
            size_kb = stat.st_size / 1024
            print(f"  [{i}] {bp.name}  ({size_kb:.1f} KB, {modified:%Y-%m-%d %H:%M})")
        
        choice = input("\nSelect backup to restore [1]: ").strip() or "1"
        try:
            idx = int(choice) - 1
            backup_path = backups[idx]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            return False
    
    # Create backup before restore (safety)
    create_backup()
    
    # Restore
    shutil.copy(backup_path, DATABASE_FILE)
    print(f"✅ Restored from: {backup_path.name}")
    return True


def sync_from_datagolf(field_players: Optional[List[str]] = None) -> Dict:
    """
    Sync player stats from DataGolf API.
    
    Args:
        field_players: Optional list of specific players to sync (tournament field)
        
    Returns:
        Dict with sync results {added: [], updated: [], failed: []}
    """
    try:
        from golf.ingest.datagolf_client import DataGolfClient
    except ImportError:
        print("❌ DataGolf client not available")
        return {"added": [], "updated": [], "failed": ["Client import error"]}
    
    results = {"added": [], "updated": [], "failed": []}
    
    try:
        client = DataGolfClient()
        print("🔄 Fetching SG decompositions from DataGolf...")
        
        # Get all player skills
        players = client.get_skill_decompositions(tour="pga", force_refresh=True)
        print(f"   Found {len(players)} players in DataGolf")
        
        # Load current database
        db = PlayerDatabase()
        
        # Filter to field if provided
        if field_players:
            field_set = {p.lower().strip() for p in field_players}
            players = [p for p in players if any(
                name in p.get("player_name", "").lower() 
                for name in field_set
            )]
            print(f"   Filtering to {len(players)} field players")
        
        for p in players:
            name = p.get("player_name", "")
            if not name:
                continue
            
            try:
                # Calculate scoring avg from SG total (approximate)
                sg_total = p.get("sg_total", 0) or 0
                scoring_avg = 70.8 - sg_total  # Tour avg is 70.8
                
                # Determine tier from SG total
                if sg_total >= 2.0:
                    tier = "elite"
                elif sg_total >= 1.0:
                    tier = "top"
                elif sg_total >= 0.0:
                    tier = "mid"
                else:
                    tier = "average"
                
                # Check if exists
                existing = db.get_player(name)
                is_new = existing is None
                
                # Add/update in database
                db.players[name.lower()] = {
                    "name": name,
                    "scoring_avg": round(scoring_avg, 2),
                    "scoring_stddev": 3.0,  # Default
                    "birdies_per_round": 4.0 + (sg_total * 0.3),  # Estimate
                    "sg_total": round(sg_total, 2),
                    "sg_ott": round(p.get("sg_ott", 0) or 0, 2),
                    "sg_app": round(p.get("sg_app", 0) or 0, 2),
                    "sg_arg": round(p.get("sg_arg", 0) or 0, 2),
                    "sg_putt": round(p.get("sg_putt", 0) or 0, 2),
                    "tier": tier,
                    "source": "datagolf",
                    "sample_size": 50,  # DataGolf uses rolling windows
                    "updated": datetime.now().strftime("%Y-%m-%d"),
                }
                
                if is_new:
                    results["added"].append(name)
                else:
                    results["updated"].append(name)
                    
            except Exception as e:
                results["failed"].append(f"{name}: {e}")
        
        # Save database
        db.save()
        print(f"\n✅ Sync complete:")
        print(f"   Added:   {len(results['added'])} players")
        print(f"   Updated: {len(results['updated'])} players")
        if results["failed"]:
            print(f"   Failed:  {len(results['failed'])} players")
            
    except ValueError as e:
        if "API key" in str(e):
            print("⚠️  DataGolf API key not configured")
            print("   Set DATAGOLF_API_KEY in .env or environment")
            print("   Using manual entry mode instead")
        else:
            raise
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        results["failed"].append(str(e))
    
    return results


def show_database_status():
    """Show current database status and statistics."""
    db = PlayerDatabase()
    
    print("\n" + "="*60)
    print("📊 GOLF PLAYER DATABASE STATUS")
    print("="*60)
    
    # Overall stats
    total = len(db.players)
    by_source = {}
    by_tier = {}
    stale = []
    
    for name, stats in db.players.items():
        source = stats.get("source", "unknown")
        tier = stats.get("tier", "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        by_tier[tier] = by_tier.get(tier, 0) + 1
        
        # Check staleness
        updated = stats.get("updated", "2020-01-01")
        try:
            updated_date = datetime.strptime(updated, "%Y-%m-%d")
            if (datetime.now() - updated_date).days > 60:
                stale.append(stats.get("name", name))
        except:
            stale.append(stats.get("name", name))
    
    print(f"\n📈 Total Players: {total}")
    
    print(f"\n📦 By Source:")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"   {source:15} {count:3} ({pct:.0f}%)")
    
    print(f"\n🏆 By Tier:")
    tier_order = ["elite", "top", "mid", "average", "unknown"]
    for tier in tier_order:
        if tier in by_tier:
            count = by_tier[tier]
            pct = count / total * 100
            emoji = {"elite": "🥇", "top": "🥈", "mid": "🥉", "average": "📊", "unknown": "❓"}
            print(f"   {emoji.get(tier, '')} {tier:10} {count:3} ({pct:.0f}%)")
    
    if stale:
        print(f"\n⚠️  Stale Data (>60 days):")
        for name in stale[:5]:
            print(f"   - {name}")
        if len(stale) > 5:
            print(f"   ... and {len(stale)-5} more")
    
    # Database file info
    if DATABASE_FILE.exists():
        stat = DATABASE_FILE.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        size_kb = stat.st_size / 1024
        print(f"\n📁 Database File:")
        print(f"   Path:     {DATABASE_FILE}")
        print(f"   Size:     {size_kb:.1f} KB")
        print(f"   Modified: {modified:%Y-%m-%d %H:%M}")
    
    # Backup status
    backups = list_backups()
    print(f"\n💾 Backups: {len(backups)} available")
    if backups:
        latest = backups[0]
        latest_mod = datetime.fromtimestamp(latest.stat().st_mtime)
        print(f"   Latest:   {latest.name} ({latest_mod:%Y-%m-%d %H:%M})")
    
    print("="*60)


def sync_tournament_field():
    """Interactive tournament field sync."""
    print("\n🏌️ TOURNAMENT FIELD SYNC")
    print("="*50)
    print("Paste player names (one per line), then blank line to finish:\n")
    
    field = []
    while True:
        line = input().strip()
        if not line:
            break
        field.append(line)
    
    if not field:
        print("❌ No players entered")
        return
    
    print(f"\n📋 {len(field)} players in field")
    
    # Create backup first
    create_backup()
    
    # Try API sync for these players
    results = sync_from_datagolf(field_players=field)
    
    # For players not found in DataGolf, seed them
    db = PlayerDatabase()
    for name in field:
        if db.get_player(name) is None:
            print(f"   ⚠️  Seeding unknown player: {name}")
            db.seed_player(name)
    
    db.save()
    print("\n✅ Tournament field synced")


def main():
    parser = argparse.ArgumentParser(description="Golf Player Database Manager")
    parser.add_argument("--sync", action="store_true", help="Sync from DataGolf API")
    parser.add_argument("--backup", action="store_true", help="Create backup")
    parser.add_argument("--restore", action="store_true", help="Restore from backup")
    parser.add_argument("--status", action="store_true", help="Show database status")
    parser.add_argument("--tournament", action="store_true", help="Sync tournament field")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive menu")
    
    args = parser.parse_args()
    
    if args.sync:
        create_backup()
        sync_from_datagolf()
    elif args.backup:
        create_backup()
    elif args.restore:
        restore_backup()
    elif args.status:
        show_database_status()
    elif args.tournament:
        sync_tournament_field()
    elif args.interactive or len(sys.argv) == 1:
        interactive_menu()
    else:
        parser.print_help()


def interactive_menu():
    """Interactive database management menu."""
    while True:
        print("\n" + "="*50)
        print("🏌️ GOLF PLAYER DATABASE MANAGER")
        print("="*50)
        print("\n[1] 📊 Show Status")
        print("[2] 🔄 Sync from DataGolf API")
        print("[3] 🏆 Sync Tournament Field")
        print("[4] 💾 Create Backup")
        print("[5] ♻️  Restore from Backup")
        print("[6] ➕ Add Player Manually")
        print("[7] 🔍 Search Player")
        print("[8] 📋 Export to CSV")
        print("\n[Q] Quit")
        
        choice = input("\nSelect option: ").strip().upper()
        
        if choice == "1":
            show_database_status()
        elif choice == "2":
            create_backup()
            sync_from_datagolf()
        elif choice == "3":
            sync_tournament_field()
        elif choice == "4":
            create_backup()
        elif choice == "5":
            restore_backup()
        elif choice == "6":
            add_player_manual()
        elif choice == "7":
            search_player()
        elif choice == "8":
            export_to_csv()
        elif choice == "Q":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid option")


def add_player_manual():
    """Add player manually."""
    print("\n➕ ADD PLAYER MANUALLY")
    print("-"*40)
    
    name = input("Player name: ").strip()
    if not name:
        return
    
    db = PlayerDatabase()
    existing = db.get_player(name)
    if existing:
        print(f"⚠️  Player exists: {existing.get('name')}")
        if input("Update? [y/N]: ").strip().lower() != "y":
            return
    
    print("\nEnter stats (press Enter for default):")
    
    try:
        scoring = input("  Scoring Avg [70.8]: ").strip()
        scoring_avg = float(scoring) if scoring else 70.8
        
        sg = input("  SG Total [0.0]: ").strip()
        sg_total = float(sg) if sg else 0.0
        
        sg_ott = input("  SG Off-Tee [0.0]: ").strip()
        sg_ott = float(sg_ott) if sg_ott else 0.0
        
        sg_app = input("  SG Approach [0.0]: ").strip()
        sg_app = float(sg_app) if sg_app else 0.0
        
        sg_arg = input("  SG Around-Green [0.0]: ").strip()
        sg_arg = float(sg_arg) if sg_arg else 0.0
        
        sg_putt = input("  SG Putting [0.0]: ").strip()
        sg_putt = float(sg_putt) if sg_putt else 0.0
        
        # Determine tier
        if sg_total >= 2.0:
            tier = "elite"
        elif sg_total >= 1.0:
            tier = "top"
        elif sg_total >= 0.0:
            tier = "mid"
        else:
            tier = "average"
        
        db.add_player(
            name=name,
            scoring_avg=scoring_avg,
            sg_total=sg_total,
            sg_ott=sg_ott,
            sg_app=sg_app,
            sg_arg=sg_arg,
            sg_putt=sg_putt,
            source="manual"
        )
        
        print(f"\n✅ Added: {name} (Tier: {tier}, SG: {sg_total:+.2f})")
        
    except ValueError as e:
        print(f"❌ Invalid input: {e}")


def search_player():
    """Search for player in database."""
    query = input("\n🔍 Search player: ").strip()
    if not query:
        return
    
    db = PlayerDatabase()
    
    # Search all players
    matches = []
    for key, stats in db.players.items():
        if query.lower() in key or query.lower() in stats.get("name", "").lower():
            matches.append(stats)
    
    if not matches:
        print(f"❌ No players found matching '{query}'")
        return
    
    print(f"\n📋 Found {len(matches)} player(s):\n")
    for p in matches[:10]:
        print(f"  {p.get('name', '?')}")
        print(f"    Tier:    {p.get('tier', '?')}")
        print(f"    SG Tot:  {p.get('sg_total', 0):+.2f}")
        print(f"    Scoring: {p.get('scoring_avg', 70.8):.1f}")
        print(f"    Source:  {p.get('source', '?')}")
        print(f"    Updated: {p.get('updated', '?')}")
        print()


def export_to_csv():
    """Export database to CSV."""
    db = PlayerDatabase()
    
    csv_path = DATABASE_FILE.parent / "player_database_export.csv"
    
    with open(csv_path, "w") as f:
        f.write("name,tier,sg_total,sg_ott,sg_app,sg_arg,sg_putt,scoring_avg,source,updated\n")
        
        for key, p in sorted(db.players.items()):
            f.write(f"{p.get('name', key)},"
                   f"{p.get('tier', '')},"
                   f"{p.get('sg_total', 0)},"
                   f"{p.get('sg_ott', 0)},"
                   f"{p.get('sg_app', 0)},"
                   f"{p.get('sg_arg', 0)},"
                   f"{p.get('sg_putt', 0)},"
                   f"{p.get('scoring_avg', 70.8)},"
                   f"{p.get('source', '')},"
                   f"{p.get('updated', '')}\n")
    
    print(f"\n✅ Exported to: {csv_path}")


if __name__ == "__main__":
    main()
