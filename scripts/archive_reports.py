"""
Archive all reports from outputs/ to organized archives/ folder
Organizes by sport → year-month → dated files
"""
import os
import re
import shutil
from pathlib import Path
from datetime import datetime

# Define output and archive paths
OUTPUT_DIR = Path("outputs")
ARCHIVE_ROOT = Path("archives")

# Sport detection patterns
SPORT_PATTERNS = {
    "nba": [
        r"(_BALANCED_|_RISK_FIRST_|_AI_REPORT_|roster_averages)",
        r"^(ALL|MIL|GSW|LAL|BOS|PHI|IND|OKC|HOU|SAS|MIN|UTA|DAL)",
        r"(ASSIST|REBOUND|3PM|PRA|GAMES|HOTS)",
    ],
    "tennis": [
        r"tennis_report|tennis_edges|tennis_merged",
        r"total_games|aces|sets",
    ],
    "cbb": [
        r"cbb_report|cbb_edges",
    ],
    "nfl": [
        r"(NFL|nfl|HOU_PIT|BUF_DEN|cheatsheet|divisional)",
        r"(MC_|CHEATSHEET_)",
    ],
}

OTHER_PATTERNS = {
    "calibration": [r"calibration_report|backtest_results"],
    "monte_carlo": [r"monte_carlo_|bayesian_tuning"],
    "governance": [r"GOVERNANCE|ALLOWED_EDGES|BLOCKED_EDGES"],
}

def detect_sport(filename: str) -> str:
    filename_lower = filename.lower()
    for sport, patterns in SPORT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return sport
    for category, patterns in OTHER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower):
                return category
    return "other"

def extract_date(filename: str) -> str:
    match = re.search(r'20\d{6}', filename)
    if match:
        date_str = match.group()
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.strftime("%Y-%m")
        except:
            pass
    match = re.search(r'20\d{2}-\d{2}-\d{2}', filename)
    if match:
        date_str = match.group()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m")
        except:
            pass
    return datetime.now().strftime("%Y-%m")

def archive_reports(dry_run=True):
    if not OUTPUT_DIR.exists():
        print(f"❌ Output directory not found: {OUTPUT_DIR}")
        return
    
    if not dry_run:
        ARCHIVE_ROOT.mkdir(exist_ok=True)
    
    files_to_archive = []
    today_str = datetime.now().strftime("%Y%m%d")
    skipped_today = 0
    for item in OUTPUT_DIR.iterdir():
        if item.is_file() and item.suffix in ['.txt', '.json', '.md']:
            # NEVER archive today's files — they may still be needed by MC/pipeline
            if today_str in item.name:
                skipped_today += 1
                continue
            files_to_archive.append(item)
    
    if skipped_today:
        print(f"⏭️  Skipped {skipped_today} file(s) from today ({today_str})")
    print(f"📂 Found {len(files_to_archive)} files to archive\n")
    
    archive_plan = {}
    for file_path in files_to_archive:
        filename = file_path.name
        sport = detect_sport(filename)
        year_month = extract_date(filename)
        dest_dir = ARCHIVE_ROOT / sport / year_month
        dest_path = dest_dir / filename
        
        if sport not in archive_plan:
            archive_plan[sport] = {}
        if year_month not in archive_plan[sport]:
            archive_plan[sport][year_month] = []
        
        archive_plan[sport][year_month].append({
            "source": file_path,
            "dest": dest_path,
            "dest_dir": dest_dir
        })
    
    total_files = 0
    for sport, months in sorted(archive_plan.items()):
        sport_total = sum(len(files) for files in months.values())
        total_files += sport_total
        print(f"📊 {sport.upper()}: {sport_total} files")
        for year_month, files in sorted(months.items()):
            print(f"   └── {year_month}: {len(files)} files")
    
    print(f"\n📦 Total files to archive: {total_files}\n")
    
    if dry_run:
        print("🔍 DRY RUN - No files will be moved")
        print("   Run with --execute to actually archive files\n")
        print("📝 Sample operations (first 10):")
        count = 0
        for sport, months in sorted(archive_plan.items()):
            for year_month, files in sorted(months.items()):
                for file_info in files:
                    if count >= 10:
                        break
                    src = file_info["source"]
                    print(f"   {src.name}")
                    print(f"      → archives/{sport}/{year_month}/{src.name}")
                    count += 1
                if count >= 10:
                    break
            if count >= 10:
                break
    else:
        print("🚀 EXECUTING ARCHIVAL...")
        moved = 0
        for sport, months in archive_plan.items():
            for year_month, files in months.items():
                for file_info in files:
                    file_info["dest_dir"].mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file_info["source"]), str(file_info["dest"]))
                    moved += 1
                    if moved % 50 == 0:
                        print(f"   Moved {moved}/{total_files} files...")
        
        print(f"\n✅ Archived {moved} files successfully!")
        print(f"📁 Archive location: {ARCHIVE_ROOT.absolute()}\n")
        
        readme_path = ARCHIVE_ROOT / "README.md"
        readme_content = f'''# Analysis Reports Archive

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Structure
archives/
├── nba/          # NBA prop analysis
├── tennis/       # Tennis analysis
├── cbb/          # College Basketball
├── nfl/          # NFL analysis
├── calibration/  # Backtest results
├── monte_carlo/  # Simulations
├── governance/   # Edge governance
└── other/        # Miscellaneous

## File Types
- *_BALANCED_*.txt: Human-readable reports
- *_RISK_FIRST_*.json: Risk-optimized JSON
- *_AI_REPORT_*.txt: AI commentary
- calibration_report_*.txt: Calibration tracking
'''
        readme_path.write_text(readme_content, encoding="utf-8")
        print(f"📄 Created {readme_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Archive analysis reports")
    parser.add_argument("--execute", action="store_true", help="Actually move files")
    args = parser.parse_args()
    archive_reports(dry_run=not args.execute)
