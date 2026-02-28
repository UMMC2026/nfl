# FUOOM DARK MATTER — VS CODE COPILOT QUICK REFERENCE

## 🎯 ONE SENTENCE
**Before modeling probability, ask: "Should this prop exist at all?"**

---

## 📋 PIPELINE ORDER (DIRECTION FIRST!)

```
GATE 1: Direction       → "Does a path exist?" (FIRST!)
GATE 2: Minutes & Role  → "Can this happen?"
GATE 3: Variance        → "Is this predictable?"
        ↓
ONLY THEN → Probability Modeling
```

**Why Direction First?**
- If direction is wrong, nothing else matters
- Wrong direction = no edge = immediate kill
- Catches μ > line but UNDER selected BEFORE checking minutes

---

## 🚦 GATE 1: DIRECTION

| Check | Rule | Action |
|-------|------|--------|
| μ > line but UNDER | Wrong direction | **BLOCK** |
| μ < line but OVER | Wrong direction | **BLOCK** |
| \|z\| < 0.50 | Coin flip | **BLOCK** |
| Obstacles > 25% | Can't survive | **BLOCK** |

**Code:**
```python
from gates import DirectionGate
gate = DirectionGate()
result = gate.validate(mu=1.6, sigma=1.7, line=1.5, direction="UNDER")
# BLOCKS: μ=1.6 > line=1.5 means OVER is correct, not UNDER
```

---

## 🚦 GATE 2: MINUTES & ROLE

| Check | Rule | Action |
|-------|------|--------|
| Volume OVER + <22 min | Impossible | **BLOCK** |
| FRINGE role | Too fragile | **BLOCK** |
| PPM < 0.40 + OVER | Efficiency trap | **BLOCK** |
| BENCH role | High variance | CAP at STRONG |

**Code:**
```python
from gates import MinutesRoleGate
gate = MinutesRoleGate()
result = gate.check(expected_minutes=18.0, stat_type="PTS", direction="OVER")
```

---

## 🚦 GATE 3: VARIANCE

| Check | Rule | Action |
|-------|------|--------|
| CV > 60% | Extreme | **BLOCK** |
| CV > 45% | High | CAP at STRONG |
| PRA OVER + CV > 35% | Triple variance | **BLOCK** |
| Low volume (μ < 2) | Binary outcome | **BLOCK** |

**Code:**
```python
from gates import VarianceKillSwitch
gate = VarianceKillSwitch()
result = gate.check(mu=3.0, sigma=2.5, stat_type="3PM", sample_size=10, direction="OVER")
# BLOCKS: CV = 83% is extreme
```

---

## 🔧 FULL PIPELINE

```python
from gates import PreModelPipeline

pipeline = PreModelPipeline()
result = pipeline.run(
    player_id="player_123",
    stat_type="PTS",
    line=15.5,
    direction="OVER",
    expected_minutes=28.0,
    mu=18.5,
    sigma=4.0,
    sample_size=10,
    obstacles=["back_to_back"],
)

if result.allowed:
    # Proceed to probability modeling
    constraints = result.constraints  # Has max_tier, slam_eligible, etc.
else:
    # Skip this prop
    print(f"Blocked by {result.blocked_by}: {result.reason}")
```

---

## ⚡ ROLE REFERENCE

| Minutes | Role | Max Tier | SLAM? | Blowout Impact |
|---------|------|----------|-------|----------------|
| 32+ | STAR | SLAM | ✓ | Sits (hurts OVER) |
| 26-32 | STARTER | SLAM | ✓ | Sits |
| 18-26 | BENCH | STRONG | ✗ | Plays more |
| <18 | FRINGE | LEAN | ✗ | Plays more |

---

## 📊 CALIBRATION (AFTER GATES PASS)

| Stat | Multiplier | Direction | Multiplier |
|------|------------|-----------|------------|
| Points | ×0.85 | OVER | ×0.94 |
| 3PM | ×0.80 | UNDER | ×1.03 |
| Assists | ×1.10 | — | — |
| PRA | ×0.85 | — | — |

**Formula:**
```
Final Conf = Raw MC × Stat Mult × Dir Mult × Context × (1 - Obstacle Penalty)
```

---

## ❌ COMMON MISTAKES

1. **Placing gates after probability** → Gates must run FIRST
2. **Using gates to adjust μ** → Gates BLOCK, they don't adjust
3. **Skipping logging** → Every block needs audit trail
4. **Wrong direction not blocked** → This is why bad picks exist

---

## ✅ SUCCESS METRICS

- [ ] Volume reduction: 60-70% fewer props
- [ ] Zero negative edge picks
- [ ] Zero wrong-direction picks  
- [ ] 100% tier alignment
- [ ] Every block logged with reason

---

## 📁 FILES

```
/gates/
├── __init__.py
├── direction_gate.py       # Gate 1 (Direction First)
├── minutes_role_gate.py    # Gate 2
├── variance_kill_switch.py # Gate 3
└── pre_model_pipeline.py   # Orchestrator
```

---

**Remember: Gates decide PERMISSION. Probability decides CONFIDENCE.**
