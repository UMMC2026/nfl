# Automated Postgame Result Ingestion

## Overview

The automated postgame result ingestion system fetches completed game scores and player stats from OddsAPI and NBA API, then automatically updates pick results in the calibration tracker.

**Status:** ✅ NBA implemented | ⚠️ NHL/Tennis/Golf pending

---

## How It Works

1. **Fetch Completed Games** — Query OddsAPI `/scores` endpoint for games that finished in the last N days
2. **Extract Results** — Parse game scores and identify completed matchups
3. **Fetch Player Stats** — Retrieve box scores from sport-specific APIs (NBA API, NHL API, etc.)
4. **Match Picks** — Find outstanding picks (no result yet) from calibration tracker
5. **Update Results** — Call `unified_tracker.update_result()` with actual stat values
6. **Calculate Brier** — Auto-compute Brier scores and hit/miss outcomes

---

## Usage

### Command Line

```bash
# NBA (default) - ingest yesterday's completed games
.venv\Scripts\python.exe scripts\ingest_postgame_results.py

# Dry run (preview without saving)
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --dry-run

# Look back 2 days
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --days 2

# Other sports
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --sport icehockey_nhl
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --sport tennis_atp

# Verbose logging
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --verbose
```

### Programmatic

```python
from src.sources.odds_api_results import OddsApiResultsIngester

# Initialize for NBA
ingester = OddsApiResultsIngester(sport_key="basketball_nba")

# Run ingestion
stats = ingester.run_auto_ingestion(days_from=1, dry_run=False)

print(f"Updated {stats['picks_updated']} picks")
print(f"Skipped {stats['picks_skipped']} picks")
```

---

## Integration Points

### OddsAPI Endpoints
- **`/v4/sports/{sport}/scores`** — Fetch completed game scores (1 request per call)
- Cost: 1 request per call (very quota-friendly)

### Sport-Specific Box Scores

| Sport | Data Source | Implementation | Status |
|-------|-------------|----------------|--------|
| **NBA** | `nba_api.stats.endpoints.BoxScoreTraditionalV2` | `NBABoxScoreFetcher` | ✅ Complete |
| **NHL** | NHL API game feed (`/api/v1/game/{id}/feed/live`) | `NHLBoxScoreFetcher` | ⚠️ Pending |
| **Tennis** | Sackmann datasets / ATP-WTA APIs | `TennisMatchScoreFetcher` | ⚠️ Pending |
| **Golf** | DataGolf API | `GolfTournamentScoreFetcher` | ⚠️ Pending |

### Calibration Tracker
- **Input:** `CalibrationPick` objects with `actual=None` (outstanding)
- **Output:** Updated picks with `actual`, `hit`, and `brier` values
- **Storage:** `calibration/calibration_history.csv`

---

## NBA Implementation Details

### Game ID Resolution
1. Query `LeagueGameFinder` with team abbreviation + date
2. Extract `GAME_ID` for box score fetch

### Box Score Parsing
```python
# Fetch box score
box = BoxScoreTraditionalV2(game_id=game_id)
player_stats = box.player_stats.get_data_frame()

# Map to canonical stats
stats = {
    "points": row['PTS'],
    "rebounds": row['REB'],
    "assists": row['AST'],
    "3pm": row['FG3M'],
    "blocks": row['BLK'],
    "steals": row['STL'],
    "turnovers": row['TO']
}

# Computed combos
stats["pra"] = stats["points"] + stats["rebounds"] + stats["assists"]
stats["blocks+steals"] = stats["blocks"] + stats["steals"]
```

### Team Abbreviation Mapping
**Critical:** OddsAPI returns full team names (e.g., "Los Angeles Lakers"), but NBA API requires abbreviations (e.g., "LAL").

**TODO:** Add team name → abbreviation mapping table for robust team resolution.

---

## Workflow Examples

### Daily Automated Ingestion (Cron)

```bash
# Run every morning at 6 AM to ingest previous day's results
0 6 * * * /path/to/.venv/Scripts/python.exe scripts/ingest_postgame_results.py --days 1
```

### Manual Backfill

```bash
# Backfill results from last 3 days
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --days 3 --dry-run
# Review output
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --days 3
```

### Integration with Main Menu

**Future Enhancement:** Add menu option:
```
[A] Auto-Ingest Postgame Results
```

---

## Error Handling

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "No completed games found" | No games finished in time window | Increase `--days` parameter |
| "Player X not found in game Y" | Name mismatch (stats vs. props) | Check name normalization logic |
| "No {stat} found for player" | Box score missing stat | Player DNP or stat type unavailable |
| NBA API timeout | Rate limiting | Retry with exponential backoff (built-in) |

### Dry Run Mode
Always test with `--dry-run` first:
```bash
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --dry-run --verbose
```
This shows what *would* be updated without saving changes.

---

## Quota Impact

### OddsAPI Costs
- **Scores endpoint:** 1 request per call (not per event!)
- **Very efficient** — can fetch 10+ completed games for 1 request
- **Recommended frequency:** Once daily (morning after games)

### NBA API Costs
- **Box scores:** 1 request per game
- **Rate limits:** ~20 requests/minute
- Built-in exponential backoff handles throttling

---

## Future Enhancements

### Priority 1: NHL Implementation
```python
class NHLBoxScoreFetcher:
    def fetch_player_stats(self, game_id: str, player_name: str):
        # Use NHL API: https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore
        # Parse skater stats: SOG, goals, assists, blocks
        # Parse goalie stats: saves, goals_against
```

### Priority 2: Team Name Normalization
Create `team_mapping.json`:
```json
{
  "basketball_nba": {
    "Los Angeles Lakers": "LAL",
    "Boston Celtics": "BOS",
    ...
  }
}
```

### Priority 3: Conflict Resolution
If multiple picks exist for same player+stat+game:
- Update all matching picks
- Log conflict warning
- Aggregate confidence-weighted results

### Priority 4: Partial Result Handling
For combo stats (PRA, blocks+steals):
- If individual stats available, compute combo
- If combo unavailable, mark as "incomplete"
- Option to wait for official box score

---

## Testing

### Unit Tests
```bash
pytest tests/test_odds_api_results.py -v
```

### Integration Tests
```bash
# Test with real API (uses quota)
.venv\Scripts\python.exe scripts\ingest_postgame_results.py --days 1 --dry-run --verbose
```

### Validation
After ingestion, verify calibration metrics:
```bash
.venv\Scripts\python.exe calibration\unified_tracker.py --report --sport nba
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  OddsAPI Scores Endpoint                     │
│              /v4/sports/{sport}/scores?daysFrom=1            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Completed Games
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              OddsApiResultsIngester                          │
│  • Extract game results (teams, scores, event IDs)          │
│  • Query outstanding picks from CalibrationTracker          │
│  • Route to sport-specific box score fetchers               │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬───────────
         │               │               │
         ▼               ▼               ▼
┌────────────────┐ ┌────────────┐ ┌────────────┐
│ NBA Fetcher    │ │NHL Fetcher │ │Tennis      │
│ (nba_api)      │ │(NHL API)   │ │(Sackmann)  │
└───────┬────────┘ └─────┬──────┘ └─────┬──────┘
        │                │              │
        └────────────────┼──────────────┘
                         │
                         │ Player Stats
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CalibrationTracker.update_result()              │
│  • Set pick.actual = stat_value                             │
│  • Compute pick.hit (compare actual vs. line + direction)   │
│  • Calculate pick.brier = (probability - hit)²              │
│  • Save to calibration_history.csv                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Related Files

| File | Purpose |
|------|---------|
| `src/sources/odds_api_results.py` | Core ingestion logic |
| `src/sources/odds_api_box_scores.py` | Sport-specific box score fetchers |
| `calibration/unified_tracker.py` | Result storage & tracking |
| `scripts/ingest_postgame_results.py` | CLI wrapper |
| `POSTGAME_INGESTION.md` | This documentation |

---

## Governance Integration

The automated result ingestion respects all governance rules:
- ✅ Only updates picks in `OPTIMIZABLE` or `VETTED` state
- ✅ Never modifies `REJECTED` picks
- ✅ Preserves original probability and tier assignments
- ✅ Computes Brier scores for calibration metrics
- ✅ Logs all updates to audit trail

---

## FAQ

**Q: Will this overwrite manually entered results?**  
A: No. The ingester only updates picks where `actual=None` (outstanding).

**Q: What if a player's box score is missing?**  
A: The pick is skipped and logged. Re-run ingestion later when data is available.

**Q: Can I run this multiple times?**  
A: Yes. It's idempotent — already-resolved picks are skipped.

**Q: How do I validate ingestion worked?**  
A: Check calibration report:
```bash
.venv\Scripts\python.exe calibration\unified_tracker.py --report --sport nba
```

**Q: What about combo stats (PRA, blocks+steals)?**  
A: NBA implementation auto-computes combos from individual stats.

---

## Next Steps

1. ✅ **Test NBA ingestion with real data**
   ```bash
   .venv\Scripts\python.exe scripts\ingest_postgame_results.py --dry-run --verbose
   ```

2. ⏳ **Implement NHL box score fetching** (Priority)
   - Use NHL API game feed endpoint
   - Parse skater and goalie stats

3. ⏳ **Add team name normalization** (Critical for robustness)
   - Create team mapping JSON
   - Handle variations (abbreviations, full names, city-only)

4. ⏳ **Schedule daily cron job** (Automation)
   - Run every morning at 6 AM
   - Email summary on completion
   - Alert on errors

5. ⏳ **Add to main menu** (UX)
   - New option: `[A] Auto-Ingest Results`
   - Show last ingestion timestamp
   - Display picks updated count

---

**Status:** Core framework complete, NBA operational, other sports pending implementation.
