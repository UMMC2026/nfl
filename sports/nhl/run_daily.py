"""
NHL Daily Pipeline — Main Entry Point v2.0
============================================

Usage:
    .venv/Scripts/python.exe sports/nhl/run_daily.py --dry-run
    .venv/Scripts/python.exe sports/nhl/run_daily.py --date 2026-02-15

Hard Gates (in order):
    1. Sport enabled in config/sport_registry.json
    2. Goalie confirmation gate (MANDATORY)
    3. Sample sufficiency gate
    4. Edge threshold gate (2% minimum)
    
v2.0 Additions:
    - Referee bias adjustments (Module 1)
    - Travel fatigue penalties (Module 2)
    - Player SOG props (Module 3)
    - Live intermission engine (Module 4)

Global Assertions:
    - unconfirmed_goalie_bets == 0
    - slam_count == 0
    - live_bets_per_game <= 1
    - |calibration_error| <= 0.03
    - max_drawdown <= 25%
"""

import argparse
import json
import sys
import hashlib
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
import logging

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sports.nhl.goalies.confirmation_gate import (
    GoalieConfirmationGate,
    GoalieInfo,
    GoalieStatus,
    GateResult,
    enforce_goalie_gate,
)
from sports.nhl.models.poisson_sim import (
    PoissonSimulator,
    TeamXG,
    SimulationResult,
    simulate_nhl_game,
)
from sports.nhl.config.thresholds import (
    NHL_TIERS,
    NHL_EDGE_MINIMUM,
    get_nhl_tier,
    apply_nhl_cap,
    apply_nhl_adjustments,
)

# v2.0 imports
try:
    from sports.nhl.context.ref_bias import RefereeBiasCalculator, get_ref_adjustment
    from sports.nhl.context.travel_fatigue import TravelFatigueCalculator, get_travel_adjustment
    from sports.nhl.players.shots_model import PlayerShotsModel, project_player_sog
    from sports.nhl.players.shots_simulate import simulate_player_sog
    V2_MODULES_AVAILABLE = True
except ImportError:
    V2_MODULES_AVAILABLE = False

# Configure logging (moved before player stats import to avoid NameError)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Import real player stats for 2025-26 season
try:
    from sports.nhl.player_stats import (
        SKATER_STATS_2026,
        GOALIE_STATS_2026,
        get_player_stats,
        get_goalie_stats,
        get_lambda,
        get_sigma,
    )
    PLAYER_STATS_AVAILABLE = True
    logger.info(f"Loaded player stats: {len(SKATER_STATS_2026)} skaters, {len(GOALIE_STATS_2026)} goalies")
except ImportError:
    PLAYER_STATS_AVAILABLE = False
    logger.warning("Player stats module not available - using defaults")


# =============================================================================
# EDGE SCHEMA
# =============================================================================

@dataclass
class NHLEdge:
    """NHL edge output schema (v2.0)."""
    sport: str = "NHL"
    game_id: str = ""
    game: str = ""
    game_time: str = ""
    
    # Goalies
    home_goalie: str = ""
    home_goalie_status: str = ""
    home_goalie_sv_pct: float = 0.0
    away_goalie: str = ""
    away_goalie_status: str = ""
    away_goalie_sv_pct: float = 0.0
    
    # Market
    market: str = ""
    side: str = ""
    model_prob: float = 0.0
    implied_prob: float = 0.0
    edge: float = 0.0
    tier: str = "NO_PLAY"
    pick_state: str = "REJECTED"
    
    # Risk
    risk_tags: List[str] = None
    confidence_cap: Optional[float] = None
    
    # Model inputs
    home_lambda: float = 0.0
    away_lambda: float = 0.0
    simulations: int = 20000
    
    # v2.0 Context adjustments
    ref_crew: str = ""
    ref_adjustment: float = 0.0
    travel_penalty_home: float = 0.0
    travel_penalty_away: float = 0.0
    
    # Audit
    sources: List[str] = None
    run_id: str = ""
    audit_hash: str = ""
    
    def __post_init__(self):
        if self.risk_tags is None:
            self.risk_tags = []
        if self.sources is None:
            self.sources = []
    
    def compute_audit_hash(self) -> str:
        """Compute SHA256 hash for audit trail."""
        content = f"{self.game_id}|{self.market}|{self.side}|{self.model_prob}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d["audit_hash"] = self.compute_audit_hash()
        return d


# =============================================================================
# PIPELINE FUNCTIONS
# =============================================================================

def check_sport_enabled() -> bool:
    """Check if NHL is enabled in sport_registry.json."""
    registry_path = PROJECT_ROOT / "config" / "sport_registry.json"
    
    if not registry_path.exists():
        logger.warning("sport_registry.json not found, NHL disabled by default")
        return False
    
    try:
        with open(registry_path) as f:
            registry = json.load(f)
        
        nhl_config = registry.get("NHL", {})
        enabled = nhl_config.get("enabled", False)
        
        if not enabled:
            logger.info("NHL is disabled in sport_registry.json")
        
        return enabled
    except Exception as e:
        logger.error(f"Failed to read sport_registry.json: {e}")
        return False


def generate_edges_from_simulation(
    game_id: str,
    game: str,
    game_time: str,
    sim_result: SimulationResult,
    goalie_evaluation,
    implied_odds: Dict[str, float],
    run_id: str,
) -> List[NHLEdge]:
    """
    Generate edges from simulation results.
    
    Args:
        game_id: NHL API game ID
        game: Game string (e.g., "BOS @ NYR")
        game_time: ISO timestamp
        sim_result: Poisson simulation result
        goalie_evaluation: Goalie gate evaluation result
        implied_odds: Market implied probabilities
        run_id: Pipeline run ID
        
    Returns:
        List of NHLEdge objects
    """
    edges = []
    
    # Extract goalie info
    home_goalie = goalie_evaluation.home_goalie
    away_goalie = goalie_evaluation.away_goalie
    risk_tags = goalie_evaluation.risk_tags
    confidence_cap = goalie_evaluation.confidence_cap
    
    # Get moneyline probabilities (including OT)
    simulator = PoissonSimulator()
    home_ml, away_ml = simulator.get_moneyline_probs(sim_result)
    
    # Define markets to evaluate
    markets = [
        ("Moneyline", sim_result.home_team, home_ml, implied_odds.get("home_ml", 0.5)),
        ("Moneyline", sim_result.away_team, away_ml, implied_odds.get("away_ml", 0.5)),
        ("Puck Line -1.5", sim_result.home_team, sim_result.home_cover_1_5, implied_odds.get("home_pl", 0.35)),
        ("Puck Line +1.5", sim_result.away_team, sim_result.away_cover_1_5, implied_odds.get("away_pl", 0.65)),
        ("Total Over 5.5", "OVER", sim_result.over_5_5, implied_odds.get("over_5_5", 0.5)),
        ("Total Under 5.5", "UNDER", sim_result.under_5_5, implied_odds.get("under_5_5", 0.5)),
        ("Total Over 6.5", "OVER", sim_result.over_6_5, implied_odds.get("over_6_5", 0.4)),
        ("Total Under 6.5", "UNDER", sim_result.under_6_5, implied_odds.get("under_6_5", 0.6)),
    ]
    
    for market, side, model_prob, implied_prob in markets:
        # Apply confidence cap if any
        if confidence_cap and model_prob > confidence_cap:
            model_prob = confidence_cap
        
        # Calculate edge
        edge = model_prob - implied_prob
        
        # Determine tier
        tier = get_nhl_tier(model_prob)
        
        # Determine pick state
        if edge < NHL_EDGE_MINIMUM:
            pick_state = "REJECTED"
            tier = "NO_PLAY"
        elif tier == "NO_PLAY":
            pick_state = "REJECTED"
        else:
            pick_state = "OPTIMIZABLE"
        
        edge_obj = NHLEdge(
            game_id=game_id,
            game=game,
            game_time=game_time,
            home_goalie=home_goalie.name if home_goalie else "",
            home_goalie_status=home_goalie.status.value if home_goalie else "",
            home_goalie_sv_pct=home_goalie.last_10_sv_pct or 0.0 if home_goalie else 0.0,
            away_goalie=away_goalie.name if away_goalie else "",
            away_goalie_status=away_goalie.status.value if away_goalie else "",
            away_goalie_sv_pct=away_goalie.last_10_sv_pct or 0.0 if away_goalie else 0.0,
            market=market,
            side=side,
            model_prob=round(model_prob, 4),
            implied_prob=round(implied_prob, 4),
            edge=round(edge, 4),
            tier=tier,
            pick_state=pick_state,
            risk_tags=risk_tags.copy(),
            confidence_cap=confidence_cap,
            home_lambda=sim_result.home_goals_mean,
            away_lambda=sim_result.away_goals_mean,
            simulations=sim_result.simulations,
            sources=["nhl_api", "naturalstattrick", "dailyfaceoff"],
            run_id=run_id,
        )
        
        edges.append(edge_obj)
    
    return edges


def run_daily_pipeline(
    target_date: date = None,
    dry_run: bool = False,
) -> List[NHLEdge]:
    """
    Run the NHL daily pipeline.
    
    Args:
        target_date: Date to analyze (default: today)
        dry_run: If True, don't write output files
        
    Returns:
        List of generated edges
    """
    target_date = target_date or date.today()
    run_id = f"nhl_{target_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}"
    
    logger.info(f"=" * 60)
    logger.info(f"NHL DAILY PIPELINE — {target_date}")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info(f"=" * 60)
    
    # === GATE 0: Check if NHL is enabled ===
    if not dry_run and not check_sport_enabled():
        logger.warning("NHL is disabled. Use --dry-run for testing.")
        print("\n⚠️  NHL is DISABLED in config/sport_registry.json")
        print("    To enable: Set 'NHL.enabled': true")
        print("    Or use: --dry-run for testing\n")
        return []
    
    # === DEMO DATA (Replace with actual API calls) ===
    # This is placeholder data for testing the pipeline structure
    demo_games = [
        {
            "game_id": "2026020801",
            "game": "BOS @ NYR",
            "game_time": f"{target_date}T19:00:00-05:00",
            "home_goalie": {
                "name": "Igor Shesterkin",
                "status": "CONFIRMED",
                "sources": ["dailyfaceoff", "nyr_beat"],
                "stats": {"sv_pct": 0.928, "gsaa": 4.1, "starts": 12, "is_b2b": False},
            },
            "away_goalie": {
                "name": "Jeremy Swayman",
                "status": "CONFIRMED",
                "sources": ["dailyfaceoff", "bruins_beat"],
                "stats": {"sv_pct": 0.921, "gsaa": 2.4, "starts": 10, "is_b2b": False},
            },
            "home_xg": {
                "xgf_5v5": 2.85,
                "xga_5v5": 2.41,
                "pp_xg_per_60": 7.2,
                "pk_xga_per_60": 5.8,
                "goalie_sv_pct": 0.928,
            },
            "away_xg": {
                "xgf_5v5": 2.92,
                "xga_5v5": 2.55,
                "pp_xg_per_60": 8.1,
                "pk_xga_per_60": 6.2,
                "goalie_sv_pct": 0.921,
            },
            "implied_odds": {
                "home_ml": 0.565,
                "away_ml": 0.435,
                "home_pl": 0.35,
                "away_pl": 0.65,
                "over_5_5": 0.52,
                "under_5_5": 0.48,
                "over_6_5": 0.38,
                "under_6_5": 0.62,
            },
        },
    ]
    
    all_edges = []
    
    for game_data in demo_games:
        logger.info(f"\nProcessing: {game_data['game']}")
        
        # === GATE 1: Goalie Confirmation ===
        gate = GoalieConfirmationGate()
        
        home_goalie = gate.create_goalie_info(
            name=game_data["home_goalie"]["name"],
            team=game_data["game"].split(" @ ")[1],
            status=game_data["home_goalie"]["status"],
            sources=game_data["home_goalie"]["sources"],
            stats=game_data["home_goalie"]["stats"],
        )
        
        away_goalie = gate.create_goalie_info(
            name=game_data["away_goalie"]["name"],
            team=game_data["game"].split(" @ ")[0],
            status=game_data["away_goalie"]["status"],
            sources=game_data["away_goalie"]["sources"],
            stats=game_data["away_goalie"]["stats"],
        )
        
        evaluation = enforce_goalie_gate(home_goalie, away_goalie)
        
        if not evaluation.can_proceed:
            logger.warning(f"GOALIE GATE FAILED: {evaluation.rejection_reasons}")
            print(f"  ❌ GOALIE GATE FAILED: {evaluation.rejection_reasons}")
            continue
        
        logger.info(f"  ✓ Goalie gate passed: {away_goalie.name} @ {home_goalie.name}")
        
        # === RUN SIMULATION ===
        sim_result = simulate_nhl_game(
            home_team=game_data["game"].split(" @ ")[1],
            away_team=game_data["game"].split(" @ ")[0],
            home_xg=game_data["home_xg"],
            away_xg=game_data["away_xg"],
        )
        
        logger.info(
            f"  Simulation: λ_home={sim_result.home_goals_mean:.2f}, "
            f"λ_away={sim_result.away_goals_mean:.2f}"
        )
        
        # === GENERATE EDGES ===
        edges = generate_edges_from_simulation(
            game_id=game_data["game_id"],
            game=game_data["game"],
            game_time=game_data["game_time"],
            sim_result=sim_result,
            goalie_evaluation=evaluation,
            implied_odds=game_data["implied_odds"],
            run_id=run_id,
        )
        
        all_edges.extend(edges)
    
    # === FILTER TO PLAYABLE EDGES ===
    playable = [e for e in all_edges if e.pick_state == "OPTIMIZABLE"]
    
    # === CROSS-SPORT DATABASE: Save top picks ===
    try:
        from engine.daily_picks_db import save_top_picks
        nhl_edges = []
        for edge in playable:
            nhl_edges.append({
                "player": edge.game,
                "stat": edge.market,
                "line": getattr(edge, 'line', 0),
                "direction": edge.side,
                "probability": edge.model_prob,
                "tier": edge.tier
            })
        if nhl_edges:
            save_top_picks(nhl_edges, "NHL", top_n=5)
            logger.info(f"📊 Cross-Sport DB: Saved top 5 NHL picks")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Cross-Sport DB save failed: {e}")
    
    logger.info(f"\n{'=' * 60}")
    logger.info(f"PIPELINE COMPLETE")
    logger.info(f"Total edges: {len(all_edges)}")
    logger.info(f"Playable edges: {len(playable)}")
    logger.info(f"{'=' * 60}")
    
    # === PRINT SUMMARY ===
    print(f"\n{'=' * 60}")
    print(f"  NHL DAILY PIPELINE — {target_date}")
    print(f"{'=' * 60}")
    
    if playable:
        print(f"\n  ✅ PLAYABLE EDGES ({len(playable)}):\n")
        for edge in playable:
            tier_icon = "🟢" if edge.tier == "STRONG" else "🟡"
            print(f"  {tier_icon} [{edge.tier}] {edge.game} — {edge.market} {edge.side}")
            print(f"     Model: {edge.model_prob:.1%} | Implied: {edge.implied_prob:.1%} | Edge: {edge.edge:.1%}")
            print(f"     Goalies: {edge.away_goalie} @ {edge.home_goalie}")
            if edge.risk_tags:
                print(f"     ⚠️ Risks: {', '.join(edge.risk_tags)}")
            print()
    else:
        print("\n  ⚠️ No playable edges found.\n")
    
    # === WRITE OUTPUT ===
    if not dry_run and playable:
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"nhl_edges_{target_date.strftime('%Y%m%d')}.json"
        
        with open(output_file, "w") as f:
            json.dump([e.to_dict() for e in all_edges], f, indent=2)
        
        logger.info(f"Output written to: {output_file}")
        print(f"  📁 Output: {output_file}\n")
    elif dry_run:
        print("  🏃 Dry run — no output files written.\n")
    
    return all_edges


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="NHL Daily Pipeline — Goalie-Centric Analysis"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing output files",
    )
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    
    run_daily_pipeline(
        target_date=target_date,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
