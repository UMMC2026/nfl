# Specialist System — Required Data Fields and Backtest Tuning

This document specifies the exact tracking and derived fields required to power the specialist system, and a safe procedure to tune classifier thresholds via backtests without overfitting.

## Global (All Players)

Mandatory fields used across all specialists:

- minutes (box): normalize everything
- usage_rate (box): role context
- assisted_fg_rate (tracking): separates creators vs finishers
- time_of_possession (tracking): AST/creator logic
- avg_shot_distance (tracking): rim runner vs shooter
- bench_minutes_rate (box): microwave detection
- usage_volatility (rolling σ, derived): risk control

## 3PM / Shooting Specialists (Critical)

Unlocks catch-and-shoot edges:

- 3pa (required): baseline volume
- 3pm (required): outcome
- assisted_3pa_rate (required): core C&S signal
- pullup_3pa_rate (required): volatility flag
- dribbles_per_shot (required): C&S vs self-creation
- corner_3_rate (optional): boosts role stability
- shot_quality_3 (expected, optional): filters fake volume

If you add only one thing for shooters: assisted_3pa_rate + pullup_3pa_rate.

## Big Man 3PM / Pick-and-Pop

- position (required): filter
- avg_3pa (required): avoid fake stretch bigs
- pick_and_pop_rate (required): role confirmation
- above_break_3_rate (optional): scheme dependency
- trailer_3_rate (optional): transition signal

## Midrange Specialists (Hidden Edge)

- midrange_fga_rate (required): defines archetype
- rim_fga_rate (required): separates slashers
- elbow_touch_rate (optional): offense hub
- shot_clock_usage_mid (optional): bailout scorer

## Big Post / Rim Runner

- post_touch_rate (required): back-to-basket
- paint_fga_rate (required): volume
- roll_man_frequency (optional): lob threat
- putback_rate (optional): rebound → points

## Assist Specialists

- potential_assists (required): true passing
- touches (required): control
- passes_per_touch (optional): pass-first signal
- drive_and_kick_rate (optional): AST sustainability

### Data Sources (Realistic)

- NBA tracking (Second Spectrum / pbp-derived)
- NBA.com advanced splits / StatMuse
- Rolling feature derivations (internal)

---

## Backtest Tuning (Safe, No ML)

The goal is rule calibration, not model learning. Freeze classifier logic and only tune thresholds.

### Step 1 — Freeze Classifier Logic

Do not change structure. Tune thresholds only.

Example for C&S 3PM:

```python
assisted_3pa_rate >= X
pullup_3pa_rate < Y
dribbles_per_shot <= Z
```

### Step 2 — Backtest by Stat + Specialist (not by player)

Group keys: `(stat, specialist_type, line_bucket)`

Examples:

- (3PM, CATCH_AND_SHOOT_3PM, 2.5)
- (PTS, MIDRANGE_SPECIALIST, 18.5)

### Step 3 — Metrics That Matter

- Hit rate
- Brier score
- Calibration curve
- False confidence rate (confidence > 65% but miss)

### Step 4 — Grid Search (Controlled)

Example ranges for C&S 3PM:

```text
assisted_3pa_rate ∈ [0.60, 0.65, 0.70]
pullup_3pa_rate ∈ [0.25, 0.30, 0.35]
dribbles_per_shot ∈ [1.0, 1.2, 1.4]
```

Constraints:

- ≥ 300 historical samples overall
- ≥ 30 per line bucket
- Reject any config with confidence inflation

### Step 5 — Lock Thresholds Per Season

- Do not retune daily
- Tune monthly at most
- Version thresholds and log deltas (e.g., `CATCH_AND_SHOOT_3PM_v1.2`)

### Step 6 — Hard Fail Test (Mandatory)

Add a deployment gate:

```python
assert avg_confidence - hit_rate <= 0.05
```

If this fails → abort deployment.

---

## Implementation Notes

- See `specialists/feature_schema.py` for typed feature definitions and ingestion stubs.
- See `backtests/specialist_threshold_backtest.py` for the grid-search harness, metrics, and constraints.
- See `scripts/test_no_specialist_confidence_inflation.py` for the hard-fail deployment test.
