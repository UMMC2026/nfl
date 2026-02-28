#!/usr/bin/env python3
"""
COLLAPSE_EDGES.PY — SOP v2.1 EDGE COLLAPSE
==========================================
Enforces Rule A2: Multiple lines for same edge → ONE PRIMARY

This MUST run before score_edges.py

Version: 2.1.0
Status: TRUTH-ENFORCED
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


# ============================================================================
# CONFIGURATION
# ============================================================================

# Lines outside this range from median are considered outliers
OUTLIER_THRESHOLD_STDDEV = 2.0

# Minimum lines to consider for outlier detection
MIN_LINES_FOR_OUTLIER_DETECTION = 3


# ============================================================================
# EDGE COLLAPSE LOGIC
# ============================================================================

def collapse_edges(raw_lines: List[Dict]) -> Dict[str, Any]:
    """
    Rule A2 — Edge Collapse (MANDATORY)
    
    If multiple lines exist for the same EDGE:
    → exactly ONE PRIMARY line
    → all others = CORRELATED_ALTERNATIVES
    
    Rule A3 — Canonical Line Selection:
    OVER  → highest reasonable line
    UNDER → lowest reasonable line
    
    Returns:
        {
            "edges": [...],
            "collapse_log": [...],
            "stats": {...}
        }
    """
    
    # Group by unique edge key
    edge_groups = defaultdict(list)
    
    for line in raw_lines:
        # Create unique edge key: player + game + stat + direction
        key = create_edge_key(line)
        edge_groups[key].append(line)
    
    collapsed_edges = []
    collapse_log = []
    
    for edge_key, lines in edge_groups.items():
        direction = lines[0]['direction']
        player_name = lines[0]['player_name']
        
        if len(lines) == 1:
            # Single line - becomes PRIMARY automatically
            edge = lines[0].copy()
            edge['is_primary'] = True
            edge['correlated_lines'] = []
            edge['collapse_source'] = 'single_line'
            collapsed_edges.append(edge)
            
            collapse_log.append({
                "edge_key": edge_key,
                "player": player_name,
                "action": "SINGLE_LINE",
                "primary_line": edge['line'],
                "correlated": []
            })
        else:
            # Multiple lines - need to collapse
            primary, correlated, outliers = select_primary_line(lines, direction)
            
            edge = primary.copy()
            edge['is_primary'] = True
            edge['correlated_lines'] = [l['line'] for l in correlated]
            edge['outlier_lines'] = [l['line'] for l in outliers]
            edge['collapse_source'] = 'collapsed'
            edge['lines_considered'] = len(lines)
            collapsed_edges.append(edge)
            
            collapse_log.append({
                "edge_key": edge_key,
                "player": player_name,
                "action": "COLLAPSED",
                "direction": direction,
                "lines_in": [l['line'] for l in lines],
                "primary_line": primary['line'],
                "correlated": [l['line'] for l in correlated],
                "outliers": [l['line'] for l in outliers],
                "selection_rule": f"{'highest' if direction == 'OVER' else 'lowest'} reasonable line"
            })
    
    # Build stats
    stats = {
        "input_lines": len(raw_lines),
        "output_edges": len(collapsed_edges),
        "lines_collapsed": len(raw_lines) - len(collapsed_edges),
        "edges_with_correlates": sum(1 for e in collapsed_edges if e.get('correlated_lines')),
        "outliers_removed": sum(len(e.get('outlier_lines', [])) for e in collapsed_edges)
    }
    
    return {
        "edges": collapsed_edges,
        "collapse_log": collapse_log,
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def create_edge_key(line: Dict) -> str:
    """Create unique identifier for an edge"""
    return f"{line['player_id']}|{line['game_id']}|{line['stat_type']}|{line['direction']}"


def select_primary_line(lines: List[Dict], direction: str) -> tuple:
    """
    Select the PRIMARY line from multiple options
    
    Rule A3:
    OVER  → highest reasonable line
    UNDER → lowest reasonable line
    
    Outlier lines are excluded from selection
    """
    
    # Extract line values
    line_values = [l['line'] for l in lines]
    
    # Detect and remove outliers
    reasonable_lines, outlier_lines = filter_outliers(lines, line_values)
    
    if not reasonable_lines:
        # All lines were outliers? Use original list
        reasonable_lines = lines
        outlier_lines = []
    
    # Sort by line value
    sorted_lines = sorted(reasonable_lines, key=lambda x: x['line'])
    
    # Select PRIMARY based on direction
    if direction == "OVER":
        # OVER → highest reasonable line
        primary = sorted_lines[-1]
        correlated = sorted_lines[:-1]
    else:  # UNDER
        # UNDER → lowest reasonable line  
        primary = sorted_lines[0]
        correlated = sorted_lines[1:]
    
    return primary, correlated, outlier_lines


def filter_outliers(lines: List[Dict], values: List[float]) -> tuple:
    """
    Remove outlier lines based on statistical distance
    
    Returns: (reasonable_lines, outlier_lines)
    """
    if len(values) < MIN_LINES_FOR_OUTLIER_DETECTION:
        return lines, []
    
    # Calculate median and MAD (median absolute deviation)
    sorted_values = sorted(values)
    n = len(sorted_values)
    median = sorted_values[n // 2] if n % 2 else (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
    
    mad = sorted([abs(v - median) for v in values])[n // 2]
    if mad == 0:
        # No variance - all lines are the same
        return lines, []
    
    # Filter outliers
    threshold = OUTLIER_THRESHOLD_STDDEV * mad * 1.4826  # MAD to std conversion
    
    reasonable = []
    outliers = []
    
    for line in lines:
        if abs(line['line'] - median) <= threshold:
            reasonable.append(line)
        else:
            outliers.append(line)
    
    return reasonable, outliers


# ============================================================================
# VALIDATION
# ============================================================================

def validate_collapse_result(result: Dict) -> List[str]:
    """Verify collapse output meets SOP requirements"""
    errors = []
    
    # Check no duplicate edge keys
    seen_keys = set()
    for edge in result['edges']:
        key = create_edge_key(edge)
        if key in seen_keys:
            errors.append(f"DUPLICATE EDGE KEY: {key}")
        seen_keys.add(key)
    
    # Check all required fields present
    required_fields = ['player_id', 'player_name', 'game_id', 'stat_type', 
                       'direction', 'line', 'is_primary']
    
    for edge in result['edges']:
        missing = [f for f in required_fields if f not in edge]
        if missing:
            errors.append(f"MISSING FIELDS in {edge.get('player_name', 'UNKNOWN')}: {missing}")
    
    return errors


# ============================================================================
# FILE I/O
# ============================================================================

def load_raw_lines(filepath: str) -> List[Dict]:
    """Load raw lines from JSON"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data.get('lines', data)


def save_collapsed_edges(result: Dict, filepath: str):
    """Save collapsed edges to JSON"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(result, f, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Edge Collapse Pipeline Step
    
    Usage: python collapse_edges.py [input_file] [output_file]
    
    Exit codes:
        0 = Success
        1 = Validation errors in output
    """
    print("=" * 60)
    print("SOP v2.1 EDGE COLLAPSE")
    print("=" * 60)
    
    # Paths
    input_file = sys.argv[1] if len(sys.argv) > 1 else "outputs/raw_lines.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "outputs/collapsed_edges.json"
    
    # Check input exists
    if not Path(input_file).exists():
        print(f"\n❌ ERROR: Input file not found: {input_file}")
        print("   Run generate_edges.py first.")
        sys.exit(1)
    
    # Load raw lines
    print(f"\n📂 Loading raw lines from: {input_file}")
    raw_lines = load_raw_lines(input_file)
    print(f"   Found {len(raw_lines)} raw lines")
    
    # Collapse
    print("\n🔄 Collapsing edges...")
    result = collapse_edges(raw_lines)
    
    # Print stats
    stats = result['stats']
    print(f"\n📊 Collapse Results:")
    print(f"   Input lines:        {stats['input_lines']}")
    print(f"   Output edges:       {stats['output_edges']}")
    print(f"   Lines collapsed:    {stats['lines_collapsed']}")
    print(f"   Edges w/correlates: {stats['edges_with_correlates']}")
    print(f"   Outliers removed:   {stats['outliers_removed']}")
    
    # Validate
    print("\n🔍 Validating collapse result...")
    errors = validate_collapse_result(result)
    
    if errors:
        print("\n❌ COLLAPSE VALIDATION FAILED:")
        for err in errors:
            print(f"   • {err}")
        sys.exit(1)
    
    # Save
    save_collapsed_edges(result, output_file)
    print(f"\n✅ Saved collapsed edges to: {output_file}")
    
    # Show collapse log summary
    print("\n📋 Collapse Log (first 5):")
    for log in result['collapse_log'][:5]:
        if log['action'] == 'COLLAPSED':
            print(f"   {log['player']}: {log['lines_in']} → PRIMARY {log['primary_line']}")
        else:
            print(f"   {log['player']}: {log['primary_line']} (single)")
    
    if len(result['collapse_log']) > 5:
        print(f"   ... and {len(result['collapse_log']) - 5} more")
    
    print("\n" + "=" * 60)
    print("EDGE COLLAPSE COMPLETE — Run score_edges.py next")
    print("=" * 60)


if __name__ == "__main__":
    main()
