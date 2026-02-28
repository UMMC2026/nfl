"""Client-facing reporting renderer for council decisions.

Generates a lightweight Markdown summary from a list of council decisions.
This is independent of the existing cheat sheet generator.
"""

from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional


def render_client_report(
    decisions: List[Dict],
    *,
    sport: str,
    calibration_snapshot: Optional[Dict] = None,
) -> str:
    """Render a Markdown client report from council decisions.

    Each decision dict is expected to have keys:
      - entity, market, line, direction, probability, tier, decision
      - sop (optional), edge (optional)
    """
    sport = sport.upper()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: List[str] = []
    lines.append(f"# {sport} Edge Report — {ts}")
    lines.append("")

    by_decision = Counter(d.get("decision", "NO PLAY") for d in decisions)
    by_tier = Counter(d.get("tier", "AVOID") for d in decisions)

    total = len(decisions)
    lines.append(f"Total candidates after council: **{total}**")
    lines.append("")
    if total:
        lines.append("## Decision breakdown")
        for dec, cnt in by_decision.items():
            lines.append(f"- **{dec}**: {cnt}")
        lines.append("")

        lines.append("## Tier breakdown")
        for tier, cnt in by_tier.items():
            lines.append(f"- **{tier}**: {cnt}")
        lines.append("")

    if calibration_snapshot:
        lines.append("## Calibration snapshot")
        brier = calibration_snapshot.get("brier")
        threshold = calibration_snapshot.get("threshold")
        status = calibration_snapshot.get("status")
        if brier is not None and threshold is not None:
            lines.append(f"- Brier score: **{brier:.4f}** (threshold {threshold})")
        if status:
            lines.append(f"- Status: {status}")
        lines.append("")

    # List PLAY and LEAN picks
    plays = [d for d in decisions if d.get("decision") in {"PLAY", "LEAN"}]
    if plays:
        lines.append("## Recommended plays")
        lines.append("")
        lines.append("| Player | Market | Line | Dir | Prob % | Tier | Decision |")
        lines.append("|--------|--------|------|-----|--------:|------|----------|")
        for d in sorted(plays, key=lambda x: x.get("probability", 0), reverse=True):
            lines.append(
                "| {entity} | {market} | {line:.1f} | {dir} | {prob:.1f} | {tier} | {dec} |".format(
                    entity=(d.get("entity") or "?")[:24],
                    market=(d.get("market") or "?"),
                    line=float(d.get("line", 0.0)),
                    dir=d.get("direction", "Higher"),
                    prob=float(d.get("probability", 0.0)),
                    tier=d.get("tier", ""),
                    dec=d.get("decision", ""),
                )
            )
        lines.append("")

    return "\n".join(lines)
