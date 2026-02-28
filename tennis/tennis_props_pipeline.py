"""
Tennis Props Pipeline Orchestrator
==================================
Full pipeline like NBA system:
1. Parse props from Underdog paste
2. Fetch player stats
3. Run Monte Carlo simulations
4. Detect edges & assign tiers
5. Generate cheat sheet

Same architecture as daily_pipeline.py
"""

from pathlib import Path
from datetime import datetime
from typing import List
import sys

sys.path.insert(0, str(Path(__file__).parent))

from tennis_props_parser import parse_tennis_props, TennisProp
from tennis_stats_api import TennisStatsAPI, TennisPlayerStats
from tennis_monte_carlo import TennisMonteCarloEngine, MonteCarloResult
from tennis_edge_detector import TennisEdgeDetector, TennisEdge


class TennisPropsAnalysisPipeline:
    """Full tennis props analysis pipeline"""
    
    def __init__(self, num_simulations: int = 10000):
        self.stats_api = TennisStatsAPI()
        self.mc_engine = TennisMonteCarloEngine(num_simulations)
        self.edge_detector = TennisEdgeDetector()
        
        self.outputs_dir = Path(__file__).parent / "outputs"
        self.outputs_dir.mkdir(exist_ok=True)
    
    def run_full_pipeline(self, underdog_paste: str) -> dict:
        """
        Run complete analysis pipeline.
        
        Steps:
        1. Parse props from paste
        2. Deduplicate
        3. Fetch player stats
        4. Run Monte Carlo simulations
        5. Detect edges
        6. Rank by tier
        
        Returns:
            Dict with all results
        """
        print("\n" + "=" * 80)
        print("🎾 TENNIS PROPS ANALYSIS PIPELINE")
        print("=" * 80)
        
        # STEP 1: Parse props
        print("\n[1/5] PARSING PROPS...")
        props = parse_tennis_props(underdog_paste)
        print(f"  ✓ Parsed {len(props)} props")
        
        if not props:
            print("  ✗ No props found - aborting")
            return {}
        
        # STEP 2: Deduplicate
        print("\n[2/5] DEDUPLICATING...")
        unique_props = self._deduplicate_props(props)
        print(f"  ✓ {len(unique_props)} unique props (removed {len(props) - len(unique_props)} duplicates)")
        
        # STEP 3: Fetch player stats
        print("\n[3/5] FETCHING PLAYER STATS...")
        player_names = list(set(p.player for p in unique_props))
        stats_map = {}
        
        for player in player_names:
            stats = self.stats_api.get_player_stats(player)
            if stats:
                stats_map[player] = stats
        
        print(f"  ✓ Loaded stats for {len(stats_map)} players")
        
        # STEP 4: Run Monte Carlo simulations
        print("\n[4/5] RUNNING MONTE CARLO SIMULATIONS...")
        mc_props = [
            (p.player, p.stat, p.line)
            for p in unique_props
            if p.player in stats_map
        ]
        
        mc_results = self.mc_engine.simulate_multiple_props(
            list(stats_map.values()),
            mc_props
        )
        
        print(f"  ✓ Simulated {len(mc_results)} props ({self.mc_engine.num_simulations:,} iterations each)")
        
        # STEP 5: Detect edges
        print("\n[5/5] DETECTING EDGES & ASSIGNING TIERS...")
        # mc_results is a dict {key: MonteCarloResult} - pass the VALUES not the dict
        edges = self.edge_detector.batch_analyze(list(mc_results.values()))
        
        tier_counts = self._count_by_tier(edges)
        print(f"  ✓ Found {len(edges)} playable edges:")
        for tier, count in tier_counts.items():
            print(f"     {tier}: {count}")
        
        print("\n" + "=" * 80)
        print("✅ PIPELINE COMPLETE")
        print("=" * 80)
        
        return {
            'raw_props': props,
            'unique_props': unique_props,
            'player_stats': stats_map,
            'mc_results': mc_results,
            'edges': edges,
            'tier_counts': tier_counts,
            'timestamp': datetime.now().isoformat()
        }
    
    def _deduplicate_props(self, props: List[TennisProp]) -> List[TennisProp]:
        """Remove duplicate props"""
        seen = set()
        unique = []
        
        for prop in props:
            key = (prop.player, prop.stat, prop.line)
            if key not in seen:
                seen.add(key)
                unique.append(prop)
        
        return unique
    
    def _count_by_tier(self, edges: List) -> dict:
        """Count edges by tier - handles both dict and object edges"""
        counts = {'SLAM': 0, 'STRONG': 0, 'LEAN': 0}
        
        for edge in edges:
            # Support both dict and object access
            tier = edge.get('tier') if isinstance(edge, dict) else getattr(edge, 'tier', None)
            if tier in counts:
                counts[tier] += 1
        
        return counts


# Interactive mode
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🎾 TENNIS PROPS ANALYSIS - MONTE CARLO ENGINE")
    print("=" * 80)
    print("\nPaste Underdog tennis props below (Press Enter twice when done):\n")
    
    lines = []
    empty_count = 0
    
    while empty_count < 2:
        try:
            line = input()
            if not line.strip():
                empty_count += 1
            else:
                empty_count = 0
                lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break
    
    if not lines:
        print("\n[!] No input received")
        sys.exit(0)
    
    paste = '\n'.join(lines)
    
    # Run pipeline
    pipeline = TennisPropsAnalysisPipeline(num_simulations=10000)
    results = pipeline.run_full_pipeline(paste)
    
    # Display top edges
    if results.get('edges'):
        print("\n" + "=" * 80)
        print("TOP EDGES (RANKED BY TIER & PROBABILITY)")
        print("=" * 80)
        
        for edge in results['edges'][:10]:  # Top 10
            # Support both dict and object access
            if isinstance(edge, dict):
                tier = edge.get('tier', 'N/A')
                player = edge.get('player', 'Unknown')
                stat = edge.get('stat_type', edge.get('market', edge.get('stat', 'Unknown')))
                direction = edge.get('direction', 'HIGHER')
                line = edge.get('line', 0)
                prob = edge.get('probability', 0)
                edge_pct = edge.get('edge', 0)
            else:
                tier = edge.tier
                player = edge.player
                stat = edge.stat_type
                direction = edge.direction
                line = edge.line
                prob = edge.probability
                edge_pct = edge.edge
            
            print(f"\n[{tier}] {player} - {stat} {direction} {line}")
            print(f"  Probability: {prob:.1%} | Edge: +{edge_pct:.1%}")
            print(f"  Mean: {edge.mean:.2f} ± {edge.std:.2f} | Confidence: {edge.confidence}")
