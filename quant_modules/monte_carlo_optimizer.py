"""
MONTE CARLO ENTRY OPTIMIZER
===========================
Simulates thousands of outcomes to find optimal entry combinations.

MATHEMATICAL FOUNDATIONS:
- Exact mode: Poisson-Binomial PMF for hit distribution
- MC mode: Stochastic simulation (legacy)
- VaR 5%: Lower 5th percentile of outcome distribution
- Kelly criterion: Fractional sizing based on edge/variance

HARDENING OPTIONS (controlled by feature flags):
- Beta distribution for probabilities (more conservative)
- CVaR (Conditional VaR) for tail-risk focus
- Correlation matrix for multi-leg adjustments
- Clamped Kelly (max 10% sizing)

See: quant_modules/mc_hardening.py for hardening implementations
See: config/feature_flags.json for enabling these features
"""

from __future__ import annotations

import random
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from itertools import combinations
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Feature flag loader for hardening
FEATURE_FLAGS_PATH = PROJECT_ROOT / "config" / "feature_flags.json"


def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags, returning empty dict if unavailable."""
    try:
        if FEATURE_FLAGS_PATH.exists():
            with open(FEATURE_FLAGS_PATH, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _is_hardening_enabled(category: str = "mc_optimizer") -> bool:
    """Check if MC hardening features are enabled."""
    flags = _load_feature_flags()
    global_flags = flags.get("global", {})
    mc_flags = flags.get(category, {})
    
    # Check global kill switch
    if not global_flags.get("enable_new_features", False):
        return False
    
    # Check specific hardening flag
    return mc_flags.get("use_beta_distribution", False)


POWER_PAYOUTS = {2: 3.0, 3: 6.0, 4: 10.0, 5: 20.0, 6: 35.0}
FLEX_PAYOUTS = {
    3: {3: 2.25, 2: 1.25},
    4: {4: 5.0, 3: 1.5},
    5: {5: 10.0, 4: 2.0, 3: 0.4},
    6: {6: 25.0, 5: 2.0, 4: 0.4},
}


def _norm_stat(stat: str) -> str:
    s = str(stat or "").strip().lower()
    s = re.sub(r"\s+", "", s)
    return s


_STAT_DISPLAY_MAP: Dict[str, str] = {
    # basketball commons
    "points": "PTS",
    "pts": "PTS",
    "rebounds": "REB",
    "reb": "REB",
    "assists": "AST",
    "ast": "AST",
    "steals": "STL",
    "stl": "STL",
    "blocks": "BLK",
    "blk": "BLK",
    "turnovers": "TOV",
    "tov": "TOV",
    "3pm": "3PM",
    "3ptm": "3PM",
    "3pt": "3PM",
    "3pts": "3PM",
    "3p": "3PM",
    "threes": "3PM",
    # composites
    "pra": "PRA",
    "pr": "PR",
    "pa": "PA",
    "ra": "RA",
    "pts+reb+ast": "PRA",
    "pts+reb": "PR",
    "pts+ast": "PA",
    "reb+ast": "RA",
    "stocks": "STOCKS",
    "stl+blk": "STOCKS",
    # Expanded stat support
    "fgm": "FGM",
    "fga": "FGA",
    "fg%": "FG%",
    "oreb": "OREB",
    "dreb": "DREB",
    "ftm": "FTM",
    "fta": "FTA",
    "ft%": "FT%",
    "min": "MIN",
    "plus_minus": "+/-",
    "pf": "PF",
    "eff": "EFF",
    # Expanded combos
    "fgm+fga": "FGM+FGA",
    "oreb+dreb": "OREB+DREB",
    "ftm+fta": "FTM+FTA",
    "pts+fgm": "PTS+FGM",
    "pts+fga": "PTS+FGA",
    "pts+oreb": "PTS+OREB",
    "pts+dreb": "PTS+DREB",
    # Synonyms
    "field_goals_made": "FGM",
    "field_goals_attempted": "FGA",
    "offensive_rebounds": "OREB",
    "defensive_rebounds": "DREB",
    "free_throws_made": "FTM",
    "free_throws_attempted": "FTA",
    "personal_fouls": "PF",
    "minutes": "MIN",
}


def _display_stat(stat: str) -> str:
    raw = str(stat or "").strip()
    norm = _norm_stat(raw)
    if norm in _STAT_DISPLAY_MAP:
        return _STAT_DISPLAY_MAP[norm]
    # Fall back to a reasonable readable label.
    if raw:
        return raw.strip().upper()
    return norm.upper() if norm else "STAT"


def _display_direction(direction: str) -> str:
    d = str(direction or "").strip().lower()
    if d in {"higher", "more", "over", ">"}:
        return ">"
    if d in {"lower", "less", "under", "<"}:
        return "<"
    return (direction or "").strip().upper() or "?"


def _format_line(value: float) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    # Use compact representation (e.g., 4.5 instead of 4.500000)
    return f"{x:g}"


def _format_leg(p: "Pick") -> str:
    stat = _display_stat(p.stat)
    sign = _display_direction(p.direction)
    line = _format_line(p.line)
    return f"{p.player} {stat} {sign}{line}"


# NBA structural discipline defaults (entry construction only)
_NBA_PRIMARY_SAFE_STATS = {
    "points",
    "rebounds",
    "steals",
    "blocks",
    # common aliases
    "pts",
    "reb",
    "stl",
    "blk",
}

_NBA_FRAGILE_STATS = {
    # role-dependent / high variance
    "assists",
    "ast",
    "3pm",
    "3ptm",
    "threes",
    "turnovers",
    "tov",
    # composites / correlation traps
    "pra",
    "pr",
    "pa",
    "ra",
    "pts+reb+ast",
    "pts+reb",
    "pts+ast",
    "reb+ast",
    "stocks",
    "stl+blk",
}


# Common NBA team abbreviations (used for league inference only).
# If teams/opponents look like 3-letter abbreviations but are *not* NBA, we treat it as likely CBB.
_NBA_TEAM_ABBRS = {
    "ATL",
    "BOS",
    "BKN",
    "CHA",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NOP",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHX",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
}


def _norm_league_label(value: Any) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    # Normalize some common labels.
    if s in {"NCAAB", "NCAA", "NCAA_MBB", "NCAA-M", "COLLEGE", "CBB", "MBB"}:
        return "CBB"
    if s in {"NBA", "BASKETBALL"}:
        return "NBA"
    if s in {"NFL", "FOOTBALL"}:
        return "NFL"
    return s


def _infer_league_from_picks(picks_data: List[dict], *, meta: Optional[dict] = None) -> str:
    """Best-effort league inference.

    We deliberately avoid overfitting to stat names because CBB and NBA share many stat labels
    (points/rebounds/assists/3pm). Instead, we prefer explicit fields and then fall back to
    team/opponent abbreviation heuristics.
    """
    # 1) Explicit league hints (if present)
    # Mixed slates can contain multiple sports. Avoid returning on the first hint;
    # instead, prefer the majority label when it is decisive.
    explicit_candidates: List[Any] = []
    if isinstance(meta, dict):
        explicit_candidates.extend([meta.get("league"), meta.get("sport")])
    for p in picks_data or []:
        if isinstance(p, dict):
            explicit_candidates.extend([p.get("league"), p.get("sport")])

    counts = {"NBA": 0, "NFL": 0, "CBB": 0}
    for cand in explicit_candidates:
        lab = _norm_league_label(cand)
        if lab in counts:
            counts[lab] += 1

    total_explicit = sum(counts.values())
    if total_explicit > 0:
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top_lab, top_count = ordered[0]
        second_count = ordered[1][1] if len(ordered) > 1 else 0

        # Decisive majority: >=60% of explicit hints OR a clear 2+ vote lead.
        if top_count >= 2 and (top_count / max(1, total_explicit) >= 0.60 or top_count >= second_count + 2):
            return top_lab

    # 2) Team/opponent abbreviation heuristics.
    # If many 3-letter codes are not NBA teams, treat as likely CBB.
    nba_team_hits = 0
    non_nba_3abbr_hits = 0
    for p in picks_data or []:
        if not isinstance(p, dict):
            continue
        for k in ("team", "opponent"):
            v = str(p.get(k, "") or "").strip().upper()
            if len(v) == 3 and v.isalpha():
                if v in _NBA_TEAM_ABBRS:
                    nba_team_hits += 1
                else:
                    non_nba_3abbr_hits += 1

    # If we see NBA team abbreviations at all, default to NBA unless CBB evidence dominates.
    if nba_team_hits > 0 and nba_team_hits >= non_nba_3abbr_hits:
        return "NBA"

    # Prefer CBB when the evidence indicates "3-letter teams, but not NBA".
    if non_nba_3abbr_hits >= 2 and nba_team_hits == 0:
        return "CBB"
    if non_nba_3abbr_hits >= 4 and non_nba_3abbr_hits > nba_team_hits:
        return "CBB"

    # If explicit hints are split (e.g., NBA + CBB) but we have some NBA teams, treat as NBA.
    if total_explicit > 0 and counts.get("NBA", 0) > 0 and nba_team_hits > 0:
        return "NBA"

    # 3) Stat-name heuristics (last resort): only NBA vs NFL.
    nba_hits = 0
    nfl_hits = 0
    for p in picks_data or []:
        if not isinstance(p, dict):
            continue
        st = _norm_stat(p.get("stat", ""))
        if not st:
            continue

        # Strong NFL signatures
        if "_" in st and any(x in st for x in ("pass", "rush", "rec", "yd", "yards", "receptions", "td")):
            nfl_hits += 2

        # NBA signatures (can collide with CBB, which is why this is last)
        if st in _NBA_PRIMARY_SAFE_STATS or st in _NBA_FRAGILE_STATS:
            nba_hits += 2
        if "pts+" in st or "reb+" in st or st == "ast":
            nba_hits += 1

    if nba_hits > nfl_hits and nba_hits >= 2:
        return "NBA"
    if nfl_hits > nba_hits and nfl_hits >= 2:
        return "NFL"
    return "UNKNOWN"


def _nba_is_primary_safe(stat: str) -> bool:
    return _norm_stat(stat) in _NBA_PRIMARY_SAFE_STATS


def _nba_is_fragile(stat: str) -> bool:
    return _norm_stat(stat) in _NBA_FRAGILE_STATS


@dataclass
class Pick:
    player: str
    stat: str
    line: float
    direction: str
    p_hit: float
    # Optional governance metadata (non-breaking): used for specialist constraints.
    specialist: str = ""
    team: str = ""
    opponent: str = ""
    game_id: str = ""
    # Display-only: mu (average) and sigma (std dev) for transparency
    mu: float = 0.0
    sigma: float = 0.0
    
    @property
    def key(self) -> str:
        return f"{self.player}|{self.stat}|{self.direction}"

    @property
    def game_bucket(self) -> str:
        """Stable same-game bucket.

        Prefer explicit game_id; else use sorted TEAM/OPP (captures both sides of NBA games);
        else fall back to team; else player (never empty).
        """
        if self.game_id:
            return str(self.game_id)

        t = (self.team or "").strip().upper()
        o = (self.opponent or "").strip().upper()
        if t and o:
            a, b = sorted([t, o])
            return f"{a}@{b}"
        if t:
            return t
        return (self.player or "UNK").strip() or "UNK"


@dataclass
class EntryResult:
    picks: List[Pick]
    legs: int
    entry_type: str
    ev: float = 0.0
    std: float = 0.0
    sharpe: float = 0.0
    prob_profit: float = 0.0
    var_95: float = 0.0
    max_drawdown: float = 0.0
    kelly_fraction: float = 0.0
    n_sims: int = 0
    mean_hits: float = 0.0
    
    def __str__(self):
        legs = "; ".join([_format_leg(p) for p in self.picks])
        return (
            f"{self.legs}L {self.entry_type.upper()} | EV={self.ev:+.2f} | "
            f"Sharpe={self.sharpe:.2f} | P(profit)={self.prob_profit:.1%} | {legs}"
        )


@dataclass 
class OptimizationResult:
    entries: List[EntryResult] = field(default_factory=list)
    best_power: Optional[EntryResult] = None
    best_flex: Optional[EntryResult] = None
    best_sharpe: Optional[EntryResult] = None
    generated_at: str = ""
    # Non-breaking metadata for reporting/debugging.
    context: Dict[str, Any] = field(default_factory=dict)


class MonteCarloOptimizer:
    def __init__(self, n_sims: int = 10000, seed: Optional[int] = None, method: str = "exact"):
        """Create an optimizer.

        Args:
            n_sims: Number of Monte Carlo sims when method == 'mc'. Ignored for 'exact'.
            seed: RNG seed for Monte Carlo mode.
            method: 'exact' (fast, deterministic) or 'mc' (slow, stochastic).
        """
        self.n_sims = n_sims
        self.method = (method or "exact").lower().strip()
        self.use_hardening = _is_hardening_enabled()
        if seed is not None:
            random.seed(seed)
        
        # Try to load hardening module if enabled
        self._hardening_module = None
        if self.use_hardening:
            try:
                from quant_modules.mc_hardening import evaluate_pick_hardened
                self._hardening_module = evaluate_pick_hardened
                print("[MC OPTIMIZER] Hardening enabled: Beta distributions, CVaR, clamped Kelly")
            except ImportError:
                print("[MC OPTIMIZER] Warning: Hardening module not found, using standard mode")
                self.use_hardening = False

    def _poisson_binomial_pmf(self, probs: List[float]) -> List[float]:
        """Return P(K=k) for k=0..n where K is sum of independent Bernoullis."""
        n = len(probs)
        pmf = [0.0] * (n + 1)
        pmf[0] = 1.0
        for p in probs:
            p = max(0.0, min(1.0, float(p)))
            # Update backwards to avoid overwriting needed terms
            for k in range(n, 0, -1):
                pmf[k] = pmf[k] * (1.0 - p) + pmf[k - 1] * p
            pmf[0] *= (1.0 - p)
        # Numerical safety
        s = sum(pmf)
        if s > 0:
            pmf = [x / s for x in pmf]
        return pmf

    def _entry_net_payout(self, legs: int, hits: int, entry_type: str) -> float:
        if entry_type == "power":
            payout = POWER_PAYOUTS[legs] if hits == legs else 0.0
        else:
            flex_table = FLEX_PAYOUTS[legs]
            payout = flex_table.get(hits, 0.0)
        return payout - 1.0

    def _var_quantile(self, outcomes: List[Tuple[float, float]], alpha: float = 0.05) -> float:
        """Lower-tail quantile for a discrete distribution.

        outcomes: list of (value, prob)
        """
        outcomes_sorted = sorted(outcomes, key=lambda t: t[0])
        cdf = 0.0
        for value, prob in outcomes_sorted:
            cdf += prob
            if cdf >= alpha:
                return value
        return outcomes_sorted[-1][0] if outcomes_sorted else 0.0
    
    def simulate_entry(
        self,
        picks: List[Pick],
        entry_type: str = "power",
        correlation_penalty: float = 0.05,
        method: Optional[str] = None,
    ) -> EntryResult:
        legs = len(picks)
        
        if entry_type == "power" and legs not in POWER_PAYOUTS:
            raise ValueError(f"Invalid power legs: {legs}")
        if entry_type == "flex" and legs not in FLEX_PAYOUTS:
            raise ValueError(f"Invalid flex legs: {legs}")
        
        # Use a stable game bucket; avoid empty keys collapsing everything into one "game".
        game_counts: Dict[str, int] = {}
        for p in picks:
            gid = p.game_bucket
            game_counts[gid] = game_counts.get(gid, 0) + 1
        
        adjusted_probs: List[float] = []
        for p in picks:
            gid = p.game_bucket
            if game_counts[gid] > 1:
                adj = p.p_hit * (1 - correlation_penalty * (game_counts[gid] - 1))
                adjusted_probs.append(max(0.01, min(0.99, adj)))
            else:
                adjusted_probs.append(p.p_hit)

        chosen_method = (method or self.method or "exact").lower().strip()

        # Fast path: exact hit distribution (Poisson-binomial).
        if chosen_method != "mc":
            pmf = self._poisson_binomial_pmf(adjusted_probs)
            outcomes: List[Tuple[float, float]] = []
            ev = 0.0
            ex2 = 0.0
            prob_profit = 0.0
            mean_hits = 0.0
            for hits, prob in enumerate(pmf):
                net = self._entry_net_payout(legs, hits, entry_type)
                outcomes.append((net, prob))
                ev += net * prob
                ex2 += (net * net) * prob
                if net > 0:
                    prob_profit += prob
                mean_hits += hits * prob

            var = max(0.0, ex2 - ev * ev)
            std = math.sqrt(var)
            var_95 = self._var_quantile(outcomes, alpha=0.05)
            max_drawdown = min(v for v, _ in outcomes) if outcomes else 0.0

            return EntryResult(
                picks=picks,
                legs=legs,
                entry_type=entry_type,
                ev=ev,
                std=std,
                sharpe=ev / std if std > 0 else 0.0,
                prob_profit=prob_profit,
                var_95=var_95,
                max_drawdown=max_drawdown,
                kelly_fraction=self._kelly_criterion(ev, std),
                n_sims=0,
                mean_hits=mean_hits,
            )

        # Slow path: Monte Carlo simulation (legacy behavior)
        payouts: List[float] = []
        hit_counts: List[int] = []
        for _ in range(max(1, int(self.n_sims))):
            hits = sum(1 for prob in adjusted_probs if random.random() < prob)
            hit_counts.append(hits)
            payouts.append(self._entry_net_payout(legs, hits, entry_type))

        mean_payout = sum(payouts) / len(payouts)
        std_payout = math.sqrt(sum((p - mean_payout) ** 2 for p in payouts) / len(payouts))
        sorted_payouts = sorted(payouts)
        var_95_idx = int(0.05 * len(sorted_payouts))

        return EntryResult(
            picks=picks,
            legs=legs,
            entry_type=entry_type,
            ev=mean_payout,
            std=std_payout,
            sharpe=mean_payout / std_payout if std_payout > 0 else 0.0,
            prob_profit=sum(1 for p in payouts if p > 0) / len(payouts),
            var_95=sorted_payouts[var_95_idx],
            max_drawdown=min(payouts),
            kelly_fraction=self._kelly_criterion(mean_payout, std_payout),
            n_sims=int(self.n_sims),
            mean_hits=sum(hit_counts) / len(hit_counts),
        )
    
    def _kelly_criterion(self, ev: float, std: float) -> float:
        if std <= 0 or ev <= 0:
            return 0.0
        kelly = (ev / (std ** 2)) * 0.25
        return max(0.0, min(0.25, kelly))
    
    def find_best_entries(
        self,
        picks: List[Pick],
        legs_options: List[int] = [3, 4, 5],
        entry_types: List[str] = ["power", "flex"],
        max_same_game: int = 2,
        max_entries: int = 20,
        max_picks_to_consider: int = 30,
        *,
        league: Optional[str] = None,
        max_primary_per_game: int = 99,
    ) -> OptimizationResult:
        """
        Find best entries using Monte Carlo simulation.
        
        max_picks_to_consider: Limit picks to top N by p_hit to prevent combinatorial explosion.
                               With 1000+ picks, we'd have billions of combinations.
        """
        result = OptimizationResult()
        result.generated_at = datetime.now().isoformat()
        
        # CRITICAL: Limit picks to top N to prevent combinatorial explosion
        # C(1096, 3) = 218M combinations, C(30, 3) = 4060 - manageable
        if len(picks) > max_picks_to_consider:
            print(f"[MONTE CARLO] Limiting to top {max_picks_to_consider} picks (from {len(picks)}) by p_hit...")
            picks = sorted(picks, key=lambda p: p.p_hit, reverse=True)[:max_picks_to_consider]
        
        all_entries: List[EntryResult] = []
        total_combos = 0
        evaluated = 0
        progress_every = 5000
        
        league_norm = (league or "").strip().upper()

        for legs in legs_options:
            if legs > len(picks):
                continue
            
            combo_count = 0
            for combo in combinations(picks, legs):
                combo_list = list(combo)

                # =========================================================
                # Specialist constraints (production lock-in)
                # - BIG_MAN_3PM max legs = 2 (skip any combo >2 containing it)
                # =========================================================
                if legs > 2:
                    has_big_man_3pm = any((p.specialist or "").strip().upper() == "BIG_MAN_3PM" for p in combo_list)
                    if has_big_man_3pm:
                        continue

                game_counts: Dict[str, int] = {}
                primary_counts: Dict[str, int] = {}
                for p in combo_list:
                    gid = p.game_bucket
                    game_counts[gid] = game_counts.get(gid, 0) + 1
                    if league_norm == "NBA" and _nba_is_primary_safe(p.stat):
                        primary_counts[gid] = primary_counts.get(gid, 0) + 1

                if any(c > max_same_game for c in game_counts.values()):
                    continue

                if league_norm == "NBA" and max_primary_per_game is not None:
                    if any(c > int(max_primary_per_game) for c in primary_counts.values()):
                        continue
                
                combo_count += 1
                for entry_type in entry_types:
                    if entry_type == "power" and legs not in POWER_PAYOUTS:
                        continue
                    if entry_type == "flex" and legs not in FLEX_PAYOUTS:
                        continue

                    if entry_type == "flex":
                        # Volatile specialists never enter FLEX.
                        if any(
                            (p.specialist or "").strip().upper() in {"BENCH_MICROWAVE", "OFF_DRIBBLE_SCORER"}
                            for p in combo_list
                        ):
                            continue
                    
                    try:
                        entry_result = self.simulate_entry(combo_list, entry_type)

                        # HARD NO-PLAY GATE (2026-01-28):
                        # If Kelly sizing is 0% *and* the entry has negative EV,
                        # we treat it as NO PLAY and do not surface it as a candidate.
                        if entry_result.kelly_fraction <= 0 and entry_result.ev < 0:
                            continue

                        if entry_result.ev > -0.5:
                            all_entries.append(entry_result)
                    except Exception:
                        continue

                evaluated += 1
                if evaluated % progress_every == 0:
                    print(f"[MONTE CARLO] ...evaluated {evaluated:,} combos so far")
            
            total_combos += combo_count
        
        print(f"[MONTE CARLO] Evaluated {total_combos} combinations, found {len(all_entries)} entries after EV/Kelly filters")
        all_entries.sort(key=lambda x: x.ev, reverse=True)
        result.entries = all_entries[:max_entries]
        
        power_entries = [e for e in all_entries if e.entry_type == "power"]
        flex_entries = [e for e in all_entries if e.entry_type == "flex"]
        
        if power_entries:
            result.best_power = max(power_entries, key=lambda x: x.ev)
        if flex_entries:
            result.best_flex = max(flex_entries, key=lambda x: x.ev)
        if all_entries:
            result.best_sharpe = max(all_entries, key=lambda x: x.sharpe)
        
        return result
    
    def generate_report(self, result: OptimizationResult) -> str:
        def _stat_key_block(*, league: str) -> List[str]:
            # Keep this short and scannable; users often ask what "PTS" / "3PM" means.
            if league not in {"NBA", "CBB"}:
                return []
            return [
                "STAT KEY (basketball):",
                "   PTS=Points | REB=Rebounds | AST=Assists | STL=Steals | BLK=Blocks | TOV=Turnovers",
                "   3PM=3-pointers made (aka 3PT/3PTS) | STOCKS=STL+BLK | PRA=PTS+REB+AST",
                "",
            ]

        def _league_label() -> str:
            ctx = getattr(result, "context", {}) if isinstance(result, OptimizationResult) else {}
            lab = str(ctx.get("inferred_league", "") or "").strip().upper()
            return lab or "UNKNOWN"

        def _filter_explain(pass_name: str) -> str:
            name = str(pass_name or "").strip().upper()
            if not name:
                return ""
            if name == "NBA_STRICT_PRIMARY":
                return "PLAY/LEAN only + min conf + primary-safe stats only (PTS/REB/STL/BLK)"
            if name == "NBA_PRIMARY_ONLY":
                return "PLAY/LEAN only + min conf + primary-safe stats only (allows fragile if needed elsewhere: no)"
            if name == "NBA_PLAYLEAN_ANY_NO_COMPOSITES":
                return "PLAY/LEAN only + min conf + allow non-composite stats (can include 3PM/AST/etc)"
            if name in {"NBA_LEGACY_FALLBACK", "CBB_LEGACY_FALLBACK", "DEFAULT"}:
                return "fallback: include PLAY/LEAN or >= min_confidence (broadest)"
            return ""

        def _entry_details(entry: EntryResult, *, league: str) -> List[str]:
            if not entry or not entry.picks:
                return []
            out: List[str] = []

            # Summary stats
            try:
                avg_p = sum(p.p_hit for p in entry.picks) / len(entry.picks)
                min_p = min(p.p_hit for p in entry.picks)
            except Exception:
                avg_p = 0.0
                min_p = 0.0

            # Same-game / matchup buckets
            try:
                buckets: Dict[str, int] = {}
                for p in entry.picks:
                    b = p.game_bucket
                    buckets[b] = buckets.get(b, 0) + 1
                bucket_str = ", ".join([f"{k}:{v}" for k, v in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))])
            except Exception:
                bucket_str = ""

            # Stat mix
            stat_counts: Dict[str, int] = {}
            for p in entry.picks:
                s = _display_stat(p.stat)
                stat_counts[s] = stat_counts.get(s, 0) + 1
            stat_mix = ", ".join([f"{k}:{v}" for k, v in sorted(stat_counts.items(), key=lambda kv: (-kv[1], kv[0]))])

            out.append(f"   ENTRY SNAPSHOT: avg p_hit={avg_p:.1%}, min p_hit={min_p:.1%}")
            if stat_mix:
                out.append(f"   Stat mix: {stat_mix}")
            if bucket_str:
                out.append(f"   Same-game buckets: {bucket_str}")

            out.append("   LEGS (what each pick is):")
            for i, p in enumerate(entry.picks, 1):
                matchup = ""
                t = (p.team or "").strip().upper()
                o = (p.opponent or "").strip().upper()
                if t and o:
                    matchup = f" ({t} vs {o})"
                elif t:
                    matchup = f" ({t})"

                cls = ""
                if league == "NBA":
                    if _nba_is_primary_safe(p.stat):
                        cls = "PRIMARY_SAFE"
                    elif _nba_is_fragile(p.stat):
                        cls = "FRAGILE"
                    else:
                        cls = "OTHER"

                cls_part = f" | {cls}" if cls else ""
                # Show mu (avg) and sigma for transparency - display only if available
                mu_part = f" | mu={p.mu:.1f}" if p.mu > 0 else ""
                sigma_part = f" | sigma={p.sigma:.1f}" if p.sigma > 0 else ""
                out.append(f"    {i}. {_format_leg(p)}{matchup}{mu_part}{sigma_part} | p_hit={p.p_hit:.1%}{cls_part}")

            # Why section (high-level, deterministic)
            out.append("   Why these markets show up here")
            out.append("    - The optimizer picks the combination that maximizes the chosen objective (EV or Sharpe) under the current filters + stacking constraints.")
            if league == "NBA":
                out.append("    - In NBA mode we *try* strict primary-safe legs first (PTS/REB/STL/BLK). If that yields <2 qualifying picks, we automatically relax filters so it can still build entries.")
                out.append("    - So if you see 3PM/AST/TOV/etc, it usually means the run selected a looser filter pass due to not enough strict-qualifying picks.")
            return out

        ctx = getattr(result, "context", {}) if isinstance(result, OptimizationResult) else {}
        league = _league_label()

        lines = [
            "=" * 70,
            "MONTE CARLO ENTRY OPTIMIZATION",
            f"Generated: {result.generated_at}",
            "=" * 70,
            "",
        ]

        lines.extend(_stat_key_block(league=league))

        # Context header (if available)
        if isinstance(ctx, dict) and ctx:
            lines.append("RUN CONTEXT:")
            lines.append(f"   League inferred: {league}")
            n_in = ctx.get("n_input_picks")
            n_q = ctx.get("n_qualifying_picks")
            if n_in is not None and n_q is not None:
                lines.append(f"   Picks: {n_q} qualifying (from {n_in} analyzed)")
            fp = str(ctx.get("filter_pass", "") or "").strip()
            if fp:
                extra = _filter_explain(fp)
                lines.append(f"   Filter pass: {fp}" + (f" — {extra}" if extra else ""))

            # If available, show how many picks each pass produced so the user can see *why* fallback happened.
            try:
                attempts = ctx.get("filter_attempts")
                if isinstance(attempts, list) and attempts:
                    parts: List[str] = []
                    for a in attempts:
                        if not isinstance(a, dict):
                            continue
                        pn = str(a.get("pass", "") or "").strip()
                        q = a.get("qualifying", None)
                        if pn and q is not None:
                            parts.append(f"{pn}={int(q)}")
                    if parts:
                        lines.append(f"   Filter attempts (qualifying picks): {', '.join(parts)}")
            except Exception:
                pass

            if league == "NBA":
                ms = ctx.get("max_same_game")
                mp = ctx.get("max_primary_per_game")
                mc = ctx.get("nba_min_conf")
                po = ctx.get("nba_primary_only")
                pl = ctx.get("nba_playlean_only")
                if ms is not None:
                    lines.append(f"   Constraints: max_same_game={ms}, max_primary_per_game={mp}")
                if mc is not None:
                    lines.append(f"   NBA min confidence: {mc}")
                if po is not None and pl is not None:
                    lines.append(f"   NBA flags: primary_only={int(bool(po))}, playlean_only={int(bool(pl))}")
            elif league == "CBB":
                mc = ctx.get("cbb_min_conf")
                pl = ctx.get("cbb_playlean_only")
                if mc is not None:
                    lines.append(f"   CBB min confidence: {mc}")
                if pl is not None:
                    lines.append(f"   CBB flags: playlean_only={int(bool(pl))}")

            lines.append("")
        
        if result.best_power:
            lines.append("BEST POWER ENTRY:")
            lines.append(f"   {result.best_power}")
            lines.append(f"   Kelly stake: {result.best_power.kelly_fraction:.1%} of bankroll")
            lines.extend(_entry_details(result.best_power, league=league))
            lines.append("")
        
        if result.best_flex:
            lines.append("BEST FLEX ENTRY:")
            lines.append(f"   {result.best_flex}")
            lines.append(f"   Kelly stake: {result.best_flex.kelly_fraction:.1%} of bankroll")
            lines.extend(_entry_details(result.best_flex, league=league))
            lines.append("")
        
        if result.best_sharpe:
            lines.append("BEST RISK-ADJUSTED (Sharpe):")
            lines.append(f"   {result.best_sharpe}")
            lines.extend(_entry_details(result.best_sharpe, league=league))
            lines.append("")
        
        lines.append("-" * 70)
        lines.append("TOP 10 ENTRIES BY EV:")
        lines.append("-" * 70)

        # Sort entries by EV descending, then by player name (first leg) ascending
        sorted_entries = sorted(
            result.entries,
            key=lambda e: (-getattr(e, 'ev', 0), getattr(e.picks[0], 'player', '') if e.picks else '')
        )
        for i, entry in enumerate(sorted_entries[:10], 1):
            lines.append(f"{i:2}. {entry}")

        return "\n".join(lines)


def optimize_entries(picks_data: List[dict], output_path: Optional[Path] = None, 
                     min_confidence: float = 55.0, *, league: Optional[str] = None,
                     enforce_governance: bool = True) -> OptimizationResult:
    """
    Optimize entry combinations using Monte Carlo simulation.
    
    CRITICAL: With enforce_governance=True (default), picks MUST pass the
    Eligibility Gate before entering Monte Carlo. This ensures:
    - NO REJECTED picks enter optimization
    - NO VETTED picks enter optimization (visible only, not optimizable)
    - Only OPTIMIZABLE picks are considered
    
    Args:
        picks_data: List of pick dicts from analysis
        output_path: Where to write report
        min_confidence: Minimum effective_confidence to include (default 55%)
        enforce_governance: Run Eligibility Gate before optimization (default True)
    """
    # =========================================================================
    # DECISION GOVERNANCE: Eligibility Gate (SOP v2.4)
    # =========================================================================
    if enforce_governance:
        try:
            from core.decision_governance import run_eligibility_gate, get_optimizable_picks, PickState
            
            # Run all picks through the eligibility gate
            gated_picks, gate_stats = run_eligibility_gate(
                picks_data if isinstance(picks_data, list) else 
                picks_data.get("results", picks_data.get("picks", []))
            )
            
            print(f"[MC][GOVERNANCE] Eligibility Gate: "
                  f"{gate_stats['optimizable']} OPTIMIZABLE, "
                  f"{gate_stats['vetted']} VETTED (excluded), "
                  f"{gate_stats['rejected']} REJECTED")
            
            # ONLY use OPTIMIZABLE picks for Monte Carlo
            picks_data = get_optimizable_picks(gated_picks)
            
            if not picks_data:
                print("[MC][GOVERNANCE] No OPTIMIZABLE picks after Eligibility Gate. Cannot build entries.")
                return OptimizationResult()
                
        except ImportError:
            print("[MC] Warning: Decision governance module not found, using legacy filtering")
        except Exception as e:
            print(f"[MC] Warning: Governance gate error: {e}, using legacy filtering")
    
    # Callers sometimes pass the full analysis JSON (dict) instead of the list of pick dicts.
    # Normalize to the list we expect.
    raw: Any = picks_data
    meta: Optional[dict] = raw if isinstance(raw, dict) else None
    if isinstance(raw, dict):
        # Common shapes: {"results": [...]} or {"picks": [...]}.
        candidate = raw.get("picks")
        if not isinstance(candidate, list):
            candidate = raw.get("results")
        if not isinstance(candidate, list):
            # Fall back to the first list-of-dicts value we can find.
            candidate = next(
                (v for v in raw.values() if isinstance(v, list) and (not v or isinstance(v[0], dict))),
                [],
            )
        raw = candidate
    if not isinstance(raw, list):
        raw = []

    # Keep only dict-like items; ignore stray strings/keys.
    normalized_picks_data: List[dict] = [p for p in raw if isinstance(p, dict)]

    print(f"[MC] Converting {len(normalized_picks_data)} picks to Pick objects...")

    inferred = (league or _infer_league_from_picks(normalized_picks_data, meta=meta)).strip().upper()
    nba_mode = inferred == "NBA"
    cbb_mode = inferred == "CBB"

    # Legs to consider. NBA mode includes 2-leg entries so we can still build entries
    # on small slates when we enforce (mostly) one-leg-per-game.
    default_legs_options = [3, 4, 5]
    nba_legs_options = [2, 3, 4]
    legs_options = nba_legs_options if nba_mode else default_legs_options
    max_legs = max(legs_options) if legs_options else 3

    # NBA defaults (entry discipline only; engine decisions unchanged)
    nba_max_same_game = int(os.getenv("NBA_MAX_SAME_GAME", "1").strip() or "1")
    nba_min_conf = float(os.getenv("NBA_MIN_CONF", "65").strip() or "65")
    nba_primary_only = os.getenv("NBA_PRIMARY_ONLY", "1").strip() == "1"
    nba_playlean_only = os.getenv("NBA_PLAYLEAN_ONLY", "1").strip() == "1"

    # CBB defaults: keep it simple and do NOT apply NBA primary/fragile discipline.
    # This is only for entry construction; the upstream CBB engine still governs what is playable.
    cbb_min_conf = float(os.getenv("CBB_MIN_CONF", "60").strip() or "60")
    cbb_playlean_only = os.getenv("CBB_PLAYLEAN_ONLY", "1").strip() == "1"

    def include_legacy(decision: str, conf: float) -> bool:
        return decision in ("PLAY", "LEAN") or conf >= float(min_confidence)

    def include_nba_strict(decision: str, conf: float, stat: str) -> bool:
        if nba_playlean_only and decision not in ("PLAY", "LEAN"):
            return False
        if conf < nba_min_conf:
            return False
        if nba_primary_only and not _nba_is_primary_safe(stat):
            return False
        if _nba_is_fragile(stat):
            return False
        return True

    passes = []
    if nba_mode:
        passes.append(("NBA_STRICT_PRIMARY", include_nba_strict))

        def include_nba_primary_only(decision: str, conf: float, stat: str) -> bool:
            if nba_playlean_only and decision not in ("PLAY", "LEAN"):
                return False
            if conf < nba_min_conf:
                return False
            return _nba_is_primary_safe(stat)

        passes.append(("NBA_PRIMARY_ONLY", include_nba_primary_only))

        def include_nba_playlean_any_no_composites(decision: str, conf: float, stat: str) -> bool:
            if decision not in ("PLAY", "LEAN"):
                return False
            if conf < nba_min_conf:
                return False
            st = _norm_stat(stat)
            if any(x in st for x in ("pra", "pts+reb+ast", "reb+ast", "pts+ast", "pts+reb", "pa", "pr", "ra")):
                return False
            return True

        passes.append(("NBA_PLAYLEAN_ANY_NO_COMPOSITES", include_nba_playlean_any_no_composites))

        def include_nba_legacy(decision: str, conf: float, stat: str) -> bool:
            _ = stat
            return include_legacy(decision, conf)

        passes.append(("NBA_LEGACY_FALLBACK", include_nba_legacy))
    elif cbb_mode:
        def include_cbb_playlean(decision: str, conf: float, stat: str) -> bool:
            _ = stat
            if cbb_playlean_only and decision not in ("PLAY", "LEAN"):
                return False
            return conf >= cbb_min_conf

        passes.append(("CBB_PLAYLEAN", include_cbb_playlean))

        def include_cbb_legacy(decision: str, conf: float, stat: str) -> bool:
            _ = stat
            return include_legacy(decision, conf)

        passes.append(("CBB_LEGACY_FALLBACK", include_cbb_legacy))
    else:
        def include_other(decision: str, conf: float, stat: str) -> bool:
            _ = stat
            return include_legacy(decision, conf)

        passes.append(("DEFAULT", include_other))

    picks: List[Pick] = []
    chosen_pass = "DEFAULT"
    pass_attempts: List[Dict[str, Any]] = []
    for pass_name, include_fn in passes:
        picks = []
        for p in normalized_picks_data:
            decision = str(p.get("decision", "") or "")
            # Prefer effective_confidence, but fall back to model_confidence for older/other schemas.
            conf_val = p.get("effective_confidence", None)
            if conf_val is None:
                conf_val = p.get("model_confidence", 0)
            conf = float(conf_val or 0)
            stat = str(p.get("stat", "") or "")

            ok = include_fn(decision, conf, stat)
            if not ok:
                continue

            picks.append(Pick(
                player=p.get("player", ""),
                stat=stat,
                line=float(p.get("line", 0) or 0),
                direction=p.get("direction", ""),
                p_hit=conf / 100.0,
                specialist=str(p.get("stat_specialist_type") or p.get("nba_stat_specialist_type") or ""),
                team=p.get("team", ""),
                opponent=p.get("opponent", ""),
                game_id=p.get("game_id", ""),
                mu=float(p.get("mu", 0) or 0),
                sigma=float(p.get("sigma", 0) or 0),
            ))

        chosen_pass = pass_name
        pass_attempts.append({"pass": pass_name, "qualifying": len(picks)})
        if len(picks) >= 2:
            break

    if nba_mode:
        print(
            f"[MC][NBA] League inferred=NBA | filter_pass={chosen_pass} | "
            f"max_same_game={nba_max_same_game} | nba_min_conf={nba_min_conf}"
        )
    elif cbb_mode:
        print(
            f"[MC][CBB] League inferred=CBB | filter_pass={chosen_pass} | "
            f"cbb_min_conf={cbb_min_conf} | playlean_only={int(cbb_playlean_only)}"
        )

    print(f"[MC] Found {len(picks)} qualifying picks")

    # If we only have one game bucket in an NBA slate, strict no-stacking would
    # eliminate all multi-leg entries. Auto-relax in this case (stacking is unavoidable).
    nba_effective_max_same_game = nba_max_same_game
    nba_effective_max_primary_per_game = 1
    if nba_mode:
        try:
            unique_games = len({p.game_bucket for p in picks})
        except Exception:
            unique_games = 0

        if unique_games <= 1:
            nba_effective_max_same_game = max(nba_max_same_game, max_legs)
            nba_effective_max_primary_per_game = max(1, max_legs)
            print(
                f"[MC][NBA] Only {unique_games} game bucket detected; relaxing stacking limits "
                f"to allow entries (max_same_game={nba_effective_max_same_game})."
            )
    
    if len(picks) < 2:
        # Add a little context for the user so "lower min_confidence" isn't misleading
        # when the upstream engine has BLOCKED/SKIP'd everything.
        try:
            decisions = [str(p.get("decision", "") or "").upper() for p in normalized_picks_data]
            counts: Dict[str, int] = {}
            for d in decisions:
                counts[d] = counts.get(d, 0) + 1
            top = ", ".join([f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))][:5])
        except Exception:
            top = ""

        print("[MC] Need at least 2 qualifying picks for entry optimization")
        if top:
            print(f"[MC] Decision breakdown: {top}")
        if cbb_mode:
            print("[MC] CBB note: if everything is BLOCKED/SKIP, Monte Carlo cannot build entries.")
        else:
            print("[MC] Try lowering min_confidence threshold")
        return OptimizationResult()
    
    print("[MC] Evaluating entries (exact hit distribution — fast, no 10k-loop sims)...")
    optimizer = MonteCarloOptimizer(n_sims=10000, method="exact")
    result = optimizer.find_best_entries(
        picks,
        legs_options=legs_options,
        max_same_game=(nba_effective_max_same_game if nba_mode else 2),
        league=("NBA" if nba_mode else ("CBB" if cbb_mode else inferred if inferred != "UNKNOWN" else None)),
        max_primary_per_game=(nba_effective_max_primary_per_game if nba_mode else 99),
    )

    # Add rich context for report readability (does not affect optimization decisions).
    try:
        result.context.update(
            {
                "inferred_league": inferred,
                "filter_pass": chosen_pass,
                "filter_attempts": pass_attempts,
                "n_input_picks": len(normalized_picks_data),
                "n_qualifying_picks": len(picks),
                "max_same_game": (nba_effective_max_same_game if nba_mode else 2),
                "max_primary_per_game": (nba_effective_max_primary_per_game if nba_mode else 99),
                "nba_min_conf": (nba_min_conf if nba_mode else None),
                "nba_primary_only": (nba_primary_only if nba_mode else None),
                "nba_playlean_only": (nba_playlean_only if nba_mode else None),
                "cbb_min_conf": (cbb_min_conf if cbb_mode else None),
                "cbb_playlean_only": (cbb_playlean_only if cbb_mode else None),
            }
        )
    except Exception:
        pass
    report = optimizer.generate_report(result)
    
    if output_path is None:
        output_path = PROJECT_ROOT / "outputs" / f"monte_carlo_entries_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    
    print(f"\n[MC] Monte Carlo optimization: {output_path}")
    print(report)
    
    return result


def optimize_entries_unfiltered(
    picks_data: List[dict],
    output_path: Optional[Path] = None,
    min_confidence: float = 55.0,
    *,
    league: Optional[str] = None,
    exclude_composites: bool = True,
) -> OptimizationResult:
    """
    Optimize entries without relying on upstream decision labels (PLAY/LEAN).
    Used for UNDER-first comparator runs so UNDERS can be evaluated even if
    they didn't pass strict upstream gates.

    Filters only by a minimal confidence threshold and optionally excludes
    composite stats (PRA, PR/PA/RA, STL+BLK, etc.).
    """
    raw: Any = picks_data
    if not isinstance(raw, list):
        # Accept dict shapes (e.g., {"results": [...]}) by extracting first list payload
        if isinstance(raw, dict):
            candidate = raw.get("results") or raw.get("picks")
            if not isinstance(candidate, list):
                candidate = next(
                    (v for v in raw.values() if isinstance(v, list) and (not v or isinstance(v[0], dict))),
                    [],
                )
            raw = candidate
        else:
            raw = []

    data_list: List[dict] = [p for p in raw if isinstance(p, dict)]
    inferred = (league or _infer_league_from_picks(data_list, meta=None)).strip().upper()
    nba_mode = inferred == "NBA"
    cbb_mode = inferred == "CBB"

    def _is_composite(stat: str) -> bool:
        st = _norm_stat(stat)
        return (
            st in {"pra", "pr", "pa", "ra", "stl+blk", "stocks"}
            or "+" in st
            or st in {"pts+reb+ast", "pts+reb", "pts+ast", "reb+ast"}
        )

    # Build Pick objects based on confidence only
    picks: List[Pick] = []
    for p in data_list:
        conf_val = p.get("effective_confidence")
        if conf_val is None:
            conf_val = p.get("model_confidence", 0)
        try:
            conf = float(conf_val or 0)
        except Exception:
            conf = 0.0
        if conf < float(min_confidence):
            continue
        st = str(p.get("stat", "") or "")
        if exclude_composites and _is_composite(st):
            continue
        picks.append(
            Pick(
                player=p.get("player", ""),
                stat=st,
                line=float(p.get("line", 0) or 0),
                direction=p.get("direction", ""),
                p_hit=conf / 100.0,
                team=p.get("team", ""),
                opponent=p.get("opponent", ""),
                game_id=p.get("game_id", ""),
            )
        )

    # Legs and constraints (reuse NBA logic for stacking relaxation)
    default_legs_options = [3, 4, 5]
    nba_legs_options = [2, 3, 4]
    legs_options = nba_legs_options if nba_mode else default_legs_options
    max_legs = max(legs_options) if legs_options else 3

    nba_max_same_game = int(os.getenv("NBA_MAX_SAME_GAME", "1").strip() or "1")
    nba_effective_max_same_game = nba_max_same_game
    nba_effective_max_primary_per_game = 1
    if nba_mode:
        try:
            unique_games = len({p.game_bucket for p in picks})
        except Exception:
            unique_games = 0
        if unique_games <= 1:
            nba_effective_max_same_game = max(nba_max_same_game, max_legs)
            nba_effective_max_primary_per_game = max(1, max_legs)
            print(
                f"[MC][NBA] Only {unique_games} game bucket detected; relaxing stacking limits "
                f"to allow entries (max_same_game={nba_effective_max_same_game})."
            )

    if len(picks) < 2:
        print("[MC][RAW] Need at least 2 qualifying picks for entry optimization (unfiltered)")
        return OptimizationResult()

    print("[MC][RAW] Evaluating entries (exact hit distribution)…")
    optimizer = MonteCarloOptimizer(n_sims=10000, method="exact")
    result = optimizer.find_best_entries(
        picks,
        legs_options=legs_options,
        max_same_game=(nba_effective_max_same_game if nba_mode else 2),
        league=("NBA" if nba_mode else ("CBB" if cbb_mode else inferred if inferred != "UNKNOWN" else None)),
        max_primary_per_game=(nba_effective_max_primary_per_game if nba_mode else 99),
    )

    try:
        result.context.update(
            {
                "inferred_league": inferred,
                "filter_pass": "UNFILTERED_DIRECT",
                "n_input_picks": len(data_list),
                "n_qualifying_picks": len(picks),
                "max_same_game": (nba_effective_max_same_game if nba_mode else 2),
                "max_primary_per_game": (nba_effective_max_primary_per_game if nba_mode else 99),
            }
        )
    except Exception:
        pass

    report = optimizer.generate_report(result)
    if output_path is None:
        output_path = PROJECT_ROOT / "outputs" / f"monte_carlo_raw_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n[MC] Monte Carlo (unfiltered): {output_path}")
    print(report)
    return result
