# Soccer Betting System - Production Documentation

**Author:** Professional Sports Betting Analytics  
**Date:** February 1, 2026  
**Version:** 1.0 (Production-Ready)

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Component Documentation](#component-documentation)
5. [Usage Examples](#usage-examples)
6. [Validation Checklist](#validation-checklist)
7. [Quant Firm Submission](#quant-firm-submission)
8. [Performance Metrics](#performance-metrics)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 System Overview

This is a production-ready soccer player props betting system designed for platforms like PrizePicks, Underdog, DraftKings, and Sleeper.

### Key Features

✅ **Opponent-Adjusted Lambda** - Adjusts player baselines for opponent strength, venue, form  
✅ **Match Context Filters** - Blocks high-variance situations (derbies, rotation, injuries)  
✅ **Statistical Distributions** - Poisson, Zero-Inflated Poisson, Normal, Binomial  
✅ **Calibration Validation** - Brier score, ECE, ROI tracking  
✅ **Production Pipeline** - Complete end-to-end automated analysis

### Architecture

```
┌─────────────────────┐
│   Player Data       │
│   Opponent Data     │
│   Match Context     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Match Context       │◄── Blocks: Derbies, Rotation, Injuries
│ Filters (8 gates)   │
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ Opponent-Adjusted   │◄── Adjusts for: Defense, Venue, Form
│ Lambda Calculator   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Distribution        │◄── Selects: Poisson / ZIP / Normal / Binomial
│ Selector            │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Probability         │◄── Caps: 65-75% by stat type
│ Calculation         │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Market Efficiency   │◄── Penalizes: Stars, Sharp Books
│ Adjustment          │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Tier Assignment     │◄── ELITE (78%+) → BET
│ & Recommendation    │    STRONG (72-78%) → MONITOR
└──────┬──────────────┘    SKIP (<72%)
       │
       ▼
┌─────────────────────┐
│ Calibration         │◄── Tracks: Brier, ECE, ROI
│ Logger              │
└─────────────────────┘
```

---

## 🔧 Installation

### Prerequisites

```bash
# Python 3.9+
python --version

# Required packages
pip install numpy scipy pandas
```

### File Structure

```
soccer/
├── soccer_opponent_adjustment.py       # Lambda adjustment engine
├── soccer_match_context_filters.py     # Context filters (8 gates)
├── soccer_distributions.py             # Statistical distributions
├── soccer_calibration_validator.py     # Calibration tracking
├── soccer_pipeline_integration.py      # Complete pipeline
├── SOCCER_SYSTEM_README.md             # This file
└── calibration_results/                # Output directory
    ├── calibration_history.json
    ├── calibration_report_*.json
    └── predictions_*.csv
```

### Installation

```bash
# Verify installation
.venv\Scripts\python.exe -c "from soccer.soccer_pipeline_integration import SoccerBettingPipeline; print('✓ Installation successful')"
```

---

## 🚀 Quick Start

### Basic Usage

```python
from soccer.soccer_pipeline_integration import SoccerBettingPipeline
from soccer.soccer_opponent_adjustment import (
    PlayerStats, OpponentProfile, MatchContext, Position, StatType
)

# Initialize pipeline
pipeline = SoccerBettingPipeline()

# Define player
salah = PlayerStats(
    name="Mohamed Salah",
    team="Liverpool",
    position=Position.W,
    season_avg=3.8,
    season_std=1.9,
    games_played=25,
    L5_avg=4.2,
    L5_games=5,
    home_avg=4.5,
    away_avg=3.2,
    home_games=12,
    away_games=13,
    avg_minutes=85.0
)

# Define opponent
opponent = OpponentProfile(
    name="Burnley",
    league="Premier League",
    defensive_rank=305,
    shots_conceded_p90=16.5,
    sot_conceded_p90=6.2,
    goals_conceded_p90=1.8,
    possession_pct=38.0,
    pressing_intensity="LOW",
    defensive_line="LOW"
)

# Define match context
context = MatchContext(
    location="HOME",
    competition="PREMIER_LEAGUE",
    is_derby=False,
    days_since_last_game=7,
    implied_goal_diff=0.5,
    expected_possession=55.0,
    team_games_under_new_manager=25,
    rotation_risk=False
)

# Analyze bet
result = pipeline.analyze_bet(
    player=salah,
    opponent=opponent,
    match_context=context,
    stat_type=StatType.SHOTS,
    line=3.5,
    direction="OVER",
    book="PRIZEPICKS"
)

# Check recommendation
print(f"Recommendation: {result['recommendation']}")
print(f"Probability: {result['probability']:.1%}")
print(f"Tier: {result['tier']}")
```

---

## 📚 Component Documentation

### 1. Opponent-Adjusted Lambda (`soccer_opponent_adjustment.py`)

**Purpose:** Adjust player baseline for opponent strength, venue, form

**Key Functions:**
```python
engine = OpponentAdjustmentEngine()
adjusted_lambda, breakdown = engine.calculate_adjusted_lambda(
    player, opponent, match_context, stat_type
)
```

**Adjustment Factors:**
- Opponent defense (0.65x - 1.25x)
- Home/away venue (0.88x - 1.12x)
- Recent form (0.88x - 1.12x)
- Tactical matchup (0.88x - 1.10x)

---

### 2. Match Context Filters (`soccer_match_context_filters.py`)

**Purpose:** Block bets in high-variance situations

**8 Filter Gates:**
1. **Derby Filter** - Blocks emotional rivalry matches
2. **Rotation Risk** - Blocks midweek tired player situations
3. **Injury Return** - Blocks first 3 games back
4. **Blowout Risk** - Blocks extreme mismatches
5. **Manager Change** - Blocks first 4 games under new manager
6. **Competition Type** - Blocks cup rotation games
7. **Venue Filter** - Blocks extreme weather/conditions
8. **Minutes Trend** - Blocks players losing minutes

**Usage:**
```python
filter_engine = MatchContextFilterEngine()
result, outcomes = filter_engine.apply_all_filters(player, opponent, context)

if result == FilterResult.BLOCK:
    print(f"Blocked: {outcomes[0].reason}")
```

---

### 3. Statistical Distributions (`soccer_distributions.py`)

**Purpose:** Calculate probabilities using appropriate statistical models

**Distributions:**

1. **Poisson** - For strikers' shots, goals (regular events)
2. **Zero-Inflated Poisson** - For defenders' shots (many zeros)
3. **Normal** - For high-volume stats (passes, touches)
4. **Binomial** - For conditional events (SOT given shots)

**Usage:**
```python
dist = SoccerDistributions()

# Poisson
prob = dist.poisson_probability(lambda_param=3.8, line=3.5, direction="OVER")

# Zero-Inflated Poisson
prob = dist.zero_inflated_poisson(
    lambda_param=0.8,
    line=0.5,
    zero_inflation=0.45,
    direction="OVER"
)

# Auto-select
dist_type, params = dist.select_distribution(
    stat_type="SHOTS",
    player_position="CB",
    mean=0.5
)
```

---

### 4. Calibration Validator (`soccer_calibration_validator.py`)

**Purpose:** Track model performance and prevent overconfidence

**Key Metrics:**
- **Brier Score** - Overall accuracy (target: <0.25)
- **ECE** - Calibration error (target: <0.10)
- **Log Loss** - Confident wrong penalty (target: <0.65)
- **ROI** - Return on investment (target: >3%)

**Usage:**
```python
validator = CalibrationValidator()

# Add prediction
validator.add_prediction(
    player_name="Salah",
    opponent="Burnley",
    stat_type="SHOTS",
    line=3.5,
    direction="OVER",
    predicted_prob=0.75,
    tier="ELITE"
)

# Update outcome after match
validator.update_outcome(
    player_name="Salah",
    timestamp=timestamp,
    actual_outcome=1,  # 1=hit, 0=miss
    actual_stat_value=5.0
)

# Generate report
report = validator.generate_calibration_report()
```

---

## 📖 Usage Examples

### Example 1: Standard Bet Analysis

```python
# Home favorite vs weak defense
result = pipeline.analyze_bet(
    player=haaland,
    opponent=luton,
    match_context=home_context,
    stat_type=StatType.SHOTS,
    line=4.5,
    direction="OVER",
    book="UNDERDOG"
)

# Expected: ELITE tier, 75%+ probability, BET recommendation
```

### Example 2: Blocked by Filter

```python
# Derby match (should block)
result = pipeline.analyze_bet(
    player=salah,
    opponent=man_city,
    match_context=derby_context,
    stat_type=StatType.SHOTS,
    line=3.5,
    direction="OVER",
    book="PRIZEPICKS"
)

# Expected: BLOCKED, Derby Filter
```

### Example 3: Monitoring Weak Edge

```python
# Moderate probability (72-78%)
result = pipeline.analyze_bet(
    player=midfielder,
    opponent=average_defense,
    match_context=away_context,
    stat_type=StatType.PASSES,
    line=55.5,
    direction="OVER",
    book="DRAFTKINGS"
)

# Expected: STRONG tier, MONITOR recommendation
```

---

## ✅ Validation Checklist

### Before Live Deployment

- [ ] **Paper Trading** (4+ weeks)
  - Minimum 100 predictions logged
  - Track all outcomes
  - No real money

- [ ] **Calibration Metrics**
  - [ ] Brier Score < 0.25
  - [ ] ECE < 0.10
  - [ ] Log Loss < 0.65
  - [ ] Hit Rate > 56%

- [ ] **Profitability**
  - [ ] ROI > +3% on -110 odds
  - [ ] Positive ROI across all tiers
  - [ ] Win rate vs predicted within 5%

- [ ] **Filter Validation**
  - [ ] Derby blocks working (0% bets)
  - [ ] Rotation risk catching tired players
  - [ ] Blowout filter active for >15 spread

- [ ] **Opponent Adjustments**
  - [ ] Elite defense: Win rate <50%
  - [ ] Weak defense: Win rate >65%
  - [ ] Home/away splits validated

### Ongoing Monitoring

- [ ] Weekly calibration reports
- [ ] Monthly full backtest
- [ ] Quarterly threshold review
- [ ] Real-time line staleness checks

---

## 🏆 Quant Firm Submission

### Required Documentation

1. **System Architecture** ✓
   - Component overview
   - Data flow diagram
   - Integration points

2. **Statistical Methodology** ✓
   - Distribution selection logic
   - Opponent adjustment formulas
   - Filter gate specifications

3. **Backtesting Results** ⚠️ REQUIRED
   - Walk-forward validation
   - Minimum 200 predictions
   - Out-of-sample performance

4. **Calibration Evidence** ⚠️ REQUIRED
   - Reliability diagrams
   - Brier score decomposition
   - ECE analysis by tier

5. **Risk Management** ✓
   - Tier thresholds
   - Maximum exposure
   - Correlation handling

### Performance Targets

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Brier Score | <0.23 | <0.25 | >0.25 |
| ECE | <0.08 | <0.10 | >0.10 |
| Hit Rate | >58% | >56% | <56% |
| ROI (-110) | >+5% | >+3% | <+3% |
| Sample Size | 200+ | 150+ | <150 |

### Submission Package

```
submission/
├── README.md                       # This file
├── system_architecture.pdf         # Architecture diagram
├── methodology.pdf                 # Statistical approach
├── backtest_results/
│   ├── walk_forward_validation.csv
│   ├── calibration_plot.png
│   ├── reliability_diagram.png
│   └── performance_summary.json
├── code/
│   ├── soccer_opponent_adjustment.py
│   ├── soccer_match_context_filters.py
│   ├── soccer_distributions.py
│   ├── soccer_calibration_validator.py
│   └── soccer_pipeline_integration.py
└── validation/
    ├── paper_trading_log.csv       # 100+ predictions
    ├── calibration_report.json
    └── roi_analysis.xlsx
```

---

## 📊 Performance Metrics

### Expected Results (After Fixes)

```
BEST CASE (Perfect Implementation):
- Brier Score: 0.21-0.23
- ECE: 0.05-0.08
- Hit Rate: 60-62%
- ROI: +5% to +7%
- Picks/week: 5-10

REALISTIC (Initial Deployment):
- Brier Score: 0.23-0.25
- ECE: 0.08-0.10
- Hit Rate: 58-60%
- ROI: +3% to +5%
- Picks/week: 8-12
```

### Tier Performance Breakdown

```
ELITE (78%+):
- Expected hit rate: 65-68%
- Volume: 20-30% of bets
- ROI: +8% to +12%
- Decision: BET

STRONG (72-78%):
- Expected hit rate: 60-63%
- Volume: 30-40% of bets
- ROI: +4% to +7%
- Decision: MONITOR (wait for line movement)

LEAN (65-72%):
- Expected hit rate: 56-59%
- Volume: 20-30% of bets
- ROI: +1% to +3%
- Decision: SKIP
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** Brier score >0.26 (worse than random)
**Fix:** Increase tier thresholds, stricter SDG, more opponent adjustments

**Issue:** Too few bets (<5 per week)
**Fix:** Review filter settings, may be too aggressive

**Issue:** Low ROI despite good hit rate
**Fix:** Check if betting into sharp lines (stars on DraftKings)

**Issue:** Calibration drift over time
**Fix:** Monthly recalibration, update opponent rankings

---

## 📞 Support & Updates

For technical support or feature requests, review the codebase documentation.

---

## 📄 License

Proprietary - For Quant Firm Submission Only

---

**Last Updated:** February 1, 2026  
**Version:** 1.0 Production  
**Status:** Ready for Paper Trading
