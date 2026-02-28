"""soccer/render/render_soccer_report.py

Text renderer for soccer risk-first report.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List


def render_report(edges: List[Dict], *, generated_at: str | None = None) -> str:
    ts = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header = []
    header.append("=" * 65)
    header.append("[SOCCER] FUTBOL STRATEGIC REPORT")
    header.append(f"   Generated: {ts}")
    header.append(f"   Total edges: {len(edges)} | Actionable: {sum(1 for e in edges if e.get('tier') in ('LEAN','STRONG','SLAM'))}")
    header.append("=" * 65)
    header.append("")

    lines: List[str] = list(header)

    # Group by match
    by_match: Dict[str, List[Dict]] = {}
    for e in edges:
        m = e.get("match") or e.get("entity") or "UNKNOWN"
        by_match.setdefault(m, []).append(e)

    for match, m_edges in by_match.items():
        lines.append("" )
        lines.append("=" * 60)
        lines.append(f" {match}")
        lines.append("=" * 60)

        # Sort actionable first
        def tier_rank(t: str | None) -> int:
            return {"SLAM": 0, "STRONG": 1, "LEAN": 2, "NO_PLAY": 9}.get((t or "NO_PLAY"), 9)

        m_edges.sort(key=lambda e: (tier_rank(e.get("tier")), -(e.get("probability") or 0.0)))

        for e in m_edges:
            tier = e.get("tier")
            p = float(e.get("probability") or 0.0)
            market = e.get("market")
            direction = e.get("direction")
            line = e.get("line")
            xg = e.get("xg_projection") or {}
            edge_est = e.get("edge_estimate")
            audit_hash = e.get("audit_hash")

            line_str = "" if line is None else f" {line}"
            edge_str = "" if edge_est is None else f" | edge={edge_est:+.3f}"

            lines.append(f"  [{tier}] {market} {direction}{line_str}  p={p*100:5.1f}%{edge_str}")
            if xg:
                lines.append(f"       xG: home={xg.get('home',0):.2f} away={xg.get('away',0):.2f}  lambda: {e.get('lambda_home',0):.2f}-{e.get('lambda_away',0):.2f}")
            if audit_hash:
                lines.append(f"       audit_hash={audit_hash}")

    return "\n".join(lines).rstrip() + "\n"
