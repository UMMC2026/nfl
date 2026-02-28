"""compare_prob_methods_calibration.py

Before/after-style report for probability math changes.

This runs the same slate through `risk_first_analyzer.analyze_slate` using
multiple RISK_PROB_METHOD values and prints a compact, auditable summary.

Typical use:
- python compare_prob_methods_calibration.py nyk_gsw_full_slate_20260115.json --label NYK_GSW

Interpretation:
- Treat `empirical` as the legacy baseline (roughly old auto behavior).
- Treat `auto` as the upgraded router.

This script does not require outcomes and does not write back to any history.
It only reads the slate and writes a report file under outputs/.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from risk_first_analyzer import analyze_slate


def _load_plays(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("plays"), list):
        return list(raw["plays"])
    if isinstance(raw, list):
        return list(raw)
    raise ValueError(f"Unrecognized slate format in {path}")


def _summarize(out: dict) -> dict:
    return {
        "total_props": int(out.get("total_props", 0)),
        "skip": int(out.get("skip", 0)),
        "blocked": int(out.get("blocked", 0)),
        "no_play": int(out.get("no_play", 0)),
        "lean": int(out.get("lean", 0)),
        "play": int(out.get("play", 0)),
    }


def _mean(xs: list[float]) -> float:
    if not xs:
        return 0.0
    return float(sum(xs) / len(xs))


def _extract_metrics(results: list[dict[str, Any]]) -> dict:
    method_counts: Counter[str] = Counter()
    conf_all: list[float] = []
    conf_play_lean: list[float] = []

    boot_widths: list[float] = []
    boot_guarded = 0

    for r in results:
        if not isinstance(r, dict):
            continue

        pm = str(r.get("prob_method", ""))
        if pm:
            method_counts[pm] += 1

        mc = r.get("model_confidence")
        if isinstance(mc, (int, float)):
            conf_all.append(float(mc))

        dec = str(r.get("decision", ""))
        if dec in {"PLAY", "LEAN"} and isinstance(mc, (int, float)):
            conf_play_lean.append(float(mc))

        pd = r.get("prob_method_details")
        if isinstance(pd, dict):
            bb = pd.get("bootstrap_band")
            if isinstance(bb, dict) and isinstance(bb.get("width"), (int, float)):
                boot_widths.append(float(bb["width"]))
            if isinstance(pd.get("bootstrap_guard_factor"), (int, float)):
                boot_guarded += 1

    return {
        "used_method_counts": dict(method_counts),
        "model_conf_mean": _mean(conf_all),
        "model_conf_mean_play_lean": _mean(conf_play_lean),
        "bootstrap_width_mean": _mean(boot_widths),
        "bootstrap_guarded": int(boot_guarded),
    }


def _format_counts(d: dict[str, int]) -> str:
    if not d:
        return "(none)"
    parts = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join([f"{k}={v}" for k, v in parts])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slate", type=str, help="Path to slate JSON (Underdog parsed plays or list)")
    ap.add_argument("--label", type=str, default="", help="Optional label for output filename")
    args = ap.parse_args()

    slate_path = Path(args.slate)
    plays = _load_plays(slate_path)

    methods = [
        "empirical",  # baseline / legacy-ish
        "empirical_hybrid",
        "wilson_empirical",
        "negbin",
        "normal_cdf",
        "auto",  # upgraded router
    ]

    ctx: dict = {}

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label = args.label.strip() or slate_path.stem
    out_dir = Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"PROB_METHOD_REPORT_{label}_{ts}.txt"

    lines: list[str] = []
    lines.append("=" * 90)
    lines.append(f"PROBABILITY METHOD REPORT: {label}")
    lines.append(f"Slate: {slate_path}")
    lines.append(f"UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("=")
    lines.append("")

    baselines: dict[str, dict] = {}

    for m in methods:
        os.environ["RISK_PROB_METHOD"] = m
        out = analyze_slate(plays, verbose=False, game_context=ctx)

        s = _summarize(out)
        metrics = _extract_metrics(list(out.get("results", []) or []))
        baselines[m] = {"summary": s, "metrics": metrics}

        lines.append(f"RISK_PROB_METHOD={m}")
        lines.append("-" * (len(lines[-1])))
        lines.append(
            f"Total={s['total_props']}  SKIP={s['skip']}  BLOCKED={s['blocked']}  "
            f"NO_PLAY={s['no_play']}  LEAN={s['lean']}  PLAY={s['play']}"
        )
        lines.append(f"Mean model_confidence: {metrics['model_conf_mean']:.2f}%")
        lines.append(f"Mean model_confidence (PLAY/LEAN): {metrics['model_conf_mean_play_lean']:.2f}%")
        lines.append(f"Used methods: {_format_counts(metrics['used_method_counts'])}")
        lines.append(
            f"Bootstrap: mean_width={metrics['bootstrap_width_mean']:.2f}pp  guarded={metrics['bootstrap_guarded']} picks"
        )
        lines.append("")

    # Before/after: empirical (baseline) vs auto (router)
    if "empirical" in baselines and "auto" in baselines:
        b = baselines["empirical"]["summary"]
        a = baselines["auto"]["summary"]
        lines.append("=" * 90)
        lines.append("BEFORE/AFTER (baseline=empirical, after=auto)")
        lines.append("=" * 90)
        for k in ("play", "lean", "no_play", "blocked", "skip"):
            lines.append(f"{k.upper():7s}: {b[k]}  ->  {a[k]}   (delta {a[k] - b[k]:+d})")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
