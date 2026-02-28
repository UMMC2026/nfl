# STAT COMBO BOOSTS & PENALTIES — Data-Driven Calibration Reference

> **Version**: 1.0  
> **Created**: 2026-02-05  
> **Author**: AI Engineer Review Implementation  
> **Source**: 97-pick calibration analysis + historical win rates

---

## Overview

This document provides the **canonical reference** for stat-specific multipliers derived from calibration data. These multipliers adjust raw probabilities based on historical performance by stat type, direction, and combination.

**Key Principle**: Not all 60% probabilities are equal. A 60% AST UNDER hits differently than a 60% PTS OVER.

---

## 🔢 Base Multipliers (from `config/data_driven_penalties.py`)

### Stat-Specific Multipliers

| Stat | Multiplier | Win Rate | Note |
|------|-----------|----------|------|
| **AST** | **1.20** | 60%+ | BOOST — Assists UNDER historically outperforms |
| **3PM** | **1.06** | 54% | Slight boost |
| PTS | 1.00 | 50% | Neutral — well-calibrated |
| REB | 1.00 | 50% | Neutral — well-calibrated |
| PRA | 1.00 | 52% | Neutral on aggregate (but direction matters!) |
| PTS+AST | **0.75** | 42% | PENALTY — combo underperforms |
| REB+AST | **0.75** | 41% | PENALTY — combo underperforms |
| PTS+REB | 0.90 | 47% | Slight penalty |

### Direction Multipliers (Critical!)

| Direction | Multiplier | Win Rate | Note |
|-----------|-----------|----------|------|
| **LOWER/UNDER** | **1.03** | 53% | UNDERs slightly outperform |
| HIGHER/OVER | 0.94 | 47% | OVERs slightly underperform |

### PRA Direction (Best Edge in System!)

| Direction | Multiplier | Win Rate | Note |
|-----------|-----------|----------|------|
| **PRA LOWER** | **1.40** | **70%** | 🔥 STRONGEST EDGE — Calendar Q4 2025 |
| PRA HIGHER | 0.50 | 25% | ⚠️ AVOID — Underperforms significantly |

---

## 📊 Composite Multiplier Calculation

When multiple conditions apply, multiply together:

```python
final_multiplier = stat_multiplier × direction_multiplier × archetype_multiplier

# Example: LeBron James, AST UNDER
# = 1.20 (AST) × 1.03 (UNDER) × 1.00 (STAR_STARTER archetype)
# = 1.236 → 23.6% boost to raw probability
```

### Caps Applied

```python
MAX_PENALTY_PERCENT = 25.0   # Maximum penalty (floor: 75% of raw)
MIN_CONFIDENCE_FLOOR = 50.0  # Never go below 50% confidence
MAX_BOOST_PERCENT = 40.0     # Maximum boost (ceiling: 140% of raw)
```

---

## 🏀 NBA-Specific Stat Combos

### Overperformers (Boost)

| Combo | Historical Win Rate | Recommended Action |
|-------|--------------------|--------------------|
| AST UNDER + Starter | 62% | Boost 15-20% |
| 3PM OVER + Sniper Archetype | 58% | Boost 8-10% |
| REB UNDER + Small Ball | 56% | Boost 5-8% |
| PRA LOWER + High Usage | 70% | Boost 35-40% |

### Underperformers (Penalty)

| Combo | Historical Win Rate | Recommended Action |
|-------|--------------------|--------------------|
| PTS+AST (any direction) | 42% | Penalty 20-25% |
| REB+AST (any direction) | 41% | Penalty 20-25% |
| PRA HIGHER (any player) | 25% | Penalty 45-50% |
| 3PM + Center/PF | 38% | Penalty 15-20% |

---

## 🎾 Tennis Stat Combos

### Total Games Props

| Condition | Multiplier | Note |
|-----------|-----------|------|
| Best-of-5 OVER | 1.08 | More games = more variance, but overs hit |
| Best-of-3 close matchup | 1.05 | Even matchups go to 3 sets |
| Surface mismatch (clay specialist on hard) | 0.90 | Player may underperform |

### Aces Props

| Condition | Multiplier | Note |
|-----------|-----------|------|
| Serve specialist OVER | 1.15 | Big servers deliver |
| Short match expected UNDER | 1.10 | Fewer games = fewer aces |

---

## 🏒 NHL Stat Combos

### Saves Props

| Condition | Multiplier | Note |
|-----------|-----------|------|
| Backup goalie | 0.85 | Cap confidence 60% |
| B2B game | 0.92 | -4% penalty for tired goalies |
| Confirmed starter | 1.05 | Confirmation boost |

### SOG (Shots on Goal)

| Condition | Multiplier | Note |
|-----------|-----------|------|
| Against backup goalie | 1.08 | More shots vs weak goalies |
| PP time leader | 1.10 | PP1 players get more looks |

---

## ⛳ Golf Stat Combos

### Round Strokes

| Condition | Multiplier | Note |
|-----------|-----------|------|
| Course history fit | 1.15 | SG-specific course fit |
| Weather wave disadvantage | 0.90 | Morning/afternoon tee time bias |
| Cut line risk (< 60% make cut) | 0.85 | Cap confidence 55% |

---

## 🏈 NFL Stat Combos

### Passing Props

| Condition | Multiplier | Note |
|-----------|-----------|------|
| Wind > 15 mph | 0.90 | Passing capped at 60% |
| Dome game | 1.05 | Controlled environment |
| Backup QB | 0.75 | High variance |

### Rushing Props

| Condition | Multiplier | Note |
|-----------|-----------|------|
| RB1 vs weak run D | 1.12 | Volume + efficiency |
| Game script (trailing) | 0.85 | Abandonment risk |

---

## 🔧 Implementation Pattern

```python
from config.data_driven_penalties import (
    STAT_MULTIPLIERS,
    DIRECTION_MULTIPLIERS,
    PRA_DIRECTION_MULTIPLIERS,
    apply_calibration_adjustment,
)

# Apply to edge calculation:
raw_probability = 0.62
stat = "AST"
direction = "lower"

adjusted = apply_calibration_adjustment(
    probability=raw_probability,
    stat=stat,
    direction=direction,
)
# Returns boosted probability (e.g., 0.62 * 1.20 * 1.03 = 0.767)
```

---

## 📈 Calibration Update Schedule

| Interval | Action |
|----------|--------|
| Weekly | Review segment-level calibration (`calibration/segmented_tracker.py`) |
| Monthly | Update multipliers if drift > 5% |
| Quarterly | Full recalibration with new data |

---

## ⚠️ Known Issues (2026-02-05)

1. **PRA HIGHER severely miscalibrated** — Only 25% win rate vs expected 60%+
   - Recommendation: Hard-block PRA HIGHER or cap at 50%
   
2. **Combo stats (PTS+AST, REB+AST) underperform** — ~42% win rate
   - Recommendation: Apply 25% penalty or downgrade tier
   
3. **3PM for Big Men** — 38% win rate
   - Recommendation: BIG_MAN_3PM cap at 62%, auto-reject at line 3.5+

---

## References

- `config/data_driven_penalties.py` — Multiplier source code
- `calibration/segmented_tracker.py` — Segment-level tracking
- `calibration/unified_tracker.py` — Aggregate calibration
- `calibration_history.csv` — Raw calibration data

---

*Last updated by AI Engineer implementation sprint, 2026-02-05*
