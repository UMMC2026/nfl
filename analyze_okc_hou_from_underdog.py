"""
OKC @ HOU - 6:30PM CST
RISK-FIRST ANALYSIS (from pasted Underdog text)

Input: okc_hou_full_slate.json (generated via parse_underdog_slate.py)
Uses: game_context_okc_hou.json if present (optional)
"""

import json
from datetime import date
from pathlib import Path

from risk_first_analyzer import analyze_slate, print_summary
from ai_commentary import generate_full_report


def _load_optional_game_context() -> dict:
    p = Path("game_context_okc_hou.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    slate_file = "okc_hou_full_slate.json"

    with open(slate_file, encoding="utf-8") as f:
        slate = json.load(f)
        props = slate.get("plays", [])

    game_context = _load_optional_game_context()

    print("=" * 70)
    print("OKC @ HOU - 6:30PM CST")
    print("RISK-FIRST ANALYSIS")
    print("=" * 70)
    print(f"Total props in slate: {len(props)}")
    print("=" * 70)
    print()

    results = analyze_slate(props, game_context=game_context)
    print_summary(results)

    stamp = date.today().strftime("%Y%m%d")

    out_json = f"outputs/OKC_HOU_RISK_FIRST_{stamp}_FROM_UD.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nFull results saved to: {out_json}\n")

    print("Generating AI sports analysis & commentary...\n")
    ai_report = generate_full_report(results, game_context)

    out_txt = f"outputs/OKC_HOU_AI_REPORT_{stamp}_FROM_UD.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(ai_report)

    print(f"AI analysis report saved to: {out_txt}")


if __name__ == "__main__":
    main()
