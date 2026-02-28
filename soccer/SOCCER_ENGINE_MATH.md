# Soccer Monte Carlo Engine — Mathematical Documentation

## Overview

The Soccer Monte Carlo engine simulates player prop outcomes using statistically appropriate distributions for each market type.

## Distributions by Market

### 1. Shots / Shots on Target (Poisson)

**Rationale**: Shots are discrete count events with independent occurrence probability.

```
P(X = k) = (λ^k × e^(-λ)) / k!

Where:
- λ = player's average shots per game
- k = number of shots to simulate
```

**Example**: Haaland averages 4.2 shots/game
- P(Shots > 4.5) = 1 - P(X ≤ 4) = 1 - Σ P(X=k) for k=0 to 4

### 2. Goals / Assists (Zero-Inflated Poisson)

**Rationale**: Goals are rare events where many players record 0 in most games. Standard Poisson underestimates P(X=0).

```
P(X = 0) = π + (1-π) × e^(-λ)
P(X = k) = (1-π) × (λ^k × e^(-λ)) / k!  for k > 0

Where:
- π = probability of "structural zero" (player won't score regardless)
- λ = expected goals when player does have opportunity
```

**Position-Based π Values**:
| Position | π (Goals) | π (Assists) |
|----------|-----------|-------------|
| Striker | 0.30 | 0.55 |
| Winger | 0.50 | 0.45 |
| Attacking Mid | 0.50 | 0.45 |
| Central Mid | 0.70 | 0.55 |
| Defensive Mid | 0.75 | 0.70 |
| Defender | 0.75 | 0.70 |

### 3. Passes / Touches (Normal)

**Rationale**: High-volume stats approximate continuous distributions.

```
X ~ N(μ, σ²)

Where:
- μ = player's average passes per game
- σ = standard deviation (typically ~18% of mean)
```

**Coefficient of Variation**: Passes have ~0.15-0.20 CV (relatively stable)

### 4. Tackles / Interceptions (Poisson)

**Rationale**: Defensive actions are discrete events.

```
λ_tackles varies by position:
- DM: 3.5
- Fullback: 2.8
- CB: 2.0
- CM: 2.5
```

## Confidence Caps by Market

To prevent overconfidence in volatile markets:

| Market | Cap | Reason |
|--------|-----|--------|
| Goals | 60% | Rare event, high variance |
| Assists | 58% | Even rarer than goals |
| Shots | 75% | Moderate predictability |
| SOT | 72% | Conversion rate varies |
| Passes | 82% | High volume, stable |
| Tackles | 70% | Depends on game state |

## League Pace Adjustments

Goals and shots vary by league:

| League | Goals/Game | Pace Factor |
|--------|------------|-------------|
| Bundesliga | 3.15 | 1.10 |
| Premier League | 2.85 | 1.05 |
| MLS | 2.95 | 1.02 |
| Ligue 1 | 2.75 | 1.00 |
| Serie A | 2.65 | 0.98 |
| La Liga | 2.55 | 0.95 |

## Sample Size Adjustments

Variance in estimated λ decreases with more games:

```
λ_std = √(λ / n_games)

For 5 games:  λ_std = √(4.2/5) = 0.92
For 20 games: λ_std = √(4.2/20) = 0.46
```

## Tier Thresholds

| Tier | Probability | Note |
|------|-------------|------|
| SLAM | N/A | DISABLED (soccer too volatile) |
| STRONG | ≥70% | High confidence |
| LEAN | ≥58% | Moderate edge |
| SPEC | ≥50% | Speculative |
| AVOID | <50% | No edge |

## Example Calculation

**Prop**: Haaland Shots O/U 4.5
**Player Avg**: 4.2 shots/game (22 games)
**League**: Premier League (pace factor 1.05)

1. Adjust average: λ = 4.2 × 1.05 = 4.41
2. Sample uncertainty: λ_std = √(4.41/22) = 0.45
3. Run 10,000 simulations with λ ~ N(4.41, 0.45²)
4. Count P(X > 4.5) ≈ 42.8%
5. Apply cap (75%): min(42.8%, 75%) = 42.8%
6. Direction: UNDER has edge (57.2%)

**Result**: Haaland Shots UNDER 4.5 → 57.2% → SPEC tier
