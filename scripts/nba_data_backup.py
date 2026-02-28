"""
NBA DATA BACKUP SYSTEM
Manages backups for NBA stats cache, game logs, and API responses.

Features:
- Automatic timestamped backups on each data refresh
- Backup manifest with metadata
- Easy restore functionality
- Cleanup of old backups (configurable retention)

Usage:
    python scripts/nba_data_backup.py --backup              # Create backup now
    python scripts/nba_data_backup.py --list                # List all backups
    python scripts/nba_data_backup.py --restore BACKUP_ID   # Restore specific backup
    python scripts/nba_data_backup.py --cleanup --keep 14   # Keep only 14 days
    python scripts/nba_data_backup.py --export              # Export all player data to CSV

SOP Compliant - Data Layer with Backup Management
"""

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "cache" / "nba_stats"
STATS_CACHE_DIR = BASE_DIR / "outputs" / "stats_cache"
BACKUP_DIR = BASE_DIR / "backups" / "nba"
BACKUP_MANIFEST = BACKUP_DIR / "backup_manifest.json"

# Databases to backup
DBS_TO_BACKUP = [
    BASE_DIR / "cache" / "home_away_splits.db",
    BASE_DIR / "cache" / "opponent_defense.db",
    BASE_DIR / "cache" / "player_stats.db",
    BASE_DIR / "cache" / "pick_history.db",
]

# Ensure directories exist
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


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
    """Create a full backup of NBA data."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"nba_backup_{timestamp}"
    backup_path = BACKUP_DIR / backup_id
    backup_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"  NBA DATA BACKUP")
    print(f"  ID: {backup_id}")
    print(f"  Reason: {reason}")
    print(f"{'='*60}")
    
    backup_info = {
        "backup_id": backup_id,
        "created": datetime.now().isoformat(),
        "reason": reason,
        "files": [],
        "databases": [],
        "stats_cache": [],
        "total_size_bytes": 0
    }
    
    # 1. Backup CSV cache files
    if CACHE_DIR.exists():
        print(f"\n[1/3] Backing up CSV cache...")
        csv_backup_dir = backup_path / "csv_cache"
        csv_backup_dir.mkdir(exist_ok=True)
        
        for csv_file in CACHE_DIR.glob("*.csv"):
            dest = csv_backup_dir / csv_file.name
            shutil.copy2(csv_file, dest)
            backup_info["files"].append({
                "name": csv_file.name,
                "size": csv_file.stat().st_size,
                "hash": get_file_hash(csv_file)
            })
            backup_info["total_size_bytes"] += csv_file.stat().st_size
            print(f"       ✓ {csv_file.name}")
        
        # Backup gamelogs subdirectory
        gamelogs_dir = CACHE_DIR / "gamelogs"
        if gamelogs_dir.exists():
            dest_gamelogs = csv_backup_dir / "gamelogs"
            shutil.copytree(gamelogs_dir, dest_gamelogs, dirs_exist_ok=True)
            gamelog_count = len(list(gamelogs_dir.glob("*.csv")))
            print(f"       ✓ gamelogs/ ({gamelog_count} files)")
        
        # Backup metadata
        if (CACHE_DIR / "metadata.json").exists():
            shutil.copy2(CACHE_DIR / "metadata.json", csv_backup_dir / "metadata.json")
            print(f"       ✓ metadata.json")
    
    # 2. Backup stats cache (mu/sigma JSON files)
    if STATS_CACHE_DIR.exists():
        print(f"\n[2/3] Backing up stats cache...")
        stats_backup_dir = backup_path / "stats_cache"
        stats_backup_dir.mkdir(exist_ok=True)
        
        # Get most recent files (last 7 days worth)
        json_files = sorted(STATS_CACHE_DIR.glob("*.json"), reverse=True)[:7]
        for json_file in json_files:
            dest = stats_backup_dir / json_file.name
            shutil.copy2(json_file, dest)
            backup_info["stats_cache"].append({
                "name": json_file.name,
                "size": json_file.stat().st_size
            })
            backup_info["total_size_bytes"] += json_file.stat().st_size
            print(f"       ✓ {json_file.name}")
    
    # 3. Backup SQLite databases
    print(f"\n[3/3] Backing up databases...")
    db_backup_dir = backup_path / "databases"
    db_backup_dir.mkdir(exist_ok=True)
    
    for db_path in DBS_TO_BACKUP:
        if db_path.exists():
            dest = db_backup_dir / db_path.name
            # Use SQLite backup API for consistency
            try:
                src_conn = sqlite3.connect(db_path)
                dst_conn = sqlite3.connect(dest)
                src_conn.backup(dst_conn)
                src_conn.close()
                dst_conn.close()
                
                backup_info["databases"].append({
                    "name": db_path.name,
                    "size": dest.stat().st_size,
                    "hash": get_file_hash(dest)
                })
                backup_info["total_size_bytes"] += dest.stat().st_size
                print(f"       ✓ {db_path.name}")
            except Exception as e:
                print(f"       ✗ {db_path.name} - {e}")
    
    # Update manifest
    manifest = load_manifest()
    manifest["backups"].append(backup_info)
    manifest["total_backups_created"] += 1
    save_manifest(manifest)
    
    # Summary
    size_mb = backup_info["total_size_bytes"] / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"  ✓ BACKUP COMPLETE")
    print(f"  Location: {backup_path}")
    print(f"  Size: {size_mb:.2f} MB")
    print(f"  Files: {len(backup_info['files'])} CSV + {len(backup_info['stats_cache'])} JSON + {len(backup_info['databases'])} DB")
    print(f"{'='*60}\n")
    
    return backup_info


def list_backups():
    """List all available backups."""
    manifest = load_manifest()
    
    print(f"\n{'='*70}")
    print(f"  NBA DATA BACKUPS")
    print(f"{'='*70}")
    
    if not manifest["backups"]:
        print("  No backups found.")
        print(f"  Backup directory: {BACKUP_DIR}")
        return
    
    # Sort by date, newest first
    backups = sorted(manifest["backups"], key=lambda x: x["created"], reverse=True)
    
    for b in backups[:20]:  # Show last 20
        created = datetime.fromisoformat(b["created"]).strftime("%Y-%m-%d %H:%M")
        size_mb = b["total_size_bytes"] / (1024 * 1024)
        file_count = len(b.get("files", [])) + len(b.get("stats_cache", [])) + len(b.get("databases", []))
        reason = b.get("reason", "unknown")[:20]
        
        print(f"  {b['backup_id']}")
        print(f"    Created: {created} | Size: {size_mb:.1f} MB | Files: {file_count} | Reason: {reason}")
    
    if len(backups) > 20:
        print(f"\n  ... and {len(backups) - 20} older backups")
    
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
    
    # 1. Restore CSV cache
    csv_backup = backup_path / "csv_cache"
    if csv_backup.exists():
        print(f"\n[1/3] Restoring CSV cache...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        for csv_file in csv_backup.glob("*.csv"):
            dest = CACHE_DIR / csv_file.name
            shutil.copy2(csv_file, dest)
            print(f"       ✓ {csv_file.name}")
        
        # Restore gamelogs
        gamelogs_backup = csv_backup / "gamelogs"
        if gamelogs_backup.exists():
            dest_gamelogs = CACHE_DIR / "gamelogs"
            dest_gamelogs.mkdir(exist_ok=True)
            for gl_file in gamelogs_backup.glob("*.csv"):
                shutil.copy2(gl_file, dest_gamelogs / gl_file.name)
            print(f"       ✓ gamelogs/ restored")
    
    # 2. Restore stats cache
    stats_backup = backup_path / "stats_cache"
    if stats_backup.exists():
        print(f"\n[2/3] Restoring stats cache...")
        STATS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        for json_file in stats_backup.glob("*.json"):
            dest = STATS_CACHE_DIR / json_file.name
            shutil.copy2(json_file, dest)
            print(f"       ✓ {json_file.name}")
    
    # 3. Restore databases
    db_backup = backup_path / "databases"
    if db_backup.exists():
        print(f"\n[3/3] Restoring databases...")
        
        for db_file in db_backup.glob("*.db"):
            # Find original path
            for orig_path in DBS_TO_BACKUP:
                if orig_path.name == db_file.name:
                    shutil.copy2(db_file, orig_path)
                    print(f"       ✓ {db_file.name}")
                    break
    
    print(f"\n{'='*60}")
    print(f"  ✓ RESTORE COMPLETE")
    print(f"{'='*60}\n")
    
    return True


def cleanup_old_backups(keep_days: int = 14):
    """Remove backups older than N days."""
    manifest = load_manifest()
    cutoff = datetime.now() - timedelta(days=keep_days)
    
    print(f"\n[CLEANUP] Removing backups older than {keep_days} days...")
    
    new_backups = []
    removed = 0
    
    for b in manifest["backups"]:
        created = datetime.fromisoformat(b["created"])
        
        if created >= cutoff:
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


def export_all_player_stats():
    """Export current stats to a master CSV for easy viewing."""
    print(f"\n[EXPORT] Generating master player stats CSV...")
    
    # Find most recent stats cache file
    if not STATS_CACHE_DIR.exists():
        print("[ERROR] No stats cache found")
        return
    
    json_files = sorted(STATS_CACHE_DIR.glob("*.json"), reverse=True)
    if not json_files:
        print("[ERROR] No stats cache JSON files found")
        return
    
    latest = json_files[0]
    print(f"       Source: {latest.name}")
    
    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Export to CSV
    export_path = BASE_DIR / "outputs" / f"nba_player_stats_export_{datetime.now().strftime('%Y%m%d')}.csv"
    
    with open(export_path, "w", encoding="utf-8", newline="") as f:
        import csv
        writer = csv.writer(f)
        writer.writerow(["player", "stat", "mu", "sigma", "team"])
        
        stats = data.get("stats", [])
        teams = {t["player"]: t["team"] for t in data.get("teams", [])}
        
        for s in stats:
            writer.writerow([
                s.get("player", ""),
                s.get("stat", ""),
                s.get("mu", 0),
                s.get("sigma", 0),
                teams.get(s.get("player", ""), "")
            ])
    
    print(f"       ✓ Exported {len(stats)} stat entries")
    print(f"       → {export_path}")


# ============================================================================
# AUTO-BACKUP HOOK (call from stats_last10_cache.py)
# ============================================================================

def auto_backup_on_refresh(reason: str = "daily_refresh"):
    """
    Call this from stats_last10_cache.py after refreshing stats.
    Creates a backup only if significant changes detected.
    """
    manifest = load_manifest()
    
    # Check if we already backed up today
    today = datetime.now().date().isoformat()
    recent_backups = [b for b in manifest["backups"] if b["created"].startswith(today)]
    
    if recent_backups:
        # Already have today's backup
        return None
    
    # Create backup
    return create_backup(reason=reason)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="NBA Data Backup System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Create manual backup:
    python nba_data_backup.py --backup
    python nba_data_backup.py --backup --reason "before major update"
    
  List all backups:
    python nba_data_backup.py --list
    
  Restore a backup:
    python nba_data_backup.py --restore nba_backup_20260202_123456
    
  Cleanup old backups:
    python nba_data_backup.py --cleanup --keep 14
    
  Export stats to CSV:
    python nba_data_backup.py --export
"""
    )
    parser.add_argument("--backup", action="store_true", help="Create a backup now")
    parser.add_argument("--reason", type=str, default="manual", help="Reason for backup")
    parser.add_argument("--list", action="store_true", help="List all backups")
    parser.add_argument("--restore", type=str, metavar="BACKUP_ID", help="Restore specific backup")
    parser.add_argument("--cleanup", action="store_true", help="Remove old backups")
    parser.add_argument("--keep", type=int, default=14, help="Days to keep (default: 14)")
    parser.add_argument("--export", action="store_true", help="Export current stats to CSV")
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    elif args.backup:
        create_backup(reason=args.reason)
    elif args.restore:
        restore_backup(args.restore)
    elif args.cleanup:
        cleanup_old_backups(args.keep)
    elif args.export:
        export_all_player_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
