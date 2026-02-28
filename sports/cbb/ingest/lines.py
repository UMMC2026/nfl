"""
CBB Lines Ingestion — Multi-Source Support (Underdog, OddAPI, MyBookie, PrizePicks)
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from .parse_cbb_paste import parse_text as parse_underdog_text

# TODO: Implement parse_oddsapi_text, parse_mybookie_text, parse_prizepicks_text
# For now, fallback to parse_underdog_text for all

def fetch_lines(target_date: str, source: Optional[str] = None, echo: bool = True) -> List[Dict]:
    """
    Load and parse the current slate from all supported sources.
    Echo the slate and abort if stale, test, or mismatched.
    """
    input_dir = Path("sports/cbb/inputs")
    latest_files = list(input_dir.glob("cbb_slate_*.json"))
    if not latest_files:
        raise RuntimeError("[ABORT] No slate files found in inputs directory.")

    # Prefer source if specified, else use most recent
    if source:
        files = [f for f in latest_files if source.lower() in f.name.lower()]
        if not files:
            raise RuntimeError(f"[ABORT] No slate file found for source: {source}")
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
    else:
        latest_file = max(latest_files, key=lambda f: f.stat().st_mtime)

    with open(latest_file) as f:
        data = json.load(f)

    # Diagnostics
    print("\n[SLATE INGESTION DIAGNOSTICS]")
    print(f"  Source file: {latest_file.name}")
    print(f"  Timestamp: {data.get('timestamp','?')}")
    print(f"  Props count: {data.get('count','?')}")
    if data.get('count', 0) == 0:
        raise RuntimeError("[ABORT] Slate file is empty.")

    # Check for test/stale slates
    if 'test' in latest_file.name.lower() or 'sample' in latest_file.name.lower():
        raise RuntimeError(f"[ABORT] Slate file appears to be a test or sample: {latest_file.name}")

    # Echo a sample of the slate
    props = data.get('props', [])
    print("  Sample props:")
    for p in props[:5]:
        print(f"    {p.get('player','?')} ({p.get('team','?')}) - {p.get('stat','?')} {p.get('direction','?')} {p.get('line','?')}")
    if len(props) > 5:
        print(f"    ... and {len(props) - 5} more")

    # TODO: Add further validation for date, matchup, and stat coverage
    # TODO: Route to correct parser based on file/source (Underdog, OddAPI, MyBookie, PrizePicks)

    return props
