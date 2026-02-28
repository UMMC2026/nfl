"""analyze_okc_hou_bos_mia_from_underdog.py

Run a combined 2-game slate from parsed Underdog text:
- OKC @ HOU
- BOS @ MIA

Inputs:
- okc_hou_full_slate.json
- bos_mia_full_slate.json

Outputs:
- outputs/OKC_HOU_BOS_MIA_RISK_FIRST_<YYYYMMDD>_FROM_UD.json
- outputs/OKC_HOU_BOS_MIA_AI_REPORT_<YYYYMMDD>_FROM_UD.txt

Notes:
- Uses risk-first analyzer (gates -> probability -> decision).
- Exports standardized signals to output/signals_latest.json.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from risk_first_analyzer import analyze_slate, print_summary
from ai_commentary import generate_full_report


def _load_plays(path: str) -> list[dict]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    plays = data.get("plays", [])
    return [x for x in plays if isinstance(x, dict)]


def main() -> None:
    okc_hou = _load_plays("okc_hou_full_slate.json")
    bos_mia = _load_plays("bos_mia_full_slate.json")

    props = okc_hou + bos_mia

    print("=" * 70)
    print("OKC @ HOU + BOS @ MIA (6:30PM CST)")
    print("RISK-FIRST ANALYSIS (combined from pasted Underdog text)")
    print("=" * 70)
    print(f"Total props in slate: {len(props)}")
    print("=" * 70)
    print()

    # ai_commentary expects a dict-like context; keep empty unless you provide a specific game_context file.
    game_context: dict = {}

    results = analyze_slate(props, game_context=game_context)
    print_summary(results)

    stamp = date.today().strftime("%Y%m%d")

    out_json = f"outputs/OKC_HOU_BOS_MIA_RISK_FIRST_{stamp}_FROM_UD.json"
    Path("outputs").mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nFull results saved to: {out_json}\n")

    print("Generating AI sports analysis & commentary...\n")
    report = generate_full_report(results, game_context=game_context)

    out_txt = f"outputs/OKC_HOU_BOS_MIA_AI_REPORT_{stamp}_FROM_UD.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"AI analysis report saved to: {out_txt}")


if __name__ == "__main__":
    main()
