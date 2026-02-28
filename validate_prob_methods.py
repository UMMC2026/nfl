"""validate_prob_methods.py

Quick validation harness for probability math changes.

Runs the SAME slate through risk_first_analyzer using different probability
methods and prints a delta summary.

Usage (examples):
- python validate_prob_methods.py okc_hou_full_slate.json
- python validate_prob_methods.py bos_mia_full_slate.json
- python validate_prob_methods.py okc_hou_full_slate.json bos_mia_full_slate.json

Notes:
- Uses environment variable RISK_PROB_METHOD with values:
    auto (default): disciplined router (hybrid/wilson/negbin/normal fallback)
    empirical: empirical hit rate (series) else normal fallback
    empirical_hybrid: empirical + margin hybrid (series) else normal fallback
    wilson_empirical: Wilson-lower-bound empirical (series) else normal fallback
    negbin: negative binomial count-process (series moments or parametric) else normal fallback
    normal_cdf: force normal cdf

- This script does not write outputs/ files; it just prints counts.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from risk_first_analyzer import analyze_slate


def _load_plays(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("plays"), list):
        return list(raw["plays"])
    if isinstance(raw, list):
        return list(raw)
    raise ValueError(f"Unrecognized slate format in {path}")


def _summarize(results: dict) -> dict:
    return {
        "total_props": int(results.get("total_props", 0)),
        "play": int(results.get("play", 0)),
        "lean": int(results.get("lean", 0)),
        "no_play": int(results.get("no_play", 0)),
        "blocked": int(results.get("blocked", 0)),
        "skip": int(results.get("skip", 0)),
    }


def _print_summary(label: str, s: dict) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Total:   {s['total_props']}")
    print(f"SKIP:    {s['skip']}")
    print(f"BLOCKED: {s['blocked']}")
    print(f"NO_PLAY: {s['no_play']}")
    print(f"LEAN:    {s['lean']}")
    print(f"PLAY:    {s['play']}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python validate_prob_methods.py <slate.json> [<slate2.json> ...]")
        return 2

    paths = [Path(a) for a in argv[1:]]
    props: list[dict] = []
    for p in paths:
        props.extend(_load_plays(p))

    # Keep context empty; we only want probability deltas.
    ctx: dict = {}

    for method in (
        "empirical",
        "empirical_hybrid",
        "wilson_empirical",
        "negbin",
        "normal_cdf",
        "auto",
    ):
        os.environ["RISK_PROB_METHOD"] = method
        out = analyze_slate(props, verbose=False, game_context=ctx)
        s = _summarize(out)
        _print_summary(f"RISK_PROB_METHOD={method}", s)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
