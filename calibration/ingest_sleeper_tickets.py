"""
Sleeper Ticket Ingestion — Convert real-money user tickets to calibration data

PURPOSE: This is GOLD-STANDARD calibration data from actual market conditions.
         NOT synthetic backtest data. Treat as EVALUATION & CORRECTION authority.

GOVERNANCE: All picks are truth-labeled with actual outcomes.
            Risk tags derived from position, role, and stat type.
"""
import csv
import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Set
import hashlib

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# --- DATA MODELS ---

@dataclass
class SleeperPick:
    """Single pick from Sleeper ticket"""
    player: str
    full_name: str
    stat: str
    line: float
    direction: str  # OVER or UNDER
    actual: float
    result: str  # WON or LOST
    game: str
    box_score: Optional[str] = None
    
    # Derived fields
    margin: float = 0.0
    hit: bool = False
    risk_tags: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.risk_tags is None:
            self.risk_tags = []
        self._compute_derived()
    
    def _compute_derived(self):
        """Compute margin and hit from actual vs line"""
        if self.direction == "OVER":
            self.margin = self.actual - self.line
            self.hit = self.actual > self.line
        else:  # UNDER
            self.margin = self.line - self.actual
            self.hit = self.actual < self.line

# --- RISK TAGGING ENGINE ---

STAT_CATEGORIES = {
    "PTS": "points",
    "AST": "assists", 
    "REB": "rebounds",
    "3PM": "3pm",
    "BLK": "blocks",
    "STL": "steals",
    "PRA": "pts+reb+ast",
    "PTS+AST": "pts+ast",
    "AST+REB": "ast+reb",
    "REB+AST": "reb+ast",
    "BLK+STL": "blk+stl",
}

# Position inference from player name (simplified - can be enhanced with roster data)
BIG_MEN = {
    "Rudy Gobert", "Alperen Sengun", "Domantas Sabonis", "Jonas Valanciunas",
    "Bobby Portis", "Kyle Filipowski", "Clint Capela", "Bam Adebayo",
    "Isaiah Stewart", "Yves Missi", "Evan Mobley", "Precious Achiuwa",
}

HIGH_USAGE_PLAYERS = {
    "Alperen Sengun", "Cade Cunningham", "Lauri Markkanen", "Jaylen Brown",
    "Kevin Durant", "Jimmy Butler", "Zion Williamson", "De'Aaron Fox",
}

BENCH_MICROWAVE_PLAYERS = {
    "Marcus Smart", "Duncan Robinson", "Bobby Portis", "Matas Buzelis",
    "Isaiah Collier", "Ryan Rollins", "Kris Dunn", "Kelly Oubre Jr.",
}


def apply_risk_tags(pick: SleeperPick) -> List[str]:
    """Apply structural risk tags based on pick characteristics"""
    tags = []
    
    # 3.1 Position / Role Risk — Big man rebound tail risk
    if pick.stat == "REB" and pick.full_name in BIG_MEN:
        tags.append("BIG_REB_TAIL_RISK")
    
    # 3.2 Combo Stat Volatility
    if pick.stat in ["PRA", "PTS+AST", "AST+REB", "REB+AST"]:
        tags.append("COMBO_HIGH_VARIANCE")
    
    # 3.3 3PM Volume Risk — Low volume shooter risk
    if pick.stat == "3PM" and pick.line >= 2.0:
        tags.append("HIGH_LINE_3PM")
    
    # 3.4 High usage UNDER risk
    if pick.direction == "UNDER" and pick.full_name in HIGH_USAGE_PLAYERS:
        tags.append("HIGH_USAGE_UNDER_RISK")
    
    # 3.5 Bench microwave risk (pts/ast volatility)
    if pick.full_name in BENCH_MICROWAVE_PLAYERS and pick.stat in ["PTS", "AST", "PTS+AST"]:
        tags.append("BENCH_MICROWAVE_RISK")
    
    # 3.6 Heavy tail loss detection (actual >> line for UNDER)
    if pick.direction == "UNDER" and pick.margin < -5:
        tags.append("TAIL_BLOWUP")
    
    return tags


# --- INGESTION ENGINE ---

def parse_json_ticket(data: dict) -> List[SleeperPick]:
    """Parse JSON ticket data into SleeperPick objects"""
    picks = []
    for result in data.get("results", []):
        pick = SleeperPick(
            player=result["player"],
            full_name=result["full_name"],
            stat=result["stat"],
            line=float(result["line"]),
            direction=result["direction"],
            actual=float(result["actual"]),
            result=result["result"],
            game=result["game"],
            box_score=result.get("box_score"),
        )
        pick.risk_tags = apply_risk_tags(pick)
        picks.append(pick)
    return picks


def parse_csv_ticket(csv_path: Path) -> List[SleeperPick]:
    """Parse CSV ticket data into SleeperPick objects"""
    picks = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pick = SleeperPick(
                player=row["player"],
                full_name=row.get("full_name", row["player"]),
                stat=row["stat"],
                line=float(row["line"]),
                direction=row["direction"],
                actual=float(row["actual"]),
                result=row["result"],
                game=row["game"],
                box_score=row.get("box_score"),
            )
            pick.risk_tags = apply_risk_tags(pick)
            picks.append(pick)
    return picks


def generate_pick_id(pick: SleeperPick, date: str) -> str:
    """Generate unique pick ID"""
    key = f"{date}_{pick.full_name}_{pick.stat}_{pick.line}_{pick.direction}"
    return f"sleeper_{hashlib.md5(key.encode()).hexdigest()[:12]}"


def normalize_stat(stat: str) -> str:
    """Normalize stat type to calibration format"""
    return STAT_CATEGORIES.get(stat, stat.lower())


def normalize_direction(direction: str) -> str:
    """Normalize direction to calibration format"""
    if direction.upper() in ["OVER", "HIGHER"]:
        return "Higher"
    return "Lower"


# --- CALIBRATION OUTPUT ---

def to_calibration_row(pick: SleeperPick, date: str, sport: str = "nba") -> dict:
    """Convert SleeperPick to calibration CSV row format"""
    pick_id = generate_pick_id(pick, date)
    
    return {
        "pick_id": pick_id,
        "date": date,
        "sport": sport,
        "player": pick.full_name,
        "stat": normalize_stat(pick.stat),
        "line": pick.line,
        "direction": normalize_direction(pick.direction),
        "probability": 50.0,  # Unknown probability from user picks
        "tier": "USER_PICK",  # Special tier for user-submitted picks
        "actual": pick.actual,
        "hit": str(pick.hit),
        "brier": "",  # Cannot compute without probability
        # Extended fields for analysis
        "margin": pick.margin,
        "risk_tags": "|".join(pick.risk_tags) if pick.risk_tags else "",
        "truth_source": "REAL_MONEY_USER_TICKET",
        "platform": "Sleeper",
        "game": pick.game,
    }


def to_calibration_history_row(pick: SleeperPick, date: str) -> dict:
    """Convert to calibration_history.csv format (legacy)"""
    return {
        "date": date,
        "player": pick.full_name,
        "stat": normalize_stat(pick.stat),
        "line": pick.line,
        "direction": normalize_direction(pick.direction).lower(),
        "predicted_prob": "",
        "decision": "",
        "actual_result": "hit" if pick.hit else "miss",
        "role": "",
        "gate_warnings": "|".join(pick.risk_tags) if pick.risk_tags else "",
        "stat_type": normalize_stat(pick.stat),
    }


def ingest_to_calibration(picks: List[SleeperPick], date: str, output_dir: Optional[Path] = None):
    """Ingest picks to calibration CSV files"""
    if output_dir is None:
        output_dir = Path(__file__).parent
    
    # --- Write to calibration/picks.csv (unified format) ---
    unified_path = output_dir / "picks.csv"
    
    # Load existing picks
    existing_ids = set()
    existing_rows = []
    fieldnames = ['pick_id', 'date', 'sport', 'player', 'stat', 'line', 
                  'direction', 'probability', 'tier', 'actual', 'hit', 'brier']
    
    if unified_path.exists():
        with open(unified_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_ids.add(row.get('pick_id', ''))
                existing_rows.append(row)
    
    # Add new picks
    added = 0
    for pick in picks:
        row = to_calibration_row(pick, date)
        if row['pick_id'] not in existing_ids:
            existing_rows.append({k: row.get(k, '') for k in fieldnames})
            added += 1
    
    # Write back
    with open(unified_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
    
    print(f"✅ Added {added} picks to {unified_path}")
    
    # --- Write to calibration_history.csv (legacy format) ---
    legacy_path = output_dir.parent / "calibration_history.csv"
    
    legacy_fieldnames = ['date', 'player', 'stat', 'line', 'direction', 
                         'predicted_prob', 'decision', 'actual_result', 
                         'role', 'gate_warnings', 'stat_type']
    
    existing_legacy = []
    if legacy_path.exists():
        with open(legacy_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_legacy = list(reader)
    
    # Add new picks (avoid duplicates by player+date+stat+line)
    existing_keys = {
        f"{r.get('date', '')}_{r.get('player', '')}_{r.get('stat', '')}_{r.get('line', '')}"
        for r in existing_legacy
    }
    
    added_legacy = 0
    for pick in picks:
        row = to_calibration_history_row(pick, date)
        key = f"{row['date']}_{row['player']}_{row['stat']}_{row['line']}"
        if key not in existing_keys:
            existing_legacy.append(row)
            added_legacy += 1
    
    with open(legacy_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=legacy_fieldnames)
        writer.writeheader()
        writer.writerows(existing_legacy)
    
    print(f"✅ Added {added_legacy} picks to {legacy_path}")
    
    return added, added_legacy


def generate_risk_analysis(picks: List[SleeperPick]) -> dict:
    """Generate risk analysis summary from picks"""
    summary = {
        "total": len(picks),
        "wins": sum(1 for p in picks if p.hit),
        "losses": sum(1 for p in picks if not p.hit),
        "by_stat": {},
        "by_direction": {"OVER": {"wins": 0, "losses": 0}, "UNDER": {"wins": 0, "losses": 0}},
        "by_risk_tag": {},
        "worst_misses": [],
    }
    
    summary["win_rate"] = summary["wins"] / summary["total"] if summary["total"] else 0
    
    for pick in picks:
        # By stat
        if pick.stat not in summary["by_stat"]:
            summary["by_stat"][pick.stat] = {"wins": 0, "losses": 0, "avg_margin": []}
        summary["by_stat"][pick.stat]["wins" if pick.hit else "losses"] += 1
        summary["by_stat"][pick.stat]["avg_margin"].append(pick.margin)
        
        # By direction
        summary["by_direction"][pick.direction]["wins" if pick.hit else "losses"] += 1
        
        # By risk tag
        for tag in (pick.risk_tags or []):
            if tag not in summary["by_risk_tag"]:
                summary["by_risk_tag"][tag] = {"wins": 0, "losses": 0}
            summary["by_risk_tag"][tag]["wins" if pick.hit else "losses"] += 1
        
        # Worst misses (UNDER blowups)
        if not pick.hit and pick.margin < -3:
            summary["worst_misses"].append({
                "player": pick.full_name,
                "stat": pick.stat,
                "line": pick.line,
                "actual": pick.actual,
                "margin": pick.margin,
                "risk_tags": pick.risk_tags,
            })
    
    # Compute average margins
    for stat, data in summary["by_stat"].items():
        data["avg_margin"] = sum(data["avg_margin"]) / len(data["avg_margin"]) if data["avg_margin"] else 0
    
    # Sort worst misses
    summary["worst_misses"].sort(key=lambda x: x["margin"])
    
    return summary


def print_risk_report(summary: dict):
    """Print risk analysis report"""
    print("\n" + "=" * 80)
    print("🎯 SLEEPER TICKET CALIBRATION ANALYSIS")
    print("=" * 80)
    
    print(f"\n📊 OVERALL: {summary['wins']}/{summary['total']} ({summary['win_rate']:.1%} hit rate)")
    
    print(f"\n📈 BY DIRECTION:")
    for direction, stats in summary["by_direction"].items():
        total = stats["wins"] + stats["losses"]
        rate = stats["wins"] / total if total else 0
        print(f"  {direction}: {stats['wins']}-{stats['losses']} ({rate:.1%})")
    
    print(f"\n📉 BY STAT TYPE:")
    for stat, data in sorted(summary["by_stat"].items(), key=lambda x: x[1]["avg_margin"]):
        total = data["wins"] + data["losses"]
        rate = data["wins"] / total if total else 0
        print(f"  {stat}: {data['wins']}-{data['losses']} ({rate:.1%}) | Avg Margin: {data['avg_margin']:+.1f}")
    
    if summary["by_risk_tag"]:
        print(f"\n🚨 BY RISK TAG:")
        for tag, stats in sorted(summary["by_risk_tag"].items(), 
                                  key=lambda x: x[1]["losses"] / (x[1]["wins"] + x[1]["losses"]) if (x[1]["wins"] + x[1]["losses"]) else 0,
                                  reverse=True):
            total = stats["wins"] + stats["losses"]
            rate = stats["wins"] / total if total else 0
            print(f"  {tag}: {stats['wins']}-{stats['losses']} ({rate:.1%})")
    
    if summary["worst_misses"]:
        print(f"\n💀 WORST MISSES (TAIL BLOWUPS):")
        for miss in summary["worst_misses"][:5]:
            tags = ", ".join(miss["risk_tags"]) if miss["risk_tags"] else "No tags"
            print(f"  {miss['player']} {miss['stat']} {miss['line']} | Actual: {miss['actual']} | Margin: {miss['margin']:+.1f}")
            print(f"    Risk Tags: {tags}")
    
    print("\n" + "=" * 80)


# --- MAIN ENTRY POINT ---

def main():
    """Main ingestion entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest Sleeper ticket data to calibration")
    parser.add_argument("--json", type=Path, help="JSON ticket file path")
    parser.add_argument("--csv", type=Path, help="CSV ticket file path")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                       help="Date of picks (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to files")
    parser.add_argument("--report-only", action="store_true", help="Only print risk report")
    
    args = parser.parse_args()
    
    picks = []
    
    if args.json:
        with open(args.json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        picks = parse_json_ticket(data)
        print(f"📥 Parsed {len(picks)} picks from JSON")
    
    if args.csv:
        picks.extend(parse_csv_ticket(args.csv))
        print(f"📥 Parsed {len(picks)} picks from CSV")
    
    if not picks:
        print("❌ No picks found. Use --json or --csv to specify input.")
        return
    
    # Apply risk tags
    for pick in picks:
        pick.risk_tags = apply_risk_tags(pick)
    
    # Generate and print risk report
    summary = generate_risk_analysis(picks)
    print_risk_report(summary)
    
    if args.report_only:
        return
    
    if not args.dry_run:
        added, added_legacy = ingest_to_calibration(picks, args.date)
        print(f"\n✅ INGESTION COMPLETE: {added} picks to unified, {added_legacy} to legacy")
    else:
        print("\n🔒 DRY RUN — No files written")


if __name__ == "__main__":
    main()
