# Golf Odds API Integration — User Guide

## Overview

The Golf Odds API integration provides **readable reports** for golf betting markets without scraping. It supports:

- **Outrights**: Tournament winner odds
- **Matchups**: Head-to-head player comparisons  
- **Conversion**: Automatically converts to golf pipeline props

## Setup

### 1. Get API Key

Visit https://the-odds-api.com/ and sign up for an API key.

### 2. Configure .env

Add your API key to `.env` in the project root:

```env
ODDS_API_KEY=your_key_here
```

## Usage

### Via Golf Menu

```bash
.venv\Scripts\python.exe golf\golf_menu.py
```

Select option **[8] 🛰️ Odds API — Golf Outrights (Majors, no scrape)**

### Menu Options

When you select option [8], you'll see:

```
Select Report Type:
  [1] 📊 Outrights (Tournament Winner)
  [2] 🥊 Matchups (Head-to-Head)
  [3] 📈 All Markets (Outrights + Matchups)
  [4] ⚙️  Convert to Props (for pipeline)
  [0] 🚪 Cancel
```

#### Option 1: Outrights Report

Shows tournament winner odds in a readable table:

```
[TOURNAMENT] The Masters
Commence: 2026-04-09T12:00:00Z
--------------------------------------------------------------------------------

[OUTRIGHTS] Tournament Winner
Player                         Odds       Prob     Book                
--------------------------------------------------------------------------------
Scottie Scheffler              +800       11.1%    DraftKings          
Rory McIlroy                   +1200      7.7%     FanDuel             
Jon Rahm                       +1400      6.7%     BetMGM              
...
```

#### Option 2: Matchups Report

Shows head-to-head player matchups:

```
[HEAD-TO-HEAD MATCHUPS]
--------------------------------------------------------------------------------

Xander Schauffele vs Tommy Fleetwood
  Xander Schauffele: -110
  Tommy Fleetwood: -110
  Book: FanDuel
```

#### Option 3: All Markets

Combines both outrights and matchups in one report.

#### Option 4: Convert to Props

Converts outright winner odds to `finishing_position` props compatible with the golf pipeline:

```json
{
  "player": "Scottie Scheffler",
  "tournament": "The Masters",
  "market": "finishing_position",
  "line": 1.5,
  "direction": "better",
  "better_mult": 9.0,
  "odds": 800,
  "source": "odds_api"
}
```

These props can then be analyzed using the existing golf pipeline with automatic:
- High variance market classification
- Pick state determination (OPTIMIZABLE/VETTED/REJECTED)
- Avoid reason tagging

## Supported Tournaments

The Odds API provides odds for the 4 major golf tournaments:

- **The Masters** (April)
- **PGA Championship** (May)
- **US Open** (June)
- **The Open Championship** (July)

## Output Files

Reports and props are saved to `golf/outputs/`:

- **Reports**: `golf_odds_api_report_YYYYMMDD_HHMMSS.txt`
- **Props**: `golf_odds_api_props_YYYYMMDD_HHMMSS.json`

## Pipeline Integration

When you convert outrights to props (option 4), they automatically integrate with the existing golf pipeline:

1. **High Variance Classification**: Outright winner props (finishing position 1.5) are automatically tagged as `high_variance_market`
2. **Pick State**: Most outrights will be marked as `VETTED` due to probability < 58% threshold
3. **Avoid Reason**: Tagged with appropriate reason (e.g., `high_variance_market`)

### Example Pipeline Flow

```bash
# Step 1: Fetch outrights from Odds API
Run golf menu → [8] → [4] Convert to Props
# Output: golf_odds_api_props_20260215_103047.json

# Step 2: Analyze with golf pipeline
.venv\Scripts\python.exe golf\run_daily.py

# Step 3: View report with VETTED section
The report will show outrights in the VETTED section with:
- Reason: high_variance_market
- Player stats (expected finish, SG data)
- Course adjustments
```

## API Rate Limits

The Odds API has rate limits based on your subscription:

- **Free tier**: 500 requests/month
- **Each fetch**: Uses 1 request per tournament

The integration displays remaining requests after each API call:

```
[ODDS API] Requests used: 12 | Remaining: 488
```

## Troubleshooting

### "ODDS_API_KEY not configured"

**Solution**: Add `ODDS_API_KEY=your_key_here` to `.env` file in project root.

### "No data available"

**Causes**:
1. Tournament not currently active on Odds API
2. Invalid API key
3. Rate limit exceeded

**Solution**: Check API key validity at https://the-odds-api.com/account

### "Import error"

**Solution**: Ensure you're running from project root:
```bash
cd "C:\Users\hiday\UNDERDOG ANANLYSIS"
.venv\Scripts\python.exe golf\golf_menu.py
```

## Advanced Usage

### Standalone Script

Run the parser directly for quick testing:

```bash
.venv\Scripts\python.exe -c "from golf.ingest.odds_api_parser import fetch_and_convert_majors; import os; props, report = fetch_and_convert_majors(os.getenv('ODDS_API_KEY')); print(report)"
```

### Custom Integration

Import the parser in your own scripts:

```python
from golf.ingest.odds_api_parser import (
    fetch_golf_odds,
    parse_outrights,
    generate_readable_report,
)

# Fetch specific tournament
odds_data = fetch_golf_odds(
    api_key="your_key",
    sport_key="golf_masters_tournament",
    markets="outrights,h2h",
)

# Parse and report
outrights = parse_outrights(odds_data)
report = generate_readable_report(outrights, [])
print(report)
```

## What's New

### Readable Reports

Previously, the golf pipeline only supported scraped Underdog/PrizePicks props. Now you get:

- **Tournament winner odds** from all major books
- **Player matchup odds** for head-to-head comparisons
- **Best line shopping** across multiple bookmakers
- **Implied probability calculations** with vig display

### Automatic Classification

Outright winner props are automatically:
- Classified as `high_variance_market`
- Marked as `VETTED` (not OPTIMIZABLE for Monte Carlo)
- Tagged with `avoid_reason` for transparency

This prevents overconfidence in low-probability events while still providing context for tournament favorites.

## Next Steps

After fetching Odds API data:

1. **Compare with Underdog lines**: See if outright winner odds reveal value
2. **Check player statistics**: Use option [5] in golf menu to lookup SG data
3. **Generate professional report**: Use option [P] to create formatted output
4. **Send to Telegram**: Use option [T] to broadcast top picks

## Support

For issues or questions:
- Check `.env` configuration
- Verify API key at https://the-odds-api.com/account
- Review `golf/outputs/` for saved reports

---

**Last Updated**: February 15, 2026  
**Version**: v1.0  
**Module**: `golf/ingest/odds_api_parser.py`
