# Underdog Fantasy Analyzer (UFA) - AI Copilot Instructions

Sports prop betting analysis system supporting **NBA, NFL, CFB**. Manual line input → data hydration from external APIs → probability calculation → entry optimization for Underdog Pick'em (2-8 leg power/flex formats).

## Architecture at a Glance

**UFA is a three-tier system:**

1. **Input Layer**: `ufa/models/schemas.py` - Pydantic models for `PropPick` (manual lines: player/stat/line/direction), `RankRequest`, `BuildRequest`
2. **Analysis Layer**: `ufa/analysis/` - Probability math (`prob_hit()` with Normal CDF), EV calculation (`entry_ev()` via itertools), payout tables by league/format
3. **Optimization Layer**: `ufa/optimizer/entry_builder.py` - Combinatorial entry builder with constraints (min 2 teams, max player/team legs, correlation penalties)
4. **Delivery**: CLI (`ufa/cli.py` via Typer) and FastAPI (`ufa/api/main.py`) endpoints

**Data Flow**: Manual Lines (JSON/CLI) → `PropPick` validation → `hydrate_recent_values()` (from `ufa.ingest.espn`, `nba_api`, `nflreadpy`, CollegeFootballData) → `prob_hit()` [Normal CDF] → `build_entries()` [combinatorial EV] → ranked/optimized entries

## Key Decision Points (Why This Design)

- **Manual Line Input**: Ensures compliance (no Underdog scraping). You control pins; system hydrates context.
- **League-Agnostic Probability**: `prob_hit(line, direction, recent_values=[...] | mu/sigma)` works for all sports via Normal approximation; swap for better distributions later.
- **Combinatorial Enumeration**: Exact EV up to 8 legs using `itertools.combinations()`; beats greedy heuristics for small combos.
- **Governance Layer** (`ufa/analysis/prob.py`): Stat classification (CORE=no gate, VOLUME_MICRO/SEQUENCE_EARLY/EVENT_BINARY=capped %) prevents over-confident alt-stats picks.
- **Roster Gate** (`data_center/guards/roster_gate.py`): Hard constraint on player eligibility; rosters in `data_center/rosters/` with columns `player_name, team, status, game_id, updated_utc`.

## Critical Patterns

### Probability Calculation (MVP)
```python
from ufa.analysis.prob import prob_hit

# Option A: Pass recent game values
p = prob_hit(line=24.5, direction="higher", recent_values=[22, 28, 25, 31, 19])

# Option B: Pass explicit distribution (mu/sigma)
p = prob_hit(line=24.5, direction="higher", mu=25.5, sigma=4.2)
```
Returns `float` in [0, 1]. Uses Normal CDF internally. Stat classification gates alt-stats confidence (e.g., "pass_attempts" capped at 68%).

### Entry Builder (Constraint Solver)
```python
from ufa.optimizer.entry_builder import build_entries
from ufa.analysis.payouts import power_table, flex_table

entries = build_entries(
    picks=[
        {"player": "LeBron", "team": "LAL", "stat": "points", "p_hit": 0.65, ...},
        {"player": "AD", "team": "LAL", "stat": "rebounds", "p_hit": 0.62, ...},
        # ... more picks
    ],
    payout_table=power_table,  # or flex_table
    legs=3,
    min_teams=2,              # Underdog requires ≥2 different teams
    max_player_legs=1,        # Max 1 prop from same player per entry
    max_team_legs=0,          # 0 = no limit
    same_team_penalty=0.1,    # Reduce EV 10% for team stacking
    correlation_groups=[{"players": ["LeBron", "AD"], "props": ["points", "rebounds"]}]  # Same-game correlation
)
# Returns list of dicts: [{"legs": 3, "teams": [...], "players": [...], "p_list": [...], "ev_units": 0.12}, ...]
```

### Data Hydration (League-Agnostic)
```python
from ufa.ingest.hydrate import hydrate_recent_values

# NBA
values = hydrate_recent_values("NBA", "LeBron James", "points", nba_season="2024-25")

# NFL
values = hydrate_recent_values("NFL", "Lamar Jackson", "pass_yds", nfl_seasons=[2024])

# CFB (requires CFBD_API_KEY in .env)
values = hydrate_recent_values("CFB", "Player", "cfb_pass_yds", team="TEX", cfb_year=2024)
```

### Stat Keys by League
- **NBA Single**: `points`, `rebounds`, `assists`, `3pm`, `steals`, `blocks`, `turnovers`
- **NBA Combo**: `pts+reb+ast` (pra), `pts+reb` (pr), `pts+ast` (pa), `stl+blk`, `reb+ast` (ra)
- **NBA Quarter**: `1q_pts`, `1q_reb`, `1q_ast` (special handling)
- **NFL**: `pass_yds`, `rush_yds`, `rec_yds`, `receptions`
- **CFB**: `cfb_pass_yds`, `cfb_rush_yds`, `cfb_rec_yds`

### Payout Tables
All defined in `ufa/analysis/payouts.py`. **Power**: all legs must hit (multiplier per k hits). **Flex**: partial payouts for k ≥ minimum. Update multipliers when Underdog changes them.

## Typical Workflows

### 1. Rank Picks by Probability
```bash
# Demo with pre-loaded lines
python -m ufa.cli rank --demo

# Custom JSON input
python -m ufa.cli rank --picks picks.json
```
Outputs ranked picks by P(hit) descending.

### 2. Build Optimized Entries
```bash
python -m ufa.cli build --demo --format power --legs 3
python -m ufa.cli build --demo --format flex --legs 5 --max-entries 50
```
Outputs top EV entries respecting constraints.

### 3. Fetch Live Data & Analyze
```bash
# ESPN NFL teams
python -m ufa.cli fetch --teams "PIT,CLE"

# Player game log
python -m ufa.cli player "Lamar Jackson" --gamelog

# Sleeper integration
python -m ufa.cli sleeper_user <username>
```

### 4. API Endpoints
```bash
uvicorn ufa.api.main:app --reload
# POST /rank { "picks": [...] } → ranked picks
# POST /build { "picks": [...], "legs": 3, "format": "power" } → entries
```

## Environment & Dependencies

Create `.env`:
```env
CFBD_API_KEY=<your_cfbd_token>
```

Install:
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements-base.txt
pip install -r requirements-extras.txt  # nba_api, nflreadpy, scipy
```

## Compliance & Safety

- **No ESPN Scraping**: Use public APIs only (see `ufa/ingest/espn.py` patterns for proper endpoint usage).
- **No Underdog Scraping**: Lines entered manually. Compliant & stable.
- **Roster Gate**: Always provide `--roster-file` for accurate gating. Hard blocker on ineligible players.
- **Stat Classification**: Governance layer prevents alt-stats overconfidence. CORE stats unrestricted; VOLUME/EVENT stats capped at 65-68%.

## Output Files

Scripts write to `outputs/` with pattern: `{action}_{format}_{legs}L_{timestamp}.txt`

## Schema Conventions

- **Direction**: Always string `"higher"` or `"lower"` (not enum).
- **League**: `"NBA"`, `"NFL"`, or `"CFB"` (exact case).
- **Format**: `"power"` or `"flex"`.
- **Stat names**: Lowercase with `+` for combos, `_` for prefixes (`pts+reb`, `1q_pts`, `cfb_pass_yds`).
