"""Quick pipeline test for CBB module."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sports.cbb.cbb_main import generate_cbb_edges, apply_cbb_gates, score_cbb_edges, poisson_probability, negbin_probability, get_cbb_sigma, CBB_SIGMA_TABLE


def test_complementary_probs():
    """Test that higher and lower give complementary probabilities."""
    print("=" * 60)
    print("TEST: Complementary Probabilities")
    print("=" * 60)
    
    # v2.0: fallback mean is neutral (mean = line)
    mean = 18.5
    line = 18.5
    
    p_higher = poisson_probability(mean, line, "higher")
    p_lower = poisson_probability(mean, line, "lower")
    
    print(f"Mean: {mean:.2f}, Line: {line}")
    print(f"P(higher): {p_higher:.1%}")
    print(f"P(lower):  {p_lower:.1%}")
    print(f"Sum:       {p_higher + p_lower:.1%}")
    
    # Sum should be close to 100% (Poisson is discrete so might be slightly off)
    assert 0.95 <= p_higher + p_lower <= 1.05, f"Probs don't sum to ~100%: {p_higher + p_lower:.1%}"
    print("PASS: Probabilities are complementary")
    return True


def test_deduplication():
    """Test that duplicate directions are removed, keeping best."""
    print("\n" + "=" * 60)
    print("TEST: Deduplication")
    print("=" * 60)
    
    # Create both directions for same prop
    test_props = [
        # NOTE: leave team blank to prevent tests from triggering live ESPN fetches.
        {"player": "Test Player", "team": "", "stat": "points", "line": 18.5, "direction": "higher"},
        {"player": "Test Player", "team": "", "stat": "points", "line": 18.5, "direction": "lower"},
    ]
    
    print(f"Input: {len(test_props)} props (both directions)")
    
    edges = generate_cbb_edges(test_props)
    
    print(f"Output: {len(edges)} edges (should be 1)")
    
    for e in edges:
        direction = e.get("direction", "?")
        prob = e.get("probability", 0)
        print(f"  Kept: {direction} with {prob:.1%}")
    
    assert len(edges) == 1, f"Expected 1 edge after dedup, got {len(edges)}"
    print("PASS: Deduplication working")
    return True


def main():
    print("=" * 60)
    print("CBB PIPELINE TESTS")
    print("=" * 60)
    
    # Test 1: Complementary probabilities
    test_complementary_probs()
    
    # Test 2: Deduplication
    test_deduplication()
    
    # Test 3: Full pipeline with sample props
    print("\n" + "=" * 60)
    print("TEST: Full Pipeline")
    print("=" * 60)
    
    test_props = [
        # NOTE: leave team blank to prevent tests from triggering live ESPN fetches.
        {"player": "Player 1", "team": "", "stat": "Points", "line": 18.5, "direction": "higher"},
        {"player": "Player 1", "team": "", "stat": "Points", "line": 18.5, "direction": "lower"},
        {"player": "Player 2", "team": "", "stat": "Rebounds", "line": 8.5, "direction": "higher"},
    ]
    
    print(f"Input: {len(test_props)} props")
    
    edges = generate_cbb_edges(test_props)
    gated = apply_cbb_gates(edges)
    scored = score_cbb_edges(gated)
    
    print(f"\nFinal: {len(scored)} edges")
    for e in scored:
        player = e.get("player", "?")
        stat = e.get("stat", "?")
        direction = e.get("direction", "?")
        prob = e.get("probability", 0)
        tier = e.get("tier", "?")
        print(f"  {player} {stat} {direction}: {prob:.1%} [{tier}]")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
