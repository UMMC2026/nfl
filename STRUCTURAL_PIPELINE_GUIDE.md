# Structural Validation Pipeline Guide

## Overview
**Standalone system** that runs independently from your enhancement pipeline. No conflicts, no interference.

## Purpose
Detects and fixes portfolio construction issues:
- ❌ Duplicate player exposure
- ❌ High variance prop overload  
- ❌ Same-team correlation
- ❌ Over-aggressive multipliers

## Quick Start

### Run Structural Analysis
```bash
python structural_validation_pipeline.py
```

### Output Files
```
outputs/
├── structural_violations_report.txt  # Violation details
├── portfolio_before.json             # Original combos
├── portfolio_after.json              # Rebuilt portfolio
└── structural_comparison.txt         # Before/after summary
```

## What It Does

### 1. Validation Phase
- Loads qualified picks from `monte_carlo_enhanced.json`
- Analyzes top 10 combos for structural issues
- Identifies violations:
  - **DUPLICATE_EXPOSURE**: Players used multiple times
  - **VARIANCE_OVERLOAD**: High variance props >20%
  - **TEAM_CORRELATION**: Same-game correlation
  - **AGGRESSIVE_MULTIPLIERS**: 5+ leg entries

### 2. Rebuild Phase
- Selects **ONE primary edge per player** (highest confidence)
- Tiers picks: SLAM (75%+) / STRONG (65-74%) / LEAN (55-64%)
- Builds entries with controls:
  - ✅ Different teams required
  - ✅ No player reuse
  - ✅ Variance-aware tier mixing
  - ✅ Max 5 entries

## Current Results (Jan 7 Slate)

### VIOLATIONS DETECTED
```
🚨 CRITICAL: Duplicate Exposure
  • Deni Avdija: 8x usage
  • Shaedon Sharpe: 9x usage  
  • Bobby Portis: 8x usage

🚨 HIGH: Variance Overload
  • 43.3% high variance props (should be ≤20%)
  • 13 3PM props across 10 combos

⚠️  MEDIUM: Team Correlation
  • All 10 combos have same-team players
```

### STRUCTURAL FIX
```
BEFORE:
  10 combos
  5 duplicate players
  43.3% high variance

AFTER:
  5 primary edges (one per player)
  Tier distribution: 1 SLAM, 1 STRONG, 3 LEAN
  Max exposure: 1 per player
```

## Integration with Main System

### Current Workflow
```
1. Run enhancement pipeline (UNCHANGED)
   → monte_carlo_enhanced.py
   → Outputs: monte_carlo_enhanced.json

2. Run structural pipeline (NEW - INDEPENDENT)
   → structural_validation_pipeline.py
   → Reads: monte_carlo_enhanced.json
   → Outputs: violation reports + rebuilt portfolio

3. Compare results
   → Review violations
   → Adopt rebuilt entries
```

### No Conflicts
- ✅ Uses same input file (`monte_carlo_enhanced.json`)
- ✅ Separate output files (no overwriting)
- ✅ Independent execution (run anytime after enhancement)
- ✅ Can run daily without affecting enhancement pipeline

## User's Diagnosis (Validated)

From executive summary:
> "You did not fail because the system can't predict. You failed because edges were not isolated."

### Truth Confirmed
✅ **Projections RIGHT**: Many picks hit (Vanderbilt, Sam Merrill, KD, Horford, Wemby, Bam, DeRozan, Deni)  
❌ **Structure WRONG**: Duplicate exposure + correlation + variance overload = guaranteed bleed

### Root Causes Detected
1. **Duplicate exposure** - Deni/Shaedon/Bobby used 8-9x each
2. **Variance overload** - 43.3% high variance (13 3PM props)
3. **Team correlation** - All combos stacked same-game players
4. **No tier enforcement** - Mixed SLAM/STRONG/LEAN randomly

## Rules Enforced (After Rebuild)

### Primary Edge Selection
- Each player appears in **exactly ONE entry**
- If player has multiple qualified props, system picks highest confidence
- Eliminates duplicate exposure completely

### Variance Control
- HIGH variance props: 3PM, blocks, steals, turnovers
- COMBO props (low variance): PRA, pts+reb, pts+ast, reb+ast
- System tracks distribution, enforces ≤20% high variance

### Tier-Based Construction
- **SLAM** (75%+ prob, low/med variance): Core of portfolio
- **STRONG** (65-74%, low/med variance): Mix with SLAMs
- **LEAN** (55-64%): Isolated, max 2-pick entries

### Correlation Prevention
- Different teams required per entry
- No same-game stacking
- 70%+ stat diversity preferred

## Next Steps

### Immediate
1. ✅ Review `outputs/structural_violations_report.txt`
2. ✅ Compare `portfolio_before.json` vs `portfolio_after.json`
3. Apply rebuilt portfolio rules to future slates

### Future Integration
Consider adding to `daily_pipeline.py`:
```python
# After monte_carlo_enhanced.py completes
import subprocess
subprocess.run(['python', 'structural_validation_pipeline.py'])
```

### Continuous Improvement
- Track violation trends over time
- Measure hit rates by tier (SLAM vs STRONG vs LEAN)
- Adjust thresholds based on actual results
- Build correlation matrices for deeper analysis

## Files Modified
**NONE** - This is a completely new, independent pipeline.

## Files Created
1. `structural_validation_pipeline.py` - Main pipeline
2. `outputs/structural_violations_report.txt` - Validation results
3. `outputs/portfolio_before.json` - Original combos
4. `outputs/portfolio_after.json` - Rebuilt portfolio
5. `outputs/structural_comparison.txt` - Summary
6. `STRUCTURAL_PIPELINE_GUIDE.md` - This guide

---

**Status**: ✅ OPERATIONAL  
**Conflicts**: ❌ NONE  
**Dependencies**: monte_carlo_enhanced.json (reads only, does not modify)
