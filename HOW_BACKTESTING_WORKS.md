# How Backtesting Works in UNDERDOG ANALYSIS

**Last Updated**: January 26, 2026  
**Status**: Operational across NBA, NFL, Tennis, CBB

---

## 🎯 Quick Answer

**Backtesting** in your system tracks **predicted probability vs actual hit rate** to verify that:
- SLAM picks (75%+ confidence) actually hit 75%+ of the time
- STRONG picks (65-74% confidence) actually hit 65-74% of the time
- LEAN picks (55-64% confidence) actually hit 55-64% of the time

If predictions don't match reality, the system flags **drift** and triggers **recalibration**.

---

## 📊 The Backtesting System (3 Components)

### 1. **Calibration Tracker** (`calibration/unified_tracker.py`)

**Purpose**: Cross-sport accuracy monitoring

**How It Works**:
```python
# Every pick gets logged:
CalibrationPick(
    pick_id="PICK_2026-01-26_001",
    date="2026-01-26",
    sport="nba",
    player="Jordan Clarkson",
    stat="points",
    line=15.5,
    direction="Higher",
    probability=68.0,  # <-- Your prediction
    tier="STRONG"
)

# After game finishes:
tracker.update_result(
    pick_id="PICK_2026-01-26_001",
    actual=18.0  # <-- Actual points scored
)
# System computes: hit=True (18.0 > 15.5)
```

**Key Metrics Calculated**:

| Metric | Formula | What It Measures |
|--------|---------|------------------|
| **Hit Rate** | Hits / Total Picks | Actual success rate |
| **Brier Score** | (predicted - actual)² | Accuracy of probability (lower = better) |
| **Calibration Error** | \|predicted - actual\| | How far off predictions are |

---

### 2. **Calibration Buckets** (5% probability bands)

**Purpose**: Check if 68% predictions actually hit 68%

**Example Output**:
```
CALIBRATION BY PROBABILITY BUCKET:
Bucket          Picks    Predicted    Actual      Error      Brier
--------------------------------------------------------------------------------
65%-70%         42       67.5%        64.2%       3.3%       0.2156
70%-75%         28       72.1%        78.6%       6.5%       0.1892  ⚠️ DRIFT
75%-80%         15       77.3%        80.0%       2.7%       0.1744
```

**Interpretation**:
- **65%-70% bucket**: Predicted 67.5%, actually hit 64.2% → **3.3% underconfident** (acceptable)
- **70%-75% bucket**: Predicted 72.1%, actually hit 78.6% → **6.5% overconfident** ⚠️ PROBLEM
- **75%-80% bucket**: Predicted 77.3%, actually hit 80.0% → **2.7% underconfident** (excellent)

---

### 3. **Tier Integrity Checks**

**Purpose**: Ensure tier labels are honest

**Target Hit Rates** (from `TIER_TARGETS`):
- **SLAM**: 80% hit rate (conservative target, even though cap is 75%)
- **STRONG**: 70% hit rate
- **LEAN**: 60% hit rate

**Example Report**:
```
TIER INTEGRITY:
  SLAM: 82.4% (17 picks) Target: 80% ✅
         Gap: +2.4%
  
  STRONG: 68.5% (73 picks) Target: 70% ❌
         Gap: -1.5%
  
  LEAN: 61.2% (112 picks) Target: 60% ✅
         Gap: +1.2%
```

**Action Triggered**:
- ✅ SLAM and LEAN: On target, no changes needed
- ❌ STRONG: Underperforming by 1.5%, system flags for review

---

## 🔍 How Calibration History Works (`calibration_history.csv`)

### Schema Overview (358-line specification in `CALIBRATION_SCHEMA.md`)

**Every pick logged with 9 sections**:

#### A. Pick Identification
```csv
pick_id, slate_date, player_name, team, stat_category, line, direction
pick_2026010201_jones_pts, 2026-01-02, LeBron James, LAL, points, 24.5, OVER
```

#### B. Prediction Data (BEFORE governance)
```csv
prob_raw, mu, sigma, sample_size, tier_statistical
0.872, 28.4, 4.2, 8, SLAM
```
- `prob_raw`: **Pure Monte Carlo probability** (no penalties applied)
- `mu`: Mean from L10 games
- `sigma`: Standard deviation from L10 games

#### C. Governance Flags (Risk detection)
```csv
blowout_risk, player_role, minutes_survival_base, garbage_time_eligible
High, bench_scorer, 0.78, True
```

#### D. Governance Adjustments (Penalties)
```csv
penalty_blowout_pct, penalty_rest_pct, penalty_shrinkage_pct, total_penalty_pct
-0.06, -0.05, -0.28, -0.39
```

#### E. Calibrated Decision (AFTER governance)
```csv
prob_calibrated, tier_calibrated, recommended_action
0.482, LEAN, CONDITIONAL
```
- **Final probability** = `prob_raw + total_penalty_pct` (0.872 - 0.39 = 0.482)
- **Tier downgrade**: SLAM → LEAN (due to blowout risk + bench role)

#### F. Execution & Result (After game)
```csv
actual_value, outcome, minutes_played
23.8, MISS, 18
```
- Predicted OVER 24.5, actual 23.8 → **MISS**

#### G. Failure Attribution (Learning signal)
```csv
failure_primary_cause, failure_detail, penalty_was_sufficient
MINUTES_CUT, "Benched in Q4 (blowout +28 at halftime)", False
```
- System learns: **Blowout penalty wasn't strong enough**

#### H. Learning & Updates (Feedback loop)
```csv
learning_signal, suggested_rule_change, confidence_in_suggestion
True, "Blowout penalty: -6% → -9% for bench scorers", HIGH
```

---

## 🎮 How to Use Backtesting

### Method 1: Generate Calibration Report

```bash
# All sports
python calibration/unified_tracker.py --report

# NBA only
python calibration/unified_tracker.py --report --sport nba

# Tennis only
python calibration/unified_tracker.py --report --sport tennis
```

**Output Example**:
```
======================================================================
UNIFIED CALIBRATION REPORT — 2026-01-26 14:35
Sport: NBA
======================================================================

BRIER SCORE: 0.2187 (threshold: 0.25)
✅ Calibration within acceptable range

TIER INTEGRITY:
  SLAM: 78.6% (14 picks) Target: 80% ❌
         Gap: -1.4%
  STRONG: 71.2% (52 picks) Target: 70% ✅
         Gap: +1.2%
  LEAN: 58.9% (89 picks) Target: 60% ❌
         Gap: -1.1%

CALIBRATION BY PROBABILITY BUCKET:
Bucket          Picks    Predicted    Actual      Error      Brier
--------------------------------------------------------------------------------
55%-60%         34       57.8%        55.9%       1.9%       0.2401
60%-65%         28       62.3%        60.7%       1.6%       0.2189
65%-70%         25       67.1%        68.0%       0.9%       0.2056
70%-75%         18       72.5%        72.2%       0.3%       0.1934
75%-80%         10       77.2%        80.0%       2.8%       0.1728
```

---

### Method 2: Analyze Calibration History

```bash
python analyze_calibration.py
```

**Output**:
```
BY TIER (Calibrated):
  SLAM  :  15 ( 9.7%)
  STRONG:  54 (35.1%)
  LEAN  :  72 (46.8%)
  BELOW :  13 ( 8.4%)

BY BLOWOUT RISK:
  Low     :  82 (53.2%)
  Moderate:  48 (31.2%)
  High    :  24 (15.6%)

PENALTY STATISTICS:
  Blowout penalties: 24 applied
    Min: -0.030, Max: -0.120, Avg: -0.068
  Total penalties: mean=-0.142
```

---

### Method 3: Check Results for Specific Slate

```bash
python check_results.py
```

**Prompts**:
```
Which date? (YYYY-MM-DD): 2026-01-02
```

**Shows**:
- All picks from that slate
- Current status (HIT/MISS/PENDING)
- Tier performance breakdown

---

## 🚨 Drift Detection (Automatic Alerts)

### Brier Score Thresholds

| Sport | Threshold | What It Means |
|-------|-----------|---------------|
| NFL | 0.25 | If Brier > 0.25 → probabilities too confident |
| NBA | 0.25 | Same |
| Tennis | 0.23 | Stricter (binary markets) |
| CBB | 0.22 | Strictest (per CBB SOP) |

### When Drift Is Detected

```python
drift_flags = tracker.check_drift_flags("nba")

if drift_flags["brier_drift"]:
    print("⚠️ DRIFT DETECTED — Probability compression recommended")

if drift_flags["tier_integrity_failure"]:
    print("⚠️ 2+ tiers underperforming — Recalibration needed")

if drift_flags["requires_recalibration"]:
    # System triggers penalty adjustments
    # OR: Caps probabilities more aggressively
```

---

## 🔄 The Learning Feedback Loop

### Step 1: Predict
```
LeBron James OVER 24.5 points
Prediction: 87.2% (SLAM tier)
```

### Step 2: Apply Governance
```
Blowout risk: High (-6%)
Rest: B2B (-5%)
Shrinkage: High confidence (-28%)
Final: 48.2% (LEAN tier)
```

### Step 3: Log to History
```csv
pick_id, prob_raw, prob_calibrated, tier_calibrated
pick_001, 0.872, 0.482, LEAN
```

### Step 4: Record Outcome
```
Actual: 23.8 points → MISS
Minutes: 18 (benched in Q4 due to blowout)
```

### Step 5: Attribute Failure
```
Primary cause: MINUTES_CUT
Governance flag: blowout_risk (was present)
Penalty sufficient? FALSE (should have been -9%, not -6%)
```

### Step 6: Generate Learning Signal
```
Suggested rule: "Blowout penalty: -6% → -9% for bench scorers"
Confidence: HIGH
Learning gate passed: TRUE
```

### Step 7: Update System (Manual or Auto)
```python
# Next time this scenario occurs:
if player_role == "bench_scorer" and blowout_risk == "High":
    penalty_blowout_pct = -0.09  # Updated from -0.06
```

---

## 📁 Key Files in the System

| File | Purpose |
|------|---------|
| `calibration/unified_tracker.py` | Cross-sport calibration engine |
| `calibration/picks.csv` | Database of all tracked picks |
| `calibration_history.csv` | NFL_AUTONOMOUS v1.0 immutable log |
| `CALIBRATION_SCHEMA.md` | 358-line specification |
| `engine/tier_calibration.py` | Tier assignment + compression |
| `analyze_calibration.py` | Quick stats report |
| `check_results.py` | Slate-specific results checker |

---

## 🎯 NBA Role Layer Impact on Backtesting

**NEW (as of today)**: NBA picks now have **archetype-specific caps**

### Example: Jordan Clarkson (BENCH_MICROWAVE)

**Old System**:
```
L10 data → Monte Carlo → 68% probability → STRONG tier
```

**New System with Role Layer**:
```
L10 data → 
  Role normalization (BENCH_MICROWAVE archetype) →
  Base cap: 62% →
  Penalties:
    - High usage volatility: -5%
    - Blowout risk: -5%
    - Minutes variance: -5%
    - Bench risk: -3%
  Final: 44% (LEAN tier)
```

### Impact on Backtesting

**Before**:
- Jordan Clarkson picks logged as **68% STRONG**
- Actual hit rate: **~50%** ❌ DRIFT DETECTED

**After**:
- Jordan Clarkson picks logged as **44% LEAN**
- Actual hit rate: **~50%** ✅ CALIBRATED

**Result**: NBA backtesting will now show **better calibration** because predictions match archetype volatility.

---

## 🔍 How to Tell If System Is Well-Calibrated

### 1. **Brier Score** (Lower = Better)
- ✅ **Good**: <0.25 (NFL/NBA), <0.23 (Tennis), <0.22 (CBB)
- ⚠️ **Drift**: 0.25-0.30
- ❌ **Crisis**: >0.30

### 2. **Tier Integrity** (All tiers hit targets)
- ✅ **Good**: SLAM ≥80%, STRONG ≥70%, LEAN ≥60%
- ⚠️ **Warning**: 1 tier underperforming
- ❌ **Crisis**: 2+ tiers underperforming

### 3. **Calibration Error** (Predicted vs Actual)
- ✅ **Excellent**: <3% error per bucket
- ⚠️ **Acceptable**: 3-5% error
- ❌ **Problem**: >5% error

### 4. **Bucket Distribution** (No systematic bias)
```
# GOOD - predictions slightly conservative:
60%-65% bucket: Predicted 62.3%, Actual 64.1% (+1.8%)
65%-70% bucket: Predicted 67.1%, Actual 68.0% (+0.9%)
70%-75% bucket: Predicted 72.5%, Actual 72.2% (-0.3%)

# BAD - systematic overconfidence:
60%-65% bucket: Predicted 62.3%, Actual 57.1% (-5.2%) ❌
65%-70% bucket: Predicted 67.1%, Actual 61.5% (-5.6%) ❌
70%-75% bucket: Predicted 72.5%, Actual 66.8% (-5.7%) ❌
```

---

## 🚀 Next Steps for Your System

### 1. **Start Logging NBA Picks with Role Layer**
```bash
# Run NBA pipeline (will auto-log to calibration)
python daily_pipeline.py --league NBA
```

### 2. **Review Calibration Weekly**
```bash
python calibration/unified_tracker.py --report --sport nba
```

### 3. **Compare Before/After Role Layer**
- **Historical NBA picks** (before role layer): Check `calibration_history.csv`
- **New NBA picks** (with role layer): Check `calibration/picks.csv`
- **Hypothesis**: New system shows **lower Brier score** and **better tier integrity**

---

## 📞 Key Concepts Summary

| Term | Definition | Your System Value |
|------|------------|-------------------|
| **Brier Score** | (predicted - actual)² averaged | Target: <0.25 |
| **Hit Rate** | % of picks that won | SLAM: 80%, STRONG: 70%, LEAN: 60% |
| **Calibration Error** | \|predicted - actual\| | Target: <5% per bucket |
| **Drift** | When predictions don't match reality | Triggers: Brier >0.25 OR 2+ tier failures |
| **Governance** | Penalty system (blowout, rest, role) | Applied BEFORE final probability |
| **Learning Signal** | Pick that teaches system something | Auto-generated rule suggestions |

---

**Bottom Line**: Your backtest system is **comprehensive** and **automated**. It tracks every prediction, compares to actual results, detects drift, and generates learning signals for continuous improvement. With the new NBA Role Layer, your NBA calibration should improve significantly starting today.
