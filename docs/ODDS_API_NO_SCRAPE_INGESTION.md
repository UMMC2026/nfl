# Odds API — No-Scrape Prop Ingestion (FUOOM)

This repo’s Playwright scraping is intentionally **not** designed to “fight” Cloudflare/human-verification gates.

If you want an ingestion path that avoids browser automation entirely, you can use **The Odds API (v4)** to pull player prop markets via JSON and feed them into the same FUOOM truth-enforced artifact + validation workflow.

## What this gives you

- No browser automation
- Immutable raw artifacts + `.sha256` sidecars
- Same downstream flow:
  - stage 1: `data/raw/scraped/raw_props_oddsapi_*.json`
  - stage 2: `src/validation/validate_scraped_data.py` → `data/processed/validated_props_*.parquet`
  - menu sets active slate from validated output

## Key limitation (quota math)

In Odds API v4, **player props are “additional markets”** and typically must be queried **one event at a time**:

- List events: `/v4/sports/{sport_key}/events`
- For each event: `/v4/sports/{sport_key}/events/{eventId}/odds?markets=player_points...`

Usage cost is roughly:

$$\text{credits} = (\#\text{unique markets returned}) \times (\#\text{regions}) \times (\#\text{events queried})$$

So on the free tier, keep `ODDS_API_MARKETS` small (the default is `player_points`).

## Configuration

Add these to `.env` (placeholders already appended by the repo):

- `ODDS_API_KEY` (required)
- `ODDS_API_REGIONS` (default: `us_dfs`)
- `ODDS_API_BOOKMAKERS` (default: `pick6,prizepicks,underdog`)
- `ODDS_API_MARKETS` (default: `player_points`)
- `ODDS_API_MAX_EVENTS` (default: `20`)

## How to run (from the main menu)

1. Open `menu.py`
2. Go to **Auto-Scrape Props (Playwright)**
3. Choose:
   - **[9] FUOOM No-Scrape Ingest (Odds API → validate → set slate)**

This will:
- call the Odds API client (`src/sources/odds_api.py`)
- write raw artifacts in `data/raw/scraped/`
- run the validation gate
- set the active slate to the validated output

## Files involved

- `src/sources/odds_api.py` — Odds API client + prop adapter
- `src/scrapers/playwright_scraper.py` — now supports an `oddsapi` platform (no browser required)
- `menu.py` — adds menu option `[9]` for no-scrape ingest

## Troubleshooting

- If you get 0 props:
  - ensure the sport key is in-season
  - keep markets to known keys (start with `player_points`)
  - check the debug file in `data/raw/scraped/debug_oddsapi_*.error.txt`
- If you hit 429 rate limits:
  - reduce `ODDS_API_MAX_EVENTS`
  - increase pacing with `ODDS_API_PACE_S` (seconds)
