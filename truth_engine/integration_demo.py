#!/usr/bin/env python3
"""
Truth Engine Integration Example

Demonstrates how the Dynamic Truth Engine integrates with existing UFA components
for live betting intelligence.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Import from truth_engine package
from truth_engine import (
    TruthEngine, PlayerNode, EvidenceBundle, EvidenceProcessor,
    EvidenceType, EvidenceSource, EvidenceSignal, DependencyEdge, EdgeFactory
)


async def setup_sample_graph(engine: TruthEngine):
    """Set up a sample player graph for demonstration."""
    print("Setting up sample player graph...")

    # Create player nodes
    players_data = [
        {"id": "lebron_james", "name": "LeBron James", "team": "LAL", "minutes": 35, "usage": 25},
        {"id": "anthony_davis", "name": "Anthony Davis", "team": "LAL", "minutes": 32, "usage": 22},
        {"id": "austin_reaves", "name": "Austin Reaves", "team": "LAL", "minutes": 28, "usage": 18},
        {"id": "dangelo_russell", "name": "D'Angelo Russell", "team": "LAL", "minutes": 30, "usage": 20},
    ]

    for player in players_data:
        node = PlayerNode(
            player_id=player["id"],
            player_name=player["name"],
            team=player["team"],
            minutes_prior=float(player["minutes"]),
            usage_prior=float(player["usage"])
        )
        engine.add_player_node(node)

    # Create dependency edges
    edges = [
        EdgeFactory.create_teammate_usage_edge("lebron_james", "anthony_davis", shared_minutes=65),
        EdgeFactory.create_teammate_usage_edge("austin_reaves", "dangelo_russell", shared_minutes=55),
        EdgeFactory.create_opponent_matchup_edge("lebron_james", "opponent_guard"),  # Placeholder
    ]

    for edge in edges:
        engine.add_dependency_edge(edge)

    print(f"Created graph with {len(engine.graph_state.nodes)} nodes and {len(engine.graph_state.edges)} edges")


async def simulate_live_evidence(engine: TruthEngine):
    """Simulate live evidence updates during a game."""
    print("\nSimulating live evidence updates...")

    # Simulate PBP evidence for LeBron
    pbp_evidence = EvidenceBundle(
        player_id="lebron_james",
        evidence_type=EvidenceType.PLAY_BY_PLAY,
        timestamp=datetime.now()
    )

    # Add signals (simulated high usage early)
    pbp_evidence.minutes_signal = EvidenceSignal(
        value=38.5,  # Played more minutes than expected
        confidence=0.85,
        strength=0.8,
        timestamp=datetime.now(),
        source=EvidenceSource.ESPN
    )

    pbp_evidence.usage_signal = EvidenceSignal(
        value=28.0,  # Higher usage than prior
        confidence=0.8,
        strength=0.7,
        timestamp=datetime.now(),
        source=EvidenceSource.ESPN
    )

    # Submit evidence
    engine.submit_evidence(pbp_evidence)

    # Wait for processing
    await asyncio.sleep(0.1)

    # Simulate fatigue evidence from commentary
    commentary_text = "LeBron James showing signs of fatigue in the fourth quarter, breathing heavily on the sidelines."

    commentary_evidence = engine.evidence_processor.process_commentary_data(
        commentary_text, "lebron_james"
    )

    engine.submit_evidence(commentary_evidence)

    # Wait for processing
    await asyncio.sleep(0.1)

    print("Processed live evidence updates")


async def demonstrate_projections(engine: TruthEngine):
    """Demonstrate getting live projections."""
    print("\nDemonstrating live projections...")

    # Get projection for LeBron points
    projection = engine.get_projection("lebron_james", "points", 28.5, "higher")

    if projection:
        print(f"LeBron points > 28.5: {projection['probability']:.3f} (confidence: {projection['confidence']:.2f})")
    else:
        print("No projection available (node may be quarantined)")

    # Get projection for Davis rebounds
    projection = engine.get_projection("anthony_davis", "rebounds", 12.5, "higher")

    if projection:
        print(f"AD rebounds > 12.5: {projection['probability']:.3f} (confidence: {projection['confidence']:.2f})")
    else:
        print("No projection available for AD")


async def run_diagnostics(engine: TruthEngine):
    """Run and display diagnostic information."""
    print("\nRunning diagnostics...")

    await engine.run_diagnostic_cycle()

    health = engine.get_system_health()
    print(f"System Health Score: {health['system_health_score']:.3f}")

    alerts = engine.get_active_alerts()
    if alerts:
        print(f"Active Alerts: {len(alerts)}")
        for alert in alerts[:3]:  # Show first 3
            print(f"  {alert['level'].upper()}: {alert['message']}")
    else:
        print("No active alerts")

    # Show component status
    components = health['components']
    print(f"Nodes: {components['nodes']['active']}/{components['nodes']['total']} active")
    print(f"Edges: {components['edges']['active']}/{components['edges']['total']} active")


def demonstrate_integration_points():
    """Show how this integrates with existing UFA code."""
    print("\n" + "="*60)
    print("INTEGRATION POINTS WITH EXISTING UFA")
    print("="*60)

    integration_code = '''
# In daily_pipeline.py - during resolve stage
from truth_engine import update_truth

def resolve_stage():
    """Enhanced resolve stage with live truth updates."""
    # Existing ground truth fetch
    ground_truth = get_ground_truth()

    # NEW: Update truth engine with live evidence
    evidence_bundles = extract_evidence_from_games(ground_truth)
    update_result = update_truth({
        "bundles": evidence_bundles,
        "game_context": get_live_game_context()
    })

    # Existing validation logic...
    validated_edges = validate_edges_with_truth(ground_truth)

    return validated_edges

# In score_edges.py - during probability calculation
from truth_engine import get_live_projection

def calculate_probability(pick):
    """Enhanced probability with live projections."""
    # Check for live projection first
    live_proj = get_live_projection(
        pick["player_id"],
        pick["stat"],
        pick["line"],
        pick["direction"]
    )

    if live_proj and live_proj["confidence"] > 0.7:
        # Use live projection
        probability = live_proj["probability"]
        source = "dynamic_truth"
    else:
        # Fall back to static calculation
        probability = calculate_static_probability(pick)
        source = "static_model"

    return probability, source

# In menu.py - add monitoring option
def show_system_status():
    """Display truth engine status."""
    from truth_engine import get_system_status

    status = get_system_status()
    print(f"Engine Status: {status['engine_status']}")
    print(f"Nodes Active: {status['nodes_active']}")
    print(f"Alerts: {status['alerts_active']}")
    print(f"Last Update: {status['last_update']}")
    print(f"System Health: {status['system_health']:.1%}")
'''

    print(integration_code)


async def main():
    """Main demonstration function."""
    print("Dynamic Truth Engine Integration Demo")
    print("="*50)

    # Initialize engine
    engine = TruthEngine(storage_path=Path("outputs/truth_engine_demo"))

    try:
        # Setup
        await setup_sample_graph(engine)

        # Simulate live updates
        await simulate_live_evidence(engine)

        # Show projections
        await demonstrate_projections(engine)

        # Run diagnostics
        await run_diagnostics(engine)

        # Show integration points
        demonstrate_integration_points()

        print("\n" + "="*50)
        print("Demo completed successfully!")
        print("Check outputs/truth_engine_demo/ for persisted state")

    except Exception as e:
        print(f"Error during demo: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Graceful shutdown
        await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())