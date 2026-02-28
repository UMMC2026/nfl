"""analyze_nyk_gsw_from_underdog.py

NYK @ GSW - 9:00PM CST
RISK-FIRST ANALYSIS (from pasted Underdog text)

Inputs:
- nyk_gsw_full_slate.json (generated via parse_underdog_file.py)

Outputs:
- outputs/NYK_GSW_RISK_FIRST_<YYYYMMDD>_FROM_UD.json
- outputs/NYK_GSW_AI_REPORT_<YYYYMMDD>_FROM_UD.txt

Notes:
- Uses risk-first analyzer (gates -> probability -> decision).
- Exports standardized signals to output/signals_latest.json.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from ai_commentary import generate_full_report
from balanced_report import build_balanced_team_report
from risk_first_analyzer import analyze_slate, print_summary


def main() -> None:
    slate_file = "nyk_gsw_full_slate.json"

    with open(slate_file, encoding="utf-8") as f:
        slate = json.load(f)
    props = slate.get("plays", [])

    print("=" * 70)
    print("NYK @ GSW - 9:00PM CST")
    print("RISK-FIRST ANALYSIS")
    print("=" * 70)
    print(f"Total props in slate: {len(props)}")
    print("=" * 70)
    print()

    # Optional context hook. Provide a dict here if you build a game_context file.
    game_context: dict = {}

    results = analyze_slate(props, game_context=game_context)
    print_summary(results)

    stamp = date.today().strftime("%Y%m%d")

    Path("outputs").mkdir(parents=True, exist_ok=True)

    out_json = f"outputs/NYK_GSW_RISK_FIRST_{stamp}_FROM_UD.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nFull results saved to: {out_json}\n")

    if os.getenv("GENERATE_AI_REPORT", "0").strip() == "1":
        print("Generating AI sports analysis & commentary...\n")
        report = generate_full_report(results, game_context=game_context)

        out_txt = f"outputs/NYK_GSW_AI_REPORT_{stamp}_FROM_UD.txt"
        with open(out_txt, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"AI analysis report saved to: {out_txt}")
    else:
        print("AI report: disabled (set GENERATE_AI_REPORT=1 to enable).")

    # Optional balanced report (top 5 per team) for operator visibility.
    try:
        if os.getenv("BALANCED_REPORT", "0").strip() == "1":
            rpt = build_balanced_team_report(results, top_n=5)
            rpt_path = Path("outputs") / f"NYK_GSW_BALANCED_{date.today().strftime('%Y%m%d')}.txt"
            rpt_path.write_text(rpt, encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
