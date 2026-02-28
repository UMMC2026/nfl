# FUOOM DARK MATTER — VS CODE AI COPILOT DIRECTIVE
## Complete System Integration Package

**Version:** 2.2 (Direction-First)  
**Date:** February 10, 2026  
**Status:** PRODUCTION READY

---

# 📌 COPILOT MASTER DIRECTIVE

You are integrating a **pre-model judgment layer** into an existing sports betting system.
This is NOT a refactor. This is adding THREE NEW GATES before probability calculation.

**Critical Understanding:**
- The existing system is infrastructure (calibration, tiers, risk controls)
- The new layer is judgment (vetoes that kill bad ideas before math runs)
- These gates BLOCK, they do not ADJUST

---

# SECTION 1: SYSTEM ARCHITECTURE

## 1.1 Required Pipeline Order

```
CURRENT (broken):
Raw Stats → Projection → Probability → Calibration → Tiers → Output

REQUIRED (correct):
Raw Stats
    ↓
[GATE 1] minutes_role_gate.py      ← BLOCKS on opportunity
    ↓
[GATE 2] direction_gate.py         ← BLOCKS on thesis
    ↓
[GATE 3] variance_kill_switch.py   ← BLOCKS on stability
    ↓
Projection (μ)
    ↓
Monte Carlo → P(OVER), P(UNDER)
    ↓
Stat Calibration
    ↓
Direction Calibration
    ↓
Context Adjustments
    ↓
Caps & Gates
    ↓
[FINAL] validate_output.py         ← BLOCKS on math errors
    ↓
Output
```

**Copilot MUST NOT place gates after probability calculation.**

---

## 1.2 Directory Structure

```
/fuoom/
├── gates/                          ← NEW DIRECTORY
│   ├── __init__.py
│   ├── minutes_role_gate.py        ← Gate 1
│   ├── direction_gate.py           ← Gate 2
│   ├── variance_kill_switch.py     ← Gate 3
│   └── pre_model_pipeline.py       ← Orchestrator
├── shared/
│   ├── math_utils.py               ← Already built
│   └── constants.py
├── calibration/
│   ├── stat_calibration.py
│   ├── direction_calibration.py
│   └── context_adjustments.py      ← Already built
├── projection/
│   ├── probability_trace.py        ← Already built
│   └── minutes_model.py            ← Already built
├── validation/
│   └── validate_output.py          ← Already built
└── config/
    └── .analysis_config.json       ← Already built
```

---

# SECTION 2: GATE 1 — MINUTES & ROLE ACCESS GATE

## 2.1 File: `gates/minutes_role_gate.py`

### Purpose
Determine if a prop is **physically possible** given player opportunity.
This is ACCESS CONTROL, not analytics.

### Inputs (no new data sources)
```python
expected_minutes: float      # From projection or recent average
stat_type: str               # PTS, REB, AST, 3PM, PRA, etc.
line: float                  # Market line
player_id: str
game_id: str
ppm: float                   # Points per minute (optional)
```

### Role Classification (DETERMINISTIC)
```python
def classify_role(minutes: float) -> str:
    """
    Classify player role strictly by minutes.
    Do NOT use player name, team, or external data.
    """
    if minutes >= 32:
        return "STAR"
    elif minutes >= 26:
        return "STARTER"
    elif minutes >= 18:
        return "BENCH"
    else:
        return "FRINGE"
```

### Access Rules (HARD BLOCKS)
```python
# Volume stats that require minutes
VOLUME_STATS = ["PTS", "POINTS", "PRA", "PTS+REB", "PTS+AST", 
                "PTS+REB+AST", "FANTASY"]

# Minimum minutes by stat type
MIN_MINUTES = {
    "VOLUME": 22,      # PTS, PRA, combos
    "REBOUNDS": 18,    # Can get boards in limited time
    "ASSISTS": 20,     # Need touches
    "3PM": 15,         # Efficiency stat
    "STEALS": 12,      # Opportunity-based
    "BLOCKS": 12,      # Opportunity-based
}

def check_minutes_access(
    expected_minutes: float,
    stat_type: str,
    direction: str
) -> tuple[bool, str]:
    """
    Check if minutes support this prop.
    Returns (allowed, reason).
    """
    stat_upper = stat_type.upper()
    
    # Volume stat OVER with low minutes
    if stat_upper in VOLUME_STATS:
        if expected_minutes < MIN_MINUTES["VOLUME"]:
            if direction.upper() in ["OVER", "HIGHER"]:
                return False, f"OVER requires ≥22 min, player has {expected_minutes:.1f}"
    
    # Fringe players blocked entirely for volume
    role = classify_role(expected_minutes)
    if role == "FRINGE" and stat_upper in VOLUME_STATS:
        return False, f"FRINGE role ({expected_minutes:.1f} min) - volume stats blocked"
    
    return True, "PASSED"
```

### PPM Trap Detection
```python
def check_ppm_viability(
    ppm: float,
    stat_type: str,
    direction: str
) -> tuple[bool, str]:
    """
    Check if scoring rate supports the direction.
    Low PPM + OVER = trap.
    """
    if stat_type.upper() in ["PTS", "POINTS"]:
        if ppm < 0.40 and direction.upper() in ["OVER", "HIGHER"]:
            return False, f"PPM {ppm:.2f} < 0.40 - OVER is a trap"
    return True, "PASSED"
```

### Role Constraints (SOFT — propagate downstream)
```python
def get_role_constraints(role: str) -> dict:
    """
    Return constraints based on role.
    These propagate to downstream modules.
    """
    constraints = {
        "STAR": {
            "slam_eligible": True,
            "max_tier": "SLAM",
            "variance_flag": "LOW",
            "blowout_vulnerable": True,   # Stars sit in blowouts
        },
        "STARTER": {
            "slam_eligible": True,
            "max_tier": "SLAM",
            "variance_flag": "NORMAL",
            "blowout_vulnerable": True,
        },
        "BENCH": {
            "slam_eligible": False,
            "max_tier": "STRONG",
            "variance_flag": "HIGH",
            "blowout_vulnerable": False,  # Bench plays MORE in blowouts
        },
        "FRINGE": {
            "slam_eligible": False,
            "max_tier": "LEAN",
            "variance_flag": "EXTREME",
            "blowout_vulnerable": False,
        },
    }
    return constraints.get(role, constraints["BENCH"])
```

### Output Contract
```python
@dataclass
class MinutesRoleResult:
    allowed: bool
    reason: str
    role: str
    expected_minutes: float
    constraints: dict
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "role": self.role,
            "expected_minutes": self.expected_minutes,
            "constraints": self.constraints,
        }
```

### Logging (REQUIRED)
```python
def log_gate_decision(result: MinutesRoleResult, player_id: str, stat: str):
    """Every decision MUST be logged."""
    if not result.allowed:
        logger.info(
            f"[BLOCKED][MINUTES_ROLE_GATE] "
            f"Player: {player_id} | Stat: {stat} | "
            f"Minutes: {result.expected_minutes:.1f} | "
            f"Role: {result.role} | "
            f"Reason: {result.reason}"
        )
    else:
        logger.debug(
            f"[PASSED][MINUTES_ROLE_GATE] "
            f"Player: {player_id} | Role: {result.role} | "
            f"Constraints: {result.constraints}"
        )
```

---

# SECTION 3: GATE 2 — DIRECTION GATE

## 3.1 File: `gates/direction_gate.py`

### Purpose
Validate that a **real directional thesis** exists.
If direction is invalid, probability is meaningless.

### Core Principle
```
Direction is decided BEFORE probability.
If direction is weak, probability cannot fix it.
```

### Direction Validation Rules
```python
def validate_direction(
    mu: float,           # Recent average
    sigma: float,        # Standard deviation
    line: float,         # Market line
    direction: str,      # OVER or UNDER
    hit_rate: float = None  # Optional historical hit rate
) -> tuple[bool, str]:
    """
    Validate that direction makes mathematical sense.
    """
    z_score = (line - mu) / sigma if sigma > 0 else 0.0
    
    # Rule 1: Raw direction must match
    raw_direction = "OVER" if mu > line else "UNDER"
    if direction.upper() != raw_direction:
        return False, (
            f"DIRECTION MISMATCH: μ={mu:.1f} vs line={line} "
            f"favors {raw_direction}, but {direction.upper()} selected"
        )
    
    # Rule 2: Must have meaningful edge (not coin flip)
    if abs(z_score) < 0.50:
        return False, (
            f"NO EDGE: |z|={abs(z_score):.2f} < 0.50 (coin flip zone)"
        )
    
    # Rule 3: Hit rate consistency (if provided)
    if hit_rate is not None:
        if direction.upper() == "OVER" and hit_rate < 0.40:
            return False, (
                f"HIT RATE CONFLICT: {direction.upper()} selected but "
                f"only {hit_rate:.0%} historical hit rate"
            )
        if direction.upper() == "UNDER" and hit_rate > 0.60:
            return False, (
                f"HIT RATE CONFLICT: {direction.upper()} selected but "
                f"{hit_rate:.0%} hits OVER historically"
            )
    
    return True, "PASSED"
```

### Obstacle Stress Test
```python
# Obstacle penalties by type
OBSTACLE_PENALTIES = {
    "elite_defender": 0.08,       # 8% penalty
    "elite_defense_team": 0.06,   # 6% penalty
    "blowout_risk": 0.05,         # 5% penalty (for stars)
    "back_to_back": 0.04,         # 4% penalty
    "usage_competition": 0.04,    # 4% penalty
    "foul_risk": 0.03,            # 3% penalty
    "pace_mismatch": 0.03,        # 3% penalty
    "minutes_uncertainty": 0.05,  # 5% penalty
}

def calculate_obstacle_penalty(
    obstacles: list[str],
    direction: str,
    role: str
) -> tuple[float, list[str]]:
    """
    Calculate cumulative obstacle penalty for the chosen direction.
    Some obstacles affect OVER differently than UNDER.
    """
    total_penalty = 0.0
    applied = []
    
    for obs in obstacles:
        obs_lower = obs.lower().replace(" ", "_")
        base_penalty = OBSTACLE_PENALTIES.get(obs_lower, 0.02)
        
        # Direction-specific adjustments
        if obs_lower == "blowout_risk":
            if role == "STAR" and direction.upper() == "OVER":
                # Stars sit in blowouts, OVER is vulnerable
                base_penalty *= 1.5
            elif role == "BENCH" and direction.upper() == "OVER":
                # Bench plays more in blowouts, OVER is protected
                base_penalty *= 0.3
        
        total_penalty += base_penalty
        applied.append(f"{obs}: -{base_penalty:.0%}")
    
    # Cap at 30%
    total_penalty = min(total_penalty, 0.30)
    
    return total_penalty, applied
```

### Output Contract
```python
@dataclass
class DirectionGateResult:
    allowed: bool
    reason: str
    direction: str
    z_score: float
    raw_direction: str
    obstacle_penalty: float
    obstacles_applied: list[str]
```

---

# SECTION 4: GATE 3 — VARIANCE KILL SWITCH

## 4.1 File: `gates/variance_kill_switch.py`

### Purpose
Determine if variance is **existential** (kills the prop entirely) 
or **cosmetic** (just affects confidence).

### Variance Classification
```python
def calculate_cv(mu: float, sigma: float) -> float:
    """Coefficient of variation = σ / μ"""
    if mu <= 0:
        return 1.0
    return sigma / mu

def classify_variance(
    cv: float,
    stat_type: str,
    sample_size: int
) -> tuple[str, str]:
    """
    Classify variance level and action.
    Returns (level, action).
    """
    stat_upper = stat_type.upper()
    
    # Inherently volatile stats get stricter thresholds
    volatile_stats = ["3PM", "THREES", "STEALS", "BLOCKS"]
    threshold_mult = 0.8 if stat_upper in volatile_stats else 1.0
    
    # Small sample penalty
    if sample_size < 5:
        threshold_mult *= 0.7
    elif sample_size < 10:
        threshold_mult *= 0.85
    
    # Adjusted thresholds
    kill_threshold = 0.60 * threshold_mult
    high_threshold = 0.45 * threshold_mult
    moderate_threshold = 0.30 * threshold_mult
    
    if cv > kill_threshold:
        return "EXTREME", "BLOCK"
    elif cv > high_threshold:
        return "HIGH", "CAP_STRONG"
    elif cv > moderate_threshold:
        return "MODERATE", "CAP_SLAM"
    else:
        return "LOW", "ALLOW"
```

### Kill Switch Logic
```python
def variance_kill_switch(
    mu: float,
    sigma: float,
    stat_type: str,
    sample_size: int,
    direction: str
) -> tuple[bool, str, str]:
    """
    Determine if variance kills this prop.
    Returns (allowed, action, reason).
    """
    cv = calculate_cv(mu, sigma)
    level, action = classify_variance(cv, stat_type, sample_size)
    
    # Absolute kill
    if action == "BLOCK":
        return False, action, (
            f"VARIANCE KILL: CV={cv:.1%} is EXTREME for {stat_type}"
        )
    
    # PRA OVER special case (triple variance)
    if stat_type.upper() in ["PRA", "PTS+REB+AST"]:
        if direction.upper() in ["OVER", "HIGHER"]:
            if cv > 0.35:
                return False, "BLOCK", (
                    f"PRA OVER with CV={cv:.1%} - triple variance trap"
                )
    
    return True, action, f"CV={cv:.1%} ({level})"
```

---

# SECTION 5: ORCHESTRATOR

## 5.1 File: `gates/pre_model_pipeline.py`

### Purpose
Run all gates in sequence. First failure stops the pipeline.

```python
from gates.minutes_role_gate import MinutesRoleGate
from gates.direction_gate import DirectionGate
from gates.variance_kill_switch import VarianceKillSwitch

@dataclass
class PreModelResult:
    allowed: bool
    blocked_by: str | None
    reason: str
    role: str
    constraints: dict
    direction: str
    obstacle_penalty: float
    variance_level: str

def run_pre_model_pipeline(
    player_id: str,
    stat_type: str,
    line: float,
    direction: str,
    expected_minutes: float,
    mu: float,
    sigma: float,
    sample_size: int,
    obstacles: list[str] = None,
    ppm: float = None,
    hit_rate: float = None,
) -> PreModelResult:
    """
    Run all pre-model gates in sequence.
    First failure stops the pipeline.
    """
    
    # GATE 1: Minutes & Role Access
    gate1 = MinutesRoleGate()
    result1 = gate1.check(
        expected_minutes=expected_minutes,
        stat_type=stat_type,
        direction=direction,
        ppm=ppm
    )
    
    if not result1.allowed:
        return PreModelResult(
            allowed=False,
            blocked_by="MINUTES_ROLE_GATE",
            reason=result1.reason,
            role=result1.role,
            constraints={},
            direction=direction,
            obstacle_penalty=0.0,
            variance_level="UNKNOWN"
        )
    
    # GATE 2: Direction Validation
    gate2 = DirectionGate()
    result2 = gate2.validate(
        mu=mu,
        sigma=sigma,
        line=line,
        direction=direction,
        obstacles=obstacles or [],
        role=result1.role,
        hit_rate=hit_rate
    )
    
    if not result2.allowed:
        return PreModelResult(
            allowed=False,
            blocked_by="DIRECTION_GATE",
            reason=result2.reason,
            role=result1.role,
            constraints=result1.constraints,
            direction=direction,
            obstacle_penalty=0.0,
            variance_level="UNKNOWN"
        )
    
    # GATE 3: Variance Kill Switch
    gate3 = VarianceKillSwitch()
    result3 = gate3.check(
        mu=mu,
        sigma=sigma,
        stat_type=stat_type,
        sample_size=sample_size,
        direction=direction
    )
    
    if not result3.allowed:
        return PreModelResult(
            allowed=False,
            blocked_by="VARIANCE_KILL_SWITCH",
            reason=result3.reason,
            role=result1.role,
            constraints=result1.constraints,
            direction=direction,
            obstacle_penalty=result2.obstacle_penalty,
            variance_level="EXTREME"
        )
    
    # All gates passed
    # Merge constraints from all gates
    final_constraints = result1.constraints.copy()
    
    # Apply variance-based caps
    if result3.action == "CAP_STRONG":
        final_constraints["max_tier"] = "STRONG"
        final_constraints["slam_eligible"] = False
    elif result3.action == "CAP_SLAM":
        # Only restrict if current max is higher
        pass
    
    return PreModelResult(
        allowed=True,
        blocked_by=None,
        reason="ALL GATES PASSED",
        role=result1.role,
        constraints=final_constraints,
        direction=direction,
        obstacle_penalty=result2.obstacle_penalty,
        variance_level=result3.level
    )
```

---

# SECTION 6: INTEGRATION WITH EXISTING MODULES

## 6.1 Calibration Flow (After Gates Pass)

```python
from shared.math_utils import (
    classify_tier,
    calculate_kelly,
    calculate_expected_value
)
from calibration.context_adjustments import apply_all_context_adjustments
from projection.probability_trace import trace_probability

def calculate_final_probability(
    pre_model_result: PreModelResult,
    mu: float,
    sigma: float,
    line: float,
    context: dict
) -> dict:
    """
    Calculate final probability ONLY for picks that passed pre-model gates.
    """
    
    # Run probability trace
    trace = trace_probability(
        player=pre_model_result.player_id,
        stat=pre_model_result.stat_type,
        line=line,
        mu=mu,
        sigma=sigma,
        n=context.get('sample_size', 10),
        direction=pre_model_result.direction
    )
    
    # Apply context adjustments
    context_result = apply_all_context_adjustments(
        base_projection=mu,
        base_confidence=trace.final_prob,
        stat=pre_model_result.stat_type,
        direction=pre_model_result.direction,
        context=context
    )
    
    # Apply obstacle penalty from direction gate
    adjusted_confidence = (
        context_result.adjusted_confidence * 
        (1 - pre_model_result.obstacle_penalty)
    )
    
    # Enforce role constraints
    max_tier = pre_model_result.constraints.get("max_tier", "SLAM")
    tier = classify_tier(adjusted_confidence)
    
    # Cap tier if needed
    tier_order = ["NO_PLAY", "LEAN", "STRONG", "SLAM"]
    if tier_order.index(tier) > tier_order.index(max_tier):
        tier = max_tier
        # Also cap confidence to tier ceiling
        tier_ceilings = {"LEAN": 0.64, "STRONG": 0.74, "SLAM": 0.95}
        adjusted_confidence = min(
            adjusted_confidence, 
            tier_ceilings.get(max_tier, 0.95)
        )
    
    return {
        "final_confidence": adjusted_confidence,
        "tier": tier,
        "role": pre_model_result.role,
        "variance_level": pre_model_result.variance_level,
        "obstacle_penalty": pre_model_result.obstacle_penalty,
        "constraints": pre_model_result.constraints,
    }
```

---

# SECTION 7: LOGGING REQUIREMENTS

## 7.1 Every Blocked Pick MUST Log

```python
# Format for blocked picks
[BLOCKED][{GATE_NAME}]
Player: {player_id}
Stat: {stat_type} {direction}
Line: {line}
Reason: {reason}
Context: {additional_context}
```

## 7.2 Every Passed Pick SHOULD Log (Debug Level)

```python
# Format for passed picks
[PASSED][PRE_MODEL_PIPELINE]
Player: {player_id}
Role: {role}
Constraints: {constraints}
Variance: {variance_level}
Obstacles: {obstacle_penalty:.1%}
```

---

# SECTION 8: CONFIGURATION

## 8.1 Gate Thresholds (in config file)

```json
{
  "gates": {
    "minutes_role": {
      "enabled": true,
      "min_minutes_volume": 22,
      "min_minutes_rebounds": 18,
      "min_minutes_assists": 20,
      "min_ppm_points_over": 0.40
    },
    "direction": {
      "enabled": true,
      "min_z_score": 0.50,
      "check_hit_rate_consistency": true
    },
    "variance": {
      "enabled": true,
      "cv_kill_threshold": 0.60,
      "cv_high_threshold": 0.45,
      "cv_moderate_threshold": 0.30,
      "small_sample_threshold": 5
    }
  },
  "tier_thresholds": {
    "SLAM": 0.75,
    "STRONG": 0.65,
    "LEAN": 0.55,
    "NO_PLAY": 0.00
  },
  "calibration": {
    "stat_multipliers": {
      "points": 0.85,
      "3pm": 0.80,
      "assists": 1.10,
      "rebounds": 1.00,
      "pra": 0.85
    },
    "direction_multipliers": {
      "over": 0.94,
      "under": 1.03
    }
  }
}
```

---

# SECTION 9: WHAT COPILOT MUST NOT DO

❌ **NEVER:**
- Place gates after probability calculation
- Use gates to adjust μ or σ
- Use gates to modify confidence (they BLOCK or ALLOW)
- Skip logging for blocked picks
- Allow negative Kelly picks to pass
- Allow wrong-direction picks to pass
- Treat variance as cosmetic (it can be existential)

---

# SECTION 10: SUCCESS CRITERIA

After implementation, verify:

1. **Volume Reduction:** ~60-70% fewer props reach output
2. **Zero Negative Edge:** No picks with edge ≤ 0
3. **Zero Wrong Direction:** No picks where μ contradicts direction
4. **Clean Tiers:** 100% alignment between confidence and tier
5. **Audit Trail:** Every blocked pick has a logged reason
6. **Role Constraints:** Bench players never get SLAM tier

---

# SECTION 11: TEST CASES

## Required Unit Tests

```python
def test_minutes_gate_blocks_low_minutes_over():
    """18 minutes should block POINTS OVER"""
    result = minutes_role_gate.check(
        expected_minutes=18.0,
        stat_type="PTS",
        direction="OVER"
    )
    assert result.allowed == False
    assert "22 min" in result.reason

def test_direction_gate_blocks_wrong_direction():
    """μ > line should block UNDER"""
    result = direction_gate.validate(
        mu=1.6,
        sigma=1.7,
        line=1.5,
        direction="UNDER"
    )
    assert result.allowed == False
    assert "MISMATCH" in result.reason

def test_variance_kills_extreme_cv():
    """CV > 60% should block"""
    result = variance_kill_switch.check(
        mu=5.0,
        sigma=4.0,  # CV = 80%
        stat_type="3PM",
        sample_size=10,
        direction="OVER"
    )
    assert result.allowed == False

def test_full_pipeline_passes_valid_pick():
    """Valid pick should pass all gates"""
    result = run_pre_model_pipeline(
        player_id="test",
        stat_type="PTS",
        line=15.5,
        direction="OVER",
        expected_minutes=32.0,
        mu=18.5,
        sigma=4.0,
        sample_size=10
    )
    assert result.allowed == True
    assert result.role == "STAR"
```

---

# FINAL REMINDER TO COPILOT

**This is ACCESS CONTROL, not analytics.**

Gates decide PERMISSION.
Probability decides CONFIDENCE.

Permission comes first.

**Lock this as SOP v2.2 — Direction First.**
