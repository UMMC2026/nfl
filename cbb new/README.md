# FUOOM DARK MATTER — System Stability Fix Package
## All 4 Sprints: Math Foundation → Distribution → Validation → Binary Markets

**Date:** 2026-02-15  
**Audit Reference:** FUOOM-AUDIT-001  
**SOP Authority:** v2.1 (Truth-Enforced)  
**Status:** All self-tests passing ✅

---

## What This Package Contains

```
fuoom_fixes/
├── shared/
│   ├── math_utils.py      ← Sprint 1: Odds conversion, Kelly criterion, EV, Brier score
│   ├── config.py           ← Sprint 1: Tier thresholds, sigma table, defensive signs, HCA
│   └── __init__.py
├── nfl/
│   ├── distributions.py    ← Sprint 2: Poisson mixture scoring, Skellam, weather, logistic
│   └── __init__.py
├── sports/cbb/
│   ├── direction_gate_wiring.py  ← CBB Fix: Direction gate + tier debug + experimental mode
│   └── __init__.py
├── markets/
│   ├── binary_markets.py   ← Sprint 4: MVP, Golf winner, YES/NO market evaluator
│   └── __init__.py
├── validate_output.py      ← Sprint 3: Universal hard gate (9 checks, fail-fast)
└── README.md                ← This file
```

---

## Audit Items Resolved

| # | Severity | Issue | File | Status |
|---|----------|-------|------|--------|
| 1 | CRITICAL | Tier thresholds v2.0 vs v2.1 | `config.py` | ✅ Fixed |
| 2 | CRITICAL | Kelly criterion hardcoded | `math_utils.py` | ✅ Fixed |
| 3 | CRITICAL | Negative Kelly not blocked | `math_utils.py` + `validate_output.py` | ✅ Fixed |
| 4 | CRITICAL | NFL scores modeled as Normal | `nfl/distributions.py` | ✅ Fixed |
| 5 | CRITICAL | Home advantage double-counted | `config.py` + `nfl/distributions.py` | ✅ Fixed |
| 6 | CRITICAL | Player-team consistency never triggers | `validate_output.py` | ✅ Fixed |
| 7 | CRITICAL | Dr. NFL Sim concurrent with Bayes | `nfl/distributions.py` (documented) | ✅ Documented |
| 8 | WARNING | Logistic transform asymmetry | `nfl/distributions.py` | ✅ Fixed |
| 9 | WARNING | Wind impact flat step function | `nfl/distributions.py` | ✅ Fixed |
| 10 | WARNING | No odds conversion utility | `math_utils.py` | ✅ Fixed |
| 11 | WARNING | Edge as prob diff, not EV | `math_utils.py` | ✅ Fixed |
| 12 | WARNING | Brier score threshold context | `math_utils.py` | ✅ Fixed |
| 13 | WARNING | 2.5σ rule missing sigma defs | `config.py` | ✅ Fixed |
| 14 | WARNING | Market Scout stale lines | `config.py` (threshold defined) | ✅ Documented |
| 15 | WARNING | Defensive sign convention | `config.py` | ✅ Fixed |
| 16 | REC | Binary market module | `markets/binary_markets.py` | ✅ Built |
| 17 | REC | MVP probability model | `markets/binary_markets.py` | ✅ Built |
| 18 | REC | Golf winner model | `markets/binary_markets.py` | ✅ Built |
| CBB-1 | CRITICAL | Direction gate orphaned | `sports/cbb/direction_gate_wiring.py` | ✅ Fixed |
| CBB-2 | WARNING | Tier mislabeling (SDG penalty order) | `sports/cbb/direction_gate_wiring.py` | ✅ Diagnosed |

---

## Integration Steps (VS Code)

### Step 1: Codebase Grep — Kill v2.0 Tier References (5 min)

Search your entire repo for these OLD thresholds and replace:

```
OLD → NEW
0.90 (tier boundary) → 0.75
0.80 (tier boundary) → 0.65  
0.70 (tier boundary) → 0.55
0.60 (tier boundary) → 0.55 (NO_PLAY, SPEC removed)
```

VS Code search regex: `(0\.90|0\.80|0\.70|0\.60)` in files matching `*.py, *.yaml, *.json`

### Step 2: Drop In Files (2 min)

Copy these files into your repo structure:

```bash
cp shared/math_utils.py  YOUR_REPO/shared/math_utils.py
cp shared/config.py       YOUR_REPO/shared/config.py
cp validate_output.py     YOUR_REPO/validate_output.py
cp nfl/distributions.py   YOUR_REPO/nfl/distributions.py  
cp markets/binary_markets.py  YOUR_REPO/markets/binary_markets.py
```

### Step 3: Wire CBB Direction Gate (5 min)

Open `sports/cbb/cbb_main.py`, find `apply_cbb_gates()` (~line 1677).  
Add at the TOP of the function, BEFORE other gates:

```python
from sports.cbb.direction_gate import apply_direction_gate

edges = apply_direction_gate(edges, context=context)
if not edges:
    logging.critical("Direction gate triggered: >65% same direction")
    return []
```

### Step 4: Wire Validation Gate (5 min)

In your main pipeline runner, replace direct `render_report.py` calls:

```python
# BEFORE (dangerous):
render_report(edges)

# AFTER (SOP v2.1 compliant):
from validate_output import gate_and_render
gate_and_render(edges, sport='NBA', render_func=render_report)
```

### Step 5: Update score_edges.py — Dynamic Kelly (10 min)

Replace hardcoded `kelly_fraction: 0.3` with:

```python
from shared.math_utils import kelly_sized, calculate_ev, full_edge_analysis

# For each signal:
analysis = full_edge_analysis(model_prob, american_odds)
if not analysis['has_edge']:
    signal['tier'] = 'NO_PLAY'  # Negative Kelly = exclude
    continue

signal['kelly_fraction'] = kelly_sized(model_prob, decimal_odds, tier)
signal['expected_value'] = analysis['expected_value']
signal['edge_estimate'] = analysis['edge_estimate']
```

### Step 6: Verify (2 min)

```bash
# Run self-tests
PYTHONPATH=. python shared/math_utils.py
PYTHONPATH=. python shared/config.py
PYTHONPATH=. python nfl/distributions.py
PYTHONPATH=. python sports/cbb/direction_gate_wiring.py
PYTHONPATH=. python markets/binary_markets.py

# Run validation gate on your latest output
python validate_output.py --input outputs/scored_edges.json --sport NBA
```

---

## NFL Agent Pipeline Fix (Dr. NFL Sim Ordering)

Dr. NFL Sim DEPENDS on Dr. NFL Bayes EPA output.  
In your NFL orchestrator, change from concurrent to sequential:

```python
# WRONG (current):
results = concurrent_nfl_agents({
    'dr_nfl_bayes': {...},
    'dr_nfl_sim': {...},     # ← Listed as concurrent, but depends on Bayes
})

# CORRECT:
# Stage 1: Concurrent agents (no dependencies)
stage1 = concurrent_nfl_agents({
    'dr_nfl_bayes': {...},
    'coach_film_room': {...},
    'game_script_analyst': {...},
    'injury_intel': {...},
})

# Stage 2: Sequential (depends on Stage 1)
stage2_sim = dr_nfl_sim.run(inputs=stage1['dr_nfl_bayes'])

# Stage 3: Market Scout (fetch fresh lines)
stage3_market = market_scout.run(
    adjusted_probs=stage2_sim,
    lines=fetch_fresh_lines()   # ← NOT cached from ingest
)
```

---

## Calibration Notes

### Values That MUST Be Calibrated From Your Data

| Parameter | File | Method |
|-----------|------|--------|
| `k` and `alpha` (logistic) | `config.py` | `calibrate_logistic_params()` in `distributions.py` |
| `SIGMA_TABLE` values | `config.py` | Calculate std dev from last 2+ seasons of game logs |
| NFL possession outcome probs | `distributions.py` | Fit from nflfastR play-by-play data |
| `HOME_ADVANTAGE` points | `config.py` | Calculate from last 3 seasons by sport |
| `DEFENSE_SIGN_CONVENTION` league_avg | `config.py` | Update at start of each season |

### CBB Experimental Mode Exit Criteria

1. Wire direction gate ✅
2. Debug tier assignment (SDG penalty order) — use `debug_tier_assignment()`
3. Track next 50 CBB picks with outcomes in `picks.csv`
4. Calculate Brier score: if < 0.20, exit experimental mode
5. If Brier > 0.25, halt CBB and investigate model structure

---

## Test Results (2026-02-15)

```
✅ shared/math_utils.py     — All self-tests passed
✅ shared/config.py          — All config self-tests passed  
✅ nfl/distributions.py      — All NFL distribution self-tests passed
✅ sports/cbb/direction_gate — All CBB direction gate tests passed
✅ markets/binary_markets.py — All binary market self-tests passed
✅ validate_output.py        — Correctly PASSED clean edges (8/8 checks)
✅ validate_output.py        — Correctly BLOCKED dirty edges (5 violations caught)
```
