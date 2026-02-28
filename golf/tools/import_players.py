"""
Golf Player Database Import from CSV/JSON
==========================================
Bulk import player stats from external files.

Supports:
- CSV import (PGA Tour exports, manual spreadsheets)
- JSON import (DataGolf exports, backups)
- PGA Tour Stats scrape format

Usage:
    python golf/tools/import_players.py data.csv
    python golf/tools/import_players.py players.json
    python golf/tools/import_players.py --pgatour sg_total.csv
"""

import sys
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from golf.data.player_database import PlayerDatabase


# =============================================================================
# COLUMN MAPPINGS (handle different export formats)
# =============================================================================

# Standard column name mappings
COLUMN_MAPPINGS = {
    # Name variants
    "player_name": "name",
    "player": "name",
    "golfer": "name",
    "dg_player_name": "name",
    
    # SG Total variants
    "sg_total": "sg_total",
    "sg total": "sg_total",
    "strokes gained total": "sg_total",
    "sg:total": "sg_total",
    "total": "sg_total",
    
    # SG Off-Tee
    "sg_ott": "sg_ott",
    "sg off-the-tee": "sg_ott",
    "sg:ott": "sg_ott",
    "sg off tee": "sg_ott",
    "strokes gained off-the-tee": "sg_ott",
    
    # SG Approach
    "sg_app": "sg_app",
    "sg approach": "sg_app",
    "sg:app": "sg_app",
    "sg approach the green": "sg_app",
    "strokes gained approach": "sg_app",
    
    # SG Around Green
    "sg_arg": "sg_arg",
    "sg around-the-green": "sg_arg",
    "sg:arg": "sg_arg",
    "sg around green": "sg_arg",
    "strokes gained around-the-green": "sg_arg",
    
    # SG Putting
    "sg_putt": "sg_putt",
    "sg putting": "sg_putt",
    "sg:putt": "sg_putt",
    "strokes gained putting": "sg_putt",
    
    # Scoring
    "scoring_avg": "scoring_avg",
    "scoring average": "scoring_avg",
    "avg": "scoring_avg",
    "average": "scoring_avg",
    
    # Other
    "driving_dist": "driving_dist",
    "driving distance": "driving_dist",
    "avg driving distance": "driving_dist",
    
    "driving_acc": "driving_acc",
    "driving accuracy": "driving_acc",
    "fairways hit": "driving_acc",
}


def normalize_column_name(col: str) -> str:
    """Map various column names to standard fields."""
    col_lower = col.lower().strip()
    return COLUMN_MAPPINGS.get(col_lower, col_lower)


def import_csv(file_path: Path, source: str = "csv_import") -> Dict:
    """
    Import players from CSV file.
    
    Expected format (flexible column names):
    name, sg_total, sg_ott, sg_app, sg_arg, sg_putt, scoring_avg
    
    Returns:
        {added: [], updated: [], skipped: []}
    """
    results = {"added": [], "updated": [], "skipped": []}
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return results
    
    db = PlayerDatabase()
    
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        # Normalize headers
        fieldnames = [normalize_column_name(h) for h in reader.fieldnames]
        
        if "name" not in fieldnames:
            print(f"❌ CSV must have a 'name' or 'player' column")
            print(f"   Found columns: {reader.fieldnames}")
            return results
        
        row_num = 0
        for row in reader:
            row_num += 1
            
            # Normalize row keys
            normalized_row = {
                normalize_column_name(k): v 
                for k, v in row.items()
            }
            
            name = normalized_row.get("name", "").strip()
            if not name:
                results["skipped"].append(f"Row {row_num}: No name")
                continue
            
            # Parse numeric fields
            try:
                sg_total = float(normalized_row.get("sg_total", 0) or 0)
            except (ValueError, TypeError):
                sg_total = 0.0
            
            try:
                sg_ott = float(normalized_row.get("sg_ott", 0) or 0)
            except (ValueError, TypeError):
                sg_ott = 0.0
            
            try:
                sg_app = float(normalized_row.get("sg_app", 0) or 0)
            except (ValueError, TypeError):
                sg_app = 0.0
            
            try:
                sg_arg = float(normalized_row.get("sg_arg", 0) or 0)
            except (ValueError, TypeError):
                sg_arg = 0.0
            
            try:
                sg_putt = float(normalized_row.get("sg_putt", 0) or 0)
            except (ValueError, TypeError):
                sg_putt = 0.0
            
            try:
                scoring_avg = float(normalized_row.get("scoring_avg", 0) or 0)
                if scoring_avg == 0:
                    # Estimate from SG total
                    scoring_avg = 70.8 - sg_total
            except (ValueError, TypeError):
                scoring_avg = 70.8 - sg_total
            
            # Determine tier
            if sg_total >= 2.0:
                tier = "elite"
            elif sg_total >= 1.0:
                tier = "top"
            elif sg_total >= 0.0:
                tier = "mid"
            else:
                tier = "average"
            
            # Check existing
            existing = db.get_player(name)
            is_new = existing is None
            
            # Add to database
            db.players[name.lower()] = {
                "name": name,
                "scoring_avg": round(scoring_avg, 2),
                "scoring_stddev": 3.0,
                "birdies_per_round": 4.0 + (sg_total * 0.3),
                "sg_total": round(sg_total, 2),
                "sg_ott": round(sg_ott, 2),
                "sg_app": round(sg_app, 2),
                "sg_arg": round(sg_arg, 2),
                "sg_putt": round(sg_putt, 2),
                "tier": tier,
                "source": source,
                "sample_size": 30,
                "updated": datetime.now().strftime("%Y-%m-%d"),
            }
            
            if is_new:
                results["added"].append(name)
            else:
                results["updated"].append(name)
    
    db.save()
    return results


def import_json(file_path: Path, source: str = "json_import") -> Dict:
    """
    Import players from JSON file.
    
    Supports formats:
    1. Direct player dict: {"player_name": {stats...}, ...}
    2. DataGolf rankings: {"rankings": [{player_name, sg_total, ...}]}
    3. Array format: [{name, sg_total, ...}, ...]
    """
    results = {"added": [], "updated": [], "skipped": []}
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return results
    
    with open(file_path, "r") as f:
        data = json.load(f)
    
    db = PlayerDatabase()
    
    # Detect format
    if isinstance(data, dict):
        if "rankings" in data:
            # DataGolf rankings format
            players = data["rankings"]
        elif "players" in data:
            # Skill decompositions format
            players = data["players"]
        else:
            # Direct player dict format
            players = [{"name": k, **v} for k, v in data.items()]
    elif isinstance(data, list):
        players = data
    else:
        print(f"❌ Unknown JSON format")
        return results
    
    for p in players:
        name = p.get("name") or p.get("player_name") or p.get("dg_player_name")
        if not name:
            results["skipped"].append("No name field")
            continue
        
        sg_total = p.get("sg_total", 0) or 0
        
        # Determine tier
        if sg_total >= 2.0:
            tier = "elite"
        elif sg_total >= 1.0:
            tier = "top"
        elif sg_total >= 0.0:
            tier = "mid"
        else:
            tier = "average"
        
        existing = db.get_player(name)
        is_new = existing is None
        
        db.players[name.lower()] = {
            "name": name,
            "scoring_avg": p.get("scoring_avg", 70.8 - sg_total),
            "scoring_stddev": p.get("scoring_stddev", 3.0),
            "birdies_per_round": p.get("birdies_per_round", 4.0 + sg_total * 0.3),
            "sg_total": round(sg_total, 2),
            "sg_ott": round(p.get("sg_ott", 0) or 0, 2),
            "sg_app": round(p.get("sg_app", 0) or 0, 2),
            "sg_arg": round(p.get("sg_arg", 0) or 0, 2),
            "sg_putt": round(p.get("sg_putt", 0) or 0, 2),
            "tier": tier,
            "source": source,
            "sample_size": p.get("sample_size", 30),
            "updated": datetime.now().strftime("%Y-%m-%d"),
        }
        
        if is_new:
            results["added"].append(name)
        else:
            results["updated"].append(name)
    
    db.save()
    return results


def import_pgatour_format(file_path: Path) -> Dict:
    """
    Import from PGA Tour Stats export format.
    
    Typical format from pgatour.com/stats CSV export:
    PLAYER NAME, ROUNDS, SG: TOTAL
    """
    return import_csv(file_path, source="pgatour")


def main():
    parser = argparse.ArgumentParser(description="Import golf player stats")
    parser.add_argument("file", type=Path, help="CSV or JSON file to import")
    parser.add_argument("--source", default=None, help="Source label for imports")
    parser.add_argument("--pgatour", action="store_true", help="PGA Tour stats format")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    
    args = parser.parse_args()
    
    file_path = Path(args.file)
    
    if not file_path.exists():
        # Check in golf/data directory
        alt_path = PROJECT_ROOT / "golf" / "data" / file_path.name
        if alt_path.exists():
            file_path = alt_path
        else:
            print(f"❌ File not found: {file_path}")
            sys.exit(1)
    
    print(f"\n📥 Importing from: {file_path}")
    
    # Create backup first
    from golf.tools.sync_players import create_backup
    create_backup()
    
    # Detect format and import
    if file_path.suffix.lower() == ".json":
        source = args.source or "json_import"
        results = import_json(file_path, source=source)
    elif file_path.suffix.lower() == ".csv":
        source = args.source or ("pgatour" if args.pgatour else "csv_import")
        results = import_csv(file_path, source=source)
    else:
        print(f"❌ Unsupported file format: {file_path.suffix}")
        print("   Supported: .csv, .json")
        sys.exit(1)
    
    # Report results
    print(f"\n✅ Import complete:")
    print(f"   Added:   {len(results['added'])} players")
    print(f"   Updated: {len(results['updated'])} players")
    if results['skipped']:
        print(f"   Skipped: {len(results['skipped'])} entries")
        for skip in results['skipped'][:5]:
            print(f"      - {skip}")


if __name__ == "__main__":
    main()
