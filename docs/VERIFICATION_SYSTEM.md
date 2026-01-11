# Pre-Output Verification System

## Overview
The verification gate ensures all betting recommendations are validated before publication. It catches team mismatches, stale data, and statistical anomalies automatically.

## Architecture

### 1. Verification Gate (`verification_gate.py`)
**Location**: Root directory  
**Purpose**: Comprehensive pre-output validation

**Checks Performed**:
- ✅ **NBA Stats API Cross-Validation** - Compares predictions against official season averages
- ✅ **Team Assignment Accuracy** - Cross-checks against known trades/transfers
- ✅ **Data Freshness** - Validates hydration timestamp < 24 hours
- ✅ **Statistical Consistency** - Detects impossible values and extreme volatility
- ✅ **Roster Status** - Verifies players are ACTIVE (not injured/unavailable)

**Auto-Corrections**:
- Team updates for known trades (e.g., Jordan Clarkson UTA→NYK)
- Invalid picks removed automatically
- Warnings issued for questionable data

**Output**:
- Console summary with corrections, warnings, and errors
- JSON report saved to `outputs/verification_report_TIMESTAMP.json`

### 2. Roster Refresh (`scripts/refresh_rosters.py`)
**Purpose**: Maintain current roster data from NBA API

**What It Does**:
- Fetches all 30 NBA team rosters from `nba_api`
- Updates `data_center/rosters/NBA_active_roster_YYYY-MM-DD.csv`
- Maintains `NBA_active_roster_current.csv` for verification gate

**When It Runs**:
- Automatically in Step 0 of `daily_workflow.py`
- Can run standalone: `python scripts/refresh_rosters.py`

**Rate Limiting**: 0.6 second delay between team fetches

### 3. Updated Workflow (`scripts/daily_workflow.py`)
**New Steps**:
```
Step 0: Refresh rosters (current NBA data)
Step 1: Cached hydration
Step 2: Generate cheatsheet (with verification gate)
Step 3: Report analyzer
Step 4: Smart validation
Step 5: Verification gate final check
```

### 4. Cheatsheet Integration (`generate_cheatsheet.py`)
**New Behavior**:
- Verification gate runs BEFORE any processing
- If critical errors found → script exits (no output generated)
- Verification report always saved for audit trail

## Known Team Changes
Configured in `verification_gate.py`:
```python
KNOWN_TEAM_CHANGES = {
    "Jordan Clarkson": ("UTA", "NYK", "2025-12-20"),
    # Add other trades here
}
```

## Usage

### Running Full Workflow
```bash
python scripts/daily_workflow.py
```

### Manual Verification
```bash
python verification_gate.py
```

### Standalone Roster Refresh
```bash
python scripts/refresh_rosters.py
```

## Verification Report Format
Saved to `outputs/verification_report_TIMESTAMP.json`:
```json
{
  "timestamp": "2026-01-03T12:00:00Z",
  "corrections": [
    "⚠️ Jordan Clarkson: Outdated team UTA → NYK (traded 2025-12-20)"
  ],
  "warnings": [
    "⚠️ Data is 18.5 hours old (fresh)",
    "⚠️ OG Anunoby: High volatility (σ=8.5, μ=25.0)"
  ],
  "errors": [],
  "passed": true
}
```

## Error Handling

### Critical Errors (Block Output)
- Invalid team codes (not in NBA_TEAMS)
- Negative mu/sigma values
- Unrealistic stat averages (points > 50, rebounds > 25, etc.)

### Warnings (Allow Output)
- Data older than 24 hours
- High volatility picks (σ > 2μ)
- Players with QUESTIONABLE/DOUBTFUL injury status
- Players not found in roster file

### Auto-Corrections
- Known team trades applied automatically
- Picks with corrections flagged in metadata:
  ```json
  {
    "player": "Jordan Clarkson",
    "team": "NYK",
    "team_corrected": true,
    "previous_team": "UTA"
  }
  ```

## Maintenance

### Adding Team Trades
Edit `verification_gate.py`:
```python
KNOWN_TEAM_CHANGES = {
    "Player Name": ("OLD_TEAM", "NEW_TEAM", "YYYY-MM-DD"),
}
```

### Adjusting Data Freshness Limit
In `VerificationGate.verify_data_freshness()`:
```python
def verify_data_freshness(self, picks: List[dict], max_age_hours: int = 24)
                                                                    # ↑ Change this
```

### Adding Custom Checks
Extend `VerificationGate` class:
```python
def verify_custom_check(self, picks: List[dict]) -> List[dict]:
    """Your custom validation logic"""
    for pick in picks:
        # Validation logic
        if issue_found:
            self.warnings.append(f"⚠️ {pick['player']}: {issue}")
    return picks

# Add to run_full_verification()
def run_full_verification(self, picks: List[dict]):
    picks = self.verify_team_accuracy(picks)
    picks = self.verify_custom_check(picks)  # ADD HERE
    # ...
```

## Integration with Existing Validators

### Order of Execution
1. **VerificationGate** - Pre-processing validation (NEW)
2. **HydrationValidator** - Basic integrity checks
3. **LocalValidator** - Team/stat sanity checks
4. **Smart Validation** - Fast rule-based checks
5. **VerificationGate** - Final verification (in workflow Step 5)

### Why Multiple Layers?
- **VerificationGate**: Catches data quality issues (stale rosters, trades)
- **HydrationValidator**: Removes malformed entries
- **LocalValidator**: Auto-corrects high-confidence errors
- **Smart Validation**: Fast spot-checks for production confidence

## Example Output

### Successful Verification
```
==================================================================
  🛡️  PRE-OUTPUT VERIFICATION GATE
==================================================================

🔍 VERIFICATION: Checking team assignments...
   ⚠️ Jordan Clarkson: Outdated team UTA → NYK (traded 2025-12-20)
   ✅ Verified 945 picks

🔍 VERIFICATION: Checking statistical consistency...
   ✅ All 945 picks passed statistical checks

🔍 VERIFICATION: Checking roster status...
   ⚠️ OG Anunoby: Listed as QUESTIONABLE
   ✅ Checked 945 picks against roster

🔍 VERIFICATION: Checking data freshness...
   ✅ Data is 18.5 hours old (fresh)

==================================================================
  📊 VERIFICATION SUMMARY
==================================================================

✅ Auto-corrections: 1
   ⚠️ Jordan Clarkson: Outdated team UTA → NYK (traded 2025-12-20)

⚠️ Warnings: 2
   ⚠️ Data is 18.5 hours old (fresh)
   ⚠️ OG Anunoby: Listed as QUESTIONABLE

✅ VERIFICATION PASSED
   945 picks validated and ready for output
==================================================================

📄 Verification report saved: outputs/verification_report_20260103_120000.json
```

### Failed Verification (Blocks Output)
```
❌ CRITICAL ERRORS: 3
   ❌ Player X: Invalid team code 'XXX'
   ❌ Player Y points: Unrealistic average 75.0 (range: 0-50)
   ❌ Player Z rebounds: negative std dev (-2.5)

⛔ VERIFICATION FAILED - Cannot generate output
```

## Troubleshooting

### "Roster file not found"
**Solution**: Run `python scripts/refresh_rosters.py`

### "Data is X hours old"
**Solution**: 
```bash
python hydrate_new_picks.py  # Refresh hydration
```

### "Player not found in roster"
**Cause**: Roster refresh failed or player recently traded  
**Solution**: 
1. Run roster refresh
2. Add to `KNOWN_TEAM_CHANGES` if recent trade

### Verification gate exits with errors
**Solution**: Review error messages and:
- Fix invalid team codes in `picks.json`
- Remove players with impossible stats
- Update team assignments for traded players

## Future Enhancements

### Planned Features
- [ ] Live NBA API cross-validation for top picks
- [ ] Hit rate comparison (actual vs predicted last 5 games)
- [ ] Automated injury status updates from official sources
- [ ] Confidence degradation for unverified picks
- [ ] Email alerts for critical verification failures

### Experimental
- [ ] Machine learning anomaly detection
- [ ] Historical accuracy tracking per player
- [ ] Correlation analysis (same-team stacking penalties)
