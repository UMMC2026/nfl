# Enhanced Workflow - Quick Start Guide

## What's New

Your system already has the critical fixes in place:
- ✅ Injury noise filtering (30 flags vs 581)
- ✅ Confidence scoring adjusted
- ✅ Duplicate removal working
- ✅ Correct date/time handling

This enhancement adds **3 new utility scripts** to make daily execution easier:

## New Scripts

### 1. **daily_workflow.py** - Complete Pipeline
Runs everything in sequence:
```bash
python scripts/daily_workflow.py
```

**What it does:**
1. Hydrates picks with nba_api (10-game rolling avg)
2. Generates cheatsheet
3. Builds parlay suggestions
4. Shows quick preview

### 2. **parlay_builder.py** - Betting Combination Generator
Automatically creates parlay suggestions:
```bash
python scripts/parlay_builder.py
```

**Outputs:**
- 🔒 SAFE 2-LEG (75%+ confidence)
- 💰 VALUE 3-LEG (65%+ confidence)
- 🎲 FLEX 4-LEG (55%+ confidence, diversified)

**Why use it:** Eliminates manual parlay construction; auto-validates team diversity

### 3. **report_analyzer.py** - Betting Recommendations
Extracts top picks and bet sizing from cheatsheet:
```bash
python scripts/report_analyzer.py
```

**Outputs:**
- Top 5 picks by confidence
- Unit sizing recommendations (Kelly Criterion)
- Risk assessment & volatility flags
- JSON export for external tools

## Recommended Daily Workflow

### Option A: Full Pipeline (Recommended)
```bash
python scripts/daily_workflow.py
```
⏱️ Takes ~5 minutes | Hydrates + Reports + Parlays + Analysis

### Option B: Quick Report Only
```bash
python generate_cheatsheet.py
python scripts/report_analyzer.py
```
⏱️ Takes ~30 seconds | Uses cached hydration data

### Option C: Custom
```bash
# Just update picks
python hydrate_new_picks.py

# Just report
python generate_cheatsheet.py

# Just parlays
python scripts/parlay_builder.py

# Just analysis
python scripts/report_analyzer.py
```

## Output Files

After running, check:
```
outputs/
  ├── CHEATSHEET_JAN03_20260103_1139_STATISTICAL.txt     ← Main report
  ├── CHEATSHEET_JAN03_20260103_1139_CALIBRATED.txt      ← Conservative version
  └── CHEATSHEET_JAN03_20260103_1139_analysis.json       ← Machine-readable
```

## Example Usage

### Morning Routine
```powershell
# Terminal 1: Start full workflow
cd C:\Users\hiday\UNDERDOG ANANLYSIS
.venv\Scripts\python.exe scripts\daily_workflow.py
```

### Quick Check (Next Time)
```powershell
# Re-use cached hydration
.venv\Scripts\python.exe scripts\report_analyzer.py
```

### Before Betting
```powershell
# Get betting recommendations
.venv\Scripts\python.exe scripts\report_analyzer.py
```

## Key Files

**Your Core System** (don't modify):
- `generate_cheatsheet.py` - Report generator (working well)
- `hydrate_new_picks.py` - Data fetcher (timeout-resilient)
- `picks.json` - Manual line input

**New Utilities** (add-on only):
- `scripts/daily_workflow.py` - Orchestrator
- `scripts/parlay_builder.py` - Parlay constructor
- `scripts/report_analyzer.py` - Analytics

## Expected Output Example

```
========================================================
  UNDERDOG FANTASY ANALYZER - DAILY WORKFLOW
  Friday, January 03, 2026 at 10:15 AM
========================================================

✓ Step 1: Hydrating picks with nba_api...
  Fetched 945 picks in 4m 23s
  TimeOuts: 0 (using cache)

✓ Step 2: Generating comprehensive cheatsheet...
  ✅ Saved: CHEATSHEET_JAN03_20260103_1200_STATISTICAL.txt
  ✅ Saved: CHEATSHEET_JAN03_20260103_1200_CALIBRATED.txt

✓ Step 3: Building parlay suggestions...
  🔒 Safe 2-Leg: 3 options found
  💰 Value 3-Leg: 2 options found
  🎲 Flex 4-Leg: 1 option found

========================================================
  ✅ WORKFLOW COMPLETE!
========================================================

📄 Latest Report: CHEATSHEET_JAN03_20260103_1200_STATISTICAL.txt

📊 Quick Preview:
   SLAM PLAYS (none)
   STRONG PLAYS:
   • Jordan Clarkson OVER 1.5 assists [67%]
   • OG Anunoby OVER 25.5 pts+reb+ast [67%]
   LEAN PLAYS:
   • Bobby Portis OVER 6.5 rebounds [63%]

✓ Ready for analysis!
```

## Customization

### To change confidence thresholds
Edit `generate_cheatsheet.py` lines 260-380

### To adjust parlay parameters
Edit `scripts/parlay_builder.py`:
- Change `0.75` for SAFE 2-LEG confidence threshold
- Change `0.65` for VALUE 3-LEG threshold
- Change `0.55` for FLEX 4-LEG threshold

### To modify bet sizing
Edit `scripts/report_analyzer.py` function `recommend_bet_sizing()`

## Troubleshooting

### "No picks found"
→ Run `python hydrate_new_picks.py` first

### "Timeout errors"
→ Already handled; system uses cached data

### "Date is wrong"
→ Check Windows system date (shows actual date)

### "Need new injury data"
→ Injury feed unavailable; system auto-caps confidence on UNKNOWN status

## Next Steps

1. ✅ Run `python scripts/daily_workflow.py` to test
2. ✅ Review output in `outputs/CHEATSHEET_*.txt`
3. ✅ Use `report_analyzer.py` for betting decisions
4. ✅ Build 2-3 leg parlays using suggestions
5. ✅ Track outcomes vs predictions

## Support

Your system is production-ready. All three new scripts are:
- ✅ Error-handled
- ✅ Tested with current data
- ✅ Non-breaking (don't modify core files)
- ✅ Modular (use any/all combinations)

Run them now and you'll have complete betting recommendations in minutes!
