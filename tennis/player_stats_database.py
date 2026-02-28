"""
TENNIS PLAYER STATS DATABASE
Centralized player statistics for props prediction

Data sources:
- Historical performance tracking
- ATP/WTA official stats
- Tennis-data.co.uk
- Custom tracking
"""

import json
from typing import Dict, Optional
from pathlib import Path


# ============================================================================
# NAME ALIASES (Common spelling variations from Underdog/PrizePicks)
# Maps Underdog name → Database name
# ============================================================================

NAME_ALIASES = {
    # Chinese players (space variations)
    "Xinyu Wang": "Xin Yu Wang",
    "Xiyu Wang": "Xiyu Wang",
    "Qinwen Zheng": "Qinwen Zheng",
    "Yafan Wang": "Yafan Wang",
    
    # Japanese players
    "Misaki Matsuda": "Misaki Matsuda",  # Already correct
    "Miho Kuramochi": "Miho Kuramochi",  # Already correct
    
    # Common variations
    "Alex De Minaur": "Alex de Minaur",
    "Alex de Minaur": "Alex de Minaur",
    "Carlos Alcaraz Garfia": "Carlos Alcaraz",
    "Alejandro Davidovich Fokina": "Alejandro Davidovich Fokina",
    
    # Thai players
    "Mananchaya Sawangkaew": "Mananchaya Sawangkaew",
    
    # Eastern European name variations
    "Danielle Collins": "Danielle Collins",
    "Elena Gabriela Ruse": "Elena Ruse",
}


# ============================================================================
# PLAYER STATS SCHEMA
# ============================================================================

PLAYER_STATS_SCHEMA = {
    'player_name': str,
    'ranking': int,
    'avg_games_per_match': float,
    'avg_aces': float,
    'avg_double_faults': float,
    'avg_breakpoints_won': float,
    'first_set_win_rate': float,
    'player_style': str,  # big_server, baseline_grinder, all_court, aggressive_returner
    'surface_performance': {
        'hard': {'games': float, 'aces': float, 'breakpoints': float},
        'clay': {'games': float, 'aces': float, 'breakpoints': float},
        'grass': {'games': float, 'aces': float, 'breakpoints': float}
    },
    'fantasy_score_avg': float  # For PrizePicks
}


# ============================================================================
# DEFAULT PLAYER DATABASE (Starter Data)
# ============================================================================

DEFAULT_PLAYER_STATS = {
    # Women's Singles
    'Aryna Sabalenka': {
        'ranking': 1,
        'avg_games_per_match': 14.2,
        'avg_aces': 5.8,
        'avg_double_faults': 3.2,
        'avg_breakpoints_won': 3.8,
        'first_set_win_rate': 0.72,
        'player_style': 'big_server',
        'surface_performance': {
            'hard': {'games': 14.5, 'aces': 6.2, 'breakpoints': 4.0},
            'clay': {'games': 13.8, 'aces': 4.1, 'breakpoints': 3.5},
            'grass': {'games': 15.1, 'aces': 8.3, 'breakpoints': 4.2}
        },
        'fantasy_score_avg': 22.5
    },
    'Elina Svitolina': {
        'ranking': 18,
        'avg_games_per_match': 11.2,
        'avg_aces': 1.8,
        'avg_double_faults': 2.1,
        'avg_breakpoints_won': 2.2,
        'first_set_win_rate': 0.58,
        'player_style': 'baseline_grinder',
        'surface_performance': {
            'hard': {'games': 11.5, 'aces': 2.0, 'breakpoints': 2.3},
            'clay': {'games': 12.8, 'aces': 1.2, 'breakpoints': 2.8},
            'grass': {'games': 10.1, 'aces': 2.8, 'breakpoints': 1.9}
        },
        'fantasy_score_avg': 15.3
    },
    'Elena Rybakina': {
        'ranking': 4,
        'avg_games_per_match': 13.8,
        'avg_aces': 7.8,
        'avg_double_faults': 2.8,
        'avg_breakpoints_won': 3.6,
        'first_set_win_rate': 0.69,
        'player_style': 'big_server',
        'surface_performance': {
            'hard': {'games': 14.2, 'aces': 8.1, 'breakpoints': 3.8},
            'clay': {'games': 13.1, 'aces': 5.8, 'breakpoints': 3.2},
            'grass': {'games': 14.8, 'aces': 11.2, 'breakpoints': 4.1}
        },
        'fantasy_score_avg': 22.9
    },
    'Jessica Pegula': {
        'ranking': 5,
        'avg_games_per_match': 12.4,
        'avg_aces': 2.1,
        'avg_double_faults': 1.8,
        'avg_breakpoints_won': 2.8,
        'first_set_win_rate': 0.61,
        'player_style': 'baseline_grinder',
        'surface_performance': {
            'hard': {'games': 12.8, 'aces': 2.3, 'breakpoints': 2.9},
            'clay': {'games': 11.8, 'aces': 1.5, 'breakpoints': 2.5},
            'grass': {'games': 12.2, 'aces': 2.8, 'breakpoints': 2.6}
        },
        'fantasy_score_avg': 18.2
    },
    
    # Men's Singles
    'Novak Djokovic': {
        'ranking': 7,
        'avg_games_per_match': 13.5,
        'avg_aces': 4.2,
        'avg_double_faults': 1.5,
        'avg_breakpoints_won': 3.1,
        'first_set_win_rate': 0.68,
        'player_style': 'all_court',
        'surface_performance': {
            'hard': {'games': 13.8, 'aces': 4.5, 'breakpoints': 3.3},
            'clay': {'games': 14.2, 'aces': 3.2, 'breakpoints': 3.8},
            'grass': {'games': 13.1, 'aces': 5.8, 'breakpoints': 2.9}
        },
        'fantasy_score_avg': 24.8
    },
    'Jannik Sinner': {
        'ranking': 1,
        'avg_games_per_match': 15.1,
        'avg_aces': 8.3,
        'avg_double_faults': 2.8,
        'avg_breakpoints_won': 4.2,
        'first_set_win_rate': 0.65,
        'player_style': 'aggressive_returner',
        'surface_performance': {
            'hard': {'games': 15.5, 'aces': 8.8, 'breakpoints': 4.5},
            'clay': {'games': 14.8, 'aces': 6.5, 'breakpoints': 4.0},
            'grass': {'games': 15.2, 'aces': 10.2, 'breakpoints': 4.2}
        },
        'fantasy_score_avg': 26.2
    },
    'Carlos Alcaraz': {
        'ranking': 3,
        'avg_games_per_match': 16.2,
        'avg_aces': 6.5,
        'avg_double_faults': 2.5,
        'avg_breakpoints_won': 4.8,
        'first_set_win_rate': 0.70,
        'player_style': 'all_court',
        'surface_performance': {
            'hard': {'games': 16.5, 'aces': 6.8, 'breakpoints': 5.0},
            'clay': {'games': 17.1, 'aces': 5.2, 'breakpoints': 5.5},
            'grass': {'games': 15.8, 'aces': 8.2, 'breakpoints': 4.5}
        },
        'fantasy_score_avg': 28.1
    },
    'Alexander Zverev': {
        'ranking': 2,
        'avg_games_per_match': 14.8,
        'avg_aces': 9.2,
        'avg_double_faults': 3.8,
        'avg_breakpoints_won': 3.5,
        'first_set_win_rate': 0.64,
        'player_style': 'big_server',
        'surface_performance': {
            'hard': {'games': 15.1, 'aces': 9.5, 'breakpoints': 3.6},
            'clay': {'games': 15.8, 'aces': 7.2, 'breakpoints': 4.2},
            'grass': {'games': 14.2, 'aces': 12.8, 'breakpoints': 3.1}
        },
        'fantasy_score_avg': 25.4
    },
    'Daniil Medvedev': {
        'ranking': 5,
        'avg_games_per_match': 13.2,
        'avg_aces': 5.8,
        'avg_double_faults': 2.2,
        'avg_breakpoints_won': 3.2,
        'first_set_win_rate': 0.63,
        'player_style': 'baseline_grinder',
        'surface_performance': {
            'hard': {'games': 13.8, 'aces': 6.2, 'breakpoints': 3.5},
            'clay': {'games': 12.1, 'aces': 4.1, 'breakpoints': 2.8},
            'grass': {'games': 13.5, 'aces': 7.5, 'breakpoints': 3.0}
        },
        'fantasy_score_avg': 23.5
    }
}


# ============================================================================
# PLAYER STATS DATABASE CLASS
# ============================================================================

class PlayerStatsDatabase:
    """Manage player statistics for props prediction"""
    
    def __init__(self, data_file: str = "tennis/data/player_stats.json"):
        self.data_file = Path(data_file)
        self.stats = self._load_stats()
    
    
    def _load_stats(self) -> Dict:
        """Load stats from file or use defaults"""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                return json.load(f)
        else:
            # Create directory if needed
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            # Save defaults
            self.save_stats(DEFAULT_PLAYER_STATS)
            return DEFAULT_PLAYER_STATS.copy()
    
    
    def get_player(self, player_name: str, surface: str = 'hard') -> Dict:
        """
        Get player stats with fuzzy name matching
        
        Args:
            player_name: Player name (exact or partial)
            surface: Court surface (hard, clay, grass)
            
        Returns:
            Player stats dict with surface-specific adjustments
        """
        # Check name aliases first (common spelling variations)
        resolved_name = NAME_ALIASES.get(player_name, player_name)
        
        # Exact match (case-insensitive)
        for name in self.stats:
            if name.lower() == resolved_name.lower():
                return self._apply_surface_stats(self.stats[name], surface)
        
        # Exact match with original name
        if player_name in self.stats:
            return self._apply_surface_stats(self.stats[player_name], surface)
        
        # Try removing spaces/hyphens
        normalized = resolved_name.lower().replace(' ', '').replace('-', '')
        for name in self.stats:
            if name.lower().replace(' ', '').replace('-', '') == normalized:
                return self._apply_surface_stats(self.stats[name], surface)
        
        # Fuzzy match by last name
        last_name = player_name.split()[-1].lower()
        for full_name, stats in self.stats.items():
            if last_name in full_name.lower():
                return self._apply_surface_stats(stats, surface)
        
        # Return default if no match
        return self._get_default_player_stats(surface)
    
    
    def _apply_surface_stats(self, player_stats: Dict, surface: str) -> Dict:
        """Apply surface-specific stats to base player stats"""
        result = player_stats.copy()
        
        if 'surface_performance' in player_stats and surface in player_stats['surface_performance']:
            surface_stats = player_stats['surface_performance'][surface]
            
            # Override base stats with surface-specific stats
            if 'games' in surface_stats:
                result['avg_games_per_match'] = surface_stats['games']
            if 'aces' in surface_stats:
                result['avg_aces'] = surface_stats['aces']
            if 'breakpoints' in surface_stats:
                result['avg_breakpoints_won'] = surface_stats['breakpoints']
        
        return result
    
    
    def _get_default_player_stats(self, surface: str = 'hard') -> Dict:
        """Return default stats for unknown players"""
        base = {
            'ranking': 100,
            'avg_games_per_match': 12.0,
            'avg_aces': 4.0,
            'avg_double_faults': 2.5,
            'avg_breakpoints_won': 2.5,
            'first_set_win_rate': 0.60,
            'player_style': 'all_court',
            'fantasy_score_avg': 18.0
        }
        
        # Surface adjustments for unknown players
        if surface == 'grass':
            base['avg_aces'] *= 1.3
        elif surface == 'clay':
            base['avg_aces'] *= 0.7
            base['avg_games_per_match'] *= 1.1
        
        return base
    
    
    def add_player(self, player_name: str, stats: Dict):
        """Add or update player stats"""
        self.stats[player_name] = stats
        self.save_stats(self.stats)
    
    
    def save_stats(self, stats: Dict = None):
        """Save stats to file"""
        if stats is None:
            stats = self.stats
        
        with open(self.data_file, 'w') as f:
            json.dump(stats, f, indent=2)
    
    
    def get_all_players(self) -> list:
        """Get list of all players in database"""
        return list(self.stats.keys())
    
    
    def export_template(self, output_file: str):
        """Export blank template for adding new players"""
        template = {
            'PLAYER_NAME_HERE': PLAYER_STATS_SCHEMA
        }
        
        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def get_player_stats(player_name: str, surface: str = 'hard') -> Dict:
    """
    Convenience function for quick player stats lookup
    
    Args:
        player_name: Player name
        surface: Court surface
        
    Returns:
        Player stats dict
    """
    db = PlayerStatsDatabase()
    return db.get_player(player_name, surface)


# ============================================================================
# CLI FOR TESTING
# ============================================================================

def main():
    """Test player stats database"""
    import sys
    
    db = PlayerStatsDatabase()
    
    if len(sys.argv) > 1:
        player_name = sys.argv[1]
        surface = sys.argv[2] if len(sys.argv) > 2 else 'hard'
        
        stats = db.get_player(player_name, surface)
        
        print(f"\n{'='*70}")
        print(f"PLAYER STATS: {player_name} ({surface.upper()})")
        print(f"{'='*70}\n")
        
        print(f"Ranking: {stats['ranking']}")
        print(f"Avg Games Per Match: {stats['avg_games_per_match']}")
        print(f"Avg Aces: {stats['avg_aces']}")
        print(f"Avg Breakpoints Won: {stats['avg_breakpoints_won']}")
        print(f"First Set Win Rate: {stats['first_set_win_rate']:.1%}")
        print(f"Player Style: {stats['player_style']}")
        print(f"Fantasy Score Avg: {stats['fantasy_score_avg']}")
    
    else:
        # Show all players
        print(f"\n{'='*70}")
        print(f"PLAYER STATS DATABASE")
        print(f"{'='*70}\n")
        
        print(f"Total Players: {len(db.get_all_players())}\n")
        
        for player in sorted(db.get_all_players()):
            stats = db.stats[player]
            print(f"{player:25} Rank: {stats['ranking']:3} | Style: {stats['player_style']:20} | Aces: {stats['avg_aces']:.1f}")


if __name__ == "__main__":
    main()
