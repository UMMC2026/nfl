# Underdog Fantasy Analyzer (NBA + NFL + CFB) — Quant Props MVP

This repository is a production-oriented scaffold for a **manual-line** Underdog Pick'em workflow:

1. You input Underdog lines (player/stat/line/higher-lower).
2. The system hydrates recent game logs from permitted sources (NBA.com via `nba_api`, nflverse via `nflreadpy`, and CollegeFootballData API for CFB).
3. It prices each leg (P(hit)), ranks picks, and builds optimal 2–8-leg entries under constraints (2+ teams, optional correlation penalties).

## Important Compliance Notes
- This project **does not include ESPN scrapers**. Automated scraping of ESPN pages/endpoints may violate ESPN/Disney terms and is brittle.
- This project **does not scrape Underdog**. You enter lines manually (CLI/JSON/API), which keeps you compliant and stable.

## Quickstart

### 1) Create environment
```bash
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows powershell
# .venv\Scripts\Activate.ps1
```

### 2) Install base dependencies
```bash
pip install -r requirements-base.txt
```

Optional data-source dependencies (recommended):
```bash
pip install -r requirements-extras.txt
```

### 3) Run the CLI
Generate demo lines and rank them:
```bash
python -m ufa.cli rank --demo
```

Build top entries (power or flex):
```bash
python -m ufa.cli build --demo --format power --legs 3
python -m ufa.cli build --demo --format flex --legs 5
```

### 4) Run the API
```bash
uvicorn ufa.api.main:app --reload
```

Then open:
- `GET /health`
- `POST /rank`
- `POST /build`

## Data Hydration
You can hydrate recent values (game logs) using:
- NBA: `nba_api` (no key required)
- NFL: `nflreadpy` (pulls nflverse data)
- CFB: CollegeFootballData API (requires token in `.env`)

Create `.env`:
```env
CFBD_API_KEY=YOUR_TOKEN_HERE
```

## What’s Included
- **Pydantic models** for props/picks/results
- **SQLite + SQLAlchemy** persistence layer (optional; works out of the box)
- **Probability engine** (Normal approximation MVP; swap-in better models later)
- **Entry optimizer** (exact EV enumeration up to 8 legs; constraints + penalties)
- **Rich + Typer CLI** for daily use
- **FastAPI** service for UI integrations

## Next Up (Professional Upgrades)
- League-specific projection models (minutes/usage for NBA; volume/share for NFL/CFB)
- Calibration by market type (over/under thresholds)
- Correlation-aware EV (same-game covariance, copula, or rules + shrinkage)
- Closing-line value (CLV) tracking for model validation
