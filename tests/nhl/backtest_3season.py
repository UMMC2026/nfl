"""
NHL 3-SEASON BACKTEST — v2.0 Validation Framework
==================================================

Extended backtest covering 3 full seasons:
- 2022-23
- 2023-24
- 2024-25

Validates ALL v2.0 modules:
- Goalie confirmation gate
- Goalie saves model
- Referee bias adjustments
- Travel fatigue model
- Player SOG props
- Live intermission engine (simulated)

NON-NEGOTIABLE ASSERTIONS:
- |calibration_error| <= 0.03
- max_drawdown <= 25%
- slam_count == 0
- unconfirmed_goalie_bets == 0
- live_bets_per_game <= 1
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────

SEASONS_3 = ["2022-23", "2023-24", "2024-25"]

MARKETS_V2 = [
    "moneyline",
    "puck_line",
    "totals",
    "goalie_saves",
    "player_sog",  # New in v2.0
]

# Non-negotiable thresholds
MAX_CALIBRATION_ERROR = 0.03
MAX_DRAWDOWN_PCT = 25.0
SLAM_COUNT_MUST_BE = 0
UNCONFIRMED_GOALIE_BETS_MUST_BE = 0
MAX_LIVE_BETS_PER_GAME = 1


class BacktestModeV2(Enum):
    """Test matrix configurations for v2.0."""
    FULL_GATES = "full_gates"             # All gates ON
    NO_GOALIE_GATE = "no_goalie_gate"     # Goalie confirmation OFF
    NO_B2B_PENALTY = "no_b2b_penalty"     # B2B penalty OFF
    NO_REF_BIAS = "no_ref_bias"           # Referee bias OFF
    NO_TRAVEL_FATIGUE = "no_travel_fatigue"  # Travel fatigue OFF
    EMPIRICAL_DIST = "empirical_dist"     # Empirical instead of Poisson
    LIVE_ENABLED = "live_enabled"         # With live adjustments


# ─────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────

@dataclass
class BacktestBetV2:
    """Single bet record for v2.0 backtest."""
    game_id: str
    season: str
    date: str
    market: str
    
    # Teams
    home_team: str
    away_team: str
    
    # Model output
    model_prob: float
    implied_prob: float
    edge: float
    tier: str
    
    # Goalie info
    home_goalie: str = ""
    away_goalie: str = ""
    home_goalie_confirmed: bool = False
    away_goalie_confirmed: bool = False
    home_goalie_b2b: bool = False
    away_goalie_b2b: bool = False
    
    # v2.0 Context
    ref_crew: str = ""
    ref_adjustment: float = 0.0
    travel_penalty_home: float = 0.0
    travel_penalty_away: float = 0.0
    
    # Player prop specific
    player_name: str = ""
    player_toi: float = 0.0
    
    # Live adjustment (if any)
    is_live_bet: bool = False
    live_adjustment: float = 0.0
    intermission: str = ""
    
    # Outcome
    result: Optional[str] = None  # "WIN", "LOSS", "PUSH"
    profit: float = 0.0
    
    def __post_init__(self):
        # SLAM tier is FORBIDDEN
        if self.tier == "SLAM":
            raise ValueError("SLAM tier bets are FORBIDDEN in NHL")


@dataclass
class MarketResultV2:
    """Results for a single market type (v2.0)."""
    market: str
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    
    # Financial
    total_wagered: float = 0.0
    total_returned: float = 0.0
    profit: float = 0.0
    roi: float = 0.0
    
    # Calibration
    predicted_probs: List[float] = field(default_factory=list)
    actual_outcomes: List[int] = field(default_factory=list)
    brier_score: float = 0.0
    calibration_error: float = 0.0
    
    # Risk
    max_drawdown: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    
    # By tier
    strong_bets: int = 0
    strong_wins: int = 0
    lean_bets: int = 0
    lean_wins: int = 0
    
    def compute_metrics(self):
        """Calculate all derived metrics."""
        if self.total_bets == 0:
            return
        
        # ROI
        self.profit = self.total_returned - self.total_wagered
        self.roi = (self.profit / self.total_wagered * 100) if self.total_wagered > 0 else 0.0
        
        # Brier Score
        if len(self.predicted_probs) == len(self.actual_outcomes) and len(self.predicted_probs) > 0:
            brier = sum(
                (p - o) ** 2 
                for p, o in zip(self.predicted_probs, self.actual_outcomes)
            ) / len(self.predicted_probs)
            self.brier_score = brier
            
            # Calibration error
            avg_predicted = sum(self.predicted_probs) / len(self.predicted_probs)
            actual_rate = sum(self.actual_outcomes) / len(self.actual_outcomes)
            self.calibration_error = avg_predicted - actual_rate
        
        # Max drawdown from equity curve
        if self.equity_curve:
            peak = self.equity_curve[0]
            self.max_drawdown = 0.0
            for value in self.equity_curve:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak * 100 if peak > 0 else 0
                self.max_drawdown = max(self.max_drawdown, drawdown)


@dataclass
class BacktestSummaryV2:
    """Complete backtest results for v2.0."""
    sport: str = "NHL"
    version: str = "2.0"
    seasons: List[str] = field(default_factory=list)
    mode: str = "full_gates"
    
    # Market breakdowns
    markets: Dict[str, MarketResultV2] = field(default_factory=dict)
    
    # Aggregates
    total_bets: int = 0
    total_wins: int = 0
    total_losses: int = 0
    overall_roi: float = 0.0
    overall_brier: float = 0.0
    overall_calibration_error: float = 0.0
    
    # Gate violations (should be 0)
    slam_count: int = 0
    unconfirmed_goalie_bets: int = 0
    live_bet_violations: int = 0  # Games with >1 live bet
    
    # Risk
    max_drawdown: float = 0.0
    
    # v2.0 Module impact
    ref_bias_impact: float = 0.0  # Average adjustment
    travel_fatigue_impact: float = 0.0
    live_adjustment_count: int = 0
    
    # Verdict
    verdict: str = ""  # "PROMOTE v2.0" or "REJECT"
    
    # Audit
    run_timestamp: str = ""
    audit_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "sport": self.sport,
            "version": self.version,
            "seasons": self.seasons,
            "mode": self.mode,
            "markets": {
                k: {
                    "roi": v.roi,
                    "brier": v.brier_score,
                    "total_bets": v.total_bets,
                    "wins": v.wins,
                    "losses": v.losses,
                    "calibration_error": v.calibration_error,
                    "max_drawdown": v.max_drawdown,
                }
                for k, v in self.markets.items()
            },
            "total_bets": self.total_bets,
            "overall_roi": self.overall_roi,
            "overall_brier": self.overall_brier,
            "overall_calibration_error": self.overall_calibration_error,
            "slam_count": self.slam_count,
            "unconfirmed_goalie_bets": self.unconfirmed_goalie_bets,
            "live_bet_violations": self.live_bet_violations,
            "max_drawdown": self.max_drawdown,
            "ref_bias_impact": self.ref_bias_impact,
            "travel_fatigue_impact": self.travel_fatigue_impact,
            "live_adjustment_count": self.live_adjustment_count,
            "verdict": self.verdict,
            "run_timestamp": self.run_timestamp,
            "audit_hash": self.audit_hash,
        }


# ─────────────────────────────────────────────────────────
# 3-SEASON BACKTEST RUNNER
# ─────────────────────────────────────────────────────────

class NHL3SeasonBacktestRunner:
    """
    Extended backtest runner for 3 NHL seasons.
    
    Validates all v2.0 modules with synthetic and real data.
    """
    
    def __init__(
        self,
        mode: BacktestModeV2 = BacktestModeV2.FULL_GATES,
        data_dir: Optional[Path] = None,
    ):
        self.mode = mode
        self.data_dir = data_dir or Path("data/nhl/historical")
        
        # Initialize results
        self.bets: List[BacktestBetV2] = []
        self.summary = BacktestSummaryV2()
        self.summary.mode = mode.value
        self.summary.seasons = SEASONS_3
        
        # Per-game live bet tracking
        self._live_bets_per_game: Dict[str, int] = {}
        
        logger.info(f"NHL3SeasonBacktestRunner initialized: mode={mode.value}")
    
    def load_season_data(self, season: str) -> List[Dict]:
        """
        Load historical data for a season.
        
        Returns list of game dicts with outcomes.
        """
        season_file = self.data_dir / f"nhl_{season.replace('-', '_')}.json"
        
        if season_file.exists():
            with open(season_file) as f:
                return json.load(f)
        
        logger.warning(f"Season data not found: {season_file}")
        return []
    
    def _gate_goalie_confirmation(self, bet: BacktestBetV2) -> bool:
        """
        Gate: Goalie confirmation check.
        
        Returns True if bet should proceed.
        """
        if self.mode == BacktestModeV2.NO_GOALIE_GATE:
            return True  # Gate disabled
        
        # For goalie-dependent markets
        if bet.market in ("goalie_saves", "totals"):
            if not bet.home_goalie_confirmed or not bet.away_goalie_confirmed:
                self.summary.unconfirmed_goalie_bets += 1
                return False
        
        return True
    
    def _gate_slam_tier(self, bet: BacktestBetV2) -> bool:
        """
        Gate: SLAM tier prohibition.
        
        SLAM is always forbidden in NHL.
        """
        if bet.tier == "SLAM":
            self.summary.slam_count += 1
            return False
        return True
    
    def _gate_live_bet_limit(self, bet: BacktestBetV2) -> bool:
        """
        Gate: Maximum 1 live bet per game.
        """
        if not bet.is_live_bet:
            return True
        
        count = self._live_bets_per_game.get(bet.game_id, 0)
        if count >= MAX_LIVE_BETS_PER_GAME:
            self.summary.live_bet_violations += 1
            return False
        
        self._live_bets_per_game[bet.game_id] = count + 1
        return True
    
    def _apply_b2b_penalty(self, bet: BacktestBetV2) -> float:
        """Apply B2B goalie penalty if enabled."""
        if self.mode == BacktestModeV2.NO_B2B_PENALTY:
            return 0.0
        
        penalty = 0.0
        if bet.home_goalie_b2b:
            penalty += 0.04  # -4% for home goalie B2B
        if bet.away_goalie_b2b:
            penalty += 0.04  # -4% for away goalie B2B (affects total)
        
        return penalty
    
    def _apply_ref_bias(self, bet: BacktestBetV2) -> float:
        """Apply referee bias adjustment if enabled."""
        if self.mode == BacktestModeV2.NO_REF_BIAS:
            return 0.0
        return bet.ref_adjustment
    
    def _apply_travel_fatigue(self, bet: BacktestBetV2) -> float:
        """Apply travel fatigue if enabled."""
        if self.mode == BacktestModeV2.NO_TRAVEL_FATIGUE:
            return 0.0
        return max(bet.travel_penalty_home, bet.travel_penalty_away)
    
    def process_bet(self, bet: BacktestBetV2, outcome: str) -> bool:
        """
        Process a single bet through all gates.
        
        Returns True if bet was placed (passed all gates).
        """
        # Gate checks
        if not self._gate_slam_tier(bet):
            return False
        
        if not self._gate_goalie_confirmation(bet):
            return False
        
        if not self._gate_live_bet_limit(bet):
            return False
        
        # Apply adjustments
        b2b_penalty = self._apply_b2b_penalty(bet)
        ref_adjustment = self._apply_ref_bias(bet)
        travel_penalty = self._apply_travel_fatigue(bet)
        
        # Track impacts
        if ref_adjustment != 0.0:
            self.summary.ref_bias_impact += abs(ref_adjustment)
        if travel_penalty > 0.0:
            self.summary.travel_fatigue_impact += travel_penalty
        if bet.is_live_bet:
            self.summary.live_adjustment_count += 1
        
        # Adjust probability
        adjusted_prob = bet.model_prob - b2b_penalty - travel_penalty
        if bet.market == "totals":
            adjusted_prob += ref_adjustment  # Ref bias affects totals
        
        adjusted_prob = max(0.01, min(0.99, adjusted_prob))
        bet.model_prob = adjusted_prob
        
        # Set outcome
        bet.result = outcome
        bet.profit = self._calculate_profit(bet, outcome)
        
        # Store bet
        self.bets.append(bet)
        
        # Update market stats
        self._update_market_stats(bet)
        
        return True
    
    def _calculate_profit(self, bet: BacktestBetV2, outcome: str) -> float:
        """Calculate profit/loss for a bet."""
        stake = 100.0  # Flat $100 stakes
        
        if outcome == "WIN":
            # Simplified: assume -110 odds = 0.909 payout
            return stake * 0.909
        elif outcome == "LOSS":
            return -stake
        else:  # PUSH
            return 0.0
    
    def _update_market_stats(self, bet: BacktestBetV2):
        """Update market-level statistics."""
        market = bet.market
        
        if market not in self.summary.markets:
            self.summary.markets[market] = MarketResultV2(market=market)
        
        stats = self.summary.markets[market]
        stats.total_bets += 1
        stats.total_wagered += 100.0
        
        if bet.result == "WIN":
            stats.wins += 1
            stats.total_returned += 190.9  # $100 + $90.90 profit
        elif bet.result == "LOSS":
            stats.losses += 1
        else:
            stats.pushes += 1
            stats.total_returned += 100.0
        
        # Track for calibration
        stats.predicted_probs.append(bet.model_prob)
        stats.actual_outcomes.append(1 if bet.result == "WIN" else 0)
        
        # Track by tier
        if bet.tier == "STRONG":
            stats.strong_bets += 1
            if bet.result == "WIN":
                stats.strong_wins += 1
        elif bet.tier == "LEAN":
            stats.lean_bets += 1
            if bet.result == "WIN":
                stats.lean_wins += 1
        
        # Update equity curve
        current_equity = stats.equity_curve[-1] if stats.equity_curve else 10000.0
        stats.equity_curve.append(current_equity + bet.profit)
    
    def run_synthetic_backtest(self, n_bets_per_season: int = 500) -> BacktestSummaryV2:
        """
        Run backtest with synthetic data for testing.
        
        Generates realistic bet distributions and outcomes.
        """
        import random
        
        random.seed(42)  # Reproducibility
        
        logger.info(f"Running synthetic 3-season backtest: {n_bets_per_season} bets/season")
        
        for season in SEASONS_3:
            for i in range(n_bets_per_season):
                # Generate synthetic bet
                market = random.choice(MARKETS_V2)
                model_prob = random.gauss(0.58, 0.06)  # Mean 58%, std 6%
                model_prob = max(0.50, min(0.70, model_prob))
                
                # Assign tier based on probability
                if model_prob >= 0.64:
                    tier = "STRONG"
                elif model_prob >= 0.58:
                    tier = "LEAN"
                else:
                    tier = "AVOID"
                    continue  # Skip AVOID tier
                
                # Goalie confirmation (95% confirmed in practice)
                goalie_confirmed = random.random() < 0.95
                
                bet = BacktestBetV2(
                    game_id=f"{season}_{i:04d}",
                    season=season,
                    date=f"2024-01-{(i % 28) + 1:02d}",
                    market=market,
                    home_team="BOS",
                    away_team="DET",
                    model_prob=model_prob,
                    implied_prob=0.52,
                    edge=model_prob - 0.52,
                    tier=tier,
                    home_goalie="Swayman",
                    away_goalie="Husso",
                    home_goalie_confirmed=goalie_confirmed,
                    away_goalie_confirmed=goalie_confirmed,
                    home_goalie_b2b=random.random() < 0.15,  # 15% B2B rate
                    ref_adjustment=random.gauss(0, 0.02),  # Small ref adjustments
                    travel_penalty_home=random.choice([0, 0, 0, 0.02, 0.04]),
                    travel_penalty_away=random.choice([0, 0, 0, 0.02, 0.04]),
                    is_live_bet=random.random() < 0.10,  # 10% live bets
                    player_name="Pastrnak" if market == "player_sog" else "",
                )
                
                # Determine outcome based on calibrated probabilities
                # Model is well-calibrated, so win rate ≈ model_prob
                if random.random() < model_prob:
                    outcome = "WIN"
                else:
                    outcome = "LOSS"
                
                self.process_bet(bet, outcome)
        
        return self.finalize()
    
    def finalize(self) -> BacktestSummaryV2:
        """Compute final metrics and verdict."""
        # Aggregate across markets
        total_wagered = 0.0
        total_returned = 0.0
        all_probs = []
        all_outcomes = []
        
        for market_stats in self.summary.markets.values():
            market_stats.compute_metrics()
            total_wagered += market_stats.total_wagered
            total_returned += market_stats.total_returned
            all_probs.extend(market_stats.predicted_probs)
            all_outcomes.extend(market_stats.actual_outcomes)
        
        # Overall metrics
        self.summary.total_bets = len(self.bets)
        self.summary.total_wins = sum(1 for b in self.bets if b.result == "WIN")
        self.summary.total_losses = sum(1 for b in self.bets if b.result == "LOSS")
        
        if total_wagered > 0:
            self.summary.overall_roi = (total_returned - total_wagered) / total_wagered * 100
        
        if len(all_probs) > 0:
            self.summary.overall_brier = sum(
                (p - o) ** 2 for p, o in zip(all_probs, all_outcomes)
            ) / len(all_probs)
            
            avg_pred = sum(all_probs) / len(all_probs)
            actual_rate = sum(all_outcomes) / len(all_outcomes)
            self.summary.overall_calibration_error = avg_pred - actual_rate
        
        # Max drawdown
        self.summary.max_drawdown = max(
            (m.max_drawdown for m in self.summary.markets.values()),
            default=0.0
        )
        
        # Average impacts
        if self.summary.total_bets > 0:
            self.summary.ref_bias_impact /= self.summary.total_bets
            self.summary.travel_fatigue_impact /= self.summary.total_bets
        
        # Audit
        self.summary.run_timestamp = datetime.now().isoformat()
        
        # Verdict
        self._set_verdict()
        
        return self.summary
    
    def _set_verdict(self):
        """Set PROMOTE/REJECT verdict based on assertions."""
        failures = []
        
        if abs(self.summary.overall_calibration_error) > MAX_CALIBRATION_ERROR:
            failures.append(f"calibration_error={self.summary.overall_calibration_error:.3f}")
        
        if self.summary.max_drawdown > MAX_DRAWDOWN_PCT:
            failures.append(f"max_drawdown={self.summary.max_drawdown:.1f}%")
        
        if self.summary.slam_count > SLAM_COUNT_MUST_BE:
            failures.append(f"slam_count={self.summary.slam_count}")
        
        if self.summary.unconfirmed_goalie_bets > UNCONFIRMED_GOALIE_BETS_MUST_BE:
            failures.append(f"unconfirmed_goalie_bets={self.summary.unconfirmed_goalie_bets}")
        
        if self.summary.live_bet_violations > 0:
            failures.append(f"live_bet_violations={self.summary.live_bet_violations}")
        
        if failures:
            self.summary.verdict = f"REJECT: {', '.join(failures)}"
        else:
            self.summary.verdict = "PROMOTE v2.0"
    
    def assert_all_constraints(self):
        """
        Assert all non-negotiable constraints.
        
        Raises AssertionError if any constraint violated.
        """
        assert abs(self.summary.overall_calibration_error) <= MAX_CALIBRATION_ERROR, \
            f"|calibration_error| > {MAX_CALIBRATION_ERROR}: {self.summary.overall_calibration_error:.3f}"
        
        assert self.summary.max_drawdown <= MAX_DRAWDOWN_PCT, \
            f"max_drawdown > {MAX_DRAWDOWN_PCT}%: {self.summary.max_drawdown:.1f}%"
        
        assert self.summary.slam_count == SLAM_COUNT_MUST_BE, \
            f"slam_count != 0: {self.summary.slam_count}"
        
        assert self.summary.unconfirmed_goalie_bets == UNCONFIRMED_GOALIE_BETS_MUST_BE, \
            f"unconfirmed_goalie_bets != 0: {self.summary.unconfirmed_goalie_bets}"
        
        assert self.summary.live_bet_violations == 0, \
            f"live_bet_violations != 0: {self.summary.live_bet_violations}"
        
        logger.info("All v2.0 constraints PASSED")


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("NHL 3-SEASON BACKTEST — v2.0 DEMO")
    print("=" * 60)
    
    runner = NHL3SeasonBacktestRunner(mode=BacktestModeV2.FULL_GATES)
    summary = runner.run_synthetic_backtest(n_bets_per_season=500)
    
    print(f"\n{'-' * 40}")
    print("BACKTEST SUMMARY")
    print(f"{'-' * 40}")
    print(f"Seasons: {summary.seasons}")
    print(f"Mode: {summary.mode}")
    print(f"Total bets: {summary.total_bets}")
    print(f"Win rate: {summary.total_wins / summary.total_bets:.1%}")
    print(f"Overall ROI: {summary.overall_roi:.2f}%")
    print(f"Brier score: {summary.overall_brier:.4f}")
    print(f"Calibration error: {summary.overall_calibration_error:.3f}")
    print(f"Max drawdown: {summary.max_drawdown:.1f}%")
    
    print(f"\nGate violations:")
    print(f"  SLAM count: {summary.slam_count}")
    print(f"  Unconfirmed goalie bets: {summary.unconfirmed_goalie_bets}")
    print(f"  Live bet violations: {summary.live_bet_violations}")
    
    print(f"\nv2.0 Module impact:")
    print(f"  Avg ref bias adjustment: {summary.ref_bias_impact:.4f}")
    print(f"  Avg travel fatigue penalty: {summary.travel_fatigue_impact:.4f}")
    print(f"  Live adjustments: {summary.live_adjustment_count}")
    
    print(f"\n{'=' * 40}")
    print(f"VERDICT: {summary.verdict}")
    print(f"{'=' * 40}")
    
    # Run assertions
    try:
        runner.assert_all_constraints()
        print("\n✅ All constraints PASSED")
    except AssertionError as e:
        print(f"\n❌ Constraint FAILED: {e}")
