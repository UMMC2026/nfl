# Tennis Props Analysis - Standard Operating Procedure (SOP) v1.0

## Overview
Full Monte Carlo simulation engine for tennis player props analysis. Same methodology as NBA system with sport-specific adaptations.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: MONTE CARLO ENGINE — Truth probability calculations   │
│ LAYER 2: EDGE DETECTION — Tier assignment (SLAM/STRONG/LEAN)   │
│ LAYER 3: CHEAT SHEET — Final presentation with recommendations │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Data Layer (`tennis_stats_api.py`)
**Purpose:** Fetch player statistics for Monte Carlo modeling

**Data Sources:**
- PHASE 1: Mock data (testing)
- PHASE 2: ATP/WTA stats API integration (TODO)
- PHASE 3: Historical match data with surface splits

**Stats Tracked:**
- Aces per match (L5, L10, Season, σ)
- Break Points Won per match (L5, L10, Season, σ)
- Games Won per match (L5, L10, Season, σ)
- Fantasy Score per match (L5, L10, Season, σ)

**Metadata:**
- Surface type (Hard/Clay/Grass)
- Opponent strength adjustment
- Sample size (matches played)

**Cache:**
- 24-hour TTL
- Location: `tennis/stats_cache/`
- Format: JSON per player

### 2. Monte Carlo Engine (`tennis_monte_carlo.py`)
**Purpose:** Simulate prop outcomes using statistical distributions

**Methodology:**
1. Normal distribution modeling
2. 10,000+ simulation iterations per prop
3. Variance modeling (σ) from historical data
4. Non-negative constraint (can't have negative aces)

**Output:**
- Mean projection
- Standard deviation
- P(Over line)
- P(Under line)
- Distribution percentiles (P25, P50, P75)
- Confidence level (HIGH/MEDIUM/LOW)

**Confidence Calculation:**
```python
cv = σ / μ  # Coefficient of variation
if sample_size >= 10 and cv < 0.3:
    confidence = "HIGH"
elif sample_size >= 5 and cv < 0.5:
    confidence = "MEDIUM"
else:
    confidence = "LOW"
```

### 3. Edge Detection (`tennis_edge_detector.py`)
**Purpose:** Identify playable edges and assign tiers

**Tier Thresholds:**
- SLAM: ≥75% probability (requires HIGH confidence)
- STRONG: ≥65% probability (requires MEDIUM+ confidence)
- LEAN: ≥55% probability
- PASS: <55% (filtered out)

**Confidence Caps (Variance Penalty):**
- HIGH: 75% max (can reach SLAM)
- MEDIUM: 68% max (max STRONG)
- LOW: 60% max (max LEAN)

**Edge Calculation:**
```
Edge = Capped_Probability - Implied_Odds
```

**Ranking:**
1. Sort by tier priority (SLAM > STRONG > LEAN)
2. Within tier, sort by probability (descending)

### 4. Pipeline Orchestrator (`tennis_props_pipeline.py`)
**Purpose:** Full end-to-end analysis

**Pipeline Steps:**
1. Parse props from Underdog paste
2. Deduplicate (same player/stat/line)
3. Fetch player stats from API
4. Run Monte Carlo simulations
5. Detect edges and assign tiers
6. Generate cheat sheet

**Output:**
- Raw props list
- Unique props (deduplicated)
- Player stats map
- Monte Carlo results (all props)
- Playable edges (SLAM/STRONG/LEAN only)
- Tier count summary

### 5. Cheat Sheet Generator (`generate_tennis_cheatsheet.py`)
**Purpose:** NBA-style cheat sheet presentation

**Format:**
```
🎾 TENNIS PROPS CHEAT SHEET
================================================
📊 SUMMARY: X SLAM | Y STRONG | Z LEAN

🎯 SLAM PICKS (X)
Player - Stat HIGHER/LOWER Line
  Probability: XX% | Edge: +YY%
  Monte Carlo: μ=X.XX, σ=Y.YY
  
🎯 STRONG PICKS (Y)
[same format]

🎯 LEAN PICKS (Z)
[same format]

📈 METHODOLOGY:
  • Monte Carlo simulations...
  • Tier assignment...
================================================
```

**Output Location:** `tennis/outputs/TENNIS_CHEATSHEET_YYYYMMDD_HHMMSS.txt`

## Usage

### Command Line
```bash
# Full pipeline (interactive)
python tennis/tennis_props_pipeline.py

# Paste Underdog props when prompted
# Press Enter twice to submit
```

### Programmatic
```python
from tennis.tennis_props_pipeline import TennisPropsAnalysisPipeline

pipeline = TennisPropsAnalysisPipeline(num_simulations=10000)
results = pipeline.run_full_pipeline(underdog_paste)

edges = results['edges']  # List of TennisEdge objects
tier_counts = results['tier_counts']  # {'SLAM': X, 'STRONG': Y, 'LEAN': Z}
```

### Menu Integration
Option [7] in tennis menu will be added for Monte Carlo props analysis.

## Data Requirements

### Minimum Sample Size
- HIGH confidence: 10+ matches
- MEDIUM confidence: 5+ matches
- LOW confidence: <5 matches

### Stats Priority
1. L10 (last 10 matches) - primary
2. L5 (last 5 matches) - recent form adjustment
3. Season average - fallback

### Surface Adjustments
- Hard court: baseline (1.0x)
- Clay court: serve adjustment (TODO)
- Grass court: serve adjustment (TODO)

## Governance & Safety

### Protected Surfaces
DO NOT modify without v1.1 authorization:
- Tier thresholds (SLAM/STRONG/LEAN)
- Confidence caps (HIGH/MEDIUM/LOW)
- Monte Carlo methodology (normal distribution)
- Edge calculation formula

### Validation Gates
1. **Sample Size Gate:** Warn if <5 matches
2. **Variance Gate:** Cap confidence if high CV
3. **Tier Gate:** No SLAM without HIGH confidence
4. **Edge Gate:** Filter out <55% probability

## Comparison to NBA System

### Similarities
- Monte Carlo simulations (10,000+ iterations)
- Tier system (SLAM/STRONG/LEAN)
- Confidence caps based on variance
- Cheat sheet format
- Pipeline architecture

### Differences
- **Data Source:** Tennis stats API vs nba_api
- **Stats:** Aces/BP/Games vs PTS/REB/AST
- **Adjustments:** Surface vs matchup defense
- **Sample Size:** Matches vs games

## Roadmap

### Phase 1 (COMPLETE)
- ✅ Mock data layer
- ✅ Monte Carlo engine
- ✅ Edge detection
- ✅ Pipeline orchestrator
- ✅ Cheat sheet generator
- ✅ SOP documentation

### Phase 2 (TODO)
- ⏳ Real ATP/WTA stats API integration
- ⏳ Surface-specific adjustments
- ⏳ Opponent strength modeling
- ⏳ Menu integration (option 7)

### Phase 3 (TODO)
- ⏳ Historical backtesting
- ⏳ Calibration tracking
- ⏳ LLM commentary layer
- ⏳ Live match adjustments

## File Locations

```
tennis/
├── tennis_stats_api.py          # Data layer
├── tennis_monte_carlo.py        # Simulation engine
├── tennis_edge_detector.py      # Edge detection & tiers
├── tennis_props_pipeline.py     # Pipeline orchestrator
├── generate_tennis_cheatsheet.py # Cheat sheet generator
├── tennis_props_parser.py       # Underdog paste parser
├── stats_cache/                 # Player stats cache (24hr TTL)
└── outputs/                     # Cheat sheets & reports
    └── TENNIS_CHEATSHEET_*.txt
```

## Critical Rules

1. **Always run Monte Carlo** - Never manually assign probabilities
2. **Respect confidence caps** - Variance penalty is non-negotiable
3. **Filter PASS tier** - Only show SLAM/STRONG/LEAN
4. **Sort by tier first** - Then probability within tier
5. **Cache stats** - Don't hammer API (24hr TTL)

## Support

For questions or issues:
- Review SOP first
- Check NBA system for parallel examples
- Test with mock data before real props
- Validate tier assignments manually

---

**Version:** 1.0  
**Last Updated:** 2026-01-26  
**Status:** Production-ready (mock data), API integration pending
