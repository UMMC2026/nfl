# 📋 SOP: DUAL-DOMAIN ACCURACY MODEL
## Formal Decision Tree & Deployment Rules

**Effective Date:** January 1, 2026  
**Status:** Locked & Operational  
**Version:** 1.0

---

## 🎯 EXECUTIVE SUMMARY

This system recognizes that **betting edge exists in two independent domains**:
1. **Domain 1 (Statistical Value):** Is the market mispriced? (μ vs line)
2. **Domain 2 (Regime Probability):** Will this hit in the current context? (confidence %)

**Core insight:** A play can be strong in one domain and weak in the other. Both are valid. Use both.

---

## 📊 DOMAIN 1: STATISTICAL VALUE (μ vs Line)

### Definition
The gap between a player's expected production (μ, per-game average) and the offered line.

### Validation Gate
```
IF μ < lower_bound OR μ > upper_bound THEN
  → DISCARD from value analysis
  → Flag as DATA_CORRUPT
  → Do NOT use for edge calculation

Valid ranges (per-game):
  Points: 5–35
  Rebounds: 2–16
  Assists: 1–12
  3-Pointers: 0–10
  Combo (PRA): 10–60
  Combo (PR, PA, RA): 8–50, 8–45, 3–28
```

### Red Flags (Auto-Reject)
- μ > 1000 (indicates career total or aggregation error)
- μ < 0 (impossible)
- μ line-agnostic (doesn't vary with line; data corruption)
- Multiple conflicting μ for same prop (Sengun PTS: 21 vs 20.5 with different μ values)

### Edge Calculation
```
μ_gap = μ - line

If μ_gap >= 3.0: VALUE_EDGE = TRUE (underpriced)
If μ_gap <= -3.0: FADE (overpriced)
If -3.0 < μ_gap < 3.0: EVEN (no edge)
```

### Output: Domain 1 Status
- ✅ **VALID_EDGE:** Clean data + gap ≥ 3pt
- ⚠️ **VALID_EVEN:** Clean data + gap < 3pt
- ❌ **DATA_CORRUPT:** μ outside valid range or impossible value

---

## 🎯 DOMAIN 2: REGIME PROBABILITY (Confidence %)

### Definition
Hit rate under current conditions: minutes, usage, matchup, rest, hot streak, role stability.

### Validation Gate
```
IF confidence < 50% OR confidence > 85% THEN
  → Flag as OUT_OF_RANGE
  → Manual review required

Valid range: 50–85%
  SLAM: 68–75%
  STRONG: 60–67%
  LEAN: 52–59%
```

### Inputs to Confidence
- Recent sample (3+ games trending)
- Minutes/usage stability
- Matchup fit (favorable vs difficult)
- Rest status (2+ days, 1 day, B2B)
- Hot streak (recent 4-game trend)
- Role clarity (starter, deep bench, unclear)

### Output: Domain 2 Status
- ✅ **CONVICTION:** Confidence ≥ 60%
- ⚠️ **MARGINAL:** Confidence 50–59%
- ❌ **WEAK:** Confidence < 50% or insufficient sample

---

## 🏆 PLAY CLASSIFICATION (4 Categories)

### 1. 🎯 HYBRID (Highest Priority)
**Both domains strong**
- Domain 1: Valid data + gap ≥ 3pt
- Domain 2: Confidence ≥ 60%

**Example:** Keyonte George O25.5
- μ = 26.5, line = 25.5 → +1.0pt gap (marginal by value)
- Confidence = 75% (SLAM)
- **Classification:** HYBRID (conviction dominates)

**Deployment:** Max this play. Lowest variance, highest reliability.

---

### 2. 🔒 CONVICTION (Primary Core)
**Domain 2 strong, Domain 1 weak or invalid**
- Domain 2: Confidence ≥ 60%
- Domain 1: Bad data OR small gap OR N/A

**Example:** Jalen Duren REB O10.5
- μ data missing/unreliable
- Confidence = 65% (STRONG)
- **Classification:** CONVICTION

**Deployment:** Use as core play. High hit rate despite no value edge signal.

---

### 3. 💎 VALUE (Secondary Tactical)
**Domain 1 strong, Domain 2 weak**
- Domain 1: Valid data + gap ≥ 3pt
- Domain 2: Confidence < 60% OR insufficient sample

**Example:** Jaden Ivey O10.5
- μ = 15.6, line = 10.5 → +5.1pt gap (strong value)
- Confidence = ~55% (estimated, unrated)
- **Classification:** VALUE

**Deployment:** Add if μ is verified. Higher variance but positive expected value.

---

### 4. ❌ REJECT (Do Not Deploy)
**Both domains weak**
- Domain 1: Data corrupt (μ outside range) OR gap < 3pt
- Domain 2: Confidence < 50% OR insufficient sample

**Example:** Kevin Durant PRA O37.5
- μ = 988.3 (DATA CORRUPT)
- Confidence = N/A
- **Classification:** REJECT

**Deployment:** Never touch. Wait for clean data.

---

## 📋 DECISION TREE (For Each Pick)

```
START: Evaluate new prop

Step 1: Does μ data exist?
  YES → Step 2
  NO  → Go to Step 4 (Domain 2 only)

Step 2: Validate μ (sanity check)
  IN_RANGE (5-35 for points, etc.)? 
    YES → Step 3
    NO  → REJECT (data corrupt)

Step 3: Calculate μ_gap
  gap = μ - line
  gap ≥ 3.0?
    YES → VALUE_EDGE = TRUE → Step 4
    NO  → VALUE_EDGE = FALSE → Step 4

Step 4: Get confidence %
  confidence ≥ 60%?
    YES → CONVICTION = TRUE
    NO  → CONVICTION = FALSE

Step 5: Classify

  IF VALUE_EDGE AND CONVICTION
    → CLASSIFY: HYBRID ✅
  ELSE IF CONVICTION (not VALUE_EDGE)
    → CLASSIFY: CONVICTION ✅
  ELSE IF VALUE_EDGE (not CONVICTION)
    → CLASSIFY: VALUE ⚠️
  ELSE
    → CLASSIFY: REJECT ❌

END: Output classification + reasoning
```

---

## 💰 CAPITAL ALLOCATION RULES

### Bankroll Split (Per Slate)

```
Core Plays (70%):        CONVICTION + HYBRID
  ↳ Established hit rate, high reliability
  ↳ Deploy maximum confidence

Additive Plays (20%):    VALUE (if μ verified)
  ↳ Statistical edge detected
  ↳ Lower conviction, higher variance
  ↳ Only if data passes μ sanity check

Contrarian (10%):        Unrated stars, speculative
  ↳ Extended slate opportunities
  ↳ No regime sample yet
  ↳ Play only if odds are exceptional
```

### Bet Sizing Rules
- **HYBRID:** 2x-3x base unit (lowest variance)
- **CONVICTION:** 2x base unit (high hit rate)
- **VALUE:** 1.5x base unit (high variance but +EV)
- **REJECT:** 0 units (never bet)

---

## 🔄 NIGHTLY VALIDATION CHECKLIST

Before sending picks to Telegram, execute this checklist:

- [ ] **Data Quality:** All props have either valid μ or recent regime sample
- [ ] **μ Sanity:** No μ > 100 (indicates aggregation error)
- [ ] **Confidence Range:** All confidence values 50–85%
- [ ] **Classification:** Each pick labeled CONVICTION/VALUE/HYBRID/REJECT
- [ ] **Reject Count:** Flag if > 10% of slate is REJECT (indicates bad data day)
- [ ] **Correlation Warning:** Identify all stacked players and assess correlation
- [ ] **Parlay Math:** Verify combined probabilities add up (no >100% combos)
- [ ] **Telegram Ready:** Domain labels shown in messages (🎯 HYBRID, 🔒 CONVICTION, 💎 VALUE, ❌ REJECT)

---

## 📊 MEASUREMENT & AUDIT (Monthly)

Track hit rates by domain:

```
Domain 1 Accuracy (VALUE plays):
  Track: μ_gap vs actual outcome
  Target: If gap ≥ 3pt, should hit 55-60% of time
  Audit: Are μ values predictive? Or stale?

Domain 2 Accuracy (CONVICTION plays):
  Track: Confidence % vs actual outcome
  Target: 75% SLAM should hit 70–80% of time
  Audit: Is regime detection accurate? Role changes?

HYBRID Accuracy:
  Track: Both domains together
  Target: Should hit 65–75% (blended)
  Audit: Best overall predictor?
```

---

## ⚠️ SPECIAL CASES

### Case 1: Missing μ Data
**Resolution:** Use Domain 2 only (classify as CONVICTION if confidence ≥ 60%)

### Case 2: Conflicting μ Values
**Example:** Sengun PTS has two lines (21 vs 20.5) with different μ values  
**Resolution:** REJECT both. Wait for data cleanup. Do not guess which is correct.

### Case 3: Unrated Star (No Regime Sample Yet)
**Resolution:** Value plays only (if μ is clean). Never CONVICTION without sample.

### Case 4: High Variance Player (σ > 8)
**Resolution:** VALUE edge must be > 3pt to overcome volatility. Mark as HIGH_VARIANCE in notes.

### Case 5: Data Corruption Detected Mid-Game
**Resolution:** 
1. Flag player as corrupted
2. Remove from Telegram push (don't re-send)
3. Add to "wait for cleanup" list
4. Manual review before next slate

---

## 🎯 TONIGHT'S SLATE (Jan 1, 2026 Validation)

### SLAM Tier (Deploy with Confidence)
- **Keyonte George O25.5** → HYBRID (75% conviction + verified volume)
- **Lauri Markkanen O26.5** → HYBRID (72% conviction + hot streak)

### STRONG Tier (Core Plays)
- **Jalen Duren REB O10.5** → CONVICTION (65% confidence, μ clean)
- **Bam Adebayo PTS+REB+AST O27.5** → CONVICTION (65% confidence, verify μ completeness)
- **Alperen Sengun PTS O20.5** → ⚠️ REVIEW (conflicting lines, needs data cleanup)

### VALUE Plays (Secondary)
- **Jaden Ivey O10.5** → VALUE (μ=15.6, +5.1pt edge, if verified)
- **Terance Mann O6.5** → VALUE (μ=9.7, +3.2pt edge, unrated)
- **PJ Washington O12.5** → VALUE (μ=17.9, +5.4pt edge, unrated)

### LEAN Tier (REJECT or VALUE-only)
- **Embiid PTS O23.5** → REJECT (conflict: our 57% but your μ suggests 60%+, data unclear)

### Unrated (Extended Slate)
- **Cooper Flagg** → Monitor 1Q plays (1.05x edges noted)
- **Raynaud 3P O0.5** → VALUE (1.34x edge, highest value outlier)

---

## ✅ FINAL SOP LOCK-IN

This framework is now **non-negotiable operational standard**:

1. ✅ Every prop gets a domain classification
2. ✅ Every classification has documented reasoning
3. ✅ Every telegram message shows domain label
4. ✅ Every reject is flagged with specific error
5. ✅ Monthly audit compares Domain 1 vs Domain 2 hit rates
6. ✅ Capital allocated by domain strength

**No ambiguity. No exceptions. No gut calls without domain justification.**

---

**Approved & Locked:** Jan 1, 2026
