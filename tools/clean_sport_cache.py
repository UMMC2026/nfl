#!/usr/bin/env python3
"""
FUOOM ONE-TIME CACHE ISOLATION & CLEANUP SCRIPT
================================================
Purpose: Safely remove cross-sport contamination WITHOUT touching other sports

🔒 Design Rules:
- Delete ONLY the target sport cache
- Preserve audit logs
- Force clean ingest next run
- Idempotent (safe to re-run)

Usage:
    python tools/clean_sport_cache.py cbb
    python tools/clean_sport_cache.py nba --dry-run
    python tools/clean_sport_cache.py tennis --force
    
After running:
    Set skip_ingest=False to force fresh data pull
"""

import shutil
import sys
import argparse
from pathlib import Path
from datetime import datetime
import json

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
AUDIT_DIR = PROJECT_ROOT / "audit" / "cache_cleanup"

# Valid sport identifiers
VALID_SPORTS = {"nba", "cbb", "nfl", "soccer", "tennis", "golf", "cfb", "wnba", "mlb", "nhl"}

# Sport-specific cache locations (some sports have multiple cache dirs)
SPORT_CACHE_PATHS = {
    "nba": [
        CACHE_DIR / "nba_stats",
        PROJECT_ROOT / "data" / "nba",
        PROJECT_ROOT / "state" / "nba",
    ],
    "cbb": [
        PROJECT_ROOT / "sports" / "cbb" / "data" / "cache",
        PROJECT_ROOT / "sports" / "cbb" / "data",
        PROJECT_ROOT / "state" / "cbb",
    ],
    "nfl": [
        PROJECT_ROOT / "nfl" / "cache",
        PROJECT_ROOT / "nfl" / "data" / "cache",
        PROJECT_ROOT / "state" / "nfl",
    ],
    "tennis": [
        PROJECT_ROOT / "tennis" / "cache",
        PROJECT_ROOT / "tennis" / "data" / "cache",
        PROJECT_ROOT / "state" / "tennis",
    ],
    "golf": [
        PROJECT_ROOT / "golf" / "cache",
        PROJECT_ROOT / "golf" / "data" / "cache",
        PROJECT_ROOT / "state" / "golf",
    ],
    "soccer": [
        PROJECT_ROOT / "soccer" / "cache",
        PROJECT_ROOT / "soccer" / "data" / "cache",
        PROJECT_ROOT / "state" / "soccer",
    ],
}


def log_cleanup(sport: str, paths_cleaned: list, dry_run: bool = False):
    """Log cleanup action to audit trail."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": "cache_cleanup",
        "sport": sport,
        "dry_run": dry_run,
        "paths_cleaned": [str(p) for p in paths_cleaned],
        "operator": "tools/clean_sport_cache.py"
    }
    
    audit_file = AUDIT_DIR / f"{sport}_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(audit_file, 'w') as f:
        json.dump(audit_entry, f, indent=2)
    
    print(f"[AUDIT] Logged to {audit_file}")


def find_sport_cache_files(sport: str) -> list:
    """Find all cache files/dirs for a sport."""
    found_paths = []
    
    # Check configured paths
    if sport in SPORT_CACHE_PATHS:
        for path in SPORT_CACHE_PATHS[sport]:
            if path.exists():
                found_paths.append(path)
    
    # Also check generic cache dir for sport-prefixed files
    if CACHE_DIR.exists():
        for item in CACHE_DIR.iterdir():
            if item.name.lower().startswith(sport):
                found_paths.append(item)
    
    # Check for pickle/json cache files with sport prefix
    for pattern in [f"{sport}_*.pkl", f"{sport}_*.json", f"{sport}_cache.*"]:
        for match in PROJECT_ROOT.glob(f"**/{pattern}"):
            if ".venv" not in str(match) and "__pycache__" not in str(match):
                found_paths.append(match)
    
    return list(set(found_paths))


def clean_cache(sport: str, dry_run: bool = False, force: bool = False):
    """
    Clean cache for a specific sport.
    
    Args:
        sport: Sport identifier (nba, cbb, etc.)
        dry_run: If True, show what would be deleted without deleting
        force: Skip confirmation prompt
    """
    sport = sport.lower().strip()
    
    if sport not in VALID_SPORTS:
        raise ValueError(f"Invalid sport: {sport}. Valid options: {', '.join(sorted(VALID_SPORTS))}")
    
    print(f"\n{'='*60}")
    print(f"  FUOOM CACHE CLEANUP — {sport.upper()}")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"{'='*60}\n")
    
    # Find all cache paths
    cache_paths = find_sport_cache_files(sport)
    
    if not cache_paths:
        print(f"[OK] No cache found for {sport.upper()}")
        print("[OK] Cache is already clean. Ready for fresh ingest.")
        return
    
    # Show what will be deleted
    print(f"[INFO] Found {len(cache_paths)} cache location(s) for {sport.upper()}:\n")
    total_size = 0
    for path in cache_paths:
        if path.is_file():
            size = path.stat().st_size
            print(f"  📄 {path} ({size / 1024:.1f} KB)")
        else:
            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            print(f"  📁 {path}/ ({size / 1024:.1f} KB)")
        total_size += size
    
    print(f"\n  Total: {total_size / 1024:.1f} KB\n")
    
    if dry_run:
        print("[DRY-RUN] No changes made. Run without --dry-run to execute.")
        log_cleanup(sport, cache_paths, dry_run=True)
        return
    
    # Confirmation
    if not force:
        confirm = input(f"Delete all {sport.upper()} cache? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("[CANCELLED] No changes made.")
            return
    
    # Execute deletion
    print(f"\n[WARN] Deleting cache for sport={sport.upper()}")
    deleted_paths = []
    
    for path in cache_paths:
        try:
            if path.is_file():
                path.unlink()
                print(f"  ✓ Deleted file: {path}")
            else:
                shutil.rmtree(path)
                path.mkdir(parents=True, exist_ok=True)
                print(f"  ✓ Cleared directory: {path}")
            deleted_paths.append(path)
        except Exception as e:
            print(f"  ✗ Error deleting {path}: {e}")
    
    # Log audit trail
    log_cleanup(sport, deleted_paths, dry_run=False)
    
    print(f"\n[OK] Cache reset complete for {sport.upper()}")
    print("\n" + "="*60)
    print("  NEXT STEPS:")
    print("="*60)
    print(f"  1. Set skip_ingest=False in your {sport.upper()} config")
    print(f"  2. Run the {sport.upper()} pipeline to re-fetch fresh data")
    print(f"  3. Verify no cross-sport contamination in new cache")
    print("="*60 + "\n")


def diagnose_all_caches():
    """Show cache status for all sports."""
    print("\n" + "="*60)
    print("  FUOOM CACHE DIAGNOSTIC")
    print("="*60 + "\n")
    
    for sport in sorted(VALID_SPORTS):
        paths = find_sport_cache_files(sport)
        if paths:
            total_size = 0
            for p in paths:
                if p.is_file():
                    total_size += p.stat().st_size
                elif p.exists():
                    total_size += sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
            print(f"  {sport.upper():<8} {len(paths):>3} location(s)  {total_size/1024:>8.1f} KB")
        else:
            print(f"  {sport.upper():<8}   — (no cache)")
    
    print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="FUOOM One-Time Cache Cleanup — Safely remove sport-specific cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/clean_sport_cache.py cbb              # Clean CBB cache
  python tools/clean_sport_cache.py nba --dry-run    # Show what would be deleted
  python tools/clean_sport_cache.py tennis --force   # Skip confirmation
  python tools/clean_sport_cache.py --diagnose       # Show all cache status
  
After cleaning:
  Set skip_ingest=False to force fresh data pull
        """
    )
    
    parser.add_argument(
        'sport',
        nargs='?',
        help=f'Sport to clean cache for ({", ".join(sorted(VALID_SPORTS))})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without deleting'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    parser.add_argument(
        '--diagnose',
        action='store_true',
        help='Show cache status for all sports'
    )
    
    args = parser.parse_args()
    
    if args.diagnose:
        diagnose_all_caches()
        return
    
    if not args.sport:
        parser.print_help()
        print(f"\nValid sports: {', '.join(sorted(VALID_SPORTS))}")
        sys.exit(1)
    
    try:
        clean_cache(args.sport, dry_run=args.dry_run, force=args.force)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
