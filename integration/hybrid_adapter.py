"""
HYBRID INTEGRATION ADAPTER
==========================
Bridges the hybrid confidence system into risk_first_analyzer.py

This adapter:
1. Converts risk_first_analyzer data format to hybrid format
2. Calls the hybrid confidence calculator
3. Returns results in risk_first_analyzer expected format
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.hybrid_confidence import calculate_hybrid_confidence


class RiskFirstHybridAdapter:
    """
    Adapter to integrate hybrid system into risk_first_analyzer.py
    """
    
    # Stat type mappings (risk_first format → hybrid format)
    STAT_CONVERSION = {
        # NBA
        'PTS': 'pts',
        'pts': 'pts',
        'points': 'pts',
        'POINTS': 'pts',
        
        'AST': 'ast',
        'ast': 'ast',
        'assists': 'ast',
        'ASSISTS': 'ast',
        
        'REB': 'reb',
        'reb': 'reb',
        'rebounds': 'reb',
        'REBOUNDS': 'reb',
        
        '3PM': '3pm',
        '3pm': '3pm',
        'threes': '3pm',
        'THREES': '3pm',
        
        'PRA': 'pra',
        'pra': 'pra',
        'PTS+REB+AST': 'pra',
        'pts+reb+ast': 'pra',
        
        'PTS+AST': 'pts+ast',
        'pts+ast': 'pts+ast',
        
        'REB+AST': 'reb+ast',
        'reb+ast': 'reb+ast',
        'AST+REB': 'ast+reb',
        'ast+reb': 'ast+reb',
        
        'BLK': 'blk',
        'blk': 'blk',
        'blocks': 'blk',
        
        'STL': 'stl',
        'stl': 'stl',
        'steals': 'stl',
        
        'BLK+STL': 'blk+stl',
        'blk+stl': 'blk+stl',
        
        # NFL (mostly vetoed by data)
        'RECS': 'recs',
        'recs': 'recs',
        'Recs': 'recs',
        'receptions': 'recs',
        
        'REC YARDS': 'rec yards',
        'rec yards': 'rec yards',
        'Rec Yards': 'rec yards',
        'receiving yards': 'rec yards',
        
        'RUSH YARDS': 'rush yards',
        'rush yards': 'rush yards',
        'Rush Yards': 'rush yards',
        
        # Tennis
        'ACES': 'aces',
        'aces': 'aces',
        'Aces': 'aces',
    }
    
    # Default CV by stat type (for when sigma not provided)
    DEFAULT_CV = {
        'pts': 0.25,      # Points are fairly stable
        'ast': 0.40,      # Assists more variable
        'reb': 0.30,      # Rebounds moderate
        '3pm': 0.55,      # Threes very variable
        'pra': 0.22,      # Combos smooth out variance
        'pts+ast': 0.28,
        'reb+ast': 0.32,
        'blk': 0.60,      # Blocks very spikey
        'stl': 0.55,      # Steals spikey
        'recs': 0.50,     # NFL receptions variable
        'rec yards': 0.45,
        'rush yards': 0.40,
        'aces': 0.50,     # Tennis aces variable
    }
    
    def __init__(self):
        pass
    
    def normalize_stat(self, stat: str) -> str:
        """Convert stat to hybrid format."""
        return self.STAT_CONVERSION.get(stat, stat.lower())
    
    def normalize_direction(self, direction: str) -> str:
        """Convert direction to hybrid format."""
        d = direction.lower().strip()
        if d in ['over', 'higher', 'o', 'h']:
            return 'higher'
        elif d in ['under', 'lower', 'u', 'l']:
            return 'lower'
        return 'higher'  # Default
    
    def estimate_sigma(self, mu: float, stat: str) -> float:
        """Estimate standard deviation if not provided."""
        stat_lower = self.normalize_stat(stat)
        cv = self.DEFAULT_CV.get(stat_lower, 0.30)
        return mu * cv
    
    def evaluate(
        self,
        mu: float,
        line: float,
        direction: str,
        stat: str,
        sigma: float = None,
        n_games: int = 10,
        verbose: bool = False
    ) -> dict:
        """
        Main entry point - evaluate a play using hybrid system.
        
        Args:
            mu: Model's predicted mean
            line: Betting line
            direction: 'higher'/'over' or 'lower'/'under'
            stat: Stat type (PTS, AST, etc.)
            sigma: Standard deviation (estimated if not provided)
            n_games: Sample size
            verbose: Print debug info
        
        Returns:
            Dict with:
            - probability: Final confidence percentage
            - edge: Edge percentage
            - tier: SLAM/STRONG/LEAN/WATCH/NO_PLAY/VETO
            - decision: Same as tier for actionable, NO_PLAY otherwise
            - raw_probability: Pre-adjustment probability
            - adjustments: Dict of applied adjustments
        """
        # Normalize inputs
        stat_normalized = self.normalize_stat(stat)
        direction_normalized = self.normalize_direction(direction)
        
        # Estimate sigma if not provided
        if sigma is None or sigma <= 0:
            sigma = self.estimate_sigma(mu, stat)
        
        # Call hybrid confidence calculator
        result = calculate_hybrid_confidence(
            mu=mu,
            sigma=sigma,
            line=line,
            n_games=n_games,
            stat=stat_normalized,
            direction=direction_normalized,
            verbose=verbose
        )
        
        # Map to risk_first expected format
        return {
            'probability': result.get('effective_probability', 50.0),
            'raw_probability': result.get('raw_probability', 50.0),
            'edge': result.get('effective_edge', 0),
            'raw_edge': result.get('raw_edge', 0),
            'tier': result.get('tier', 'NO_PLAY'),
            'decision': result.get('decision', 'NO_PLAY'),
            'z_score': result.get('z_score', 0),
            'stat_multiplier': result.get('stat_direction_multiplier', 1.0),
            'sample_multiplier': result.get('sample_size_multiplier', 1.0),
            'reason': result.get('reason', ''),
            'is_veto': result.get('tier') == 'VETO',
            'should_bet': result.get('tier') in ['SLAM', 'STRONG', 'LEAN'],
        }


# Singleton instance for easy import
_adapter = None

def get_adapter() -> RiskFirstHybridAdapter:
    """Get singleton adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = RiskFirstHybridAdapter()
    return _adapter


def evaluate_play_hybrid(
    mu: float,
    line: float,
    direction: str,
    stat: str,
    sigma: float = None,
    n_games: int = 10,
    verbose: bool = False
) -> dict:
    """
    Convenience function to evaluate a play.
    
    Usage:
        from integration.hybrid_adapter import evaluate_play_hybrid
        
        result = evaluate_play_hybrid(
            mu=28.4, 
            line=27.5, 
            direction='higher',
            stat='PTS',
            n_games=15
        )
        
        if result['should_bet']:
            print(f"BET: {result['tier']} with {result['edge']:.1f}% edge")
    """
    return get_adapter().evaluate(
        mu=mu,
        line=line,
        direction=direction,
        stat=stat,
        sigma=sigma,
        n_games=n_games,
        verbose=verbose
    )


# === TEST ===
if __name__ == "__main__":
    print("=" * 60)
    print("HYBRID ADAPTER TEST")
    print("=" * 60)
    
    test_cases = [
        # Embiid - should be LEAN now (was NO_PLAY)
        {'mu': 28.4, 'sigma': 6.5, 'line': 27.5, 'direction': 'OVER', 'stat': 'PTS', 'n_games': 15, 'name': 'Embiid PTS'},
        
        # AST - should be BOOSTED
        {'mu': 11.5, 'sigma': 3.0, 'line': 10.5, 'direction': 'OVER', 'stat': 'AST', 'n_games': 20, 'name': 'Trae AST'},
        
        # 3PM - should be preserved
        {'mu': 4.2, 'sigma': 2.1, 'line': 3.5, 'direction': 'OVER', 'stat': '3PM', 'n_games': 18, 'name': 'Curry 3PM'},
        
        # NFL RECS - should be VETOED
        {'mu': 5.0, 'sigma': 2.0, 'line': 4.5, 'direction': 'OVER', 'stat': 'RECS', 'n_games': 10, 'name': 'WR Recs'},
        
        # Small sample - should be VETOED
        {'mu': 20.0, 'sigma': 5.0, 'line': 18.5, 'direction': 'OVER', 'stat': 'PTS', 'n_games': 4, 'name': 'Small Sample'},
        
        # High edge AST - should be SLAM
        {'mu': 12.0, 'sigma': 2.5, 'line': 8.5, 'direction': 'OVER', 'stat': 'AST', 'n_games': 25, 'name': 'High Edge AST'},
    ]
    
    for tc in test_cases:
        result = evaluate_play_hybrid(
            mu=tc['mu'],
            sigma=tc.get('sigma'),
            line=tc['line'],
            direction=tc['direction'],
            stat=tc['stat'],
            n_games=tc['n_games']
        )
        
        bet_icon = "✅" if result['should_bet'] else "❌" if result['is_veto'] else "⚠️"
        print(f"\n{bet_icon} {tc['name']}: {tc['stat']} {tc['direction']} {tc['line']}")
        print(f"   μ={tc['mu']}, σ={tc.get('sigma', 'auto')}, n={tc['n_games']}")
        print(f"   Raw: {result['raw_probability']:.1f}% | Adj: {result['probability']:.1f}%")
        print(f"   Edge: {result['edge']:.2f}% | Tier: {result['tier']}")
        if result['reason']:
            print(f"   Reason: {result['reason']}")
    
    print("\n" + "=" * 60)
