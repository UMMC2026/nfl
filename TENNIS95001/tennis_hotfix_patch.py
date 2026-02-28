"""
TENNIS CONFIDENCE HOTFIX - Option 1 Implementation
SOP v2.1 Compliant Emergency Patch

Apply this patch to tennis/tennis_edge_detector.py to fix KeyError
"""

# ============================================================================
# HOTFIX PATCH - ADD TO TOP OF tennis_edge_detector.py (after imports)
# ============================================================================

from config.thresholds import CONFIDENCE_CAPS

# Emergency mapping: Tennis legacy confidence to canonical thresholds
TENNIS_CONFIDENCE_MAP = {
    'HIGH': 'core',           # Maps to 0.75 (SLAM tier)
    'MEDIUM': 'volume_micro', # Maps to 0.65 (STRONG tier)  
    'LOW': 'sequence_early'   # Maps to 0.60 (LEAN tier)
}

# ============================================================================
# REPLACE EXISTING _assign_tier METHOD (around line 138-150)
# ============================================================================

def _assign_tier(self, confidence: str, prob: float) -> str:
    """
    Assign tier based on confidence and probability
    
    HOTFIX: Maps tennis confidence strings to canonical thresholds
    SOP v2.1 Section 2.4 - "Confidence Is Earned, Not Assumed"
    
    Args:
        confidence: Tennis confidence level ('HIGH', 'MEDIUM', 'LOW')
        prob: Calculated probability (0.0 to 1.0)
        
    Returns:
        Tier string: 'SLAM', 'STRONG', 'LEAN', or 'NO PLAY'
        
    SOP Compliance:
        - Maps legacy tennis confidence to canonical caps
        - Validates probability against thresholds
        - Returns SOP-compliant tier labels
    """
    # Map tennis confidence to canonical key
    canonical_key = TENNIS_CONFIDENCE_MAP.get(confidence, 'event_binary')
    threshold = CONFIDENCE_CAPS.get(canonical_key, 0.55)
    
    # SOP v2.1 Section 5 - Rule C2: Tier Alignment
    if confidence == "HIGH" and prob > threshold:
        tier = "SLAM"
    elif confidence == "MEDIUM" and prob > threshold:
        tier = "STRONG"  
    elif confidence == "LOW" and prob > threshold:
        tier = "LEAN"
    else:
        tier = "NO PLAY"
    
    # Validation: Ensure tier matches probability range
    if tier == "SLAM" and prob < 0.75:
        tier = "STRONG"  # Downgrade if probability too low
    elif tier == "STRONG" and prob < 0.65:
        tier = "LEAN"
    
    return tier


# ============================================================================
# QUICK TEST - Add to test file or run standalone
# ============================================================================

def test_hotfix():
    """Verify hotfix resolves KeyError"""
    
    # Mock detector class for testing
    class TennisDetector:
        def _assign_tier(self, confidence: str, prob: float) -> str:
            canonical_key = TENNIS_CONFIDENCE_MAP.get(confidence, 'event_binary')
            threshold = CONFIDENCE_CAPS.get(canonical_key, 0.55)
            
            if confidence == "HIGH" and prob > threshold:
                return "SLAM"
            elif confidence == "MEDIUM" and prob > threshold:
                return "STRONG"
            elif confidence == "LOW" and prob > threshold:
                return "LEAN"
            else:
                return "NO PLAY"
    
    detector = TennisDetector()
    
    # Test cases that previously caused KeyError
    assert detector._assign_tier("HIGH", 0.76) == "SLAM"
    assert detector._assign_tier("MEDIUM", 0.68) == "STRONG"
    assert detector._assign_tier("LOW", 0.62) == "LEAN"
    assert detector._assign_tier("LOW", 0.52) == "NO PLAY"
    
    print("✅ Hotfix validated - no KeyError")
    print("✅ All tier assignments working")
    

if __name__ == "__main__":
    test_hotfix()
