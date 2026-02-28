"""
CBB Edge Schema Validator

Validates edge objects have required fields and valid values.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import fields


REQUIRED_FIELDS = [
    "edge_id",
    "game_id",
    "player_id",
    "player_name",
    "team",
    "stat",
    "line",
    "direction",
    "probability",
    "tier",
]

VALID_DIRECTIONS = ["higher", "lower"]
VALID_TIERS = ["STRONG", "LEAN", "NO_PLAY"]


def validate_edge_schema(edge) -> Tuple[bool, List[str]]:
    """
    Validate a single edge has correct schema.
    
    Args:
        edge: CBBEdge object
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    # Check required fields
    for field in REQUIRED_FIELDS:
        if not hasattr(edge, field):
            errors.append(f"Missing required field: {field}")
        elif getattr(edge, field) is None:
            errors.append(f"Required field is None: {field}")
    
    # Validate direction
    if hasattr(edge, "direction"):
        if edge.direction not in VALID_DIRECTIONS:
            errors.append(f"Invalid direction: {edge.direction}")
    
    # Validate tier
    if hasattr(edge, "tier"):
        if edge.tier not in VALID_TIERS:
            errors.append(f"Invalid tier: {edge.tier}")
    
    # Validate probability range
    if hasattr(edge, "probability"):
        if not (0.0 <= edge.probability <= 1.0):
            errors.append(f"Probability out of range: {edge.probability}")
    
    # Validate line is positive
    if hasattr(edge, "line"):
        if edge.line < 0:
            errors.append(f"Negative line value: {edge.line}")
    
    return (len(errors) == 0, errors)


def validate_edges_batch(edges: List) -> Dict:
    """
    Validate a batch of edges.
    
    Returns summary of validation results.
    """
    total = len(edges)
    valid = 0
    invalid = 0
    all_errors = []
    
    for edge in edges:
        is_valid, errors = validate_edge_schema(edge)
        if is_valid:
            valid += 1
        else:
            invalid += 1
            for err in errors:
                all_errors.append(f"{edge.edge_id}: {err}")
    
    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "errors": all_errors,
        "pass": invalid == 0,
    }


def validate_data_sources(edge) -> Tuple[bool, str]:
    """
    Validate edge has required data sources.
    
    CBB requires at least 1 data source (less strict than NFL/NBA).
    """
    if not hasattr(edge, "data_sources") or not edge.data_sources:
        return (False, "No data sources")
    
    if len(edge.data_sources) < 1:
        return (False, f"Insufficient data sources: {len(edge.data_sources)}")
    
    return (True, "OK")
