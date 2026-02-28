# CBB Playwright Scraper - Troubleshooting Guide

## Issue: 100% OVER Bias + Roster Validation Failures

### Root Cause (Feb 16, 2026)

**Symptoms:**
```
⛔ DIRECTION GATE TRIGGERED: 34/34 (100.0%) are OVER
[AUTO] [!] 40 prop(s) flagged: player not found on current team roster
```

**Causes:**
1. **Direction Bias**: Persistent browser mode only captured visible props (OVER side)
2. **Missing Teams**: Scraper wasn't extracting team/matchup context
3. **Roster Validation Failure**: Without teams, can't match players to rosters

### Fixed (2026-02-16)

**Changes Made:**
1. **[ingestion/prop_ingestion_pipeline.py](ingestion/prop_ingestion_pipeline.py#L172-L255)**
   - Added `current_matchup` tracker to extract game context
   - Changed: `# Skip matchup lines` → `# Extract matchup lines for team context`
   - Now captures: `{'team1': 'ISU', 'team2': 'HOU'}` from text patterns

2. **[sports/cbb/cbb_main.py](sports/cbb/cbb_main.py#L2973)**
   - Added user guidance: "Toggle BOTH 'Higher' AND 'Lower' to see all prop sides"
   - Extracts `matchup` field from scraped props
   - Stores team as `"TEAM1_vs_TEAM2"` for roster resolution

### How to Use (Updated Workflow)

```powershell
.venv\Scripts\python.exe sports\cbb\cbb_main.py → [1B] Auto-Ingest
```

**Critical Steps:**
1. Select **[1] Persistent browser** mode
2. Browser opens → Login to Underdog/PrizePicks
3. **Navigate to COLLEGE BASKETBALL section**
4. **Scroll through ALL available games** (future dates too)
5. **Toggle filters**:
   - Click "Higher" → see OVER props
   - Click "Lower" → see UNDER props
   - **Must do BOTH** to avoid direction bias
6. Press **Ctrl+C** when done browsing
7. Scraper extracts all visible props with teams

### Direction Gate (Governance)

**Purpose**: Detect structural model bias, not real edges

**Threshold**: 65% same direction triggers abort

**Why This Matters:**
- If 100% of picks are OVER, lines aren't mispriced—model is biased
- CBB lines are efficient; systematic one-way edges don't exist
- **False alarms happen** if user only views one side of props

**How to Avoid:**
```
✅ Toggle BOTH Higher/Lower in DFS interface
✅ Scroll through ALL games (not just one matchup)
✅ Verify scraped props show mix of directions before analysis
```

### Verification

**Check scraped data:**
```powershell
Get-Content sports\cbb\inputs\cbb_slate_latest.json | Select-String -Pattern '"direction"' | Group-Object
```

**Expected output:**
```
Count  Name
-----  ----
  20   "direction": "higher",
  20   "direction": "lower",
```

**If 100% one direction:**
- Re-scrape with BOTH Higher/Lower toggled
- OR use [8] Odds API ingest (gets both sides automatically)
- OR use [1] Manual paste (copy from DFS site)

###Team Extraction Examples

**What scraper now captures:**
```
Input text:
  "Iowa State @ Houston - 7:00PM EST"
  "Tamin Lipsey"
  "11.5"
  "Points"
  "Higher"

Extracted:
  matchup: {team1: "Iowa State", team2: "Houston"}
  player: "Tamin Lipsey"
  stat: "points"
  line: 11.5
  direction: "higher"
```

**Matched formats:**
- `ISU vs HOU` → NBA-style abbreviations
- `Iowa State @ Houston` → Full team names  
- `MIN vs NOP - 7:00PM CST` → With timestamps

### Alternative: Odds API (Recommended for CBB)

**Why better for CBB:**
- Gets BOTH directions automatically
- Includes team data in API response
- No browser automation needed
- Usually posted 1-3 hours before tip-off

**Usage:**
```powershell
.venv\Scripts\python.exe sports\cbb\cbb_main.py → [8] Odds API Ingest
```

**Tradeoffs:**
- ❌ Uses API quota (~5-10 units per run)
- ❌ Only marquee games have props posted
- ✅ No manual navigation needed
- ✅ Guaranteed both directions
- ✅ Team names included

### Roster Validation (Future Enhancement)

**Current behavior:**
```python
team = 'UNK'  # Hardcoded when matchup extraction fails
```

**After this fix:**
```python
team = "ISU_vs_HOU"  # From matchup context
# ESPN API resolves to actual rosters
```

**If still fails:**
1. Player name spelling mismatch (e.g., "De'Aaron" vs "DeAaron")
2. Transfer portal (player changed teams mid-season)
3. Redshirt/walk-on not in ESPN data

**Workaround:**
```powershell
.venv\Scripts\python.exe sports\cbb\cbb_main.py → [O] Player Overrides
# Manually set team for specific players
```

### Summary

| Issue | Before | After |
|-------|--------|-------|
| **Direction bias** | User saw only OVER side | Guidance to toggle both |
| **Team extraction** | Skipped matchup lines | Extracts `{'team1', 'team2'}` |
| **Roster validation** | 40/40 failures | Resolved by matchup context |
| **Direction gate** | 100% OVER → abort | Mix of both → passes |

**Next Steps:**
1. Re-run [1B] with BOTH Higher/Lower toggled
2. Verify mix of directions in scraped data
3. Pipeline should pass direction gate (if real edge exists)
