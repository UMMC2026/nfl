#!/usr/bin/env python3
"""src/markets/edge_scanner.py

FUOOM Edge Scanner — Binary Market Edge Detection
===================================================

Scans binary markets (moneyline, spread, total, DK Predictions) for edges
by comparing market-implied fair probabilities against model probabilities.

Two modes:
  1. Auto-edge: Fetches game markets via Odds API, applies model probs if available
  2. Manual-edge: Accepts pasted odds + your model prob, calculates edge instantly

Integrates with:
  - NBA: risk_first_analyzer.py model probabilities
  - NFL: Agent Council win probabilities
  - NHL: Poisson simulation win/total probabilities
  - Golf: Course-fit model win probabilities
  - Tennis: Surface-adjusted match win probabilities

Edge thresholds (from SOP v2.1):
  - SLAM:    ≥8% edge (rare, high conviction)
  - STRONG:  ≥4% edge (actionable)
  - LEAN:    ≥2% edge (minimum for play)
  - NO_PLAY: <2% edge (skip)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.markets.binary_markets import (
    BinaryMarket,
    BinaryMarketEngine,
    american_to_implied,
    apply_model_probabilities,
    consensus_markets,
    edge_pct,
    expected_value,
    format_market_table,
    markets_to_json,
    remove_vig_two_way,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs"


# ── Quick Edge Calculator ──────────────────────────────────────────


def quick_edge(
    *,
    yes_odds: float,
    no_odds: float,
    model_prob: float,
    label: str = "",
) -> Dict[str, Any]:
    """Instant edge calculation from odds + model probability.

    Example:
        quick_edge(yes_odds=+127, no_odds=-257, model_prob=0.52, label="Darnold MVP")

    Returns dict with implied_prob, fair_prob, edge, ev_per_100, tier.
    """
    yes_imp = american_to_implied(yes_odds)
    no_imp = american_to_implied(no_odds)
    fair_yes, fair_no = remove_vig_two_way(yes_imp, no_imp)
    vig = (yes_imp + no_imp) - 1.0

    edge = model_prob - fair_yes
    ev = expected_value(model_prob, yes_odds)

    # Tier classification
    edge_abs = abs(edge)
    if edge_abs >= 0.08:
        tier = "SLAM"
    elif edge_abs >= 0.04:
        tier = "STRONG"
    elif edge_abs >= 0.02:
        tier = "LEAN"
    else:
        tier = "NO_PLAY"

    return {
        "label": label,
        "yes_odds": yes_odds,
        "no_odds": no_odds,
        "implied_prob_yes": round(yes_imp, 4),
        "implied_prob_no": round(no_imp, 4),
        "fair_prob_yes": round(fair_yes, 4),
        "fair_prob_no": round(fair_no, 4),
        "vig_pct": round(vig, 4),
        "model_prob": round(model_prob, 4),
        "edge": round(edge, 4),
        "ev_per_100": round(ev, 2),
        "tier": tier,
        "playable": edge >= 0.02,
        "direction": "YES" if edge > 0 else "NO",
    }


def print_quick_edge(result: Dict[str, Any]) -> None:
    """Pretty-print a quick_edge result."""
    label = result.get("label", "Market")
    print(f"\n  {'═' * 50}")
    print(f"  🎯 {label}")
    print(f"  {'═' * 50}")
    print(f"  YES odds:       {result['yes_odds']:>+.0f}")
    print(f"  NO odds:        {result['no_odds']:>+.0f}")
    print(f"  Vig:            {result['vig_pct']:.1%}")
    print(f"  ────────────────────────────────────────")
    print(f"  Implied (YES):  {result['implied_prob_yes']:.1%}")
    print(f"  Fair (YES):     {result['fair_prob_yes']:.1%}")
    print(f"  Model prob:     {result['model_prob']:.1%}")
    print(f"  ────────────────────────────────────────")
    print(f"  Edge:           {result['edge']:>+.1%}")
    print(f"  EV per $100:    ${result['ev_per_100']:>+.2f}")
    print(f"  Tier:           {result['tier']}")
    print(f"  Playable:       {'✅ YES' if result['playable'] else '❌ NO'}")
    print(f"  Direction:      {result['direction']}")


# ── Full Sport Scanner ─────────────────────────────────────────────


def scan_sport_edges(
    *,
    sport: str = "NBA",
    model_probs: Optional[Dict[str, float]] = None,
    consensus: bool = True,
    min_edge: float = 0.02,
) -> List[BinaryMarket]:
    """Fetch all binary markets for a sport and identify edges.

    Args:
        sport: Sport tag
        model_probs: Dict mapping entity name → model probability
        consensus: Whether to aggregate across bookmakers
        min_edge: Minimum edge to include in results

    Returns:
        List of BinaryMarket objects with edges, sorted by edge descending
    """
    engine = BinaryMarketEngine.from_env()
    if engine is None:
        print("  ❌ ODDS_API_KEY not found")
        return []

    print(f"\n  📡 Fetching {sport} markets from Odds API...")
    markets = engine.fetch_game_markets(sport=sport)

    if not markets:
        print(f"  ⚠ No {sport} markets found")
        return []

    print(f"  ✅ {len(markets)} outcomes across {len(set(m.event_id for m in markets))} events")

    # Consensus aggregation
    if consensus:
        markets = consensus_markets(markets)
        print(f"  📊 {len(markets)} consensus lines")

    # Apply model probabilities if provided
    if model_probs:
        markets = apply_model_probabilities(markets, model_probs)
        with_edge = [m for m in markets if m.edge is not None and abs(m.edge) >= min_edge]
        print(f"  🎯 {len(with_edge)} markets with ≥{min_edge:.0%} edge")
        markets = with_edge

    # Sort by edge descending
    markets.sort(key=lambda m: (m.edge or 0), reverse=True)

    return markets


# ── Interactive Edge Calculator ────────────────────────────────────


def interactive_edge_calculator():
    """Interactive mode for quick edge calculations.

    Allows users to enter odds + model probability and get instant edge feedback.
    Designed for the menu.py interactive flow.
    """
    print(f"\n{'═' * 55}")
    print(f"  🧮 BINARY MARKET EDGE CALCULATOR")
    print(f"{'═' * 55}")
    print(f"  Enter DK Predictions odds to calculate edges.")
    print(f"  Type 'done' when finished.\n")

    results = []

    while True:
        try:
            label = input("  Market label (or 'done'): ").strip()
            if label.lower() in ("done", "quit", "exit", "q"):
                break

            yes_str = input("  YES odds (e.g., +127): ").strip()
            no_str = input("  NO odds (e.g., -257): ").strip()
            model_str = input("  Your model probability (0-1 or %): ").strip()

            # Parse model probability
            try:
                mp = float(model_str.replace("%", ""))
                if mp > 1.0:
                    mp /= 100.0
            except ValueError:
                print("  ⚠ Invalid probability. Skipping.\n")
                continue

            result = quick_edge(
                yes_odds=float(yes_str),
                no_odds=float(no_str),
                model_prob=mp,
                label=label,
            )
            print_quick_edge(result)
            results.append(result)
            print()

        except (ValueError, EOFError):
            print("  ⚠ Invalid input. Try again.\n")
            continue

    # Summary
    if results:
        playable = [r for r in results if r["playable"]]
        print(f"\n{'═' * 55}")
        print(f"  EDGE SCAN SUMMARY")
        print(f"{'═' * 55}")
        print(f"  Scanned: {len(results)} markets")
        print(f"  Playable (≥2% edge): {len(playable)}")

        if playable:
            print(f"\n  {'Label':<30} {'Edge':>7} {'EV/100':>9} {'Tier':<8}")
            print(f"  {'─' * 55}")
            for r in sorted(playable, key=lambda x: x["edge"], reverse=True):
                print(f"  {r['label'][:29]:<30} {r['edge']:>+6.1%} ${r['ev_per_100']:>+8.1f} {r['tier']:<8}")

    return results


# ── Report Generation ──────────────────────────────────────────────


def generate_binary_markets_report(
    markets: List[BinaryMarket],
    *,
    sport: str = "NBA",
    save: bool = True,
) -> str:
    """Generate a text report of binary market edges.

    Returns the report text and optionally saves to outputs/.
    """
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append("=" * 60)
    lines.append(f"  FUOOM BINARY MARKETS REPORT — {sport}")
    lines.append(f"  Generated: {ts}")
    lines.append("=" * 60)

    if not markets:
        lines.append("\n  No markets found.")
        return "\n".join(lines)

    # Group by market type
    by_type: Dict[str, List[BinaryMarket]] = {}
    for m in markets:
        by_type.setdefault(m.market_type, []).append(m)

    for mkt_type, mkt_list in by_type.items():
        lines.append(f"\n{'─' * 60}")
        lines.append(f"  📊 {mkt_type.upper()} ({len(mkt_list)} outcomes)")
        lines.append(f"{'─' * 60}")

        # Sort by edge if available, else by fair_prob
        mkt_list.sort(key=lambda m: (m.edge or 0), reverse=True)

        for m in mkt_list:
            entity = m.entity[:35]
            side = m.side.upper()
            odds_str = f"{m.american_odds:>+.0f}"
            fair_str = f"{m.fair_prob:.1%}"

            line = f"  {entity:<36} {side:<6} {odds_str:>7}  Fair: {fair_str:>6}"

            if m.edge is not None:
                edge_str = f"{m.edge:>+.1%}"
                tier = m.tier
                line += f"  Edge: {edge_str}  [{tier}]"

            lines.append(line)

    # Summary
    lines.append(f"\n{'═' * 60}")
    lines.append(f"  SUMMARY")
    lines.append(f"{'═' * 60}")

    playable = [m for m in markets if m.is_playable]
    lines.append(f"  Total outcomes: {len(markets)}")
    lines.append(f"  Playable (≥2% edge): {len(playable)}")
    lines.append(f"  Events: {len(set(m.event_id for m in markets))}")

    if playable:
        lines.append(f"\n  🎯 PLAYABLE EDGES:")
        for m in sorted(playable, key=lambda x: (x.edge or 0), reverse=True):
            lines.append(
                f"     {m.entity[:30]:<31} {m.side:<6} "
                f"Edge: {m.edge:>+.1%}  EV: ${m.ev_per_100:>+.1f}/100  [{m.tier}]"
            )

    report = "\n".join(lines)

    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts_file = now.strftime("%Y%m%d_%H%M")
        path = OUTPUT_DIR / f"binary_markets_{sport}_{ts_file}.txt"
        path.write_text(report, encoding="utf-8")
        print(f"\n  📁 Report saved: {path.name}")

    return report
