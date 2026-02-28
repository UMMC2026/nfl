"""
NFL Props Analyzer - Complete PrizePicks Integration
NFL_AUTONOMOUS v1.0 Compatible

Main entry point for analyzing NFL props using market simulator.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

# Add project root and engines/nfl to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "engines" / "nfl"))

# Import directly from modules (avoid __init__.py that requires nfl_data_py)
from nfl_markets import NFLMarket, get_market_from_string, MARKET_DISPLAY_NAMES
from market_simulator import NFLMarketSimulator, SimulationResult
from edge_collapse import collapse_to_primary_lines, EdgeCollapser


class NFLPropsAnalyzer:
    """Main analyzer for NFL props with PrizePicks market support."""
    
    def __init__(self):
        self.simulator = NFLMarketSimulator()
        self.collapser = EdgeCollapser(reasonable_threshold=0.30)
    
    def analyze_player_slate(
        self,
        slate_data: List[Dict[str, Any]],
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Analyze complete slate of NFL props.
        
        Args:
            slate_data: List of prop dicts with keys:
                - player_id, player_name, position
                - game_id, opponent_team
                - market (string or NFLMarket)
                - line, direction
                - player_features (optional)
                - opponent_features (optional)
                - game_context (optional)
            output_path: Where to save results (optional)
        
        Returns:
            Dict with analyzed edges, stats, and recommendations
        """
        print(f"\n{'='*60}")
        print(f"🏈 NFL PROPS ANALYZER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}\n")
        
        print(f"📊 Analyzing {len(slate_data)} props...\n")
        
        # Process each prop
        all_edges = []
        failed = []
        
        for i, prop in enumerate(slate_data, 1):
            try:
                edge = self._analyze_single_prop(prop)
                if edge:
                    all_edges.append(edge)
                    
                if i % 10 == 0:
                    print(f"  Processed {i}/{len(slate_data)} props...")
            except Exception as e:
                failed.append({
                    'prop': prop,
                    'error': str(e)
                })
                print(f"  ⚠️  Failed: {prop.get('player_name', '?')} {prop.get('market', '?')}")
        
        print(f"\n✅ Analysis complete: {len(all_edges)} edges generated\n")
        
        # Collapse to primary lines
        print("🔄 Collapsing to primary lines...")
        collapsed_edges = collapse_to_primary_lines(all_edges, reasonable_threshold=0.30)
        print(f"✅ {len(collapsed_edges)} primary edges selected\n")
        
        # Rank edges
        ranked = sorted(collapsed_edges, key=lambda e: e['probability'], reverse=True)
        
        # Generate summary
        summary = self._generate_summary(ranked)
        
        # Build result
        result = {
            'timestamp': datetime.now().isoformat(),
            'total_props_analyzed': len(slate_data),
            'edges_generated': len(all_edges),
            'primary_edges': len(collapsed_edges),
            'failed': len(failed),
            'summary': summary,
            'edges': ranked,
            'failures': failed
        }
        
        # Save if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"💾 Results saved to: {output_path}\n")
        
        # Print summary
        self._print_summary(summary, ranked[:10])
        
        return result
    
    def _analyze_single_prop(self, prop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze a single prop and return edge dict."""
        # Parse market
        market_str = prop.get('market', '')
        market = get_market_from_string(market_str) if isinstance(market_str, str) else market_str
        
        if not market:
            return None
        
        # Get features (or use defaults)
        player_features = prop.get('player_features', self._get_default_features(prop))
        opponent_features = prop.get('opponent_features', {})
        game_context = prop.get('game_context', {'is_home': True, 'wind_mph': 0})
        
        # Get line and direction
        line = float(prop.get('line', 0))
        direction = prop.get('direction', 'over').lower()
        
        # Simulate
        result = self.simulator.simulate_market(
            market=market,
            player_features=player_features,
            opponent_features=opponent_features,
            game_context=game_context,
            lines=[line]
        )
        
        # Calculate probability based on direction
        if direction in ('over', 'higher'):
            probability = result.prob_over.get(line, 0.5)
        else:
            probability = 1 - result.prob_over.get(line, 0.5)
        
        # Build edge dict
        return {
            'player_id': prop.get('player_id', ''),
            'player_name': prop.get('player_name', ''),
            'game_id': prop.get('game_id', ''),
            'market': market.value,
            'line': line,
            'direction': direction,
            'probability': probability,
            'edge_strength': probability - 0.5,
            'expected_value': result.mean,
            'std_dev': result.std,
            'distribution': result.distribution_type,
            'position': player_features.get('position', '')
        }
    
    def _get_default_features(self, prop: Dict[str, Any]) -> Dict[str, Any]:
        """Generate default features if not provided."""
        position = prop.get('position', 'UNKNOWN')
        market_str = prop.get('market', '')
        
        # Very basic defaults - in production, would load from database
        if 'pass' in market_str.lower():
            return {
                'position': 'QB',
                'pass_attempts_rate': 35.0,
                'yards_per_attempt': 7.0,
                'completion_pct': 0.65,
                'pass_td_rate': 1.8
            }
        elif 'rush' in market_str.lower():
            return {
                'position': 'RB',
                'rush_attempt_share': 15.0,
                'yards_before_contact': 2.5,
                'yards_per_carry': 4.2
            }
        elif 'rec' in market_str.lower():
            return {
                'position': 'WR',
                'target_share': 0.20,
                'catch_rate': 0.65,
                'adot': 12.0
            }
        else:
            return {'position': position}
    
    def _generate_summary(self, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not edges:
            return {}
        
        # Count by market
        by_market = {}
        for edge in edges:
            market = edge['market']
            if market not in by_market:
                by_market[market] = []
            by_market[market].append(edge)
        
        # Count by position
        by_position = {}
        for edge in edges:
            pos = edge.get('position', 'UNKNOWN')
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(edge)
        
        # Probability distribution
        prob_buckets = {
            '50-60%': len([e for e in edges if 0.50 <= e['probability'] < 0.60]),
            '60-70%': len([e for e in edges if 0.60 <= e['probability'] < 0.70]),
            '70-80%': len([e for e in edges if 0.70 <= e['probability'] < 0.80]),
            '80%+': len([e for e in edges if e['probability'] >= 0.80])
        }
        
        return {
            'total_edges': len(edges),
            'avg_probability': sum(e['probability'] for e in edges) / len(edges),
            'by_market': {k: len(v) for k, v in by_market.items()},
            'by_position': {k: len(v) for k, v in by_position.items()},
            'prob_distribution': prob_buckets,
            'top_markets': sorted(by_market.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        }
    
    def _print_summary(self, summary: Dict[str, Any], top_edges: List[Dict[str, Any]]):
        """Print formatted summary to console."""
        print(f"{'='*60}")
        print("📈 ANALYSIS SUMMARY")
        print(f"{'='*60}\n")
        
        print(f"Total Edges: {summary['total_edges']}")
        print(f"Average Probability: {summary['avg_probability']:.1%}\n")
        
        print("Probability Distribution:")
        for bucket, count in summary['prob_distribution'].items():
            print(f"  {bucket}: {count} edges")
        
        print(f"\nTop Markets:")
        for market, count in summary['top_markets']:
            display_name = MARKET_DISPLAY_NAMES.get(NFLMarket(market), market)
            print(f"  {display_name}: {count} edges")
        
        print(f"\n{'='*60}")
        print("🔥 TOP 10 EDGES")
        print(f"{'='*60}\n")
        
        for i, edge in enumerate(top_edges, 1):
            market_display = MARKET_DISPLAY_NAMES.get(NFLMarket(edge['market']), edge['market'])
            direction_symbol = "↑" if edge['direction'] in ('over', 'higher') else "↓"
            print(f"{i:2d}. {edge['player_name']:<20} {market_display:<20} "
                  f"{direction_symbol} {edge['line']:<6.1f} @ {edge['probability']:.1%}")
        
        print(f"\n{'='*60}\n")


def analyze_from_json(input_file: Path, output_file: Optional[Path] = None) -> Dict:
    """
    Analyze props from JSON file.
    
    Expected JSON format:
    [
      {
        "player_name": "Patrick Mahomes",
        "position": "QB",
        "market": "pass_yards",
        "line": 275.5,
       "direction": "over",
        "opponent_team": "BUF",
        "game_id": "KC_BUF"
      },
      ...
    ]
    """
    with open(input_file, 'r') as f:
        slate_data = json.load(f)
    
    analyzer = NFLPropsAnalyzer()
    return analyzer.analyze_player_slate(slate_data, output_path=output_file)


def analyze_from_clipboard():
    """Analyze props from clipboard (paste PrizePicks slate)."""
    print("📋 Paste your PrizePicks slate (Ctrl+D or Ctrl+Z when done):\n")
    
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    # Parse slate (basic parser - would be more sophisticated in production)
    slate_data = _parse_prizepicks_text(lines)
    
    analyzer = NFLPropsAnalyzer()
    output_path = Path(f"outputs/nfl_analysis_{datetime.now():%Y%m%d_%H%M%S}.json")
    return analyzer.analyze_player_slate(slate_data, output_path=output_path)


def _parse_prizepicks_text(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse PrizePicks text format (simplified)."""
    # This would be much more sophisticated in production
    # For now, return empty list - use JSON input instead
    print("⚠️  Text parsing not yet implemented. Please use JSON format.")
    return []


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NFL Props Analyzer with PrizePicks support")
    parser.add_argument("--input", "-i", type=Path, help="Input JSON file with slate data")
    parser.add_argument("--output", "-o", type=Path, help="Output JSON file for results")
    parser.add_argument("--clipboard", "-c", action="store_true", help="Read from clipboard")
    
    args = parser.parse_args()
    
    if args.clipboard:
        analyze_from_clipboard()
    elif args.input:
        analyze_from_json(args.input, args.output)
    else:
        print("Usage:")
        print("  python nfl_props_analyzer.py --input slate.json")
        print("  python nfl_props_analyzer.py --clipboard")
