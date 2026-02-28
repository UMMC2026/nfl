# ⚽ SOCCER (FUTBOL) SYSTEM STRUCTURE
## Architecture Overview & Capabilities for AI Assistant

**Status:** RESEARCH v1.0 (Manual Inputs Only)  
**Sport:** Soccer/Futbol (International + MLS)  
**Last Updated:** January 29, 2026

---

## 🎯 WHAT THE SOCCER SYSTEM DOES

### ✅ CORE CAPABILITIES

#### 1. **Match Winner & Team Markets Analysis**
- **Markets Supported:**
  - Match Winner (Home/Draw/Away)
  - Over/Under Total Goals (2.5, 3.5)
  - Both Teams to Score (BTTS)
  - Double Chance (Home or Draw, Away or Draw)
  - Asian Handicaps
  
- **Analysis Method:**
  - Dr. Soccer Bayes lambda (λ) estimation
  - Poisson-based scoreline distributions
  - Monte Carlo simulations (10,000 iterations)
  - xG (expected goals) data integration

#### 2. **Player Props Analysis** (Separate Pipeline)
- **Markets Supported:**
  - Shots on Target
  - Goals
  - Assists
  - Tackles Won
  - Passes Completed
  - Fouls Committed
  
- **Analysis Method:**
  - Manual player stats hydration (interactive prompts)
  - Monte Carlo prop simulations
  - Position-based variance modeling
  - Team/opponent context integration

#### 3. **Hard Validation Gates** (SOP v2.1 Compliant)
- Match data completeness check
- Lambda estimation bounds validation
- Market probability sum validation (must equal ~100%)
- Edge schema validation (required fields)
- Audit hash generation for traceability

#### 4. **Tier Assignment System**
```
SLAM:   ≥75% probability (highest confidence)
STRONG: ≥65% probability 
LEAN:   ≥55% probability
NO_PLAY: <55% (filtered out)
```

#### 5. **Output Generation**
- **RISK_FIRST JSON:** Machine-readable edge data
- **Text Reports:** Human-readable analysis with:
  - Match predictions with probabilities
  - Primary recommended market per match
  - Edge values and tier assignments
  - Confidence caps applied
  - Lineage tracking (data source trail)

---

## ❌ WHAT THE SOCCER SYSTEM DOES NOT DO

### 🚫 NO LIVE SCRAPING
- **Does NOT scrape live data** from websites
- No API connections to live odds providers
- No automated data fetching from soccer stats sites
- Requires **manual input** of match data via JSON files

### 🚫 NO LIVE MATCH ANALYSIS
- **Pre-match analysis only**
- Does NOT support in-play betting
- No live score tracking
- No live probability updates during matches

### 🚫 NO AUTOMATED SLATE GENERATION
- **Manual slate creation required**
- User must manually create JSON files with:
  - Match lineups
  - Team xG data
  - Home/away designation
  - Opponent information
  
### 🚫 NO PLAYER STATS AUTO-FETCH
- **Manual player stats hydration**
- Interactive prompts for each player prop
- Optional JSON import of pre-cached stats
- No connection to transfermarkt, fbref, or other stats APIs

### 🚫 NO INJURY/LINEUP SCRAPING
- Does NOT pull injury reports
- No lineup confirmation from official sources
- User responsible for verifying rosters

### 🚫 NO BET PLACEMENT
- System generates recommendations only
- Does NOT place bets automatically
- No integration with sportsbooks
- No bankroll management execution (advisory only)

### 🚫 NO MULTI-MATCH PARLAYS
- **1 primary market per match**
- No automatic parlay construction
- No correlation modeling across matches
- User must manually build multi-leg bets

### 🚫 NO LIVE ODDS MONITORING
- Does NOT track line movement
- No odds comparison across books
- Static line analysis only (from user input)

---

## 📂 SYSTEM STRUCTURE

### Directory Layout
```
soccer/
├── config.py                      # Constants, thresholds, market registry
├── run_daily.py                   # Main match pipeline runner
├── soccer_main.py                 # Interactive menu system
├── soccer_props_pipeline.py       # Player props analysis orchestrator
│
├── gates/
│   └── soccer_gates.py            # Hard validation gates
│
├── models/
│   └── dr_soccer_bayes.py         # Lambda estimation (Bayesian)
│
├── sim/
│   ├── soccer_sim.py              # Match scoreline simulation
│   └── soccer_props_monte_carlo.py # Player props MC engine
│
├── data/
│   └── soccer_stats_api.py        # Player stats store (manual cache)
│
├── ingest/
│   └── soccer_ingest_props.py     # Props text parser (PrizePicks/Underdog)
│
├── render/
│   └── render_soccer_report.py    # Report generation (TXT + JSON)
│
├── inputs/                        # User-created match/prop slates (JSON)
│   ├── slate_example.json
│   └── props_jan29.json
│
├── outputs/                       # Generated reports
│   ├── soccer_report_YYYYMMDD.txt
│   └── soccer_RISK_FIRST_YYYYMMDD.json
│
└── tests/                         # Smoke tests
    ├── test_soccer_smoke.py
    └── test_soccer_props_parser.py
```

---

## 🔧 HOW TO USE THE SOCCER SYSTEM

### **Option 1: Match Winner Pipeline**
```bash
# Interactive menu
python menu.py
# Select Soccer → [1] Run Pipeline

# Direct execution
.venv\Scripts\python.exe soccer\run_daily.py --slate inputs\slate_jan29.json
```

**Requirements:**
- JSON file with match data including:
  ```json
  {
    "home_team": "Manchester City",
    "away_team": "Arsenal",
    "home_xg": 1.8,
    "away_xg": 1.3,
    "league": "Premier League"
  }
  ```

**Output:**
- `outputs/soccer_report_YYYYMMDD.txt` — Human-readable recommendations
- `outputs/soccer_RISK_FIRST_YYYYMMDD.json` — Machine-readable edges

---

### **Option 2: Player Props Pipeline**
```bash
# Interactive menu
python menu.py
# Select Soccer → [4] Analyze Player Props

# Direct execution
.venv\Scripts\python.exe soccer\soccer_props_pipeline.py
```

**Requirements:**
- Paste PrizePicks/Underdog props text, OR
- Provide JSON file with props data
- Interactively input player stats when prompted (or use cached data)

**Output:**
- `outputs/soccer_props_report_YYYYMMDD.txt`
- `outputs/soccer_props_RISK_FIRST_YYYYMMDD.json`

---

## 🧪 TECHNICAL ARCHITECTURE

### Layer 1: Monte Carlo Truth Engine
```
INPUT: Match xG data OR player stats
↓
PROCESS: Dr. Soccer Bayes lambda estimation
         Poisson scoreline distributions
         10,000 Monte Carlo simulations per match/prop
↓
OUTPUT: Probabilities (locked, immutable)
```

### Layer 2: LLM Commentary (DISABLED in v1.0)
```
Soccer system does NOT use LLM layer
All analysis is pure Monte Carlo
No Ollama/GPT integration
```

### Layer 3: Render & Presentation
```
INPUT: MC probabilities + tier assignments
↓
PROCESS: Apply confidence caps
         Format human-readable reports
         Generate RISK_FIRST JSON
↓
OUTPUT: Betting recommendations with disclaimers
```

---

## 📊 CONFIDENCE CAPS (SOP v2.1)

Soccer uses **sport-specific confidence caps** to prevent overconfidence:

```python
CONFIDENCE_CAPS = {
    'HIGH': 0.70,      # Max 70% for high-confidence soccer picks
    'MEDIUM': 0.62,    # Max 62% for medium
    'LOW': 0.58,       # Max 58% for low
}

GLOBAL_CONFIDENCE_CAP = 0.72  # Absolute maximum for any soccer pick
```

**Why Lower Than NBA/Tennis?**
- Soccer has more variance (low-scoring, draw possibility)
- Single goals dramatically shift outcomes
- Poisson modeling has known limitations
- Defensive tactics can nullify statistical edges

---

## 🎯 HARD GATES (Pipeline Aborts)

| Gate | Validation | Aborts When |
|------|-----------|-------------|
| **Match Data Gate** | Required fields present | Missing home_team, away_team, xG |
| **Lambda Bounds Gate** | Lambdas within realistic range | λ < 0.1 or λ > 5.0 |
| **Probability Sum Gate** | Market probs sum to ~100% | Sum deviates >3% from 1.0 |
| **Edge Schema Gate** | Required fields in output | Missing edge_id, tier, probability |
| **Tier Alignment Gate** | Tier matches probability | SLAM tier but prob <75% |

**Gate Failure = Pipeline Abort**  
No recommendations generated if any gate fails.

---

## 🔬 DR. SOCCER BAYES MODEL

### Lambda (λ) Estimation Formula
```
λ_home = xG_home × (1 + HOME_ADV_FACTOR)
λ_away = xG_away × (1 - HOME_ADV_FACTOR × 0.5)

HOME_ADV_FACTOR = 0.15  # 15% boost for home team
```

### Scoreline Distribution (Poisson)
```
P(Home = h, Away = a) = P(h|λ_home) × P(a|λ_away)

Where:
P(k|λ) = (λ^k × e^-λ) / k!
```

### Monte Carlo Simulation
```
For each of 10,000 trials:
  1. Sample home goals from Poisson(λ_home)
  2. Sample away goals from Poisson(λ_away)
  3. Determine match result (Home/Draw/Away)
  4. Calculate derived markets (BTTS, O/U goals)
  
Probability = (Favorable outcomes) / 10,000
```

---

## 📈 PLAYER PROPS VARIANCE MODEL

### Position-Based Variance Multipliers
```python
POSITION_VARIANCE = {
    'FW': 1.5,   # Forwards (high variance in goals)
    'MF': 1.2,   # Midfielders (moderate variance)
    'DF': 0.8,   # Defenders (low variance in defensive stats)
    'GK': 0.6,   # Goalkeepers (very low variance)
}
```

### Sample Size Confidence Adjustment
```python
if sample_size < 5:
    confidence = 'LOW'
    cap_multiplier = 0.85
elif sample_size < 10:
    confidence = 'MEDIUM'
    cap_multiplier = 0.93
else:
    confidence = 'HIGH'
    cap_multiplier = 1.0
```

---

## 🚨 CRITICAL LIMITATIONS

### 1. **Manual Data Entry Required**
- System relies on user to provide accurate xG data
- No automated verification of match information
- User responsible for checking lineups/injuries

### 2. **No Correlation Modeling**
- Each match analyzed independently
- No multi-match parlay correlation
- No player prop correlation within same match

### 3. **Static Model Parameters**
- Home advantage factor fixed at 15%
- Variance multipliers hardcoded
- No dynamic adjustment based on league/tournament

### 4. **No In-Game Context**
- Cannot account for weather conditions
- No referee tendency adjustments
- No crowd size/atmosphere factors

### 5. **Poisson Model Limitations**
- Assumes independent goal events (not always true)
- Doesn't model red cards or injuries mid-match
- May underestimate draw probability in low-scoring matches

---

## 🎮 INTERACTIVE MENU OPTIONS

When you run `python menu.py` and select **Soccer**:

```
[1] Run Pipeline (Match Markets)
    → Analyze match winner + totals from JSON slate
    
[2] View Latest Report
    → Display most recent text report
    
[3] View Latest RISK_FIRST
    → Display most recent JSON output
    
[4] Analyze Player Props
    → Run props pipeline with manual stats
    
[5] Ingest Props (Text Paste)
    → Parse PrizePicks/Underdog format
    
[0] Back to Main Menu
```

---

## 📝 EXAMPLE WORKFLOW

### Match Analysis Workflow
```
1. User creates slate JSON:
   {
     "matches": [
       {
         "home_team": "Liverpool",
         "away_team": "Chelsea",
         "home_xg": 2.1,
         "away_xg": 1.4,
         "league": "Premier League"
       }
     ]
   }

2. Run pipeline:
   python soccer/run_daily.py --slate inputs/my_slate.json

3. System outputs:
   ✓ Lambda home: 2.42 (2.1 × 1.15)
   ✓ Lambda away: 1.30 (1.4 × 0.93)
   ✓ MC simulation: 10,000 trials
   ✓ Home Win: 68% → STRONG tier
   ✓ Over 2.5 Goals: 71% → STRONG tier
   ✓ BTTS: 64% → LEAN tier
   
4. User reviews report:
   outputs/soccer_report_20260129.txt
   
5. User manually places bets based on recommendations
```

---

## 🔐 GOVERNANCE & COMPLIANCE

### SOP v2.1 Alignment
- ✅ Three-layer architecture (MC → No LLM → Render)
- ✅ Immutable Monte Carlo probabilities
- ✅ Hard validation gates
- ✅ Tier thresholds enforced
- ✅ Audit trail via lineage tracking
- ✅ Confidence caps prevent overconfidence

### What Makes Soccer Different
- **Lower confidence caps** than NBA/Tennis (more variance)
- **No LLM layer** (pure statistical)
- **Manual inputs only** (no scraping)
- **1 primary market per match** (no auto-parlays)

---

## 🛠️ DEPENDENCIES

### Python Packages
```
numpy       # MC simulations
scipy       # Poisson distributions
dataclasses # Type safety
pathlib     # File handling
```

### Internal Modules
```
truth_engine.lineage_tracer  # Audit trail
config.thresholds            # Tier definitions
```

---

## 🎓 KEY CONCEPTS FOR AI ASSISTANT

### When User Asks About Soccer System:

**✅ CORRECT RESPONSES:**
- "Soccer system supports match markets (winner, totals, BTTS) and player props"
- "Uses Dr. Soccer Bayes model with Poisson distributions and Monte Carlo"
- "Requires manual input of xG data or player stats - no live scraping"
- "Generates pre-match recommendations only, not live betting"
- "Confidence capped at 70-72% due to soccer's inherent variance"

**❌ INCORRECT RESPONSES:**
- "Soccer system scrapes live odds" (NO - manual input only)
- "Can analyze in-play matches" (NO - pre-match only)
- "Auto-generates parlays" (NO - single primary per match)
- "Has LLM commentary layer" (NO - pure MC, no LLM)
- "Supports all soccer markets" (NO - limited to core markets)

### When User Wants to Analyze Soccer Props:

**✅ GUIDE USER TO:**
1. Menu → Soccer → [4] Analyze Player Props
2. Paste props text OR provide JSON
3. Answer interactive prompts for player stats
4. Review generated report in `outputs/`

**❌ DON'T TELL USER:**
- "System will auto-fetch player stats" (NO - manual only)
- "Just paste and it works" (NO - requires stats input)
- "System tracks injuries" (NO - user responsible)

### When User Asks About Improving Soccer Analysis:

**✅ VALID SUGGESTIONS:**
- Expand player stats database with more cached data
- Add league-specific home advantage factors
- Include tournament stage adjustments
- Add referee tendency data (if user provides it)

**❌ INVALID SUGGESTIONS:**
- "Add live scraping" (violates v1.0 design)
- "Use LLM to adjust probabilities" (violates SOP v2.1)
- "Auto-generate parlays" (violates single-primary rule)
- "Remove confidence caps" (violates governance)

---

## 📞 TROUBLESHOOTING GUIDE

### Issue: "No matches parsed"
**Cause:** Invalid JSON format  
**Fix:** Verify JSON has required fields (home_team, away_team, home_xg, away_xg)

### Issue: "Lambda estimation failed"
**Cause:** xG values out of realistic bounds  
**Fix:** Ensure 0.1 < xG < 5.0 for both teams

### Issue: "Probability sum validation failed"
**Cause:** Market probabilities don't sum to ~100%  
**Fix:** Check lambda estimation, verify Poisson calculations

### Issue: "No SLAM tier picks generated"
**Cause:** Low probabilities or strict caps  
**Fix:** Expected - soccer has high variance, SLAM tier is rare

### Issue: "Player stats not found"
**Cause:** Missing cached stats for requested player  
**Fix:** System prompts for manual entry - provide stats interactively

---

## 🎯 SUMMARY FOR AI ASSISTANT

**Soccer System = Manual Research Tool**
- Pre-match analysis only
- Match markets: Winner, Totals, BTTS
- Player props: Goals, Assists, Shots, Tackles
- Monte Carlo simulations (10,000 trials)
- Confidence capped at 70-72% (sport variance)
- **No scraping, no live data, no auto-parlays**
- User provides all input data via JSON or interactive prompts
- Outputs: Text reports + RISK_FIRST JSON
- Hard validation gates enforce data quality
- SOP v2.1 compliant (three-layer architecture)

**Use Cases:**
- Daily match slate analysis (user creates JSON manually)
- Player props from PrizePicks/Underdog (manual stats entry)
- Pre-match research and edge detection
- Educational/backtesting (historical match data)

**NOT For:**
- Live betting (no in-game analysis)
- Automated betting (no sportsbook integration)
- High-frequency trading (too manual)
- Production at scale (manual inputs limit throughput)

---

**Last Updated:** January 29, 2026  
**Version:** 1.0 RESEARCH  
**Maintainer:** UNDERDOG ANALYSIS System  
**Sport Registry Status:** READY (manual inputs only)
