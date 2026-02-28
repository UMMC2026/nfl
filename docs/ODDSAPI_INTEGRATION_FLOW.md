# OddsAPI Integration Flow — How It Works Together

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION                             │
│                        (menu.py Option [1])                          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   PROP INGESTION PIPELINE                            │
│          (ingestion/prop_ingestion_pipeline.py)                      │
│                                                                       │
│  • Checks for ODDS_API_KEY in .env                                   │
│  • Calls run_odds_api(sport="NBA")                                   │
│  • Supports NBA, CBB, NHL, Soccer, Tennis, Golf                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ODDS API CLIENT                                 │
│                   (src/sources/odds_api.py)                          │
│                                                                       │
│  1. Fetch sports list              → GET /v4/sports                  │
│  2. Fetch events (games today)     → GET /v4/sports/{sport}/events  │
│  3. For each event:                                                  │
│     • Fetch player props            → GET /events/{id}/odds          │
│     • Parse markets (points, rebounds, assists, etc.)                │
│  4. Participant validation          → Validate against rosters       │
│  5. Quota logging                   → Track API usage                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PROP NORMALIZATION                              │
│                   (ingestion/prop_ingestion_pipeline.py)             │
│                                                                       │
│  • Convert OddsAPI format → Standard format                          │
│    - player_points → "points"                                        │
│    - player_rebounds → "rebounds"                                    │
│    - player_assists → "assists"                                      │
│    - player_threes → "3pm"                                           │
│    - player_points_rebounds_assists → "pra"                          │
│  • Add metadata (source, timestamp, bookmaker)                       │
│  • Save to outputs/props_latest.json                                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PROP VALIDATION                                 │
│                        (FUOOM Stage 2)                               │
│                                                                       │
│  • Check for duplicate props                                         │
│  • Validate player names                                             │
│  • Ensure all required fields present                                │
│  • Flag suspicious lines                                             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ACTIVE SLATE SETTING                              │
│                      (menu.py global)                                │
│                                                                       │
│  • Sets _ACTIVE_PROPS_FILE = "props_latest.json"                    │
│  • Menu option [2] now analyzes these props                          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼ [User selects [2] Analyze Slate]
┌─────────────────────────────────────────────────────────────────────┐
│                   RISK-FIRST ANALYSIS PIPELINE                       │
│                    (risk_first_analyzer.py)                          │
│                                                                       │
│  STEP 1: Load props from outputs/props_latest.json                   │
│  STEP 2: For each prop:                                              │
│    • Fetch player stats (last 10 games)                              │
│    • Calculate mu (mean), sigma (std dev)                            │
│    • Get matchup context (pace, defense rating)                      │
│  STEP 3: Risk Gates (engine/)                                        │
│    • Schedule Gate    → Games today?                                 │
│    • Roster Gate      → Active players only                          │
│    • Injury Gate      → Remove OUT/DTD players                       │
│    • Bias Gate        → Check Higher/Lower imbalance                 │
│  STEP 4: Probability Calculation                                     │
│    • P(X > line) = 1 - Φ((line - mu) / sigma)                       │
│    • Apply specialist caps (3PM, PRA, etc.)                          │
│    • Apply data-driven penalties (calibration)                       │
│  STEP 5: Decision Governance (core/)                                 │
│    • Tier classification (SLAM/STRONG/LEAN)                          │
│    • Pick state (OPTIMIZABLE/VETTED/REJECTED)                        │
│    • Edge collapse (combine similar props)                           │
│  STEP 6: Output Generation                                           │
│    • Save to outputs/signals_latest.json                             │
│    • Generate reports (cheat sheets, narratives)                     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   MONTE CARLO OPTIMIZATION                           │
│                      (menu.py Option [3])                            │
│                                                                       │
│  • Run 10k simulations per parlay combo                              │
│  • Only OPTIMIZABLE picks participate                                │
│  • Output: Best 2-6 leg parlays with EV                              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      TELEGRAM BROADCAST                              │
│                    (telegram_push.py)                                │
│                                                                       │
│  • Send top picks to Telegram channel                                │
│  • Include tier, probability, risk flags                             │
│  • Idempotency check (no duplicates)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

## 🔑 Key Components

### 1. OddsAPI Client (`src/sources/odds_api.py`)
**Purpose**: Fetch player props from The-Odds-API.com without browser scraping

**Key Functions**:
- `oddsapi_fetch_player_props(sport, api_key)` - Main entry point
- `get_sports()` - List available sports
- `get_markets(sport)` - List prop markets for a sport
- `get_event_odds(event_id, markets)` - Fetch props for specific game
- Participant validation - Verify players against rosters
- Quota logging - Track API usage to CSV

**Configuration** (`.env`):
```bash
ODDS_API_KEY=your_key_here
ODDS_API_REGIONS=us_dfs        # Default: DFS books (PrizePicks, Underdog)
ODDS_API_BOOKMAKERS=prizepicks,underdog,draftkings
ODDS_API_MARKETS=all           # Or comma-separated: player_points,player_assists
```

### 2. Ingestion Pipeline (`ingestion/prop_ingestion_pipeline.py`)
**Purpose**: Normalize props from OddsAPI into standard format

**Input (OddsAPI format)**:
```json
{
  "bookmaker": "prizepicks",
  "market": "player_points",
  "outcomes": [
    {
      "name": "LeBron James",
      "description": "Over",
      "price": 0.0,
      "point": 25.5
    }
  ]
}
```

**Output (Standard format)**:
```json
{
  "player": "LeBron James",
  "stat": "points",
  "line": 25.5,
  "direction": "higher",
  "team": "LAL",
  "opponent": "GSW",
  "source": "OddsAPI",
  "bookmaker": "prizepicks",
  "market": "player_points",
  "timestamp": "2026-02-20T10:30:00Z"
}
```

**Key Functions**:
- `run_odds_api(sport)` - Main entry point called by menu
- `_try_import_odds_api()` - Dynamic import of OddsAPI client
- Market mapping - Convert OddsAPI keys to repo stat names
- Deduplication - Remove duplicate props across bookmakers

### 3. Risk-First Analyzer (`risk_first_analyzer.py`)
**Purpose**: Calculate probabilities and apply governance rules

**Data Flow**:
```
props_latest.json
    ↓
Load props
    ↓
Fetch player stats (NBA API / ESPN)
    ↓
Calculate mu, sigma (mean, std dev)
    ↓
Apply risk gates (schedule, roster, injury, bias)
    ↓
Calculate P(X > line) using normal distribution
    ↓
Apply specialist caps (3PM ≤70%, PRA LOWER ≤62%)
    ↓
Apply data-driven penalties (calibration multipliers)
    ↓
Classify tier (SLAM/STRONG/LEAN)
    ↓
Determine pick state (OPTIMIZABLE/VETTED/REJECTED)
    ↓
signals_latest.json
```

**Key Fields**:
- `mu` (Recent Avg) - Player's last 10-game average
- `sigma` (σ) - Standard deviation
- `sample_n` (n) - Number of games in sample
- `probability` - P(X > line) percentage
- `tier` - SLAM (75%+) / STRONG (65%+) / LEAN (55%+)
- `pick_state` - OPTIMIZABLE / VETTED / REJECTED

### 4. Menu System (`menu.py`)
**Purpose**: Interactive CLI for entire workflow

**OddsAPI Flow Options**:
- `[1]` Ingest New Slate → Calls `run_odds_api()` → Saves props_latest.json
- `[2]` Analyze Slate → Calls `analyze_slate()` → Runs risk_first_analyzer.py
- `[3]` Monte Carlo → Optimizes parlay combos
- `[T]` Telegram → Broadcasts picks

**State Management**:
- `_ACTIVE_PROPS_FILE` - Currently loaded props file
- `_ACTIVE_SLATE_CONTEXT` - Metadata (timestamp, prop count, sport)

## 📈 Data Flow Example

### Step-by-Step: NBA Props via OddsAPI

1. **User Action**: Select `[1]` Ingest New Slate from menu

2. **API Call**: 
   ```
   GET https://api.the-odds-api.com/v4/sports/basketball_nba/events
   → Returns: 10 games today (20 teams)
   
   For each game:
     GET /v4/sports/basketball_nba/events/{event_id}/odds
       ?regions=us_dfs
       &markets=player_points,player_rebounds,player_assists
       &bookmakers=prizepicks,underdog
   → Returns: ~200-300 props per game
   ```

3. **Normalization**:
   - OddsAPI returns nested structure with bookmakers/markets/outcomes
   - Pipeline flattens to one record per prop
   - Converts market keys: `player_points` → `"points"`
   - Adds metadata: sport, timestamp, source

4. **Participant Validation**:
   - ESPN roster fetcher called (now fixed!)
   - Validates each player name against active rosters
   - Flags/removes players not on rosters
   - Corrects team assignments (e.g., traded players)

5. **Save**:
   ```
   outputs/props_latest.json (645 props)
   outputs/props_combined.json (historical archive)
   data/raw/scraped/oddsapi_nba_20260220_103045.json (audit trail)
   ```

6. **Menu Updates**:
   - Sets `_ACTIVE_PROPS_FILE = "props_latest.json"`
   - Shows: "✓ Loaded 645 props (NBA) from OddsAPI"
   - Prompts: "Run [2] Analyze Slate?"

7. **User Action**: Select `[2]` Analyze Slate

8. **Analysis Pipeline**:
   - Loads 645 props from props_latest.json
   - Fetches player stats (now via ESPN API, 525 players)
   - Calculates mu/sigma for each prop
   - Applies risk gates:
     * Schedule Gate: ✓ 10 games today
     * Roster Gate: ✓ 525 players active, 64 OUT, 5 DTD
     * Injury Gate: Removed 87 props (players OUT)
     * Bias Gate: ✓ 52% Higher / 48% Lower (balanced)
   - Calculates probabilities (normal distribution)
   - Applies governance:
     * 3PM specialist cap: 15 props capped at 70%
     * PRA LOWER specialist: 8 props boosted to 62%
     * Data-driven penalties: AST +20%, PRA LOWER +40%
   - Classifies tiers:
     * SLAM (75%+): 12 picks
     * STRONG (65-75%): 38 picks
     * LEAN (55-65%): 95 picks
     * AVOID (<55%): 413 props REJECTED

9. **Output**:
   ```
   outputs/signals_latest.json (145 edges)
   outputs/NBA_REPORT_20260220_103512.txt (cheat sheet)
   outputs/NBA_NARRATIVE_20260220_103512.md (AI commentary)
   ```

10. **Monte Carlo** (if user selects [3]):
    - Simulates 10k games per parlay combo
    - Tests 2-leg, 3-leg, 4-leg, 5-leg, 6-leg parlays
    - Only OPTIMIZABLE picks participate (85 picks)
    - Outputs best combos with EV estimates

11. **Telegram** (if user selects [T]):
    - Sends top 10 picks to Telegram channel
    - Format: `🔥 LeBron James — PTS 25.5 HIGHER (72% STRONG)`
    - Includes risk flags if any

## 🔧 Configuration Reference

### Required `.env` Variables
```bash
# OddsAPI (required for no-scrape ingestion)
ODDS_API_KEY=your_api_key_here

# Optional OddsAPI settings (defaults shown)
ODDS_API_REGIONS=us_dfs                    # us, us_dfs, uk, eu, au
ODDS_API_BOOKMAKERS=prizepicks,underdog    # Comma-separated
ODDS_API_MARKETS=all                       # Or: player_points,player_assists

# ESPN Roster (now used instead of stats.nba.com)
# No API key needed - public endpoint

# Telegram (optional for broadcasts)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Supported Sports & Markets

| Sport | OddsAPI Sport Key | Supported Markets |
|-------|-------------------|-------------------|
| NBA | `basketball_nba` | points, rebounds, assists, 3pm, blocks, steals, pra, pts+ast, pts+reb, reb+ast |
| CBB | `basketball_ncaab` | Same as NBA |
| NHL | `icehockey_nhl` | sog, saves, goals, points, assists, blocked_shots, pp_points |
| Tennis | `tennis_atp`, `tennis_wta` | aces, double_faults, games_won, sets_won |
| Soccer | `soccer_epl`, `soccer_mls`, etc. | shots, shots_on_target, assists |
| Golf | `golf_masters`, `golf_us_open`, etc. | finishing_position (via odds conversion) |

## 🚨 Common Issues & Solutions

### Issue: "✗ Odds API ingest returned 0 props"
**Causes**:
1. Bookmakers haven't posted props yet (typical <4 hours before games)
2. Wrong region (e.g., UK books don't offer US DFS props)
3. API quota exhausted (check quota log)
4. Participant validation filtering all props (now fixed!)

**Solutions**:
- Wait closer to game time (4-6 hours before tipoff)
- Check `ODDS_API_REGIONS` and `ODDS_API_BOOKMAKERS` in .env
- Review quota log: `outputs/oddsapi_quota_log.csv`
- Bypass validation: `ODDS_API_SKIP_PARTICIPANT_VALIDATION=1`

### Issue: "Loaded 17 players instead of 525"
**Cause**: stats.nba.com blocking automated requests

**Solution**: ✅ FIXED - Now using ESPN API roster fetcher
- [engine/roster_gate.py](engine/roster_gate.py) updated
- Fetches all 30 teams reliably
- No auth required, never blocks

### Issue: "More Anthony Edwards" in output
**Cause**: Paste parser bug (section headers included)

**Solution**: Use OddsAPI ingestion (Option [1]) instead of paste parser
- OddsAPI returns clean player names
- No manual parsing needed
- Validate before analysis (FUOOM Stage 2)

### Issue: Tier misalignment (48.5% hit rate on SLAM tier)
**Cause**: Math errors (hardcoded Kelly, double-counted home advantage, wrong thresholds)

**Solution**: Math fixes pending (priority after roster fix)
- Dynamic Kelly criterion
- Single home advantage application
- Tier threshold audit (0.90→0.75, 0.80→0.65, 0.70→0.55)
- NFL Poisson model (replace Normal distribution)

## 📊 Quota Management

OddsAPI charges per request × markets × regions. Track usage:

```bash
# View quota log
cat outputs/oddsapi_quota_log.csv

# Current month usage
python -c "import pandas as pd; df = pd.read_csv('outputs/oddsapi_quota_log.csv'); print(df[df['timestamp'].str.startswith('2026-02')]['requests_used'].sum())"

# Average cost per slate ingest
python -c "import pandas as pd; df = pd.read_csv('outputs/oddsapi_quota_log.csv'); print(df['last_request_cost'].mean())"
```

**Cost Estimates**:
- NBA slate (10 games, 5 markets): ~50-100 requests
- Free tier: 500 requests/month
- Paid tier: $99/mo for 10k requests

## 🎯 Next Steps

1. ✅ **ESPN Roster Fix** - COMPLETE (30/30 teams, 525 players)
2. ⏳ **Math Fixes** - IN PROGRESS (tier thresholds, Kelly, home advantage)
3. ⏳ **"More" Prefix Bug** - Audit paste parser (secondary issue)
4. 🔮 **Data Warehouse** - DEFERRED (after math fixes validated)

## 🔗 Related Documentation

- [POSTGAME_INGESTION.md](../POSTGAME_INGESTION.md) - Auto-resolve results via OddsAPI
- [ODDS_API_BOOKMAKERS.md](../ODDS_API_BOOKMAKERS.md) - Bookmaker configuration
- [FUOOM_GUIDELINES.md](../FUOOM_GUIDELINES.md) - No-scrape ingestion standards
- [CALIBRATION_COMPLETE.md](../CALIBRATION_COMPLETE.md) - Data-driven penalties
- [copilot-instructions.md](../.github/copilot-instructions.md) - Full system architecture
