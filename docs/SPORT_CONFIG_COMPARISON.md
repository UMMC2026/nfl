# 🏆 SPORT CONFIGURATION COMPARISON — AI Engineer Reference

> **Version**: 1.0 | **Generated**: 2026-02-05  
> **Purpose**: Technical comparison of all sport configurations, math models, and governance rules

---

## 📋 Table of Contents
1. [Executive Summary](#executive-summary)
2. [Tier Thresholds Comparison](#tier-thresholds-comparison)
3. [Probability Models by Sport](#probability-models-by-sport)
4. [Confidence Caps & Governance](#confidence-caps--governance)
5. [Data Sources & APIs](#data-sources--apis)
6. [Sport-Specific Hard Gates](#sport-specific-hard-gates)
7. [Why Each Sport Differs](#why-each-sport-differs)

---

## Executive Summary

| Sport | Status | SLAM? | Model | MC Iterations | Key Differentiator |
|-------|--------|-------|-------|---------------|-------------------|
| **NBA** | PRODUCTION | ✅ Yes (80%) | Gaussian + Neg-Binomial | 10,000 | Most calibrated, data-driven penalties |
| **NHL** | PRODUCTION v2.1 | ❌ Disabled | Poisson | 20,000 | Goalie confirmation mandatory |
| **Tennis** | PRODUCTION | ✅ Yes (82%) | Surface-adjusted MC | 10,000 | Surface-specific, Elo integration |
| **CBB** | PRODUCTION | ❌ Disabled | Poisson | 10,000 | Rotation volatility, no composites |
| **Golf** | PRODUCTION | ❌ Disabled | Gaussian + Elo | 10,000 | Course-fit SG weights |
| **Soccer** | RESEARCH | ✅ Yes (78%) | Poisson (goals) | 10,000 | Draw modeling required |
| **NFL** | FROZEN v1.0 | ✅ Yes (80%) | Gaussian | 10,000 | Weather/wind gates |

---

## Tier Thresholds Comparison

### Base Thresholds (NBA Standard)
```python
TIERS = {
    "SLAM":   0.80,   # ≥80% confidence
    "STRONG": 0.65,   # ≥65% confidence  
    "LEAN":   0.55,   # ≥55% confidence
    "SPEC":   0.50,   # ≥50% (research only)
    "AVOID":  0.00,   # No edge
}
```

### Sport-Specific Overrides

| Sport | SLAM | STRONG | LEAN | Why Different |
|-------|------|--------|------|---------------|
| **NBA** | 0.80 | 0.65 | 0.55 | Base reference — most calibration data |
| **NHL** | ❌ **None** | 0.64 | 0.58 | Goalie variance destroys high-confidence |
| **Tennis** | 0.82 | 0.68 | 0.58 | Single-elimination + surface variance |
| **CBB** | ❌ **None** | 0.70 | 0.60 | 350+ teams, massive rotation chaos |
| **Golf** | ❌ **None** | 0.65 | 0.55 | 156-player fields, weather variance |
| **Soccer** | 0.78 | 0.68 | 0.60 | Low-scoring + draw probability |
| **NFL** | 0.80 | 0.65 | 0.55 | Matches NBA (similar governance) |

### Visual: Why SLAM is Disabled

```
NBA:    ████████████████████ 80%+ achievable (high-usage stars consistent)
NHL:    ██████████████░░░░░░ Goalie variance kills confidence
CBB:    ██████████░░░░░░░░░░ 350 teams, freshmen, inconsistent minutes
Golf:   ████████░░░░░░░░░░░░ Field size (156), weather, course-fit
```

---

## Probability Models by Sport

### NBA — Gaussian + Negative Binomial Hybrid

```python
# Location: risk_first_analyzer.py
def monte_carlo_sim(mu, sigma, line, direction, trials=10000):
    """Gaussian Monte Carlo simulation"""
    samples = np.random.normal(mu, sigma, trials)
    if direction == "higher":
        return (samples > line).mean()
    return (samples < line).mean()

# For count stats (3PM, AST), use Negative Binomial
# Caps scipy r-parameter to prevent extreme near-Poisson cases
```

**Why Gaussian?**
- NBA player stats are continuous (points, rebounds)
- Large sample sizes (82 games/season)
- Normal distribution fits well with 10+ game samples

---

### NHL — Poisson Simulation

```python
# Location: sports/nhl/models/poisson_sim.py
# 20,000 simulations per matchup (higher than NBA due to variance)

TIERS = {
    "STRONG": (0.64, 0.67),
    "LEAN":   (0.58, 0.63),
    "NO_PLAY": (0.0, 0.579),
}

# SOG-specific tiers (slightly lower due to goalie dependency)
SOG_TIERS = {
    "STRONG": (0.62, 0.66),
    "LEAN":   (0.58, 0.61),
}
```

**Why Poisson?**
- Goals/SOG are count events (0, 1, 2, 3...)
- Low-scoring nature (avg 3 goals/team/game)
- Poisson models rare events better than Gaussian

---

### Tennis — Surface-Adjusted Monte Carlo

```python
# Location: tennis/calibrated_props_engine.py

STAT_CONFIDENCE_CAPS = {
    'aces': 70,
    'double_faults': 65,
    'games_won': 72,
    'total_games': 70,
    'sets_played': 65,
    'tiebreakers': 55,
}

# Surface multipliers affect serve stats
SURFACE_ADJUSTMENTS = {
    'HARD': 1.00,
    'CLAY': 0.85,  # Fewer aces on clay
    'GRASS': 1.15, # More aces on grass
}
```

**Why Surface Matters?**
- Serve speeds vary 20% between surfaces
- Break rates differ dramatically
- Historical splits are surface-dependent

---

### CBB — Poisson (NOT Gaussian)

```python
# Location: sports/cbb/models/probability.py
"""Uses Poisson/Negative Binomial instead of Normal.
Normal is FRAGILE for CBB's high variance."""

def poisson_probability(mean, line, direction):
    if direction == "higher":
        target = math.floor(line)
        prob = 1 - poisson_cdf(mean, target)
    else:
        target = math.ceil(line) - 1
        prob = poisson_cdf(mean, target)
    return prob

# Variance penalty: if std > mean * 0.6, cap at 70%
```

**Why NOT Gaussian?**
- College players have inconsistent minutes (coach decisions)
- Blowouts truncate stats
- Small samples (30 games vs NBA's 82)

---

### Golf — Gaussian + Course-Fit SG Weights

```python
# Location: golf/config/golf_config.py

SG_WEIGHTS_BY_COURSE_TYPE = {
    "LONG_BOMBERS_PARADISE": {"sg_ott": 0.35, "sg_approach": 0.30, "sg_putting": 0.35},
    "APPROACH_HEAVY": {"sg_ott": 0.20, "sg_approach": 0.45, "sg_putting": 0.35},
    "PUTTING_PREMIUM": {"sg_ott": 0.20, "sg_approach": 0.30, "sg_putting": 0.50},
}

GOLF_THRESHOLDS = {
    "SLAM": None,      # DISABLED
    "STRONG": 0.72,
    "LEAN": 0.60,
}

GOLF_CONFIDENCE_CAPS = {
    "outright": 0.45,      # Win/Top5 caps very low
    "make_cut": 0.85,      # Binary, more predictable
    "matchup_h2h": 0.72,
    "round_scoring": 0.62,
}
```

**Why Course-Fit?**
- TPC Scottsdale rewards bombers
- Harbour Town rewards precision
- SG categories must be weighted by course type

---

### Soccer — Poisson with Draw Modeling

```python
# Location: soccer/config.py

# Home advantage multiplier
HOME_ADV_FACTOR = 1.12

TIER_THRESHOLDS = {
    "SLAM": 0.78,
    "STRONG": 0.68,
    "LEAN": 0.60,
}

CONFIDENCE_CAPS = {
    "match_result": 0.72,  # 1X2 capped
    "over_under": 0.75,
    "btts": 0.72,
}
```

**Why Draw Matters?**
- ~25% of matches end in draws
- 1X2 markets require 3-way probability
- Cannot use binary higher/lower logic

---

## Confidence Caps & Governance

### NBA — Data-Driven Penalties (Most Sophisticated)

```python
# Location: config/data_driven_penalties.py
# Calibrated from 114 picks (Feb 1-3 data)

STAT_MULTIPLIERS_DATA_DRIVEN = {
    "ast":     1.20,   # 60% win rate → BOOST
    "3pm":     1.10,   # Slight boost
    "pts":     1.00,   # Neutral
    "pra":     1.00,   # Neutral base
    "pts+ast": 0.75,   # PENALTY
}

# Direction-specific combos
STAT_DIRECTION_COMBOS = {
    ("pra", "under"):  1.40,  # PRA UNDER = 70% historical!
    ("pra", "over"):   0.40,  # PRA OVER = 25% — AVOID
    ("3pm", "under"):  1.30,
    ("3pm", "over"):   0.80,
}

# Penalty caps (prevent over-penalization)
MAX_PENALTY_PERCENT = 25.0
MIN_CONFIDENCE_FLOOR = 50.0
```

---

### NHL — Goalie Confirmation Gate

```python
# Location: sports/nhl/nhl_menu.py

# MANDATORY GATE — Cannot bet saves without goalie confirmation
# ≥2 sources required (DailyFaceoff + Natural Stat Trick)

# Goalie-specific caps
B2B_GOALIE_PENALTY = -4%      # Back-to-back penalty
SMALL_SAMPLE_CAP = 0.58        # <5 starts → cap
BACKUP_GOALIE_CAP = 0.60       # Backup → cap

# Edge minimum
MIN_EDGE_PERCENT = 2.0
MIN_TOI_MINUTES = 12.0
MAX_CV_PERCENT = 45.0
```

---

### CBB — Composite Stat Ban

```python
# Location: sports/cbb/config.py

class CBBEdgeGates:
    # Ban composite stats initially (PRA, PR, PA)
    allow_composite_stats: bool = False
    
    # Minimum requirements
    min_minutes_avg: float = 20.0
    min_games_played: int = 5
    
    # Variance penalty
    variance_penalty_factor: float = 0.6
    variance_confidence_cap: float = 0.70
```

---

### Golf — Stat-Specific Caps

```python
# Location: golf/config/market_governance.py

GOLF_MARKETS = {
    "round_strokes":      {"status": "ENABLED", "max_confidence": 0.62},
    "finishing_position": {"status": "ENABLED", "max_confidence": 0.55},
    "birdies_or_better":  {"status": "ENABLED", "max_confidence": 0.65},
    "made_cut":           {"status": "ENABLED", "max_confidence": 0.85},
}
```

---

## Data Sources & APIs

| Sport | Primary Source | Backup | Refresh Cadence |
|-------|---------------|--------|-----------------|
| **NBA** | nba_api | ESPN | Every 6 hours |
| **NHL** | NHL API | NaturalStatTrick, DailyFaceoff | Every 4 hours |
| **Tennis** | Tennis Abstract (manual) | ATP/WTA stats | Daily |
| **CBB** | ESPN, SportsReference | — | Daily |
| **Golf** | DataGolf API | PrizePicks (manual) | Pre-tournament |
| **Soccer** | FBRef, Understat | ESPN | Daily |
| **NFL** | nflverse, nflreadpy | — | Weekly |

---

## Sport-Specific Hard Gates

### NBA Hard Gates
| Gate | Condition | Action |
|------|-----------|--------|
| Eligibility | prob < 55% | REJECTED |
| High Usage Volatility | CV > 40% | REJECTED |
| Bench Microwave | bench_min ≥ 80% + high CV | REJECTED for PTS/AST |
| Small Sample Matchup | matchup_games < 3 | prob × 0.85, VETTED |
| Big Man 3PM | C/PF + line ≥ 3.5 | Auto-reject |

### NHL Hard Gates
| Gate | Condition | Action |
|------|-----------|--------|
| Goalie Confirmation | <2 sources | BLOCKED |
| Back-to-Back | B2B goalie | -4% probability |
| Small Sample Goalie | <5 starts | Cap 58% |
| Backup Goalie | Not starter | Cap 60% |
| Min TOI | <12 min avg | BLOCKED |

### CBB Hard Gates
| Gate | Condition | Action |
|------|-----------|--------|
| SLAM Tier | Any | DISABLED (returns None) |
| Composite Stats | PRA, PR, PA | BLOCKED |
| Low Minutes | <20 min avg | BLOCKED |
| High Variance | std > mean × 0.6 | Cap 70% |
| Small Sample | <5 games | BLOCKED |

### Golf Hard Gates
| Gate | Condition | Action |
|------|-----------|--------|
| SLAM Tier | Any | DISABLED |
| Non-UI Stat | Not in ingest_schema_v1 | REJECTED at ingest |
| Cut Risk | <60% make-cut probability | Cap 55% |
| ShotLink Required | No strokes-gained data | RESEARCH_ONLY |

### Soccer Hard Gates
| Gate | Condition | Action |
|------|-----------|--------|
| League | Not in TIER_1/2/3 | BLOCKED |
| Team Matches | <20 matches | BLOCKED |
| Player Props | Goals, assists, shots | BLOCKED (v1.0) |

---

## Why Each Sport Differs

### 🏀 NBA — The Gold Standard
**Why most calibrated?**
- 82-game season = massive sample
- Player roles are stable (starters play 30+ min)
- Advanced stats available (usage rate, on/off splits)
- 114+ picks calibrated with data-driven penalties

**Unique Features:**
- Stat specialists (CATCH_AND_SHOOT_3PM, BIG_MAN_3PM)
- Direction-based multipliers (PRA UNDER = 1.40×)
- Hybrid tier override from context signals

---

### 🏒 NHL — Goalie Variance Dominates
**Why no SLAM?**
- Single goalie can swing game ±3 goals
- Backup announcements happen late (10 AM ET)
- Even elite goalies have 5-goal games

**Unique Features:**
- Mandatory 2-source goalie confirmation
- Poisson simulation (20k games)
- SOG has separate tiers from base

---

### 🎾 Tennis — Surface is Everything
**Why surface-specific?**
- Aces: 12 on grass → 4 on clay
- Break rates vary 40% by surface
- Bo3 vs Bo5 changes variance profile

**Unique Features:**
- Surface multipliers on serve stats
- Elo integration for matchup odds
- Correlation groups (can't parlay games_won + sets_played)

---

### 🏈 CBB — Chaos is the Norm
**Why no SLAM?**
- Freshman starters = unknown quantities
- Coach can pull star in blowout (10-min games happen)
- 350+ teams = impossible to model all

**Unique Features:**
- Poisson instead of Gaussian
- Composite stats BANNED
- 70%/60% thresholds (stricter than NBA)

---

### ⛳ Golf — Field Size Kills Confidence
**Why no SLAM?**
- 156 players = any can pop off
- Weather (AM/PM wave advantage)
- Course fit overrides recent form

**Unique Features:**
- SG weights by course type
- Outright cap at 45%
- Make-cut binary is most predictable (85% cap)

---

### ⚽ Soccer — Low-Scoring + Draws
**Why different?**
- Average 2.5 goals/game
- 25% of matches draw
- 1X2 requires 3-way probability

**Unique Features:**
- Home advantage factor (1.12×)
- Player props BLOCKED in v1.0
- Draw must be explicitly modeled

---

## 📁 Key File References

| Purpose | File Path |
|---------|-----------|
| Tier Thresholds (CANONICAL) | [config/thresholds.py](../config/thresholds.py) |
| NBA Data-Driven Penalties | [config/data_driven_penalties.py](../config/data_driven_penalties.py) |
| NBA Analysis Engine | [risk_first_analyzer.py](../risk_first_analyzer.py) |
| NHL Menu + Tiers | [sports/nhl/nhl_menu.py](../sports/nhl/nhl_menu.py) |
| Tennis Confidence Caps | [tennis/calibrated_props_engine.py](../tennis/calibrated_props_engine.py) |
| CBB Config | [sports/cbb/config.py](../sports/cbb/config.py) |
| Golf Market Governance | [golf/config/market_governance.py](../golf/config/market_governance.py) |
| Golf Ingest Schema v1 | [golf/config/ingest_schema_v1.py](../golf/config/ingest_schema_v1.py) |
| Soccer Config | [soccer/config.py](../soccer/config.py) |
| Sport Registry | [config/sport_registry.json](../config/sport_registry.json) |

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-05 | Initial comprehensive comparison |

---

*Generated for AI Engineer Reference — UNDERDOG ANALYSIS*
