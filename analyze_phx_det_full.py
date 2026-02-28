"""
PHX @ DET - 6:00PM CST
RISK-FIRST ANALYSIS WITH AI COMMENTARY

Input: phx_det_full_slate.json (generated via parse_underdog_slate.py)
"""

import json
from datetime import date

from risk_first_analyzer import analyze_slate, print_summary
from ai_commentary import generate_full_report


def main() -> None:
    slate_file = "phx_det_full_slate.json"

    # ai_commentary expects a dict-like game_context; use an empty dict when we don't have one.
    game_context: dict = {}

    with open(slate_file, encoding="utf-8") as f:
        slate = json.load(f)
        props = slate.get("plays", [])

    print("=" * 70)
    print("PHX @ DET - 6:00PM CST")
    print("RISK-FIRST ANALYSIS")
    print("=" * 70)
    print(f"Total props in slate: {len(props)}")
    print("=" * 70)
    print()

    results = analyze_slate(props, game_context=game_context)
    print_summary(results)

    stamp = date.today().strftime("%Y%m%d")

    out_json = f"outputs/PHX_DET_RISK_FIRST_{stamp}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nFull results saved to: {out_json}\n")

    print("Generating AI sports analysis & commentary...\n")
    ai_report = generate_full_report(results, game_context)

    out_txt = f"outputs/PHX_DET_AI_REPORT_{stamp}.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(ai_report)

    print(f"AI analysis report saved to: {out_txt}")


if __name__ == "__main__":
    main()
