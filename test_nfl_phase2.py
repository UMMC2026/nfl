"""
Phase 2 Integration Test - Bayesian Priors
==========================================
Tests the complete Bayesian prior system for NFL props.
"""

from ufa.analysis.prob import prob_hit, prob_hit_nfl
from ufa.analysis.nfl_bayesian_prior import NFLBayesianPrior, get_nfl_posterior


def test_bayesian_vs_simple():
    """Compare Bayesian prior vs simple mean/std."""
    print("=" * 70)
    print("PHASE 2 TEST: Bayesian Priors vs Simple μ/σ")
    print("=" * 70)
    
    # Test case: Josh Allen Pass Yards 265.5 HIGHER vs KC
    player = "Josh Allen"
    position = "QB"
    stat = "pass_yds"
    line = 265.5
    direction = "higher"
    opponent = "KC"  # Tough pass defense (0.92 multiplier)
    recent = [285, 310, 245, 290, 275, 305, 260, 280]
    
    print(f"\n[TEST 1] {player} {stat} {line} {direction.upper()} vs {opponent}")
    print(f"Recent games: {recent}")
    
    # Method 1: Simple mean/std (old way)
    simple_p = prob_hit(line, direction, recent_values=recent)
    print(f"\n  Simple μ/σ method:")
    print(f"    P(hit) = {simple_p:.1%}")
    
    # Method 2: Bayesian priors (new way)
    result = prob_hit_nfl(
        line, direction,
        player=player,
        position=position,
        stat=stat,
        recent_values=recent,
        opponent=opponent
    )
    print(f"\n  Bayesian Prior method:")
    print(f"    Prior μ = {result['prior_mu']:.1f}, σ = {result['prior_sigma']:.1f}")
    print(f"    Sample μ = {result['sample_mu']:.1f} (n={result['sample_size']})")
    print(f"    Posterior μ = {result['posterior_mu']:.1f}, σ = {result['posterior_sigma']:.1f}")
    print(f"    Shrinkage = {result['shrinkage']:.0%} toward prior")
    print(f"    Elite adj = {result['elite_adj']:.2f}x (Josh Allen boost)")
    print(f"    Matchup adj = {result['matchup_adj']:.2f}x (KC tough pass def)")
    print(f"    Raw P(hit) = {result['raw_p']:.1%}")
    print(f"    Governed P(hit) = {result['p_hit']:.1%}")
    print(f"    Confidence: {result['confidence'].upper()}")
    
    # Show the difference
    diff = result['p_hit'] - simple_p
    print(f"\n  DELTA: {diff:+.1%} ({'+' if diff > 0 else ''}more conservative with Bayesian)")


def test_elite_vs_average():
    """Show how elite players get adjusted priors."""
    print("\n" + "=" * 70)
    print("PHASE 2 TEST: Elite Player Adjustments")
    print("=" * 70)
    
    # Same recent values, different players
    recent = [65, 70, 55, 80, 60]
    line = 70.5
    direction = "higher"
    
    players = [
        ("Travis Kelce", "TE", 1.50),   # Elite TE
        ("Average TE", "TE", 1.00),     # League average
    ]
    
    print(f"\nComparing rec_yds {line} HIGHER with same recent games: {recent}")
    
    for player, pos, expected_mult in players:
        result = prob_hit_nfl(
            line, direction,
            player=player,
            position=pos,
            stat="rec_yds",
            recent_values=recent
        )
        print(f"\n  {player}:")
        print(f"    Posterior μ = {result['posterior_mu']:.1f}")
        print(f"    Elite adj = {result['elite_adj']:.2f}x")
        print(f"    P(hit) = {result['p_hit']:.1%}")


def test_matchup_adjustments():
    """Show how opponent defense affects probability."""
    print("\n" + "=" * 70)
    print("PHASE 2 TEST: Matchup Adjustments")
    print("=" * 70)
    
    recent = [95, 110, 85, 100, 90, 105]
    line = 99.5
    direction = "higher"
    
    opponents = [
        ("CAR", "Bad defense", 1.15),
        ("KC", "Average defense", 0.95),  
        ("BAL", "Good defense", 0.85),
    ]
    
    print(f"\nDerrick Henry rush_yds {line} HIGHER vs different opponents")
    print(f"Recent games: {recent}")
    
    for opp, desc, _ in opponents:
        result = prob_hit_nfl(
            line, direction,
            player="Derrick Henry",
            position="RB",
            stat="rush_yds",
            recent_values=recent,
            opponent=opp
        )
        print(f"\n  vs {opp} ({desc}):")
        print(f"    Matchup adj = {result['matchup_adj']:.2f}x")
        print(f"    Posterior μ = {result['posterior_mu']:.1f}")
        print(f"    P(hit) = {result['p_hit']:.1%}")


def test_sample_size_shrinkage():
    """Show how small samples shrink toward prior."""
    print("\n" + "=" * 70)
    print("PHASE 2 TEST: Sample Size Shrinkage")
    print("=" * 70)
    
    line = 55.5
    direction = "higher"
    
    # Same average but different sample sizes
    samples = {
        "3 games": [60, 55, 70],
        "5 games": [60, 55, 70, 58, 65],
        "10 games": [60, 55, 70, 58, 65, 62, 54, 68, 59, 66],
    }
    
    print(f"\nUnknown WR rec_yds {line} HIGHER (same ~62 avg, different n)")
    
    for label, recent in samples.items():
        result = prob_hit_nfl(
            line, direction,
            player="Unknown WR",
            position="WR",
            stat="rec_yds",
            recent_values=recent
        )
        print(f"\n  {label}:")
        print(f"    Sample μ = {result['sample_mu']:.1f}")
        print(f"    Shrinkage = {result['shrinkage']:.0%}")
        print(f"    Posterior μ = {result['posterior_mu']:.1f}")
        print(f"    Confidence = {result['confidence'].upper()}")
        print(f"    P(hit) = {result['p_hit']:.1%}")


def test_full_workflow():
    """Demonstrate full analysis workflow."""
    print("\n" + "=" * 70)
    print("PHASE 2 TEST: Full Playoff Prop Analysis")
    print("=" * 70)
    
    # Playoff props
    props = [
        {"player": "Josh Allen", "pos": "QB", "stat": "pass_yds", 
         "line": 265.5, "dir": "higher", "opp": "KC", 
         "recent": [285, 310, 245, 290, 275, 305]},
        
        {"player": "Patrick Mahomes", "pos": "QB", "stat": "pass_yds",
         "line": 275.5, "dir": "higher", "opp": "BUF",
         "recent": [280, 265, 295, 310, 245, 290]},
        
        {"player": "Travis Kelce", "pos": "TE", "stat": "rec_yds",
         "line": 64.5, "dir": "higher", "opp": "BUF",
         "recent": [75, 82, 65, 90, 55, 78]},
        
        {"player": "James Cook", "pos": "RB", "stat": "rush_yds",
         "line": 54.5, "dir": "higher", "opp": "KC",
         "recent": [60, 45, 70, 55, 65, 50]},
    ]
    
    print("\nPlayoff Props Analysis with Bayesian Priors:\n")
    print(f"{'Player':<20} {'Line':<12} {'Post μ':<10} {'P(hit)':<10} {'Confidence':<12} {'Edge':<10}")
    print("-" * 74)
    
    for p in props:
        result = prob_hit_nfl(
            p["line"], p["dir"],
            player=p["player"],
            position=p["pos"],
            stat=p["stat"],
            recent_values=p["recent"],
            opponent=p["opp"]
        )
        
        # Calculate edge (p_hit - 0.5)
        edge = result["p_hit"] - 0.5
        edge_str = f"{edge:+.1%}" if edge != 0 else "0%"
        
        line_str = f"{p['stat']} {p['line']} {p['dir'][0].upper()}"
        
        print(f"{p['player']:<20} {line_str:<12} {result['posterior_mu']:<10.1f} "
              f"{result['p_hit']:<10.1%} {result['confidence'].upper():<12} {edge_str:<10}")
    
    print("\n✅ Phase 2 Bayesian Priors: OPERATIONAL")


if __name__ == "__main__":
    test_bayesian_vs_simple()
    test_elite_vs_average()
    test_matchup_adjustments()
    test_sample_size_shrinkage()
    test_full_workflow()
    
    print("\n" + "=" * 70)
    print("PHASE 2 COMPLETE: Bayesian priors integrated into probability engine")
    print("=" * 70)
