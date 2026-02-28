"""balanced_report.py

Balanced post-analysis reporting:
- Top N picks per team
- Includes PLAY, LEAN, ANALYSIS_ONLY
- Excludes SKIP (team mismatch/no data)

This is a *slicer* only; it does not change any analysis decisions.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _score(r: Dict[str, Any]) -> float:
    # Sort by adjusted probability (effective_confidence), then abs(z_score)
    # Prefer view-layer confidence when present.
    eff = float(r.get("status_confidence", r.get("effective_confidence", 0.0)) or 0.0)
    z = abs(float(r.get("z_score", 0.0) or 0.0))
    return eff * 1000.0 + z


def build_balanced_team_report(analysis: Dict[str, Any], *, top_n: int = 5) -> str:
    results = analysis.get("results") or []
    if not isinstance(results, list):
        return "(no results)"

    # Include both old tier names and new tier names for compatibility
    # Old: PLAY, LEAN, ANALYSIS_ONLY
    # New: SLAM, STRONG, LEAN (canonical tiers from config/thresholds.py)
    # Also include NO_PLAY for completeness (low confidence but analyzed)
    include = {
        "PLAY", "LEAN", "ANALYSIS_ONLY",  # Old names
        "SLAM", "STRONG", "SOLID",        # New high-confidence tiers
        "LEAN_TIER",                      # Alternate naming
    }
    try:
        hq = analysis.get("hq_options")
        if isinstance(hq, dict):
            rep = hq.get("reporting")
            if isinstance(rep, dict):
                inc = rep.get("include_status")
                if isinstance(inc, list) and inc:
                    # Merge user preferences with mandatory new tier names
                    include = {str(x).strip().upper() for x in inc if isinstance(x, str) and str(x).strip()}
                    # Always add new tier names for compatibility
                    include.update({"SLAM", "STRONG", "SOLID", "LEAN_TIER"})
                tn = rep.get("top_n_per_team")
                if isinstance(tn, int) and tn >= 1:
                    top_n = tn
    except Exception:
        pass

    by_team: Dict[str, List[Dict[str, Any]]] = {}
    team_opponents: Dict[str, str] = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        status = r.get("status", r.get("decision"))
        if status not in include:
            continue
        team = r.get("team") or "UNK"
        by_team.setdefault(str(team), []).append(r)
        # Track opponent for team context
        opp = r.get("opponent")
        if opp:
            team_opponents[str(team)] = str(opp)

    if not by_team:
        return "(no PLAY/LEAN/ANALYSIS_ONLY results)"

    # Try to import matchup summary for context
    try:
        from nba_team_context import get_matchup_summary
        has_context = True
    except ImportError:
        has_context = False

    lines: List[str] = []
    for team in sorted(by_team.keys()):
        rows = sorted(by_team[team], key=_score, reverse=True)[:top_n]
        lines.append(f"TEAM: {team}")
        
        # Add matchup context if available
        if has_context and team in team_opponents:
            opp = team_opponents[team]
            summary = get_matchup_summary(team, opp)
            if summary:
                lines.append(f"  Matchup vs {opp}: {summary}")
        
        lines.append("Top edges:")
        for i, r in enumerate(rows, 1):
            player = r.get("player", "?")
            stat = r.get("stat", "?")
            direction = r.get("direction", "?")
            line = r.get("line", "?")
            dec = r.get("status", r.get("decision", "?"))
            p = r.get("status_confidence", r.get("effective_confidence", 0.0))
            p_str = f"{float(p):.1f}%" if isinstance(p, (int, float)) else "?"
            flag = ""
            if dec == "ANALYSIS_ONLY":
                flag = " (ANALYSIS_ONLY)"
            
            # Add context notes if present
            ctx_notes = r.get("context_notes", [])
            ctx_str = ""
            if ctx_notes:
                ctx_str = f" [{', '.join(ctx_notes)}]"
            
            lines.append(f"{i}) {player} {stat} {direction} {line} — {dec}{flag} ({p_str}){ctx_str}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"