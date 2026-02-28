# ⚽ SOCCER PROP ANALYSIS SYSTEM — Technical Architecture

## For AI Engineers & Maintainers

**Last Updated**: February 1, 2026  
**Status**: PRODUCTION  
**Version**: 2.0 (Risk-First Engine)

---

## 🎯 System Overview

The Soccer module analyzes player prop markets (passes, shots, SOT, dribbles, saves) using **statistical distributions** calibrated to soccer's unique game mechanics.

### Key Differences from NBA/CBB:

| Aspect | NBA/CBB | Soccer |
|--------|---------|--------|
| Game Length | 48/40 minutes | 90 minutes |
| Scoring Frequency | High (100+ points) | Low (2-3 goals avg) |
| Stat Volatility | Moderate | HIGH for goals, LOW for passes |
| Sample Size | 82/30+ games | 38 league games (less data) |
| Substitutions | Unlimited | 3-5 per game (limited) |
| Position Rigidity | Fluid | More rigid (formation-based) |

---

## 📊 Mathematical Models

### 1. Poisson Distribution (Count Stats)

Used for: **Shots, SOT, Saves, Goals, Assists, Tackles, Dribbles**

**Why Poisson?**
- These are discrete count events (0, 1, 2, 3...)
- Events are relatively rare per game
- Each event is independent
- Rate (λ) = average events per game

**Formula:**
```
P(X = k) = (λ^k × e^(-λ)) / k!

Where:
- λ = player's average per game
- k = number of events
- e = Euler's number (2.71828...)
```

**For OVER lines:**
```python
def poisson_over_probability(avg: float, line: float) -> float:
    """P(X > line) using Poisson distribution."""
    # P(X > line) = 1 - P(X <= floor(line))
    k_max = int(line)  # For "over 1.5", need P(X >= 2)
    
    cumulative = 0.0
    for k in range(k_max + 1):
        cumulative += (avg ** k) * math.exp(-avg) / math.factorial(k)
    
    return 1.0 - cumulative
```

**Example: Mbappé SOT Over 1.5**
```
λ (avg SOT/game) = 1.8
Line = 1.5 (need 2+ to hit OVER)

P(X=0) = (1.8^0 × e^-1.8) / 0! = 0.165
P(X=1) = (1.8^1 × e^-1.8) / 1! = 0.298

P(X <= 1) = 0.165 + 0.298 = 0.463
P(X > 1.5) = 1 - 0.463 = 0.537 = 53.7%
```

---

### 2. Normal Distribution (High-Count Stats)

Used for: **Passes, Touches**

**Why Normal?**
- High volume (30-80+ per game)
- Central Limit Theorem applies
- More stable, less variance than count stats

**Formula:**
```
Z = (Line - μ) / σ

Where:
- μ = player's average passes per game
- σ = standard deviation (typically 15-25% of mean)
- Z = standard score
```

**For OVER lines:**
```python
def normal_over_probability(avg: float, line: float, std_ratio: float = 0.20) -> float:
    """P(X > line) using Normal distribution."""
    std = avg * std_ratio  # 20% of mean as default std
    z = (line - avg) / std
    
    # Standard normal CDF
    return 1.0 - norm_cdf(z)
```

**Example: Bellingham Passes Over 47.5**
```
μ (avg passes/game) = 42.0
σ (std dev) = 42.0 × 0.20 = 8.4
Line = 47.5

Z = (47.5 - 42.0) / 8.4 = 0.655

P(X > 47.5) = 1 - Φ(0.655) = 1 - 0.744 = 0.256 = 25.6%
→ UNDER is 74.4% = STRONG
```

---

## 🎚️ Tier Thresholds (Soccer-Specific)

```python
TIER_THRESHOLDS = {
    "STRONG": 0.72,   # 72%+ — HIGH CONFIDENCE
    "LEAN": 0.60,     # 60-72% — ACTIONABLE
    "SLIGHT": 0.55,   # 55-60% — CAUTION
    "NO_PLAY": 0.0    # <55% — AVOID
}
```

### Why No SLAM Tier for Soccer?

Unlike NBA where you can get 85%+ on stable stats, soccer has:
1. **Fewer games** = smaller sample sizes
2. **Tactical variance** = managers rotate, change formations
3. **Match context** = cup vs league, rivalry matches
4. **Weather/pitch conditions** = affects play style

**Maximum practical confidence: ~85%** (and that's rare)

---

## 🧮 Position-Based Defaults

When a player isn't in the database, we use position averages:

```python
POSITION_DEFAULTS = {
    "striker": {
        "shots": 3.5, 
        "shots_on_target": 1.5, 
        "passes": 25, 
        "dribbles": 2.0,
        "crosses": 0.3, 
        "tackles": 0.5
    },
    "winger": {
        "shots": 2.2, 
        "shots_on_target": 0.9, 
        "passes": 32, 
        "dribbles": 4.0,
        "crosses": 2.0, 
        "tackles": 1.0
    },
    "attacking_mid": {
        "shots": 2.0, 
        "shots_on_target": 0.8, 
        "passes": 45, 
        "dribbles": 2.5,
        "crosses": 1.5, 
        "tackles": 1.5
    },
    "midfielder": {
        "shots": 1.2, 
        "shots_on_target": 0.5, 
        "passes": 55, 
        "dribbles": 1.5,
        "crosses": 1.0, 
        "tackles": 2.5
    },
    "defender": {
        "shots": 0.4, 
        "shots_on_target": 0.15, 
        "passes": 65, 
        "dribbles": 0.5,
        "crosses": 0.8, 
        "tackles": 2.5, 
        "clearances": 5.0
    },
    "goalkeeper": {
        "saves": 3.0, 
        "passes": 30
    }
}
```

### Position Detection from Underdog Format

```
Kylian Mbappé
Real Madrid - Attacker    ← Position extracted here
vs Rayo
1.5
SOT
```

---

## 📁 File Structure

```
soccer/
├── soccer_menu.py              # Main interactive menu (NEW)
├── soccer_slate_analyzer.py    # Core analysis engine
├── data/
│   └── player_database.py      # Pre-loaded player stats
├── inputs/
│   └── slate_YYYYMMDD.txt      # Saved Underdog slates
├── outputs/
│   └── soccer_props_report_*.txt
├── config/
│   ├── soccer_config.py        # Tier thresholds, caps
│   └── stat_types.py           # Stat configurations
└── SOCCER_SYSTEM_ARCHITECTURE.md  # This file
```

---

## 🔄 Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  1. INGEST                                                  │
│     └── parse_underdog_slate(text)                          │
│         • Extract: player, team, position, stat, line       │
│         • Normalize stat names (SOT → shots_on_target)      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. LOOKUP                                                  │
│     └── get_player_avg(player, stat, position)              │
│         • Try: KNOWN_PLAYERS database (exact match)         │
│         • Try: Partial name match (fuzzy)                   │
│         • Fallback: Position-based defaults                 │
│         • Return: (avg, source, games_played)               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. PROBABILITY CALCULATION                                 │
│     └── analyze_prop(prop)                                  │
│         • If stat == "passes": use Normal distribution      │
│         • Else: use Poisson distribution                    │
│         • Calculate: P(OVER), P(UNDER)                      │
│         • Determine: best direction, tier                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. TIER CLASSIFICATION                                     │
│     └── get_tier(probability)                               │
│         • STRONG: ≥72%                                      │
│         • LEAN: ≥60%                                        │
│         • SLIGHT: ≥55%                                      │
│         • NO_PLAY: <55%                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. OUTPUT                                                  │
│     └── format_report(analyzed_props)                       │
│         • Group by tier                                     │
│         • Show data source (DATABASE vs ESTIMATE)           │
│         • Generate cheat sheet                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗃️ Player Database Schema

```python
@dataclass
class PlayerStats:
    """Player statistics container."""
    name: str
    team: str
    position: str           # striker, winger, midfielder, defender, goalkeeper
    league: str             # premier_league, la_liga, bundesliga, serie_a, ligue_1
    games_played: int
    
    # Attacking (per game averages)
    shots: float = 0.0
    shots_on_target: float = 0.0
    goals: float = 0.0
    assists: float = 0.0
    
    # Passing
    passes: float = 0.0
    passes_completed: float = 0.0
    crosses: float = 0.0
    
    # Creative
    dribbles: float = 0.0
    key_passes: float = 0.0
    
    # Defensive
    tackles: float = 0.0
    interceptions: float = 0.0
    clearances: float = 0.0
    
    # Goalkeeper
    saves: float = 0.0
    clean_sheet_rate: float = 0.0
```

### Adding New Players

```python
# In soccer/data/player_database.py

KNOWN_PLAYERS = {
    # ... existing players ...
    
    "new player name": PlayerStats(
        name="New Player Name",
        team="Team Name",
        position="midfielder",  # striker, winger, attacking_mid, midfielder, defender, goalkeeper
        league="premier_league",  # premier_league, la_liga, bundesliga, serie_a, ligue_1
        games_played=20,
        shots=1.5,
        shots_on_target=0.6,
        passes=45,
        tackles=2.0,
        # ... other stats ...
    ),
}
```

---

## 📈 Stat Type Configuration

```python
# Which distribution to use per stat

STAT_MODEL_TYPE = {
    # Poisson (discrete counts)
    "shots": "poisson",
    "shots_on_target": "poisson",
    "goals": "poisson",
    "assists": "poisson",
    "tackles": "poisson",
    "interceptions": "poisson",
    "clearances": "poisson",
    "saves": "poisson",
    "dribbles": "poisson",
    "crosses": "poisson",
    
    # Normal (high volume)
    "passes": "normal",
    "passes_completed": "normal",
    "touches": "normal",
}

# Standard deviation ratios for Normal distribution
STD_RATIOS = {
    "passes": 0.20,          # 20% of mean
    "passes_completed": 0.18,
    "touches": 0.15,
}
```

---

## 🔧 Extending the System

### 1. Adding a New Stat Type

```python
# 1. Add to STAT_ALIASES in soccer_slate_analyzer.py
STAT_ALIASES = {
    "new stat name": "internal_name",
    # ...
}

# 2. Add to POSITION_DEFAULTS
POSITION_DEFAULTS["striker"]["internal_name"] = 2.5

# 3. Add to player database entries
```

### 2. Adjusting Tier Thresholds

```python
# In soccer_slate_analyzer.py
TIER_THRESHOLDS = {
    "STRONG": 0.72,  # Adjust if calibration shows different optimal
    "LEAN": 0.60,
    "SLIGHT": 0.55,
    "NO_PLAY": 0.0
}
```

### 3. Adding Match Context Adjustments

Future enhancement - adjust probabilities based on:
- Home/Away (±5% for passes, ±3% for shots)
- Rivalry matches (increase variance)
- Cup vs League (rotation risk)
- Weather conditions

```python
def apply_match_context(prob: float, context: dict) -> float:
    """Adjust probability based on match context."""
    adj = prob
    
    if context.get("is_home"):
        adj *= 1.03  # 3% boost
    
    if context.get("is_cup_match"):
        adj *= 0.95  # 5% penalty (rotation risk)
    
    return min(adj, 0.85)  # Cap at 85%
```

---

## 📊 Comparison: NBA vs Soccer Models

| Component | NBA | Soccer |
|-----------|-----|--------|
| **Primary Model** | Monte Carlo (10k sims) | Poisson + Normal |
| **Sample Size** | 10-20 recent games | Season average |
| **Volatility Adjustment** | Specialist caps | Position defaults |
| **Max Confidence** | 85% | 85% |
| **Tier: SLAM** | 80%+ | DISABLED |
| **Tier: STRONG** | 65%+ | 72%+ |
| **Tier: LEAN** | 55%+ | 60%+ |

### Why Different Approaches?

**NBA Monte Carlo:**
- More games = better rolling averages
- Higher scoring = more data points
- Opponent-specific adjustments matter more
- Usage rates and pace adjustable

**Soccer Poisson/Normal:**
- Fewer games = need full season data
- Low-scoring = Poisson fits perfectly
- Position/role more deterministic
- Less opponent-specific variance in props

---

## 🧪 Validation & Calibration

### Expected Hit Rates by Tier

| Tier | Target | Acceptable Range |
|------|--------|------------------|
| STRONG | 72%+ | 68-80% |
| LEAN | 60-72% | 55-75% |
| SLIGHT | 55-60% | 50-65% |

### Calibration Tracking

```python
# Track results in calibration/calibration_history.csv
# Columns: date, sport, player, stat, line, direction, probability, tier, result

# Future: soccer/calibration/soccer_tracker.py
```

---

## 🚨 Known Limitations

1. **No live injury data** — Check lineups before betting
2. **Formation changes** — Can significantly impact touches/passes
3. **Weather not factored** — Rain reduces passing accuracy
4. **Cup rotation** — Players rested in less important matches
5. **Position detection** — Sometimes wrong from Underdog format

---

## 📱 Telegram Integration

```python
# In soccer_menu.py

def send_top_picks_to_telegram(num_picks: int = 7):
    """Send top N picks to Telegram."""
    # 1. Load most recent slate
    # 2. Parse and analyze all props
    # 3. Sort by probability (descending)
    # 4. Take top N actionable picks (≥60%)
    # 5. Format HTML message
    # 6. Send via Telegram Bot API
```

---

## 🔮 Future Enhancements

1. **Live API integration** — Fetch real-time stats when rate limits allow
2. **xG-based adjustments** — Use expected goals for shot quality
3. **Form factor** — Recent 5-game rolling average
4. **Head-to-head** — Performance vs specific opponents
5. **Combo prop support** — Multi-leg parlays
6. **Goalkeeper saves model** — Based on opponent xG

---

## 📝 Quick Reference Commands

```bash
# Run soccer menu
.venv\Scripts\python.exe soccer\soccer_menu.py

# Analyze saved slate
.venv\Scripts\python.exe soccer\soccer_slate_analyzer.py

# Show all picks including NO_PLAY
.venv\Scripts\python.exe soccer\soccer_slate_analyzer.py --all

# Access via main menu
.venv\Scripts\python.exe menu.py
# Then press [O] for Soccer
```

---

**Author**: Risk-First Engine Team  
**Contact**: UNDERDOG ANALYSIS System
