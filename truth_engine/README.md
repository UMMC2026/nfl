# Dynamic Truth Engine

A probabilistic dependency graph system for maintaining live betting intelligence. Evolves the UFA system from Single Truth to Dynamic Truth with real-time evidence updates, constraint propagation, and diagnostic safeguards.

## Architecture Overview

The Dynamic Truth Engine models player performance as interconnected nodes in a probabilistic graph:

- **PlayerNode**: Stateful nodes containing prior distributions and live posteriors
- **DependencyEdge**: Constraints between players (teammates, opponents, role dependencies)
- **Evidence**: Live data streams (PBP, commentary, tracking) with confidence weighting
- **Diagnostics**: Health monitoring, sensitivity analysis, and quarantine mechanisms

## Key Features

- **Bayesian Updates**: Evidence adjusts priors without replacing truth
- **Constraint Propagation**: Player performances are linked through game situations
- **Diagnostic Safeguards**: Automatic quarantine of unstable or low-confidence components
- **Real-time Processing**: Async evidence processing with queue management
- **Health Monitoring**: Comprehensive system health metrics and alerting

## Quick Start

```python
from truth_engine import TruthEngine, PlayerNode, EvidenceBundle

# Initialize engine
engine = TruthEngine()

# Add a player node
node = PlayerNode(
    player_id="lebron_james",
    player_name="LeBron James",
    team="LAL",
    minutes_prior=35.0,
    usage_prior=25.0
)
engine.add_player_node(node)

# Submit live evidence
evidence = EvidenceBundle(
    player_id="lebron_james",
    evidence_type=EvidenceType.PLAY_BY_PLAY,
    timestamp=datetime.now()
)
# Add evidence signals...
engine.submit_evidence(evidence)

# Get live projection
projection = engine.get_projection("lebron_james", "points", 28.5, "higher")
```

## Core Components

### PlayerNode
Represents a player's probabilistic state with:
- Base statistical distributions (priors)
- Live adjustments (posteriors) from evidence
- Dependency relationships
- Health diagnostics and quarantine status

### Evidence System
Processes multiple evidence types:
- **PBP (Play-by-Play)**: Game action analysis
- **Commentary**: Analyst insights with NLP
- **Tracking**: Biomechanical performance data
- **Injury Reports**: Health status updates

Each evidence bundle includes integrity validation and time-based decay.

### Dependency Edges
Model relationships between players:
- **Teammate Usage**: Minutes/possessions competition
- **Opponent Matchup**: Defensive assignments
- **Role Constraints**: Strategic dependencies
- **Injury Backup**: Substitution patterns

### Diagnostic Layer
Maintains system stability:
- Confidence scoring for all components
- Sensitivity analysis for risk assessment
- Automatic quarantine of problematic nodes
- Health metrics and alerting system

## Integration with UFA

The engine integrates with existing UFA components:

```python
# In existing pipeline stages
from truth_engine import update_truth, get_live_projection

# During evidence processing
result = update_truth({
    "bundles": [evidence_bundle],
    "game_context": game_data
})

# During probability calculation
live_prob = get_live_projection(player_id, stat, line, direction)
if live_prob:
    # Use live projection instead of static
    probability = live_prob["probability"]
```

## Configuration

Engine configuration through constructor:
```python
engine = TruthEngine(
    storage_path=Path("outputs/truth_engine"),  # State persistence
    diagnostic_log_path=Path("logs/diagnostics.log")  # Health logging
)
```

## Health Monitoring

```python
# Get system health report
health = engine.get_system_health()
print(f"System health: {health['system_health_score']:.2f}")

# Check active alerts
alerts = engine.get_active_alerts()
for alert in alerts:
    print(f"ALERT: {alert['level']} - {alert['message']}")
```

## Backup and Recovery

```python
# Create backup
backup_path = engine.create_backup("pre_game_backup")

# Automatic state persistence on updates
# Engine saves state after each evidence processing cycle
```

## Safety Mechanisms

- **Quarantine System**: Automatically isolates unstable components
- **Integrity Validation**: Rejects corrupted evidence bundles
- **Confidence Thresholds**: Filters low-quality updates
- **Cascade Prevention**: Limits propagation of erroneous updates
- **Time Decay**: Reduces confidence of stale evidence

## Performance Characteristics

- Async evidence processing with queue management
- Thread pool for CPU-intensive operations
- Incremental updates (no full graph recomputation)
- Lazy evaluation of constraints
- Compressed state storage

## Development Status

✅ **Implemented**:
- Core node/edge/evidence classes
- Bayesian update logic
- Constraint propagation
- Diagnostic engine with alerting
- Async processing framework
- State persistence
- Health monitoring

🔄 **Next Steps**:
- LLM integration for evidence interpretation
- Advanced NLP for commentary analysis
- Real-time data feed integration
- Monte Carlo simulation for projections
- Web dashboard for monitoring

## File Structure

```
truth_engine/
├── __init__.py          # Package exports
├── truth_engine.py      # Main orchestrator
├── player_node.py       # Player state management
├── evidence.py          # Evidence processing
├── dependency_edge.py   # Constraint modeling
├── diagnostics.py       # Health monitoring
└── README.md           # This file
```

## Dependencies

- scipy: Statistical distributions and calculations
- asyncio: Async processing
- pathlib: File system operations
- json: State serialization
- logging: Diagnostic logging
- dataclasses: Data structure definitions

## Testing

Run diagnostic cycle:
```python
await engine.run_diagnostic_cycle()
health = engine.get_system_health()
assert health["system_health_score"] > 0.8
```

## Troubleshooting

**Common Issues**:

1. **Low System Health**: Check active alerts with `get_active_alerts()`
2. **Quarantined Nodes**: Review quarantine reasons in node metadata
3. **Stale Projections**: Ensure evidence feeds are active
4. **High Sensitivity**: Run sensitivity analysis on affected components

**Debug Mode**:
Enable detailed logging:
```python
import logging
logging.getLogger("TruthEngine").setLevel(logging.DEBUG)
```