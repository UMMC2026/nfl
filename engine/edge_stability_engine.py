class EdgeStabilityEngine:
    """
    Calculates ESS to filter out 'Fragile Edges'.
    Formula: (Dislocation * 1/Sigma * Min_Stability * Role_Certainty * (1-TailRisk))
    """
    
    def calculate_ess(self, 
                      mean: float, 
                      line: float, 
                      sigma: float, 
                      min_stability: float, # 0.0 to 1.0 (historical minute variance)
                      role_entropy: float,   # 0.0 to 1.0 (coaching rotation flux)
                      tail_risk: float       # Probability of < 50% of projected stat
                      ) -> float:
        
        # 1. Dislocation (The raw 'value')
        dislocation = abs(mean - line) / line
        
        # 2. Variance Penalty (Reward lower std dev)
        # We normalize sigma by the mean to get CV (Coefficient of Variation)
        cv = sigma / mean
        precision = 1 / (1 + cv)
        
        # 3. Role/Minute Confidence
        context_multiplier = min_stability * (1 - role_entropy)
        
        # 4. Tail Risk Mitigation
        safety_factor = 1 - tail_risk
        
        ess = (dislocation * precision * context_multiplier * safety_factor) * 10
        return round(ess, 4)

    def get_tier(self, ess: float) -> str:
        if ess >= 0.75: return "SLAM"
        if ess >= 0.55: return "STRONG"
        if ess >= 0.40: return "LEAN-A"
        if ess >= 0.25: return "LEAN-B"
        return "SKIP"
