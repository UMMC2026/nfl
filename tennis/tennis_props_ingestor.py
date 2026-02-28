"""
TENNIS PROPS INGESTION MODULE
Replaces match winner ingestion with DFS props parsing

Integrates with existing tennis pipeline structure while adding props support
"""

import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

# Import unified parser
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from prizepicks_parser import UnifiedTennisParser


# ============================================================================
# PROPS INGESTION (Replaces Match Winner Ingestion)
# ============================================================================

class TennisPropsIngestor:
    """
    Ingest tennis props from PrizePicks, Underdog, or other platforms
    
    Replaces match winner ingestion with player props ingestion
    """
    
    def __init__(self, data_dir: str = "tennis/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    
    def ingest_from_file(self, filepath: str) -> Dict:
        """
        Ingest props from text file (auto-detects platform)
        
        Args:
            filepath: Path to text file with copied props
            
        Returns:
            Ingestion result with parsed props and metadata
        """
        parser = UnifiedTennisParser()
        props = parser.parse_file(filepath)
        
        return self._build_ingestion_result(props, filepath)
    
    
    def ingest_from_text(self, text: str, source_name: str = "manual") -> Dict:
        """
        Ingest props from raw text (auto-detects platform)
        
        Args:
            text: Raw text copied from DFS platform
            source_name: Identifier for this data source
            
        Returns:
            Ingestion result with parsed props and metadata
        """
        parser = UnifiedTennisParser()
        props = parser.parse_text(text)
        
        return self._build_ingestion_result(props, source_name)
    
    
    def _build_ingestion_result(self, props: List[Dict], source: str) -> Dict:
        """
        Build standardized ingestion result
        
        Compatible with existing pipeline validation gates
        """
        if not props:
            return {
                'success': False,
                'error': 'No props parsed from input',
                'props': [],
                'metadata': {
                    'source': source,
                    'timestamp': datetime.now().isoformat(),
                    'platform': 'unknown'
                }
            }
        
        # Extract metadata
        platform = props[0].get('platform', 'unknown')
        
        # Count markets
        total_markets = sum(len(p['markets']) for p in props)
        
        # Market distribution
        market_counts = {}
        for prop in props:
            for market in prop['markets'].keys():
                market_counts[market] = market_counts.get(market, 0) + 1
        
        return {
            'success': True,
            'props': props,
            'metadata': {
                'source': source,
                'timestamp': datetime.now().isoformat(),
                'platform': platform,
                'total_players': len(props),
                'total_markets': total_markets,
                'market_distribution': market_counts
            }
        }
    
    
    def save_ingested_props(self, ingestion_result: Dict, filename: str = None) -> str:
        """
        Save ingested props to JSON file
        
        Args:
            ingestion_result: Result from ingest_from_* methods
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            platform = ingestion_result['metadata']['platform']
            filename = f"props_{platform}_{timestamp}.json"
        
        filepath = self.data_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(ingestion_result, f, indent=2)
        
        return str(filepath)
    
    
    def validate_ingestion(self, ingestion_result: Dict) -> Dict:
        """
        Validate ingestion result meets minimum requirements
        
        SOP v2.1 compliant validation
        """
        errors = []
        warnings = []
        
        # Check success flag
        if not ingestion_result.get('success'):
            errors.append(ingestion_result.get('error', 'Unknown ingestion error'))
            return {
                'valid': False,
                'errors': errors,
                'warnings': warnings
            }
        
        props = ingestion_result['props']
        
        # Minimum props requirement
        if len(props) < 1:
            errors.append("No props parsed")
        
        # Check required fields
        for i, prop in enumerate(props):
            if 'player_name' not in prop:
                errors.append(f"Prop {i}: Missing player_name")
            
            if 'markets' not in prop or not prop['markets']:
                errors.append(f"Prop {i}: No markets available")
            
            # Validate market structure
            for market_type, market_data in prop.get('markets', {}).items():
                if 'line' not in market_data:
                    errors.append(f"Prop {i}, Market {market_type}: Missing line value")
        
        # Warnings
        if ingestion_result['metadata']['platform'] == 'unknown':
            warnings.append("Could not detect platform - may affect threshold selection")
        
        if ingestion_result['metadata']['total_markets'] < 5:
            warnings.append(f"Low market count ({ingestion_result['metadata']['total_markets']}) - limited opportunities")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'summary': {
                'total_props': len(props),
                'total_markets': ingestion_result['metadata']['total_markets'],
                'platform': ingestion_result['metadata']['platform']
            }
        }


# ============================================================================
# LEGACY COMPATIBILITY (For existing pipeline)
# ============================================================================

def ingest_tennis_props(input_source: str) -> Dict:
    """
    Legacy function signature for backward compatibility
    
    Args:
        input_source: File path or raw text
        
    Returns:
        Ingestion result compatible with existing pipeline
    """
    ingestor = TennisPropsIngestor()
    
    # Check if input is a file or raw text
    if Path(input_source).exists():
        return ingestor.ingest_from_file(input_source)
    else:
        return ingestor.ingest_from_text(input_source)


# ============================================================================
# CLI FOR TESTING
# ============================================================================

def main():
    """Test ingestion from command line"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python tennis_props_ingestor.py <props_file.txt>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Ingest
    ingestor = TennisPropsIngestor()
    result = ingestor.ingest_from_file(input_file)
    
    # Validate
    validation = ingestor.validate_ingestion(result)
    
    # Print results
    print("\n" + "="*70)
    print("TENNIS PROPS INGESTION RESULT")
    print("="*70)
    
    if result['success']:
        print(f"\n✅ Successfully ingested props")
        print(f"   Platform: {result['metadata']['platform']}")
        print(f"   Players: {result['metadata']['total_players']}")
        print(f"   Total Markets: {result['metadata']['total_markets']}")
        
        print(f"\nMarket Distribution:")
        for market, count in sorted(result['metadata']['market_distribution'].items(), 
                                   key=lambda x: x[1], reverse=True):
            print(f"   {market:30} {count:2}")
    else:
        print(f"\n❌ Ingestion failed: {result.get('error')}")
    
    print(f"\n" + "="*70)
    print("VALIDATION RESULT")
    print("="*70)
    
    if validation['valid']:
        print(f"\n✅ Validation passed")
    else:
        print(f"\n❌ Validation failed")
        for error in validation['errors']:
            print(f"   ERROR: {error}")
    
    if validation['warnings']:
        print(f"\nWarnings:")
        for warning in validation['warnings']:
            print(f"   ⚠️  {warning}")
    
    # Save to file
    if result['success']:
        saved_path = ingestor.save_ingested_props(result)
        print(f"\n✅ Saved to: {saved_path}")


if __name__ == "__main__":
    main()
