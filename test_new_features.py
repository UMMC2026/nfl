"""
Test New Features with Previous Analysis
=========================================

This script demonstrates how to apply the new Task 1-3 features
to an existing analysis output file.
"""

import json
from pathlib import Path
from datetime import datetime

# Task 1: Matchup Memory
from features.nba import (
    PlayerVsOpponentStats,
    MatchupRecord,
    MatchupIndex,
    compute_matchup_adjustment,
    validate_matchup_sample,
    MatchupGate,
)

# Task 2: Probability Lineage
from truth_engine import (
    ProbabilityLineageTracer,
    LineageSource,
    record_lineage_step,
)

# Task 3: MC Hardening
from quant_modules import (
    BetaDistribution,
    scalar_to_beta,
    compute_cvar,
    compute_clamped_kelly,
    evaluate_pick_hardened,
    evaluate_portfolio_hardened,
    estimate_loss_streak_probability,
    HardenedEvaluation,
)


def load_analysis(filepath: str) -> dict:
    """Load a previous analysis file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def test_hardened_evaluation(results: list):
    """Apply MC hardening to picks from analysis."""
    print("\n" + "=" * 60)
    print("TASK 3: MONTE CARLO HARDENING TEST")
    print("=" * 60)
    
    # Filter to plays/leans only
    plays = [r for r in results if r.get("decision") in ["PLAY", "LEAN", "STRONG", "SLAM"]]
    
    if not plays:
        # Use top confidence picks if no plays
        plays = sorted(results, key=lambda x: x.get("model_confidence", 0), reverse=True)[:5]
    
    print(f"\nEvaluating {len(plays)} picks with hardened metrics:\n")
    
    hardened_picks = []
    
    for pick in plays[:10]:  # Limit to 10
        player = pick.get("player", "Unknown")
        stat = pick.get("stat", "PTS")
        line = pick.get("line", 0)
        direction = pick.get("direction", "higher").upper()
        
        # Get probability from analysis
        p_hit = pick.get("model_confidence", 50) / 100
        
        # Map tier to confidence
        tier = pick.get("edge_quality", "LEAN")
        confidence_map = {"SLAM": 0.8, "STRONG": 0.6, "LEAN": 0.4, "NO_PLAY": 0.3}
        confidence = confidence_map.get(tier, 0.5)
        
        # Apply hardened evaluation
        eval_result = evaluate_pick_hardened(
            player_id=player.replace(" ", "_").lower(),
            stat_type=stat.upper(),
            line=line,
            direction=direction,
            p_hit=p_hit,
            payout=3.0,  # 3-pick power payout
            confidence=confidence,
            risk_aversion=0.1,
        )
        
        hardened_picks.append({
            "player": player,
            "stat": stat,
            "line": line,
            "eval": eval_result,
        })
        
        print(f"📊 {player} {stat} {direction} {line}")
        print(f"   Point estimate:    {eval_result.p_hit_point:.1%}")
        print(f"   Conservative (10%): {eval_result.p_hit_conservative:.1%}")
        print(f"   95% CI:            [{eval_result.p_hit_beta.ci_95[0]:.1%}, {eval_result.p_hit_beta.ci_95[1]:.1%}]")
        print(f"   EV (point):        {eval_result.ev_point:+.3f}")
        print(f"   EV (conservative): {eval_result.ev_conservative:+.3f}")
        print(f"   CVaR(95%):         {eval_result.cvar_95:.3f}")
        print(f"   Kelly (clamped):   {eval_result.kelly_clamped:.2%}")
        print()
    
    # Portfolio evaluation
    if len(hardened_picks) >= 3:
        print("\n" + "-" * 40)
        print("PORTFOLIO ANALYSIS (3-pick entry)")
        print("-" * 40)
        
        portfolio_picks = [
            {
                "player_id": p["player"].replace(" ", "_").lower(),
                "stat_type": p["stat"].upper(),
                "p_hit": p["eval"].p_hit_point,
                "confidence": 0.5,
                "line": p["line"],
                "direction": "HIGHER",
            }
            for p in hardened_picks[:3]
        ]
        
        portfolio_result = evaluate_portfolio_hardened(
            portfolio_picks,
            payouts={3: 6.0}  # 3-pick flex payout
        )
        
        print(f"\n🎯 Portfolio Correlation: {portfolio_result['portfolio_correlation']:.2f}")
        print(f"   Correlation Risk: {portfolio_result['risk_summary']['correlation_risk']}")
        print(f"   EV (point avg): {portfolio_result['ev_point_avg']:+.3f}")
        print(f"   EV (correlation adjusted): {portfolio_result['ev_correlation_adjusted']:+.3f}")
        print(f"   5-loss streak probability: {portfolio_result['loss_streak_5_prob']:.1%}")
        print(f"   Streak Risk: {portfolio_result['risk_summary']['streak_risk']}")
        print(f"   Max Drawdown (mean): {portfolio_result['max_drawdown_mean']:.1%}")
        print(f"   Drawdown Risk: {portfolio_result['risk_summary']['drawdown_risk']}")
    
    return hardened_picks


def test_lineage_tracking(results: list):
    """Demonstrate probability lineage tracking."""
    print("\n" + "=" * 60)
    print("TASK 2: PROBABILITY LINEAGE TRACKING TEST")
    print("=" * 60)
    
    tracer = ProbabilityLineageTracer()
    
    # Track a few picks
    for i, pick in enumerate(results[:3]):
        player = pick.get("player", "Unknown")
        stat = pick.get("stat", "PTS")
        line = pick.get("line", 0)
        direction = pick.get("direction", "higher").upper()
        edge_id = f"edge_{i}"
        
        # Start lineage
        tracer.start_lineage(edge_id, player, stat, line, direction)
        
        # Record baseline
        prob = pick.get("model_confidence", 50) / 100
        record_lineage_step(
            tracer, edge_id, LineageSource.BASELINE,
            0.0, prob, 0.9, f"Monte Carlo baseline from L10 stats"
        )
        
        # Record pace factor
        pace_factor = pick.get("pace_factor", 1.0)
        if pace_factor != 1.0:
            new_prob = prob * pace_factor
            record_lineage_step(
                tracer, edge_id, LineageSource.PACE,
                prob, min(new_prob, 0.75), 0.8, f"Pace adjustment x{pace_factor:.3f}",
                {"pace_factor": pace_factor}
            )
            prob = min(new_prob, 0.75)
        
        # Record matchup factor
        matchup_factor = pick.get("matchup_factor", 1.0)
        if matchup_factor != 1.0:
            new_prob = prob * matchup_factor
            record_lineage_step(
                tracer, edge_id, LineageSource.MATCHUP_MEMORY,
                prob, min(new_prob, 0.75), 0.7, f"Matchup adjustment x{matchup_factor:.3f}",
                {"matchup_factor": matchup_factor}
            )
            prob = min(new_prob, 0.75)
        
        # Check if cap was applied
        effective_conf = pick.get("effective_confidence", prob * 100)
        if effective_conf < pick.get("model_confidence", 50):
            record_lineage_step(
                tracer, edge_id, LineageSource.GATE_CAP,
                prob, effective_conf / 100, 1.0, "Confidence cap applied",
                {"original": prob, "capped_to": effective_conf / 100}
            )
    
    # Print lineage summary
    print("\nLineage traces created:")
    for edge_id, lineage in tracer.get_all_lineages().items():
        print(f"\n📜 {lineage.player_id} {lineage.stat_type} {lineage.direction} {lineage.line}")
        print(f"   Initial: {lineage.initial_prob:.1%} → Final: {lineage.final_prob:.1%}")
        print(f"   Adjustments: {lineage.adjustment_count}")
        print(f"   Was capped: {lineage.was_capped}")
        print(f"   Steps:")
        for entry in lineage.entries:
            print(f"      {entry.source.value}: {entry.input_prob:.1%} → {entry.output_prob:.1%} ({entry.reason})")
    
    # Summary report
    report = tracer.generate_summary_report()
    print(f"\n📊 Session Summary:")
    print(f"   Total lineages: {report['total_lineages']}")
    print(f"   Total adjustments: {report['total_adjustments']}")
    print(f"   Source breakdown: {report['source_breakdown']}")
    
    return tracer


def test_matchup_memory():
    """Demonstrate matchup memory (would need historical data to be useful)."""
    print("\n" + "=" * 60)
    print("TASK 1: MATCHUP MEMORY TEST")
    print("=" * 60)
    
    # Create a sample matchup index
    index = MatchupIndex()
    
    # Simulate adding historical matchup data
    print("\nSimulating matchup history for LeBron vs BOS:")
    
    sample_games = [
        {"game_id": "g1", "date": "2025-12-01", "pts": 32, "min": 38},
        {"game_id": "g2", "date": "2025-11-15", "pts": 28, "min": 35},
        {"game_id": "g3", "date": "2025-02-10", "pts": 35, "min": 40},
        {"game_id": "g4", "date": "2024-12-25", "pts": 30, "min": 37},
        {"game_id": "g5", "date": "2024-11-01", "pts": 27, "min": 34},
    ]
    
    for game in sample_games:
        record = MatchupRecord(
            game_id=game["game_id"],
            game_date=datetime.fromisoformat(game["date"]),
            player_id="lebron_james",
            player_name="LeBron James",
            opponent_team="BOS",
            stat_type="PTS",
            stat_value=float(game["pts"]),
            minutes_played=float(game["min"]),
        )
        index.add_record(record)
        print(f"   Added: {game['date']} - {game['pts']} PTS in {game['min']} MIN")
    
    # Retrieve stats
    stats = index.get_stats("lebron_james", "BOS", "PTS")
    
    print(f"\n📊 Matchup Stats: LeBron vs BOS (PTS)")
    print(f"   Games: {stats.games_played}")
    print(f"   Mean: {stats.mean:.1f}")
    print(f"   Std Dev: {stats.std_dev:.1f}")
    print(f"   Recency-weighted: {stats.recency_weighted_mean:.1f}")
    
    # Apply shrinkage
    stats.apply_bayesian_shrinkage(league_mean=25.0, league_std=8.0)
    print(f"   Shrunk mean: {stats.shrunk_mean:.1f}")
    print(f"   Shrinkage weight: {stats.shrinkage_weight:.2f}")
    print(f"   Confidence: {stats.confidence:.2f}")
    
    # Compute adjustment
    baseline = 25.0  # League average
    adjusted, confidence, lineage = compute_matchup_adjustment(
        player_id="lebron_james",
        opponent_team="BOS",
        stat_type="PTS",
        baseline_projection=baseline,
        matchup_index=index,
        league_mean=25.0,
        league_std=8.0,
    )
    
    print(f"\n🎯 Adjustment Applied:")
    print(f"   Baseline: {baseline:.1f}")
    print(f"   Adjusted: {adjusted:.1f}")
    print(f"   Factor: {lineage['adjustment_factor']:.3f}")
    print(f"   Confidence: {confidence:.2f}")
    
    # Validate with gates
    can_apply, discount, audit = validate_matchup_sample(
        games_played=stats.games_played,
        mean=stats.mean,
        std_dev=stats.std_dev,
        last_game_date=stats.last_game_date,
        confidence=stats.confidence,
    )
    
    print(f"\n🚦 Gate Validation:")
    print(f"   Can apply: {can_apply}")
    print(f"   Discount factor: {discount:.2f}")
    for gate_name, gate_result in audit["gates"].items():
        print(f"   {gate_name}: {gate_result['status']} ({gate_result['message']})")


def main():
    # Load most recent analysis
    analysis_file = "outputs/NBATUESDAYPTS_RISK_FIRST_20260126_FROM_UD.json"
    
    print("=" * 60)
    print("TESTING NEW FEATURES WITH PREVIOUS ANALYSIS")
    print("=" * 60)
    print(f"\nLoading: {analysis_file}")
    
    data = load_analysis(analysis_file)
    results = data.get("results", [])
    
    print(f"Loaded {len(results)} props from analysis")
    print(f"Summary: {data.get('play', 0)} plays, {data.get('lean', 0)} leans, {data.get('no_play', 0)} no-play")
    
    # Test each feature
    test_matchup_memory()
    test_lineage_tracking(results)
    test_hardened_evaluation(results)
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE ✓")
    print("=" * 60)
    print("\nTo enable these features in production:")
    print("  Edit config/feature_flags.json and set enabled: true")


if __name__ == "__main__":
    main()
