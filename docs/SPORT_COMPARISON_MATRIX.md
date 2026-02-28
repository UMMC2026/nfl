# SPORT-BY-SPORT TECHNICAL COMPARISON MATRIX

**Quick Reference for AI Engineers**

---

## 📊 FEATURE COMPARISON TABLE

| Feature | NBA | Tennis | CBB | Soccer | Golf | NFL |
|---------|-----|--------|-----|--------|------|-----|
| **Status** | ✅ PROD | ✅ PROD | ✅ PROD | ✅ PROD | 🟡 DEV | 🔒 FROZEN |
| **Entry Point** | `daily_pipeline.py` | `tennis/run_daily.py` | `sports/cbb/run_daily.py` | `soccer/run_daily.py` | `golf/run_daily.py` | `run_autonomous.py` |
| **Lines of Code** | ~5000+ | ~1500 | ~1000 | ~2000 | ~1500 | ~500 |

---

## 🎯 TIER THRESHOLDS

| Tier | NBA | Tennis | CBB | Soccer | Golf | NFL |
|------|-----|--------|-----|--------|------|-----|
| SLAM | **80%** | **82%** | ❌ DISABLED | **78%** | ❌ DISABLED | 80% |
| STRONG | **65%** | **68%** | **70%** | **68%** | **72%** | 65% |
| LEAN | **55%** | **58%** | **60%** | **60%** | **60%** | 55% |
| Calibration Brier | <0.25 | <0.23 | <0.22 | <0.25 | <0.25 | <0.25 |

---

## 📈 STATISTICAL MODELS

| Component | NBA | Tennis | CBB | Soccer | Golf | NFL |
|-----------|-----|--------|-----|--------|------|-----|
| **Primary Distribution** | Normal | Structural | Normal | Poisson | Normal | Normal |
| **Secondary** | Poisson | ELO-gap | - | ZIP | Poisson | - |
| **Monte Carlo** | 10k sims | No | No | Yes | 10k sims | Yes |
| **Opponent Adjustment** | ❌ MISSING | ❌ MISSING | ❌ MISSING | ✅ YES | ✅ Course Fit | ❌ |
| **Position-Aware** | ❌ MISSING | N/A | ❌ MISSING | ✅ YES | ✅ SG Weights | ❌ |

---

## 🚫 BLOCKED FEATURES

| Sport | Blocked Stats/Markets | Reason |
|-------|----------------------|--------|
| NBA | None blocked, but caps on specialists | Volatility control |
| Tennis | Lines ≥36.5 with ELO gap >120 | Mismatch blowout |
| CBB | PRA, PR, PA, fantasy_points | Composite volatility |
| Soccer | Player props, corners, cards, SGP, live | v1.0 scope limit |
| Golf | None blocked | Markets self-limit via caps |
| NFL | N/A | Frozen |

---

## 🔧 GATES COMPARISON

| Gate Type | NBA | Tennis | CBB | Soccer | Golf | NFL |
|-----------|-----|--------|-----|--------|------|-----|
| Eligibility | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Schedule | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Roster | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Bias | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Render | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Specialist | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Stat Deviation | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Market Alignment | ✅ | ❌ | ✅ (12%) | ❌ | ❌ | ❌ |
| Derby/Context | ❌ | ❌ | ❌ | ✅ (8 gates) | ❌ | ❌ |

---

## 📊 DATA SOURCES

| Sport | Primary | Secondary | Manual Input |
|-------|---------|-----------|--------------|
| NBA | nba_api | ESPN | No |
| Tennis | Manual | ELO file | **YES** |
| CBB | sportsreference | ESPN | Partial |
| Soccer | Manual | fbref, understat | **YES** |
| Golf | Manual | DataGolf (limited) | **YES** |
| NFL | nflverse | nflreadpy | No |

---

## 🔴 CRITICAL GAPS BY SPORT

### NBA
```
1. No opponent defensive adjustment (DRTG not integrated)
2. Basic injury handling (binary only)
3. No travel/fatigue model
4. Same distribution for all positions
```

### Tennis
```
1. No head-to-head history database
2. No return game stats (only hold %)
3. No tournament depth fatigue
4. No retirement probability
```

### CBB
```
1. No conference strength adjustment
2. No tournament pressure context
3. No freshman volatility flags
4. No home court advantage scaling
```

### Soccer
```
1. Player props completely blocked
2. No live xG integration
3. No corner/card models
4. No SGP correlation engine
```

### Golf
```
1. No weather (wind is critical!)
2. No AM/PM wave advantage
3. No dynamic cut line projection
4. Limited historical course fit data
```

---

## 🏗️ ARCHITECTURE PATTERNS

### Mature (Copy These Patterns)
| Pattern | Location | Sport Origin |
|---------|----------|--------------|
| Pick State Machine | `core/decision_governance.py` | NBA |
| Data-Driven Penalties | `config/data_driven_penalties.py` | NBA |
| Opponent Adjustment | `soccer/soccer_opponent_adjustment.py` | Soccer |
| Match Context Filters | `soccer/soccer_match_context_filters.py` | Soccer |
| Distribution Selection | `soccer/soccer_distributions.py` | Soccer |
| Calibration Validator | `soccer/soccer_calibration_validator.py` | Soccer |

### Immature (Need Upgrades)
| Pattern | Gap | Priority |
|---------|-----|----------|
| Position-Aware Stats | Only Soccer has it | HIGH |
| Weather Integration | Only Golf partially | MEDIUM |
| Head-to-Head History | No sport has full H2H | HIGH |
| Injury Severity | All sports binary only | HIGH |

---

## 🚀 UPGRADE IMPLEMENTATION ORDER

### Phase 1: Port Soccer Patterns (1-2 weeks)
```python
# Port to NBA, CBB, Tennis, Golf:
from soccer.soccer_opponent_adjustment import OpponentAdjustmentEngine
from soccer.soccer_match_context_filters import MatchContextFilterEngine
from soccer.soccer_distributions import SoccerDistributions
```

### Phase 2: Add Missing Features (2-4 weeks)
```
- NBA: Add team DRTG integration
- Tennis: Build H2H database
- CBB: Add conference strength
- Golf: Add weather model
```

### Phase 3: Calibration Validation (Ongoing)
```
- Track Brier scores by sport
- Adjust thresholds based on performance
- Paper trade all upgrades before production
```

---

## 📋 QUICK COMMANDS

```bash
# NBA (Primary)
.venv\Scripts\python.exe daily_pipeline.py

# Tennis (Surface REQUIRED)
.venv\Scripts\python.exe tennis/run_daily.py --surface HARD

# CBB
.venv\Scripts\python.exe sports/cbb/run_daily.py --dry-run

# Soccer
.venv\Scripts\python.exe soccer/run_daily.py

# Golf
.venv\Scripts\python.exe golf/run_daily.py --dry-run

# NFL (READ-ONLY)
.venv\Scripts\python.exe run_autonomous.py

# Calibration Report
.venv\Scripts\python.exe calibration/unified_tracker.py --report --sport nba
```

---

## 🔒 GOVERNANCE RULES (ALL SPORTS)

1. **NEVER** hardcode tier thresholds — import from `config/thresholds.py`
2. **ALWAYS** call eligibility gate before Monte Carlo
3. **NEVER** let LLMs override MC probabilities
4. **ALWAYS** track picks in calibration system
5. **NEVER** modify NFL (frozen v1.0)
6. **ALWAYS** use "data suggests" language, never "bet this"

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-02-01  
**For**: AI Engineer Review
