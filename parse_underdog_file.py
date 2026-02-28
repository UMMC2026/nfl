"""parse_underdog_file.py

Small helper to parse a saved Underdog paste (raw text) into the JSON schema
expected by the risk-first analyzer.

This exists so we can keep raw pastes in versioned files under inputs/ and
re-run parsing deterministically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from parse_underdog_slate import parse_underdog_slate


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse a raw Underdog slate text file into JSON")
    ap.add_argument("--input", required=True, help="Path to raw text file")
    ap.add_argument("--output", required=True, help="Output JSON path")
    ap.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
    args = ap.parse_args()

    raw_path = Path(args.input)
    text = raw_path.read_text(encoding="utf-8", errors="replace")

    parsed = parse_underdog_slate(text)
    if args.date:
        parsed["date"] = args.date

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    print(f"Parsed {len(parsed.get('plays', []))} props")
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
