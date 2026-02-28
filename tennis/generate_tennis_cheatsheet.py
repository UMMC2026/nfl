"""
Tennis Props Cheat Sheet Generator
==================================
Same format as NBA cheat sheet:
- Tiered recommendations
- Clean, actionable format
- Probability & edge display
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# TennisEdge can be a dict or dataclass - handle both
TennisEdge = Dict[str, Any]


def generate_tennis_cheatsheet(edges: List[TennisEdge], timestamp: str = None) -> str:
    """
    Generate NBA-style cheat sheet for tennis props.
    
    Format:
    - Header with summary
    - Props grouped by tier (SLAM → STRONG → LEAN)
    - Each prop shows: Player, Stat, Direction, Line, Probability, Edge
    """
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = []
    lines.append("=" * 90)
    lines.append("🎾 TENNIS PROPS CHEAT SHEET - MONTE CARLO ANALYSIS")
    lines.append(f"   Generated: {timestamp}")
    lines.append("=" * 90)
    
    # Helper to get edge attribute (supports both dict and object)
    def _get(edge, key, default=None):
        return edge.get(key, default) if isinstance(edge, dict) else getattr(edge, key, default)
    
    # Summary
    tier_counts = {'SLAM': 0, 'STRONG': 0, 'LEAN': 0}
    for edge in edges:
        tier = _get(edge, 'tier')
        if tier in tier_counts:
            tier_counts[tier] += 1
    
    lines.append(f"\n📊 SUMMARY: {tier_counts['SLAM']} SLAM | {tier_counts['STRONG']} STRONG | {tier_counts['LEAN']} LEAN")
    lines.append("")
    
    # Group by tier
    by_tier = {'SLAM': [], 'STRONG': [], 'LEAN': []}
    for edge in edges:
        tier = _get(edge, 'tier')
        if tier in by_tier:
            by_tier[tier].append(edge)
    
    # Display each tier
    for tier in ['SLAM', 'STRONG', 'LEAN']:
        tier_edges = by_tier[tier]
        
        if not tier_edges:
            continue
        
        lines.append("\n" + "=" * 90)
        lines.append(f"🎯 {tier} PICKS ({len(tier_edges)})")
        lines.append("=" * 90)
        
        for edge in tier_edges:
            # Format direction with arrow
            direction = _get(edge, 'direction', 'HIGHER')
            arrow = "⬆️" if direction == "HIGHER" else "⬇️"
            direction_str = f"{arrow} {direction}"

            player = _get(edge, 'player', 'Unknown')
            stat_type = _get(edge, 'stat_type', _get(edge, 'market', _get(edge, 'stat', 'Unknown')))
            line = _get(edge, 'line', 0)
            prob = _get(edge, 'probability', 0)
            edge_pct = _get(edge, 'edge', 0)
            # Prefer filtered mean if present
            filtered_mean = edge.get('filtered_games_mean') or edge.get('filtered_aces_mean')
            raw_mean = edge.get('raw_games_mean') or edge.get('raw_aces_mean') or _get(edge, 'mean', _get(edge, 'mu', 0))
            mean = filtered_mean if filtered_mean is not None else raw_mean
            std = edge.get('kalman_games_var') or edge.get('kalman_aces_var') or _get(edge, 'std', _get(edge, 'sigma', 0))
            conf = _get(edge, 'confidence', 0)
            sample = _get(edge, 'sample_size', _get(edge, 'n_matches', 0))
            sims = _get(edge, 'simulations', _get(edge, 'n_simulations', 10000))

            lines.append(f"\n{player} - {stat_type} {direction_str} {line}")
            lines.append(f"  Probability: {prob:.1%}  |  Edge: +{edge_pct:.1%}")
            if filtered_mean is not None:
                lines.append(f"  Monte Carlo: μ={mean:.2f} (Filtered), raw={raw_mean:.2f}, σ={std:.2f}  |  Confidence: {conf}")
            else:
                lines.append(f"  Monte Carlo: μ={mean:.2f}, σ={std:.2f}  |  Confidence: {conf}")
            lines.append(f"  Sample: {sample} matches  |  Simulations: {sims:,}")
    
    # Footer
    lines.append("\n" + "=" * 90)
    lines.append("📈 METHODOLOGY:")
    lines.append("  • Monte Carlo simulations (10,000+ iterations per prop)")
    lines.append("  • Player stats: L10 performance with variance modeling")
    lines.append("  • Tier assignment: SLAM ≥75%, STRONG ≥65%, LEAN ≥55%")
    lines.append("  • Confidence caps applied based on sample size and variance")
    lines.append("=" * 90)
    
    return '\n'.join(lines)


def save_cheatsheet(edges: List[TennisEdge], filename: str = None) -> Path:
    """Save cheat sheet to outputs folder"""
    outputs_dir = Path(__file__).parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"TENNIS_CHEATSHEET_{timestamp}.txt"
    
    filepath = outputs_dir / filename
    
    cheatsheet = generate_tennis_cheatsheet(edges)
    filepath.write_text(cheatsheet, encoding='utf-8')
    
    print(f"\n✓ Cheat sheet saved: {filepath}")
    return filepath


# Test
if __name__ == "__main__":
    from tennis_stats_api import TennisStatsAPI
    from tennis_monte_carlo import TennisMonteCarloEngine
    from tennis_edge_detector import TennisEdgeDetector
    
    # Get stats
    api = TennisStatsAPI()
    sinner = api.get_player_stats("Jannik Sinner")
    alcaraz = api.get_player_stats("Carlos Alcaraz")
    gauff = api.get_player_stats("Coco Gauff")
    
    # Run Monte Carlo
    engine = TennisMonteCarloEngine(10000)
    props = [
        ("Jannik Sinner", "Fantasy Score", 34.0),
        ("Jannik Sinner", "Aces", 8.0),
        ("Carlos Alcaraz", "Games Won", 20.5),
        ("Carlos Alcaraz", "Breakpoints Won", 4.5),
        ("Coco Gauff", "Fantasy Score", 16.0),
        ("Coco Gauff", "Games Won", 12.5),
    ]
    
    mc_results = engine.simulate_multiple_props([sinner, alcaraz, gauff], props)
    
    # Detect edges
    detector = TennisEdgeDetector()
    edges = detector.batch_analyze(mc_results)
    
    # Generate cheat sheet
    cheatsheet = generate_tennis_cheatsheet(edges)
    print(cheatsheet)
    
    # Save
    save_cheatsheet(edges)
