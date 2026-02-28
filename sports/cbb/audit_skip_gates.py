"""
CBB Skip Gate Audit — Standalone
=================================
Reads the latest cbb_RISK_FIRST_*.json output and audits every SKIP edge
to identify WHICH gate caused the skip and whether it was justified.

Usage:
    python sports/cbb/audit_skip_gates.py
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import Counter

# ── Paths ──────────────────────────────────────────────────────────────────
CBB_DIR = Path(__file__).parent
OUTPUTS_DIR = CBB_DIR / "outputs"


# ── Gate Config (recalibrated per user proposal) ──────────────────────────
# Stat-specific CV thresholds — binary/event stats are inherently volatile
STAT_CV_THRESHOLDS = {
    "points": 0.50,       "rebounds": 0.65,    "assists": 0.60,
    "3pm": 0.85,          "threes": 0.85,      "three_pointers": 0.85,
    "blocks": 0.90,       "steals": 0.85,      "turnovers": 0.80,
    "pra": 0.45,          "pts_ast": 0.50,     "pts_reb": 0.50,
    "reb_ast": 0.60,
}
STAT_CV_DEFAULT = 0.55


def get_stat_cv_threshold(stat: str) -> float:
    """Return per-stat CV threshold, defaulting to 0.55."""
    key = stat.lower().replace("+", "_").replace(" ", "_").replace("-", "_")
    return STAT_CV_THRESHOLDS.get(key, STAT_CV_DEFAULT)


@dataclass
class CBBGateConfig:
    """Tunable gate thresholds for CBB analysis."""
    PROB_STRONG: float = 0.70        # v3.0 restored threshold
    PROB_LEAN: float = 0.60          # CBB lean
    EDGE_THRESHOLD: float = 0.08     # lowered from 0.12
    MIN_GAMES: int = 5
    MIN_3PT_ATTEMPTS_AVG: float = 1.0
    CBB_HARD_CAP: float = 0.79       # no SLAM tier


GATE_CFG = CBBGateConfig()


# ── Gate Functions ─────────────────────────────────────────────────────────

def gate_probability(edge: dict) -> Tuple[str, bool, str]:
    """Check if probability meets minimum tier threshold."""
    prob = edge.get("probability", 0)
    if prob >= GATE_CFG.PROB_STRONG:
        return "PROBABILITY", True, f"STRONG ({prob*100:.1f}%)"
    elif prob >= GATE_CFG.PROB_LEAN:
        return "PROBABILITY", True, f"LEAN ({prob*100:.1f}%)"
    else:
        return "PROBABILITY", False, f"BELOW_LEAN ({prob*100:.1f}% < {GATE_CFG.PROB_LEAN*100:.0f}%)"


def gate_market_edge(edge: dict) -> Tuple[str, bool, str]:
    """Check if edge vs. implied 50% is large enough."""
    prob = edge.get("probability", 0)
    edge_pct = abs(prob - 0.50)
    if edge_pct >= GATE_CFG.EDGE_THRESHOLD:
        return "MARKET_EDGE", True, f"edge={edge_pct*100:.1f}% >= {GATE_CFG.EDGE_THRESHOLD*100:.0f}%"
    else:
        return "MARKET_EDGE", False, f"edge={edge_pct*100:.1f}% < {GATE_CFG.EDGE_THRESHOLD*100:.0f}%"


def gate_direction_alignment(edge: dict) -> Tuple[str, bool, str]:
    """Check if direction aligns with projection."""
    direction = edge.get("direction", "").lower()
    mu = edge.get("player_mean", 0) or 0
    line = edge.get("line", 0) or 0

    if direction == "higher" and mu > line:
        delta = mu - line
        return "DIRECTION", True, f"OVER aligned (mu={mu:.1f} > line={line}  delta=+{delta:.1f})"
    elif direction == "lower" and mu < line:
        delta = line - mu
        return "DIRECTION", True, f"UNDER aligned (mu={mu:.1f} < line={line}  delta=+{delta:.1f})"
    elif direction == "higher" and mu <= line:
        delta = line - mu
        return "DIRECTION", False, f"OVER misaligned (mu={mu:.1f} <= line={line}  delta=-{delta:.1f})"
    elif direction == "lower" and mu >= line:
        delta = mu - line
        return "DIRECTION", False, f"UNDER misaligned (mu={mu:.1f} >= line={line}  delta=-{delta:.1f})"
    else:
        return "DIRECTION", True, f"direction={direction} mu={mu:.1f} line={line}"


def gate_stat_governance(edge: dict) -> Tuple[str, bool, str]:
    """CBB stat-specific rules (3PM volume, combo stats, etc.)."""
    stat = (edge.get("stat") or "").lower()
    mu = edge.get("player_mean", 0) or 0

    # 3PM: Only allow if player avg shooting attempts warrant it
    if stat in ("3pm", "threes", "three_pointers"):
        if mu < GATE_CFG.MIN_3PT_ATTEMPTS_AVG:
            return "STAT_GOV", False, f"3PM below volume floor (mu={mu:.1f} < {GATE_CFG.MIN_3PT_ATTEMPTS_AVG})"
        return "STAT_GOV", True, f"3PM volume OK (mu={mu:.1f})"

    return "STAT_GOV", True, f"stat={stat} (no restriction)"


def gate_volatility(edge: dict) -> Tuple[str, bool, str]:
    """Check coefficient of variation using stat-specific thresholds."""
    dt = edge.get("decision_trace", {}) or {}
    model_info = dt.get("model", {}) or {}
    sigma = model_info.get("sigma", 0) or 0
    mu = edge.get("player_mean", 0) or 0
    stat = edge.get("stat", "") or ""

    if mu <= 0:
        return "VOLATILITY", False, f"mu=0 → cannot compute CV"

    cv = sigma / mu
    threshold = get_stat_cv_threshold(stat)
    if cv > threshold:
        return "VOLATILITY", False, f"CV={cv:.2f} > {threshold:.2f} [{stat}] (sigma={sigma:.1f}, mu={mu:.1f})"
    else:
        return "VOLATILITY", True, f"CV={cv:.2f} <= {threshold:.2f} [{stat}] (sigma={sigma:.1f}, mu={mu:.1f})"


def gate_sample_size(edge: dict) -> Tuple[str, bool, str]:
    """Check if enough game data exists."""
    # Look in gate_status for games info
    gate_status = edge.get("gate_status", []) or []
    gp = None
    for gs in gate_status:
        if gs.get("gate") == "games":
            reason = gs.get("reason", "")
            if "GP=" in reason:
                try:
                    gp = int(reason.split("GP=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
            break

    if gp is None:
        return "SAMPLE_SIZE", False, "GP=UNKNOWN"
    elif gp < GATE_CFG.MIN_GAMES:
        return "SAMPLE_SIZE", False, f"GP={gp} < {GATE_CFG.MIN_GAMES}"
    else:
        return "SAMPLE_SIZE", True, f"GP={gp}"


def gate_data_quality(edge: dict) -> Tuple[str, bool, str]:
    """Check mean_source and confidence_flag."""
    mean_source = edge.get("mean_source", "UNKNOWN")
    confidence = edge.get("confidence_flag", "UNKNOWN")
    signal = edge.get("signal_flag", "OK")

    issues = []
    if mean_source == "FALLBACK":
        issues.append(f"mean_source=FALLBACK")
    if confidence in ("NO_DATA", "UNVERIFIED"):
        issues.append(f"confidence={confidence}")
    if signal != "OK":
        issues.append(f"signal={signal}")

    if issues:
        return "DATA_QUALITY", False, " | ".join(issues)
    else:
        return "DATA_QUALITY", True, f"source={mean_source} conf={confidence}"


def gate_hard_gates(edge: dict) -> Tuple[str, bool, str]:
    """Check if the pipeline's own hard gates (gates_all_passed) failed."""
    passed = edge.get("gates_all_passed", True)
    failed_gates = edge.get("gates_failed", [])

    if passed is False or (failed_gates and len(failed_gates) > 0):
        return "HARD_GATES", False, f"FAILED: {', '.join(failed_gates)}"
    else:
        return "HARD_GATES", True, "all_passed"


# ── All gates ──────────────────────────────────────────────────────────────
ALL_GATES = [
    gate_probability,
    gate_market_edge,
    gate_direction_alignment,
    gate_stat_governance,
    gate_volatility,
    gate_sample_size,
    gate_data_quality,
    gate_hard_gates,
]


# ── Audit Engine ───────────────────────────────────────────────────────────

@dataclass
class AuditedEdge:
    """Edge with gate verdict tracking."""
    edge: dict
    gate_verdicts: List[Tuple[str, bool, str]] = field(default_factory=list)

    @property
    def player(self) -> str:
        return self.edge.get("player", "???")

    @property
    def stat(self) -> str:
        return self.edge.get("stat", "???")

    @property
    def direction(self) -> str:
        return self.edge.get("direction", "???")

    @property
    def line(self):
        return self.edge.get("line", "???")

    @property
    def probability(self) -> float:
        return self.edge.get("probability", 0)

    @property
    def tier(self) -> str:
        return self.edge.get("tier", "???")

    @property
    def mu(self) -> float:
        return self.edge.get("player_mean", 0) or 0

    @property
    def failed_gates(self) -> List[str]:
        return [name for name, passed, _ in self.gate_verdicts if not passed]

    @property
    def first_kill_gate(self) -> Optional[str]:
        for name, passed, _ in self.gate_verdicts:
            if not passed:
                return name
        return None


def audit_edges(edges: List[dict]) -> List[AuditedEdge]:
    """Run all gates against every edge, return AuditedEdge list."""
    results = []
    for edge in edges:
        ae = AuditedEdge(edge=edge)
        for gate_fn in ALL_GATES:
            name, passed, reason = gate_fn(edge)
            ae.gate_verdicts.append((name, passed, reason))
        results.append(ae)
    return results


# ── Reporting ──────────────────────────────────────────────────────────────

def print_skip_audit(audited: List[AuditedEdge]) -> None:
    """Print detailed audit of every SKIP edge with gate reasons."""
    skips = [ae for ae in audited if ae.tier == "SKIP"]
    actionable = [ae for ae in audited if ae.tier in ("STRONG", "LEAN")]

    print("\n" + "=" * 80)
    print("  CBB SKIP GATE AUDIT")
    print(f"  Total edges: {len(audited)} | SKIP: {len(skips)} | Actionable: {len(actionable)}")
    print("=" * 80)

    if not skips:
        print("\n  [OK] No SKIP edges found — all edges are actionable.")
        return

    # Sort SKIPs by probability descending (show highest-probability skips first)
    skips.sort(key=lambda ae: ae.probability, reverse=True)

    # Categorize: suspicious vs justified
    suspicious = []
    justified = []

    for ae in skips:
        # Suspicious = probability >= LEAN threshold AND direction aligned
        dir_aligned = any(
            name == "DIRECTION" and passed
            for name, passed, _ in ae.gate_verdicts
        )
        if ae.probability >= GATE_CFG.PROB_LEAN and dir_aligned:
            suspicious.append(ae)
        else:
            justified.append(ae)

    # ── Suspicious SKIPs (should be actionable?) ──
    if suspicious:
        print(f"\n{'='*80}")
        print(f"  ⚠️  SUSPICIOUS SKIPS ({len(suspicious)}) — Prob >= {GATE_CFG.PROB_LEAN*100:.0f}% + Direction Aligned")
        print(f"{'='*80}")
        for ae in suspicious:
            print(f"\n  [{ae.player}] {ae.stat} {ae.direction.upper()} {ae.line}")
            print(f"    Prob: {ae.probability*100:.1f}% | mu: {ae.mu:.1f} | Tier: {ae.tier}")
            print(f"    Kill gates: {', '.join(ae.failed_gates) if ae.failed_gates else 'NONE (tier assigned <LEAN by scorer?)'}")
            for name, passed, reason in ae.gate_verdicts:
                marker = "✓" if passed else "✗"
                print(f"      {marker} {name}: {reason}")

    # ── Justified SKIPs ──
    if justified:
        print(f"\n{'='*80}")
        print(f"  ✓  JUSTIFIED SKIPS ({len(justified)}) — Below threshold or direction misaligned")
        print(f"{'='*80}")
        for ae in justified[:20]:  # Show first 20
            kill = ae.first_kill_gate or "SCORER"
            print(f"    {ae.player:<22} {ae.stat:<12} {ae.direction:<6} {ae.line:>5} | "
                  f"prob={ae.probability*100:>5.1f}% mu={ae.mu:>5.1f} | KILL: {kill}")
        if len(justified) > 20:
            print(f"    ... and {len(justified) - 20} more")


def print_gate_summary(audited: List[AuditedEdge]) -> None:
    """Summary: which gates kill the most edges?"""
    skips = [ae for ae in audited if ae.tier == "SKIP"]
    if not skips:
        print("\n[OK] No SKIP edges — no gate summary needed.")
        return

    # Count how many times each gate caused a failure (across all SKIPs)
    gate_fail_counts = Counter()
    gate_first_kill_counts = Counter()

    for ae in skips:
        for name, passed, _ in ae.gate_verdicts:
            if not passed:
                gate_fail_counts[name] += 1
        if ae.first_kill_gate:
            gate_first_kill_counts[ae.first_kill_gate] += 1

    print(f"\n{'='*80}")
    print("  GATE KILL SCOREBOARD")
    print(f"{'='*80}")
    print(f"\n  {'GATE':<20} {'TOTAL FAILS':>12} {'FIRST KILL':>12} {'% OF SKIPS':>12}")
    print(f"  {'-'*56}")
    for gate_name, count in gate_fail_counts.most_common():
        first_kills = gate_first_kill_counts.get(gate_name, 0)
        pct = (count / len(skips)) * 100
        print(f"  {gate_name:<20} {count:>12} {first_kills:>12} {pct:>11.1f}%")


def print_poisson_check(audited: List[AuditedEdge]) -> None:
    """For suspicious skips, show what Poisson says the probability should be."""
    skips = [ae for ae in audited if ae.tier == "SKIP"]

    # Focus on edges where mu > line (higher) or mu < line (lower) AND prob >= 55%
    candidates = []
    for ae in skips:
        direction = ae.direction.lower()
        mu = ae.mu
        line = ae.line
        prob = ae.probability

        if direction == "higher" and mu > float(line) and prob >= 0.55:
            candidates.append(ae)
        elif direction == "lower" and mu < float(line) and prob >= 0.55:
            candidates.append(ae)

    if not candidates:
        print("\n  [OK] No suspicious high-prob skips with favorable direction.")
        return

    print(f"\n{'='*80}")
    print(f"  POISSON VERIFICATION — {len(candidates)} edges should be actionable")
    print(f"{'='*80}")
    print(f"\n  {'PLAYER':<22} {'STAT':<10} {'DIR':<6} {'LINE':>5} {'MU':>6} {'DELTA':>6} {'PROB':>7} {'KILL GATE':<20}")
    print(f"  {'-'*82}")

    for ae in candidates:
        delta = abs(ae.mu - float(ae.line))
        kill = ae.first_kill_gate or "SCORER"
        print(f"  {ae.player:<22} {ae.stat:<10} {ae.direction:<6} {ae.line:>5} {ae.mu:>6.1f} {delta:>6.1f} "
              f"{ae.probability*100:>6.1f}% {kill:<20}")


def print_actionable_summary(audited: List[AuditedEdge]) -> None:
    """Print edges that passed all gates — current actionable picks."""
    actionable = [ae for ae in audited if ae.tier in ("STRONG", "LEAN")]
    if not actionable:
        print("\n  [!] No actionable edges found.")
        return

    actionable.sort(key=lambda ae: ae.probability, reverse=True)
    print(f"\n{'='*80}")
    print(f"  CURRENT ACTIONABLE ({len(actionable)})")
    print(f"{'='*80}")
    print(f"\n  {'PLAYER':<22} {'STAT':<10} {'DIR':<6} {'LINE':>5} {'MU':>6} {'PROB':>7} {'TIER':<8} {'FLAG':<12}")
    print(f"  {'-'*80}")

    for ae in actionable:
        flag = "FLOOR" if ae.edge.get("sdg_floor_applied") else ""
        print(f"  {ae.player:<22} {ae.stat:<10} {ae.direction:<6} {ae.line:>5} {ae.mu:>6.1f} "
              f"{ae.probability*100:>6.1f}% {ae.tier:<8} {flag:<12}")

    # Show SDG floor-protected edges
    floored = [ae for ae in actionable if ae.edge.get("sdg_floor_applied")]
    if floored:
        print(f"\n  SDG FLOOR APPLIED ({len(floored)}) — Penalty capped to preserve LEAN tier:")
        for ae in floored:
            raw = ae.edge.get("raw_probability", ae.probability)
            print(f"    {ae.player:<22} {ae.stat:<10} raw={raw*100:.0f}% → floored={ae.probability*100:.0f}%")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    # Find latest RISK_FIRST JSON
    json_files = sorted(OUTPUTS_DIR.glob("cbb_RISK_FIRST_*.json"), reverse=True)
    if not json_files:
        print("No cbb_RISK_FIRST_*.json found in", OUTPUTS_DIR)
        sys.exit(1)

    latest = json_files[0]
    print(f"\nLoading: {latest.name}")

    with open(latest, "r", encoding="utf-8") as f:
        data = json.load(f)

    edges = data.get("picks", data) if isinstance(data, dict) else data

    if not edges:
        print("No edges found in JSON.")
        sys.exit(1)

    print(f"Loaded {len(edges)} edges")

    # Run audit
    audited = audit_edges(edges)

    # Print reports
    print_actionable_summary(audited)
    print_gate_summary(audited)
    print_skip_audit(audited)
    print_poisson_check(audited)

    print(f"\n{'='*80}")
    print("  AUDIT COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
