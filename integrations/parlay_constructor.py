"""
Smart Parlay Constructor with Gates and Correlation Checks
- Applies minutes gates, variance checks, and correlation penalties
- Uses correlation_matrix.py for safe/dangerous checks
"""
from integrations.correlation_matrix import check_parlay_correlation

class SmartParlayBuilder:
    def __init__(self, min_edge=0.65, max_size=3):
        self.min_edge = min_edge
        self.max_size = max_size

    def apply_gates(self, candidate_legs):
        """
        Filters out legs that fail minutes, variance, or blowout gates
        Each leg should have: player_role, minutes_prob, stat_variance, game_script_risk, direction, edge
        """
        approved_legs = []
        for leg in candidate_legs:
            # Gate 1: Minutes probability
            if getattr(leg, 'player_role', 'STARTER') == 'BENCH':
                if getattr(leg, 'minutes_prob', 1.0) < 0.75:
                    continue
            # Gate 2: Stat variance (block high-variance combo props)
            if getattr(leg, 'stat_variance', 1.0) > 1.5 and '+' in getattr(leg, 'stat', ''):
                continue
            # Gate 3: Blowout exposure
            if getattr(leg, 'game_script_risk', 'LOW') == 'HIGH' and getattr(leg, 'direction', 'OVER') == 'OVER':
                continue
            # Gate 4: Edge threshold
            if getattr(leg, 'edge', 0.0) < self.min_edge:
                continue
            approved_legs.append(leg)
        return approved_legs

    def build_parlay(self, candidate_legs):
        """
        Builds optimal parlay using gates and correlation checks
        Returns: (parlay_legs, status, reason)
        """
        safe_legs = self.apply_gates(candidate_legs)
        if len(safe_legs) < self.max_size:
            return ([], 'FAIL', 'Not enough safe legs')
        # Try all combos, pick first safe
        import itertools
        for combo in itertools.combinations(safe_legs, self.max_size):
            status, reason = check_parlay_correlation(combo)
            if status == 'SAFE':
                return (combo, 'SUCCESS', None)
        return ([], 'FAIL', 'No safe parlay found (correlation)')
