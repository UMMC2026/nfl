"""
CBB (College Basketball) DATA BACKUP SYSTEM
============================================
Backup management for CBB data including:
- ESPN API cache
- Player stats cache
- Player overrides

Usage:
    python sports/cbb/data/cbb_data_backup.py --backup      # Create backup
    python sports/cbb/data/cbb_data_backup.py --list        # List backups
    python sports/cbb/data/cbb_data_backup.py --restore ID  # Restore
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# PATHS
# ============================================================================

CBB_DIR = PROJECT_ROOT / "sports" / "cbb"
DATA_DIR = CBB_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
BACKUP_DIR = PROJECT_ROOT / "backups" / "cbb"
BACKUP_MANIFEST = BACKUP_DIR / "backup_manifest.json"

# Ensure directories
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# MANIFEST
# ============================================================================

def load_manifest() -> dict:
    if BACKUP_MANIFEST.exists():
        with open(BACKUP_MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"backups": [], "last_updated": None, "total_backups_created": 0}


def save_manifest(manifest: dict):
    manifest["last_updated"] = datetime.now().isoformat()
    with open(BACKUP_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


# ============================================================================
# BACKUP OPERATIONS
# ============================================================================

def create_backup(reason: str = "manual") -> Dict:
    """Create a full backup of CBB data."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"cbb_backup_{timestamp}"
    backup_path = BACKUP_DIR / backup_id
    backup_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"  CBB DATA BACKUP")
    print(f"  ID: {backup_id}")
    print(f"{'='*60}")
    
    backup_info = {
        "backup_id": backup_id,
        "created": datetime.now().isoformat(),
        "reason": reason,
        "files": [],
        "total_size_bytes": 0
    }
    
    # Backup cache files
    print(f"\n  Backing up cache files...")
    if CACHE_DIR.exists():
        for cache_file in CACHE_DIR.glob("*.json"):
            dest = backup_path / cache_file.name
            shutil.copy2(cache_file, dest)
            backup_info["files"].append({
                "name": cache_file.name,
                "size": cache_file.stat().st_size
            })
            backup_info["total_size_bytes"] += cache_file.stat().st_size
            print(f"       ✓ {cache_file.name}")
    
    # Update manifest
    manifest = load_manifest()
    manifest["backups"].append(backup_info)
    manifest["total_backups_created"] += 1
    save_manifest(manifest)
    
    size_kb = backup_info["total_size_bytes"] / 1024
    print(f"\n  ✓ BACKUP COMPLETE ({size_kb:.1f} KB)")
    print(f"{'='*60}\n")
    
    return backup_info


def list_backups():
    """List all backups."""
    manifest = load_manifest()
    
    print(f"\n{'='*60}")
    print(f"  CBB DATA BACKUPS")
    print(f"{'='*60}")
    
    if not manifest["backups"]:
        print("  No backups found.")
        return
    
    for b in sorted(manifest["backups"], key=lambda x: x["created"], reverse=True)[:10]:
        created = datetime.fromisoformat(b["created"]).strftime("%Y-%m-%d %H:%M")
        size_kb = b["total_size_bytes"] / 1024
        print(f"  {b['backup_id']}")
        print(f"    Created: {created} | Size: {size_kb:.1f} KB | Files: {len(b['files'])}")
    
    print(f"\n  Total: {len(manifest['backups'])} backups")
    print(f"{'='*60}\n")


def restore_backup(backup_id: str) -> bool:
    """Restore a backup."""
    backup_path = BACKUP_DIR / backup_id
    if not backup_path.exists():
        print(f"[ERROR] Backup not found: {backup_id}")
        return False
    
    print(f"\n  ⚠️  Restoring {backup_id}...")
    response = input("  Type 'YES' to confirm: ")
    if response != "YES":
        print("  Cancelled.")
        return False
    
    # Backup current first
    create_backup(reason="pre_restore_safety")
    
    # Restore
    CACHE_DIR.mkdir(exist_ok=True)
    for f in backup_path.glob("*.json"):
        shutil.copy2(f, CACHE_DIR / f.name)
        print(f"       ✓ {f.name}")
    
    print(f"\n  ✓ RESTORE COMPLETE")
    return True


def cleanup_old_backups(keep: int = 10):
    """Remove old backups."""
    manifest = load_manifest()
    backups = sorted(manifest["backups"], key=lambda x: x["created"], reverse=True)
    
    removed = 0
    new_backups = []
    for i, b in enumerate(backups):
        if i < keep:
            new_backups.append(b)
        else:
            path = BACKUP_DIR / b["backup_id"]
            if path.exists():
                shutil.rmtree(path)
                removed += 1
    
    manifest["backups"] = new_backups
    save_manifest(manifest)
    print(f"[CLEANUP] Removed {removed} old backups")


def main():
    parser = argparse.ArgumentParser(description="CBB Data Backup")
    parser.add_argument("--backup", action="store_true", help="Create backup")
    parser.add_argument("--reason", type=str, default="manual")
    parser.add_argument("--list", action="store_true", help="List backups")
    parser.add_argument("--restore", type=str, metavar="ID", help="Restore backup")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup old")
    parser.add_argument("--keep", type=int, default=10)
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    elif args.backup:
        create_backup(args.reason)
    elif args.restore:
        restore_backup(args.restore)
    elif args.cleanup:
        cleanup_old_backups(args.keep)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
