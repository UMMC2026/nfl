# UNIVERSAL GOVERNANCE OBJECT — INTEGRATION GUIDE

## STATUS: Phase 1 Complete ✅

**Created:** 2026-02-01  
**Version:** UGO v1.0  
**File:** `core/universal_governance_object.py`

---

## 🎯 MISSION

**Enable cross-sport governance by standardizing edge representation.**

Before UGO:
- Each sport has different field names (mu vs mean vs avg)
- Edge calculations inconsistent (Soccer inverted, Golf multiplier-based)
- ESS/FAS cannot compare across sports
- Portfolio optimization impossible

After UGO:
- Single mathematical language: `edge_std = (mu - line) / sigma`
- Every sport outputs same schema
- ESS/FAS work universally
- Kelly criterion applies across portfolio

---

## 📐 THE UNIVERSAL EDGE SCHEMA

### Core Fields (Non-Negotiable)

```python
{
  "edge_id": "NBA::LeBron_James::PTS::25.5",
  "sport": "NBA",
  "entity": "LeBron James",
  "market": "PTS",
  "line": 25.5,
  "direction": "HIGHER",
  
  # STATISTICAL CORE
  "mu": 28.3,              # Projection (stat anchor)
  "sigma": 4.2,            # Standard deviation
  "edge_std": 0.67,        # (mu - line) / sigma ← Z-SCORE
  "sample_n": 10,          # Games in sample
  
  # GOVERNANCE
  "probability": 0.72,     # Adjusted probability [0-1]
  "confidence": 0.68,      # Certainty measure [0-1]
  "tier": "STRONG",        # SLAM/STRONG/LEAN/AVOID
  "pick_state": "OPTIMIZABLE",  # RAW/ADJUSTED/VETTED/OPTIMIZABLE/REJECTED
  
  # STABILITY (ESS)
  "ess_score": 0.68,
  "stability_tags": ["HIGH_VARIANCE"],
  "tail_risk": 0.05,
  
  # SPORT-SPECIFIC (Flexible)
  "sport_context": {
    "opponent": "GSW",
    "home_away": "HOME",
    "pace_adj": 1.05
  }
}
```

---

## 🔌 SPORT ADAPTERS

Each sport has an adapter that converts native format → UGO.

### ✅ Implemented

| Sport | Adapter Class | Status | Notes |
|-------|---------------|--------|-------|
| **NBA** | `NBAAdapter` | ✅ COMPLETE | Direct mapping from risk_first_analyzer |
| **Soccer** | `SoccerAdapter` | ✅ COMPLETE | **FIXES inverted CDF issue** |
| **Golf** | `GolfAdapter` | ✅ COMPLETE | **Hybrid: multiplier + shadow anchor** |

### 🚧 Pending

| Sport | Adapter Class | Priority | Complexity |
|-------|---------------|----------|------------|
| **CBB** | `CBBAdapter` | HIGH | Low (similar to NBA) |
| **NFL** | `NFLAdapter` | HIGH | Low (already uses mu/sigma) |
| **Tennis** | `TennisAdapter` | MEDIUM | Medium (match-based logic) |

---

## 🔧 INTEGRATION STEPS (Per Sport)

### Step 1: Create Adapter

```python
# In core/universal_governance_object.py

class CBBAdapter(SportAdapter):
    def __init__(self):
        super().__init__(Sport.CBB)
    
    def adapt(self, cbb_edge: Dict) -> UniversalGovernanceObject:
        # Map CBB fields → UGO
        return UniversalGovernanceObject(
            edge_id=cbb_edge['edge_id'],
            sport=Sport.CBB,
            entity=cbb_edge['player'],
            mu=cbb_edge['mean'],  # CBB uses 'mean'
            sigma=cbb_edge['std'],  # CBB uses 'std'
            # ... rest of mapping
        )

# Register adapter
SPORT_ADAPTERS[Sport.CBB] = CBBAdapter()
```

### Step 2: Update Pipeline

```python
# In sports/cbb/cbb_main.py (end of pipeline)

from core.universal_governance_object import adapt_edge, Sport

# After generating CBB edges
cbb_edges = [...]  # Your current output

# Convert to UGO
ugo_edges = [adapt_edge(Sport.CBB, edge) for edge in cbb_edges]

# Export both formats (backward compatibility)
with open('outputs/cbb_edges_native.json', 'w') as f:
    json.dump(cbb_edges, f, indent=2)

with open('outputs/cbb_edges_ugo.json', 'w') as f:
    json.dump([ugo.to_dict() for ugo in ugo_edges], f, indent=2)
```

### Step 3: Validate

```python
from core.universal_governance_object import validate_ugo

for ugo in ugo_edges:
    is_valid, error = validate_ugo(ugo)
    if not is_valid:
        print(f"❌ INVALID: {ugo.edge_id} — {error}")
```

---

## 🔬 SOCCER FIX (Critical)

### The Problem

Soccer was using **inverted CDF**:
```python
z_score = (line - mean) / std  # ❌ WRONG for governance
```

This breaks:
- ESS comparability (negative z-scores confuse stability)
- FAS attribution (tail risk calculation inverted)
- Mental model consistency (line-centric vs stat-centric)

### The Solution

`SoccerAdapter` **standardizes to stat-centric**:
```python
# In SoccerAdapter.adapt()
mu = xg_projection['home']  # Or away
sigma = mu ** 0.5  # Poisson variance
edge_std = (mu - line) / sigma  # ✅ CORRECT (stat-centric)
```

**Math is unchanged**, governance compatibility is restored.

---

## 🏌️ GOLF HYBRID (Shadow Anchor)

### The Challenge

Golf uses **multiplier-based edges** (market efficiency), not stat projections.

But ESS/FAS need `mu`, `sigma`, `edge_std` to function.

### The Solution: Shadow Anchor

Golf adapter creates a **performance shadow**:

```python
# In GolfAdapter.adapt()

# PRIMARY: Multiplier edge (preserved)
prob = implied_prob_from_multiplier(golf_edge['higher_mult'])

# SHADOW: Performance anchor (for ESS/FAS)
sg_total = golf_edge['sg_total']  # Strokes Gained Total
mu = baseline_score - sg_total    # Expected score
sigma = abs(sg_total * 0.3)       # Variance estimate
edge_std = (mu - line) / sigma    # Z-score (governance)

# Store both in UGO
ugo.probability = prob  # From multiplier (market efficiency)
ugo.mu = mu            # From SG:Total (performance anchor)
ugo.sport_context = {
    'higher_mult': golf_edge['higher_mult'],  # Preserve pricing edge
    'sg_total': sg_total,                     # Preserve performance
}
```

This enables:
- **FAS:** Attribute failures to SG variance, course difficulty
- **ESS:** Measure stability via SG consistency
- **Portfolio:** Compare golf edges to NBA/NFL via z-score

---

## 📊 CROSS-SPORT PORTFOLIO (Future Phase 3)

With UGO, you can now do:

```python
from core.universal_governance_object import adapt_edge, Sport

# Load edges from all sports
nba_edges = load_nba_edges()
nfl_edges = load_nfl_edges()
soccer_edges = load_soccer_edges()

# Convert all to UGO
all_ugos = []
all_ugos.extend([adapt_edge(Sport.NBA, e) for e in nba_edges])
all_ugos.extend([adapt_edge(Sport.NFL, e) for e in nfl_edges])
all_ugos.extend([adapt_edge(Sport.SOCCER, e) for e in soccer_edges])

# Filter to OPTIMIZABLE only
optimizable = [ugo for ugo in all_ugos if ugo.is_optimizable()]

# Sort by edge_std (universal z-score)
top_edges = sorted(optimizable, key=lambda x: abs(x.edge_std), reverse=True)[:10]

# Portfolio optimization (Kelly criterion)
for ugo in top_edges:
    edge_pct = (ugo.probability - 0.5) * 2  # Edge over 50%
    kelly_fraction = edge_pct * ugo.confidence
    print(f"{ugo.sport.value} {ugo.entity} {ugo.market}: {kelly_fraction:.2%} bankroll")
```

**This is now possible because all sports speak the same language.**

---

## 🚦 VALIDATION CHECKLIST

Before deploying UGO for a sport:

- [ ] Adapter converts native format → UGO
- [ ] `mu` is stat projection (not line-anchored)
- [ ] `sigma` is standard deviation (not variance)
- [ ] `edge_std = (mu - line) / sigma` (z-score)
- [ ] `probability` in [0, 1] (not percentage)
- [ ] `confidence` in [0, 1] (governance-adjusted)
- [ ] `sample_n >= 1` (games/matches)
- [ ] `tier` from config/thresholds.py
- [ ] `pick_state` follows state machine
- [ ] `stability_tags` populated for OPTIMIZABLE
- [ ] `validate_ugo()` passes

---

## 🎯 NEXT STEPS

### Phase 1 (COMPLETE) ✅
- [x] Create UGO schema
- [x] Implement NBA adapter
- [x] Implement Soccer adapter (fix inverted CDF)
- [x] Implement Golf adapter (shadow anchor)
- [x] Validation logic

### Phase 2 (CURRENT)
- [ ] Implement CBB adapter
- [ ] Implement NFL adapter
- [ ] Implement Tennis adapter
- [ ] Update all sport pipelines to export UGO
- [ ] Backward compatibility (export both native + UGO)

### Phase 3 (FUTURE)
- [ ] ESS integration with UGO
- [ ] FAS integration with UGO
- [ ] Cross-sport portfolio optimizer
- [ ] Kelly criterion bankroll allocation
- [ ] Correlation matrix (cross-sport)

---

## 📝 USAGE EXAMPLES

### Example 1: Convert NBA Edge

```python
from core.universal_governance_object import adapt_edge, Sport

nba_edge = {
    'player': 'LeBron James',
    'stat': 'PTS',
    'line': 25.5,
    'direction': 'higher',
    'mu': 28.3,
    'sigma': 4.2,
    'sample_n': 10,
    'probability': 0.72,
    'tier': 'STRONG',
    'pick_state': 'OPTIMIZABLE',
}

ugo = adapt_edge(Sport.NBA, nba_edge)
print(f"Edge Z-Score: {ugo.edge_std:.2f}")  # 0.67
print(f"Optimizable: {ugo.is_optimizable()}")  # True
```

### Example 2: Validate Edge

```python
from core.universal_governance_object import validate_ugo

is_valid, error = validate_ugo(ugo)
if not is_valid:
    raise ValueError(f"Invalid UGO: {error}")
```

### Example 3: Cross-Sport Comparison

```python
nba_ugo = adapt_edge(Sport.NBA, nba_edge)
soccer_ugo = adapt_edge(Sport.SOCCER, soccer_edge)

# Compare z-scores (universal metric)
print(f"NBA edge_std: {nba_ugo.edge_std:.2f}")      # 0.67
print(f"Soccer edge_std: {soccer_ugo.edge_std:.2f}")  # 0.82

# Soccer edge is stronger (higher z-score)
```

---

## 🔒 IMMUTABILITY RULE

**Once v1.0 is locked, UGO schema is IMMUTABLE.**

Changes require:
1. New version (v2.0)
2. Migration script
3. Backward compatibility layer

This ensures governance stability.

---

## 📞 SUPPORT

Questions about UGO implementation:
- Check adapter examples in `core/universal_governance_object.py`
- Review Soccer adapter for inverted CDF fix
- Review Golf adapter for hybrid approach

**UGO is the keystone. Everything else depends on this working correctly.**
