"""
CBB Diagnostics and Data Integrity Validation
Blocks or flags picks with missing trend/context/line data, suspicious line gaps, or confidence logic bugs.
"""

def validate_cbb_edges(edges):
    """
    Validates CBB edges for data integrity before output.
    Returns (valid_edges, blocked_edges, diagnostics_report)
    """
    valid = []
    blocked = []
    diagnostics = []
    for e in edges:
        # Extract key fields
        mean = e.get('mean') or e.get('player_mean') or e.get('mu')
        line = e.get('line')
        prob = e.get('probability')
        stat = e.get('stat') or e.get('market')
        direction = e.get('direction')
        spread = e.get('spread')
        context = e.get('context')
        sigma = e.get('sigma')
        sample_n = e.get('sample_n') or e.get('n')
        # 1. Missing trend data
        if mean is None or mean == 0:
            blocked.append(e)
            diagnostics.append(f"BLOCKED: {e.get('player','?')} {stat} {direction} {line} — missing mean/trend data.")
            continue
        # 2. Suspicious line gaps
        if line is None or abs(line - mean) < 0.01:
            blocked.append(e)
            diagnostics.append(f"BLOCKED: {e.get('player','?')} {stat} {direction} {line} — line equals mean (no edge).")
            continue
        if abs(line - mean) / (abs(mean) + 1e-6) > 0.5:
            diagnostics.append(f"WARN: {e.get('player','?')} {stat} {direction} {line} — line >50% from mean (possible stale line).")
        # 3. Missing spread/context
        if not spread or spread == 'MISSING' or not context:
            blocked.append(e)
            diagnostics.append(f"BLOCKED: {e.get('player','?')} {stat} {direction} {line} — missing spread/context.")
            continue
        # 4. Confidence logic bugs
        if prob is None or prob < 0.55 or prob > 0.99:
            blocked.append(e)
            diagnostics.append(f"BLOCKED: {e.get('player','?')} {stat} {direction} {line} — probability out of bounds: {prob}.")
            continue
        # 5. Volatility check
        if sigma is not None and sigma == 0 and sample_n and sample_n > 2:
            diagnostics.append(f"WARN: {e.get('player','?')} {stat} {direction} {line} — zero volatility with n={sample_n}.")
        valid.append(e)
    # UNDER bias check
    under_count = sum(1 for e in valid if e.get('direction') == 'lower')
    over_count = sum(1 for e in valid if e.get('direction') == 'higher')
    total = len(valid)
    if total > 0:
        if under_count / total > 0.8:
            diagnostics.append(f"BLOCKED: Systematic UNDER bias detected ({under_count}/{total}).")
            blocked.extend(valid)
            valid = []
    return valid, blocked, diagnostics
