"""Extract situational edges from saved balanced report text files.

Why this exists:
- Sometimes the strict daily pipeline produces no actionable edges (or no slate is loaded).
- But situational single-game reports (e.g., *_BALANCED_*_FROM_UD.txt) can still contain
  useful LEAN/STRONG candidates with matchup/context modifiers.

This script parses those reports and emits:
- outputs/situational_edges_latest.json
- outputs/SITUATIONAL_EDGES_<timestamp>.txt

It is intentionally read-only with respect to the core engines/gates.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


OUTPUTS_DIR = Path("outputs")


@dataclass
class SituationalEdge:
    source_file: str
    team: str
    opponent: str
    player: str
    stat: str
    direction: str
    line: float
    tier: str
    probability: float
    notes: str = ""

    def to_edge_dict(self) -> Dict[str, Any]:
        # Emit a compatible-ish edge schema for downstream viewing.
        base = asdict(self)
        base["sport"] = "nba"  # These balanced reports are currently NBA-focused.
        base["league"] = "NBA"
        base["edge_id"] = self._edge_id()
        return base

    def _edge_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", f"sit_{self.team}_{self.player}_{self.stat}_{self.line}_{self.direction}".lower()).strip("_")
        return slug


_TEAM_HEADER_RE = re.compile(r"^TEAM:\s*(?P<team>[A-Z]{2,4})\s*$")
_MATCHUP_RE = re.compile(r"^\s*Matchup\s+vs\s+(?P<opp>[A-Z]{2,4})\s*:")

# Example:
# 1) Russell Westbrook pra higher 23.5 — LEAN (68.0%) [Matchup: +6.3%, ✅ vs Weak D (#27), Away: -2.0%]
_EDGE_LINE_RE = re.compile(
    r"^\s*\d+\)\s+"
    r"(?P<player>.+?)\s+"
    r"(?P<stat>pts\+reb\+ast|pra|pts\+reb|pts\+ast|reb\+ast|points|rebounds|assists|3pm|blocks|steals)\s+"
    r"(?P<direction>higher|lower|over|under)\s+"
    r"(?P<line>-?\d+(?:\.\d+)?)\s+"
    r"—\s+(?P<tier>[A-Z]+)\s+\((?P<prob>\d+(?:\.\d+)?)%\)"
    r"(?:\s*\[(?P<notes>.*)\])?\s*$",
    re.IGNORECASE,
)


def iter_report_files(pattern: str) -> Iterable[Path]:
    # Allow pattern to be a single file path or a glob.
    p = Path(pattern)
    if p.exists() and p.is_file():
        yield p
        return

    # Otherwise treat as glob relative to workspace root.
    for fp in sorted(Path().glob(pattern)):
        if fp.is_file():
            yield fp


def parse_report(path: Path) -> List[SituationalEdge]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    current_team: Optional[str] = None
    current_opp: Optional[str] = None

    edges: List[SituationalEdge] = []

    for raw in lines:
        line = raw.rstrip("\n")

        m_team = _TEAM_HEADER_RE.match(line.strip())
        if m_team:
            current_team = (m_team.group("team") or "").strip().upper()
            current_opp = None
            continue

        m_mu = _MATCHUP_RE.match(line)
        if m_mu:
            current_opp = (m_mu.group("opp") or "").strip().upper()
            continue

        m_edge = _EDGE_LINE_RE.match(line)
        if m_edge and current_team:
            player = (m_edge.group("player") or "").strip()
            stat = (m_edge.group("stat") or "").strip().lower()
            direction = (m_edge.group("direction") or "").strip().lower()
            tier = (m_edge.group("tier") or "").strip().upper()
            notes = (m_edge.group("notes") or "").strip() if m_edge.group("notes") else ""
            try:
                line_val = float(m_edge.group("line"))
            except Exception:
                continue
            try:
                prob = float(m_edge.group("prob"))
            except Exception:
                continue

            edges.append(
                SituationalEdge(
                    source_file=str(path).replace("\\", "/"),
                    team=current_team,
                    opponent=current_opp or "UNK",
                    player=player,
                    stat=stat,
                    direction=direction,
                    line=line_val,
                    tier=tier,
                    probability=prob,
                    notes=notes,
                )
            )

    return edges


def render_text_report(edges: List[SituationalEdge]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(f"SITUATIONAL EDGES (EXTRACTED) — {ts}")
    lines.append("=" * 80)

    if not edges:
        lines.append("No edges extracted from the selected report files.")
        return "\n".join(lines)

    # Sort: tier strength then probability desc
    tier_rank = {"SLAM": 0, "STRONG": 1, "LEAN": 2, "FLIP": 3, "FADE": 4}

    def key(e: SituationalEdge):
        return (tier_rank.get(e.tier, 9), -e.probability)

    edges_sorted = sorted(edges, key=key)

    by_game: Dict[str, List[SituationalEdge]] = {}
    for e in edges_sorted:
        matchup = f"{e.team} vs {e.opponent}"
        by_game.setdefault(matchup, []).append(e)

    for matchup, group in by_game.items():
        lines.append("")
        lines.append(f"{matchup} — {len(group)} edge(s)")
        lines.append("-" * 80)
        for e in group:
            notes = f" [{e.notes}]" if e.notes else ""
            lines.append(
                f"{e.tier:<6} {e.player} {e.stat} {e.direction} {e.line:g} | P={e.probability:.1f}%{notes}"
            )
            lines.append(f"        source: {e.source_file}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract situational edges from balanced report .txt files")
    parser.add_argument(
        "--pattern",
        default="outputs/*BALANCED*.txt",
        help="Glob pattern (or single file path) of report files to parse. Default: outputs/*BALANCED*.txt",
    )
    parser.add_argument(
        "--min-prob",
        type=float,
        default=0.0,
        help="Minimum probability percent to keep (0-100). Default: 0",
    )
    args = parser.parse_args()

    files = list(iter_report_files(args.pattern))
    all_edges: List[SituationalEdge] = []

    for fp in files:
        all_edges.extend(parse_report(fp))

    if args.min_prob > 0:
        all_edges = [e for e in all_edges if e.probability >= args.min_prob]

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    latest_json = OUTPUTS_DIR / "situational_edges_latest.json"
    latest_json.write_text(json.dumps([e.to_edge_dict() for e in all_edges], indent=2), encoding="utf-8")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_txt = OUTPUTS_DIR / f"SITUATIONAL_EDGES_{ts}.txt"
    out_txt.write_text(render_text_report(all_edges), encoding="utf-8")

    print(f"[*] Parsed {len(files)} file(s)")
    print(f"[*] Extracted {len(all_edges)} edge(s)")
    print(f"[OK] Wrote: {latest_json}")
    print(f"[OK] Wrote: {out_txt}")


if __name__ == "__main__":
    main()
