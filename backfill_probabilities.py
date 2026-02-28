"""
PROBABILITY BACKFILL FOR CALIBRATION
====================================
Recovers predicted probabilities from historical *RISK_FIRST*.json outputs
and updates calibration_history.csv for proper Brier scoring.

This fixes the CRITICAL GAP: having outcomes but no probabilities.
"""

import csv
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Optional, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent


def normalize_name(name: str) -> str:
    """Normalize player name for matching."""
    s = (name or "").strip().lower()
    # Remove punctuation
    s = re.sub(r"[^a-z0-9\s]", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_stat(stat: str) -> str:
    """Normalize stat name for matching."""
    s = (stat or "").strip().lower()
    s = s.replace("+", "+").replace("_", " ")
    return s


def normalize_direction(direction: str) -> str:
    """Normalize direction for matching."""
    s = (direction or "").strip().lower()
    if s in ("over", "higher", "hi", "h"):
        return "higher"
    if s in ("under", "lower", "lo", "l"):
        return "lower"
    return s


def build_pick_key(player: str, stat: str, line: float, direction: str) -> str:
    """Build consistent key for matching picks."""
    return f"{normalize_name(player)}|{normalize_stat(stat)}|{line:.1f}|{normalize_direction(direction)}"


def load_outputs_index() -> Dict[str, Dict]:
    """
    Load all RISK_FIRST JSON outputs and index by pick key.
    
    Returns: {pick_key: {probability, tier, date, ...}}
    """
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        print(f"  ⚠️ No outputs directory found at {outputs_dir}")
        return {}
    
    index = {}
    json_files = list(outputs_dir.glob("*RISK_FIRST*.json"))
    print(f"  Found {len(json_files)} RISK_FIRST JSON files")
    
    for json_path in json_files:
        try:
            data = json.loads(json_path.read_text(encoding='utf-8'))
            
            # Extract date from filename (format: *_YYYYMMDD_*.json)
            date_match = re.search(r'(\d{8})', json_path.name)
            file_date = date_match.group(1) if date_match else ""
            
            results = data.get("results") if isinstance(data, dict) else None
            if not isinstance(results, list):
                continue
            
            for pick in results:
                if not isinstance(pick, dict):
                    continue
                
                player = pick.get("player", "")
                stat = pick.get("stat", "")
                line = pick.get("line")
                direction = pick.get("direction", "")
                
                if not player or line is None:
                    continue
                
                try:
                    line_f = float(line)
                except:
                    continue
                
                # Get probability - try multiple fields
                prob = pick.get("effective_confidence")
                if prob is None:
                    prob = pick.get("confidence")
                if prob is None:
                    prob = pick.get("probability")
                if prob is None:
                    prob = pick.get("final_probability")
                
                if prob is None:
                    continue
                
                # Normalize probability to 0-1
                if prob > 1:
                    prob = prob / 100.0
                
                key = build_pick_key(player, stat, line_f, direction)
                
                # Store with file date for preference
                if key not in index or file_date > index[key].get("date", ""):
                    index[key] = {
                        "probability": prob,
                        "tier": pick.get("tier", pick.get("decision", "")),
                        "date": file_date,
                        "source_file": json_path.name,
                        "player": player,
                        "stat": stat,
                        "line": line_f,
                        "direction": direction,
                    }
        
        except Exception as e:
            print(f"  ⚠️ Error reading {json_path.name}: {e}")
            continue
    
    print(f"  Indexed {len(index)} unique picks with probabilities")
    return index


def backfill_calibration_history():
    """
    Main function: backfill probabilities into calibration_history.csv.
    """
    print("=" * 80)
    print("  PROBABILITY BACKFILL FOR CALIBRATION")
    print("=" * 80)
    print()
    
    history_path = PROJECT_ROOT / "calibration_history.csv"
    if not history_path.exists():
        print(f"❌ No calibration_history.csv found at {history_path}")
        return
    
    # Load outputs index
    print("📂 Loading RISK_FIRST JSON outputs...")
    outputs_index = load_outputs_index()
    
    if not outputs_index:
        print("❌ No probability data found in outputs")
        return
    
    # Read current history
    print()
    print("📂 Reading calibration_history.csv...")
    rows = []
    fieldnames = None
    
    with open(history_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    print(f"  Found {len(rows)} rows")
    
    # Track stats
    total = 0
    already_had_prob = 0
    backfilled = 0
    not_found = 0
    resolved_no_prob = 0
    
    # Process rows
    updated_rows = []
    for row in rows:
        total += 1
        
        prob = row.get('probability', '')
        outcome = (row.get('outcome') or '').upper()
        
        # Check if already has probability
        if prob and prob.strip():
            already_had_prob += 1
            updated_rows.append(row)
            continue
        
        # Try to find probability in outputs
        player = row.get('player', '')
        stat = row.get('stat', '')
        line = row.get('line', 0)
        direction = row.get('direction', '')
        
        try:
            line_f = float(line) if line else 0
        except:
            line_f = 0
        
        key = build_pick_key(player, stat, line_f, direction)
        match = outputs_index.get(key)
        
        if match:
            # Found match - backfill probability
            row['probability'] = str(round(match['probability'] * 100, 1))  # Store as percent
            backfilled += 1
            updated_rows.append(row)
        else:
            # No match found
            not_found += 1
            if outcome in ('HIT', 'MISS'):
                resolved_no_prob += 1
            updated_rows.append(row)
    
    # Report
    print()
    print("📊 BACKFILL RESULTS:")
    print(f"  Total rows:              {total}")
    print(f"  Already had probability: {already_had_prob}")
    print(f"  Backfilled:              {backfilled}")
    print(f"  Not found in outputs:    {not_found}")
    print(f"  Resolved but no prob:    {resolved_no_prob} ⚠️")
    
    # Calculate scorable
    scorable_after = 0
    for row in updated_rows:
        prob = row.get('probability', '')
        outcome = (row.get('outcome') or '').upper()
        if prob and prob.strip() and outcome in ('HIT', 'MISS'):
            scorable_after += 1
    
    print()
    print(f"📊 SCORABLE PICKS (probability + outcome):")
    print(f"  Before backfill: 0")
    print(f"  After backfill:  {scorable_after}")
    
    # Write updated file
    if backfilled > 0:
        backup_path = history_path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        
        print()
        print(f"💾 Creating backup: {backup_path.name}")
        history_path.rename(backup_path)
        
        print(f"💾 Writing updated calibration_history.csv...")
        with open(history_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)
        
        print(f"✅ Done! Backfilled {backfilled} probabilities")
    else:
        print()
        print("⚠️ No probabilities backfilled - outputs may not match history picks")
    
    # Recommendations
    if resolved_no_prob > 0 and scorable_after < 50:
        print()
        print("=" * 80)
        print("  ⚠️ RECOMMENDATIONS")
        print("=" * 80)
        print(f"  You have {resolved_no_prob} resolved picks without probabilities.")
        print("  These cannot be recovered automatically.")
        print()
        print("  OPTIONS:")
        print("  1. Re-run analysis on those game dates to regenerate outputs")
        print("  2. Manually assign tier-based probabilities:")
        print("     - SLAM: 75%")
        print("     - STRONG: 65%")
        print("     - LEAN: 55%")
        print("  3. Focus on collecting NEW picks with probabilities going forward")


def estimate_from_tier():
    """
    Fallback: estimate probabilities from tier labels for resolved picks.
    
    Use when outputs are unavailable but tiers are recorded.
    """
    print("=" * 80)
    print("  TIER-BASED PROBABILITY ESTIMATION")
    print("=" * 80)
    print()
    
    history_path = PROJECT_ROOT / "calibration_history.csv"
    if not history_path.exists():
        print("❌ No calibration_history.csv found")
        return
    
    TIER_PROBS = {
        "SLAM": 0.75,
        "STRONG": 0.65,
        "LEAN": 0.55,
        "NO_PLAY": 0.45,
        "NO PLAY": 0.45,
    }
    
    rows = []
    fieldnames = None
    
    with open(history_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    estimated = 0
    for row in rows:
        prob = row.get('probability', '')
        tier = (row.get('tier') or '').upper()
        outcome = (row.get('outcome') or '').upper()
        
        # Skip if already has probability
        if prob and prob.strip():
            continue
        
        # Only estimate for resolved picks with known tier
        if outcome not in ('HIT', 'MISS'):
            continue
        
        if tier in TIER_PROBS:
            row['probability'] = str(round(TIER_PROBS[tier] * 100, 1))
            estimated += 1
    
    if estimated > 0:
        print(f"  Estimated {estimated} probabilities from tier labels")
        
        backup_path = history_path.with_suffix(f'.backup_tier_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        history_path.rename(backup_path)
        
        with open(history_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"  ✅ Written to calibration_history.csv")
    else:
        print("  ⚠️ No picks eligible for tier-based estimation")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--tier":
        estimate_from_tier()
    else:
        backfill_calibration_history()
