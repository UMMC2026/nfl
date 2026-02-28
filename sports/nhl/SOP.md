# NHL Standard Operating Procedure — v2.0

## 🎯 Module Overview

NHL v2.0 is a **goalie-centric, risk-first hockey analysis system** with:
- Mandatory goalie confirmation gate
- **NO SLAM tier** (hockey volatility too high)
- Live intermission adjustments
- Context-aware probability modeling

---

## 🏗️ Architecture

```
sports/nhl/
├── __init__.py           # v2.0 exports
├── run_daily.py          # Daily pipeline orchestrator
├── SOP.md                # This file
│
├── goalies/              # Goalie-centric models
│   ├── confirmation_gate.py  # HARD GATE (v1.0)
│   ├── saves_model.py        # Saves props (v1.1)
│   └── saves_simulate.py     # Monte Carlo (v1.1)
│
├── models/               # Core game models
│   └── poisson_sim.py        # Poisson simulator (v1.0)
│
├── context/              # Game context (v2.0)
│   ├── ref_bias.py           # Referee special-teams bias
│   └── travel_fatigue.py     # Travel + home ice
│
├── players/              # Player props (v2.0)
│   ├── shots_model.py        # SOG projections
│   └── shots_simulate.py     # Monte Carlo
│
├── live/                 # Live engine (v2.0)
│   ├── ingest_live.py        # NHL API ingestion
│   ├── intermission_model.py # Live adjustments
│   └── validate_live.py      # Gate validation
│
└── xg_model/             # Expected goals (future)
    └── expected_goals.py
```

---

## 🚨 Global Assertions (NON-NEGOTIABLE)

```python
# Every pipeline run MUST satisfy:
assert unconfirmed_goalie_bets == 0      # Goalie gate
assert slam_count == 0                    # NO SLAM tier
assert live_bets_per_game <= 1           # Max 1 live bet
assert abs(calibration_error) <= 0.03    # Calibration target
assert max_drawdown <= 25%               # Risk limit
```

---

## 🛡️ Gates

### G1: Goalie Confirmation (HARD GATE)
```python
# From goalies/confirmation_gate.py
# MUST have ≥2 sources confirming goalie
# NO PLAY if goalie unconfirmed
```

### G2: B2B Penalty
```python
# -4% probability for back-to-back starts
# Applied to saves and totals markets
```

### G3: Small Sample Gate
```python
# <5 goalie starts → cap confidence 58%
# Backup goalie → cap confidence 60%
```

### G4: Edge Minimum
```python
# Minimum 2% edge required to play
# Live bets require 3% edge
```

### R1-R3: Referee Bias Gates
```python
# R1: <30 games sample → ignore ref
# R2: Cap adjustment ±0.15 goals
# R3: Only affects totals/saves markets
```

### T1-T2: Travel Fatigue Gates
```python
# T1: <300 miles → no adjustment
# T2: Cap penalty at 6%
```

### P1-P3: Player SOG Gates
```python
# P1: TOI <12 min → NO PLAY
# P2: CV >45% → cap 60%
# P3: Adverse line movement → NO PLAY
```

### L1-L4: Live Betting Gates
```python
# L1: Only during intermissions
# L2: Single update per intermission
# L3: Max 1 live bet per game
# L4: Data must be <60 seconds old
```

---

## 📊 Tier Thresholds

| Tier | Probability | Notes |
|------|-------------|-------|
| **SLAM** | DISABLED | Too volatile for hockey |
| **STRONG** | 64-67% | Primary targets |
| **LEAN** | 58-63% | Secondary, smaller units |
| **AVOID** | <58% | No play |

### Goalie Saves Tiers (Stricter)
| Tier | Probability |
|------|-------------|
| STRONG | 63-67% |
| LEAN | 58-62% |

### Player SOG Tiers
| Tier | Probability |
|------|-------------|
| STRONG | 62-66% |
| LEAN | 58-61% |

---

## 🏃 Daily Pipeline

```bash
# Full pipeline
.venv\Scripts\python.exe sports/nhl/run_daily.py

# Dry run (no telegram)
.venv\Scripts\python.exe sports/nhl/run_daily.py --dry-run
```

### Pipeline Steps:
1. **Fetch schedule** — Get today's NHL games
2. **Goalie confirmation** — HARD GATE
3. **Apply context** — Ref bias + travel fatigue
4. **Run simulations** — Poisson for goals, saves, SOG
5. **Assign tiers** — Based on probability thresholds
6. **Validate output** — Gate checks
7. **Render report** — JSON + human-readable

---

## 🔴 v2.0 Modules

### Module 1: Referee Special-Teams Bias
```python
from sports.nhl.context.ref_bias import get_ref_adjustment

# Adjusts totals based on referee PP/PK tendencies
adjustment = get_ref_adjustment("Wes McCauley", "home_pp", 20)
# Returns adjustment to game total (±0.15 cap)
```

### Module 2: Travel Fatigue
```python
from sports.nhl.context.travel_fatigue import get_travel_adjustment

# Calculates fatigue penalty from travel
penalty = get_travel_adjustment(
    origin="LAK",
    destination="NYR",
    days_rest=1,
    games_in_5_days=3
)
# Returns probability penalty (max 6%)
```

### Module 3: Player SOG Props
```python
from sports.nhl.players import project_player_sog, simulate_player_sog

# Project expected shots
projection = project_player_sog(
    player_name="David Pastrnak",
    avg_sog=4.1,
    opponent="DET",
    opp_sa_per_game=28.5,
    toi_expected=20.5
)

# Monte Carlo simulation
result = simulate_player_sog(
    player_name="Pastrnak",
    opponent_name="DET",
    lambda_shots=projection.lambda_shots,
    line=3.5,
    n_sims=20_000
)
print(f"OVER 3.5: {result.over_prob:.1%}")
```

### Module 4: Live Intermission Engine
```python
from sports.nhl.live import (
    fetch_validated_live,
    GameTotalModel,
    validate_live_bet,
    assert_global_constraints
)

# Fetch live data (with gate validation)
snapshot, reason = fetch_validated_live(game_id="2024020815")

if snapshot:
    # Run live adjustment
    adjustment = GameTotalModel.adjust(
        snapshot=snapshot,
        original_projection=6.2,
        original_probability=0.58,
        line=6.5,
        direction="OVER"
    )
    
    # Validate before placing
    result = validate_live_bet(
        game_id="2024020815",
        snapshot=snapshot,
        adjustment=adjustment
    )
    
    if result.is_valid:
        # Place bet
        pass

# Always assert at end
assert_global_constraints()
```

---

## 🧪 Testing

### Run 3-Season Backtest
```bash
.venv\Scripts\python.exe tests/nhl/backtest_3season.py
```

### Run Goalie Gate Tests
```bash
.venv\Scripts\python.exe -m pytest tests/nhl/test_goalie_gate.py -v
```

### Run Calibration Tests
```bash
.venv\Scripts\python.exe -m pytest tests/nhl/test_calibration.py -v
```

---

## 📈 Calibration

### Expected Performance (3-season backtest)
| Metric | Target | Status |
|--------|--------|--------|
| Win Rate | ~58-62% | ✓ |
| ROI | +3-8% | ✓ |
| Brier Score | <0.24 | ✓ |
| Calibration Error | ≤3% | ✓ |
| Max Drawdown | ≤25% | ✓ |

---

## ⚠️ Common Failure Modes

| Issue | Cause | Fix |
|-------|-------|-----|
| `unconfirmed_goalie_bets > 0` | Goalie gate bypassed | Never skip confirmation |
| `slam_count > 0` | SLAM tier used | SLAM is DISABLED |
| `live_bets_per_game > 1` | Multiple live bets | Use `validate_live_bet()` |
| `calibration_error > 3%` | Model drift | Re-train on recent data |
| Referee bias too aggressive | Exceeded caps | Gates R1-R3 should catch |

---

## 📜 Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2025-01 | Initial: Goalie gate, Poisson sim |
| v1.1 | 2025-01 | Goalie saves props, backtest harness |
| **v2.0** | 2025-01 | Ref bias, travel fatigue, SOG props, live engine |

---

## 🔮 Future (v2.1+)

- xG (expected goals) model integration
- Shot location heatmaps
- Corsi/Fenwick adjustments
- Period-by-period projections
- Multi-leg parlay optimization
