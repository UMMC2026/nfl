# ⚡ QUICK REFERENCE - Daily Betting Workflow

## 🚀 ONE-COMMAND ANALYSIS
```bash
python scripts/daily_workflow.py
```
✅ Updates picks | ✅ Generates report | ✅ Analyzes picks | **30 seconds**

---

## 📊 THREE-STEP WORKFLOW

### Step 1: Update Data (Optional)
```bash
python hydrate_new_picks.py
```
Use if lines changed since last hydration. Skip if using cached data.

### Step 2: Generate Report
```bash
python generate_cheatsheet.py
```
Outputs: `CHEATSHEET_*_STATISTICAL.txt` + `CHEATSHEET_*_CALIBRATED.txt`

### Step 3: Get Betting Recommendations
```bash
python scripts/report_analyzer.py
```
Shows: Top picks | Unit sizing | Risk factors | Parlay eligibility

---

## 📋 TODAY'S QUICK SUMMARY

**Latest Report:** `CHEATSHEET_JAN03_20260103_1155_STATISTICAL.txt`

| Metric | Value |
|--------|-------|
| Strong Plays (60-74%) | 2 picks @ 67% |
| Lean Plays (50-59%) | 8 picks @ 54-63% |
| Total Actionable | 10 picks |
| **Top Pick #1** | **Jordan Clarkson OVER 1.5 ast [67%]** |
| **Top Pick #2** | **OG Anunoby OVER 25.5 PRA [67%]** |
| **Top Pick #3** | **Bobby Portis OVER 6.5 reb [63%]** |
| Parlay Eligible | ❌ NO (skip parlays today) |
| Bet Sizing | 💪 1 unit per STRONG pick |

---

## 💰 TODAY'S BETTING PLAN

### ✅ DO THIS
- [ ] Play **Jordan Clarkson OVER 1.5 assists** at 1 unit (67% confidence)
- [ ] Play **OG Anunoby OVER 25.5 PRA** at 1 unit (67% confidence)
- [ ] Play 2-3 **LEAN picks** at 0.5 units each (reduce variance)

### ❌ DON'T DO THIS
- ❌ Skip parlays (insufficient high-confidence picks)
- ❌ Avoid high-volatility players (Curry, Booker)
- ❌ Don't increase sizing (confidence capped due to injury feed)

---

## 🎯 UNIT SIZING (Kelly Criterion)

| Confidence | Unit Sizing | Payout |
|------------|------------|--------|
| 75%+ (SLAM) | **2 units** | 3.5x |
| 60-74% (STRONG) | **1 unit** | 2.0x |
| 50-59% (LEAN) | **0.5 units** | 1.5x |
| Parlay 2-leg | ❌ SKIP | N/A |

---

## 🚑 INJURY FLAGS TO CHECK

These players are in your picks but have UNKNOWN injury status:
- **Jordan Poole** - Check status before betting
- **Mark Williams** - Check status before betting
- **AJ Green** - Check status before betting

*Note: Injury feed is degraded; manually verify before wagering*

---

## 📈 HIGH VOLATILITY PLAYERS
Avoid parlaying these (high std deviation):
- Stephen Curry (σ=14.4 points)
- Devin Booker (σ=10.8 points)

---

## 🔄 DAILY CHECKLIST

**Every Morning:**
- [ ] Run `python scripts/daily_workflow.py` (or use cache)
- [ ] Review output in terminal
- [ ] Read top 3 picks from report analyzer
- [ ] Check injury status of flagged players
- [ ] Place bets on STRONG picks only
- [ ] Note outcomes at day's end

**Every Week:**
- [ ] Track pick outcomes vs predictions
- [ ] Adjust confidence thresholds if needed
- [ ] Monitor injury feed status

---

## 📂 IMPORTANT FILES

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `picks.json` | Manual line input | Daily (new games) |
| `picks_hydrated.json` | Cached rolling averages | On demand |
| `outputs/CHEATSHEET_*.txt` | Main betting report | Daily |
| `scripts/report_analyzer.py` | Betting recommendations | Daily |
| `generate_cheatsheet.py` | Report generator | Don't modify |

---

## 🛠️ COMMON COMMANDS

```bash
# Full fresh analysis
python scripts/daily_workflow.py

# Just get betting recommendations
python scripts/report_analyzer.py

# Generate parlay suggestions
python scripts/parlay_builder.py

# Re-hydrate picks (if lines changed)
python hydrate_new_picks.py

# Generate report only
python generate_cheatsheet.py

# Check latest report
type outputs\CHEATSHEET_*.txt | head -50
```

---

## ⚙️ CUSTOM THRESHOLDS

**Want stricter filters?** Edit `generate_cheatsheet.py`:
```python
# Line 260-270 (change these)
SLAM_STAT = 0.70      # Increase to 0.75
STRONG_STAT = 0.55    # Increase to 0.60
OVERS_STAT = 0.55     # Increase to 0.65
```

**Want more parlay options?** Edit `scripts/parlay_builder.py`:
```python
# Line 40 (lower the threshold)
if p.get('prob_display', 0) >= 0.75:  # Change to 0.70
```

---

## 📊 EXPECTED DAILY OUTPUTS

**Worst Day:**
- 0 SLAM plays
- 0-1 STRONG plays
- 3-5 LEAN plays
- Action: Play single picks only

**Good Day:**
- 0-1 SLAM plays
- 2-3 STRONG plays
- 5-8 LEAN plays
- Action: 2-leg parlay may be viable

**Great Day:**
- 1+ SLAM plays
- 3+ STRONG plays
- 8+ LEAN plays
- Action: Build 2-3 leg parlay

---

## 🎯 TODAY'S GRADE: MODERATE

**Pick Quality:** ⭐⭐⭐ (3/5)
- 2 solid STRONG plays at 67%
- 8 LEAN plays for diversification
- No SLAM plays (don't get greedy)

**Parlay Opportunity:** ❌ SKIP
- Need 3+ picks at 65%+
- Today has only 2 at that level

**Recommended Action:** 
**Play 1 unit on each STRONG pick + 0.5 units on 2-3 LEAN picks**

Expected Win Rate: ~58% (break-even: 52%)

---

**Last Updated:** January 3, 2026
**Next Report:** Run `python scripts/daily_workflow.py`
**System Status:** ✅ PRODUCTION READY
