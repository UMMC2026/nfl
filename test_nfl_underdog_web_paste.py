r"""Quick regression test for Underdog NFL web multi-line paste parsing.

Run:
  .venv\Scripts\python.exe test_nfl_underdog_web_paste.py

This is not a pytest suite; it's a lightweight sanity check so we don't
break parsing when Underdog changes the UI copy format again.
"""

from __future__ import annotations

from nfl_menu import parse_nfl_lines
from nfl_menu import _normalize_underdog_web_to_single_lines


SAMPLE = """
13h 59m
Trending
496.4K
Sam DarnoldMoney Mouth
SEA - QB
Sam Darnold
vs LA Sun 5:32pm
235.50.5
Pass Yards
More

Trending
46.3K
Drake Maye
NE - QB
Drake Maye
@ DEN Sun 2:00pm

226.5
Pass Yards
Less
More

Privacy
END
""".strip()


def main() -> None:
  raw_lines = SAMPLE.splitlines()
  normalized = _normalize_underdog_web_to_single_lines(raw_lines)
  print("=" * 70)
  print(f"Normalizer produced: {len(normalized)} single-line candidate(s)")
  for s in normalized:
    print(f"  >> {s}")

    picks = parse_nfl_lines(SAMPLE)
    print("=" * 70)
    print(f"Parsed picks: {len(picks)}")
    for p in picks[:10]:
        print(f"  - {p.get('player')} | {p.get('team')} | {p.get('position')} | {p.get('stat')} | {p.get('line')} | {p.get('direction')}")


if __name__ == "__main__":
    main()
