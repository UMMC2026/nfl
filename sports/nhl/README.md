# NHL Module

**STATUS:** DEVELOPMENT  
**VERSION:** 1.0.0  

This module is **fully isolated** from NBA/NFL/Tennis pipelines.  
Delete this folder to remove NHL with **zero collateral damage**.

## Quick Start

```bash
# Dry run (no output files, no Telegram)
.venv\Scripts\python.exe sports/nhl/run_daily.py --dry-run

# Full run (when enabled in sport_registry.json)
.venv\Scripts\python.exe sports/nhl/run_daily.py --date 2026-02-15
```

## Architecture

```
sports/nhl/
├── config/           # NHL-specific thresholds, team metadata
├── ingest/           # Data ingestion (schedule, goalies, xG)
├── goalies/          # Goalie confirmation gate (CRITICAL)
├── models/           # xG model, Poisson simulation
├── gates/            # Hard gates (goalie, sample, B2B, edge)
├── outputs/          # Generated reports
├── run_daily.py      # Main entry point
└── validate_output.py
```

## Key Differences from NBA

| Aspect | NBA | NHL |
|--------|-----|-----|
| SLAM tier | Enabled | **Disabled** |
| STRONG threshold | 65% | **64%** |
| LEAN threshold | 55% | **58%** |
| Primary driver | Player usage | **Goalie** |
| Simulation | Monte Carlo | **Poisson** |
| Hard gate | Roster | **Goalie confirmed** |

## Critical Gate: Goalie Confirmation

**NO PLAY without confirmed goalie from ≥2 sources.**

Sources checked:
1. DailyFaceoff.com
2. Team beat reporters
3. NHL official channels

## Enabling Production

NHL is disabled by default. To enable:

1. Complete 50-game paper trading
2. Achieve Brier score ≤ 0.24
3. Update `config/sport_registry.json`: `"NHL": {"enabled": true}`
4. Change status to `"LIVE_SMALL"`

## See Also

- [SOP_NHL_v1.0.md](SOP_NHL_v1.0.md) — Full governance rules
- [../../config/thresholds.py](../../config/thresholds.py) — Tier definitions
