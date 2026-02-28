"""
parse_nba_slate.py

Parses raw NBA prop lines (as pasted from Underdog/PrizePicks) into structured JSON for analysis.
"""
import re
import json
from collections import defaultdict

RAW_FILE = "nba_slate_raw.txt"  # Save your pasted slate here
OUT_FILE = "nba_slate_structured.json"

# Regex patterns for props
PROP_PATTERNS = [
    (re.compile(r"([\d\.]+)\s*Points"), "points"),
    (re.compile(r"([\d\.]+)\s*Rebounds"), "rebounds"),
    (re.compile(r"([\d\.]+)\s*Assists"), "assists"),
    (re.compile(r"([\d\.]+)\s*Pts \+ Rebs \+ Asts"), "pra"),
    (re.compile(r"([\d\.]+)\s*3-Pointers Made"), "threes"),
    (re.compile(r"([\d\.]+)\s*Points \+ Rebounds"), "points_rebounds"),
]

MULTIPLIER_PATTERN = re.compile(r"(Higher|Lower)\s*([\d\.]+x)?")


def parse_slate(raw_lines):
    players = []
    current = None
    for line in raw_lines:
        line = line.strip()
        # Player header
        if line and not any(x in line for x in ["Points", "Rebounds", "Assists", "3-Pointers", "Pts + Rebs + Asts", "Points + Rebounds"]):
            if current:
                players.append(current)
            current = {"name": line, "props": []}
            continue
        # Prop lines
        for pat, prop_type in PROP_PATTERNS:
            m = pat.match(line)
            if m:
                value = float(m.group(1))
                current_prop = {"type": prop_type, "line": value, "higher": None, "lower": None}
                current["props"].append(current_prop)
                break
        # Multiplier lines
        m = MULTIPLIER_PATTERN.match(line)
        if m and current and current["props"]:
            last_prop = current["props"][-1]
            if m.group(1) == "Higher":
                last_prop["higher"] = float(m.group(2)[:-1]) if m.group(2) else 1.0
            elif m.group(1) == "Lower":
                last_prop["lower"] = float(m.group(2)[:-1]) if m.group(2) else 1.0
    if current:
        players.append(current)
    return players


def main():
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()
    structured = parse_slate(raw_lines)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(structured, f, indent=2)
    print(f"Parsed {len(structured)} players. Output: {OUT_FILE}")

if __name__ == "__main__":
    main()
