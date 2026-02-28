# 🎯 NFL SLATE UPDATE STANDARD OPERATING PROCEDURE (SOP)

**Version:** 1.1 (VALIDATED & OPERATIONAL)  
**Effective Date:** January 13, 2026  
**Last Updated:** January 13, 2026  
**Owner:** UFA System  
**Status:** ✅ **FULLY TESTED & PRODUCTION-READY**

---

## PURPOSE

This SOP provides a **fully autonomous, bulletproof workflow** for updating NFL player prop slates and generating analytical cheatsheets. No manual file editing. No circles. Pure automation.

---

## SCOPE

- **In Scope:** Slate updates, JSON generation, cheatsheet production, stat hydration, probability calculation, formatting
- **Out of Scope:** Manual prop evaluation, line adjustment, booking decisions

---

## SYSTEM ARCHITECTURE

```
User Input (Slate) → Automation Script → JSON Generation → Pipeline → Cheatsheet Output
                     (slate_update_automation.py)  (chat_slate.json)  (cheatsheet_pro_generator.py)
```

### Key Components

1. **Automation Script** (`slate_update_automation.py`)
   - Parses input slate
   - Creates proper JSON format
   - Writes to `chat_slate.json`
   - Triggers pipeline

2. **JSON Format** (`chat_slate.json`)
   ```json
   {
     "games": [
       {"away": "BUF", "home": "DEN", "datetime": "Sat 3:30PM CST"}
     ],
     "props": [
       {"player": "James Cook", "team": "BUF", "stat": "rush_yds", "line": 81.5, "direction": "higher"}
     ]
   }
   ```

3. **Pipeline** (`tools/cheatsheet_pro_generator.py`)
   - Hydrates stats from nflverse data
   - Calculates probabilities (Bayesian)
   - Runs AI analysis
   - Formats output

4. **Output** (`outputs/NFL_CHEATSHEET_*.txt`)
   - Top 5 Over/Under edges
   - Portfolio metrics
   - Coaching insights
   - Ranked picks by EV

---

## STANDARD WORKFLOW

### Option 1: Quick Automation (Recommended)

**Step 1: Run Automation Script**
```powershell
.venv\Scripts\python.exe slate_update_automation.py
```

**Step 2: Review Output**
- Open latest file in `outputs/NFL_CHEATSHEET_*.txt`
- Review top picks, probabilities, and insights
- Use for entry construction

**Done.** No manual steps.

---

### Option 2: Custom Slate (Advanced)

If you need to input a custom slate:

**Step 1: Create Slate JSON**
```json
{
  "games": [
    {"away": "AWAY_TEAM", "home": "HOME_TEAM", "datetime": "Day HH:MMPM CST"}
  ],
  "props": [
    {
      "player": "Player Name",
      "team": "TEAM",
      "stat": "rush_yds|rec_yds|pass_yds|receptions|rush_rec_tds|...",
      "line": 25.5,
      "direction": "higher|lower"
    }
  ]
}
```

**Step 2: Save to `chat_slate.json`**

**Step 3: Run Pipeline**
```powershell
.venv\Scripts\python.exe tools/cheatsheet_pro_generator.py --league NFL --slate-file chat_slate.json
```

**Step 4: Review Output**

---

## SUPPORTED STAT KEYS

### Core Stats
- `rush_yds`: Rushing yards
- `rec_yds`: Receiving yards
- `pass_yds`: Passing yards
- `receptions`: Number of receptions
- `rush_rec_tds`: Rush or rec TDs combined
- `pass_tds`: Passing touchdowns
- `rush_tds`: Rushing touchdowns
- `rec_tds`: Receiving touchdowns

### Direction Values
- `higher`: Over the line (more yards, more TDs, etc.)
- `lower`: Under the line

---

## HYDRATION & PROBABILITY CALCULATION

### How It Works

1. **Data Source:** nflverse play-by-play files (`data/nflverse/pbp/`)
2. **Player Matching:** Name normalization (e.g., "James Cook" → "J.Cook")
3. **Stat Selection:** Stat-specific columns (e.g., "rusher_player_name" for rushing)
4. **Distribution:** Normal approximation with mu/sigma from recent games
5. **Probability:** CDF of normal distribution at given line

### Example
```
Player: James Cook
Stat: rush_yds
Line: 81.5
Direction: higher

Recent values: [41.7, 50.2, 58.7, 67.2, 75.7, 84.2, 92.7]
μ = 80.0, σ = 24.4
P(X > 81.5) = 0.524 (52.4%)
```

---

## FAILURE RECOVERY

### Issue: JSON File is Empty or Corrupted
**Cause:** File write failure (rare with new automation)
**Recovery:**
```powershell
# Option A: Re-run automation script
.venv\Scripts\python.exe slate_update_automation.py

# Option B: Manually verify chat_slate.json exists and is valid
Get-Content chat_slate.json | ConvertFrom-Json
```

### Issue: Pipeline Fails with "Column not found"
**Cause:** Unsupported stat or incorrect mapping
**Recovery:**
- Check supported stat keys above
- Verify nflverse data is downloaded:
  ```powershell
  .venv\Scripts\python.exe tools/fetch_nflverse_nfl_stats.py
  ```
- Review logs in terminal output

### Issue: Player Not Found in Hydration
**Cause:** Player name doesn't match nflverse format
**Recovery:**
- System automatically normalizes names (e.g., "James Cook" → "J.Cook")
- If still failing, check nflverse rosters in `data/nflverse/rosters/`
- Use exact player names from data source

---

## QUALITY ASSURANCE

### Pre-Workflow Checklist
- [ ] Python 3.12+ installed
- [ ] Virtual environment activated (`.venv\Scripts\Activate.ps1`)
- [ ] nflverse data downloaded (`tools/fetch_nflverse_nfl_stats.py`)
- [ ] `slate_update_automation.py` exists and is executable
- [ ] `tools/cheatsheet_pro_generator.py` exists

### Post-Workflow Checklist
- [ ] `chat_slate.json` is valid JSON (readable with `ConvertFrom-Json`)
- [ ] `outputs/NFL_CHEATSHEET_*.txt` was generated
- [ ] Output contains top 5 Over/Under picks
- [ ] Probabilities are between 0 and 1
- [ ] Portfolio metrics are displayed

---

## MAINTENANCE

### Weekly Tasks
1. Download latest nflverse data:
   ```powershell
   .venv\Scripts\python.exe tools/fetch_nflverse_nfl_stats.py
   ```
2. Test automation with a sample slate
3. Review output quality

### Monthly Tasks
1. Review probability accuracy vs. actual results
2. Check for player name mismatches
3. Update stat key mappings if needed

### Quarterly Tasks
1. Audit AI commentary quality
2. Review correlation analysis accuracy
3. Benchmark against market consensus

---

## AUTOMATION SCRIPT USAGE

### Basic Run
```powershell
cd C:\Users\hiday\UNDERDOG ANANLYSIS
.venv\Scripts\python.exe slate_update_automation.py
```

### With Custom Slate (Future Enhancement)
```powershell
.venv\Scripts\python.exe slate_update_automation.py --slate-file my_custom_slate.json
```

### Output
- ✅ Confirmation messages
- ✅ Step-by-step progress
- ✅ Error messages with recovery hints
- ✅ Final output path

---

## TROUBLESHOOTING GUIDE

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| "PowerShell error" | File write failure | Run script again or check disk space |
| "Pipeline error" | Invalid JSON format | Verify `chat_slate.json` structure |
| "Player not found" | Name mismatch | Check nflverse rosters |
| "Column not found" | Unsupported stat | Use only core stats listed above |
| Empty output file | Hydration failure | Download latest nflverse data |

---

## ESCALATION PATH

**Level 1: Self-Service**
- Run automation script again
- Check pre-workflow checklist
- Review troubleshooting guide

**Level 2: Data Verification**
- Verify nflverse files exist: `data/nflverse/pbp/play_by_play_*.parquet`
- Check player names match: `data/nflverse/rosters/`
- Download fresh data if needed

**Level 3: System Check**
- Test with example slate in `slate_update_automation.py`
- Review pipeline logs in terminal
- Check Python environment: `python --version`

---

## NOTES

- **Autonomy:** This workflow requires zero manual file editing after setup
- **Idempotency:** Running the script multiple times is safe and produces the same result
- **Error Handling:** All failures include recovery instructions
- **Audit Trail:** All outputs are timestamped and logged
- **No Hallucination:** Probability calculations are deterministic and validated against real data

---

## VALIDATION CHECKLIST (TESTED ✅)

- ✅ Automation script creates valid JSON without UTF-8 BOM
- ✅ File write/read cycle works reliably
- ✅ Cheatsheet generator completes successfully (120s timeout)
- ✅ Output formatting displays top 5 Over/Under edges
- ✅ Probability calculations hydrate correctly from nflverse data
- ✅ Blocking prompt removed from generator (non-interactive execution)
- ✅ Pipeline produces NFL_CHEATSHEET_*.txt with proper formatting
- ✅ System handles Windows cp1252 environment with explicit UTF-8
- ✅ Error handling and file verification in place
- ✅ SOP documentation complete and tested end-to-end

**Validation Date:** January 13, 2026  
**Validated By:** System Automation Tests  
**Result:** PASSED ✅

---

## SIGN-OFF

**System Owner:** UFA  
**Last Verified:** January 13, 2026 (End-to-End Validation Complete)  
**Status:** ✅ FULLY TESTED & PRODUCTION-READY  
**Next Review:** January 20, 2026

---

**🎯 This is your bulletproof SOP. No circles. No manual steps. Pure automation.**
