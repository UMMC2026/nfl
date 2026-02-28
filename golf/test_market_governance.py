"""Test script for market governance module."""

from golf.config.market_governance import (
    MarketStatus,
    GOLF_MARKETS,
    is_market_enabled,
    get_golf_confidence_cap,
    validate_market_for_edge,
    normalize_market
)

def main():
    print("=" * 60)
    print("GOLF MARKET GOVERNANCE TEST")
    print("=" * 60)
    
    # List enabled markets
    print("\n✅ ENABLED MARKETS (Phase 1 - No ShotLink Required):")
    enabled = [(k, v) for k, v in GOLF_MARKETS.items() if v.status == MarketStatus.ENABLED]
    for name, config in enabled:
        print(f"   • {name}")
    
    # List disabled markets
    print("\n❌ DISABLED MARKETS (Require ShotLink/Round Data):")
    disabled = [(k, v) for k, v in GOLF_MARKETS.items() if v.status == MarketStatus.DISABLED]
    for name, config in disabled:
        print(f"   • {name}: {config.reason}")
    
    # List requires_data markets
    print("\n🔒 REQUIRES_DATA MARKETS:")
    requires = [(k, v) for k, v in GOLF_MARKETS.items() if v.status == MarketStatus.REQUIRES_DATA]
    for name, config in requires:
        print(f"   • {name}: {config.reason}")
    
    # Test validation functions
    print("\n" + "=" * 60)
    print("VALIDATION TESTS")
    print("=" * 60)
    
    test_cases = [
        ("birdies", 0.65),
        ("round_strokes", 0.65),
        ("fairways_hit", 0.65),
        ("head_to_head", 0.65),
        ("top_20", 0.65),
        ("pars", 0.65),
    ]
    
    for market, prob in test_cases:
        is_valid, state, msg = validate_market_for_edge(market, prob)
        status = "✅" if is_valid else "❌"
        print(f"   {status} {market} @ {prob:.0%}: {state} - {msg if msg else 'OK'}")
    
    # Test confidence caps
    print("\n" + "=" * 60)
    print("CONFIDENCE CAP TESTS")
    print("=" * 60)
    
    cap_tests = [
        ("birdies", "lower"),
        ("birdies", "higher"),
        ("round_strokes", "lower"),
        ("round_strokes", "higher"),
        ("pars", "lower"),
        ("head_to_head", "higher"),
    ]
    
    for market, direction in cap_tests:
        cap = get_golf_confidence_cap(market, direction)
        print(f"   {market} {direction}: {cap:.0%} max")
    
    # Test alias normalization
    print("\n" + "=" * 60)
    print("MARKET ALIAS NORMALIZATION")
    print("=" * 60)
    
    alias_tests = [
        "birdies_or_better",
        "Birdies Or Better", 
        "strokes",
        "Round Strokes",
        "finishing_position",
        "Tourney Finishing Position"
    ]
    
    for alias in alias_tests:
        normalized = normalize_market(alias)
        print(f"   '{alias}' → '{normalized}'")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
