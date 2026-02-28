# Specialist Backtest — Usage Guide

This guide shows how to generate the historical dataset, run the grid-search backtest, and enforce the hard-fail gate before updating season thresholds.

## 1) Prepare the dataset (JSON)

Schema (list of records):

```json
{
  "player": "Isaiah Hartenstein",
  "stat": "3PM",
  "specialist_type": "CATCH_AND_SHOOT_3PM",
  "line": 0.5,
  "confidence": 72.0,
  "hit": true,
  "features": {
    "assisted_3pa_rate": 0.68,
    "pullup_3pa_rate": 0.18,
    "dribbles_per_shot": 0.9,
    "corner_3_rate": 0.22
  }
}
```

See `data/specialist_history.example.json` for a ready-made template.

Grouping keys are `(stat, specialist_type, line_bucket)` where `line_bucket` rounds to nearest 0.5 (2.5, 3.0, 3.5, ...).

## 2) Run the backtest

Default grid (C&S 3PM): assisted_3pa_rate ∈ [0.60, 0.65, 0.70], pullup_3pa_rate ∈ [0.25, 0.30, 0.35], dribbles_per_shot ∈ [1.0, 1.2, 1.4].

Outputs JSON to `outputs/specialist_backtest_result.json`:

- Thresholds chosen
- Brier score
- Hit rate
- Avg confidence
- False-confidence rate
- Calibration curve
- Samples count and per-bucket distribution

## 3) Enforce hard-fail gate

Run `scripts/test_no_specialist_confidence_inflation.py` to abort when:

```text
avg_confidence − hit_rate > 0.05
```

If it fails, do not update thresholds. Increase samples or tighten ranges.

## 4) Update thresholds (seasonal)

- Version your thresholds (e.g., `CATCH_AND_SHOOT_3PM_v1.2`)
- Log deltas (previous → new)
- Do not retune daily; monthly at most

## 5) Integrate with pipeline

- Use `specialists/feature_ingest.py` to attach tracking features onto props before analysis
- Your specialist engines (`core/stat_specialist_engine.py`, `stat_specialist_engine.py`) will read keys like `assisted_3pa_rate`, `pullup_3pa_rate`, `dribbles_per_shot`, `time_of_possession`, `avg_shot_distance`, `potential_assists`, etc.

## Optional command examples

```powershell
# Backtest (C&S 3PM)
.venv\Scripts\python.exe backtests\specialist_threshold_backtest.py --input data\specialist_history.json --stat 3PM --specialist CATCH_AND_SHOOT_3PM

# Hard-fail gate
.venv\Scripts\python.exe scripts\test_no_specialist_confidence_inflation.py --result outputs\specialist_backtest_result.json
```
