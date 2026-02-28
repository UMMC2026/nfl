# ⚡ CALIBRATION SYSTEM — QUICK REFERENCE

## 🚀 30-SECOND START

```bash
# 1. Enable tracking
.venv\Scripts\python.exe scripts\setup_calibration_env.py --enable

# 2. Run tonight's NBA slate
.venv\Scripts\python.exe menu.py
→ [2] Analyze Slate

# 3. Tomorrow: Fetch results
→ [6] → [A] Auto-fetch

# 4. After 20+ picks: Diagnose
→ [DG] NBA Diagnostic
```

---

## 📱 MENU SHORTCUTS

| Key | Function | When to Use |
|-----|----------|-------------|
| **[2]** | Analyze Slate | Run nightly to capture predictions |
| **[6]→[A]** | Auto-fetch Results | Next morning after games |
| **[DG]** | NBA Diagnostic | After 20-30 resolved picks |
| **[CM]** | Migrate Old Data | One-time: convert old CSV |
| **[CE]** | Setup Environment | Configure .env tracking |
| **[CT]** | Test System | Validate installation |
| **[7]** | Calibration Backtest | Historical accuracy |

---

## 🎯 WHAT GETS CAPTURED

### Every Prediction Saves:
- **Lambda** (`lambda_player=27.3`) — Poisson anchor for diagnosis
- **Gap** (`gap=6.6%`) — Edge quality metric
- **Z-Score** (`z_score=0.35`) — Difficulty rating
- **Probability Chain** (`72.3% → 70% → 68.5%`) — Cap tracking
- **Game Context** (`team=LAL, opponent=BOS, game_id=002260145`)

### After Auto-Resolve:
- **Actual** (`actual=28.0`) — Box score result
- **Hit** (`hit=True`) — Outcome vs line
- **Brier** (`brier=0.0256`) — Calibration quality

---

## 🔬 DIAGNOSTIC OUTPUTS

### What It Tells You:
1. **Overall**: Win rate (48.5%) vs expected (60%) = **-11.5% gap**
2. **Broken Markets**: "PRA HIGHER: 25% vs 60%" → **Disable or adjust**
3. **Lambda Accuracy**: "PTS +2.1 error" → **Multiply lambda by 0.92**
4. **Optimal Threshold**: "Raise edge from 1.5 → 2.8" → **58% win rate**
5. **Tier Integrity**: "STRONG tier 40% vs 60%" → **Recalibrate**

### How to Fix:
```python
# Option 1: Disable broken market
if stat == "pra" and direction == "higher":
    return REJECTED

# Option 2: Adjust lambda
if stat == "points":
    mu_adj *= 0.92  # Fix +2.1 over-projection

# Option 3: Raise threshold
MIN_EDGE = 2.8  # From 1.5

# Option 4: Cap confidence
if market == "pra_higher":
    probability = min(probability, 55)
```

---

## 📂 KEY FILES

| File | Purpose |
|------|---------|
| `calibration/picks.csv` | All predictions + outcomes |
| `.env` | Has `ENABLE_CALIBRATION_TRACKING=1` |
| `scripts/auto_resolve_nba.py` | NBA API auto-fetch |
| `scripts/diagnose_nba_calibration.py` | Diagnostic engine |
| `CALIBRATION_COMPLETE.md` | Full documentation |

---

## 🆘 COMMON ISSUES

### "No predictions captured"
```bash
# Check tracking is enabled
cat .env | grep CALIBRATION
# Should show: ENABLE_CALIBRATION_TRACKING=1

# If missing:
.venv\Scripts\python.exe scripts\setup_calibration_env.py --enable
```

### "Auto-resolve fails"
```bash
# NBA API rate limit hit - script has auto-retry
# Wait 60 seconds and try again

# Or run manually:
.venv\Scripts\python.exe scripts\auto_resolve_nba.py
```

### "Diagnostic shows 0 picks"
```bash
# Need to resolve outcomes first:
.venv\Scripts\python.exe menu.py
→ [6] Resolve Picks → [A] Auto-fetch

# Verify outcomes populated:
python -c "import pandas as pd; df = pd.read_csv('calibration/picks.csv'); print(f'{len(df[df.hit.notna()])} resolved')"
```

---

## 📊 SUCCESS METRICS

### Week 1-2 (Data Collection)
- ✅ 5-10 picks/day captured with lambda
- ✅ Outcomes auto-resolved next day
- ✅ Lambda values present in CSV

### Week 3 (Diagnosis)
- 🎯 Diagnostic identifies broken markets
- 🎯 Lambda accuracy calculated per stat
- 🎯 Optimal edge threshold found

### Week 4+ (Improvement)
- 🎯 Win rate: 48.5% → 54%+ (above 52.4% breakeven)
- 🎯 STRONG tier: 40% → 60%+ hit rate
- 🎯 High-edge picks outperform low-edge

---

## 🎓 KEY CONCEPTS

### Lambda (μ)
**What**: Poisson distribution anchor (expected value)  
**Why**: Tells you if projection is wrong vs variance unlucky  
**Example**: `lambda=27.3`, `actual=28.0` → error = +0.7 (good!)

### Gap
**What**: `(lambda - line) / lambda × 100`  
**Why**: Edge quality — bigger gap = easier win  
**Example**: `lambda=27.3`, `line=25.5` → gap = 6.6%

### Z-Score
**What**: `(line - mu) / sigma`  
**Why**: Difficulty rating — higher z = harder pick  
**Example**: `z=0.35` = easy, `z=2.0` = very hard

### Brier Score
**What**: `(predicted - actual)²` where actual is 0 or 1  
**Why**: Calibration quality — lower = better  
**Example**: 68.5% prediction hits → `(0.685 - 1)² = 0.099`

---

## ⚡ POWER USER TIPS

### Batch Enable + Run
```bash
.venv\Scripts\python.exe scripts\setup_calibration_env.py --enable && .venv\Scripts\python.exe menu.py
```

### Check Lambda Accuracy (Manual)
```python
import pandas as pd
df = pd.read_csv('calibration/picks.csv')
df = df[df.hit.notna()]  # Only resolved picks
df['lambda_error'] = df.actual - df.lambda_player
print(df.groupby('stat')['lambda_error'].mean())
```

### Find Broken Markets (Manual)
```python
import pandas as pd
df = pd.read_csv('calibration/picks.csv')
df = df[df.hit.notna()]
df['market'] = df.stat + '_' + df.direction
results = df.groupby('market').agg({
    'hit': ['count', 'sum', 'mean'],
    'probability': 'mean'
})
results['gap'] = results[('hit','mean')] - results[('probability','mean')]/100
print(results[results[('gap','')] < -0.15])  # Markets >15% below expected
```

### Migrate + Test in One Command
```bash
.venv\Scripts\python.exe scripts\migrate_calibration_history.py && .venv\Scripts\python.exe scripts\test_calibration_system.py
```

---

## 📞 HELP

- **Full docs**: `CALIBRATION_COMPLETE.md`
- **Quick start**: `QUICKSTART_CALIBRATION.md`
- **Technical**: `docs/CALIBRATION_SYSTEM_UPGRADE.md`
- **Menu help**: Type `help` in main menu

---

**Status**: ✅ **FULLY OPERATIONAL** — Ready to use today!

**Last Updated**: February 7, 2026  
**Version**: v2.1.4
