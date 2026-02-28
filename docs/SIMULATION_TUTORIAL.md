# 🎮 SIMULATION TUTORIAL & ADVANCED TOOLS GUIDE

**UNDERDOG ANALYSIS — Power User Documentation**  
*Last Updated: February 5, 2026*  
*Status: ✅ INTEGRATED INTO MAIN MENU (Phase 5A Complete)*

---

## 📚 TABLE OF CONTENTS

1. [New Menu Options](#-new-menu-options-phase-5a)
2. [Game Simulator Tutorial](#-nba-game-simulator-tutorial)
3. [Monte Carlo Engine](#-monte-carlo-engine)
4. [All Advanced Tools](#-all-advanced-tools)
5. [Quick Reference Commands](#-quick-reference-commands)

---

## 🆕 NEW MENU OPTIONS (Phase 5A)

**These tools are now accessible from the main menu!**

Run the main menu:
```powershell
.venv\Scripts\python.exe menu.py
```

Look for the **🔧 Advanced Tools** section:

| Key | Tool | Description |
|-----|------|-------------|
| `[SIM]` | 🎮 Game Simulator | Possession-chain Monte Carlo for player props |
| `[SQ]` | 📊 Slate Quality | Grade today's slate (A-F) |
| `[KS]` | 💰 Kelly Sizing | Optimal bet sizing calculator |
| `[TE]` | 🧠 Truth Engine | View dependency graph for picks |
| `[ESS]` | ⚡ Edge Stability | ESS scores for edge reliability |
| `[REG]` | 📉 Regret Analysis | Post-game missed opportunities |
| `[CAP]` | 🏦 Capital Allocation | Bankroll management system |
| `[BL]` | 🎲 Probability Blender | Multi-method probability synthesis |

**Slate Quality is now shown in the header automatically!**

---

## 📈 NEW OUTPUT FEATURES (Phase 5A Part 2)

### Kelly Sizing in Analysis Output

Every pick now shows **Kelly stake** recommendations:

```
[SLAM] PLAY PICKS (>=80% Effective Confidence) | Bankroll: $1000:

1. LeBron James - PTS HIGHER 27.5
   Confidence: 82.3% | Edge: +3.2 (+1.85sigma) [STRONG] STRONG
   Stats: mu=30.7, sigma=5.2 | Kelly: $145
```

**Kelly Column in Cheat Sheets:**
```powershell
.venv\Scripts\python.exe scripts/generate_consolidated_cheatsheet.py --bankroll 500
```

### Slate Quality in Summary

The analysis summary now shows **Slate Quality** at the top:

```
======================================================================
RISK-FIRST ANALYSIS SUMMARY
======================================================================
Slate Quality: 🟢 A (87/100)
   Drivers: None - high quality slate
----------------------------------------------------------------------
Total Props Analyzed: 45
...
```

---

## 🏀 NBA GAME SIMULATOR TUTORIAL

### What It Does
Simulates full NBA games possession-by-possession to derive **context-aware** player stat distributions.

**Key Advantage Over Basic MC:**
- Models **game script** (leading/trailing/blowout)
- Models **coaching decisions** (star benching in blowouts)
- Models **play type transitions** (PnR → ISO → Spot-up)
- Outputs **full distribution** for any line comparison

---

### Step-by-Step Usage

#### 1. Basic Single-Player Simulation

```powershell
# Run the demo
.venv\Scripts\python.exe nba_game_simulator.py
```

**Output:**
```
--- NBA Game Simulator Results ---
Probability Jokic > 26.5: 0.68
Mean: 28.42 | Std: 6.31
Sample: [32, 24, 29, 31, 22, 28, 35, 27, 26, 30]
```

---

#### 2. Custom Player Simulation (Python)

```python
from nba_game_simulator import (
    GameSimulator, TeamStateModel, CoachingModel, PlayerOpportunityModel
)

# Define coaching tendencies (key: {player}_usage_{game_script})
coach_tendencies = {
    'lebron_usage_close': 0.30,      # Usage when game is close
    'lebron_usage_leading': 0.25,    # Usage when leading
    'lebron_usage_trailing': 0.35,   # Usage when trailing (higher!)
    'lebron_usage_blowout': 0.15,    # Usage in blowouts (benched)
    'default_usage': 0.25,           # Fallback
    'pace_adjustment': {
        'leading': -3.0,   # Slow down when ahead
        'trailing': +4.0,  # Speed up when behind
        'close': 0,
        'blowout': -5
    },
    'blowout_threshold': 15
}

# Setup
coach = CoachingModel('JJ Redick', coach_tendencies)
lakers = TeamStateModel('LAL', pace=101, ppp=1.14, coach=coach)
celtics = TeamStateModel('BOS', pace=97, ppp=1.18, coach=coach)
lebron = PlayerOpportunityModel('LeBron', 'SF', coach)

# Run 2000 simulations
sim = GameSimulator(lakers, celtics, lebron)
result = sim.simulate_game(n_sims=2000, market_line=25.5)

print(f"P(LeBron > 25.5 PTS): {result['probability_over']:.2%}")
print(f"Mean: {sum(result['distribution'])/len(result['distribution']):.1f}")
```

---

#### 3. Integrate With Live Slate Data

```python
# After running analysis, enhance with simulation
from fuoom_simulation_integration import SimulationEnhancedProjector

projector = SimulationEnhancedProjector()

# Example edge from slate analysis
edge = {
    'player': 'Anthony Davis',
    'stat': 'REB',
    'line': 11.5,
    'mu': 12.8,
    'sigma': 3.2,
    'base_probability': 0.68
}

# Team context (from API)
team_stats = {'LAL': {'pace': 101, 'ppp': 1.12}}
player_stats = {'Anthony Davis': {'usage_base': 0.28, 'position': 'PF'}}

enhanced = projector.enhance_edge(edge, team_stats, player_stats)
print(f"Simulation-adjusted probability: {enhanced['sim_probability']:.2%}")
```

---

### Understanding the Output

| Field | Meaning |
|-------|---------|
| `probability_over` | % of simulations where player exceeded line |
| `distribution` | List of all simulated stat outcomes |
| `mean` | Average across simulations |
| `std` | Standard deviation (variance indicator) |

---

## 🎲 MONTE CARLO ENGINE

### Location: `sports_quant/simulation/monte_carlo.py`

**Simpler than Game Simulator** — pure statistical MC without game context.

### Usage

```python
from sports_quant.simulation.monte_carlo import run_monte_carlo

result = run_monte_carlo(
    line=25.5,           # Market line
    mean=28.0,           # Projected average
    variance=36.0,       # Variance (std²)
    dist="normal",       # "normal", "poisson", or "lognormal"
    n_sims=10000         # Simulation count
)

print(f"P(Over):  {result['p_over']:.2%}")
print(f"P(Under): {result['p_under']:.2%}")
print(f"EV:       {result['expected_value']:.2f}")
print(f"5th %ile: {result['tail_risk']['p05']:.1f}")
print(f"95th %ile: {result['tail_risk']['p95']:.1f}")
```

### When to Use Which Distribution

| Stat Type | Distribution | Rationale |
|-----------|--------------|-----------|
| PTS, REB, AST | `normal` | Continuous, symmetric |
| 3PM, BLK, STL | `poisson` | Count data, discrete |
| Fantasy points | `lognormal` | Right-skewed, no negatives |

---

## 🔮 HIDDEN FEATURES NOT IN MAIN MENU

These powerful tools exist but aren't accessible via the main `menu.py`:

### 1. **HUB Menu** (Alternative Main Menu)
```powershell
.venv\Scripts\python.exe hub.py
```
Contains:
- `[X]` **Chaos Stress Test** — 50-game noise simulation to validate ESS
- `[E]` **ESS Config** — Tweak stability weights
- `[C]` **Coaching Profiles** — Rotation elasticity settings
- `[OB]` **Observability** — System health dashboard

---

### 2. **Chaos Stress Test**
```powershell
.venv\Scripts\python.exe -c "from engine.chaos_stress_test import run_chaos_simulation; from engine.edge_stability_engine import EdgeStabilityEngine; run_chaos_simulation(EdgeStabilityEngine())"
```
Tests if your ESS thresholds prevent false SLAMs in high-variance environments.

---

### 3. **Edge Stability Engine (ESS)**
```python
from engine.edge_stability_engine import EdgeStabilityEngine

ess = EdgeStabilityEngine()
score = ess.calculate_ess(
    mean=28.0,
    line=25.5,
    sigma=5.2,
    min_stability=0.85,   # Historical minutes variance
    role_entropy=0.12,    # Coaching rotation flux
    tail_risk=0.20        # P(< 50% of projection)
)
tier = ess.get_tier(score)
print(f"ESS: {score:.4f} → {tier}")
```

---

### 4. **Probability Blender** (Hybrid Model)
```powershell
.venv\Scripts\python.exe probability_blender.py
```
Blends 3 probability methods:
- Normal CDF (parametric)
- Empirical hit rate (historical)
- Bayesian posterior (shrinkage toward prior)

```python
from probability_blender import blend_probabilities

result = blend_probabilities(
    line=25.5,
    direction='higher',
    recent_values=[28, 24, 31, 26, 29, 27, 30, 25, 28, 27]
)
print(f"Blended P: {result.p_final:.2%}")
print(f"Confidence: {result.confidence}")
```

---

### 5. **Blowout Risk Analysis**
```python
from engine.blowout_risk import blowout_risk_analysis

result = blowout_risk_analysis(
    spread=-8.5,       # Point spread
    total=220.5,       # Over/Under
    player_tier='STAR' # 'STAR' or 'BENCH'
)
print(f"Blowout Probability: {result['blowout_prob']:.1%}")
print(f"Impact Multiplier: {result['impact_multiplier']:.2f}")
print(f"High Risk? {result['is_high_risk']}")
```

---

### 6. **Kelly Criterion Sizing**
```python
from core.kelly import final_stake

stake = final_stake(
    bankroll=100,
    p_raw=0.68,        # Model probability
    p_exec=0.65,       # Execution probability
    odds=1.91,         # Decimal odds (-110)
    half_life=12,      # Edge half-life in hours
    platform='underdog'
)
print(f"Recommended stake: ${stake:.2f}")
```

---

### 7. **Capital Allocation Engine**
```python
from engine.capital_allocation import allocate_capital

picks = [
    {'tier': 'SLAM', 'probability': 0.78, 'player': 'Jokic', 'team': 'DEN'},
    {'tier': 'STRONG', 'probability': 0.67, 'player': 'LeBron', 'team': 'LAL'},
]

allocation = allocate_capital(
    picks=picks,
    bankroll=100.0,
    mode="BROADCAST",
    bias_detected=False
)
```

---

### 8. **Slate Quality Scorer**
```python
from core.slate_quality import compute_slate_quality

quality = compute_slate_quality({
    'api_health': 0.95,
    'injury_density': 0.08,
    'avg_sigma': 5.5,
    'sigma_threshold': 7.0,
    'pct_above_55': 0.35
})
print(f"Slate Grade: {quality.grade} ({quality.score}/100)")
print(f"Max Tier Allowed: {quality.max_allowed_tier}")
```

---

### 9. **Regret Analysis** (Post-Mortem)
```python
from core.regret import compute_regret

# After game completes
edge = type('Edge', (), {
    'edge_id': 'jokic_pts_25.5',
    'raw_probability': 0.68,
    'execution_probability': 0.65,
    'executed': True,
    'outcome': True  # Win
})()

regret = compute_regret(edge, stake=1.0)
print(f"Regret Score: {regret.regret_score:.3f}")
print(f"Opportunity Cost: {regret.opportunity_cost:.3f}")
```

---

### 10. **Truth Engine** (Full Dependency Graph)
```python
from truth_engine.truth_engine import TruthEngine

engine = TruthEngine()
# See truth_engine/README.md for full documentation
```

---

## ⚡ ADVANCED ENGINES

### A. Correlation Controls
```python
from sports_quant.correlation.controls import CorrelationMatrix
# Prevents correlated props from stacking in parlays
```

### B. Feature Engine
```python
from sports_quant.feature_engine import build_features
# Builds ML features from raw stats
```

### C. Normalization
```python
from sports_quant.normalization import normalize_by_opponent
# Adjusts stats by opponent strength
```

---

## 📋 QUICK REFERENCE COMMANDS

### Daily Workflow with Simulation

```powershell
# 1. Standard analysis
.venv\Scripts\python.exe menu.py
# Select [1] to ingest slate, [2] to analyze

# 2. Run simulation stress test
.venv\Scripts\python.exe hub.py
# Select [X] for Chaos Stress Test

# 3. Custom simulation on a player
.venv\Scripts\python.exe -c "
from nba_game_simulator import *
import numpy as np

coach = CoachingModel('Coach', {'default_usage': 0.25})
home = TeamStateModel('LAL', 99, 1.12, coach)
away = TeamStateModel('BOS', 97, 1.10, coach)
player = PlayerOpportunityModel('LeBron', 'SF', coach)
sim = GameSimulator(home, away, player)
result = sim.simulate_game(n_sims=2000, market_line=26.5)
print(f'P(Over): {result[\"probability_over\"]:.2%}')
print(f'Mean: {np.mean(result[\"distribution\"]):.1f}')
"
```

### Batch Analysis Commands

| Purpose | Command |
|---------|---------|
| Run Hub Menu | `.venv\Scripts\python.exe hub.py` |
| Chaos Test | `.venv\Scripts\python.exe -m engine.chaos_stress_test` |
| Slate Quality Check | `.venv\Scripts\python.exe -c "from core.slate_quality import *; print(compute_slate_quality({'api_health': 1.0, 'injury_density': 0.1, 'avg_sigma': 5.0, 'sigma_threshold': 7.0, 'pct_above_55': 0.3}))"` |

---

## 🎯 BEST PRACTICES

1. **Always Run Chaos Test Before Live** — Validates your ESS thresholds
2. **Use Blowout Risk for Star Players** — Especially with large spreads
3. **Blend Probabilities** — Don't rely on single method
4. **Check Slate Quality First** — Low quality = defensive mode
5. **Use Kelly for Sizing** — But cap at 2.5% per pick
6. **Review Regret Weekly** — Learn from missed opportunities

---

## 📊 INTEGRATION ROADMAP

**Currently Standalone:**
- `nba_game_simulator.py`
- `hub.py`
- `probability_blender.py`
- `engine/chaos_stress_test.py`

**Recommendation:** Add `[SIM]` to main menu for one-click access.

---

*Document generated by FUOOM System Documentation v2.0*
