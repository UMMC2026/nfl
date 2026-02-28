"""
CANONICAL TIER SYSTEM - SOP v2.1 Full Compliance
Sport-Agnostic Probability-Driven Tier Assignment

This module implements the "truth-enforced" tier system per SOP v2.1:
- Single source of truth for tier definitions
- NO sport-specific tier logic (only probability)
- Mandatory validation at render gate
- Audit trail for all tier assignments
"""

from typing import Dict, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CANONICAL TIER DEFINITIONS (SOP v2.1 Section 2.4)
# ============================================================================

class Tier(Enum):
    """
    Canonical tier enumeration
    
    SOP Reference: Section 2.4 - "Confidence Is Earned, Not Assumed"
    
    Confidence Tiers:
    - SLAM (75%+): Multiple independent signal convergence required
    - STRONG (65-74%): Statistical edge + feature consistency
    - LEAN (55-64%): Statistical edge present, lower conviction
    - NO_PLAY (<55%): Excluded from betting recommendations
    """
    SLAM = "SLAM"
    STRONG = "STRONG"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"


TIER_THRESHOLDS = {
    Tier.SLAM: 0.75,      # ≥75% win probability
    Tier.STRONG: 0.65,    # 65-74% win probability
    Tier.LEAN: 0.55,      # 55-64% win probability
    Tier.NO_PLAY: 0.00    # <55% (excluded)
}


# ============================================================================
# CORE TIER ASSIGNMENT FUNCTION
# ============================================================================

def assign_tier(probability: float, 
                strict_mode: bool = True,
                context: Optional[Dict] = None) -> Tier:
    """
    Single source of truth for tier assignment
    
    SOP v2.1 Compliance:
    - Section 2.4: Probability-driven only
    - Section 5 Rule C2: Tier alignment validation
    - Section 6: Render gate enforcement
    
    Args:
        probability: Calculated win probability (0.0 to 1.0)
        strict_mode: If True, enforce SOP compression rules
        context: Optional context for audit trail
        
    Returns:
        Tier enum value
        
    Raises:
        ValueError: If probability is out of range [0.0, 1.0]
        
    Example:
        >>> assign_tier(0.76)
        Tier.SLAM
        >>> assign_tier(0.68)
        Tier.STRONG
        >>> assign_tier(0.52)
        Tier.NO_PLAY
    """
    # Validate probability range
    if not (0.0 <= probability <= 1.0):
        raise ValueError(f"Probability must be in [0.0, 1.0], got {probability}")
    
    # SOP v2.1 Section 5 - Rule C1: Compression
    # If strict mode, compress extreme probabilities
    if strict_mode and probability > 0.90:
        logger.warning(f"Extreme probability {probability:.3f} compressed to 0.85")
        probability = 0.85
    
    # Tier assignment based on thresholds
    if probability >= TIER_THRESHOLDS[Tier.SLAM]:
        tier = Tier.SLAM
    elif probability >= TIER_THRESHOLDS[Tier.STRONG]:
        tier = Tier.STRONG
    elif probability >= TIER_THRESHOLDS[Tier.LEAN]:
        tier = Tier.LEAN
    else:
        tier = Tier.NO_PLAY
    
    # Audit trail (SOP Section 7.1)
    if context:
        _log_tier_assignment(probability, tier, context)
    
    return tier


def assign_tier_string(probability: float, **kwargs) -> str:
    """
    Convenience function returning tier as string
    
    Args:
        probability: Win probability
        **kwargs: Passed to assign_tier()
        
    Returns:
        Tier string value
    """
    tier = assign_tier(probability, **kwargs)
    return tier.value


# ============================================================================
# VALIDATION FUNCTIONS (SOP Section 6 - Render Gate)
# ============================================================================

def validate_tier(tier_str: str, probability: float, raise_on_error: bool = False) -> bool:
    """
    Validate that tier label matches probability
    
    SOP v2.1 Section 6 - Render Gate:
    "Before any report is generated, the system MUST assert:
    ✔ Tier labels match probabilities"
    
    Args:
        tier_str: Tier label string
        probability: Calculated probability
        raise_on_error: If True, raise exception on mismatch
        
    Returns:
        True if tier matches probability
        
    Raises:
        TierMismatchError: If raise_on_error=True and validation fails
        
    Example:
        >>> validate_tier("SLAM", 0.76)
        True
        >>> validate_tier("SLAM", 0.68)
        False
    """
    expected_tier = assign_tier(probability, strict_mode=False)
    is_valid = tier_str == expected_tier.value
    
    if not is_valid:
        error_msg = (
            f"Tier mismatch: '{tier_str}' assigned but probability "
            f"{probability:.3f} suggests '{expected_tier.value}'"
        )
        logger.error(error_msg)
        
        if raise_on_error:
            raise TierMismatchError(error_msg)
    
    return is_valid


def validate_batch_tiers(edges: list, raise_on_error: bool = False) -> Tuple[bool, list]:
    """
    Validate tier consistency across multiple edges
    
    SOP v2.1 Section 6 - Render Gate batch validation
    
    Args:
        edges: List of edge dictionaries with 'tier' and 'probability'
        raise_on_error: If True, raise on first mismatch
        
    Returns:
        (all_valid: bool, errors: list of error messages)
        
    Example:
        >>> edges = [
        ...     {'tier': 'SLAM', 'probability': 0.76},
        ...     {'tier': 'STRONG', 'probability': 0.68}
        ... ]
        >>> validate_batch_tiers(edges)
        (True, [])
    """
    all_valid = True
    errors = []
    
    for i, edge in enumerate(edges):
        tier_str = edge.get('tier')
        probability = edge.get('probability')
        
        if not tier_str or probability is None:
            error_msg = f"Edge {i}: Missing 'tier' or 'probability' field"
            errors.append(error_msg)
            all_valid = False
            continue
        
        try:
            is_valid = validate_tier(tier_str, probability, raise_on_error=False)
            if not is_valid:
                expected = assign_tier(probability, strict_mode=False).value
                error_msg = (
                    f"Edge {i}: Tier '{tier_str}' should be '{expected}' "
                    f"(probability={probability:.3f})"
                )
                errors.append(error_msg)
                all_valid = False
        except Exception as e:
            errors.append(f"Edge {i}: Validation error - {str(e)}")
            all_valid = False
    
    if not all_valid and raise_on_error:
        raise BatchValidationError(f"Tier validation failed: {len(errors)} errors")
    
    return all_valid, errors


# ============================================================================
# TIER DISTRIBUTION ANALYSIS
# ============================================================================

def get_tier_distribution(probabilities: list) -> Dict[str, int]:
    """
    Calculate tier distribution for a set of probabilities
    
    Useful for validation and reporting
    
    Args:
        probabilities: List of probability values
        
    Returns:
        Dictionary mapping tier names to counts
        
    Example:
        >>> probs = [0.76, 0.68, 0.62, 0.52, 0.78]
        >>> get_tier_distribution(probs)
        {'SLAM': 2, 'STRONG': 1, 'LEAN': 1, 'NO_PLAY': 1}
    """
    distribution = {tier.value: 0 for tier in Tier}
    
    for prob in probabilities:
        tier = assign_tier(prob, strict_mode=False)
        distribution[tier.value] += 1
    
    return distribution


def get_tier_statistics(edges: list) -> Dict[str, any]:
    """
    Calculate comprehensive tier statistics
    
    Args:
        edges: List of edge dictionaries
        
    Returns:
        Statistics dictionary with counts, averages, etc.
    """
    tier_probs = {tier.value: [] for tier in Tier}
    
    for edge in edges:
        tier_str = edge.get('tier')
        probability = edge.get('probability')
        
        if tier_str and probability is not None:
            tier_probs[tier_str].append(probability)
    
    stats = {}
    for tier_name, probs in tier_probs.items():
        if probs:
            stats[tier_name] = {
                'count': len(probs),
                'avg_probability': sum(probs) / len(probs),
                'min_probability': min(probs),
                'max_probability': max(probs)
            }
        else:
            stats[tier_name] = {
                'count': 0,
                'avg_probability': 0.0,
                'min_probability': 0.0,
                'max_probability': 0.0
            }
    
    return stats


# ============================================================================
# COMPRESSION RULES (SOP Section 5 - Rule C1)
# ============================================================================

def apply_compression(probability: float, 
                     projection: float,
                     line: float,
                     std_dev: Optional[float] = None) -> float:
    """
    Apply SOP v2.1 compression rule for extreme projections
    
    Rule C1 - Compression:
    If |projection − line| > 2.5 × std_dev, then confidence ≤ 65%
    
    Args:
        probability: Base calculated probability
        projection: Model projection value
        line: Market line value
        std_dev: Standard deviation of projections (if available)
        
    Returns:
        Compressed probability
        
    Example:
        >>> apply_compression(0.82, projection=30, line=22, std_dev=2.5)
        0.65
    """
    if std_dev is None:
        # If no std_dev, use simple threshold
        deviation = abs(projection - line)
        if deviation > 5.0:  # Arbitrary threshold
            return min(probability, 0.65)
        return probability
    
    # Calculate deviation in standard deviations
    deviation = abs(projection - line) / std_dev
    
    # Apply compression if deviation exceeds 2.5 sigma
    if deviation > 2.5:
        compressed = min(probability, 0.65)
        logger.info(
            f"Compression applied: {probability:.3f} → {compressed:.3f} "
            f"(deviation={deviation:.2f}σ)"
        )
        return compressed
    
    return probability


# ============================================================================
# AUDIT LOGGING (SOP Section 7.1)
# ============================================================================

def _log_tier_assignment(probability: float, tier: Tier, context: Dict):
    """
    Log tier assignment for audit trail
    
    SOP v2.1 Section 7.1 - Audit Trail Requirements
    """
    audit_entry = {
        'action': 'TIER_ASSIGNMENT',
        'probability': probability,
        'tier': tier.value,
        'timestamp': context.get('timestamp'),
        'sport': context.get('sport'),
        'player': context.get('player'),
        'market': context.get('market')
    }
    logger.info(f"Tier assigned: {audit_entry}")


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class TierMismatchError(Exception):
    """Raised when tier label doesn't match probability"""
    pass


class BatchValidationError(Exception):
    """Raised when batch tier validation fails"""
    pass


# ============================================================================
# MIGRATION HELPERS (Backward Compatibility)
# ============================================================================

def migrate_legacy_confidence(legacy_confidence: str, 
                              legacy_map: Dict[str, float]) -> Tier:
    """
    Convert legacy confidence strings to canonical tiers
    
    Args:
        legacy_confidence: Old confidence string (e.g., 'HIGH', 'MEDIUM')
        legacy_map: Mapping of legacy strings to probabilities
        
    Returns:
        Canonical Tier enum
        
    Example:
        >>> legacy_map = {'HIGH': 0.75, 'MEDIUM': 0.65, 'LOW': 0.55}
        >>> migrate_legacy_confidence('HIGH', legacy_map)
        Tier.SLAM
    """
    probability = legacy_map.get(legacy_confidence, 0.50)
    return assign_tier(probability, strict_mode=False)


# ============================================================================
# UNIT TESTS
# ============================================================================

if __name__ == "__main__":
    # Test tier assignment
    print("=== Tier Assignment Tests ===")
    test_cases = [
        (0.90, Tier.SLAM),   # With compression
        (0.76, Tier.SLAM),
        (0.68, Tier.STRONG),
        (0.60, Tier.LEAN),
        (0.52, Tier.NO_PLAY)
    ]
    
    for prob, expected in test_cases:
        result = assign_tier(prob, strict_mode=True)
        status = "✅" if result == expected else "❌"
        print(f"{status} P={prob:.2f} → {result.value} (expected {expected.value})")
    
    # Test validation
    print("\n=== Tier Validation Tests ===")
    validation_cases = [
        ("SLAM", 0.76, True),
        ("STRONG", 0.68, True),
        ("SLAM", 0.68, False),  # Mismatch
        ("LEAN", 0.80, False)   # Mismatch
    ]
    
    for tier_str, prob, expected in validation_cases:
        result = validate_tier(tier_str, prob)
        status = "✅" if result == expected else "❌"
        print(f"{status} Tier={tier_str}, P={prob:.2f} → valid={result}")
    
    # Test batch validation
    print("\n=== Batch Validation Test ===")
    edges = [
        {'tier': 'SLAM', 'probability': 0.76, 'player': 'Player A'},
        {'tier': 'STRONG', 'probability': 0.68, 'player': 'Player B'},
        {'tier': 'SLAM', 'probability': 0.62, 'player': 'Player C'}  # Error!
    ]
    
    valid, errors = validate_batch_tiers(edges)
    if valid:
        print("✅ All edges valid")
    else:
        print(f"❌ Validation failed with {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
    
    # Test tier distribution
    print("\n=== Tier Distribution Test ===")
    probs = [0.76, 0.78, 0.68, 0.65, 0.62, 0.60, 0.52, 0.48]
    distribution = get_tier_distribution(probs)
    for tier_name, count in distribution.items():
        print(f"{tier_name}: {count} picks")
    
    # Test compression
    print("\n=== Compression Test ===")
    compressed = apply_compression(0.85, projection=30, line=20, std_dev=2.5)
    print(f"Original: 0.85 → Compressed: {compressed:.2f}")
