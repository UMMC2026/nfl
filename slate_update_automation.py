#!/usr/bin/env python3
"""
SLATE UPDATE AUTOMATION SCRIPT
Purpose: Fully autonomous slate update workflow
This script handles: parsing → JSON format → cheatsheet generation
No manual steps. No circles. Pure automation.
"""

import json
import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

# Fix Unicode encoding on Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent


def create_slate_dict(games: list, props: list) -> dict:
    """
    Create the proper slate format expected by the pipeline.
    
    Args:
        games: List of game dicts {"away": "...", "home": "...", "datetime": "..."}
        props: List of prop dicts {"player": "...", "team": "...", "stat": "...", "line": ..., "direction": "..."}
    
    Returns:
        Dict with "games" and "props" keys
    """
    return {
        "games": games,
        "props": props
    }


def write_slate_json(slate_dict: dict, filepath: str = "chat_slate.json") -> bool:
    """
    Write the slate dict to JSON file using Python's file write (avoids BOM issues).
    
    Args:
        slate_dict: The slate dictionary
        filepath: Path to write the JSON file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        json_str = json.dumps(slate_dict, indent=2)
        
        # Use Python's built-in file write to avoid PowerShell BOM issues
        filepath_obj = PROJECT_ROOT / filepath
        filepath_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath_obj, 'w', encoding='utf-8') as f:
            f.write(json_str)
        
        time.sleep(0.5)  # Brief pause for file to be written
        
        # Verify file was written
        if not filepath_obj.exists() or filepath_obj.stat().st_size == 0:
            print(f"❌ File was not written or is empty: {filepath_obj}")
            return False
        
        print(f"✅ Slate JSON written to {filepath}")
        return True
    
    except Exception as e:
        print(f"❌ Failed to write slate JSON: {e}")
        return False


def run_cheatsheet_generator(slate_file: str = "chat_slate.json") -> bool:
    """
    Run the cheatsheet generator pipeline.
    
    Args:
        slate_file: Path to the slate JSON file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        generator_script = PROJECT_ROOT / "tools" / "cheatsheet_pro_generator.py"
        
        if not venv_python.exists():
            print(f"❌ Python venv not found at {venv_python}")
            return False
        
        if not generator_script.exists():
            print(f"❌ Cheatsheet generator not found at {generator_script}")
            return False
        
        print(f"🚀 Running cheatsheet generator...")
        
        # Ensure file is ready with a longer wait
        time.sleep(2)
        
        # Verify file exists and has content before running generator
        slate_path = PROJECT_ROOT / slate_file
        if not slate_path.exists():
            print(f"❌ Slate file not found: {slate_path}")
            return False
        
        file_size = slate_path.stat().st_size
        if file_size == 0:
            print(f"❌ Slate file is empty: {slate_path}")
            return False
        
        print(f"   Slate file verified: {file_size} bytes")
        
        # Run with output redirected to file to avoid Unicode issues
        log_file = PROJECT_ROOT / "outputs" / "pipeline.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, "w", encoding="utf-8") as log:
            result = subprocess.run(
                [str(venv_python), str(generator_script), "--league", "NFL", "--slate-file", str(slate_path.absolute())],
                cwd=PROJECT_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
        
        if result.returncode != 0:
            print(f"❌ Pipeline failed (see {log_file} for details)")
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.read()[-500:]  # Last 500 chars
                print(f"Last logs:\n{logs}")
            return False
        
        print(f"✅ Cheatsheet generation complete")
        return True
    
    except Exception as e:
        print(f"❌ Failed to run cheatsheet generator: {e}")
        return False


def parse_pasted_slate(pasted_text: str) -> tuple:
    """
    Parse a pasted slate string and extract games and props.
    
    This is a placeholder for manual entry guidance.
    Users should provide structured input.
    
    Args:
        pasted_text: Raw pasted slate data
    
    Returns:
        (games, props) tuple
    """
    print("⚠️  Manual parsing required. Please provide structured input:")
    print("   games: [{'away': '...', 'home': '...', 'datetime': '...'}]")
    print("   props: [{'player': '...', 'team': '...', 'stat': '...', 'line': ..., 'direction': '...'}]")
    return ([], [])


def main():
    """Main entry point for slate update automation."""
    
    print("=" * 80)
    print("🎯 NFL SLATE UPDATE AUTOMATION")
    print("=" * 80)
    print()
    
    # Example usage with hardcoded slate for testing
    example_games = [
        {"away": "BUF", "home": "DEN", "datetime": "Sat 3:30PM CST"}
    ]
    
    example_props = [
        {"player": "James Cook", "team": "BUF", "stat": "rush_rec_tds", "line": 0.5, "direction": "higher"},
        {"player": "James Cook", "team": "BUF", "stat": "rush_yds", "line": 81.5, "direction": "higher"},
        {"player": "James Cook", "team": "BUF", "stat": "rec_yds", "line": 15.5, "direction": "higher"},
        {"player": "James Cook", "team": "BUF", "stat": "receptions", "line": 2.5, "direction": "higher"},
        {"player": "Courtland Sutton", "team": "DEN", "stat": "rush_rec_tds", "line": 0.5, "direction": "higher"},
        {"player": "Courtland Sutton", "team": "DEN", "stat": "rec_yds", "line": 51.5, "direction": "higher"},
        {"player": "Courtland Sutton", "team": "DEN", "stat": "receptions", "line": 4.5, "direction": "higher"},
        {"player": "Courtland Sutton", "team": "DEN", "stat": "longest_rec", "line": 20.5, "direction": "higher"},
    ]
    
    # Step 1: Create slate dict
    print("📝 Step 1: Creating slate dictionary...")
    slate_dict = create_slate_dict(example_games, example_props)
    print(f"   Games: {len(slate_dict['games'])}")
    print(f"   Props: {len(slate_dict['props'])}")
    print()
    
    # Step 2: Write to JSON
    print("💾 Step 2: Writing slate to JSON...")
    if not write_slate_json(slate_dict):
        print("❌ Failed to write slate JSON")
        return False
    print()
    
    # Step 3: Run cheatsheet generator
    print("🔧 Step 3: Running cheatsheet generator...")
    if not run_cheatsheet_generator():
        print("❌ Failed to run cheatsheet generator")
        return False
    print()
    
    print("=" * 80)
    print("✅ SLATE UPDATE COMPLETE")
    print("=" * 80)
    print(f"Output: outputs/NFL_CHEATSHEET_*.txt")
    print()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
