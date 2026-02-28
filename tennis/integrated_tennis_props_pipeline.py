"""
INTEGRATED TENNIS PROPS PIPELINE
Connects parsers + database + models into existing pipeline structure

Replaces match winner workflow with DFS props workflow
SOP v2.1 compliant with full validation gates
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Import integration modules
from tennis_props_ingestor import TennisPropsIngestor
from player_stats_database import PlayerStatsDatabase
from tennis_props_model import TennisPropsModel

# Import thresholds
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.underdog_tennis_thresholds import (
    get_underdog_threshold,
    get_market_priority,
    UNDERDOG_TENNIS_CAPS
)


# ============================================================================
# INTEGRATED PROPS PIPELINE
# ============================================================================

class IntegratedTennisPropsPipeline:
    """
    Complete end-to-end tennis props analysis pipeline
    
    Stages:
    1. Ingest (parse DFS props)
    2. Model (predict outcomes)
    3. Score (assign tiers)
    4. Validate (hard gates)
    5. Render (generate report)
    """
    
    def __init__(self, surface: str = 'hard', min_probability: float = 0.58):
        self.surface = surface
        self.min_probability = min_probability
        
        self.ingestor = TennisPropsIngestor()
        self.player_db = PlayerStatsDatabase()
        self.model = TennisPropsModel(surface=surface)
        
        self.ingestion_result = None
        self.predictions = []
        self.scored_edges = []
    
    
    def run_full_pipeline(self, input_source: str, output_dir: str = "outputs") -> Dict:
        """
        Execute complete pipeline
        
        Args:
            input_source: Path to props file or raw text
            output_dir: Directory for outputs
            
        Returns:
            Pipeline result with all stages
        """
        print("🎾 Starting Integrated Tennis Props Pipeline...")
        print(f"   Surface: {self.surface.upper()}")
        print(f"   Min Probability: {self.min_probability:.1%}\n")
        
        # Stage 1: Ingest
        print("Stage 1: Ingesting props...")
        self.ingestion_result = self._stage_ingest(input_source)
        
        if not self.ingestion_result['success']:
            return self._abort_pipeline("Ingestion failed", self.ingestion_result)
        
        print(f"✅ Ingested {self.ingestion_result['metadata']['total_players']} players, "
              f"{self.ingestion_result['metadata']['total_markets']} markets\n")
        
        # Stage 2: Model Predictions
        print("Stage 2: Generating predictions...")
        self.predictions = self._stage_predict()
        print(f"✅ Generated {len(self.predictions)} predictions\n")
        
        # Stage 3: Score Edges
        print("Stage 3: Scoring edges...")
        self.scored_edges = self._stage_score()
        print(f"✅ Scored {len(self.scored_edges)} playable edges\n")
        
        # Stage 4: Validate
        print("Stage 4: Validating output...")
        validation = self._stage_validate()
        
        if not validation['valid']:
            return self._abort_pipeline("Validation failed", validation)
        
        print(f"✅ Validation passed\n")
        
        # Stage 5: Render
        print("Stage 5: Generating reports...")
        reports = self._stage_render(output_dir)
        print(f"✅ Reports generated\n")
        
        # Summary
        self._print_summary()
        
        return {
            'success': True,
            'ingestion': self.ingestion_result,
            'predictions': len(self.predictions),
            'scored_edges': len(self.scored_edges),
            'validation': validation,
            'reports': reports
        }
    
    
    def _stage_ingest(self, input_source: str) -> Dict:
        """Stage 1: Ingest props"""
        if Path(input_source).exists():
            result = self.ingestor.ingest_from_file(input_source)
        else:
            result = self.ingestor.ingest_from_text(input_source)
        
        # Validate ingestion
        validation = self.ingestor.validate_ingestion(result)
        
        if not validation['valid']:
            result['success'] = False
            result['error'] = '; '.join(validation['errors'])
        
        return result
    
    
    def _stage_predict(self) -> List[Dict]:
        """Stage 2: Generate predictions"""
        predictions = []
        
        for prop in self.ingestion_result['props']:
            player_name = prop['player_name']
            opponent = prop.get('opponent', 'Unknown')
            
            for market_type, market_data in prop['markets'].items():
                line = market_data['line']
                
                # Generate prediction
                pred = self.model.predict_prop(
                    player_name, opponent, market_type, line
                )
                
                predictions.append({
                    'player': player_name,
                    'opponent': opponent,
                    'match_time': prop.get('match_time'),
                    'market': market_type,
                    'line': line,
                    'prediction': pred['prediction'],
                    'probability_over': pred['probability_over'],
                    'probability_under': pred['probability_under'],
                    'edge': pred['edge_value'],
                    'confidence': pred['confidence'],
                    'platform': prop.get('platform', 'unknown'),
                    'popularity': market_data.get('popularity')
                })
        
        return predictions
    
    
    def _stage_score(self) -> List[Dict]:
        """Stage 3: Score edges and assign tiers"""
        scored = []
        
        for pred in self.predictions:
            # Determine direction and probability
            if pred['probability_over'] > pred['probability_under']:
                direction = 'MORE/HIGHER'
                probability = pred['probability_over']
            else:
                direction = 'LESS/LOWER'
                probability = pred['probability_under']
            
            # Check minimum probability threshold
            if probability < self.min_probability:
                continue
            
            # Assign tier (SOP v2.1)
            tier = self._assign_tier(probability)
            
            if tier == 'NO PLAY':
                continue
            
            # Get market-specific threshold
            threshold = get_underdog_threshold(
                market_type=pred['market'],
                player_style='all_court',  # Could enhance with actual style
                tournament_stage='early_rounds',
                surface=self.surface
            )
            
            # Get priority
            priority = get_market_priority(pred['market'])
            
            scored.append({
                **pred,
                'direction': direction,
                'probability': probability,
                'tier': tier,
                'threshold': threshold,
                'priority': priority,
                'priority_rank': {'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}[priority]
            })
        
        # Sort by tier and probability
        scored.sort(key=lambda x: (
            {'SLAM': 0, 'STRONG': 1, 'LEAN': 2}[x['tier']],
            -x['probability']
        ))
        
        return scored
    
    
    def _assign_tier(self, probability: float) -> str:
        """Assign SOP v2.1 tier"""
        if probability >= 0.75:
            return 'SLAM'
        elif probability >= 0.65:
            return 'STRONG'
        elif probability >= 0.55:
            return 'LEAN'
        else:
            return 'NO PLAY'
    
    
    def _stage_validate(self) -> Dict:
        """Stage 4: Validate output"""
        errors = []
        warnings = []
        
        # Check we have playable edges
        if len(self.scored_edges) == 0:
            warnings.append("No playable edges generated")
        
        # Check each edge
        for edge in self.scored_edges:
            # Required fields
            required = ['player', 'opponent', 'market', 'line', 'probability', 'tier']
            for field in required:
                if field not in edge:
                    errors.append(f"Missing field: {field}")
            
            # Tier integrity
            if edge['tier'] == 'SLAM' and edge['probability'] < 0.75:
                errors.append(f"SLAM tier with probability {edge['probability']:.1%} < 75%")
            
            if edge['tier'] == 'STRONG' and edge['probability'] < 0.65:
                errors.append(f"STRONG tier with probability {edge['probability']:.1%} < 65%")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_edges': len(self.scored_edges)
        }
    
    
    def _stage_render(self, output_dir: str) -> Dict:
        """Stage 5: Generate output files"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON output
        json_file = output_path / f"tennis_props_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump({
                'metadata': self.ingestion_result['metadata'],
                'edges': self.scored_edges
            }, f, indent=2)
        
        # TXT report
        txt_file = output_path / f"tennis_props_report_{timestamp}.txt"
        self._generate_text_report(txt_file)
        
        return {
            'json': str(json_file),
            'txt': str(txt_file)
        }
    
    
    def _generate_text_report(self, filepath: Path):
        """Generate formatted text report"""
        lines = []
        lines.append("="*80)
        lines.append("🎾 TENNIS PROPS BETTING RECOMMENDATIONS")
        lines.append("="*80)
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Surface: {self.surface.upper()}")
        lines.append(f"Platform: {self.ingestion_result['metadata']['platform'].upper()}")
        lines.append(f"Total Recommendations: {len(self.scored_edges)}\n")
        
        # Group by tier
        tiers = {'SLAM': [], 'STRONG': [], 'LEAN': []}
        for edge in self.scored_edges:
            tier = edge['tier']
            if tier in tiers:
                tiers[tier].append(edge)
        
        # Display each tier
        for tier_name, tier_edges in tiers.items():
            if not tier_edges:
                continue
            
            icon = '🔥' if tier_name == 'SLAM' else '✅' if tier_name == 'STRONG' else '⚠️'
            
            lines.append("-"*80)
            lines.append(f"{icon} {tier_name} TIER ({len(tier_edges)} picks)")
            lines.append("-"*80 + "\n")
            
            for edge in tier_edges:
                lines.append(f"🎯 {edge['player']} vs {edge['opponent']}")
                lines.append(f"   Match: {edge.get('match_time', 'TBD')}")
                lines.append(f"   Market: {edge['market']}")
                lines.append(f"   Line: {edge['line']}")
                lines.append(f"   Prediction: {edge['prediction']:.2f}")
                lines.append(f"   Recommendation: Bet {edge['direction']}")
                lines.append(f"   Probability: {edge['probability']:.1%}")
                lines.append(f"   Edge: {edge['edge']:.2f}")
                lines.append(f"   Priority: {edge['priority']}")
                if edge.get('popularity'):
                    lines.append(f"   Popularity: {edge['popularity']}")
                lines.append("")
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(lines))
    
    
    def _print_summary(self):
        """Print pipeline summary"""
        print("="*80)
        print("PIPELINE SUMMARY")
        print("="*80 + "\n")
        
        # Tier counts
        tier_counts = {'SLAM': 0, 'STRONG': 0, 'LEAN': 0}
        for edge in self.scored_edges:
            tier = edge['tier']
            if tier in tier_counts:
                tier_counts[tier] += 1
        
        print(f"Total Playable Edges: {len(self.scored_edges)}")
        print(f"  SLAM: {tier_counts['SLAM']}")
        print(f"  STRONG: {tier_counts['STRONG']}")
        print(f"  LEAN: {tier_counts['LEAN']}\n")
        
        # Top recommendation
        if self.scored_edges:
            top = self.scored_edges[0]
            print(f"Top Recommendation:")
            print(f"  {top['player']} vs {top['opponent']}")
            print(f"  {top['market']}: Bet {top['direction']} {top['line']}")
            print(f"  Probability: {top['probability']:.1%} ({top['tier']})")
    
    
    def _abort_pipeline(self, reason: str, data: Dict) -> Dict:
        """Abort pipeline with error"""
        print(f"\n❌ Pipeline aborted: {reason}")
        
        if 'errors' in data:
            for error in data['errors']:
                print(f"   ERROR: {error}")
        
        return {
            'success': False,
            'error': reason,
            'data': data
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    """Run integrated pipeline from command line"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python integrated_tennis_props_pipeline.py <props_file.txt> [--surface HARD] [--output outputs/]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Parse optional args
    surface = 'hard'
    output_dir = 'outputs'
    
    if '--surface' in sys.argv:
        surface_idx = sys.argv.index('--surface') + 1
        if surface_idx < len(sys.argv):
            surface = sys.argv[surface_idx].lower()
    
    if '--output' in sys.argv:
        output_idx = sys.argv.index('--output') + 1
        if output_idx < len(sys.argv):
            output_dir = sys.argv[output_idx]
    
    # Run pipeline
    pipeline = IntegratedTennisPropsPipeline(surface=surface)
    result = pipeline.run_full_pipeline(input_file, output_dir)
    
    if result['success']:
        print(f"\n✅ Pipeline completed successfully")
        print(f"   JSON: {result['reports']['json']}")
        print(f"   TXT: {result['reports']['txt']}")
    else:
        print(f"\n❌ Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
