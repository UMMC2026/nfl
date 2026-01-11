# ESPN Integration Guide

## Status: ✅ READY FOR PRODUCTION

The `load_game_results.py` file is now fully integrated with ESPN's public APIs for NBA games.

## What's Implemented

### Core Function: `fetch_game_result(game_id: str)`
- **Input:** ESPN game ID (numeric, e.g., `"401547819"`)
- **Output:** Dictionary with game metadata + player box scores
- **Process:**
  1. Fetches game summary from ESPN API
  2. Checks game status (must be FINAL)
  3. Extracts player stats (points, rebounds, assists, 3pm, steals, blocks, turnovers)
  4. Computes PRA (points + rebounds + assists)
  5. Returns structured JSON

### API Endpoint Used
```
https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?id={game_id}
```

### Example Output
```json
{
  "game_id": "401547819",
  "date": "2026-01-02",
  "status": "FINAL",
  "home_team": "CLE",
  "away_team": "NYK",
  "players": {
    "Darius Garland": {
      "team": "CLE",
      "points": 18.0,
      "rebounds": 2.0,
      "assists": 6.0,
      "pra": 26.0,
      "3pm": 1.0,
      "steals": 1.0,
      "blocks": 0.0,
      "turnovers": 2.0
    }
  }
}
```

## How to Use

### 1. Identify ESPN Game IDs
Find the numeric ESPN game ID for your games:
- Go to ESPN.com → Find the game
- Game URL format: `https://www.espn.com/nba/game?gameId=401547819`
- Extract the number: `401547819`

### 2. Update picks.json
Replace or add `game_id` field with ESPN numeric ID:
```json
{
  "date": "2026-01-03",
  "game_id": "401547819",
  "player_name": "LeBron James",
  "team": "LAL",
  "stat": "points",
  "direction": "OVER",
  "line": 25.5,
  ...
}
```

### 3. Run the Loader
```bash
python load_game_results.py
```

**Output:**
```
======================================================================
GAME RESULTS LOADER
======================================================================

🔍 Finding games needing resolution...
   ✓ 3 unique games

📊 Fetching game results...
   ✓ 401547819
   ✓ 401547820
   ✓ 401547821

💾 Writing to C:\...\outputs\game_results.json...
   ✓ 3 games written

======================================================================
✅ LOADED 3 FINAL GAMES
======================================================================
```

### 4. Run the Resolver
Once game results are loaded:
```bash
python generate_resolved_ledger.py --picks picks.json --results outputs/game_results.json
```

## Testing Without Real Games

If you want to test the full pipeline without waiting for real games to finalize:

### Option A: Use Mock Data
```bash
# Generate mock picks + results
python test_resolved_ledger.py

# Run resolver with mocks
python generate_resolved_ledger.py --picks picks_mock.json --results outputs/game_results_mock.json
```

### Option B: Manually Create game_results.json
Create `outputs/game_results.json` manually:
```json
{
  "401547819": {
    "game_id": "401547819",
    "date": "2026-01-03",
    "status": "FINAL",
    "home_team": "CLE",
    "away_team": "NYK",
    "players": {
      "LeBron James": {
        "team": "LAL",
        "points": 28.0,
        "rebounds": 8.0,
        "assists": 7.0,
        "pra": 43.0,
        ...
      }
    }
  }
}
```

Then run resolver as normal.

## Error Handling

### "No games found"
- Check picks.json has `game_id` field
- Verify game_id is ESPN numeric format

### "Game not finalized"
- ESPN returns None if game status is not FINAL
- Wait for the game to finish, then retry

### "Player not found in results"
- ESPN may have different player name spellings
- Check ESPN box score for exact spelling
- Update player_name in picks.json to match

## Next Steps

1. **Identify your game IDs** from ESPN.com
2. **Update picks.json** with ESPN numeric IDs  
3. **Run `python load_game_results.py`** after games finish
4. **Run resolver** automatically via `ledger_pipeline.py`

## Architecture Integration

```
picks.json (with ESPN game_ids)
    ↓
load_game_results.py
    ↓
outputs/game_results.json (ESPN box scores)
    ↓
generate_resolved_ledger.py
    ↓
reports/RESOLVED_PERFORMANCE_LEDGER.md
```

---

**Status: ✅ PRODUCTION READY**

ESPN integration is complete and tested. Ready for live game data.
