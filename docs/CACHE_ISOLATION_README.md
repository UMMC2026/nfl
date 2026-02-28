# FUOOM Cache & Validation System - Integration Guide

## Overview

This document describes the production-ready artifacts for sport-isolated caching, namespace enforcement, and output validation in the FUOOM betting analysis system.

---

## Quick Start

### 1. Clean Existing Contamination (ONE-TIME)

```powershell
# Diagnose first (dry-run)
.venv\Scripts\python.exe tools/clean_sport_cache.py --sport CBB --diagnose

# Clean with audit trail (dry-run)
.venv\Scripts\python.exe tools/clean_sport_cache.py --sport CBB --dry-run

# Execute cleanup
.venv\Scripts\python.exe tools/clean_sport_cache.py --sport CBB
```

### 2. Validate Outputs

```powershell
# Validate edges from file
.venv\Scripts\python.exe -m validation.validate_output outputs/edges.json --sport NBA

# Check all validation checks
.venv\Scripts\python.exe -m validation.validate_output --list-checks
```

### 3. Track Calibration

```powershell
# Initialize database
.venv\Scripts\python.exe calibration_tracker.py --init

# Record a pick
.venv\Scripts\python.exe calibration_tracker.py --record pick --data '{"edge_id": "...", ...}'

# Generate report
.venv\Scripts\python.exe calibration_tracker.py --report --sport NBA
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FUOOM CACHE ISOLATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │  clean_sport_   │    │  cache_writer   │    │   cache_    │ │
│  │    cache.py     │───▶│     .py         │◀───│  manager.py │ │
│  │  (ONE-TIME)     │    │  (WRITE-TIME)   │    │  (RUNTIME)  │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│         │                       │                     │         │
│         │                       │                     │         │
│         ▼                       ▼                     ▼         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SPORT-ISOLATED CACHES                    ││
│  │  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐     ││
│  │  │  NBA  │  │  CBB  │  │ TENNIS│  │  NFL  │  │ GOLF  │     ││
│  │  └───────┘  └───────┘  └───────┘  └───────┘  └───────┘     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. `tools/clean_sport_cache.py` — One-Time Cleanup

**Purpose**: Remove cross-sport contamination from legacy caches.

**Usage**:
```python
from tools.clean_sport_cache import SportCacheCleaner

cleaner = SportCacheCleaner("CBB")
audit = cleaner.diagnose()
cleaner.clean(dry_run=False)
```

**Flags**:
- `--sport SPORT` — Target sport (required)
- `--diagnose` — Show what would be cleaned
- `--dry-run` — Simulate without deleting
- `--force` — Skip confirmation prompt

**Audit Log**: Written to `tools/cache_cleanup_audit_{sport}_{timestamp}.json`

---

### 2. `core/cache/cache_writer.py` — Write-Time Enforcement

**Purpose**: Prevent cross-sport writes at the source (not read-time filtering).

**Usage**:
```python
from core.cache import SportCacheWriter, CacheContextGuard

# Create writer for specific sport
writer = SportCacheWriter(sport="CBB", version="v1")

# Generate namespaced key
key = writer.make_key("player", "cooper_flagg", "DUKE")
# Returns: "CBB::v1::player::cooper_flagg::DUKE"

# Write with validation
writer.write("player::cooper_flagg::DUKE", {"points_avg": 18.5})

# Context guard (rejects cross-sport writes in block)
with CacheContextGuard("CBB"):
    # All cache operations here must be CBB
    writer.write(key, data)
```

**Canonical Key Format**: `{SPORT}::{VERSION}::{ENTITY}`

---

### 3. `cache_manager.py` — Runtime Cache Management

**Purpose**: Singleton cache manager with sport isolation and diagnostics.

**Usage**:
```python
from cache_manager import CacheManager, CacheDiagnosticTool

# Get sport-specific manager
manager = CacheManager.for_sport("CBB")

# Set/get with automatic namespacing
manager.set("player:cooper_flagg", {"pts": 18.5})
data = manager.get("player:cooper_flagg")

# Diagnostics
diag = CacheDiagnosticTool()
report = diag.scan_for_contamination()
diag.fix_contamination("CBB", dry_run=False)
```

**CLI**:
```powershell
# Diagnose contamination
.venv\Scripts\python.exe cache_manager.py --diagnose

# Clean specific sport
.venv\Scripts\python.exe cache_manager.py --clean --sport CBB

# Fix cross-sport keys
.venv\Scripts\python.exe cache_manager.py --fix-contamination --sport CBB
```

---

### 4. `validation/validate_output.py` — Output Validation Gate

**Purpose**: Hard gate before render/broadcast — blocks malformed outputs.

**Usage**:
```python
from validation import EdgeValidator, TierConfig

validator = EdgeValidator(sport="NBA")
result = validator.validate(edges)

if not result.passed:
    for error in result.errors:
        print(f"[{error['severity']}] {error['check']}: {error['message']}")
    raise RuntimeError("Validation failed")
```

**Validation Checks**:
| Check | Severity | Description |
|-------|----------|-------------|
| `NO_DUPLICATE_EDGES` | CRITICAL | No duplicate edge_ids |
| `NO_DUPLICATE_PRIMARY_PLAYERS` | CRITICAL | One primary edge per player per game |
| `NO_CORRELATED_IN_TIERS` | ERROR | Correlated edges excluded from tiers |
| `TIER_PROBABILITY_ALIGNMENT` | CRITICAL | Tier label matches probability |
| `REQUIRED_FIELDS` | ERROR | All required fields present |
| `PICK_STATE_VALID` | WARNING | Valid pick_state value |

**Sport-Specific Tiers**:
```python
# CBB: No SLAM tier
TierConfig(sport="CBB")
# SLAM: disabled (None)
# STRONG: 70%+
# LEAN: 60-70%

# GOLF: No SLAM tier
TierConfig(sport="GOLF")
# SLAM: disabled (None)
# STRONG: 68%+
# LEAN: 58-68%
```

---

### 5. `calibration_tracker.py` — Result Tracking & Drift Detection

**Purpose**: SQLite-based calibration tracking with Brier scores and drift alerts.

**Usage**:
```python
from calibration_tracker import CalibrationTracker, Pick, Result

tracker = CalibrationTracker()

# Record pick
pick = Pick(
    edge_id="NBA_2024_abc123",
    sport="NBA",
    player="LeBron James",
    stat_type="points",
    line=25.5,
    direction="over",
    probability=0.72,
    tier="STRONG"
)
tracker.record_pick(pick)

# Record result
result = Result(
    edge_id="NBA_2024_abc123",
    actual_value=28,
    hit=True
)
tracker.record_result(result)

# Generate report
report = tracker.generate_report(sport="NBA")
print(f"Win Rate: {report.win_rate:.1%}")
print(f"Brier Score: {report.brier_score:.3f}")

# Check for drift
drift = tracker.check_drift(sport="NBA", window_days=7)
if drift["drifting"]:
    print(f"DRIFT ALERT: {drift['message']}")
```

**Built-in Queries**:
```powershell
# Daily performance
.venv\Scripts\python.exe calibration_tracker.py --query daily_performance

# Calibration by probability bucket
.venv\Scripts\python.exe calibration_tracker.py --query calibration_by_bucket

# Overconfidence detection
.venv\Scripts\python.exe calibration_tracker.py --query overconfidence_detection

# Direction bias
.venv\Scripts\python.exe calibration_tracker.py --query direction_bias

# Brier score trend
.venv\Scripts\python.exe calibration_tracker.py --query brier_score_trend
```

---

### 6. `config/fuoom_config_locked.json` — Locked Configuration

**Purpose**: Immutable configuration parameters. Changes require SOP review.

**Key Sections**:
- `tier_definitions` — Probability ranges per tier
- `sport_tier_overrides` — CBB/GOLF/TENNIS specific tiers
- `stat_distributions` — Statistical models per stat type
- `multi_window_weights` — L3/L5/L10/L20/season weights
- `confidence_calibration` — Data-driven multipliers
- `cbb_specific_settings` — CBB guards and caps
- `validation_gates` — Pre-render checks

**Usage**:
```python
import json
from pathlib import Path

config = json.loads(Path("config/fuoom_config_locked.json").read_text())

# Get CBB tier thresholds
cbb_tiers = config["sport_tier_overrides"]["CBB"]
# SLAM: null (disabled)
# STRONG: min 0.70
# LEAN: min 0.60

# Get stat distribution for NBA points
dist = config["stat_distributions"]["NBA"]["points"]
# distribution: t_distribution, df: 5
```

---

## Integration Patterns

### Pipeline Integration

```python
from core.cache import SportCacheWriter, CacheContextGuard
from cache_manager import CacheManager
from validation import EdgeValidator
from calibration_tracker import CalibrationTracker

def run_cbb_pipeline(slate):
    """Example CBB pipeline with full isolation."""
    
    # 1. Assert sport context
    with CacheContextGuard("CBB"):
        
        # 2. Get sport-specific cache
        cache = CacheManager.for_sport("CBB")
        writer = SportCacheWriter("CBB", "v1")
        
        # 3. Process slate
        edges = analyze_slate(slate, cache)
        
        # 4. Validate before render
        validator = EdgeValidator("CBB")
        result = validator.validate(edges)
        
        if not result.passed:
            raise RuntimeError(f"Validation failed: {result.errors}")
        
        # 5. Track picks
        tracker = CalibrationTracker()
        for edge in edges:
            if edge["pick_state"] == "OPTIMIZABLE":
                tracker.record_pick_from_edge(edge)
        
        # 6. Render (only if validation passed)
        render_report(edges)
```

### CBB-Specific Guards

```python
from config.fuoom_config_locked import load_config

config = load_config()
cbb_guards = config["cbb_specific_settings"]["guards"]

def apply_cbb_guards(edge, player_data):
    """Apply CBB-specific confidence guards."""
    
    confidence = edge["probability"]
    
    # Usage volatility clamp
    if cbb_guards["usage_volatility_clamp"]["enabled"]:
        if player_data.get("minutes_std", 0) > cbb_guards["usage_volatility_clamp"]["minutes_std_threshold"]:
            confidence *= cbb_guards["usage_volatility_clamp"]["confidence_multiplier"]
    
    # Coaching pace guard
    if cbb_guards["coaching_pace_guard"]["enabled"]:
        pace_rank_change = abs(player_data.get("pace_rank", 0) - player_data.get("prev_pace_rank", 0))
        if pace_rank_change > cbb_guards["coaching_pace_guard"]["pace_rank_change_threshold"]:
            confidence = min(confidence, cbb_guards["coaching_pace_guard"]["confidence_cap"])
    
    # Freshman/transfer penalty
    if cbb_guards["freshman_transfer_penalty"]["enabled"]:
        if player_data.get("class_year") in cbb_guards["freshman_transfer_penalty"]["class_years"]:
            confidence *= cbb_guards["freshman_transfer_penalty"]["half_life_multiplier"]
    
    # Hard cap
    confidence = min(confidence, config["cbb_specific_settings"]["caps"]["max_confidence"])
    
    return confidence
```

---

## File Locations

| File | Purpose |
|------|---------|
| `tools/clean_sport_cache.py` | One-time cache cleanup |
| `core/cache/cache_writer.py` | Write-time namespace enforcement |
| `core/cache/__init__.py` | Module exports |
| `cache_manager.py` | Runtime cache management |
| `validation/validate_output.py` | Output validation gate |
| `validation/__init__.py` | Module exports |
| `calibration_tracker.py` | SQLite calibration tracking |
| `config/fuoom_config_locked.json` | Locked configuration |

---

## Error Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `CacheNamespaceError` | Cross-sport write attempted | Ensure correct sport context |
| `CacheContextError` | Write outside CacheContextGuard | Wrap operations in context guard |
| `ValidationError: NO_DUPLICATE_EDGES` | Duplicate edge_ids | Deduplicate edges in pipeline |
| `ValidationError: TIER_PROBABILITY_ALIGNMENT` | Tier doesn't match probability | Check tier thresholds for sport |
| `DriftAlert` | Calibration drift detected | Review recent model changes |

---

## Changelog

### v1.0.0 (2026-01-31)
- Initial production release
- Sport-isolated caching with namespace enforcement
- Output validation gate with 6 checks
- SQLite calibration tracking with drift detection
- CBB-specific guards (usage volatility, coaching pace, freshman penalty)
- Locked configuration with SOP v2.1 compliance

---

## Support

For issues with these components:
1. Check the audit log at `tools/cache_cleanup_audit_*.json`
2. Run diagnostics: `.venv\Scripts\python.exe cache_manager.py --diagnose`
3. Validate outputs: `.venv\Scripts\python.exe -m validation.validate_output --list-checks`
