# CBB Architecture — NBA Prototype Mapping

## Overview

CBB module is a **prototype** of the NBA architecture with sport-specific distinctions.
It follows the same pipeline pattern but with CBB-appropriate models and thresholds.

## Architecture Comparison

### Directory Structure (Mirrors NBA's `ufa/`)

| NBA (`ufa/`)              | CBB (`sports/cbb/`)           | Purpose                        |
|---------------------------|-------------------------------|--------------------------------|
| `ufa/ingest/nba.py`       | `cbb/ingest/cbb_data_provider.py` | Player stats from API       |
| `ufa/ingest/espn.py`      | `cbb/ingest/cbb_data_provider.py` | ESPN API integration        |
| `ufa/analysis/prob.py`    | `cbb/models/prob.py`          | Probability computation        |
| `ufa/analysis/calibration.py` | `cbb/models/calibration.py` | Track prediction accuracy    |
| `ufa/roster_gate.py`      | `cbb/gates/roster_gate.py`    | Roster verification           |
| `ufa/gates/injury_gate.py`| `cbb/gates/edge_gates.py`     | Gate orchestration            |
| `ufa/config.py`           | `cbb/config.py`               | Sport-specific settings       |

### Key Differences

| Aspect              | NBA                          | CBB                              |
|---------------------|------------------------------|----------------------------------|
| **Distribution**    | Normal (Gaussian)            | Poisson (discrete counts)        |
| **Max Confidence**  | 80% (SLAM with usage gate)   | 79% (no SLAM tier)               |
| **Tiers**           | SLAM / STRONG / LEAN / SKIP  | STRONG / LEAN / SKIP only        |
| **Core Stat Cap**   | 75-80%                       | 70-75%                           |
| **Volume Cap**      | 68%                          | 65%                              |
| **Event Cap**       | 55%                          | 55%                              |
| **Min Games**       | 10                           | 5                                |
| **Min MPG**         | 25                           | 20                               |
| **Data Source**     | `nba_api` package            | ESPN CBB API                     |
| **Season Length**   | 82 games                     | ~35 games                        |
| **Composite Stats** | Allowed (PRA, etc.)          | Blocked initially                |

### Probability Model Rationale

**NBA uses Normal distribution because:**
- Higher scoring (100-120 PPG team, 20-30 PPG player)
- 82-game season provides robust samples
- Central Limit Theorem applies well
- GMM (Gaussian Mixture Model) handles multi-modal distributions

**CBB uses Poisson distribution because:**
- Lower scoring (60-80 PPG team, 10-20 PPG player)
- ~35 game season = smaller samples
- Discrete count data (can't score 15.7 points)
- Variance ≈ Mean relationship holds better
- Cannot have negative values (Poisson bounded at 0)

### Tier Thresholds

```
NBA:                         CBB:
┌──────────────┐             ┌──────────────┐
│ SLAM   ≥80% │             │              │  (No SLAM tier)
├──────────────┤             ├──────────────┤
│ STRONG ≥65% │             │ STRONG ≥70% │  (Stricter threshold)
├──────────────┤             ├──────────────┤
│ LEAN   ≥55% │             │ LEAN   ≥60% │  (Stricter threshold)
├──────────────┤             ├──────────────┤
│ SKIP   <55% │             │ SKIP   <60% │
└──────────────┘             └──────────────┘
```

### Gate System

| Gate              | NBA                        | CBB                           |
|-------------------|----------------------------|-------------------------------|
| Roster Gate       | ✅ Via ESPN/nba_api        | ✅ Via ESPN CBB API           |
| Minutes Gate      | ≥25 MPG                    | ≥20 MPG                       |
| Games Played      | ≥10 games                  | ≥5 games                      |
| Blowout Gate      | Spread >20                 | Spread >25                    |
| Injury Gate       | ✅ OUT/DOUBTFUL blocked    | ✅ Same                       |
| Variance Gate     | std > mean × 0.5           | std > mean × 0.6              |

### Pipeline Flow (Identical Pattern)

```
┌─────────────────────────────────────────────────────────────┐
│  1. INGEST     │ Parse Underdog paste → Structured props    │
├─────────────────────────────────────────────────────────────┤
│  2. DATA       │ Fetch player stats from API                │
├─────────────────────────────────────────────────────────────┤
│  3. EDGES      │ Compute probability using sport model      │
├─────────────────────────────────────────────────────────────┤
│  4. GATES      │ Apply hard gates (roster, minutes, etc.)   │
├─────────────────────────────────────────────────────────────┤
│  5. SCORE      │ Assign tiers based on capped probability   │
├─────────────────────────────────────────────────────────────┤
│  6. VALIDATE   │ Schema check, duplicate detection          │
├─────────────────────────────────────────────────────────────┤
│  7. RENDER     │ Generate human-readable report             │
└─────────────────────────────────────────────────────────────┘
```

### Data Provider API

**NBA (ufa/ingest/nba.py):**
```python
from nba_api.stats.endpoints import playergamelogs
logs = playergamelogs.PlayerGameLogs(player_id=player_id)
```

**CBB (cbb/ingest/cbb_data_provider.py):**
```python
from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
provider = CBBDataProvider()
player = provider.get_player_stats_by_name("Player Name", "TEAM")
```

### Configuration Files

| NBA                              | CBB                              |
|----------------------------------|----------------------------------|
| `ufa/config.py`                  | `cbb/config.py`                  |
| (inline in prob.py)              | `cbb/config/gate_thresholds.yaml`|
| (inline)                         | `cbb/models/seed_ref_coach.yaml` |
| (inline)                         | `cbb/models/travel_fatigue.yaml` |

### What CBB Borrows from NBA

1. **Pipeline pattern** — Same 7-stage flow
2. **Gate architecture** — Roster, minutes, injury checks
3. **Confidence capping** — Stat class → cap mapping
4. **Calibration tracking** — Predicted vs actual hit rates
5. **Report rendering** — Similar output format
6. **Menu integration** — Same command pattern

### What CBB Does Differently

1. **Poisson model** — Not Normal distribution
2. **No SLAM tier** — Max confidence 79%
3. **Stricter thresholds** — STRONG ≥70%, LEAN ≥60%
4. **Blocked composite stats** — No PRA until validated
5. **Lower sample requirements** — 5 games vs 10
6. **Conference weighting** — Conference games more predictable
7. **Seed/Ref/Coach adjustments** — Unique to college

### Status

CBB is in **RESEARCH** status:
- Enabled in `config/sport_registry.json` → `"enabled": false`
- No Telegram broadcast
- No live betting recommendations
- Paper run only until Phase 6 validation passes

### Files Created for CBB

```
sports/cbb/
├── cbb_main.py                    # Pipeline orchestrator
├── config.py                      # Sport-specific settings
├── menu_integration.py            # Menu hooks
├── ingest/
│   ├── cbb_data_provider.py       # ESPN CBB API
│   └── parse_cbb_paste.py         # Underdog paste parser
├── gates/
│   ├── roster_gate.py             # Roster verification
│   └── edge_gates.py              # Gate orchestrator
├── models/
│   ├── prob.py                    # Poisson probability
│   ├── probability.py             # Alternative model
│   └── calibration.py             # Track accuracy
├── config/
│   └── gate_thresholds.yaml       # Gate configuration
├── outputs/                       # Generated reports
└── tests/
    ├── test_data_provider.py      # API tests
    └── test_pipeline.py           # Pipeline tests
```
