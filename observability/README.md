# 📊 FUOOM Observability Layer - Quick Reference

## Installation Complete ✅

Packages installed:
- `prometheus_client` - Metrics collection
- `opentelemetry-api` / `opentelemetry-sdk` - Distributed tracing
- `pybreaker` - Circuit breaker pattern

## Access Methods

### 1. From Main Menu
```
[OB] Observability — Metrics, Health, Circuit Breakers
```

### 2. Command Line
```bash
# Full dashboard
.venv\Scripts\python.exe -m observability.dashboard

# Health only
.venv\Scripts\python.exe -m observability.dashboard --health

# Circuits only
.venv\Scripts\python.exe -m observability.dashboard --circuits

# Metrics only
.venv\Scripts\python.exe -m observability.dashboard --metrics

# Interactive mode
.venv\Scripts\python.exe -m observability.dashboard -i
```

### 3. In Code
```python
from observability import metrics, circuit_breaker, tracer, health

# Record metrics
metrics.record_edge_generated("NBA", "PTS", "STRONG")
metrics.record_edge_rejected("NBA", "AST", "LOW_PROBABILITY")
metrics.record_gate_pass("NBA", "eligibility")
metrics.record_api_call("espn_api", success=True, latency=0.5)

# Time operations
with metrics.time_operation("NBA", "full_pipeline"):
    # ... your code ...
    pass

# Circuit breaker
@circuit_breaker.protect("espn_api")
def fetch_from_espn():
    # Auto-opens circuit after 3 failures
    # Auto-recovers after 60 seconds
    pass

# Tracing
with tracer.span("analyze_player", player="LeBron") as span:
    span.set_attribute("stat", "PTS")
    span.add_event("data_loaded")
    # ... analysis ...

# Health check
status = health.get_overall_status()
health.print_status()
```

## Pre-Configured Circuit Breakers

| API | Fail Threshold | Reset Timeout |
|-----|---------------|---------------|
| espn_api | 3 | 60s |
| basketball_reference | 5 | 120s |
| underdog_api | 3 | 30s |
| nba_api | 3 | 60s |
| tennis_api | 5 | 90s |
| telegram_api | 5 | 60s |
| serpapi | 3 | 120s |

## Health Checks

Built-in checks:
- `cache_directory` - Cache health, stale files
- `outputs_directory` - Output count, today's files
- `calibration_data` - Calibration freshness
- `config_files` - Required configs present

## Files Created

```
observability/
├── __init__.py          # Main exports
├── metrics.py           # Prometheus metrics
├── circuit_breaker.py   # Circuit breaker manager
├── tracer.py            # Distributed tracing
├── health.py            # Health checks
├── dashboard.py         # Console dashboard
└── integration.py       # Pipeline integration helpers
```

## Integration Example

In your existing pipeline:
```python
from observability.integration import (
    instrument_api_call,
    instrument_gate,
    wrap_pipeline
)

@wrap_pipeline("NBA")
def run_daily_analysis():
    # Full pipeline traced and timed
    pass

@instrument_api_call("espn_api")
def fetch_player_stats(player_id):
    # Auto circuit breaker + metrics
    pass

with instrument_gate("NBA", "eligibility"):
    # Gate pass/fail recorded
    if probability < 0.55:
        raise ValueError("Low probability")
```

## What This Solves

1. ✅ **Peak Volume Blindness** → Now have real-time metrics
2. ✅ **API Cascade Failures** → Circuit breakers prevent crashes
3. ✅ **No Observability** → Full health/metrics/tracing dashboard
4. ✅ **Debugging Nightmares** → Trace every operation

## Next Steps

1. Wire circuit breakers to your API calls (ESPN, Basketball Reference, etc.)
2. Add tracing spans to your main pipelines
3. Set up metrics recording in edge generation
4. Check dashboard regularly on game days
