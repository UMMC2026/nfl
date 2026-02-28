"""
MASTER DATA BACKUP SYSTEM
=========================
Unified backup manager for all sports data.

Creates coordinated backups across:
- NBA (stats cache, databases)
- Tennis (Sackmann CSVs, stats DB)
- Golf (player database, DataGolf cache)
- Soccer (API cache)
- CBB (ESPN cache)
- NHL (hardcoded - optional)

Usage:
    python scripts/backup_all_sports.py               # Backup all sports
    python scripts/backup_all_sports.py --status      # Show backup status
    python scripts/backup_all_sports.py --cleanup     # Cleanup old backups
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BACKUP_ROOT = PROJECT_ROOT / "backups"


def backup_all_sports(reason: str = "scheduled"):
    """Run backups for all sports."""
    print("\n" + "="*70)
    print("  MASTER DATA BACKUP - ALL SPORTS")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Reason: {reason}")
    print("="*70)
    
    results = {}
    
    # NBA
    print("\n" + "-"*50)
    print("  🏀 NBA")
    print("-"*50)
    try:
        from scripts.nba_data_backup import create_backup as nba_backup
        info = nba_backup(reason=reason)
        results["nba"] = {"status": "✓", "backup_id": info["backup_id"], "size_kb": info["total_size_bytes"]/1024}
    except Exception as e:
        results["nba"] = {"status": "✗", "error": str(e)}
        print(f"  ✗ NBA backup failed: {e}")
    
    # Tennis
    print("\n" + "-"*50)
    print("  🎾 Tennis")
    print("-"*50)
    try:
        from tennis.scripts.backup_tennis_data import create_full_backup as tennis_backup
        backup_name = tennis_backup()
        results["tennis"] = {"status": "✓", "backup_id": backup_name}
    except Exception as e:
        results["tennis"] = {"status": "✗", "error": str(e)}
        print(f"  ✗ Tennis backup failed: {e}")
    
    # Golf
    print("\n" + "-"*50)
    print("  ⛳ Golf")
    print("-"*50)
    try:
        from golf.tools.golf_data_backup import create_backup as golf_backup
        info = golf_backup(reason=reason)
        results["golf"] = {"status": "✓", "backup_id": info["backup_id"], "size_kb": info["total_size_bytes"]/1024}
    except Exception as e:
        results["golf"] = {"status": "✗", "error": str(e)}
        print(f"  ✗ Golf backup failed: {e}")
    
    # Soccer
    print("\n" + "-"*50)
    print("  ⚽ Soccer")
    print("-"*50)
    try:
        from soccer.data.soccer_data_backup import create_backup as soccer_backup
        info = soccer_backup(reason=reason)
        results["soccer"] = {"status": "✓", "backup_id": info["backup_id"], "size_kb": info["total_size_bytes"]/1024}
    except Exception as e:
        results["soccer"] = {"status": "✗", "error": str(e)}
        print(f"  ✗ Soccer backup failed: {e}")
    
    # CBB
    print("\n" + "-"*50)
    print("  🏀 CBB")
    print("-"*50)
    try:
        from sports.cbb.data.cbb_data_backup import create_backup as cbb_backup
        info = cbb_backup(reason=reason)
        results["cbb"] = {"status": "✓", "backup_id": info["backup_id"], "size_kb": info["total_size_bytes"]/1024}
    except Exception as e:
        results["cbb"] = {"status": "✗", "error": str(e)}
        print(f"  ✗ CBB backup failed: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("  BACKUP SUMMARY")
    print("="*70)
    
    for sport, result in results.items():
        status = result.get("status", "?")
        if status == "✓":
            size = result.get("size_kb", 0)
            print(f"  {status} {sport.upper():8} - {size:.1f} KB")
        elif status == "ℹ":
            print(f"  {status} {sport.upper():8} - {result.get('note', '')}")
        else:
            print(f"  {status} {sport.upper():8} - FAILED: {result.get('error', 'Unknown')}")
    
    print("="*70 + "\n")
    
    return results


def show_status():
    """Show backup status for all sports."""
    print("\n" + "="*70)
    print("  BACKUP STATUS - ALL SPORTS")
    print("="*70)
    
    sports = {
        "nba": BACKUP_ROOT / "nba" / "backup_manifest.json",
        "tennis": PROJECT_ROOT / "tennis" / "data" / "backups" / "backup_manifest.json",
        "golf": BACKUP_ROOT / "golf" / "backup_manifest.json",
        "soccer": BACKUP_ROOT / "soccer" / "backup_manifest.json",
        "cbb": BACKUP_ROOT / "cbb" / "backup_manifest.json",
    }
    
    for sport, manifest_path in sports.items():
        print(f"\n  {sport.upper()}")
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            backups = manifest.get("backups", [])
            if backups:
                latest = sorted(backups, key=lambda x: x.get("created", ""), reverse=True)[0]
                created = latest.get("created", "")[:16].replace("T", " ")
                size_kb = latest.get("total_size_bytes", 0) / 1024
                print(f"    Latest: {created}")
                print(f"    Size:   {size_kb:.1f} KB")
                print(f"    Total:  {len(backups)} backups")
            else:
                print("    No backups yet")
        else:
            print("    No backup manifest found")
    
    print("\n" + "="*70)
    print(f"  Backup Root: {BACKUP_ROOT}")
    print("="*70 + "\n")


def cleanup_all(keep: int = 10):
    """Cleanup old backups for all sports."""
    print("\n[CLEANUP] Removing old backups across all sports...")
    
    try:
        from scripts.nba_data_backup import cleanup_old_backups as nba_cleanup
        print("\n  NBA:")
        nba_cleanup(keep)
    except Exception as e:
        print(f"  NBA cleanup failed: {e}")
    
    try:
        from golf.tools.golf_data_backup import cleanup_old_backups as golf_cleanup
        print("\n  Golf:")
        golf_cleanup(keep)
    except Exception as e:
        print(f"  Golf cleanup failed: {e}")
    
    try:
        from soccer.data.soccer_data_backup import cleanup_old_backups as soccer_cleanup
        print("\n  Soccer:")
        soccer_cleanup(keep)
    except Exception as e:
        print(f"  Soccer cleanup failed: {e}")
    
    try:
        from sports.cbb.data.cbb_data_backup import cleanup_old_backups as cbb_cleanup
        print("\n  CBB:")
        cbb_cleanup(keep)
    except Exception as e:
        print(f"  CBB cleanup failed: {e}")
    
    print("\n[CLEANUP] Complete\n")


def main():
    parser = argparse.ArgumentParser(description="Master Data Backup System")
    parser.add_argument("--status", action="store_true", help="Show backup status")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup old backups")
    parser.add_argument("--keep", type=int, default=10, help="Backups to keep per sport")
    parser.add_argument("--reason", type=str, default="scheduled", help="Backup reason")
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
    elif args.cleanup:
        cleanup_all(args.keep)
    else:
        backup_all_sports(args.reason)


if __name__ == "__main__":
    main()
