"""
NFL Market Simulator - Drive-Level Monte Carlo
NFL_AUTONOMOUS v1.0 Compatible

Simulates NFL prop markets using drive-level modeling with feature-based distributions.
"""

import numpy as np
from scipy import stats
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Import without relative imports to avoid package issues
import sys
sys.path.insert(0, str(Path(__file__).parent))
from nfl_markets import NFLMarket, is_market_valid_for_position


@dataclass
class SimulationResult:
    """Result from Monte Carlo simulation."""
    market: NFLMarket
    simulated_values: np.ndarray
    mean: float
    std: float
    prob_over: Dict[float, float]  # line -> probability
    distribution_type: str


class NFLMarketSimulator:
    """Drive-level Monte Carlo simulator for NFL markets."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize simulator with feature map configuration."""
        if config_path is None:
            config_path = Path(__file__).parent / "nfl_feature_map.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.n_sims = 10000
        self.drives_per_game_avg = self.config['modeling_rules']['drive_simulation']['drives_per_game_avg']
        self.drives_per_game_std = self.config['modeling_rules']['drive_simulation']['drives_per_game_std']
    
    def simulate_market(
        self, 
        market: NFLMarket, 
        player_features: Dict[str, Any],
        opponent_features: Dict[str, Any],
        game_context: Dict[str, Any],
        lines: Optional[List[float]] = None
    ) -> SimulationResult:
        """
        Simulate a market using drive-level Monte Carlo.
        
        Args:
            market: NFLMarket enum
            player_features: Player stats/features
            opponent_features: Opponent defensive stats
            game_context: Weather, home/away, etc.
            lines: List of lines to calculate prob_over for
        
        Returns:
            SimulationResult with probabilities and distribution
        """
        market_key = market.value
        market_config = self.config.get(market_key, {})
        
        if not market_config:
            raise ValueError(f"No configuration for market: {market}")
        
        # Validate position compatibility
        position = player_features.get('position', '')
        if not is_market_valid_for_position(market, position):
            raise ValueError(f"Market {market} not valid for position {position}")
        
        # Build distribution from features
        distribution = self._build_distribution(market_config, player_features, opponent_features, game_context)
        
        # Run Monte Carlo simulation
        if market_config.get('drive_level', False):
            simulated_values = self._simulate_drive_level(distribution, game_context)
        else:
            simulated_values = self._simulate_game_level(distribution)
        
        # Calculate probabilities for lines
        prob_over = {}
        if lines:
            for line in lines:
                prob_over[line] = np.mean(simulated_values > line)
        
        return SimulationResult(
            market=market,
            simulated_values=simulated_values,
            mean=np.mean(simulated_values),
            std=np.std(simulated_values),
            prob_over=prob_over,
            distribution_type=market_config.get('distribution', 'Empirical')
        )
    
    def _build_distribution(
        self, 
        market_config: Dict, 
        player_features: Dict,
        opponent_features: Dict,
        game_context: Dict
    ):
        """Build probability distribution from features."""
        dist_type = market_config.get('distribution', 'Normal')
        
        # Get required inputs
        inputs = market_config.get('inputs', [])
        
        # Extract base rate from player features (simplified - would be more complex in production)
        # This is where you'd apply your feature engineering
        base_value = self._extract_base_value(inputs, player_features)
        
        # Apply opponent adjustment
        opponent_adj = self._calculate_opponent_adjustment(inputs, opponent_features)
        adjusted_value = base_value * opponent_adj
        
        # Apply game context adjustment (weather, home/away, etc.)
        context_adj = self._calculate_context_adjustment(inputs, game_context)
        final_value = adjusted_value * context_adj
        
        # Build distribution
        if dist_type == 'Normal':
            std = final_value * 0.25  # 25% coefficient of variation
            return stats.norm(loc=final_value, scale=std)
        
        elif dist_type == 'Poisson':
            return stats.poisson(mu=max(0, final_value))
        
        elif dist_type == 'LogNormal':
            mu = np.log(final_value)
            sigma = 0.30
            return stats.lognorm(s=sigma, scale=np.exp(mu))
        
        elif dist_type == 'Gamma':
            shape = 4.0  # k parameter
            scale = final_value / shape  # theta parameter
            return stats.gamma(a=shape, scale=scale)
        
        elif dist_type == 'Beta':
            # For completion percentage, etc.
            alpha = final_value * 100
            beta = (1 - final_value) * 100
            return stats.beta(a=alpha, b=beta)
        
        elif dist_type == 'Exponential':
            # For longest plays
            rate = 1 / max(1, final_value)
            return stats.expon(scale=1/rate)
        
        else:
            # Fallback: Normal
            std = final_value * 0.25
            return stats.norm(loc=final_value, scale=std)
    
    def _simulate_drive_level(self, distribution, game_context: Dict) -> np.ndarray:
        """Simulate stat accumulation at drive level."""
        results = np.zeros(self.n_sims)
        
        for i in range(self.n_sims):
            # Simulate number of drives for this game
            n_drives = int(np.random.normal(self.drives_per_game_avg, self.drives_per_game_std))
            n_drives = max(1, min(n_drives, 20))  # Clamp to reasonable range
            
            # Accumulate stat per drive
            game_total = 0
            for _ in range(n_drives):
                drive_outcome = distribution.rvs()
                game_total += max(0, drive_outcome)  # Can't have negative yards/stats
            
            results[i] = game_total
        
        return results
    
    def _simulate_game_level(self, distribution) -> np.ndarray:
        """Simulate stat at game level (not drive-based)."""
        return distribution.rvs(size=self.n_sims)
    
    def _extract_base_value(self, inputs: List[str], player_features: Dict) -> float:
        """Extract base statistical value from player features."""
        # Simplified: In production, this would use sophisticated feature engineering
        # For now, look for the primary rate/average feature
        
        for input_name in inputs:
            if 'rate' in input_name or 'avg' in input_name or 'per_game' in input_name:
                value = player_features.get(input_name, 0)
                if value > 0:
                    return float(value)
        
        # Fallback: use first numeric feature
        for key, value in player_features.items():
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
        
        return 0.0
    
    def _calculate_opponent_adjustment(self, inputs: List[str], opponent_features: Dict) -> float:
        """Calculate multiplier based on opponent defense."""
        adjustment = 1.0
        
        # Check for defensive rank features
        for input_name in inputs:
            if 'opponent' in input_name or 'defensive' in input_name:
                rank = opponent_features.get(input_name, 16)  # Default to mid-tier
                # Better defense (lower rank) = lower adjustment
                adjustment *= (33 - rank) / 32  # Scale from ~0.03 to ~1.0
        
        return max(0.5, min(adjustment, 1.5))  # Clamp to reasonable range
    
    def _calculate_context_adjustment(self, inputs: List[str], game_context: Dict) -> float:
        """Calculate multiplier based on game context."""
        adjustment = 1.0
        
        # Home/away
        if 'home_away_adjustment' in inputs:
            if not game_context.get('is_home', True):
                adjustment *= 0.95  # 5% away penalty
        
        # Weather
        if 'weather_wind_mph' in inputs:
            wind = game_context.get('wind_mph', 0)
            if wind > 15:
                adjustment *= 0.90  # 10% wind penalty
        
        if 'weather_conditions' in inputs:
            if game_context.get('rain', False):
                adjustment *= self.config['modeling_rules']['weather_gates']['rain_impact_pass']
            if game_context.get('snow', False):
                adjustment *= self.config['modeling_rules']['weather_gates']['snow_impact_all']
        
        return max(0.5, min(adjustment, 1.5))
    
    def batch_simulate(
        self,
        markets: List[NFLMarket],
        player_features: Dict[str, Any],
        opponent_features: Dict[str, Any],
        game_context: Dict[str, Any],
        lines: Dict[NFLMarket, List[float]]
    ) -> Dict[NFLMarket, SimulationResult]:
        """Simulate multiple markets for efficiency."""
        results = {}
        for market in markets:
            market_lines = lines.get(market, [])
            try:
                results[market] = self.simulate_market(
                    market, player_features, opponent_features, game_context, market_lines
                )
            except Exception as e:
                # Best-effort: log and continue
                print(f"Warning: Failed to simulate {market}: {e}")
                continue
        
        return results


def simulate_player_props(
    player_id: str,
    player_features: Dict[str, Any],
    opponent_features: Dict[str, Any],
    game_context: Dict[str, Any],
    prop_lines: Dict[str, float]
) -> Dict[str, float]:
    """
    Convenience function for simulating props for a single player.
    
    Returns dict of {market: probability_over}
    """
    simulator = NFLMarketSimulator()
    results = {}
    
    for market_str, line in prop_lines.items():
        try:
            market = NFLMarket(market_str)
            sim_result = simulator.simulate_market(
                market, player_features, opponent_features, game_context, [line]
            )
            results[market_str] = sim_result.prob_over[line]
        except Exception:
            continue
    
    return results
