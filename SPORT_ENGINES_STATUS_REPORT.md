# SPORT ENGINES & PIPELINES — COMPREHENSIVE STATUS REPORT
**Generated:** 2026-02-07  
**Source:** Underdog Analysis System v1.0+

---

## 📊 EXECUTIVE SUMMARY

| Sport | Status | Version | Win Rate | Primary Data | Odds API | Best Feature | Main Limitation |
|-------|--------|---------|----------|--------------|----------|--------------|-----------------|
| **NBA** | ✅ PRODUCTION | v1.0 | 48.5% (97 picks) | nba_api | ✅ Excellent | Monte Carlo optimizer | Over-relies on recency |
| **NHL** | ✅ PRODUCTION | v2.1 | Unknown (new) | nhl_api + NST | ✅ Good | Goalie gates | No SLAM tier |
| **CBB** | ✅ PRODUCTION | v1.1 | Unknown | ESPN + SR | ❌ Rare | Poisson engine | Data gaps (300+ teams) |
| **Tennis** | ✅ PRODUCTION | v1.0 | Unknown | Tennis Abstract | ⚠️ Minimal | Surface adjustments | Manual paste only |
| **Soccer** | ✅ PRODUCTION | v1.0 | Unknown | FBref + Manual | ⚠️ EPL only | Opponent lambda | 27 players only |
| **Golf** | ⚠️ PRODUCTION | v1.0 | Unknown (volatile) | DataGolf + Manual | ❌ None | SG-based modeling | High variance |
| **NFL** | 🔒 FROZEN | v1.0 | Unknown | nflverse | ✅ Excellent | Weather gates | Season over, read-only |

**Legend:**
- ✅ = Fully operational
- ⚠️ = Limited/Development
- ❌ = Not available
- 🔒 = Frozen (read-only)

---

## 🏀 NBA — PRIMARY ENGINE (PRODUCTION)

**Status:** ✅ PRODUCTION v1.0  
**Command:** `.venv\Scripts\python.exe menu.py`

### ✅ PROS
1. **Most mature pipeline** — 5500+ lines in menu.py alone
2. **Live API hydration** — Real-time stats from nba_api (BoxScoreTraditionalV2)
3. **Monte Carlo optimizer** — 10k simulations per entry combination
4. **Specialist detection** — CATCH_AND_SHOOT_3PM, BIG_MAN_3PM, BENCH_MICROWAVE
5. **Calibrated penalties** — 97-pick backtest with stat-specific multipliers
6. **Rich governance** — pick_state machine, 8+ hard gates
7. **Matchup memory** — Player vs opponent history tracking
8. **Odds API integration** — Excellent DFS props coverage
9. **Telegram auto-send** — Top 7 picks broadcast
10. **Professional reports** — NBA-style cheat sheets

### ❌ CONS
1. **Recency bias** — L10 games weighted too heavily (40%)
2. **Win rate below 50%** — 48.5% (47/97) tracked picks
3. **PRA HIGHER miscalibration** — 25% actual vs 60% expected
4. **Combo stats underperform** — PTS+AST, REB+AST at ~42%
5. **API rate limits** — NBA.com returns 429 errors frequently
6. **Cache complexity** — `stats_last10_cache.py` can go stale
7. **Over-penalization risk** — MAX_PENALTY_PERCENT at 25% can zero picks

### 🎯 BEST USE CASES
- Daily DFS props (Underdog, PrizePicks)
- 2-5 leg parlays with Monte Carlo optimization
- High-usage starters (25+ MPG)
- AST props (1.20x multiplier — best edge)
- PRA LOWER (1.40x — 70% historical)

### 🚨 AVOID
- PRA HIGHER (0.50x — only 25% hit rate)
- Combo stats (PTS+AST, REB+AST)
- BENCH_MICROWAVE on PTS/AST props
- BIG_MAN_3PM at line 3.5+ (auto-reject)

### 📁 KEY FILES
- `menu.py` (5500 lines) — Main orchestration
- `risk_first_analyzer.py` — Core analysis engine
- `core/decision_governance.py` — Eligibility gates
- `config/data_driven_penalties.py` — Stat multipliers
- `monte_carlo_optimizer.py` — Entry combinations

---

## 🏒 NHL — GOALIE-CENTRIC ENGINE (PRODUCTION v2.1)

**Status:** ✅ PRODUCTION v2.1  
**Command:** `.venv\Scripts\python.exe sports/nhl/nhl_menu.py`

### ✅ PROS
1. **Goalie-first modeling** — Mandatory GOALIE_CONFIRMED gate
2. **Poisson simulation** — 20k games per matchup
3. **145 players in database** — Good coverage for active NHL
4. **Odds API integration** — Solid DFS props coverage
5. **Small sample penalty** — <5 starts → cap at 58%
6. **B2B goalie adjustment** — -4% penalty for back-to-back
7. **Edge minimum enforced** — 2% edge required to play
8. **NO SLAM tier** — Prevents overconfidence (goalie variance)
9. **Interactive menu** — Professional NHL command center
10. **Multi-source data** — NHL API + NaturalStatTrick + DailyFaceoff

### ❌ CONS
1. **No player props yet** — Only SOG, Saves, team markets (v3.0 planned)
2. **Goalie variance high** — Why SLAM tier disabled
3. **Stricter thresholds** — STRONG=64%, LEAN=58% (harder to qualify)
4. **Goalie confirmation lag** — Requires 2+ sources, delays analysis
5. **Limited historical data** — Newer system, less calibration
6. **Backup goalie cap** — 60% max confidence (conservative)
7. **No live/intermission model** — Planned for v3.0

### 🎯 BEST USE CASES
- Goalie saves props (Underdog, PrizePicks)
- Team totals (over/under goals)
- Shots on goal props
- Matchups with confirmed starter goalies

### 🚨 AVOID
- Player-level props beyond SOG (not supported yet)
- Backup goalies in high-stakes entries
- Small sample goalies (<5 starts)
- B2B scenarios without adjustment

### 📁 KEY FILES
- `sports/nhl/nhl_menu.py` — Interactive command center
- `sports/nhl/player_stats.py` — 145 player database (2025-26)
- `sports/nhl/run_daily.py` — Daily pipeline
- `sports/nhl/process_slate.py` — Quick slate analyzer

---

## 🏀 CBB — COLLEGE BASKETBALL ENGINE (PRODUCTION v1.1)

**Status:** ✅ PRODUCTION v1.1  
**Command:** `.venv\Scripts\python.exe sports/cbb/cbb_main.py`

### ✅ PROS
1. **Poisson-based modeling** — Proper probabilistic framework
2. **NO SLAM tier** — Conservative (max 79%) due to college volatility
3. **Stricter thresholds** — STRONG=70%, LEAN=60% (higher bar)
4. **Blowout detection** — Skips games with >25% spread
5. **Min MPG gate** — 20 minutes required (filters bench)
6. **ESPN + SportsReference** — Dual data sources
7. **Roster averages view** — Team-by-team breakdowns
8. **Archetype filtering** — Role-based player classification
9. **Professional reports** — NBA-style formatting
10. **Telegram integration** — Top 7 picks broadcast

### ❌ CONS
1. **Manual paste only** — Odds API CBB props are rare (March only)
2. **Data gaps** — 300+ teams, many missing stats
3. **Offline mode required** — ESPN blocks scraping frequently
4. **Player overrides needed** — Manual averages when ESPN missing
5. **High volatility** — College players less consistent than NBA
6. **Limited calibration** — Newer system, less historical validation
7. **Conference bias** — ACC/Big Ten covered better than mid-majors
8. **Tournament compression** — Rotation changes in March

### 🎯 BEST USE CASES
- Major conference games (ACC, Big Ten, Big 12)
- High-usage starters (25+ MPG)
- Standard props (PTS, REB, AST)
- Regular season (not March Madness — too volatile)

### 🚨 AVOID
- March Madness props (rotation chaos)
- Mid-major games (data gaps)
- Neutral court games (harder to adjust)
- Tournament basketball (>8 man rotation)

### 📁 KEY FILES
- `sports/cbb/cbb_main.py` (2347 lines) — Full pipeline
- `sports/cbb/ingest/parse_cbb_paste.py` — Paste parser
- `sports/cbb/ingest/cbb_data_provider.py` — ESPN + SR integration
- `sports/cbb/gates/cbb_context_gates.py` — Blowout + MPG gates

---

## 🎾 TENNIS — SURFACE-SPECIFIC ENGINE (PRODUCTION v1.0)

**Status:** ✅ PRODUCTION v1.0  
**Command:** `.venv\Scripts\python.exe tennis/run_daily.py --surface HARD`

### ✅ PROS
1. **Surface-specific models** — HARD/CLAY/GRASS/CARPET adjustments
2. **Monte Carlo simulation** — 10k iterations from Tennis Abstract 2024
3. **Bidirectional parsing** — Both HIGHER + LOWER from same prop
4. **Multiplier extraction** — Reads Underdog multipliers (1.03x, 0.88x)
5. **Match-winner Elo** — Deterministic model for moneylines
6. **SLAM tier enabled** — Tennis=0.82 threshold (higher than NBA)
7. **Governed signals export** — Unified outputs/tennis_signals_latest.json
8. **Telegram/parlays ready** — Both flows read from signals file
9. **Indoor/outdoor split** — Separate coefficients

### ❌ CONS
1. **Manual paste ONLY** — Odds API tennis DFS props minimal (4 markets)
2. **No real-time API** — Tennis Abstract 2024 is annual data
3. **Surface flag REQUIRED** — Pipeline aborts without `--surface`
4. **Limited prop types** — Games Played/Won focus (not aces/DFs via API)
5. **Travel fatigue guessed** — Timezone shift heuristic (-5% >2 zones)
6. **Best-of-3 vs 5 variance** — Different volatility profiles
7. **No live/in-match model** — Pre-match only

### 🎯 BEST USE CASES
- Games Played props (main edge)
- Games Won props
- Surface-specific matchups (clay specialists)
- Major tournaments (better data quality)

### 🚨 AVOID
- Odds API tennis props (only 4 markets: aces, double_faults, games_won, sets_won)
- Challenger/ITF events (data gaps)
- Players with <5 matches on surface
- Best-of-5 matches (higher variance)

### 📁 KEY FILES
- `tennis/run_daily.py` — Daily pipeline entry
- `tennis/calibrated_props_engine.py` — Monte Carlo + paste parser
- `tennis/tennis_main.py` — Match-winner + menu orchestration
- `tennis/tennis_quant_export.py` — Signals export for Telegram/parlays
- `tennis/oddsapi_dfs_props.py` — Limited Odds API ingestion

---

## ⚽ SOCCER — OPPONENT-ADJUSTED ENGINE (PRODUCTION v1.0)

**Status:** ✅ PRODUCTION v1.0  
**Command:** `.venv\Scripts\python.exe soccer/run_daily.py`

### ✅ PROS
1. **Opponent-adjusted lambda** — Adjusts for defense strength, venue, form
2. **8 match context filters** — Derbies, rotation, injuries blocked
3. **Statistical distributions** — Poisson, Zero-Inflated Poisson, Normal, Binomial
4. **Calibration validation** — Brier score, ECE, ROI tracking
5. **5 league support** — EPL, La Liga, Serie A, Bundesliga, Ligue 1
6. **API-Football integration** — Real player stats via RapidAPI
7. **FBref scraping** — Free alternative for EPL stats
8. **Professional reports** — Risk-first structured output
9. **Market efficiency penalties** — Stars + sharp books penalized
10. **Odds API option** — No-scrape ingestion (EPL when available)

### ❌ CONS
1. **Only 27 players in database** — Very limited coverage
2. **Manual paste primary** — Odds API soccer props spotty (EPL only)
3. **API-Football requires paid key** — $10-50/mo subscription
4. **FBref rate limited** — Free scraping is slow
5. **Heavy ESTIMATES** — Falls back to position averages (Avg: 1.2/game)
6. **Duplicate picks issue** — Same player appears twice in reports
7. **Tournament fragmentation** — 100+ leagues/tournaments, separate keys
8. **International coverage weak** — US DFS books prioritize domestic sports

### 🎯 BEST USE CASES
- EPL shots/shots on target props (best data)
- Top 27 database players (real stats, not estimates)
- Big 5 league matches
- API-Football hydrated slates

### 🚨 AVOID
- Relying on ESTIMATES (position-based 1.2/game averages)
- Mid-table or lower league players (no database entry)
- Tournament matches (Copa, Champions League — API keys vary)
- Odds API-only runs without API-Football fetch (gets duplicates + estimates)

### 📁 KEY FILES
- `soccer/run_daily.py` — Daily pipeline
- `soccer/soccer_menu.py` — Interactive command center
- `soccer/api_football_integration.py` — RapidAPI fetcher (BEST DATA SOURCE)
- `soccer/scripts/download_fbref_stats.py` — Free scraper
- `soccer/soccer_props_pipeline.py` — Opponent lambda calculator
- `soccer/test_allsports_api.py` — AllSportsAPI2 evaluation (FAILED — don't use)

---

## ⛳ GOLF — STROKES GAINED ENGINE (PRODUCTION v1.0)

**Status:** ⚠️ PRODUCTION v1.0 (volatile)  
**Command:** `.venv\Scripts\python.exe golf/run_daily.py --dry-run`

### ✅ PROS
1. **Strokes Gained modeling** — SG: Off-the-Tee, Approach, Around-Green, Putting
2. **Course fit emphasis** — Overrides recent form (critical for golf)
3. **Cut-line risk gate** — <60% make-cut → cap at 55%
4. **Field strength normalization** — Adjusts vs field average (not absolute)
5. **Weather wave adjustments** — AM/PM tee time bias
6. **DataGolf integration** — Professional-grade data source
7. **NO SLAM tier** — Golf too volatile (correct decision)
8. **PrizePicks/Sleeper support** — Manual paste ingestion

### ❌ CONS
1. **Extremely volatile** — Golf inherently high variance sport
2. **Manual paste ONLY** — No Odds API golf DFS props
3. **DataGolf requires subscription** — Not free
4. **Course history gaps** — Many players lack history at specific courses
5. **Weather unpredictability** — Wave adjustments are estimates
6. **Cut risk hard to model** — Binary outcome (make/miss cut)
7. **Small sample on course** — Players may have 0-2 rounds at venue
8. **NO SLAM tier means <75% max** — Conservative by design

### 🎯 BEST USE CASES
- Major tournaments (Augusta, St Andrews — more course history)
- SG-based props (not fantasy score — too noisy)
- Players with 3+ rounds at course
- Birdies/Round Strokes props (lower variance than finishing position)

### 🚨 AVOID
- Finishing position props (high variance)
- Players with no course history
- Fantasy score props (too many variables)
- Weather-dependent props without recent forecasts

### 📁 KEY FILES
- `golf/run_daily.py` — Daily pipeline
- `golf/golf_menu.py` — Interactive menu
- `golf/config/course_adjustments.py` — Course fit logic
- `golf/calibration/golf_tracker.py` — Results tracking

---

## 🏈 NFL — FROZEN ENGINE (v1.0 — READ-ONLY)

**Status:** 🔒 FROZEN v1.0 (season over)  
**Command:** `.venv\Scripts\python.exe run_autonomous.py`

### ✅ PROS
1. **Autonomous scheduler** — Set-and-forget daily runs
2. **Weather gates** — Wind >15mph → passing props capped 60%
3. **QB confirmation gate** — No projection without confirmed starter
4. **nflverse integration** — Professional-grade pbp + player stats
5. **Excellent Odds API coverage** — NFL DFS props abundant
6. **Postmortem + regret analysis** — Calibration built-in
7. **Drift detection** — Schedule safeguards prevent bad runs

### ❌ CONS
1. **FROZEN — READ-ONLY** — Season over, no new commits to main
2. **Limited calibration window** — Only 17-week regular season
3. **Playoff variance** — Different from regular season
4. **Weather data requires external source** — Not automated
5. **QB injury risk** — Hard to predict mid-week changes
6. **Roster churn** — Practice squad elevations hard to track

### 🎯 BEST USE CASES
- Historical reference for NFL v2.0 (2026 season)
- Studying autonomous scheduler architecture
- Understanding weather gate implementation

### 🚨 AVOID
- Making new picks (season over)
- Committing changes to main branch
- Using for 2026 season without unfreezing + validation

### 📁 KEY FILES
- `run_autonomous.py` — Scheduler entry point
- `sports/nfl/` — Full pipeline (FROZEN)

---

## 🎯 CROSS-SPORT COMPARISON MATRIX

| Feature | NBA | NHL | CBB | Tennis | Soccer | Golf | NFL |
|---------|-----|-----|-----|--------|--------|------|-----|
| **Monte Carlo** | ✅ 10k | ✅ 20k | ❌ | ✅ 10k | ⚠️ | ❌ | ❌ |
| **Odds API** | ✅ | ✅ | ❌ | ⚠️ | ⚠️ EPL | ❌ | ✅ |
| **Manual Paste** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔒 |
| **Governance** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Calibration** | ✅ 97 picks | ⚠️ New | ⚠️ New | ⚠️ New | ⚠️ New | ⚠️ New | 🔒 |
| **Telegram** | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | 🔒 |
| **SLAM Tier** | ✅ 80% | ❌ None | ❌ None | ✅ 82% | ✅ 78% | ❌ None | ✅ 80% |
| **Database Size** | Large | 145 | Sparse | Sparse | 27 | Sparse | 🔒 |
| **Win Rate** | 48.5% | Unknown | Unknown | Unknown | Unknown | Unknown | 🔒 |

---

## 🔍 KEY INSIGHTS

### 🏆 STRONGEST ENGINES
1. **NBA** — Most mature, best coverage, richest features
2. **NHL** — Excellent goalie modeling, Poisson simulation
3. **CBB** — Solid Poisson framework, conservative thresholds

### ⚠️ NEEDS IMPROVEMENT
1. **Soccer** — Only 27 players, heavy ESTIMATES, duplicate picks
2. **Golf** — High variance, manual only, course history gaps
3. **Tennis** — Manual paste only, no real-time API

### 🎯 CALIBRATION STATUS
- **NBA**: 48.5% (47/97) — **BELOW TARGET** ⚠️
- **All others**: Insufficient data (new systems)

### 📊 DATA SOURCE RELIABILITY
| Source | Sports | Quality | Cost | Reliability |
|--------|--------|---------|------|-------------|
| **Odds API** | NBA, NFL, NHL | ⭐⭐⭐⭐⭐ | Free tier | 95%+ |
| **nba_api** | NBA | ⭐⭐⭐⭐ | Free | 85% (429 errors) |
| **nhl_api** | NHL | ⭐⭐⭐⭐ | Free | 90% |
| **API-Football** | Soccer | ⭐⭐⭐⭐⭐ | $10-50/mo | 95% |
| **FBref** | Soccer | ⭐⭐⭐ | Free | 70% (rate limits) |
| **ESPN** | CBB | ⭐⭐⭐ | Free | 60% (blocks scraping) |
| **Tennis Abstract** | Tennis | ⭐⭐⭐ | Free | Annual data |
| **DataGolf** | Golf | ⭐⭐⭐⭐ | $$ | Requires subscription |

---

## 🚀 RECOMMENDED PRIORITIES

### IMMEDIATE (Fix Critical Issues)
1. **NBA win rate investigation** — 48.5% below 50% baseline
2. **Soccer database expansion** — 27 → 100+ players
3. **Soccer duplicate fix** — Same player appearing twice in reports

### SHORT-TERM (Enhance Existing)
1. **NHL player props** — Expand beyond SOG/Saves (v3.0)
2. **CBB Odds API** — Works only in March, needs better fallback
3. **Tennis API integration** — Beyond Tennis Abstract annual data

### LONG-TERM (New Capabilities)
1. **Live betting models** — NHL intermission, tennis in-match
2. **Multi-sport parlays** — Cross-sport Monte Carlo
3. **Unified calibration dashboard** — All sports in one view

---

## 📌 QUICK REFERENCE

### Daily Workflow Commands
```bash
# NBA (primary)
.venv\Scripts\python.exe menu.py

# NHL
.venv\Scripts\python.exe sports/nhl/nhl_menu.py

# CBB
.venv\Scripts\python.exe sports/cbb/cbb_main.py

# Tennis (surface REQUIRED)
.venv\Scripts\python.exe tennis/run_daily.py --surface HARD

# Soccer
.venv\Scripts\python.exe soccer/run_daily.py

# Golf (dry-run recommended)
.venv\Scripts\python.exe golf/run_daily.py --dry-run
```

### Calibration Reports
```bash
# All sports
.venv\Scripts\python.exe calibration/unified_tracker.py --report

# Specific sport
.venv\Scripts\python.exe calibration/unified_tracker.py --report --sport nba
```

---

**End of Report** | Generated: 2026-02-07 | System: Underdog Analysis v1.0+
