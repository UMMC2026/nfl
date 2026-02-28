"""
Estimate Missing Probabilities from Tier Labels
================================================

Since we have 90 resolved picks without probabilities, but most have
tier labels (SLAM, STRONG, LEAN), we can estimate probabilities:

- SLAM: 75% (0.75)
- STRONG: 65% (0.65)  
- LEAN: 55% (0.55)
- NO_PLAY/SKIP: 50% (0.50)

This is not ideal but allows us to compute calibration metrics.
"""

import csv
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent

# Tier to probability mapping (conservative estimates)
TIER_PROB_MAP = {
    'SLAM': 0.75,
    'STRONG': 0.65,
    'LEAN': 0.55,
    'NO_PLAY': 0.50,
    'SKIP': 0.50,
    'AVOID': 0.45,
    '': 0.55,  # Default to LEAN if missing
}


def estimate_probabilities():
    """Estimate missing probabilities based on tier labels."""
    history_path = PROJECT_ROOT / "calibration_history.csv"
    
    if not history_path.exists():
        print("No calibration_history.csv found")
        return
    
    # Read all rows
    rows = []
    fieldnames = None
    
    with open(history_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(dict(row))
    
    # Ensure we have the probability column
    prob_col = None
    for col in ['probability', 'predicted_prob', 'prob']:
        if col in fieldnames:
            prob_col = col
            break
    
    if not prob_col:
        prob_col = 'probability'
        fieldnames = list(fieldnames) + ['probability']
    
    print(f"{'='*60}")
    print("  ESTIMATING MISSING PROBABILITIES FROM TIER LABELS")
    print(f"{'='*60}\n")
    
    # Count current state
    resolved_no_prob = 0
    already_has_prob = 0
    estimated = 0
    
    outcome_col = None
    for col in ['outcome', 'actual_result', 'result']:
        if col in fieldnames:
            outcome_col = col
            break
    
    tier_col = None
    for col in ['tier', 'decision']:
        if col in fieldnames:
            tier_col = col
            break
    
    print(f"Using columns: prob={prob_col}, outcome={outcome_col}, tier={tier_col}\n")
    
    for row in rows:
        outcome = str(row.get(outcome_col, '')).strip().upper()
        is_resolved = outcome in ['HIT', 'MISS', '1', '0']
        
        prob_val = str(row.get(prob_col, '')).strip()
        has_prob = bool(prob_val) and prob_val not in ['', 'None', 'nan']
        
        if is_resolved:
            if has_prob:
                already_has_prob += 1
            else:
                resolved_no_prob += 1
                
                # Estimate from tier
                tier = str(row.get(tier_col, '')).strip().upper()
                estimated_prob = TIER_PROB_MAP.get(tier, 0.55)
                row[prob_col] = str(estimated_prob)
                estimated += 1
    
    print(f"Resolved picks with probability:    {already_has_prob}")
    print(f"Resolved picks missing probability: {resolved_no_prob}")
    print(f"Estimated from tier:                {estimated}")
    
    if estimated == 0:
        print("\nNo picks needed estimation.")
        return
    
    # Backup original
    backup_path = PROJECT_ROOT / f"calibration_history.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(history_path, 'r', encoding='utf-8') as f_in:
        with open(backup_path, 'w', encoding='utf-8') as f_out:
            f_out.write(f_in.read())
    print(f"\nBacked up to: {backup_path}")
    
    # Write updated
    with open(history_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Updated calibration_history.csv with {estimated} estimated probabilities")
    
    # Show new scorable count
    scorable = sum(
        1 for r in rows
        if str(r.get(outcome_col, '')).strip().upper() in ['HIT', 'MISS', '1', '0']
        and str(r.get(prob_col, '')).strip() not in ['', 'None', 'nan']
    )
    print(f"\nNew scorable picks count: {scorable}")


if __name__ == '__main__':
    estimate_probabilities()
