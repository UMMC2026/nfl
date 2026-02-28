"""
Tennis Data Backup System

Creates timestamped backups of ALL tennis data:
- Raw CSV files (Sackmann main tour, challengers, futures)
- SQLite database
- Configuration files

Usage:
    python tennis/scripts/backup_tennis_data.py --full
    python tennis/scripts/backup_tennis_data.py --csv-only
    python tennis/scripts/backup_tennis_data.py --db-only
    python tennis/scripts/backup_tennis_data.py --status
    python tennis/scripts/backup_tennis_data.py --restore 20260127_120000

SOP v2.1 Compliant - Tennis Data Backup Layer
"""

import argparse
import shutil
import json
from pathlib import Path
from datetime import datetime
import sqlite3


# ============================================================================
# PATHS
# ============================================================================

TENNIS_DIR = Path(__file__).parent.parent
DATA_DIR = TENNIS_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BACKUP_DIR = Path(__file__).parents[2] / "backups" / "tennis"
BACKUP_MANIFEST = BACKUP_DIR / "backup_manifest.json"

# Tennis data files
DB_PATH = DATA_DIR / "tennis_stats.db"
CONFIG_FILES = [
    DATA_DIR / "player_stats.json",
]


def ensure_dirs():
    """Create backup directories if needed."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def load_manifest() -> dict:
    """Load backup manifest."""
    if BACKUP_MANIFEST.exists():
        return json.loads(BACKUP_MANIFEST.read_text(encoding='utf-8'))
    return {"backups": [], "last_backup": None}


def save_manifest(manifest: dict):
    """Save backup manifest."""
    manifest["last_updated"] = datetime.now().isoformat()
    BACKUP_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def create_full_backup() -> str:
    """Create complete backup of all tennis data."""
    ensure_dirs()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"tennis_full_{timestamp}"
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"CREATING FULL TENNIS BACKUP: {backup_name}")
    print(f"{'='*60}")
    
    files_backed_up = []
    total_size = 0
    
    # 1. Backup raw CSV files
    csv_dir = backup_path / "raw"
    csv_dir.mkdir(exist_ok=True)
    
    print("\n[1/3] Backing up raw CSV files...")
    csv_files = list(RAW_DIR.glob("*.csv")) if RAW_DIR.exists() else []
    
    for csv_file in csv_files:
        dest = csv_dir / csv_file.name
        shutil.copy2(csv_file, dest)
        size = csv_file.stat().st_size
        total_size += size
        files_backed_up.append({
            "type": "csv",
            "name": csv_file.name,
            "size": size
        })
        print(f"  ✓ {csv_file.name} ({size/1024:.0f} KB)")
    
    # 2. Backup database
    print("\n[2/3] Backing up SQLite database...")
    if DB_PATH.exists():
        db_dest = backup_path / "tennis_stats.db"
        shutil.copy2(DB_PATH, db_dest)
        size = DB_PATH.stat().st_size
        total_size += size
        files_backed_up.append({
            "type": "database",
            "name": "tennis_stats.db",
            "size": size
        })
        print(f"  ✓ tennis_stats.db ({size/1024:.0f} KB)")
        
        # Also get DB stats
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM players')
        players = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM matches')
        matches = cur.fetchone()[0]
        conn.close()
        print(f"     → {players:,} players, {matches:,} matches")
    else:
        print("  ⚠ Database not found!")
    
    # 3. Backup config files
    print("\n[3/3] Backing up configuration files...")
    for config_file in CONFIG_FILES:
        if config_file.exists():
            dest = backup_path / config_file.name
            shutil.copy2(config_file, dest)
            size = config_file.stat().st_size
            total_size += size
            files_backed_up.append({
                "type": "config",
                "name": config_file.name,
                "size": size
            })
            print(f"  ✓ {config_file.name} ({size/1024:.0f} KB)")
    
    # Create backup metadata
    metadata = {
        "timestamp": timestamp,
        "created": datetime.now().isoformat(),
        "backup_type": "full",
        "files": files_backed_up,
        "total_size": total_size,
        "csv_count": len(csv_files),
        "path": str(backup_path)
    }
    
    # Save metadata in backup folder
    (backup_path / "backup_info.json").write_text(
        json.dumps(metadata, indent=2), encoding='utf-8'
    )
    
    # Update manifest
    manifest = load_manifest()
    manifest["backups"].append({
        "name": backup_name,
        "type": "full",
        "timestamp": timestamp,
        "total_size": total_size,
        "file_count": len(files_backed_up)
    })
    manifest["last_backup"] = timestamp
    save_manifest(manifest)
    
    print(f"\n{'='*60}")
    print(f"BACKUP COMPLETE")
    print(f"{'='*60}")
    print(f"  Location: {backup_path}")
    print(f"  Files: {len(files_backed_up)}")
    print(f"  Total size: {total_size/1024/1024:.1f} MB")
    
    return backup_name


def backup_csv_only() -> str:
    """Backup only raw CSV files."""
    ensure_dirs()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"tennis_csv_{timestamp}"
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(exist_ok=True)
    
    print(f"\nBacking up CSV files to {backup_name}...")
    
    csv_files = list(RAW_DIR.glob("*.csv")) if RAW_DIR.exists() else []
    total_size = 0
    
    for csv_file in csv_files:
        shutil.copy2(csv_file, backup_path / csv_file.name)
        total_size += csv_file.stat().st_size
        print(f"  ✓ {csv_file.name}")
    
    print(f"\nBackup complete: {len(csv_files)} files, {total_size/1024/1024:.1f} MB")
    return backup_name


def backup_db_only() -> str:
    """Backup only the SQLite database."""
    ensure_dirs()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"tennis_db_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_name
    
    print(f"\nBacking up database to {backup_name}...")
    
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_path)
        print(f"  ✓ {backup_path.name} ({DB_PATH.stat().st_size/1024/1024:.1f} MB)")
    else:
        print("  ⚠ Database not found!")
    
    return backup_name


def show_status():
    """Show backup status and history."""
    ensure_dirs()
    
    print(f"\n{'='*60}")
    print("TENNIS BACKUP STATUS")
    print(f"{'='*60}")
    
    manifest = load_manifest()
    
    # Show data directory status
    print("\n[CURRENT DATA]")
    
    if RAW_DIR.exists():
        csv_files = list(RAW_DIR.glob("*.csv"))
        csv_size = sum(f.stat().st_size for f in csv_files)
        print(f"  CSV Files: {len(csv_files)} files ({csv_size/1024/1024:.1f} MB)")
    else:
        print("  CSV Files: None (raw/ directory not found)")
    
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM players')
        players = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM matches')
        matches = cur.fetchone()[0]
        conn.close()
        print(f"  Database: {DB_PATH.stat().st_size/1024/1024:.1f} MB")
        print(f"    → {players:,} players, {matches:,} matches")
    else:
        print("  Database: Not found")
    
    # Show backup history
    print("\n[BACKUP HISTORY]")
    
    if not manifest.get("backups"):
        print("  No backups found.")
    else:
        print(f"  Last backup: {manifest.get('last_backup', 'Never')}")
        print(f"  Total backups: {len(manifest['backups'])}")
        print("\n  Recent backups:")
        
        for b in sorted(manifest["backups"], key=lambda x: x["timestamp"], reverse=True)[:5]:
            size_mb = b.get("total_size", 0) / 1024 / 1024
            print(f"    • {b['name'][:35]:35} | {b['type']:5} | {size_mb:6.1f} MB")
    
    # Show available backups on disk
    print("\n[BACKUPS ON DISK]")
    backup_dirs = [d for d in BACKUP_DIR.iterdir() if d.is_dir()] if BACKUP_DIR.exists() else []
    backup_files = [f for f in BACKUP_DIR.glob("*.db")] if BACKUP_DIR.exists() else []
    
    all_backups = backup_dirs + backup_files
    if not all_backups:
        print("  No backups found.")
    else:
        for item in sorted(all_backups, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if item.is_dir():
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            else:
                size = item.stat().st_size
            print(f"    • {item.name[:40]:40} | {mtime.strftime('%Y-%m-%d %H:%M')} | {size/1024/1024:.1f} MB")
    
    print(f"\n{'='*60}")


def restore_backup(backup_name: str):
    """Restore from a backup."""
    backup_path = BACKUP_DIR / backup_name
    
    if not backup_path.exists():
        print(f"Backup not found: {backup_name}")
        return False
    
    print(f"\n{'='*60}")
    print(f"RESTORING FROM: {backup_name}")
    print(f"{'='*60}")
    
    # Restore CSV files
    csv_dir = backup_path / "raw"
    if csv_dir.exists():
        print("\n[1/3] Restoring CSV files...")
        RAW_DIR.mkdir(exist_ok=True, parents=True)
        for csv_file in csv_dir.glob("*.csv"):
            shutil.copy2(csv_file, RAW_DIR / csv_file.name)
            print(f"  ✓ {csv_file.name}")
    
    # Restore database
    db_backup = backup_path / "tennis_stats.db"
    if db_backup.exists():
        print("\n[2/3] Restoring database...")
        shutil.copy2(db_backup, DB_PATH)
        print(f"  ✓ tennis_stats.db")
    
    # Restore config files
    print("\n[3/3] Restoring config files...")
    for config_name in ["player_stats.json"]:
        config_backup = backup_path / config_name
        if config_backup.exists():
            shutil.copy2(config_backup, DATA_DIR / config_name)
            print(f"  ✓ {config_name}")
    
    print(f"\n{'='*60}")
    print("RESTORE COMPLETE")
    print(f"{'='*60}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Tennis Data Backup System")
    parser.add_argument('--full', action='store_true', help='Create full backup')
    parser.add_argument('--csv-only', action='store_true', help='Backup CSV files only')
    parser.add_argument('--db-only', action='store_true', help='Backup database only')
    parser.add_argument('--status', action='store_true', help='Show backup status')
    parser.add_argument('--restore', metavar='NAME', help='Restore from backup')
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
    elif args.full:
        create_full_backup()
    elif args.csv_only:
        backup_csv_only()
    elif args.db_only:
        backup_db_only()
    elif args.restore:
        restore_backup(args.restore)
    else:
        # Default: show status
        show_status()
        print("\nUsage:")
        print("  --full      Create full backup (CSV + DB + configs)")
        print("  --csv-only  Backup CSV files only")
        print("  --db-only   Backup database only")
        print("  --status    Show backup status")
        print("  --restore   Restore from backup")


if __name__ == "__main__":
    main()
