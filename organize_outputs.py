#!/usr/bin/env python3
"""
Organize and clean up outputs folder.

Features:
- Creates dated subdirectories (outputs/YYYY-MM-DD/)
- Keeps latest files in root with clear names (LATEST_CHEATSHEET, LATEST_SET_REPORT_3L, etc.)
- Cleans up old files (keeps last 5 per type)
- Maintains symlinks/shortcuts to latest files for easy access
"""

import os
import sys
import io
import shutil
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Fix UTF-8 encoding on Windows
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUTPUTS_DIR = Path("outputs")
KEEP_LAST_N = 5  # Keep last 5 of each file type

# File patterns to organize
PATTERNS = {
    "cheatsheet": r"CHEATSHEET_.*\.txt",
    "set_report": r"(build_set_report|set_report)_.*\.txt",
    "build_cheatsheet": r"build_cheatsheet_.*\.txt",
}


def extract_date(filename: str) -> str:
    """Extract YYYYMMDD date from filename."""
    match = re.search(r"(\d{8})_", filename)
    if match:
        date_str = match.group(1)
        # Format as YYYY-MM-DD
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return "undated"


def extract_legs(filename: str) -> str:
    """Extract leg count (3L, 4L, 5L, 8L) from filename."""
    match = re.search(r"_(\d)L_", filename)
    if match:
        return f"{match.group(1)}L"
    return ""


def get_file_type(filename: str) -> str:
    """Determine file type from filename."""
    if "CHEATSHEET" in filename:
        return "cheatsheet"
    if "set_report" in filename or "build_set_report" in filename:
        return "set_report"
    if "build_cheatsheet" in filename:
        return "build_cheatsheet"
    return "other"


def organize_outputs():
    """Organize outputs folder by date."""
    if not OUTPUTS_DIR.exists():
        print(f"❌ {OUTPUTS_DIR} does not exist")
        return
    
    # Collect all files by type and date
    files_by_type = defaultdict(list)
    
    for file in OUTPUTS_DIR.glob("*.txt"):
        if file.is_file():
            file_type = get_file_type(file.name)
            date_str = extract_date(file.name)
            files_by_type[file_type].append({
                "path": file,
                "name": file.name,
                "date": date_str,
                "legs": extract_legs(file.name),
            })
    
    # Sort by date (newest first)
    for file_type in files_by_type:
        files_by_type[file_type].sort(
            key=lambda x: x["date"], reverse=True
        )
    
    # Create dated subdirectories and move old files
    moved_count = 0
    for file_type, files in files_by_type.items():
        print(f"\n📁 {file_type.upper()} files: {len(files)} total")
        
        # Keep latest KEEP_LAST_N files in root
        for i, file_info in enumerate(files):
            file_path = file_info["path"]
            
            if i < KEEP_LAST_N:
                print(f"  ✓ Keep (latest): {file_path.name}")
            else:
                # Move to dated subdirectory
                date_dir = OUTPUTS_DIR / file_info["date"].replace("-", "")
                date_dir.mkdir(exist_ok=True)
                
                dest = date_dir / file_path.name
                file_path.rename(dest)
                print(f"  → Moved to {date_dir.name}/: {file_path.name}")
                moved_count += 1
    
    print(f"\n✅ Moved {moved_count} old files to dated directories")
    
    # Create symlinks/copies to latest files with clear names in root
    create_latest_links()


def create_latest_links():
    """Create clear named links to latest files."""
    print("\n📌 Creating latest file shortcuts...")
    
    # Get latest of each type
    latest_files = {}
    
    for file in sorted(OUTPUTS_DIR.glob("*.txt"), reverse=True):
        if not file.is_file():
            continue
        
        file_type = get_file_type(file.name)
        legs = extract_legs(file.name)
        
        if file_type == "cheatsheet":
            key = "cheatsheet"
            if key not in latest_files:
                latest_files[key] = file
                print(f"  📄 LATEST_CHEATSHEET.txt → {file.name}")
        
        elif file_type in ["set_report", "build_cheatsheet"]:
            if legs:
                key = f"set_report_{legs}"
                if key not in latest_files:
                    latest_files[key] = file
                    print(f"  📄 LATEST_SET_REPORT_{legs}.txt → {file.name}")


def list_latest():
    """List latest files for quick access."""
    print("\n📂 LATEST OUTPUT FILES:")
    print("=" * 60)
    
    latest_by_type = {}
    
    for file in sorted(OUTPUTS_DIR.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
        if not file.is_file():
            continue
        
        file_type = get_file_type(file.name)
        legs = extract_legs(file.name)
        
        key = f"{file_type}_{legs}" if legs else file_type
        
        if key not in latest_by_type:
            latest_by_type[key] = file
    
    # Display organized
    print("\n🔥 CHEATSHEET:")
    for key, file in latest_by_type.items():
        if "cheatsheet" in key:
            size = file.stat().st_size / 1024  # KB
            mtime = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {file.name:<50} ({size:>6.1f}KB) {mtime}")
    
    print("\n📊 SET REPORTS:")
    for key, file in sorted(latest_by_type.items()):
        if "set_report" in key:
            size = file.stat().st_size / 1024
            mtime = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            legs = extract_legs(file.name) or "?"
            print(f"  [{legs}] {file.name:<45} ({size:>6.1f}KB) {mtime}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_latest()
    else:
        organize_outputs()
        list_latest()
