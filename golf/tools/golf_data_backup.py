"""
GOLF DATA BACKUP SYSTEM
=======================
Comprehensive backup management for Golf data including:
- DataGolf API cache responses
- Player database
- Tournament predictions
- Course adjustments

Usage:
    python golf/tools/golf_data_backup.py --backup           # Create full backup
    python golf/tools/golf_data_backup.py --list             # List all backups
    python golf/tools/golf_data_backup.py --restore ID       # Restore specific backup
    python golf/tools/golf_data_backup.py --sync-and-backup  # Sync from API then backup
    python golf/tools/golf_data_backup.py --cleanup          # Remove old backups

SOP Compliant - Data Layer with Manifest Tracking
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# PATHS
# ============================================================================

GOLF_DIR = PROJECT_ROOT / "golf"
DATA_DIR = GOLF_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"  # DataGolf API cache
BACKUP_DIR = PROJECT_ROOT / "backups" / "golf"
BACKUP_MANIFEST = BACKUP_DIR / "backup_manifest.json"

# Files to backup
FILES_TO_BACKUP = [
    DATA_DIR / "player_database.json",
]

# Ensure directories exist
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# MANIFEST MANAGEMENT
# ============================================================================

def load_manifest() -> dict:
    """Load backup manifest or create empty one."""
    if BACKUP_MANIFEST.exists():
        with open(BACKUP_MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "backups": [],
        "last_updated": None,
        "total_backups_created": 0
    }


def save_manifest(manifest: dict):
    """Save backup manifest."""
    manifest["last_updated"] = datetime.now().isoformat()
    with open(BACKUP_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def get_file_hash(filepath: Path) -> str:
    """Get MD5 hash of file for change detection."""
    if not filepath.exists():
        return ""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()[:12]


# ============================================================================
# BACKUP OPERATIONS
# ============================================================================

def create_backup(reason: str = "manual") -> Dict:
    """Create a full backup of Golf data."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"golf_backup_{timestamp}"
    backup_path = BACKUP_DIR / backup_id
    backup_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"  GOLF DATA BACKUP")
    print(f"  ID: {backup_id}")
    print(f"  Reason: {reason}")
    print(f"{'='*60}")
    
    backup_info = {
        "backup_id": backup_id,
        "created": datetime.now().isoformat(),
        "reason": reason,
        "files": [],
        "api_cache": [],
        "total_size_bytes": 0
    }
    
    # 1. Backup player database and config files
    print(f"\n[1/2] Backing up data files...")
    for filepath in FILES_TO_BACKUP:
        if filepath.exists():
            dest = backup_path / filepath.name
            shutil.copy2(filepath, dest)
            backup_info["files"].append({
                "name": filepath.name,
                "size": filepath.stat().st_size,
                "hash": get_file_hash(filepath)
            })
            backup_info["total_size_bytes"] += filepath.stat().st_size
            print(f"       ✓ {filepath.name}")
    
    # Also backup from the existing backup dir (consolidate)
    old_backup_dir = DATA_DIR / "backups"
    if old_backup_dir.exists():
        old_backups = list(old_backup_dir.glob("player_database_*.json"))
        if old_backups:
            # Just note them, don't duplicate
            print(f"       ℹ {len(old_backups)} existing backups in data/backups/")
    
    # 2. Backup DataGolf API cache
    print(f"\n[2/2] Backing up API cache...")
    cache_backup_dir = backup_path / "api_cache"
    cache_backup_dir.mkdir(exist_ok=True)
    
    if CACHE_DIR.exists():
        cache_files = list(CACHE_DIR.glob("*.json"))
        for cache_file in cache_files:
            dest = cache_backup_dir / cache_file.name
            shutil.copy2(cache_file, dest)
            backup_info["api_cache"].append({
                "name": cache_file.name,
                "size": cache_file.stat().st_size
            })
            backup_info["total_size_bytes"] += cache_file.stat().st_size
            print(f"       ✓ {cache_file.name}")
    
    if not backup_info["api_cache"]:
        print(f"       ℹ No API cache files found")
    
    # Update manifest
    manifest = load_manifest()
    manifest["backups"].append(backup_info)
    manifest["total_backups_created"] += 1
    save_manifest(manifest)
    
    # Summary
    size_kb = backup_info["total_size_bytes"] / 1024
    print(f"\n{'='*60}")
    print(f"  ✓ BACKUP COMPLETE")
    print(f"  Location: {backup_path}")
    print(f"  Size: {size_kb:.1f} KB")
    print(f"  Files: {len(backup_info['files'])} data + {len(backup_info['api_cache'])} cache")
    print(f"{'='*60}\n")
    
    return backup_info


def list_backups():
    """List all available backups."""
    manifest = load_manifest()
    
    print(f"\n{'='*70}")
    print(f"  GOLF DATA BACKUPS")
    print(f"{'='*70}")
    
    if not manifest["backups"]:
        print("  No backups found.")
        print(f"  Backup directory: {BACKUP_DIR}")
        
        # Check old backup location
        old_backup_dir = DATA_DIR / "backups"
        if old_backup_dir.exists():
            old_backups = list(old_backup_dir.glob("player_database_*.json"))
            if old_backups:
                print(f"\n  ℹ {len(old_backups)} legacy backups in golf/data/backups/")
        return
    
    # Sort by date, newest first
    backups = sorted(manifest["backups"], key=lambda x: x["created"], reverse=True)
    
    for b in backups[:15]:
        created = datetime.fromisoformat(b["created"]).strftime("%Y-%m-%d %H:%M")
        size_kb = b["total_size_bytes"] / 1024
        file_count = len(b.get("files", [])) + len(b.get("api_cache", []))
        reason = b.get("reason", "unknown")[:30]
        
        print(f"  {b['backup_id']}")
        print(f"    Created: {created} | Size: {size_kb:.1f} KB | Files: {file_count} | {reason}")
    
    if len(backups) > 15:
        print(f"\n  ... and {len(backups) - 15} older backups")
    
    print(f"\n{'='*70}")
    print(f"  Total backups: {len(backups)}")
    print(f"  Backup dir: {BACKUP_DIR}")
    print(f"{'='*70}\n")


def restore_backup(backup_id: str) -> bool:
    """Restore a specific backup."""
    backup_path = BACKUP_DIR / backup_id
    
    if not backup_path.exists():
        print(f"[ERROR] Backup not found: {backup_id}")
        return False
    
    print(f"\n{'='*60}")
    print(f"  RESTORING BACKUP: {backup_id}")
    print(f"{'='*60}")
    
    # Confirm
    print("\n  ⚠️  WARNING: This will overwrite current data!")
    response = input("  Type 'YES' to confirm: ")
    if response != "YES":
        print("  Restore cancelled.")
        return False
    
    # Create backup of current state before restore
    print("\n  Creating safety backup of current state...")
    create_backup(reason="pre_restore_safety")
    
    # 1. Restore data files
    print(f"\n[1/2] Restoring data files...")
    for filepath in FILES_TO_BACKUP:
        backup_file = backup_path / filepath.name
        if backup_file.exists():
            shutil.copy2(backup_file, filepath)
            print(f"       ✓ {filepath.name}")
    
    # 2. Restore API cache
    cache_backup = backup_path / "api_cache"
    if cache_backup.exists():
        print(f"\n[2/2] Restoring API cache...")
        for cache_file in cache_backup.glob("*.json"):
            dest = CACHE_DIR / cache_file.name
            shutil.copy2(cache_file, dest)
            print(f"       ✓ {cache_file.name}")
    
    print(f"\n{'='*60}")
    print(f"  ✓ RESTORE COMPLETE")
    print(f"{'='*60}\n")
    
    return True


def cleanup_old_backups(keep_count: int = 10):
    """Remove old backups, keeping only the most recent N."""
    manifest = load_manifest()
    
    print(f"\n[CLEANUP] Keeping {keep_count} most recent backups...")
    
    # Sort by date, newest first
    backups = sorted(manifest["backups"], key=lambda x: x["created"], reverse=True)
    
    new_backups = []
    removed = 0
    
    for i, b in enumerate(backups):
        if i < keep_count:
            new_backups.append(b)
        else:
            # Remove backup directory
            backup_path = BACKUP_DIR / b["backup_id"]
            if backup_path.exists():
                shutil.rmtree(backup_path)
                removed += 1
                print(f"       ✗ Removed: {b['backup_id']}")
    
    manifest["backups"] = new_backups
    save_manifest(manifest)
    
    print(f"[CLEANUP] Removed {removed} old backups, kept {len(new_backups)}")


def sync_and_backup():
    """Sync from DataGolf API then create backup."""
    print("\n" + "="*60)
    print("  SYNC & BACKUP")
    print("="*60)
    
    # Try to sync from DataGolf
    try:
        from golf.tools.sync_players import sync_from_datagolf
        print("\n[1/2] Syncing from DataGolf API...")
        results = sync_from_datagolf()
        
        if results.get("added") or results.get("updated"):
            print(f"       Added: {len(results.get('added', []))}")
            print(f"       Updated: {len(results.get('updated', []))}")
    except Exception as e:
        print(f"⚠️  Sync skipped: {e}")
    
    # Create backup
    print("\n[2/2] Creating backup...")
    create_backup(reason="post_sync")


def export_to_csv():
    """Export player database to CSV."""
    db_path = DATA_DIR / "player_database.json"
    if not db_path.exists():
        print("❌ No player database found")
        return
    
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle both formats: {players: {...}} or direct player dict
    if "players" in data:
        players = data["players"]
    else:
        players = data  # Direct player dict format
    
    export_path = PROJECT_ROOT / "outputs" / f"golf_players_export_{datetime.now().strftime('%Y%m%d')}.csv"
    
    with open(export_path, "w", encoding="utf-8") as f:
        f.write("name,tier,sg_total,sg_ott,sg_app,sg_arg,sg_putt,scoring_avg,source,updated\n")
        
        for key, p in sorted(players.items()):
            if isinstance(p, dict):  # Skip non-player entries
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
    
    print(f"\n✅ Exported {len(players)} players to: {export_path}")


# ============================================================================
# AUTO-BACKUP HOOK
# ============================================================================

def auto_backup_after_sync(reason: str = "api_sync"):
    """
    Call this after DataGolf API sync to create automatic backup.
    Only creates backup if not already done today.
    """
    manifest = load_manifest()
    
    # Check if we already backed up today
    today = datetime.now().date().isoformat()
    recent_backups = [b for b in manifest["backups"] if b["created"].startswith(today)]
    
    if recent_backups:
        return None  # Already have today's backup
    
    return create_backup(reason=reason)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Golf Data Backup System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Create backup:
    python golf_data_backup.py --backup
    python golf_data_backup.py --backup --reason "pre-tournament"
    
  List all backups:
    python golf_data_backup.py --list
    
  Restore a backup:
    python golf_data_backup.py --restore golf_backup_20260202_123456
    
  Sync from DataGolf API then backup:
    python golf_data_backup.py --sync-and-backup
    
  Cleanup old backups:
    python golf_data_backup.py --cleanup --keep 10
    
  Export to CSV:
    python golf_data_backup.py --export
"""
    )
    parser.add_argument("--backup", action="store_true", help="Create a backup now")
    parser.add_argument("--reason", type=str, default="manual", help="Reason for backup")
    parser.add_argument("--list", action="store_true", help="List all backups")
    parser.add_argument("--restore", type=str, metavar="BACKUP_ID", help="Restore specific backup")
    parser.add_argument("--sync-and-backup", action="store_true", help="Sync from API then backup")
    parser.add_argument("--cleanup", action="store_true", help="Remove old backups")
    parser.add_argument("--keep", type=int, default=10, help="Backups to keep (default: 10)")
    parser.add_argument("--export", action="store_true", help="Export to CSV")
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    elif args.backup:
        create_backup(reason=args.reason)
    elif args.restore:
        restore_backup(args.restore)
    elif args.sync_and_backup:
        sync_and_backup()
    elif args.cleanup:
        cleanup_old_backups(args.keep)
    elif args.export:
        export_to_csv()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
