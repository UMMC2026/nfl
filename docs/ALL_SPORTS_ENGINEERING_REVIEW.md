# UNDERDOG ANALYSIS — ALL SPORTS ENGINEERING REVIEW

**Generated**: 2026-02-01  
**Purpose**: AI Engineer Review & Upgrade Planning  
**System Version**: Multi-Sport v1.0

---

## 📋 TABLE OF CONTENTS

1. [System Architecture Overview](#system-architecture-overview)
2. [NBA (Primary Sport)](#1-nba-primary-sport)
3. [Tennis](#2-tennis)
4. [College Basketball (CBB)](#3-college-basketball-cbb)
5. [Soccer](#4-soccer)
6. [Golf](#5-golf)
7. [NFL (Frozen)](#6-nfl-frozen)
8. [Cross-Sport Infrastructure](#cross-sport-infrastructure)
9. [Upgrade Opportunities](#upgrade-opportunities)
10. [Priority Matrix](#priority-matrix)

---

## SYSTEM ARCHITECTURE OVERVIEW

### Three-Layer Design Pattern
```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 3: RENDER                                   │
│  Reports, Telegram, Professional Output                              │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 2: LLM ADAPTERS                            │
│  Evidence interpretation (EvidenceBundle), NO probability override   │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 1: TRUTH ENGINE                            │
│  Immutable probabilities, Monte Carlo simulations, Governance        │
└─────────────────────────────────────────────────────────────────────┘
```

### Pick State Machine (ALL SPORTS)
```
RAW → ADJUSTED → VETTED → OPTIMIZABLE
                    ↓           ↓
               REJECTED     REJECTED

States:
- RAW: Parsed, not analyzed
- ADJUSTED: Probability computed
- VETTED: Visible but NOT optimizable (context only)
- OPTIMIZABLE: Allowed into Monte Carlo
- REJECTED: Hidden from all outputs
```

### Canonical Threshold Import
```python
# ALL modules MUST use:
from config.thresholds import TIERS, SPORT_TIER_OVERRIDES, get_tier_threshold

# NEVER hardcode thresholds
```

---

## 1. NBA (PRIMARY SPORT)

### Status: ✅ PRODUCTION (Flagship)

### File Structure
```
├── risk_first_analyzer.py          # Main analysis engine (2614 lines)
├── daily_pipeline.py               # Entry point
├── core/
│   ├── decision_governance.py      # Pick state machine (672 lines)
│   ├── stat_specialist_engine.py   # Specialist classification (348 lines)
│   ├── shot_profile_archetypes.py  # 3PM governors
│   ├── hybrid_confidence.py        # Confidence calculation
│   └── stat_deviation_gate.py      # Coin-flip detection (NEW)
├── config/
│   ├── thresholds.py               # CANONICAL tier source (298 lines)
│   ├── data_driven_penalties.py    # Calibration multipliers (235 lines)
│   └── penalty_mode.json           # Penalty mode switch
├── nba/
│   └── stat_specialists.py         # NBA-specific specialist types
└── calibration/
    ├── unified_tracker.py          # Result tracking
    └── calibration_history.csv     # Historical picks
```

### Tier Thresholds
| Tier | Threshold | Notes |
|------|-----------|-------|
| SLAM | 80% | Highest confidence |
| STRONG | 65% | Reliable edge |
| LEAN | 55% | Minimum playable |
| SPEC | 50% | Research only |
| AVOID | <50% | No edge |

### Statistical Distributions
- **Primary**: Normal distribution with Poisson fallback for counting stats
- **Formula**: `P(X > line) = 1 - CDF(line | μ, σ)`

### Specialist System (2nd-Axis Archetype)
```python
class StatSpecialist(Enum):
    CATCH_AND_SHOOT_3PM = "CATCH_AND_SHOOT_3PM"   # Cap: 70%
    BIG_MAN_3PM = "BIG_MAN_3PM"                   # Cap: 62% (CRITICAL)
    MIDRANGE_SPECIALIST = "MIDRANGE_SPECIALIST"   # Cap: 60%
    BIG_POST_SCORER = "BIG_POST_SCORER"           # Cap: 63%
    RIM_RUNNER = "RIM_RUNNER"                     # Cap: 65%
    PASS_FIRST_CREATOR = "PASS_FIRST_CREATOR"     # Cap: 68%
    OFF_DRIBBLE_SCORER = "OFF_DRIBBLE_SCORER"     # Cap: 58%
    BENCH_MICROWAVE = "BENCH_MICROWAVE"           # Cap: 55%
    GENERIC = "GENERIC"                           # Cap: 65%
```

### Data-Driven Penalties (97-Pick Calibration)
```python
# PROFITABLE (BOOST)
"ast": 1.20           # 60% win rate
"3pm": 1.06           # 53.3% win rate

# BREAK-EVEN (NEUTRAL)
"pts": 1.00
"reb": 1.00
"pra": 1.00

# LOSING (PENALIZE)
"pts+ast": 0.75       # 37.5% win rate
"reb+ast": 0.75

# DIRECTION COMBOS (CRITICAL)
("pra", "lower"): 1.40    # 70% win rate - BEST EDGE
("pra", "higher"): 0.50   # 25% win rate - AVOID
```

### Gates
1. **Eligibility Gate** - `core/decision_governance.py`
2. **Schedule Gate** - Games today check
3. **Roster Gate** - Active roster validation
4. **Bias Gate** - Directional balance (≤70%)
5. **Render Gate** - Output validation
6. **Stat Deviation Gate (NEW)** - Coin-flip detection

### Key Metrics
- **Calibration**: Brier threshold <0.25
- **Sample**: 97+ tracked picks
- **Calibration Data**: `calibration_history.csv`

### 🔴 GAPS / UPGRADE OPPORTUNITIES
1. **Missing Opponent Adjustment Engine** — No systematic defensive rating integration
2. **No Position-Aware Distribution Selection** — Uses same distribution for guards/centers
3. **Limited Injury Context** — Binary (active/inactive) only
4. **No Weather/Travel Fatigue** — Back-to-back handling is basic
5. **Monte Carlo Needs Upgrade** — Currently 10k sims, could benefit from variance reduction

---

## 2. TENNIS

### Status: ✅ PRODUCTION

### File Structure
```
tennis/
├── run_daily.py                    # Entry point (279 lines)
├── engines/
│   ├── generate_totals_games_edges.py   # Total games engine (639 lines)
│   ├── generate_totals_sets_edges.py    # Total sets engine
│   ├── generate_player_aces_edges.py    # Player aces engine
│   └── total_sets_engine_v1.py          # Legacy
├── config/
│   └── totals_games.json           # Engine config
├── ingest/
│   └── ingest_tennis.py            # Data loading
├── validate/
│   └── validate_tennis_output.py   # Output validation
└── render/
    └── render_report.py            # Report generation
```

### Tier Thresholds (Tennis-Specific Override)
| Tier | Threshold | Notes |
|------|-----------|-------|
| SLAM | 82% | Higher due to variance |
| STRONG | 68% | |
| LEAN | 58% | |

### Markets Supported
1. **TOTAL_GAMES** - Match total games over/under
2. **TOTAL_SETS** - Match total sets (Bo3/Bo5)
3. **PLAYER_ACES** - Individual player aces

### Statistical Model
```python
# Surface baselines for total games
SURFACE_BASELINES = {
    "HARD": 9.9,
    "CLAY": 9.5,
    "GRASS": 10.8,
    "INDOOR": 10.5,
}

# ELO-based mismatch detection
# Formula: expected_sets * expected_games_per_set
# Adjustments: tiebreak_prob * 1.2 - blowout_risk * 1.5
```

### Key Features
- **ELO System** - `player_elo.json` tracks ratings
- **Surface Awareness** - Mandatory surface parameter
- **Hold Percentage** - Service game dominance factor
- **Best-of Detection** - Bo3 vs Bo5 handling

### Block Rules
```json
{
  "games_line_gte_36_5_and_elo_gap_gt_120": true,
  "games_line_gte_36_5_and_hold_pct_lt_78": true
}
```

### 🔴 GAPS / UPGRADE OPPORTUNITIES
1. **No Live H2H Data** — ELO is generic, not opponent-specific
2. **Missing Return Game Stats** — Only hold %, no break %
3. **No Fatigue Modeling** — Tournament depth not factored
4. **Limited Historical Data** — Manual input reliance
5. **No Set-by-Set Simulation** — Aggregate only
6. **Missing Retirement Risk** — Player injury/retirement probability

---

## 3. COLLEGE BASKETBALL (CBB)

### Status: ✅ PRODUCTION (Activated 2026-01-24)

### File Structure
```
sports/cbb/
├── run_daily.py                    # Entry point (201 lines)
├── config.py                       # CBB-specific config (270 lines)
├── ingest/
│   └── player_stats.py             # Stats ingestion
├── features/                       # Feature engineering
├── edges/                          # Edge generation
├── models/                         # Probability computation
├── validate/                       # Output validation
├── render/                         # Report generation
└── docs/
    └── README.md                   # CBB documentation
```

### Tier Thresholds (CBB-Specific — STRICTER)
| Tier | Threshold | Notes |
|------|-----------|-------|
| SLAM | **DISABLED** | Too volatile |
| STRONG | 70% | Stricter than NBA (65%) |
| LEAN | 60% | Stricter than NBA (55%) |

### Key Differences from NBA
```python
# CBB ≠ NBA
- 350+ teams with massive rotation volatility
- Inconsistent pace & minutes
- Market lines are softer but noisier

# L10 Blend Weight (aligned with NBA Tier 1 fix)
L10_BLEND_WEIGHT = 0.40  # 40% recent, 60% stable

# Market Alignment Threshold
MARKET_ALIGNMENT_THRESHOLD = 12.0  # Reduced from 15%
```

### Confidence Caps (Stricter)
```python
CONFIDENCE_CAPS = {
    "core": 0.70,           # PTS, REB, AST
    "volume_micro": 0.65,   # FGA, FTA
    "event_binary": 0.55,   # Blocks, steals
}
```

### Edge Gates
```python
@dataclass
class CBBEdgeGates:
    min_minutes_avg: float = 20.0
    allow_composite_stats: bool = False  # BANNED (PRA, PR, PA)
    block_under_low_minutes: bool = True
    max_blowout_probability: float = 0.25
    min_games_played: int = 5
    variance_penalty_factor: float = 0.6
```

### Blocked Stats (Phase 1)
```python
BLOCKED_STATS = [
    "pts+reb",
    "pts+ast",
    "pts+reb+ast",
    "reb+ast",
    "fantasy_points",
]
```

### 🔴 GAPS / UPGRADE OPPORTUNITIES
1. **No Conference Strength Adjustment** — Big Ten vs Mid-Major not differentiated
2. **Missing Tournament Context** — Conference/NCAA tournament pressure
3. **No Freshman Volatility Flags** — First-year players highly variable
4. **Limited Home Court Advantage** — CBB has stronger HCA than NBA
5. **No Travel/Schedule Density** — Multiple games per week untracked
6. **Preflight Cache Only** — No warm cache strategy

---

## 4. SOCCER

### Status: ✅ PRODUCTION (v1.0)

### File Structure
```
soccer/
├── run_daily.py                    # Entry point (372 lines)
├── config.py                       # Soccer config (137 lines)
├── SOCCER_SYSTEM_README.md         # Full documentation
├── soccer_opponent_adjustment.py   # Opponent-adjusted lambda (NEW)
├── soccer_match_context_filters.py # 8 filter gates (NEW)
├── soccer_distributions.py         # 4 distribution types (NEW)
├── soccer_calibration_validator.py # Calibration tracking (NEW)
├── soccer_pipeline_integration.py  # Full pipeline (NEW)
├── gates/
│   └── soccer_gates.py             # Hard governance gates
├── models/
│   └── dr_soccer_bayes.py          # Lambda estimation
├── sim/
│   └── soccer_sim.py               # Scoreline simulation
└── render/
    └── render_soccer_report.py     # Report generation
```

### Enabled Leagues
```python
LEAGUE_TIERS = {
    "TIER_1": ["EPL", "UCL", "UEL"],
    "TIER_2": ["LALIGA", "BUNDESLIGA", "SERIE_A", "LIGUE_1"],
    "TIER_3": ["MLS", "WORLD_CUP", "EUROS", "COPA_AMERICA"],
}
ENABLED_LEAGUES = LEAGUE_TIERS["TIER_1"]  # v1.0 limit
```

### Tier Thresholds
| Tier | Threshold | Notes |
|------|-----------|-------|
| SLAM | 78% | |
| STRONG | 68% | |
| LEAN | 60% | |

### Confidence Caps
```python
GLOBAL_CONFIDENCE_CAP = 0.78
CONFIDENCE_CAPS = {
    "match_result": 0.72,
    "over_under": 0.75,
    "btts": 0.72,
    "team_total": 0.70,
    "asian_handicap": 0.72,
}
```

### Markets (v1.0 — Team Only)
```python
APPROVED_MARKETS = [
    "match_result",     # 1X2
    "asian_handicap",
    "over_under",       # totals
    "btts",             # Both Teams To Score
    "team_total",
]

BLOCKED_MARKETS = [
    "player_goals",
    "player_shots",
    "player_assists",
    "corners",
    "cards",
    "sgp",
    "live",
]
```

### NEW: Opponent Adjustment Engine
```python
# Defensive rank → multiplier
DEFENSE_ADJUSTMENT = {
    "elite": 0.65,      # Top 5 defense
    "good": 0.85,
    "average": 1.00,
    "poor": 1.15,
    "terrible": 1.25,   # Bottom 5 defense
}

# Position-aware distribution selection
- Striker: Poisson (low-count events)
- Midfielder: Normal
- Defender (goals/assists): Zero-Inflated Poisson
```

### NEW: Match Context Filters (8 Gates)
| Gate | Blocks When |
|------|-------------|
| Derby | Local rivalry match |
| Rotation Risk | UCL/UEL midweek sandwiches |
| Injury Return | Player back from 3+ week absence |
| Blowout Risk | >3 goal expected margin |
| Manager Change | New manager <5 matches |
| Competition | Non-enabled league |
| Venue | Neutral venue/relocation |
| Minutes Trend | <50% of recent minutes avg |

### Hard Gates
```python
@dataclass
class SoccerHardGates:
    min_team_matches: int = 20
    min_xg_sources: int = 1
    block_live: bool = True
    require_decimal_odds: bool = True
```

### 🔴 GAPS / UPGRADE OPPORTUNITIES
1. **Player Props Blocked** — v1.0 is team-only, player props need:
   - Shot map data (xG per shot)
   - Set piece assignment tracking
   - Penalty taker identification
2. **No Live xG Feed** — Manual input only
3. **Missing Corner/Card Models** — Blocked in v1.0
4. **No SGP Correlation Engine** — Same-game parlays blocked
5. **Limited League Coverage** — Only Tier 1 enabled
6. **No Weather Integration** — Rain/wind affect totals

---

## 5. GOLF

### Status: 🟡 DEVELOPMENT (v0.1.0)

### File Structure
```
golf/
├── run_daily.py                    # Entry point (405 lines)
├── golf_menu.py                    # Interactive menu
├── config/
│   └── golf_config.py              # Full config (275 lines)
├── ingest/
│   ├── underdog_parser.py          # Slate parsing
│   └── prizepicks_parser.py        # PrizePicks format
├── engines/
│   ├── generate_edges.py           # Edge generator (752 lines)
│   ├── golf_monte_carlo.py         # MC simulation
│   └── correlation_engine.py       # Course correlation
├── data/
│   └── player_database.py          # Player stats
├── calibration/
│   └── golf_tracker.py             # Result tracking
└── docs/
    └── GOLF_ENGINE_MATH.md         # Mathematical docs
```

### Tier Thresholds (Golf-Specific — CONSERVATIVE)
| Tier | Threshold | Notes |
|------|-----------|-------|
| SLAM | **DISABLED** | Golf too volatile |
| STRONG | 72% | With SG edge ≥+1.5 |
| LEAN | 60% | Course fit required |
| SPEC | 52% | Longshots, weather plays |

### Markets Supported
```python
GOLF_MARKETS = {
    "outright": finish_position == 1,
    "top_5": finish_position ≤ 5,
    "top_10": finish_position ≤ 10,
    "top_20": finish_position ≤ 20,
    "make_cut": made_cut == True,
    "miss_cut": made_cut == False,
    "h2h_tournament": head-to-head finish,
    "h2h_round": single round H2H,
    "round_score_over/under": round strokes,
    "frl": first round leader,
}
```

### Confidence Caps by Market
```python
GOLF_CONFIDENCE_CAPS = {
    "outright_winner": 0.45,  # Even elite players <15% to win
    "top_5": 0.60,
    "top_10": 0.68,
    "top_20": 0.72,
    "make_cut": 0.85,         # Highest confidence market
    "miss_cut": 0.65,
    "h2h_matchup": 0.72,
    "h2h_round": 0.68,
    "first_round_leader": 0.40,  # High variance
}
```

### Strokes Gained (SG) Model
```python
SG_WEIGHTS_BY_COURSE_TYPE = {
    "balanced": {
        "sg_ott": 0.25,   # Off the tee
        "sg_app": 0.30,   # Approach
        "sg_arg": 0.20,   # Around green
        "sg_putt": 0.25,  # Putting
    },
    "ball_strikers": {
        "sg_ott": 0.35,
        "sg_app": 0.35,
        "sg_arg": 0.15,
        "sg_putt": 0.15,
    },
    "bombers": {
        "sg_ott": 0.40,
        "sg_app": 0.25,
        "sg_arg": 0.15,
        "sg_putt": 0.20,
    },
    "putting_premium": {
        "sg_ott": 0.20,
        "sg_app": 0.25,
        "sg_arg": 0.20,
        "sg_putt": 0.35,
    },
}
```

### Course Database Sample
```python
COURSE_DATABASE = {
    "augusta_national": {
        "name": "Augusta National Golf Club",
        "tournament": "The Masters",
        "par": 72,
        "yardage": 7545,
        "type": "putting_premium",
        "avg_winning_score": -12,
        "sg_correlation": {"sg_app": 0.35, "sg_putt": 0.32, "sg_ott": 0.20},
    },
    # ... 20+ courses
}
```

### 🔴 GAPS / UPGRADE OPPORTUNITIES
1. **No Live SG Feed** — Requires DataGolf API ($$$)
2. **Missing Weather Model** — Wind is CRITICAL for links courses
3. **No Wave Advantage** — AM/PM tee time edge unmodeled
4. **Limited Historical Course Fit** — Past performance at venue
5. **No Cut Line Predictor** — Dynamic cut projection missing
6. **Monte Carlo Needs Course Conditions** — Pin positions, green speed

---

## 6. NFL (FROZEN)

### Status: 🔒 FROZEN v1.0 (Read-Only)

### File Structure
```
nfl/
├── ingest_nfl_stats.py
├── nfl_config.yaml
├── nfl_edge_generator.py
├── nfl_feature_builder.py
├── nfl_validation.py
└── nfl_resolve_results.py

run_autonomous.py                   # Main entry point (222 lines)
```

### Key Constraint
```python
def assert_version_lock():
    with open("VERSION.lock") as f:
        data = f.read()
    if "STATUS: FROZEN" not in data or "VERSION: v1.0" not in data:
        raise RuntimeError("VERSION LOCK VIOLATION")
```

### Current State
- **Data Sources**: nflverse, nflreadpy
- **Pipeline**: `run_autonomous.py`
- **Status**: Cron-safe autonomous execution
- **NO MODIFICATIONS** — Breaking changes require new version

### 🔴 FROZEN — NO UPGRADES ALLOWED
NFL system is version-locked. Any changes require:
1. New branch: `feature/nfl-v2.0`
2. Full regression test suite
3. Version bump to v2.0
4. Separate deployment

---

## CROSS-SPORT INFRASTRUCTURE

### Shared Components
| Component | Location | Purpose |
|-----------|----------|---------|
| `config/thresholds.py` | Global | CANONICAL tier thresholds |
| `core/decision_governance.py` | Global | Pick state machine |
| `calibration/unified_tracker.py` | Global | Cross-sport calibration |
| `truth_engine/` | Global | Lineage tracking |
| `engine/render_gate.py` | Global | Output validation |

### Calibration Tracking
```python
class UnifiedCalibration:
    BRIER_THRESHOLDS = {
        "nfl": 0.25,
        "nba": 0.25,
        "tennis": 0.23,  # Stricter (binary)
        "cbb": 0.22,     # Stricter
    }
```

### Sport Registry
```json
// config/sport_registry.json
{
  "NBA": {"status": "PRODUCTION", "frozen": false},
  "Tennis": {"status": "PRODUCTION", "frozen": true},
  "CBB": {"status": "PRODUCTION", "frozen": false},
  "SOCCER": {"status": "PRODUCTION", "frozen": false},
  "GOLF": {"status": "DEVELOPMENT", "frozen": false},
  "NFL": {"status": "PRODUCTION", "frozen": true}
}
```

---

## UPGRADE OPPORTUNITIES

### HIGH PRIORITY (All Sports)

| ID | Sport | Gap | Upgrade | Effort |
|----|-------|-----|---------|--------|
| U1 | ALL | No unified opponent adjustment | Port Soccer's OpponentAdjustmentEngine to all sports | 2 weeks |
| U2 | ALL | Inconsistent distribution selection | Standardize position-aware distribution selection | 1 week |
| U3 | ALL | No injury severity | Add injury return ramp-up modeling | 2 weeks |
| U4 | NBA | Missing defensive rating | Add team DRTG to projection | 3 days |
| U5 | Tennis | No H2H history | Build head-to-head database | 1 week |
| U6 | CBB | No conference strength | Add RPI/NET adjustment | 3 days |
| U7 | Soccer | Player props blocked | Implement xG per shot model | 3 weeks |
| U8 | Golf | No weather | Add wind/rain adjustment | 1 week |

### MEDIUM PRIORITY

| ID | Sport | Gap | Upgrade | Effort |
|----|-------|-----|---------|--------|
| M1 | NBA | Basic B2B handling | Add travel fatigue model | 1 week |
| M2 | Tennis | No fatigue modeling | Add tournament depth factor | 3 days |
| M3 | CBB | No tournament context | Add postseason volatility | 3 days |
| M4 | Soccer | Team-only markets | Enable SGP correlation | 2 weeks |
| M5 | Golf | No AM/PM wave | Add tee time advantage | 3 days |
| M6 | ALL | Monte Carlo efficiency | Implement variance reduction | 1 week |

### LOW PRIORITY (Nice-to-Have)

| ID | Sport | Gap | Upgrade | Effort |
|----|-------|-----|---------|--------|
| L1 | NBA | No lineup confirmation | Real-time lineup integration | 2 weeks |
| L2 | Tennis | No retirement risk | Player health tracking | 1 week |
| L3 | CBB | No freshman flags | First-year volatility adjustment | 2 days |
| L4 | Soccer | Limited leagues | Expand to all TIER_2 | 1 week |
| L5 | Golf | No cut line | Dynamic cut projection | 1 week |

---

## PRIORITY MATRIX

### Immediate (This Week)
1. **U4** — NBA defensive rating integration
2. **U6** — CBB conference strength adjustment
3. **M5** — Golf AM/PM wave advantage

### Short-Term (This Month)
1. **U1** — Unified opponent adjustment engine
2. **U5** — Tennis H2H database
3. **M1** — NBA travel fatigue model
4. **M2** — Tennis tournament depth

### Medium-Term (This Quarter)
1. **U3** — Injury severity modeling (all sports)
2. **U7** — Soccer player props
3. **M4** — Soccer SGP correlation
4. **U8** — Golf weather model

### Long-Term (Next Quarter)
1. **L1** — Real-time lineup confirmation
2. **L4** — Soccer league expansion
3. **M6** — Monte Carlo optimization

---

## VALIDATION CHECKLIST

Before any production deployment:

- [ ] All modules import from `config/thresholds.py` for tiers
- [ ] Pick state machine enforced (`decision_governance.py`)
- [ ] Eligibility gate called before Monte Carlo
- [ ] Calibration tracking enabled
- [ ] Brier score monitored (<0.25 for most sports)
- [ ] Output passes render gate validation
- [ ] No hardcoded thresholds anywhere
- [ ] LLM language uses "data suggests" not "bet this"

---

## CONTACT

System Owner: @hidayquant  
Last Updated: 2026-02-01  
Document Version: 1.0.0
