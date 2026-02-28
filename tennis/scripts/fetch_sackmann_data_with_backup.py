"""
Fetch Jeff Sackmann ATP/WTA match data with automatic backups.
Downloads latest match CSVs and saves timestamped backups.

Usage:
    python tennis/scripts/fetch_sackmann_data_with_backup.py --year 2024
    python tennis/scripts/fetch_sackmann_data_with_backup.py --year 2024 --tour wta
    python tennis/scripts/fetch_sackmann_data_with_backup.py --list-backups

SOP v2.1 Compliant - Data Layer with Backup Management
"""

import argparse
import urllib.request
import shutil
from pathlib import Path
from datetime import datetime
import json

# ============================================================================
# PATHS
# ============================================================================

TENNIS_DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = TENNIS_DATA_DIR / "raw"
BACKUP_DIR = TENNIS_DATA_DIR / "backups"
BACKUP_LOG = BACKUP_DIR / "backup_manifest.json"

# Ensure directories exist
TENNIS_DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

SACKMANN_BASE_URL = "https://raw.githubusercontent.com/JeffSackmann"

REPO_MAP = {
    "atp": "tennis_atp",
    "wta": "tennis_wta",
}


# ============================================================================
# BACKUP MANAGEMENT
# ============================================================================

def load_backup_manifest() -> dict:
    """Load backup manifest or create empty one."""
    if BACKUP_LOG.exists():
        with open(BACKUP_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"backups": [], "last_updated": None}


def save_backup_manifest(manifest: dict):
    """Save backup manifest."""
    manifest["last_updated"] = datetime.now().isoformat()
    with open(BACKUP_LOG, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def create_backup(source_path: Path) -> Path | None:
    """Create timestamped backup of a CSV file."""
    if not source_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{source_path.stem}_{timestamp}{source_path.suffix}"
    backup_path = BACKUP_DIR / backup_name
    
    shutil.copy2(source_path, backup_path)
    
    # Update manifest
    manifest = load_backup_manifest()
    manifest["backups"].append({
        "filename": backup_name,
        "original": source_path.name,
        "created": datetime.now().isoformat(),
        "size_bytes": backup_path.stat().st_size,
        "lines": len(backup_path.read_text(encoding="utf-8").splitlines())
    })
    save_backup_manifest(manifest)
    
    return backup_path


def list_backups():
    """List all available backups."""
    manifest = load_backup_manifest()
    
    print("\n" + "=" * 70)
    print("  TENNIS DATA BACKUPS")
    print("=" * 70)
    
    if not manifest["backups"]:
        print("  No backups found.")
        print(f"  Backup directory: {BACKUP_DIR}")
        return
    
    # Group by original file
    by_original = {}
    for b in manifest["backups"]:
        orig = b["original"]
        if orig not in by_original:
            by_original[orig] = []
        by_original[orig].append(b)
    
    for orig, backups in sorted(by_original.items()):
        print(f"\n  [{orig}]")
        for b in sorted(backups, key=lambda x: x["created"], reverse=True)[:5]:
            created = datetime.fromisoformat(b["created"]).strftime("%Y-%m-%d %H:%M")
            size_kb = b["size_bytes"] / 1024
            print(f"    • {b['filename'][:45]:45} | {created} | {size_kb:,.0f} KB | {b['lines']:,} rows")
        
        if len(backups) > 5:
            print(f"    ... and {len(backups) - 5} older backups")
    
    print("\n" + "=" * 70)
    print(f"  Total backups: {len(manifest['backups'])}")
    print(f"  Backup dir: {BACKUP_DIR}")
    print("=" * 70 + "\n")


def cleanup_old_backups(keep_per_file: int = 10):
    """Remove old backups, keeping only the most recent N per file."""
    manifest = load_backup_manifest()
    
    # Group by original file
    by_original = {}
    for b in manifest["backups"]:
        orig = b["original"]
        if orig not in by_original:
            by_original[orig] = []
        by_original[orig].append(b)
    
    removed = 0
    new_backups = []
    
    for orig, backups in by_original.items():
        # Sort by created date, newest first
        sorted_backups = sorted(backups, key=lambda x: x["created"], reverse=True)
        
        # Keep the newest N
        for i, b in enumerate(sorted_backups):
            if i < keep_per_file:
                new_backups.append(b)
            else:
                # Remove old backup file
                old_path = BACKUP_DIR / b["filename"]
                if old_path.exists():
                    old_path.unlink()
                    removed += 1
    
    manifest["backups"] = new_backups
    save_backup_manifest(manifest)
    
    if removed > 0:
        print(f"[CLEANUP] Removed {removed} old backups")


# ============================================================================
# FETCH WITH BACKUP
# ============================================================================

def fetch_matches_with_backup(tour: str, year: int) -> bool:
    """Download match CSV with automatic backup of existing file."""
    repo = REPO_MAP.get(tour.lower())
    if not repo:
        print(f"[ERROR] Invalid tour: {tour}. Use 'atp' or 'wta'.")
        return False
    
    filename = f"{tour.lower()}_matches_{year}.csv"
    url = f"{SACKMANN_BASE_URL}/{repo}/master/{filename}"
    
    # Save to raw directory
    output_path = RAW_DIR / filename
    
    # Also keep a copy in main data directory for compatibility
    compat_path = TENNIS_DATA_DIR / filename
    
    print(f"\n[FETCH] {tour.upper()} {year} Matches")
    print(f"        URL: {url}")
    
    # STEP 1: Backup existing file if it exists
    if output_path.exists():
        print(f"[BACKUP] Creating backup of existing {filename}...")
        backup_path = create_backup(output_path)
        if backup_path:
            print(f"         → {backup_path.name}")
    
    # STEP 2: Download new file
    try:
        print(f"[DOWNLOAD] Fetching from GitHub...")
        urllib.request.urlretrieve(url, output_path)
        
        # Verify file
        if output_path.exists() and output_path.stat().st_size > 0:
            line_count = len(output_path.read_text(encoding="utf-8").splitlines())
            size_kb = output_path.stat().st_size / 1024
            print(f"[✓] Downloaded: {line_count:,} rows ({size_kb:,.0f} KB)")
            
            # Copy to compatibility location
            shutil.copy2(output_path, compat_path)
            print(f"[✓] Copied to: {compat_path}")
            
            return True
        else:
            print("[ERROR] File is empty or missing")
            return False
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"[ERROR] File not found (404) - {year} data may not be published yet")
        else:
            print(f"[ERROR] HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to download: {e}")
        return False


def restore_backup(backup_filename: str) -> bool:
    """Restore a specific backup file."""
    backup_path = BACKUP_DIR / backup_filename
    if not backup_path.exists():
        print(f"[ERROR] Backup not found: {backup_filename}")
        return False
    
    # Parse original filename from backup name (e.g., atp_matches_2024_20260202_123456.csv)
    parts = backup_filename.rsplit("_", 2)  # Split from right to get timestamp parts
    if len(parts) >= 3:
        original_name = f"{parts[0]}.csv"
    else:
        print("[ERROR] Cannot determine original filename")
        return False
    
    # Actually it's format: {tour}_matches_{year}_{timestamp}.csv
    # So original is: {tour}_matches_{year}.csv
    name_parts = backup_filename.split("_")
    if len(name_parts) >= 4:
        original_name = f"{name_parts[0]}_matches_{name_parts[2]}.csv"
    
    output_path = RAW_DIR / original_name
    compat_path = TENNIS_DATA_DIR / original_name
    
    print(f"[RESTORE] {backup_filename}")
    print(f"       → {output_path}")
    
    shutil.copy2(backup_path, output_path)
    shutil.copy2(backup_path, compat_path)
    
    print("[✓] Backup restored successfully")
    return True


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Fetch Sackmann tennis data with automatic backups",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Fetch 2024 data (both tours):
    python fetch_sackmann_data_with_backup.py --year 2024
    
  Fetch WTA only:
    python fetch_sackmann_data_with_backup.py --year 2024 --tour wta
    
  List all backups:
    python fetch_sackmann_data_with_backup.py --list-backups
    
  Restore a backup:
    python fetch_sackmann_data_with_backup.py --restore atp_matches_2024_20260202_123456.csv
    
  Cleanup old backups (keep 5 per file):
    python fetch_sackmann_data_with_backup.py --cleanup --keep 5
"""
    )
    parser.add_argument("--year", type=int, default=datetime.now().year, 
                        help="Year to fetch (default: current year)")
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="both",
                        help="Tour to fetch (atp, wta, or both)")
    parser.add_argument("--list-backups", action="store_true",
                        help="List all available backups")
    parser.add_argument("--restore", type=str, metavar="FILENAME",
                        help="Restore a specific backup file")
    parser.add_argument("--cleanup", action="store_true",
                        help="Remove old backups")
    parser.add_argument("--keep", type=int, default=10,
                        help="Number of backups to keep per file (default: 10)")
    
    args = parser.parse_args()
    
    # Handle list-backups
    if args.list_backups:
        list_backups()
        return 0
    
    # Handle restore
    if args.restore:
        return 0 if restore_backup(args.restore) else 1
    
    # Handle cleanup
    if args.cleanup:
        cleanup_old_backups(args.keep)
        return 0
    
    # Regular fetch with backup
    print("\n" + "=" * 60)
    print("  TENNIS DATA FETCHER (WITH BACKUP)")
    print("=" * 60)
    print(f"  Year: {args.year}")
    print(f"  Tour: {args.tour.upper()}")
    print(f"  Backup Dir: {BACKUP_DIR}")
    print("=" * 60)
    
    success = True
    
    if args.tour in ["atp", "both"]:
        success &= fetch_matches_with_backup("atp", args.year)
    
    if args.tour in ["wta", "both"]:
        success &= fetch_matches_with_backup("wta", args.year)
    
    # Cleanup old backups automatically
    cleanup_old_backups(args.keep)
    
    print("\n" + "=" * 60)
    if success:
        print("  ✓ FETCH COMPLETE")
        print("\n  Next steps:")
        print("  1. Run: python tennis/data/tennis_csv_importer.py --import <file>")
        print("  2. Or use the main menu for tennis analysis")
    else:
        print("  ✗ FETCH FAILED (check errors above)")
        print("  Note: 2025/2026 data may not be published yet on GitHub")
    print("=" * 60 + "\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
