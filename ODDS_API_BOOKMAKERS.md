# Odds API Bookmaker Configuration

## Current Setup (Default)

```bash
prizepicks,underdog,draftkings,mybookieag,pick6,sleeperspick6
```

## Available DFS Bookmakers via The Odds API

| Bookmaker | Odds API Key | Coverage | Notes |
|-----------|--------------|----------|-------|
| **PrizePicks** | `prizepicks` | NBA, NFL, NHL, MLB, CBB, WNBA | ✅ Primary DFS platform |
| **Underdog Fantasy** | `underdog` | NBA, NFL, NHL, MLB, CBB, Soccer | ✅ Primary DFS platform, multipliers |
| **DraftKings Pick6** | `pick6` | NBA, NFL, NHL, MLB, CBB | ✅ Formerly Sleeper Pick6 |
| **Betr Picks** | `betr_us_dfs` | NBA, NFL, NHL, MLB | ✅ Often has "No Brainer" promos |
| **MyBookie** | `mybookieag` | NBA, NFL, NHL, MLB | ⚠️ Traditional sportsbook, not pure DFS |
| **Sleeper** | `sleeperspick6` | NBA, NFL (limited) | ⚠️ Alias for `pick6`, limited markets |

## NOT Available via Odds API

These platforms do not provide API access via The Odds API:
- ❌ **Dabble** — Social DFS, no API integration
- ❌ **Chalkboard** — Prop tracking tool, not a bookmaker
- ❌ **Fliff** — Not currently supported
- ❌ **Underdog Pick'em (via scraper)** — Use Playwright scraper instead

## Customization

### Option 1: Environment Variable (Recommended)
Add to `.env`:
```bash
# Comma-separated list (no spaces)
ODDS_API_BOOKMAKERS=prizepicks,underdog,pick6,betr_us_dfs
```

### Option 2: Edit Default
Modify [ingestion/prop_ingestion_pipeline.py](ingestion/prop_ingestion_pipeline.py#L611):
```python
bookmakers_s = (
    os.getenv("ODDS_API_BOOKMAKERS")
    or "prizepicks,underdog,pick6,betr_us_dfs,mybookieag"  # ← Edit here
).strip()
```

## CBB Coverage Issue (Feb 16, 2026)

**Why only Syracuse @ Duke had props:**

```
Events: 20 | Events with bookmaker data: 1
```

**Root Cause:**
1. DFS platforms prioritize **marquee matchups** (Duke #3 ranked)
2. Houston game props may not have been posted yet
3. CBB prop availability is **event-dependent**, not sport-wide

**When DFS books post CBB props:**
- **1-3 hours before tip-off** for non-marquee games
- **Morning of game day** for ranked matchups
- **Not at all** for low-profile games

**Workaround:**
```bash
# Check Odds API closer to game time (6pm+ ET for evening CBB)
.venv\Scripts\python.exe sports\cbb\cbb_main.py → [8] Odds API ingest

# OR manually paste from Underdog/PrizePicks
.venv\Scripts\python.exe sports\cbb\cbb_main.py → [1] Paste props
```

## API Quota Management

Each bookmaker adds to your API quota cost:
- **5 bookmakers** = 5x quota usage per event
- **20 events × 5 books** = 100 quota cost

**Optimize for CBB:**
```bash
# .env — use only books that reliably post CBB props
ODDS_API_BOOKMAKERS=prizepicks,underdog,pick6
```

This reduces quota cost while maintaining coverage.

## Testing

```powershell
# Verify current bookmakers
.venv\Scripts\python.exe -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('ODDS_API_BOOKMAKERS', 'DEFAULT'))"

# Test live (uses 1-5 quota units)
.venv\Scripts\python.exe scripts\fuoom_no_scrape_ingest.py --sport BASKETBALL_NCAAB
```

## Playwright Scraper (Fallback)

For platforms not in Odds API:
```bash
# Full auto-scrape (DK Pick6, PrizePicks, Underdog web)
.venv\Scripts\python.exe menu.py → [1A] Auto-Scrape

# Or sport-specific
.venv\Scripts\python.exe sports\cbb\cbb_main.py → [1B] Auto-Ingest
```

This uses browser automation (Playwright) to scrape props directly from DFS platform websites.
