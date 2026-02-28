# NHL Standard Operating Procedure — v1.1

**STATUS:** DEVELOPMENT  
**EFFECTIVE:** 2026-02-02  
**UPDATED:** 2026-02-02 (v1.1 Extensions)  
**OWNER:** UNDERDOG ANALYSIS  

---

## 0. Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-02-02 | Initial release: Game model, goalie gate |
| v1.1 | 2026-02-02 | Added: Goalie Saves props, Backtesting harness |

---

## 1. Scope Lock (Non-Negotiable)

### v1.1 Markets
| Market | Supported | Notes |
|--------|-----------|-------|
| Moneyline | ✅ | Primary focus |
| Puck Line (±1.5) | ✅ | Poisson-derived |
| Game Totals | ✅ | 5.5 / 6.0 / 6.5 |
| **Goalie Saves** | ✅ **NEW** | v1.1 — See Section 8 |
| Player Props | ❌ | v2.0+ |
| Live/In-Game | ❌ | v2.0+ |

### Granularity
- **Game-level + Goalie-centric**
- No player-level props until v2.0
- Pre-game only (no live adjustments)

---

## 2. Modeling Philosophy

**Hockey is goalie + shot quality driven. Team averages lie.**

### Primary Drivers (Ordered by Impact)
1. **Confirmed Goalie** — ABSOLUTE GATE
2. **Shot Quality** — xG, slot vs point, high-danger chances
3. **5v5 vs Special Teams** — Separate modeling required
4. **Rest / Travel / Back-to-Back** — Material impact
5. **Home Ice Advantage** — Real, not cosmetic (~3-4%)

### Key Insight
> If goalie is not confirmed → **NO PLAY**. No exceptions.

---

## 3. Hard Gates (ABORT Pipeline)

### GATE 1: Goalie Confirmation (MANDATORY)
```
IF home_goalie.confirmed_sources < 2 → ABORT
IF away_goalie.confirmed_sources < 2 → ABORT
```

### GATE 2: Small Sample Cap
```
IF goalie.starts_last_30 < 5 → probability_cap = 0.58
```

### GATE 3: Back-to-Back Penalty
```
IF goalie.is_b2b → probability -= 0.04
```

### GATE 4: Market Sanity
```
IF |model_prob - implied_prob| < 0.02 → NO EDGE
```

---

## 4. Tier Thresholds

| Tier | Probability | Notes |
|------|-------------|-------|
| **SLAM** | ❌ DISABLED | NHL variance too high |
| **STRONG** | 64–69% | Maximum confidence |
| **LEAN** | 58–63% | Playable edge |
| **NO PLAY** | <58% | Insufficient edge |

**Critical:** No NHL pick may exceed 69% confidence. SLAM tier is FORBIDDEN.

---

## 5. Confidence Caps (Stackable)

| Condition | Cap | Stacks |
|-----------|-----|--------|
| Small sample goalie (<5 starts) | 58% | No |
| Backup goalie | 60% | Yes |
| B2B goalie | -4% penalty | Yes |

---

## 6. Simulation Engine

### Poisson Game Model
```python
λ_home = composite_xg(home_team, away_goalie)
λ_away = composite_xg(away_team, home_goalie)

# Monte Carlo: 20,000 games
home_goals = Poisson(λ_home × home_ice_adj)
away_goals = Poisson(λ_away)
```

### xG Composite Formula
```python
xG = (
    0.45 × team_5v5_xgf +
    0.25 × opponent_5v5_xga +
    0.20 × goalie_adjustment +
    0.10 × special_teams_delta
)
```

### Home Ice Multiplier
- Base: **1.035** (3.5% boost to home λ)

---

## 7. Output Contract

```json
{
  "sport": "NHL",
  "game": "BOS @ NYR",
  "goalies": {
    "home": "Shesterkin (CONFIRMED)",
    "away": "Swayman (CONFIRMED)"
  },
  "market": "Moneyline|Puck Line|Total",
  "model_prob": 0.621,
  "implied_prob": 0.565,
  "edge": 0.056,
  "tier": "LEAN",
  "pick_state": "OPTIMIZABLE",
  "risk_tags": ["GOALIE_DEPENDENT"],
  "sources": ["nhl_api", "naturalstattrick", "dailyfaceoff"],
  "audit_hash": "sha256..."
}
```

---

## 8. Goalie Saves Props (v1.1 NEW)

### Market
- **Goalie Saves** (OVER/UNDER)
- Pre-game only
- Starter must be CONFIRMED

### Model
```
Expected_Shots ~ Poisson(λ_shots)
Expected_Saves = Expected_Shots × SV%
Saves = Shots - Goals (binomial)
```

### Additional Gates (Goalie Saves Specific)
```
GATE S1: Goalie CONFIRMED (≥2 sources) → else ABORT
GATE S2: <5 recent starts → NO PLAY
GATE S3: Opponent shots <26/gm → cap prob ≤60%
GATE S4: |model - implied| < 3% → NO EDGE
```

### Stricter Tiers (Saves)
| Tier | Probability |
|------|-------------|
| STRONG | 63–67% |
| LEAN | 58–62% |
| NO PLAY | <58% |

### Files
- `sports/nhl/goalies/saves_model.py` — Projection engine
- `sports/nhl/goalies/saves_simulate.py` — MC simulator

---

## 9. Backtesting Harness (v1.1 NEW)

### Seasons Validated
- 2023-24
- 2024-25

### Test Matrix
| Component | ON | OFF |
|-----------|-----|-----|
| Goalie confirmation gate | ✅ | ❌ |
| B2B penalty | ✅ | ❌ |
| Market sanity gate | ✅ | ❌ |
| Distribution: Poisson vs Empirical | ✅ | ❌ |

### Non-Negotiable Assertions
```python
assert abs(calibration_error) <= 0.03
assert max_drawdown <= 25%
assert slam_count == 0
assert goalie_unknown_bets == 0  # In FULL_GATES mode
```

### Files
- `tests/nhl/backtest_runner.py` — Orchestrator
- `tests/nhl/test_goalie_gate.py` — Gate assertions
- `tests/nhl/test_calibration.py` — Calibration metrics

### Output
```json
{
  "sport": "NHL",
  "seasons": ["2023-24", "2024-25"],
  "markets": {
    "moneyline": {"roi": 4.1, "brier": 0.188},
    "totals": {"roi": 2.6, "brier": 0.194},
    "goalie_saves": {"roi": 3.8, "brier": 0.181}
  },
  "drawdown_max": 18.4,
  "verdict": "PROMOTE v1.1"
}
```

---

## 10. Pipeline Execution

### Daily Run
```bash
.venv\Scripts\python.exe sports/nhl/run_daily.py --dry-run
.venv\Scripts\python.exe sports/nhl/run_daily.py  # Production
```

### Run Backtests
```bash
.venv\Scripts\python.exe tests/nhl/backtest_runner.py
```

### Run Gate Tests
```bash
.venv\Scripts\python.exe -m pytest tests/nhl/ -v
```

---

## 11. Directory Structure (v1.1)

```
sports/
└── nhl/
    ├── __init__.py
    ├── run_daily.py           # Main entry point
    ├── SOP_NHL_v1.1.md        # This file
    ├── config/
    │   ├── thresholds.py      # Tier caps
    │   └── teams.json         # Team metadata
    ├── goalies/
    │   ├── confirmation_gate.py    # HARD GATE
    │   ├── saves_model.py          # v1.1 NEW
    │   └── saves_simulate.py       # v1.1 NEW
    ├── gates/
    │   └── __init__.py
    ├── ingest/
    │   └── __init__.py        # Placeholder (TODO)
    ├── models/
    │   └── poisson_sim.py     # Game simulator
    └── outputs/
        └── .gitkeep

tests/
└── nhl/
    ├── __init__.py
    ├── backtest_runner.py     # v1.1 NEW
    ├── test_goalie_gate.py    # v1.1 NEW
    └── test_calibration.py    # v1.1 NEW

outputs/
└── nhl/
    └── backtests/
        └── .gitkeep
```

---

## 12. Risk Tags Reference

| Tag | Meaning | Action |
|-----|---------|--------|
| `GOALIE_DEPENDENT` | Default for all NHL picks | Info only |
| `GOALIE_NOT_CONFIRMED` | Gate violation | ABORT |
| `SMALL_SAMPLE_GOALIE` | <5 starts | Cap 58% |
| `BACKUP_GOALIE` | Non-starter | Cap 60% |
| `B2B_GOALIE` | Back-to-back | -4% penalty |
| `INSUFFICIENT_EDGE` | Edge <2% | NO PLAY |
| `LOW_SHOT_OPPONENT` | <26 shots/gm (saves) | Cap 60% |
| `INSUFFICIENT_STARTS` | <5 starts (saves) | NO PLAY |

---

## 13. Promotion Criteria (v1.1 → Production)

1. ✅ All backtest assertions pass
2. ✅ 50 games paper trading
3. ✅ Brier score ≤ 0.24
4. ✅ ROI positive across all markets
5. ✅ No SLAM tier picks generated

---

## 14. Future Extensions (v2.0 Candidates)

- **Referee special-teams bias** (PP inflation/deflation)
- **Home-ice + travel fatigue spline**
- **Player shots-on-goal props**
- **Live NHL (intermission-only, low latency)**

---

**Document Version:** v1.1  
**Last Updated:** 2026-02-02  
**Next Review:** After 50 games paper trading
