"""
Backfill calibration_history.csv from Jan 02 CALIBRATED slate.

Reads:
  - picks_hydrated.json (prediction data: mu, sigma, prob_raw, sample_size)
  - governance_context.py (role, blowout_risk, survival, penalties)
  - generate_cheatsheet.py logic (how calibration was applied)

Outputs:
  - calibration_history.csv (immutable baseline for learning)

Outcome fields left NULL until games finish.
"""

import json
import csv
from datetime import datetime
from pathlib import Path
import uuid
import sys

# Add ufa to path for imports
sys.path.insert(0, str(Path.cwd()))

# ============================================================================
# LOAD PREDICTION DATA
# ============================================================================

with open('picks_hydrated.json', 'r') as f:
    hydrated_picks = json.load(f)

print(f"Loaded {len(hydrated_picks)} picks from picks_hydrated.json")

# ============================================================================
# IMPORT GOVERNANCE CONTEXT & PROBABILITY CALCULATOR
# ============================================================================

from governance_context import (
    PLAYER_ROLES,
    GAME_SPREADS,
    get_blowout_risk,
    get_governance_context,
    apply_blowout_penalty,
)

from ufa.analysis.prob import prob_hit

# ============================================================================
# CALIBRATION LOGIC (Mirrors generate_cheatsheet.py)
# ============================================================================

def apply_governance_calibration(prob, tier):
    """
    Shrinkage logic from generate_cheatsheet.py.
    Regression-to-mean adjustment.
    """
    if tier == 'slam':
        return 0.62  # 90%+ → 62%
    elif tier == 'strong':
        return min(0.68, prob - 0.12)
    else:  # lean
        return min(0.58, prob - 0.12)

def determine_tier_statistical(prob_raw):
    """Tier based on raw probability."""
    if prob_raw >= 0.90:
        return 'SLAM'
    elif prob_raw >= 0.80:
        return 'STRONG'
    elif prob_raw >= 0.70:
        return 'LEAN'
    else:
        return 'BELOW'

def determine_tier_calibrated(prob_calibrated):
    """Tier based on calibrated probability."""
    if prob_calibrated >= 0.75:
        return 'SLAM'
    elif prob_calibrated >= 0.60:
        return 'STRONG'
    elif prob_calibrated >= 0.52:
        return 'LEAN'
    else:
        return 'BELOW'

# ============================================================================
# GENERATE CALIBRATION HISTORY ROWS
# ============================================================================

rows = []
now = datetime.utcnow().isoformat() + 'Z'

for pick in hydrated_picks:
    # A. PICK IDENTIFICATION
    player_name = pick['player']
    team = pick['team']
    stat_category = pick['stat']
    line = pick['line']
    direction = pick['direction'].upper()
    
    # Infer opponent team from GAME_SPREADS
    opponent_team = None
    for (away, home), spread in GAME_SPREADS.items():
        if away == team:
            opponent_team = home
            break
        elif home == team:
            opponent_team = away
            break
    if opponent_team is None:
        opponent_team = '???'  # Unknown
    
    # Create unique pick_id
    stat_short = stat_category.replace('+', '').replace(' ', '')[:8]
    pick_id = f"pick_2026010201_{player_name.lower().replace(' ', '_')}_{stat_short}"
    
    # B. PREDICTION DATA
    direction_map = {'higher': 'higher', 'lower': 'lower', 'OVER': 'higher', 'UNDER': 'lower'}
    direction_normalized = direction_map.get(pick['direction'], pick['direction']).lower()
    
    mu = pick.get('mu', 0.0)
    sigma = pick.get('sigma', 1.0)
    recent_values = pick.get('recent_values', [])
    actual_sample_size = len(recent_values) if recent_values else 0
    
    # Calculate prob_hit using CDF
    prob_raw = prob_hit(
        line=line,
        direction=direction_normalized,
        mu=mu,
        sigma=sigma
    )
    
    sample_size = actual_sample_size
    
    tier_statistical = determine_tier_statistical(prob_raw)
    
    # C. GOVERNANCE FLAGS
    gov_ctx = get_governance_context(player_name, team)
    blowout_risk = get_blowout_risk(team, opponent_team)
    player_role = gov_ctx.get('role', 'unknown')
    minutes_survival_base = gov_ctx.get('minutes_survival', 0.80)
    garbage_time_eligible = gov_ctx.get('garbage_time_eligible', False)
    
    # Rest/Sample flags (defaults)
    rest_days = 2
    rest_flag = 'OK'
    sample_size_flag = 'OK' if actual_sample_size >= 10 else ('CAUTION' if actual_sample_size >= 5 else 'RISK')
    usage_trend = 'UNKNOWN'
    
    # D. GOVERNANCE ADJUSTMENTS
    penalty_blowout_pct = 0.0
    penalty_rest_pct = 0.0
    penalty_shrinkage_pct = 0.0
    penalty_other_pct = 0.0
    
    # Apply shrinkage based on tier
    if tier_statistical == 'SLAM':
        penalty_shrinkage_pct = -(prob_raw - 0.62)
    elif tier_statistical == 'STRONG':
        shrink_to = min(0.68, prob_raw - 0.12)
        penalty_shrinkage_pct = -(prob_raw - shrink_to)
    elif tier_statistical == 'LEAN':
        shrink_to = min(0.58, prob_raw - 0.12)
        penalty_shrinkage_pct = -(prob_raw - shrink_to)
    
    # Apply blowout penalty (soft, before final display)
    blowout_penalty_amount = 0.0
    if blowout_risk == 'Moderate':
        if player_role in ['bench_scorer', 'bench_big']:
            blowout_penalty_amount = -0.04
        else:
            blowout_penalty_amount = -0.01
    elif blowout_risk == 'High':
        if player_role in ['bench_scorer', 'bench_big']:
            blowout_penalty_amount = -0.08
        elif player_role in ['high_usage_starter', 'role_starter']:
            blowout_penalty_amount = -0.05
        else:  # Stars
            blowout_penalty_amount = -0.03
    
    penalty_blowout_pct = blowout_penalty_amount
    total_penalty_pct = penalty_blowout_pct + penalty_rest_pct + penalty_shrinkage_pct + penalty_other_pct
    
    # E. CALIBRATED DECISION
    prob_calibrated = max(0.0, prob_raw + total_penalty_pct)
    tier_calibrated = determine_tier_calibrated(prob_calibrated)
    
    # Recommendation logic
    if tier_calibrated == 'SLAM':
        recommended_action = 'PLAY'
    elif tier_calibrated == 'STRONG':
        recommended_action = 'PLAY'
    elif tier_calibrated == 'LEAN':
        recommended_action = 'CONDITIONAL'
    else:
        recommended_action = 'PASS'
    
    # Confidence note
    confidence_note = f"{player_role}, {blowout_risk} blowout risk"
    if sample_size_flag == 'RISK':
        confidence_note += ", small sample"
    if garbage_time_eligible:
        confidence_note += ", garbage-time eligible"
    
    # F. EXECUTION & RESULT (NULL - games haven't finished)
    actually_placed = None
    entry_format = None
    actual_value = None
    outcome = None
    minutes_played = None
    terminal_state = None
    
    # G. FAILURE ATTRIBUTION (NULL - no outcome yet)
    failure_primary_cause = None
    failure_detail = None
    governance_flag_present = None
    governance_flag_name = None
    penalty_was_sufficient = None
    suggested_penalty_increase_pct = None
    
    # H. LEARNING & UPDATES (NULL - no outcome yet)
    learning_signal = False
    learning_type = None
    suggested_rule_change = None
    confidence_in_suggestion = None
    learning_gate_passed = None
    correction_risk = None
    
    # I. METADATA
    created_at = now
    result_posted_at = None
    audited = False
    notes = None
    
    # Build row dict
    row = {
        'pick_id': pick_id,
        'slate_date': '2026-01-02',
        'slate_id': 'JAN02_2026',
        'player_name': player_name,
        'team': team,
        'stat_category': stat_category,
        'line': round(line, 1),
        'direction': direction,
        'opponent_team': opponent_team,
        'prob_raw': round(prob_raw, 3),
        'mu': round(mu, 1),
        'sigma': round(sigma, 2),
        'sample_size': actual_sample_size,
        'tier_statistical': tier_statistical,
        'blowout_risk': blowout_risk,
        'player_role': player_role,
        'minutes_survival_base': round(minutes_survival_base, 2),
        'garbage_time_eligible': str(garbage_time_eligible),
        'rest_days': rest_days,
        'rest_flag': rest_flag,
        'sample_size_flag': sample_size_flag,
        'usage_trend': usage_trend,
        'penalty_blowout_pct': round(penalty_blowout_pct, 3),
        'penalty_rest_pct': round(penalty_rest_pct, 3),
        'penalty_shrinkage_pct': round(penalty_shrinkage_pct, 3),
        'penalty_other_pct': round(penalty_other_pct, 3),
        'total_penalty_pct': round(total_penalty_pct, 3),
        'prob_calibrated': round(prob_calibrated, 3),
        'tier_calibrated': tier_calibrated,
        'recommended_action': recommended_action,
        'confidence_note': confidence_note,
        'actually_placed': '' if actually_placed is None else str(actually_placed),
        'entry_format': entry_format or '',
        'actual_value': '' if actual_value is None else round(actual_value, 1),
        'outcome': outcome or '',
        'minutes_played': '' if minutes_played is None else minutes_played,
        'terminal_state': terminal_state or '',
        'failure_primary_cause': failure_primary_cause or '',
        'failure_detail': failure_detail or '',
        'governance_flag_present': '' if governance_flag_present is None else str(governance_flag_present),
        'governance_flag_name': governance_flag_name or '',
        'penalty_was_sufficient': '' if penalty_was_sufficient is None else str(penalty_was_sufficient),
        'suggested_penalty_increase_pct': '' if suggested_penalty_increase_pct is None else round(suggested_penalty_increase_pct, 3),
        'learning_signal': str(learning_signal),
        'learning_type': learning_type or '',
        'suggested_rule_change': suggested_rule_change or '',
        'confidence_in_suggestion': confidence_in_suggestion or '',
        'learning_gate_passed': '' if learning_gate_passed is None else str(learning_gate_passed),
        'correction_risk': '' if correction_risk is None else str(correction_risk),
        'created_at': created_at,
        'result_posted_at': result_posted_at or '',
        'audited': str(audited),
        'notes': notes or '',
    }
    
    rows.append(row)

print(f"Generated {len(rows)} calibration history rows")

# ============================================================================
# WRITE CSV
# ============================================================================

fieldnames = [
    'pick_id', 'slate_date', 'slate_id', 'player_name', 'team', 'stat_category', 'line', 'direction', 'opponent_team',
    'prob_raw', 'mu', 'sigma', 'sample_size', 'tier_statistical',
    'blowout_risk', 'player_role', 'minutes_survival_base', 'garbage_time_eligible', 'rest_days', 'rest_flag', 'sample_size_flag', 'usage_trend',
    'penalty_blowout_pct', 'penalty_rest_pct', 'penalty_shrinkage_pct', 'penalty_other_pct', 'total_penalty_pct',
    'prob_calibrated', 'tier_calibrated', 'recommended_action', 'confidence_note',
    'actually_placed', 'entry_format', 'actual_value', 'outcome', 'minutes_played', 'terminal_state',
    'failure_primary_cause', 'failure_detail', 'governance_flag_present', 'governance_flag_name', 'penalty_was_sufficient', 'suggested_penalty_increase_pct',
    'learning_signal', 'learning_type', 'suggested_rule_change', 'confidence_in_suggestion', 'learning_gate_passed', 'correction_risk',
    'created_at', 'result_posted_at', 'audited', 'notes',
]

output_path = Path('calibration_history.csv')

with open(output_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Saved: {output_path}")
print(f"\nBreakdown by tier:")
for tier in ['SLAM', 'STRONG', 'LEAN', 'BELOW']:
    count = sum(1 for r in rows if r['tier_calibrated'] == tier)
    if count > 0:
        print(f"  {tier}: {count} picks")

print(f"\nBreakdown by blowout risk:")
for risk in ['Low', 'Moderate', 'High']:
    count = sum(1 for r in rows if r['blowout_risk'] == risk)
    if count > 0:
        print(f"  {risk}: {count} picks")

print(f"\nSample row (first SLAM pick):")
slam_rows = [r for r in rows if r['tier_calibrated'] == 'SLAM']
if slam_rows:
    slam = slam_rows[0]
    print(f"  {slam['player_name']} ({slam['team']}) {slam['direction']} {slam['line']} {slam['stat_category']}")
    print(f"    Raw: {slam['prob_raw']} ({slam['tier_statistical']}) → Calibrated: {slam['prob_calibrated']} ({slam['tier_calibrated']})")
    print(f"    Penalties: Blowout {slam['penalty_blowout_pct']}, Shrinkage {slam['penalty_shrinkage_pct']}")
