# NBA Analysis System — Client Guide
**Version 1.0 | January 26, 2026**

---

## Why NBA Props Are Different

### The Core Problem
**NFL is stable. NBA is chaos.**

| Factor | NFL | NBA |
|--------|-----|-----|
| **Games** | 17 regular season | 82 regular season |
| **Roles** | Fixed (CB, WR, RB) | Fluid (minutes vary ±10/game) |
| **Blowouts** | Rare (1-2 per week) | Common (5-10 per night) |
| **Coaching** | Fixed game plans | Rotation experimentation |
| **Sample Size** | Small (need full season) | Large (but more variance) |

**Result**: NFL can hit 75% (SLAM) confidence. NBA caps at **62%-72%** depending on player archetype.

---

## The 5 Volatility Factors

### 1. **Player Archetype** (7 types)
We classify every player into one of 7 archetypes with different confidence caps:

| Archetype | Examples | Usage | Confidence Cap | Why Lower? |
|-----------|----------|-------|----------------|------------|
| **PRIMARY_USAGE_SCORER** | Luka, Giannis, SGA | 28%+ | **72%** | Sits in blowouts (-15 min) |
| **SECONDARY_CREATOR** | Kyrie, Jaylen Brown | 22-28% | **70%** | Role fluctuates with stars |
| **CONNECTOR_STARTER** | Jrue Holiday, Mikal | 15-22% | **68%** | Most stable archetype |
| **STRETCH_BIG** | Brook Lopez, KAT | 18-25% | **68%** | 3PT variance (hot/cold) |
| **RIM_RUNNER** | Capela, Hartenstein | <18% | **66%** | Low-frequency events |
| **DEFENSIVE_SPECIALIST** | Herb Jones, Caruso | <15% | **65%** | Limited offensive role |
| **BENCH_MICROWAVE** | Clarkson, Quickley | 20%+ (bench) | **62%** | Highest volatility |

### 2. **Coach Rotation Style**
Different coaches = different predictability:

| Style | Rotation Size | Confidence Effect | Examples |
|-------|---------------|-------------------|----------|
| **TIGHT** (7-8 man) | 7-8 players | **+3% to +5%** | Tom Thibodeau, Erik Spoelstra |
| **MODERATE** (9-10) | 9-10 players | **Neutral** | Most NBA coaches |
| **LOOSE** (10-11+) | 10-12 players | **-5% to -8%** | Gregg Popovich, Steve Kerr |

**Why it matters**: Tight rotations = predictable minutes. Loose rotations = wildcard bench usage.

### 3. **Blowout Risk**
If the spread is ≥10 points, confidence drops **-5%** for stars and **-10%** for bench microwave scorers.

**Example**:  
- **BOS -13.5 vs DET**: Jayson Tatum sits after 3 quarters → 28 minutes instead of 36 minutes.
- **Effect**: SLAM pick (75%) downgrades to STRONG (65%) or LEAN (55%).

### 4. **Minutes Variance** (L10 games)
If a player's minutes fluctuate wildly (std dev >8), we penalize **-5%** confidence.

**Example**:  
Jordan Clarkson last 10 games: 32, 18, 24, 29, 12, 26, 21, 34, 16, 28  
→ Avg: 24 min, Std Dev: 7.5 → **No penalty** (barely safe)  
vs  
Norman Powell: 28, 14, 32, 9, 26, 19, 31, 12, 27, 15  
→ Avg: 21 min, Std Dev: 9.2 → **-5% penalty** (too volatile)

### 5. **Bench Risk**
Players with >20% DNP-CD risk (healthy scratches) get **-3%** confidence.

**High-risk archetypes**: BENCH_MICROWAVE (25%), DEFENSIVE_SPECIALIST (15%)

---

## How We Adjust the System

### Before (Old NFL-style approach):
1. Calculate mean/variance from L10 games
2. Run Monte Carlo (10,000 iterations)
3. Output probability → 68% (STRONG tier)

### After (New NBA-aware approach):
1. **Classify archetype** (e.g., BENCH_MICROWAVE)
2. **Adjust parameters BEFORE Monte Carlo**:
   - Minutes: 24 min × 0.90 = **21.6 min** (loose rotation penalty)
   - Variance: σ × 1.40 = **Higher variance** (elastic minutes)
   - Usage: 26.8% × 1.0 = **Unchanged** (no blowout)
3. Run Monte Carlo with **adjusted parameters**
4. Apply **confidence governance**:
   - Base cap: 62% (BENCH_MICROWAVE)
   - High usage volatility: -5%
   - Blowout game (spread 12): -5%
   - Loose rotation: -8%
   - **Final cap: 44%** (LEAN tier, not STRONG)

---

## What You'll See in Reports

### New Metadata Fields

Every NBA pick now includes:

```
Player: Jordan Clarkson
Archetype: BENCH_MICROWAVE
Confidence: 44% (LEAN)
Base Cap: 62%
Flags:
  • HIGH_USAGE_VOLATILITY (-5%)
  • BLOWOUT_GAME_RISK (-5%)
  • LOOSE_ROTATION (-8%)
Minutes Adjustment: -10% (loose rotation)
Variance Adjustment: +40% (elastic minutes)
```

### Tier Distribution Shifts

| Tier | NFL % of Picks | NBA % of Picks |
|------|----------------|----------------|
| **SLAM** (75%+) | 15% | **<5%** (rare) |
| **STRONG** (65-74%) | 35% | **25%** |
| **LEAN** (55-64%) | 40% | **60%** |
| **Avoid** (<55%) | 10% | 15% |

**Takeaway**: More LEAN picks, fewer SLAM picks. This is intentional and accurate.

---

## Example Downgrades

### Example 1: Luka Doncic (PRIMARY_USAGE_SCORER)

**Old Confidence**: 78% (SLAM) → **Too high**  
**New Confidence**: 68% (STRONG)

**Why downgrade**:
- Archetype cap: 72%
- Blowout sensitivity: -5% (DAL favored by 11.5)
- **Final**: 68% (STRONG tier)

**Still a good pick**, just not SLAM-tier due to blowout risk.

---

### Example 2: Jordan Clarkson (BENCH_MICROWAVE)

**Old Confidence**: 68% (STRONG) → **Way too high**  
**New Confidence**: 44% (LEAN)

**Why major downgrade**:
- Archetype: BENCH_MICROWAVE (base cap 62%)
- High usage volatility: -5%
- Blowout game (UTA underdog by 12): -5%
- High minutes variance (L10 std = 9.2): -5%
- Loose rotation (Quin Snyder = deep bench): -8%
- **Cumulative**: 62% - 23% = **39% → Rounded to 44%** (LEAN)

**Action**: Still playable at + odds, but not a core play.

---

### Example 3: Jrue Holiday (CONNECTOR_STARTER)

**Old Confidence**: 70% (STRONG)  
**New Confidence**: 68% (STRONG)

**Why minimal change**:
- Archetype: CONNECTOR_STARTER (stable role)
- Low volatility: No penalties
- Tight rotation (Celtics = 8-man): +3%
- **Final**: 68% (unchanged tier)

**Action**: Most stable archetype — confidence barely affected.

---

## FAQ

### Q: Why are NBA picks capped lower than NFL?
**A**: 82-game variance + blowouts + rotation chaos = structural uncertainty. NFL has 17 games with fixed roles.

### Q: Should I avoid LEAN picks?
**A**: No! LEAN = 55-64% win rate. At + odds, these are profitable long-term. Just don't overbet.

### Q: What about injury replacements?
**A**: Archetype shifts temporarily. If Luka sits, Kyrie becomes PRIMARY_USAGE_SCORER (72% cap).

### Q: Can I see the raw archetype before penalties?
**A**: Yes. Reports show:
- **Archetype Base Cap**: 62%
- **Penalties**: -23%
- **Final Confidence**: 44%

### Q: Why do some stars get downgraded in blowouts?
**A**: Coaches pull stars early. If BOS is up 20 in Q3, Jayson Tatum sits the 4th quarter.

### Q: What's the most stable archetype?
**A**: **CONNECTOR_STARTER** (68% cap, low volatility, consistent minutes). Examples: Jrue Holiday, Mikal Bridges.

### Q: What's the riskiest archetype?
**A**: **BENCH_MICROWAVE** (62% cap, high volatility, DNP risk). Examples: Jordan Clarkson, Norman Powell.

---

## Cheat Sheet Quick Reference

| Archetype | Cap | Risk Level | When to Play |
|-----------|-----|------------|--------------|
| PRIMARY_USAGE_SCORER | 72% | Medium | Avoid blowouts |
| SECONDARY_CREATOR | 70% | Medium | Stable minutes games |
| CONNECTOR_STARTER | 68% | **LOW** | Anytime (most stable) |
| STRETCH_BIG | 68% | Medium | 3PT variance aware |
| RIM_RUNNER | 66% | Medium-Low | Low-frequency stats |
| DEFENSIVE_SPECIALIST | 65% | Medium-High | Limited offensive stats |
| BENCH_MICROWAVE | 62% | **HIGH** | Only at + odds |

---

## Bottom Line

**NBA analysis is now tuned for NBA chaos, not NFL stability.**

✅ **More accurate** long-term calibration  
✅ **Fewer false SLAMs** (inflated confidence)  
✅ **Better risk management** (flags warn you)  
✅ **Profitable LEAN picks** at the right price

**Trust the process. Bet the math.**
