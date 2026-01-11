"""
Daily Pipeline Orchestrator

One-command script to run the complete daily analysis:
1. Load picks.json (user provides fresh lines)
2. Hydrate with NBA API data
3. Apply governance layer (stat classification, regime gating)
4. Apply confidence calibration
5. Add context flags
6. Tag correlations and apply correlation penalties
7. Generate comprehensive cheat sheet
8. Save picks for tracking

Usage:
    python -m ufa.daily_pipeline --picks picks.json --output outputs/
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import sys

# Our modules
from ufa.analysis.calibration import ConfidenceCalibrator, ConfidenceTier
from ufa.analysis.context import ContextProvider, format_context_flags
from ufa.analysis.correlation import CorrelationTagger
from ufa.analysis.results_tracker import ResultsTracker, TrackedPick
from ufa.analysis.prob import STAT_CLASS, correlation_penalty
from ufa.optimizer.ticket_governor import TicketGovernor, VerdictType
from ufa.prior.nfl_structural_priors import compute_prior


# ============================================================================
# SAFETY & RECONCILIATION FUNCTIONS
# ============================================================================

def reconcile_picks(all_picks: list, results_lookup: dict) -> tuple:
    """
    Separate resolved picks from pending picks.
    
    Args:
        all_picks: List of pick dicts
        results_lookup: Dict keyed by (date, player, stat) → result info
    
    Returns:
        (resolved_picks, pending_picks)
    """
    resolved = []
    pending = []

    for pick in all_picks:
        key = (pick.get('date'), pick.get('player'), pick.get('stat'))
        outcome = results_lookup.get(key)

        if outcome is None:
            pending.append(pick)
        else:
            pick_copy = pick.copy()
            pick_copy['result'] = outcome['result']
            pick_copy['actual_value'] = outcome['actual_value']
            resolved.append(pick_copy)

    return resolved, pending


def compute_performance_metrics(resolved_picks: list) -> dict:
    """
    Compute performance metrics from resolved picks only.
    
    Safe: Returns 0-valued metrics if no resolved picks exist.
    """
    wins = sum(1 for p in resolved_picks if p.get('result') == 'HIT')
    losses = sum(1 for p in resolved_picks if p.get('result') == 'MISS')
    pushes = sum(1 for p in resolved_picks if p.get('result') == 'PUSH')

    total_decided = wins + losses

    roi = (
        sum(p.get('payout', 1.0) for p in resolved_picks if p.get('result') == 'HIT')
        - sum(p.get('stake', 1.0) for p in resolved_picks if p.get('result') == 'MISS')
    )

    return {
        'wins': wins,
        'losses': losses,
        'pushes': pushes,
        'resolved': len(resolved_picks),
        'win_rate': round(wins / total_decided, 3) if total_decided > 0 else None,
        'roi': round(roi, 2),
    }


def is_yesterday_game(pick: dict) -> bool:
    """
    Check if a pick's game was yesterday (using game end time, not pick date).
    Safe fallback: uses pick['date'] if game_end_time unavailable.
    """
    yesterday = (datetime.utcnow().date() - timedelta(days=1))

    # Prefer game_end_time if available
    if 'game_end_time' in pick and pick['game_end_time']:
        try:
            end_time = datetime.fromisoformat(pick['game_end_time'])
            return end_time.date() == yesterday
        except (ValueError, TypeError):
            pass

    # Fallback to pick['date']
    if 'date' in pick and pick['date']:
        try:
            pick_date = datetime.strptime(pick['date'], '%Y-%m-%d').date()
            return pick_date == yesterday
        except ValueError:
            pass

    return False


def validate_metrics_state(metrics: dict, resolved_count: int) -> None:
    """
    Enforce impossible state guard: prevents "0–0 with resolved picks".
    Raises RuntimeError if state is invalid.
    """
    if resolved_count > 0:
        if metrics['wins'] == 0 and metrics['losses'] == 0:
            raise RuntimeError(
                f"Invalid state: {resolved_count} resolved picks but "
                f"metrics show 0 wins and 0 losses. "
                f"Possible causes: result field corrupted, or all picks are PUSH."
            )


def print_data_status(metrics: dict, pending_count: int) -> None:
    """Print DATA STATUS telemetry (audit trail)."""
    print("\n" + "=" * 60)
    print("⚙️  DATA STATUS")
    print("=" * 60)
    print(f"  Resolved picks: {metrics['resolved']}")
    print(f"  Pending picks: {pending_count}")
    if metrics['resolved'] > 0:
        print(f"  Win rate: {metrics['wins']}/{metrics['wins']+metrics['losses']} "
              f"({metrics['win_rate']*100:.1f}%)")
        print(f"  ROI: {metrics['roi']:+.2f} units")
    print(f"  Last reconciliation: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60 + "\n")


class DailyPipeline:
    """
    Orchestrates the complete daily analysis workflow.
    """
    
    def __init__(
        self,
        picks_file: str = "picks_hydrated.json",
        output_dir: str = "outputs",
        roster_file: str = None
    ):
        self.picks_file = Path(picks_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.roster_file = roster_file
        
        # Initialize modules
        self.calibrator = ConfidenceCalibrator()
        self.context_provider = ContextProvider()
        self.correlation_tagger = CorrelationTagger()
        self.results_tracker = ResultsTracker()
        self.ticket_governor = TicketGovernor()  # Phase C-1 exposure governor
        
        self.picks = []
        self.calibrated_picks = []
        self.today = datetime.now().strftime("%Y-%m-%d")
    
    def load_picks(self) -> list[dict]:
        """Load picks from JSON file."""
        if not self.picks_file.exists():
            print(f"❌ Picks file not found: {self.picks_file}")
            return []
        
        with open(self.picks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both list and dict formats
        if isinstance(data, list):
            self.picks = data
        elif isinstance(data, dict) and "picks" in data:
            self.picks = data["picks"]
        else:
            self.picks = [data]
        
        print(f"✅ Loaded {len(self.picks)} picks from {self.picks_file}")
        return self.picks
    
    def calculate_probability(self, pick: dict) -> float:
        """Calculate hit probability using normal approximation."""
        from scipy.stats import norm
        
        mu = pick.get("mu")
        sigma = pick.get("sigma")
        line = pick.get("line")
        direction = pick.get("direction", "higher")
        
        if mu is None or sigma is None or sigma <= 0:
            return 0.50  # Default when no data
        
        if direction == "higher":
            return 1 - norm.cdf(line, mu, sigma)
        else:
            return norm.cdf(line, mu, sigma)
    
    def _format_adjustments(self, calibrated) -> list[str]:
        """Format adjustment notes for display."""
        adjustments = []
        
        if calibrated.shrinkage_applied > 0.01:
            adjustments.append(f"shrinkage -{calibrated.shrinkage_applied:.0%}")
        
        if calibrated.streak_penalty_applied > 0.01:
            adjustments.append(f"{calibrated.recent_trend} streak -{calibrated.streak_penalty_applied:.0%}")
        
        if calibrated.volatility_penalty_applied > 0.01:
            adjustments.append(f"volatility -{calibrated.volatility_penalty_applied:.0%}")
        
        if calibrated.sample_penalty_applied > 0.01:
            adjustments.append(f"sample size -{calibrated.sample_penalty_applied:.0%}")
        
        return adjustments

    def process_picks(self):
        """Process all picks through calibration, context, and correlation."""
        if not self.picks:
            self.load_picks()
        
        processed = []
        
        for pick in self.picks:
            # Ensure hydration: populate recent_values/mu/sigma for NFL picks when missing
            try:
                from ufa.ingest.hydrate import hydrate_recent_values
                from engine.stat_derivation import COMPOSITE_MAP
            except Exception:
                hydrate_recent_values = None
                COMPOSITE_MAP = {}

            if not pick.get('mu') and not pick.get('sigma') and not pick.get('recent_values'):
                league = pick.get('sport', 'NFL')
                player = pick.get('player')
                stat = pick.get('stat')
                team = pick.get('team')
                try:
                    if hydrate_recent_values:
                        seasons = [datetime.now().year - 1]
                        rv = hydrate_recent_values(league, player, stat, team=team, nfl_seasons=seasons, last_n=10)
                    else:
                        rv = []
                except Exception:
                    rv = []

                # If composite stat, attempt to derive from components
                if rv is None:
                    # Composite stat: derive by aggregating atomic component series
                    comps = COMPOSITE_MAP.get(stat, [])
                    comp_series = []
                    for c in comps:
                        try:
                            comp_vals = hydrate_recent_values(league, player, c, team=team, nfl_seasons=seasons, last_n=10)
                        except Exception:
                            comp_vals = []
                        comp_series.append(comp_vals or [])
                    # Sum component series element-wise where possible
                    if comp_series and any(comp_series):
                        length = max(len(s) for s in comp_series)
                        summed = []
                        for i in range(length):
                            s = 0
                            for comp in comp_series:
                                if i < len(comp):
                                    s += comp[i]
                            summed.append(s)
                        rv = summed

                if rv:
                    # compute mu/sigma
                    import math
                    vals = [v for v in rv if v is not None]
                    if vals:
                        mu = sum(vals) / len(vals)
                        if len(vals) > 1:
                            var = sum((x - mu) ** 2 for x in vals) / (len(vals) - 1)
                            sigma = math.sqrt(var)
                        else:
                            sigma = 0.0
                        # Ensure non-zero sigma for downstream probability calc
                        if sigma <= 0:
                            # Heuristic fallback by stat type:
                            # - For count-like stats (tds, attempts, receptions, sacks): use Poisson-like std ~ sqrt(mu) with slight overdispersion
                            # - For yardage/continuous stats: use a fraction of mu
                            stat = str(pick.get('stat', '')).lower()
                            count_indicators = ['td', 'attempt', 'recept', 'sack', 'fg_made', 'kicking_points']
                            yard_indicators = ['yard', 'yd']

                            try:
                                if any(k in stat for k in count_indicators):
                                    # Poisson-like variance: sigma ~ sqrt(mu); add 20% overdispersion
                                    sigma = max(0.5, (abs(mu) ** 0.5) * 1.2)
                                elif any(k in stat for k in yard_indicators):
                                    # Yardage: more continuous; use 20% of mu as proxy
                                    sigma = max(1.0, abs(mu) * 0.20)
                                else:
                                    # Fallback generic: 15% of mu
                                    sigma = max(0.5, abs(mu) * 0.15)
                            except Exception:
                                sigma = max(0.5, abs(mu) * 0.15)
                        pick['recent_values'] = vals
                        pick['mu'] = mu
                        pick['sigma'] = sigma
                else:
                    # No recent values available after hydration/derivation.
                    # Apply conservative league-average fallback so downstream
                    # calibration has sensible mu/sigma instead of defaulting to 0.5.
                    try:
                        line_val = float(pick.get('line', 0) or 0)
                    except Exception:
                        line_val = 0.0

                    # Conservative bias under market line to avoid degenerate 0.5
                    mu = max(0.0, 0.95 * line_val)

                    # Stat-type-aware sigma heuristics (same reasoning as above)
                    stat = str(pick.get('stat', '')).lower()
                    count_indicators = ['td', 'attempt', 'recept', 'sack', 'fg_made', 'kicking_points']
                    yard_indicators = ['yard', 'yd']

                    try:
                        if any(k in stat for k in count_indicators):
                            sigma = max(0.5, (abs(mu) ** 0.5) * 1.2)
                        elif any(k in stat for k in yard_indicators):
                            sigma = max(1.0, abs(mu) * 0.20)
                        else:
                            sigma = max(0.5, abs(mu) * 0.15)
                    except Exception:
                        sigma = max(0.5, abs(mu) * 0.15)

                    # Persist fallback to pick for transparency and downstream uses
                    pick['recent_values'] = []
                    pick['mu'] = mu
                    pick['sigma'] = sigma

            # Get context (needed for structural prior computation)
            context = self.context_provider.get_context(
                player=pick.get("player", "Unknown"),
                team=pick.get("team", "UNK"),
                opponent=pick.get("opponent", "UNK"),
                stat=pick.get("stat", "points")
            )

            # Structural prior (ALWAYS ON): compute a conservative prior belief based on
            # context. This is used when empirical recent_values are unavailable so we
            # do inference instead of collapsing to a flat baseline.
            try:
                prior_prob, prior_mu, prior_sigma = compute_prior(pick, context)
            except Exception:
                prior_prob, prior_mu, prior_sigma = (None, None, None)

            # Calculate raw probability
            # If no empirical mu/sigma (no recent_values), use prior as raw_prob and
            # persist prior mu/sigma; mark pick as prior_only so downstream steps can
            # treat it differently (e.g., tier labeling).
            if (not pick.get('recent_values') or len(pick.get('recent_values', [])) == 0) and prior_prob is not None:
                raw_prob = prior_prob
                # Persist conservative mu/sigma for downstream components
                pick.setdefault('mu', prior_mu)
                pick.setdefault('sigma', prior_sigma)
                pick['prior_only'] = True
            else:
                raw_prob = self.calculate_probability(pick)
            
            # Apply calibration
            calibrated = self.calibrator.calibrate(
                player=pick.get("player", "Unknown"),
                team=pick.get("team", "UNK"),
                stat=pick.get("stat", "unknown"),
                line=pick.get("line", 0),
                direction=pick.get("direction", "higher"),
                raw_prob=raw_prob,
                mu=pick.get("mu"),
                sigma=pick.get("sigma"),
                recent_values=pick.get("recent_values", []),
                career_avg=pick.get("career_avg"),
                prior_prob=prior_prob,
                prior_mu=prior_mu,
                prior_sigma=prior_sigma,
            )
            
            # Tag stat class (governance layer)
            stat_name = pick.get("stat", "unknown").lower()
            stat_class = STAT_CLASS.get(stat_name, "core")
            
            # Build processed pick
            processed_pick = {
                **pick,
                "raw_prob": raw_prob,
                "calibrated_prob": calibrated.calibrated_probability,
                "display_prob": calibrated.display_probability,
                "tier": calibrated.tier.value,
                "stat_class": stat_class,
                "adjustments": self._format_adjustments(calibrated),
                "context": {
                    "minutes_tier": context.minutes_tier.value if context.minutes_tier else "Unknown",
                    "rest": context.rest_status.value if context.rest_status else "Unknown",
                    "usage": context.usage_context.value if context.usage_context else "0",
                    "matchup": context.matchup_rank.value if context.matchup_rank else "Unknown",
                    "formatted": format_context_flags(context)
                }
            }

            # If this pick used prior-only mode (no recent_values), prefer a LEAN (PRIOR)
            # label so we don't treat it as a blind FLIP. This preserves rank ordering
            # while signaling lower empirical confidence.
            if pick.get("prior_only"):
                processed_pick["tier"] = "LEAN (PRIOR)"
            
            processed.append(processed_pick)
        
        # Sort by calibrated probability
        processed.sort(key=lambda x: x["calibrated_prob"], reverse=True)
        
        # Add correlation badges
        badges = self.correlation_tagger.format_correlation_badges(processed)
        for p in processed:
            key = f"{p['player']}|{p['stat']}"
            p["correlation_badges"] = badges.get(key, [])
        
        # Auto-demote correlated SLAMs (only one SLAM per player allowed)
        processed = self._demote_correlated_slams(processed)
        
        self.calibrated_picks = processed
        print(f"✅ Processed {len(processed)} picks through calibration pipeline")
        
        return processed
    
    def _demote_correlated_slams(self, picks: list[dict]) -> list[dict]:
        """
        Auto-demote correlated picks from SLAM tier.
        Rule: Only one SLAM per player; if player has multiple, keep highest prob as SLAM.
        """
        from ufa.analysis.calibration import ConfidenceTier
        
        # Group SLAM picks by player
        slam_by_player = {}
        for p in picks:
            if p["tier"] == "SLAM":
                player = p["player"]
                if player not in slam_by_player:
                    slam_by_player[player] = []
                slam_by_player[player].append(p)
        
        # For players with multiple SLAMs, demote all but the highest
        demoted_count = 0
        for player, player_slams in slam_by_player.items():
            if len(player_slams) > 1:
                # Sort by probability, keep only the best as SLAM
                player_slams.sort(key=lambda x: x["calibrated_prob"], reverse=True)
                for p in player_slams[1:]:  # All but the first
                    p["tier"] = "STRONG"
                    p["adjustments"].append("🔗 demoted (correlated)")
                    demoted_count += 1
        
        if demoted_count > 0:
            print(f"  📉 Demoted {demoted_count} correlated SLAMs to STRONG")
        
        return picks

    def generate_cheat_sheet(self) -> str:
        """Generate the comprehensive cheat sheet."""
        from ufa.ingest.reconciliation_loader import ReconciliationLoader
        
        if not self.calibrated_picks:
            self.process_picks()
        
        # Load reconciliation results (if CSV exists)
        loader = ReconciliationLoader()
        results_lookup = {}
        
        try:
            for result in loader.load_csv():
                key = (result['date'], result['player'], result['stat'])
                results_lookup[key] = result
        except FileNotFoundError:
            # CSV doesn't exist yet (OK on first run)
            pass
        
        # Separate resolved / pending
        resolved, pending = reconcile_picks(self.calibrated_picks, results_lookup)
        metrics = compute_performance_metrics(resolved)
        
        # Safety check
        validate_metrics_state(metrics, len(resolved))
        
        # Audit trail
        print_data_status(metrics, len(pending))
        
        lines = []
        timestamp = datetime.now().strftime("%B %d, %Y %I:%M %p")
        
        # Header
        lines.append("=" * 70)
        lines.append(f"🏀 UNDERDOG FANTASY CHEAT SHEET - {timestamp}")
        lines.append("=" * 70)
        lines.append("⚙️  GOVERNANCE LAYER ACTIVE: Stat classification, regime gating, confidence caps")
        lines.append("   Core props: 75% ceiling | Alt-stats: 68% ceiling | Event: 55% ceiling")
        lines.append("=" * 70)
        lines.append("")
        
        # Yesterday's performance
        lines.append(self.results_tracker.format_yesterday_block())
        
        # 7-day rolling
        lines.append(self.results_tracker.format_rolling_block(7))
        
        # Tier breakdown
        slam = [p for p in self.calibrated_picks if p["tier"] == "SLAM"]
        strong = [p for p in self.calibrated_picks if p["tier"] == "STRONG"]
        lean = [p for p in self.calibrated_picks if p["tier"] == "LEAN"]
        flip = [p for p in self.calibrated_picks if p["tier"] == "FLIP"]
        fade = [p for p in self.calibrated_picks if p["tier"] == "FADE"]
        
        # SLAM plays
        if slam:
            lines.append("🎯 SLAM PLAYS (68-75% Confidence)")
            lines.append("=" * 70)
            for p in slam[:5]:
                lines.append(self._format_pick_line(p))
            lines.append("")
        
        # STRONG plays
        if strong:
            lines.append("💪 STRONG PLAYS (60-67% Confidence)")
            lines.append("=" * 70)
            for p in strong[:8]:
                lines.append(self._format_pick_line(p))
            lines.append("")
        
        # LEAN plays
        if lean:
            lines.append("👍 LEAN PLAYS (52-59% Confidence)")
            lines.append("=" * 70)
            for p in lean[:6]:
                lines.append(self._format_pick_line(p))
            lines.append("")
        
        # Top Overs
        overs = [p for p in self.calibrated_picks 
                 if p["direction"] == "higher" and p["tier"] in ["SLAM", "STRONG", "LEAN"]]
        if overs:
            lines.append("⬆️ TOP OVERS")
            lines.append("-" * 70)
            for p in overs[:5]:
                prob_pct = p["display_prob"] * 100
                lines.append(f"  {p['player']} O {p['line']} {p['stat']} ({prob_pct:.0f}%)")
            lines.append("")
        
        # Top Unders
        unders = [p for p in self.calibrated_picks 
                  if p["direction"] == "lower" and p["tier"] in ["SLAM", "STRONG", "LEAN"]]
        if unders:
            lines.append("⬇️ TOP UNDERS")
            lines.append("-" * 70)
            for p in unders[:5]:
                prob_pct = p["display_prob"] * 100
                lines.append(f"  {p['player']} U {p['line']} {p['stat']} ({prob_pct:.0f}%)")
            lines.append("")
        
        # Parlay suggestions
        lines.append(self._generate_parlay_section())
        
        # Correlation warnings
        lines.append(self._generate_correlation_warnings())
        
        # Avoid list
        if fade:
            lines.append("🚫 AVOID LIST (Fade these)")
            lines.append("-" * 70)
            for p in fade[:5]:
                prob_pct = p["display_prob"] * 100
                dir_symbol = "O" if p["direction"] == "higher" else "U"
                lines.append(f"  {p['player']} {dir_symbol} {p['line']} {p['stat']} ({prob_pct:.0f}%)")
            lines.append("")
        
        # Legend
        lines.append("📚 LEGEND")
        lines.append("-" * 70)
        lines.append("  Tiers: SLAM (68-75%) | STRONG (60-67%) | LEAN (52-59%)")
        lines.append("  Context: Min:XX-XX | Rest:Xd | Usage:+/0/- | vs X-X")
        lines.append("  Correlation: 🔗 High | ⚠️ Moderate | ↔️ Hedge")
        lines.append("")
        lines.append("  ⚠️  DISCLAIMER: These are probabilistic estimates, not guarantees.")
        lines.append("      Calibrated confidence accounts for regression and variance.")
        lines.append("")
        
        return "\n".join(lines)
    
    def _format_pick_line(self, pick: dict) -> str:
        """Format a single pick line with all details."""
        dir_symbol = "O" if pick["direction"] == "higher" else "U"
        prob_pct = pick["display_prob"] * 100
        
        # Build badges
        badges = " ".join(pick.get("correlation_badges", []))
        if badges:
            badges = f" {badges}"
        
        # Context flags
        context_str = pick.get("context", {}).get("formatted", "")
        if context_str:
            context_str = f"  [{context_str}]"
        
        # Adjustments
        adjustments = pick.get("adjustments", [])
        adj_str = ""
        if adjustments:
            adj_str = f"  ({', '.join(adjustments[:2])})"
        
        line = f"  {pick['player']} ({pick['team']}) {dir_symbol} {pick['line']} {pick['stat']}"
        line += f" - {prob_pct:.0f}%{badges}{context_str}{adj_str}"
        
        return line
    
    def _generate_parlay_section(self) -> str:
        """Generate parlay suggestions with ticket-level exposure governance (Phase C-1)."""
        lines = ["🎲 PARLAY SUGGESTIONS", "-" * 70]
        
        # Get top picks from different teams
        slam_strong = [p for p in self.calibrated_picks if p["tier"] in ["SLAM", "STRONG"]]
        
        if len(slam_strong) < 3:
            lines.append("  Not enough high-confidence picks for parlays")
            lines.append("")
            return "\n".join(lines)
        
        # Build 3-leg parlay with different teams
        teams_used = set()
        parlay_picks = []
        
        for p in slam_strong:
            if p["team"] not in teams_used and len(parlay_picks) < 3:
                parlay_picks.append(p)
                teams_used.add(p["team"])
        
        if len(parlay_picks) >= 3:
            # Phase C-1: Ticket governance
            ticket_verdict = self.ticket_governor.evaluate_ticket(parlay_picks)
            
            # Check correlations
            penalty, warnings = self.correlation_tagger.get_parlay_penalty(parlay_picks)
            penalty_mult = max(0.5, 1.0 - penalty)  # Cap penalty at 50%
            
            # Apply stat-class correlation penalty (governance layer)
            stat_classes = [p.get("stat_class", "core") for p in parlay_picks]
            stat_class_penalty = correlation_penalty(stat_classes)
            
            # Calculate combined probability
            combined_prob = 1.0
            for p in parlay_picks:
                combined_prob *= p["calibrated_prob"]
            
            # Apply ticket governor penalty
            combined_prob *= penalty_mult * stat_class_penalty * ticket_verdict.penalty_mult
            
            # Handle blocked tickets
            if ticket_verdict.verdict == VerdictType.BLOCKED:
                lines.append(f"  ❌ {ticket_verdict.message}")
                if ticket_verdict.warnings:
                    lines.append(f"     Reason: {'; '.join(ticket_verdict.warnings)}")
                lines.append("")
                return "\n".join(lines)
            
            # Underdog 3-leg power play payout is 6x (implied ~16.7% breakeven)
            implied_breakeven = 1 / 6.0  # ~16.67%
            edge_pct = (combined_prob - implied_breakeven) / implied_breakeven * 100
            
            lines.append("  3-Leg Power Play:")
            for p in parlay_picks:
                dir_sym = "O" if p["direction"] == "higher" else "U"
                stat_class_label = f"[{p.get('stat_class', 'core')}]" if p.get("stat_class") != "core" else ""
                lines.append(f"    • {p['player']} {dir_sym} {p['line']} {p['stat']} ({p['display_prob']*100:.0f}%) {stat_class_label}")
            
            lines.append(f"  Combined probability: {combined_prob*100:.1f}%")
            lines.append(f"  Payout: 6x | Breakeven: 16.7% | Edge: {'+' if edge_pct > 0 else ''}{edge_pct:.1f}%")
            
            # Show governance verdict
            if ticket_verdict.verdict == VerdictType.DOWNGRADED:
                lines.append(f"  ⬇️  {ticket_verdict.message}")
            elif ticket_verdict.verdict == VerdictType.APPROVED_WITH_PENALTY:
                lines.append(f"  ⚠️  {ticket_verdict.message}")
                if ticket_verdict.warnings:
                    for w in ticket_verdict.warnings:
                        lines.append(f"     - {w}")
            
            if stat_class_penalty < 1.0 and ticket_verdict.penalty_mult >= 1.0:
                lines.append(f"  ⚠️  Stat-class penalty: {(1-stat_class_penalty)*100:.0f}%")
            
            if warnings:
                lines.append(f"  ⚠️  Correlation warnings: {', '.join(warnings)}")
        
        lines.append("")
        return "\n".join(lines)
    
    def _generate_correlation_warnings(self) -> str:
        """Generate correlation warnings section."""
        lines = ["⚠️  CORRELATION WARNINGS", "-" * 70]
        
        tags = self.correlation_tagger.tag_correlations(self.calibrated_picks)
        
        high_corr = [t for t in tags if t.level.value == "🔗"]
        mod_corr = [t for t in tags if t.level.value == "⚠️"]
        
        if not high_corr and not mod_corr:
            lines.append("  No significant correlations detected")
            lines.append("")
            return "\n".join(lines)
        
        if high_corr:
            lines.append("  🔗 HIGHLY CORRELATED (avoid stacking):")
            for t in high_corr[:5]:
                lines.append(f"    • {t.reason}")
        
        if mod_corr:
            lines.append("  ⚠️  MODERATELY CORRELATED:")
            for t in mod_corr[:5]:
                lines.append(f"    • {t.reason}")
        
        lines.append("")
        return "\n".join(lines)
    
    def save_cheat_sheet(self, content: str = None) -> str:
        """Save cheat sheet to output file."""
        if content is None:
            content = self.generate_cheat_sheet()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_str = datetime.now().strftime("%b%d").upper()
        filename = f"CHEATSHEET_{date_str}_{timestamp}.txt"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Saved cheat sheet to {filepath}")
        return str(filepath)
    
    def save_for_tracking(self):
        """Save today's picks for result tracking."""
        if not self.calibrated_picks:
            self.process_picks()
        
        tracked = []
        for p in self.calibrated_picks:
            if p["tier"] in ["SLAM", "STRONG", "LEAN"]:  # Only track confident picks
                tracked.append(TrackedPick(
                    date=self.today,
                    player=p["player"],
                    team=p["team"],
                    stat=p["stat"],
                    line=p["line"],
                    direction=p["direction"],
                    tier=p["tier"],
                    confidence=p["display_prob"],
                    result="PENDING"
                ))
        
        if tracked:
            self.results_tracker.save_picks(tracked, self.today)
            print(f"✅ Saved {len(tracked)} picks for tracking")
    
    def run(self) -> str:
        """Run the complete pipeline."""
        print("\n" + "=" * 50)
        print("🚀 DAILY PIPELINE STARTING")
        print("=" * 50 + "\n")
        
        # Load and process
        self.load_picks()
        self.process_picks()
        
        # Generate and save cheat sheet
        content = self.generate_cheat_sheet()
        filepath = self.save_cheat_sheet(content)
        
        # Save for tracking
        self.save_for_tracking()
        
        print("\n" + "=" * 50)
        print("✅ PIPELINE COMPLETE")
        print("=" * 50 + "\n")
        
        return filepath


def main():
    parser = argparse.ArgumentParser(description="Run daily analysis pipeline")
    parser.add_argument("--picks", default="picks_hydrated.json", help="Path to picks JSON file")
    parser.add_argument("--output", default="outputs", help="Output directory")
    parser.add_argument("--roster", default=None, help="Path to roster CSV file")
    parser.add_argument("--print", action="store_true", help="Print cheat sheet to console")
    
    args = parser.parse_args()
    
    pipeline = DailyPipeline(
        picks_file=args.picks,
        output_dir=args.output,
        roster_file=args.roster
    )
    
    filepath = pipeline.run()
    
    if args.print:
        with open(filepath, 'r', encoding='utf-8') as f:
            print(f.read())


if __name__ == "__main__":
    main()
