# CBB (College Basketball) Module

**STATUS:** RESEARCH  
**VERSION:** 0.1.0  

This module is **fully isolated** from NFL/NBA pipelines.  
Delete this folder to remove CBB with **zero collateral damage**.

## Quick Start

```bash
# Dry run (no output files)
python sports/cbb/run_daily.py --dry-run

# Full run (when enabled)
python sports/cbb/run_daily.py --date 2026-01-21
```

## Architecture

```
sports/cbb/
├── config/           # Runtime configs, thresholds, regimes
├── ingest/           # Data ingestion (FINAL games only)
├── features/         # Player, team, context features
├── edges/            # Edge generation + gates
├── models/           # Probability + priors + calibration
├── validate/         # Render gate + schema validation
├── render/           # Report generation
├── live/             # In-game controls
└── runs/             # State, logs, audits
```

## Key Differences from NBA

| Aspect | NBA | CBB |
|--------|-----|-----|
| SLAM tier | Enabled | **Disabled** |
| STRONG threshold | 65% | **70%** |
| LEAN threshold | 55% | **60%** |
| Composite stats | Allowed | **Blocked** |
| Min minutes | 25 mpg | **20 mpg** |
| Blowout block | 30% | **25%** |

## Critical Controls

1. **Tournament Mode** (March): Overs blocked, confidence capped at 65%
2. **Conference Priors**: Adjusts projections by conference strength
3. **Coach Priors**: Pace and foul tendency multipliers
4. **Ref Bias**: Home/neutral/away adjustments
5. **Auto-Unders**: Switches to unders-only after 1 loss
6. **Seed Volatility**: Variance multipliers for seed gaps

## Enabling Production

CBB is disabled by default. To enable:

1. Complete Phase 6 paper run (≥100 edges, <3% calibration error)
2. Update `config/sport_registry.json`: `"enabled": true`
3. Change status to `"LIVE_SMALL"`

## SOP Reference

See `docs/SOP_CBB_ADDENDUM.md` for full governance rules.
