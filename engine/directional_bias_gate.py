# engine/directional_bias_gate.py
"""
DIRECTIONAL BIAS GATE — Statistical Honesty Enforcement

Prevents distribution bias from masking true edge by ensuring balanced UNDER/OVER distributions.

Rules:
1. If |unders - overs| > 70/30 threshold → Downgrade all probabilities by 5%
2. If imbalanced → Cap SLAM tier eligibility (downgrade SLAM → STRONG)
3. If >90% single direction → Hard abort (model is broken)

This gate enforces statistical humility: Volume without balance = amplified error.
"""

def directional_bias_gate(edges: list[dict]) -> list[dict]:
    """
    Check UNDER/OVER balance, apply probability downgrades if imbalanced, abort if extreme.
    
    Args:
        edges: List of edge dicts with 'direction', 'prob_hit', 'tier' fields
        
    Returns:
        Corrected edges (probabilities downgraded if needed)
        
    Raises:
        ValueError: If >90% single direction (model is broken)
    """
    if not edges:
        return edges
    
    # Count directions (normalize to UNDER/OVER equivalents)
    unders = 0
    overs = 0
    
    for e in edges:
        direction = str(e.get("direction", "")).strip().lower()
        if direction in ("under", "u", "lower", "l"):
            unders += 1
        elif direction in ("over", "o", "higher", "h"):
            overs += 1
    
    total = len(edges)
    
    if total == 0:
        return edges
    
    # Calculate ratio
    under_pct = (unders / total) * 100
    over_pct = (overs / total) * 100
    
    print(f"   📊 Distribution: {unders} UNDERS ({under_pct:.1f}%) | {overs} OVERS ({over_pct:.1f}%)")
    
    # Hard abort if >90% single direction (model is broken)
    if under_pct > 90 or over_pct > 90:
        raise ValueError(
            f"DIRECTIONAL BIAS GATE FAILURE\n"
            f"   Distribution: {under_pct:.1f}% UNDERS / {over_pct:.1f}% OVERS\n"
            f"   >90% single direction indicates model bias, not true edge\n"
            f"   Root causes to check:\n"
            f"     - Recent-form overweighting defensive regression\n"
            f"     - Normal CDF symmetry assumption on asymmetric distributions\n"
            f"     - Missing pace adjustment for opponent matchups\n"
            f"   DO NOT BROADCAST until model is fixed"
        )
    
    # Check balance threshold (70/30)
    imbalanced = (under_pct > 70 or over_pct > 70)
    
    if not imbalanced:
        print(f"   ✅ Distribution balanced (within 70/30 threshold)")
        return edges
    
    # IMBALANCED: Apply corrections
    print(f"   ⚠️  Distribution imbalanced (exceeds 70/30 threshold)")
    print(f"   🔧 Applying corrections:")
    print(f"      • All probabilities downgraded by 5%")
    print(f"      • SLAM tier capped (SLAM → STRONG)")
    
    corrected_edges = []
    slam_downgrades = 0
    
    for edge in edges:
        corrected = edge.copy()
        
        # Downgrade probability by 5% (absolute, not relative)
        original_prob = edge.get("prob_hit", 0)
        corrected["prob_hit"] = max(0.50, original_prob - 0.05)  # Floor at 50%
        
        # Cap SLAM tier (downgrade to STRONG)
        if edge.get("tier") == "SLAM":
            corrected["tier"] = "STRONG"
            slam_downgrades += 1
        
        # Add flag for audit trail
        corrected["bias_correction_applied"] = True
        corrected["original_prob_hit"] = original_prob
        
        corrected_edges.append(corrected)
    
    if slam_downgrades > 0:
        print(f"      • {slam_downgrades} SLAM picks downgraded to STRONG")
    
    return corrected_edges
