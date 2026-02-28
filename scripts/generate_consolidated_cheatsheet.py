"""
CONSOLIDATED CHEAT SHEET GENERATOR
Cross-Sport Unified Report with Clear OVER/UNDER Probabilities
NBA | Tennis | CBB | NFL | Golf

GOVERNANCE: Uses config/thresholds.py for tier assignment (single source of truth).
"""
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.thresholds import implied_tier, get_all_thresholds, validate_tier_consistency
from calibration.unified_tracker import UnifiedCalibration


def _configure_stdout_for_windows() -> None:
    """Best-effort: avoid UnicodeEncodeError on Windows consoles (cp1252).

    We keep file outputs in UTF-8 already; this only protects console printing.
    """

    try:
        # Python 3.7+: TextIOWrapper supports reconfigure
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Never fail cheat sheet generation due to console capabilities.
        pass

class ConsolidatedCheatSheet:
    """Generate clean, consolidated cheat sheets with clear OVER/UNDER probabilities"""
    
    TIER_ICONS = {
        "SLAM": "[SLAM]",
        "STRONG": "[STRONG]", 
        "LEAN": "[LEAN]",
        "FLIP": "[FLIP]",
        "FADE": "[FADE]",
        "AVOID": "[AVOID]"
    }
    
    # Kelly Criterion settings (Phase 5A integration)
    KELLY_FRACTION = 0.25  # Conservative fractional Kelly
    DEFAULT_ODDS = 1.91    # Standard -110 odds
    
    def __init__(
        self,
        edges: List[Dict],
        sport: str = "NBA",
        bankroll: float = 1000.0,
        unicode_output: bool = False,
    ):
        self.edges = edges
        self.sport = sport.upper()
        self.bankroll = bankroll
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.unicode_output = bool(unicode_output)
        self.tier_corrections = 0
        self.duplicates_removed = 0
        self.market_conflicts_removed = 0
        self.market_conflict_warnings: List[str] = []
        self.correlation_warnings = []
        # Optional: per-player stat averages (PTS/REB/AST/3PM) from latest cache
        self.player_stat_avgs: Dict[str, Dict[str, float]] = {}
        
        # Normalize edge fields across sports (CBB uses player/stat, NBA uses entity/market)
        self._normalize_edge_fields()
        
        # Validate and correct edges on init
        self._validate_and_correct_edges()
        self._detect_duplicates()
        self._consolidate_player_market_conflicts()
        self._detect_correlations()
        # Best-effort load of stat averages (NBA only)
        if self.sport == "NBA":
            self._load_player_stat_avgs()

    def _get_calibration_status_line(self) -> Optional[str]:
        """Return a compact one-line calibration status for quick reference.

        Uses UnifiedCalibration but never raises; returns None if calibration
        data is missing or unavailable for this sport.
        """
        try:
            calib = UnifiedCalibration()
        except Exception:
            return None

        sport_key = self.sport.lower()
        if not calib.picks:
            return None

        sport_picks = [p for p in calib.picks if p.sport == sport_key and p.brier is not None]
        if not sport_picks:
            return None

        try:
            brier = calib.get_sport_brier(sport_key)
            threshold = calib.BRIER_THRESHOLDS.get(sport_key, 0.25)
            flags = calib.check_drift_flags(sport_key)
        except Exception:
            return None

        needs_recal = flags.get("requires_recalibration")
        status = "WARN" if needs_recal else "OK"
        return f"[{status}] Calib Brier {brier:.3f} (thr {threshold})"

    def _append_calibration_snapshot(self, lines: List[str]) -> None:
        """Append Brier-based calibration snapshot if calibration data is available.

        Uses UnifiedCalibration (calibration/picks.csv) and never raises; silently
        skips if no data or if anything goes wrong.
        """
        try:
            calib = UnifiedCalibration()
        except Exception:
            return

        sport_key = self.sport.lower()
        if not calib.picks:
            return

        # Ensure we actually have Brier-scored picks for this sport
        sport_picks = [p for p in calib.picks if p.sport == sport_key and p.brier is not None]
        if not sport_picks:
            return

        try:
            brier = calib.get_sport_brier(sport_key)
            flags = calib.check_drift_flags(sport_key)
            tier_stats = calib.get_tier_stats(sport_key)
            threshold = calib.BRIER_THRESHOLDS.get(sport_key, 0.25)
        except Exception:
            return

        lines.append("CALIBRATION SNAPSHOT (Brier-based):")
        lines.append(f"  Brier score: {brier:.4f} (threshold: {threshold})")

        if flags.get("requires_recalibration"):
            status = "[WARN] DRIFT DETECTED - monitor hit rates and consider recalibration"
        else:
            status = "[OK] Calibration within acceptable range"
        lines.append(f"  Status: {status}")

        if tier_stats:
            lines.append("  Tier integrity (realized vs targets):")
            for tier in ["SLAM", "STRONG", "LEAN"]:
                stats = tier_stats.get(tier)
                if not stats:
                    continue
                icon = "OK" if stats["meets_target"] else "FAIL"
                lines.append(
                    f"    {tier}: {stats['hit_rate']:.1%} over {stats['picks']} picks "
                    f"(target {stats['target']:.0%}) [{icon}]"
                )

        lines.append("")
    
    def _normalize_edge_fields(self) -> None:
        """Normalize edge field names across all sports.
        
        CBB/Tennis/NHL pipelines use 'player'/'stat'; NBA uses 'entity'/'market'.
        The cheat sheet renderer expects 'entity', 'market', and title-case
        direction ('Higher'/'Lower').  Map once on init so everything works.
        """
        for edge in self.edges:
            # player → entity
            if "entity" not in edge or not edge.get("entity"):
                edge["entity"] = edge.get("player", "Unknown")
            # stat → market
            if "market" not in edge or not edge.get("market"):
                edge["market"] = edge.get("stat", "?")
            # Normalize direction to title case ('higher' → 'Higher')
            d = edge.get("direction", "")
            if d and d[0].islower():
                edge["direction"] = d.title()
            # Ensure probability is percentage (0-100) — some pipelines output 0-1
            p = edge.get("probability", 0)
            if isinstance(p, (int, float)) and 0 < p < 1:
                edge["probability"] = p * 100

    def _validate_and_correct_edges(self) -> None:
        """Validate tier assignments using canonical thresholds"""
        for edge in self.edges:
            prob = edge.get("probability", 0)
            # Convert percentage to decimal if needed
            if prob > 1:
                prob = prob / 100
            
            declared_tier = edge.get("tier", "")
            expected_tier = implied_tier(prob, self.sport)
            
            if declared_tier != expected_tier:
                self.tier_corrections += 1
                edge["tier_original"] = declared_tier
                edge["tier"] = expected_tier
                edge["tier_corrected"] = True
        
        if self.tier_corrections > 0:
            print(f"[!] TIER CORRECTION: Fixed {self.tier_corrections} tier mismatches using canonical thresholds")
    
    def _detect_duplicates(self) -> None:
        """Detect and remove duplicate edges"""
        seen: Set[Tuple[str, str, float, str]] = set()
        unique_edges = []
        
        for edge in self.edges:
            key = (
                edge.get("entity", "").lower(),
                edge.get("market", "").lower(),
                edge.get("line", 0),
                edge.get("direction", "").lower()
            )
            
            if key in seen:
                self.duplicates_removed += 1
                print(f"[!] DUPLICATE REMOVED: {edge.get('entity')} {edge.get('market')} {edge.get('line')} {edge.get('direction')}")
            else:
                seen.add(key)
                unique_edges.append(edge)
        
        self.edges = unique_edges
        
        if self.duplicates_removed > 0:
            print(f"[!] DUPLICATE DETECTION: Removed {self.duplicates_removed} duplicate edges")

    def _probability_pct(self, edge: Dict) -> float:
        """Return probability in percent (0-100), robust to 0-1 inputs."""
        p = edge.get("probability", 0)
        try:
            p = float(p)
        except Exception:
            return 0.0
        # Heuristic: treat 0-1 as decimal, otherwise assume percent
        if 0.0 <= p <= 1.0:
            return p * 100.0
        return p

    def _consolidate_player_market_conflicts(self) -> None:
        """Collapse multiple lines for the same (player, market).

        The ingest/analysis layer can sometimes emit multiple entries for the
        same player+stat (e.g., alternate lines, duplicate boards, or mixed
        slates). A cheat sheet should present at most one actionable line per
        player+market to avoid contradictory guidance.

        Policy:
        - Group by (entity, market) regardless of direction/line.
        - Keep the single edge with the highest success probability.
        - Record a compact warning for transparency.
        """

        grouped: Dict[Tuple[str, str], List[Dict]] = {}
        for e in self.edges:
            ent = (e.get("entity") or "").strip()
            mkt = (e.get("market") or "").strip()
            if not ent or not mkt:
                # Keep ungroupable edges untouched
                grouped.setdefault(("__ungrouped__", str(id(e))), []).append(e)
                continue
            key = (ent.lower(), mkt.lower())
            grouped.setdefault(key, []).append(e)

        consolidated: List[Dict] = []
        for key, items in grouped.items():
            if key[0] == "__ungrouped__":
                consolidated.extend(items)
                continue
            if len(items) == 1:
                consolidated.append(items[0])
                continue

            # Pick the best by probability; tie-break with tier then Kelly.
            def tier_rank(t: str) -> int:
                order = ["SLAM", "STRONG", "LEAN", "FLIP", "FADE", "AVOID"]
                try:
                    return order.index((t or "").upper())
                except ValueError:
                    return len(order)

            def score(e: Dict) -> Tuple[float, int, float]:
                p = self._probability_pct(e)
                tr = tier_rank(e.get("tier"))
                # Kelly stake as a tie-break signal
                stake = 0.0
                try:
                    stake = self.bankroll * self._calculate_kelly(p)
                except Exception:
                    stake = 0.0
                # Higher probability wins; better tier (lower rank) next; bigger stake last
                return (p, -tr, stake)

            best = max(items, key=score)
            consolidated.append(best)
            removed = [e for e in items if e is not best]
            self.market_conflicts_removed += len(removed)

            # Store a human-readable summary (include line + direction)
            def fmt_line(v) -> str:
                try:
                    fv = float(v)
                    return f"{fv:.1f}"
                except Exception:
                    return str(v)

            ent_name = best.get("entity", "Unknown")
            mkt = best.get("market", "?")
            kept = f"{best.get('direction', '?')} {fmt_line(best.get('line', '-'))} @ {self._probability_pct(best):.1f}%"
            dropped = ", ".join(
                [
                    f"{e.get('direction','?')} {fmt_line(e.get('line','-'))} @ {self._probability_pct(e):.1f}%"
                    for e in removed
                ]
            )
            self.market_conflict_warnings.append(
                f"{ent_name}: {mkt} kept [{kept}] | dropped [{dropped}]"
            )

        # Preserve original ordering as much as possible while using consolidation
        # (best effort): sort consolidated by original index in self.edges.
        index = {id(e): i for i, e in enumerate(self.edges)}
        consolidated.sort(key=lambda e: index.get(id(e), 10**9))
        self.edges = consolidated

        if self.market_conflicts_removed > 0:
            print(f"[!] MARKET CONSOLIDATION: Removed {self.market_conflicts_removed} conflicting player/stat lines")
    
    def _detect_correlations(self) -> None:
        """Detect when same player appears in multiple markets (correlation risk)"""
        player_markets: Dict[str, List[Dict]] = {}
        
        for edge in self.edges:
            player = edge.get("entity", "").lower()
            if player:
                if player not in player_markets:
                    player_markets[player] = []
                player_markets[player].append(edge)
        
        for player, markets in player_markets.items():
            # Only warn when there are multiple DISTINCT markets after consolidation
            distinct = {}
            for m in markets:
                mkt = (m.get("market") or "").upper()
                distinct.setdefault(mkt, []).append(m)
            if len(distinct) > 1:
                market_names = [
                    f"{m.get('market')} {m.get('direction')} {m.get('line')}"
                    for m in markets
                ]
                warning = f"{player.title()}: {', '.join(market_names)}"
                self.correlation_warnings.append(warning)
                
                # Tag edges as correlated
                for edge in markets:
                    edge["correlated"] = True
                    edge["correlation_count"] = len(markets)
        
        if self.correlation_warnings:
            print(f"[!] CORRELATION WARNING: {len(self.correlation_warnings)} players with multiple markets")

    def _load_player_stat_avgs(self) -> None:
        """Load latest NBA stats cache and build player -> {stat: mu} map.

        Reads outputs/stats_cache/nba_mu_sigma_*.json and extracts mu for
        base stats: points, rebounds, assists, 3pm.
        """
        try:
            cache_dir = Path("outputs") / "stats_cache"
            if not cache_dir.exists():
                return
            latest = None
            latest_mtime = 0
            for f in cache_dir.glob("nba_mu_sigma_*.json"):
                mt = f.stat().st_mtime
                if mt > latest_mtime:
                    latest_mtime = mt
                    latest = f
            if not latest:
                return
            raw = json.loads(latest.read_text(encoding="utf-8"))
            stats_list = raw.get("stats", []) or []
            for item in stats_list:
                player = item.get("player")
                stat = item.get("stat")
                mu = item.get("mu")
                if not (isinstance(player, str) and isinstance(stat, str) and isinstance(mu, (int, float))):
                    continue
                pkey = player.strip()
                if pkey not in self.player_stat_avgs:
                    self.player_stat_avgs[pkey] = {}
                self.player_stat_avgs[pkey][stat.lower()] = float(mu)
        except Exception:
            # Silent fail; report should still generate
            self.player_stat_avgs = {}

    def _append_player_stat_snapshots(self, lines: List[str]) -> None:
        """Append a compact table of stat snapshots (PTS/REB/AST/3PM/PRA)."""
        if self.sport != "NBA" or not self.player_stat_avgs:
            return
        # Collect unique players from current edges
        players = []
        seen = set()
        for e in self.edges:
            p = e.get("entity")
            if isinstance(p, str) and p and p not in seen:
                seen.add(p)
                players.append(p)
        if not players:
            return
        lines.append("")
        lines.append("Player Stat Snapshots (mu across recent window)")
        sep = "─" if self.unicode_output else "-"
        lines.append("  " + sep * 95)
        header = f"  {'Player':<25} {'PTS':<6} {'REB':<6} {'AST':<6} {'3PM':<6} {'PRA':<6}"
        lines.append(header)
        lines.append("  " + sep * 95)
        for p in players:
            avgs = self.player_stat_avgs.get(p, {})
            pts = avgs.get("points")
            reb = avgs.get("rebounds")
            ast = avgs.get("assists")
            tpm = avgs.get("3pm")
            pra = None
            try:
                if all(isinstance(x, (int, float)) for x in (pts, reb, ast)):
                    pra = float(pts) + float(reb) + float(ast)
            except Exception:
                pra = None
            def fmt(x):
                return f"{x:.1f}" if isinstance(x, (int, float)) else "-"
            lines.append(
                f"  {p[:24]:<25} {fmt(pts):<6} {fmt(reb):<6} {fmt(ast):<6} {fmt(tpm):<6} {fmt(pra):<6}"
            )
        lines.append("")
    
    def filter_by_tier(self, min_tier: str = "LEAN") -> List[Dict]:
        """Filter edges by minimum tier, robust to unknown/extra tiers"""
        tier_order = ["SLAM", "STRONG", "LEAN", "FLIP", "FADE"]
        min_idx = tier_order.index(min_tier) if min_tier in tier_order else len(tier_order) - 1

        def get_tier_idx(tier):
            try:
                return tier_order.index(tier)
            except ValueError:
                # Unknown tier: treat as lowest priority (after FADE)
                return len(tier_order)

        return [
            e for e in self.edges
            if get_tier_idx(e.get("tier", "FADE")) <= min_idx
        ]
    
    def generate_text_report(self, output_path: Optional[Path] = None) -> str:
        """Generate text-based cheat sheet"""
        lines = []
        
        # Header (ASCII-safe by default)
        header_bar = "═" if self.unicode_output else "="
        sub_bar = "─" if self.unicode_output else "-"
        lines.append(header_bar * 100)
        dash = "—" if self.unicode_output else "-"
        lines.append(f"  {self.sport} CONSOLIDATED CHEAT SHEET {dash} {self.timestamp}")
        lines.append(header_bar * 100)
        lines.append("")
        
        # Summary stats
        by_tier = {}
        by_direction = {"Higher": 0, "Lower": 0}
        
        for edge in self.edges:
            tier = edge.get("tier", "FADE")
            direction = edge.get("direction", "Higher")
            
            by_tier[tier] = by_tier.get(tier, 0) + 1
            by_direction[direction] = by_direction.get(direction, 0) + 1
        
        lines.append(f"[*] TOTAL PLAYS: {len(self.edges)}")
        lines.append(f"   OVERS:  {by_direction.get('Higher', 0)}")
        lines.append(f"   UNDERS: {by_direction.get('Lower', 0)}")
        lines.append("")

        # Optional calibration snapshot (if calibration data exists for this sport)
        self._append_calibration_snapshot(lines)
        
        for tier in ["SLAM", "STRONG", "LEAN"]:
            if tier in by_tier:
                icon = self.TIER_ICONS.get(tier, "")
                lines.append(f"   {icon} {tier}: {by_tier[tier]}")
        lines.append("")
        lines.append(sub_bar * 100)
        lines.append("")
        
        # Group by tier
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_edges = [e for e in self.edges if e.get("tier") == tier]
            if not tier_edges:
                continue
            
            icon = self.TIER_ICONS.get(tier, "")
            lines.append(f"\n{icon} {tier} PLAYS ({len(tier_edges)})")
            lines.append(sub_bar * 110)
            
            # Separate OVERS and UNDERS
            overs = [e for e in tier_edges if e.get("direction") == "Higher"]
            unders = [e for e in tier_edges if e.get("direction") == "Lower"]
            
            if overs:
                lines.append("\n  [OVERS]:")
                lines.append(f"  {'Player':<25} {'Stat':<12} {'Line':<8} {'OVER %':<10} {'UNDER %':<10} {'Edge':<10} {'Kelly':<8}")
                lines.append("  " + ("─" * 105 if self.unicode_output else "-" * 105))
                
                for edge in sorted(overs, key=lambda x: x.get("probability", 0), reverse=True):
                    player = edge.get("entity", "Unknown")[:24]
                    stat = edge.get("market", "?")[:11]
                    line = edge.get("line", 0)
                    over_prob = edge.get("probability", 0)
                    under_prob = 100 - over_prob
                    
                    # Calculate edge from line
                    edge_str = self._calculate_edge_display(edge)
                    kelly_str = self._get_kelly_stake(over_prob)
                    
                    lines.append(
                        f"  {player:<25} {stat:<12} {line:<8.1f} "
                        f"{over_prob:<10.1f} {under_prob:<10.1f} {edge_str:<10} {kelly_str:<8}"
                    )
            
            if unders:
                lines.append("\n  [UNDERS]:")
                lines.append(f"  {'Player':<25} {'Stat':<12} {'Line':<8} {'UNDER %':<10} {'OVER %':<10} {'Edge':<10} {'Kelly':<8}")
                lines.append("  " + ("─" * 105 if self.unicode_output else "-" * 105))
                
                for edge in sorted(unders, key=lambda x: x.get("probability", 0), reverse=True):
                    player = edge.get("entity", "Unknown")[:24]
                    stat = edge.get("market", "?")[:11]
                    line = edge.get("line", 0)
                    under_prob = edge.get("probability", 0)
                    over_prob = 100 - under_prob
                    
                    edge_str = self._calculate_edge_display(edge)
                    kelly_str = self._get_kelly_stake(under_prob)
                    
                    lines.append(
                        f"  {player:<25} {stat:<12} {line:<8.1f} "
                        f"{under_prob:<10.1f} {over_prob:<10.1f} {edge_str:<10} {kelly_str:<8}"
                    )
            
            lines.append("")
        
        # Footer
        lines.append(sub_bar * 100)
        # Optional per-player stat breakdown
        self._append_player_stat_snapshots(lines)
        
        # Get canonical thresholds for legend
        thresholds = get_all_thresholds(self.sport)
        slam_pct = int(thresholds.get("SLAM", 0.80) * 100) if thresholds.get("SLAM") else None
        strong_pct = int(thresholds.get("STRONG", 0.65) * 100)
        lean_pct = int(thresholds.get("LEAN", 0.55) * 100)
        
        lines.append("\nLEGEND (canonical thresholds):")
        if slam_pct:
            lines.append(f"  [SLAM]:   >={slam_pct}% confidence | Highest conviction plays")
        else:
            lines.append(f"  [SLAM]:   DISABLED for {self.sport}")
        lines.append(f"  [STRONG]: {strong_pct}-{slam_pct-1 if slam_pct else 79}% confidence | High conviction plays")
        lines.append(f"  [LEAN]:   {lean_pct}-{strong_pct-1}% confidence | Moderate conviction plays")
        lines.append(f"  [AVOID]:  <{lean_pct}% confidence | No edge, skip")
        lines.append("")
        lines.append("  OVER %:  Probability of going OVER the line")
        lines.append("  UNDER %: Probability of going UNDER the line")
        lines.append("  Edge:    Statistical advantage vs line")
        lines.append(f"  Kelly:   Recommended bet size (25% Kelly, ${self.bankroll:.0f} bankroll)")
        
        # Show corrections if any
        if self.tier_corrections > 0:
            lines.append("")
            lines.append(f"  [!] {self.tier_corrections} tier labels were corrected to match probabilities")
        
        if self.duplicates_removed > 0:
            lines.append(f"  [!] {self.duplicates_removed} duplicate edges were removed")

        if self.market_conflicts_removed > 0:
            lines.append(f"  [!] {self.market_conflicts_removed} conflicting player/stat lines were removed")
            # Show a couple of examples for transparency
            for msg in self.market_conflict_warnings[:3]:
                lines.append(f"      - {msg}")
            if len(self.market_conflict_warnings) > 3:
                lines.append(f"      ... and {len(self.market_conflict_warnings) - 3} more")
        
        if self.correlation_warnings:
            lines.append("")
            lines.append("  [WARN] CORRELATION WARNINGS (same player, multiple markets):")
            for warning in self.correlation_warnings[:5]:  # Show first 5
                lines.append(f"     - {warning}")
            if len(self.correlation_warnings) > 5:
                lines.append(f"     ... and {len(self.correlation_warnings) - 5} more")
        
        lines.append("")
        lines.append(("═" * 110) if self.unicode_output else ("=" * 110))
        lines.append(f"Generated: {self.timestamp} | Bankroll: ${self.bankroll:.0f} | Kelly: 25% fractional")
        lines.append(("═" * 110) if self.unicode_output else ("=" * 110))
        
        report = "\n".join(lines)
        
        # Save if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding='utf-8')
            print(f"[OK] Saved: {output_path}")
        
        return report
    
    def _calculate_edge_display(self, edge: Dict) -> str:
        """Calculate and format edge display"""
        # Try to extract expected value or create from probability
        probability = edge.get("probability", 50)
        
        # Simple edge calculation: how much above 50%
        if probability >= 50:
            edge_pct = probability - 50
            return f"+{edge_pct:.1f}%"
        else:
            edge_pct = 50 - probability
            return f"-{edge_pct:.1f}%"
    
    def _calculate_kelly(self, probability: float, odds: float = None) -> float:
        """Calculate Kelly Criterion bet sizing.
        
        Formula: k = (b*p - q) / b
        where b = net odds, p = win prob, q = 1-p
        
        We use fractional Kelly (25%) for safety.
        """
        if odds is None:
            odds = self.DEFAULT_ODDS
        
        prob = probability / 100.0 if probability > 1 else probability
        
        if prob <= 0 or prob >= 1 or odds <= 1:
            return 0.0
        
        b = odds - 1  # Net odds
        q = 1 - prob
        
        kelly = (b * prob - q) / b
        
        # Fractional Kelly and floor at 0
        return max(0, kelly * self.KELLY_FRACTION)
    
    def _get_kelly_stake(self, probability: float) -> str:
        """Get formatted Kelly stake recommendation."""
        kelly_pct = self._calculate_kelly(probability)
        stake = self.bankroll * kelly_pct
        
        if stake < 5:  # Minimum bet threshold
            return "-"
        return f"${stake:.0f}"
    
    def generate_quick_reference(self) -> str:
        """Generate ultra-compact quick reference card"""
        lines = []
        if self.unicode_output:
            lines.append("╔" + "═" * 78 + "╗")
            lines.append(f"║  {self.sport} QUICK REFERENCE — {datetime.now().strftime('%m/%d %I:%M%p'):<60} ║")
        else:
            lines.append("+" + "=" * 78 + "+")
            lines.append(f"|  {self.sport} QUICK REFERENCE - {datetime.now().strftime('%m/%d %I:%M%p'):<60} |")

        status = self._get_calibration_status_line()
        if status:
            if self.unicode_output:
                lines.append(f"║  {status:<76} ║")
            else:
                lines.append(f"|  {status:<76} |")

        if self.unicode_output:
            lines.append("╠" + "═" * 78 + "╣")
        else:
            lines.append("+" + "=" * 78 + "+")
        
        # Top plays only (SLAM + STRONG)
        top_plays = [e for e in self.edges if e.get("tier") in ["SLAM", "STRONG"]]
        
        if not top_plays:
            if self.unicode_output:
                lines.append("║  No high-confidence plays available" + " " * 43 + "║")
            else:
                lines.append("|  No high-confidence plays available" + " " * 43 + "|")
        else:
            # Overs
            overs = [e for e in top_plays if e.get("direction") == "Higher"][:5]
            if overs:
                if self.unicode_output:
                    lines.append("║  [TOP OVERS]:" + " " * 63 + "║")
                else:
                    lines.append("|  [TOP OVERS]:" + " " * 63 + "|")
                for i, edge in enumerate(overs, 1):
                    player = edge.get("entity", "Unknown")[:18]
                    stat = edge.get("market", "?")[:6]
                    line = edge.get("line", 0)
                    prob = edge.get("probability", 0)
                    tier = edge.get("tier", "?")
                    icon = self.TIER_ICONS.get(tier, "")
                    kelly = self._get_kelly_stake(prob)
                    
                    text = f"  {i}. {player:<18} {stat:<6} O{line:<5.1f} {prob:.0f}% {icon:<10} {kelly}"
                    if self.unicode_output:
                        lines.append(f"║  {text:<76} ║")
                    else:
                        lines.append(f"|  {text:<76} |")
            
            # Unders
            unders = [e for e in top_plays if e.get("direction") == "Lower"][:5]
            if unders:
                if self.unicode_output:
                    lines.append("║" + " " * 78 + "║")
                    lines.append("║  📉 TOP UNDERS:" + " " * 62 + "║")
                else:
                    lines.append("|" + " " * 78 + "|")
                    lines.append("|  TOP UNDERS:" + " " * 66 + "|")
                for i, edge in enumerate(unders, 1):
                    player = edge.get("entity", "Unknown")[:18]
                    stat = edge.get("market", "?")[:6]
                    line = edge.get("line", 0)
                    prob = edge.get("probability", 0)
                    tier = edge.get("tier", "?")
                    icon = self.TIER_ICONS.get(tier, "")
                    kelly = self._get_kelly_stake(prob)
                    
                    text = f"  {i}. {player:<18} {stat:<6} U{line:<5.1f} {prob:.0f}% {icon:<10} {kelly}"
                    if self.unicode_output:
                        lines.append(f"║  {text:<76} ║")
                    else:
                        lines.append(f"|  {text:<76} |")
        
        if self.unicode_output:
            lines.append("╚" + "═" * 78 + "╝")
        else:
            lines.append("+" + "=" * 78 + "+")
        return "\n".join(lines)


def load_latest_edges(sport: str = "nba") -> Optional[List[Dict]]:
    """Load latest edges file for sport"""
    outputs_dir = Path("outputs")

    # Prefer the canonical "latest" pointer if available.
    if sport.lower() == "nba":
        preferred = outputs_dir / "signals_latest.json"
        if preferred.exists():
            try:
                print(f"[*] Loading: {preferred}")
                data = json.loads(preferred.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    for key in ["edges", "signals", "picks", "plays", "props", "results"]:
                        if key in data:
                            items = data[key]
                            if key == "results" and items and isinstance(items[0], dict):
                                return convert_risk_first_to_edges(items)
                            return items
            except Exception:
                # Fall through to heuristic search
                pass

        # Next best: use active slate label to pick the matching RISK_FIRST output.
        try:
            active_path = Path("state") / "active_slate.json"
            if active_path.exists():
                active = json.loads(active_path.read_text(encoding="utf-8"))
                label = (active.get("label") or "").strip()
                if label:
                    candidates = sorted(outputs_dir.glob(f"{label}_RISK_FIRST_*FROM_UD.json"), key=lambda p: p.stat().st_mtime)
                    if candidates:
                        chosen = candidates[-1]
                        print(f"[*] Loading (active slate): {chosen}")
                        data = json.loads(chosen.read_text(encoding="utf-8"))
                        if isinstance(data, list):
                            return data
                        if isinstance(data, dict) and "results" in data:
                            return convert_risk_first_to_edges(data["results"])
        except Exception:
            # Fall through to heuristic search
            pass
    
    # Search patterns by sport
    patterns = {
        # Prefer canonical analysis outputs over broad NBA globbing (prevents stale file selection)
        "nba": ["*_RISK_FIRST_*FROM_UD.json", "*signals*.json"],
        "tennis": ["*tennis*.json"],
        "cbb": ["*cbb*.json", "*CBB*.json"],
        "nfl": ["*nfl*.json", "*NFL*.json", "*cheatsheet*.json"],
        "golf": ["*golf*.json", "*GOLF*.json", "*phoenix*.json", "*pga*.json"]
    }
    
    sport_key = sport.lower()
    sport_patterns = patterns.get(sport_key, ["*.json"])

    # Find most recent file. For some sports (e.g., CBB), analysis outputs
    # live under sport-specific subdirectories (sports/cbb/outputs). We
    # prefer those over any legacy root-level JSONs in outputs/.
    latest_file = None
    latest_time = 0

    search_dirs = [outputs_dir]
    if sport_key == "cbb":
        cbb_dir = Path("sports") / "cbb" / "outputs"
        if cbb_dir.exists():
            # Prefer sport-specific directory by searching it first; we still
            # include outputs/ as a fallback in case older pipelines wrote
            # there.
            search_dirs = [cbb_dir, outputs_dir]

    # Skip known summary/metadata files that contain counters, not edge lists
    _SUMMARY_FILENAMES = {"cbb_run_latest.json"}

    for base in search_dirs:
        for pattern in sport_patterns:
            for file in base.glob(pattern):
                if file.name.lower() in _SUMMARY_FILENAMES:
                    continue
                try:
                    mtime = file.stat().st_mtime
                except OSError:
                    continue
                if mtime > latest_time:
                    latest_time = mtime
                    latest_file = file
    
    if not latest_file:
        return None
    
    print(f"[*] Loading: {latest_file}")
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Try common keys — only accept list values (skip int counters like props: 536)
        for key in ["edges", "signals", "picks", "plays", "props", "results"]:
            if key in data and isinstance(data[key], list):
                items = data[key]
                # Convert risk_first format to edge format
                if key == "results" and items and isinstance(items[0], dict):
                    return convert_risk_first_to_edges(items)
                return items
    
    return None


def convert_risk_first_to_edges(results: List[Dict]) -> List[Dict]:
    """Convert risk_first analysis format to edge format"""
    edges = []
    for r in results:
        # Skip blocked/no_play entries (support multiple schema versions)
        decision = (
            r.get("decision")
            or r.get("status")
            or r.get("tier_label")
            or r.get("final_status")
            or "NO_PLAY"
        )
        decision = str(decision).upper()
        if decision in ["BLOCKED", "NO_PLAY", "SKIP", "AVOID", "FAIL"]:
            continue
        
        # Map tier
        tier_map = {
            "PLAY": "STRONG",
            "STRONG": "STRONG",
            "LEAN": "LEAN",
            "SLAM": "SLAM",
        }
        tier = tier_map.get(decision, decision)
        
        # Determine probability and direction
        confidence = (
            r.get("effective_confidence")
            if r.get("effective_confidence") is not None
            else r.get("status_confidence")
            if r.get("status_confidence") is not None
            else r.get("model_confidence")
            if r.get("model_confidence") is not None
            else r.get("confidence")
            if r.get("confidence") is not None
            else 50
        )
        direction = r.get("direction", "higher")
        
        # For "lower" direction, we need to invert probability
        if str(direction).lower() in ["lower", "under"]:
            probability = confidence  # Already the UNDER probability
            direction = "Lower"
        else:
            probability = confidence  # OVER probability
            direction = "Higher"
        
        edge = {
            "edge_id": f"{r.get('player', 'Unknown')}_{r.get('stat', '?')}",
            "entity": r.get("player", "Unknown"),
            "market": r.get("stat", "?").upper(),
            "line": r.get("line", 0),
            "direction": direction,
            "probability": probability,
            "tier": tier,
            "sport": "NBA",
            "team": r.get("team", "?"),
            "opponent": r.get("opponent", "?")
        }
        edges.append(edge)
    
    return edges


def main():
    _configure_stdout_for_windows()

    parser = argparse.ArgumentParser(description="Generate consolidated cheat sheet")
    parser.add_argument("--sport", choices=["nba", "tennis", "cbb", "nfl", "golf"], default="nba",
                       help="Sport to generate cheat sheet for")
    parser.add_argument("--input", type=str, help="Input JSON file path")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--min-tier", choices=["SLAM", "STRONG", "LEAN"], default="LEAN",
                       help="Minimum tier to include")
    parser.add_argument("--quick", action="store_true", help="Generate quick reference only")
    parser.add_argument("--bankroll", type=float, default=1000.0,
                       help="Bankroll for Kelly Criterion sizing (default: $1000)")
    parser.add_argument(
        "--unicode",
        action="store_true",
        help="Use unicode box-drawing and icons in output (default: ASCII-safe)",
    )
    
    args = parser.parse_args()
    
    # Load edges
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                edges = data
            elif "results" in data:
                edges = convert_risk_first_to_edges(data["results"])
            else:
                edges = data.get("edges", data.get("signals", data.get("picks", [])))
    else:
        edges = load_latest_edges(args.sport)
        if not edges:
            print(f"[X] No edges found for {args.sport}")
            print(f"   Run analysis first or use --input to specify file")
            return
    
    print(f"\n[*] Loaded {len(edges)} edges")
    print(f"[*] Kelly sizing based on ${args.bankroll:.0f} bankroll")
    
    # Create cheat sheet with bankroll
    sheet = ConsolidatedCheatSheet(edges, sport=args.sport, bankroll=args.bankroll, unicode_output=args.unicode)
    
    # Filter by tier
    filtered = sheet.filter_by_tier(args.min_tier)
    sheet.edges = filtered
    
    print(f"[*] Filtered to {len(filtered)} plays ({args.min_tier}+ tier)\n")
    
    # Generate reports
    if args.quick:
        quick = sheet.generate_quick_reference()
        print(quick)
    else:
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_path = Path(f"outputs/{args.sport.upper()}_CHEATSHEET_{timestamp}.txt")
        
        # Generate full report
        report = sheet.generate_text_report(output_path)
        print(report)
        
        # Also generate quick reference
        print("\n" + "="*80)
        print("QUICK REFERENCE CARD:")
        print("="*80 + "\n")
        print(sheet.generate_quick_reference())


if __name__ == "__main__":
    main()
