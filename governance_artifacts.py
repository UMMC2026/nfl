from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or ""), encoding="utf-8")


def _fmt_pct(p: Any) -> str:
    try:
        if p is None:
            return "?"
        return f"{float(p):.1f}%"
    except Exception:
        return "?"


def _fmt_num(x: Any) -> str:
    try:
        if x is None:
            return "?"
        return f"{float(x):.2f}"
    except Exception:
        return "?"


def _render_governance_summary(
    *,
    slug: str,
    stamp: str,
    created_at_utc: str,
    results: list[dict],
    allowed_rows: list[dict],
    blocked_rows: list[dict],
    source: dict,
    max_lines: int = 40,
) -> str:
    # Decision counts
    decision_counts: dict[str, int] = {}
    for r in results:
        if not isinstance(r, dict):
            continue
        d = str(r.get("decision") or r.get("status") or "").strip().upper() or "UNKNOWN"
        decision_counts[d] = decision_counts.get(d, 0) + 1

    # Block reasons
    reason_counts: dict[str, int] = {}
    for r in blocked_rows:
        if not isinstance(r, dict):
            continue
        reason = str(r.get("block_reason") or "Blocked").strip() or "Blocked"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    top_reasons = sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:10]

    # Top plays (by effective_confidence then edge)
    def _score(row: dict) -> tuple:
        eff = row.get("effective_confidence")
        edge = row.get("edge")
        try:
            eff_f = float(eff) if eff is not None else -1e9
        except Exception:
            eff_f = -1e9
        try:
            edge_f = float(edge) if edge is not None else -1e9
        except Exception:
            edge_f = -1e9
        return (eff_f, edge_f)

    plays = [r for r in allowed_rows if str(r.get("decision") or "").strip().upper() == "PLAY"]
    leans = [r for r in allowed_rows if str(r.get("decision") or "").strip().upper() == "LEAN"]
    plays = sorted(plays, key=_score, reverse=True)[:10]
    leans = sorted(leans, key=_score, reverse=True)[:10]

    lines: list[str] = []
    lines.append("=" * 78)
    lines.append(f"GOVERNANCE SUMMARY - {slug} - {stamp}")
    lines.append("=" * 78)
    lines.append(f"Created (UTC): {created_at_utc}")
    if source:
        slate = source.get("slate_json") or source.get("slate")
        results_json = source.get("results_json")
        if slate:
            lines.append(f"Input slate : {slate}")
        if results_json:
            lines.append(f"Results JSON: {results_json}")
    lines.append("")

    lines.append("COUNTS")
    lines.append("-" * 78)
    lines.append(f"Total results : {len(results)}")
    lines.append(f"Allowed edges : {len(allowed_rows)}")
    lines.append(f"Blocked edges : {len(blocked_rows)}")
    if decision_counts:
        ordered = sorted(decision_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        lines.append("Decision breakdown:")
        for k, v in ordered:
            lines.append(f"  - {k}: {v}")
    lines.append("")

    if top_reasons:
        lines.append("TOP BLOCK REASONS")
        lines.append("-" * 78)
        for reason, cnt in top_reasons:
            lines.append(f"  {cnt:3d}x - {reason}")
        lines.append("")

    if plays:
        lines.append("TOP PLAY PICKS")
        lines.append("-" * 78)
        for i, r in enumerate(plays, 1):
            lines.append(
                f"{i:2d}. {r.get('player')} ({r.get('team')}) {r.get('stat')} {str(r.get('direction') or '').upper()} {r.get('line')}"
            )
            lines.append(
                f"    eff={_fmt_pct(r.get('effective_confidence'))} model={_fmt_pct(r.get('model_confidence'))} edge={_fmt_num(r.get('edge'))} z={_fmt_num(r.get('z_score'))}"
            )
        lines.append("")

    if leans:
        lines.append("TOP LEANS")
        lines.append("-" * 78)
        for i, r in enumerate(leans, 1):
            lines.append(
                f"{i:2d}. {r.get('player')} ({r.get('team')}) {r.get('stat')} {str(r.get('direction') or '').upper()} {r.get('line')}"
            )
            lines.append(
                f"    eff={_fmt_pct(r.get('effective_confidence'))} model={_fmt_pct(r.get('model_confidence'))} edge={_fmt_num(r.get('edge'))} z={_fmt_num(r.get('z_score'))}"
            )
        lines.append("")

    lines.append("FILES")
    lines.append("-" * 78)
    lines.append("- outputs/governance_config.json")
    lines.append("- outputs/allowed_edges.json")
    lines.append("- outputs/blocked_edges.json")
    lines.append("(These are the stable 'latest' artifacts.)")

    # Keep the summary readable in terminals and editors.
    if max_lines and len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["... (truncated)"]

    return "\n".join(lines) + "\n"


def _edge_id(r: dict) -> str:
    """Stable-ish ID for a single edge/result row."""
    player = str(r.get("player", "")).strip()
    team = str(r.get("team", "")).strip()
    opp = str(r.get("opponent", "")).strip()
    stat = str(r.get("stat", "")).strip()
    direction = str(r.get("direction", "")).strip()
    line = r.get("line", "")
    key = f"{player}|{team}|{opp}|{stat}|{direction}|{line}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _compact_row(r: dict) -> dict:
    """Compact, audit-friendly row.

    Keeps the evidence needed for "blocked/allowed + reasons", plus the
    "expected output tonight" fields (mu/sigma).
    """
    return {
        "edge_id": _edge_id(r),
        "player": r.get("player"),
        "team": r.get("team"),
        "opponent": r.get("opponent"),
        "stat": r.get("stat"),
        "line": r.get("line"),
        "direction": r.get("direction"),
        "decision": r.get("decision"),
        "status": r.get("status", r.get("decision")),
        "model_confidence": r.get("model_confidence"),
        "effective_confidence": r.get("effective_confidence"),
        "mu": r.get("mu"),
        "sigma": r.get("sigma"),
        "edge": r.get("edge"),
        "z_score": r.get("z_score"),
        "edge_quality": r.get("edge_quality"),
        "prob_method": r.get("prob_method"),
        "sample_n": r.get("sample_n"),
        "minutes_cv": r.get("minutes_cv"),
        "context_notes": r.get("context_notes", []),
        "context_warnings": r.get("context_warnings", []),
        "block_reason": r.get("block_reason") or r.get("reason"),
        "gate_details": r.get("gate_details", []),
        "stat_adjustment": r.get("stat_adjustment"),
    }


def _player_matrix(results: list[dict]) -> list[dict]:
    """Per-player view:

    - allowed_stats
    - blocked_stats
    - block_reasons (by stat)
    - prediction_allowed
    """
    by_player: dict[str, dict] = {}

    for r in results:
        if not isinstance(r, dict):
            continue
        player = str(r.get("player", "")).strip() or "UNKNOWN"
        stat = str(r.get("stat", "")).strip() or "UNKNOWN"
        decision = str(r.get("decision", "")).strip().upper()

        entry = by_player.setdefault(
            player,
            {
                "player": player,
                "team": r.get("team"),
                "opponent": r.get("opponent"),
                "allowed_stats": [],
                "blocked_stats": [],
                "block_reasons": {},  # stat -> reason
            },
        )

        if decision in {"BLOCKED", "SKIP"}:
            entry["blocked_stats"].append(stat)
            entry["block_reasons"][stat] = r.get("block_reason") or r.get("reason") or "Blocked"
        else:
            entry["allowed_stats"].append(stat)

    out: list[dict] = []
    for _, d in sorted(by_player.items(), key=lambda kv: kv[0].lower()):
        d["allowed_stats"] = sorted(set(d["allowed_stats"]))
        d["blocked_stats"] = sorted(set(d["blocked_stats"]))
        d["prediction_allowed"] = bool(d["allowed_stats"])
        out.append(d)

    return out


def export_governance_artifacts(
    analysis: dict,
    *,
    slug: str,
    stamp: str,
    out_dir: Path,
    run_settings: Optional[object] = None,
    source: Optional[dict] = None,
) -> dict[str, Path]:
    """Write governance artifacts (stable latest + timestamped audit copies)."""
    created_at = _utc_now_iso()

    results = analysis.get("results", []) if isinstance(analysis, dict) else []
    if not isinstance(results, list):
        results = []

    allowed_rows: list[dict] = []
    blocked_rows: list[dict] = []

    for r in results:
        if not isinstance(r, dict):
            continue
        decision = str(r.get("decision", "")).strip().upper()
        row = _compact_row(r)
        if decision in {"BLOCKED", "SKIP"}:
            blocked_rows.append(row)
        else:
            allowed_rows.append(row)

    # Settings snapshot (auditable)
    settings_payload: dict[str, Any] = {}
    try:
        if run_settings is not None:
            # is_dataclass() returns True for both dataclass instances AND dataclass types.
            # We only want to serialize instances here.
            if is_dataclass(run_settings) and not isinstance(run_settings, type):
                settings_payload = asdict(run_settings)
            elif hasattr(run_settings, "__dict__"):
                settings_payload = dict(run_settings.__dict__)
    except Exception:
        settings_payload = {}

    cfg = {
        "schema_version": "governance_artifacts.v1",
        "created_at_utc": created_at,
        "slug": slug,
        "stamp": stamp,
        "pipeline_steps_executed": [
            "raw_txt (inputs/*.txt)",
            "parse_underdog_slate -> parsed JSON",
            "risk_first_analyzer.analyze_slate (probability + gates + context gates)",
            "export: governance_config.json",
            "export: allowed_edges.json",
            "export: blocked_edges.json",
        ],
        "counts": {
            "total_results": len(results),
            "allowed_edges": len(allowed_rows),
            "blocked_edges": len(blocked_rows),
        },
        "run_settings": settings_payload,
        "source": source or {},
        "by_player": _player_matrix(results),
    }

    out_dir.mkdir(parents=True, exist_ok=True)

    # Stable latest outputs
    cfg_latest = out_dir / "governance_config.json"
    allowed_latest = out_dir / "allowed_edges.json"
    blocked_latest = out_dir / "blocked_edges.json"
    summary_latest = out_dir / "governance_summary.txt"

    _write_json(cfg_latest, cfg)
    _write_json(allowed_latest, {"created_at_utc": created_at, "edges": allowed_rows})
    _write_json(blocked_latest, {"created_at_utc": created_at, "edges": blocked_rows})

    summary_text = _render_governance_summary(
        slug=slug,
        stamp=stamp,
        created_at_utc=created_at,
        results=results,
        allowed_rows=allowed_rows,
        blocked_rows=blocked_rows,
        source=source or {},
    )
    _write_text(summary_latest, summary_text)

    # Timestamped copies
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cfg_ts = out_dir / f"{slug}_GOVERNANCE_CONFIG_{stamp}_{ts}.json"
    allowed_ts = out_dir / f"{slug}_ALLOWED_EDGES_{stamp}_{ts}.json"
    blocked_ts = out_dir / f"{slug}_BLOCKED_EDGES_{stamp}_{ts}.json"
    summary_ts = out_dir / f"{slug}_GOVERNANCE_SUMMARY_{stamp}_{ts}.txt"

    _write_json(cfg_ts, cfg)
    _write_json(allowed_ts, {"created_at_utc": created_at, "edges": allowed_rows})
    _write_json(blocked_ts, {"created_at_utc": created_at, "edges": blocked_rows})
    _write_text(summary_ts, summary_text)

    return {
        "governance_config": cfg_latest,
        "allowed_edges": allowed_latest,
        "blocked_edges": blocked_latest,
        "governance_summary": summary_latest,
        "governance_config_timestamped": cfg_ts,
        "allowed_edges_timestamped": allowed_ts,
        "blocked_edges_timestamped": blocked_ts,
        "governance_summary_timestamped": summary_ts,
    }
