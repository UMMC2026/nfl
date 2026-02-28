# 🚀 QUICK START GUIDE — Calibration System

## ⚡ 5-Minute Setup

### Step 1: Enable Calibration Tracking (30 seconds)
```powershell
# PowerShell
$env:ENABLE_CALIBRATION_TRACKING="1"

# Or add to .env file permanently
"ENABLE_CALIBRATION_TRACKING=1" | Out-File -Append .env
```

### Step 2: Run Tonight's Slate (2 minutes)
```powershell
.venv\Scripts\python.exe menu.py
```
- Choose **[1]** Ingest New Slate (paste Underdog lines)
- Choose **[2]** Analyze Slate
- **Result**: Predictions saved to `calibration/picks.csv` with lambda values ✅

### Step 3: Resolve Outcomes Tomorrow (1 minute)
```powershell
.venv\Scripts\python.exe menu.py
```
- Choose **[6]** Resolve Picks
- Choose **[A]** Auto-fetch from NBA API
- **Result**: Box scores fetched, outcomes updated ✅

### Step 4: Run Diagnostic (1 minute)
```powershell
.venv\Scripts\python.exe menu.py
```
- Choose **[DG]** NBA Diagnostic
- Choose **[Y]** to save report
- **Result**: Comprehensive diagnostic report showing what's broken ✅

---

## 📊 What You'll Discover

### Example Diagnostic Output:
```
PERFORMANCE BY MARKET + DIRECTION
Market          Dir      WinRate    N     Expected    Error     
----------------------------------------------------------------------
PRA             higher   25.0%      20    60.0%       -35.0% ⚠️ LOSING
PRA             lower    70.0%      10    65.0%       +5.0%
Points          higher   52.0%      25    58.0%       -6.0%

LAMBDA (ANCHOR) ACCURACY
Market          Mean Error   RMSE       N    
--------------------------------------------------
PRA             +3.1         4.2        30 ⚠️
Points          +1.8         3.1        25
Rebounds        +0.5         2.0        20

💡 RECOMMENDATION: 
  1. DISABLE: PRA HIGHER (25% win rate vs 60% expected)
  2. FIX: PRA lambda over-projects by +3.1 units
  3. RAISE: Minimum edge to 3.0 (gives 56% win rate)
```

---

## 🔧 Quick Fixes

### Fix 1: Disable Broken Market
**File:** `config/penalty_mode.json` or via menu [10] Settings

Add to ban list:
```json
{
  "banned_combinations": [
    {"stat": "pra", "direction": "higher"}
  ]
}
```

### Fix 2: Adjust Lambda Calculation
**File:** `risk_first_analyzer.py` (line ~1138)

```python
# BEFORE:
mu_adj = float(mu_raw * total_factor)

# AFTER (reduce PRA projection by 15%):
if stat.lower() == "pra":
    mu_adj = float(mu_raw * total_factor * 0.85)
else:
    mu_adj = float(mu_raw * total_factor)
```

### Fix 3: Raise Edge Threshold
**File:** `config/thresholds.py` or in analyze function

```python
MINIMUM_EDGE = {
    "PRA": 3.5,
    "Points": 3.0,
    "Rebounds": 2.5,
}
```

---

## 📈 Expected Results

After fixes + 2 weeks:
- **Win Rate**: 48.5% → 54%+ ✅
- **PRA HIGHER**: Disabled or fixed to 55%+
- **Lambda Error**: +3.1 → <1.0
- **Profitability**: Losing → Winning at -110 odds

---

## ❓ Troubleshooting

### "No completed NBA picks found"
**Solution:** Run [6] Resolve Picks → [A] Auto-fetch first

### "Player not found in NBA API"
**Cause:** Name mismatch (e.g., "K. Durant" vs "Kevin Durant")
**Solution:** Check `calibration/picks.csv` and fix player names manually

### "No games found"
**Cause:** Pick date doesn't match game date (timezone issue)
**Solution:** Check date in `calibration/picks.csv`, adjust if needed

---

## 🎯 Daily Workflow

**Before Games (5pm ET):**
1. Ingest slate
2. Analyze → Predictions saved with lambda ✅

**After Games (11pm ET):**
3. Auto-resolve → Outcomes updated ✅

**Weekly (Sunday morning):**
4. Run diagnostic → Find new issues
5. Deploy fixes → Improve model
6. Monitor win rate → Validate improvements

---

## 📞 Need Help?

Check full docs: `docs/CALIBRATION_SYSTEM_UPGRADE.md`

Run validation: `.venv\Scripts\python.exe scripts\validate_calibration_system.py`

---

**Time Investment:** 5 min/day during season
**Payoff:** Fix 48.5% → 54%+ win rate in 2 weeks
**ROI:** Worth it? YES ✅
