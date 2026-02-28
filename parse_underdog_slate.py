#!/usr/bin/env python3
"""Parse Underdog Fantasy slate text into JSON format."""

import json
import re
from datetime import date
import argparse

from ufa.utils.player_exclusions import is_excluded_player

# Paste the raw slate text here
SLATE_TEXT = """
[PASTE YOUR SLATE HERE]
"""

def parse_underdog_slate(text):
    """Parse Underdog slate text into structured JSON."""
    
    plays = []
    current_game = None
    current_player = None
    current_team = None
    current_opponent = None
    expect_player_name = False
    skip_current_player = False
    
    lines = text.strip().split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()

        if not line:
            continue

        # Explicit player marker from Underdog UI
        if "athlete or team avatar" in line:
            expect_player_name = True
            continue

        # Detect team line shown directly under the player name in many Underdog pastes
        # e.g. "LAL - F-G", "SAS - F-C", "UTA - C"
        if re.match(r"^[A-Z]{2,3}\s*-\s*", line):
            m_team = re.match(r"^([A-Z]{2,3})\s*-\s*", line)
            if m_team:
                current_team = m_team.group(1)
            continue
        
        # Detect game matchup (e.g., "PHX @ MIA" or "DET vs PHX")
        # Some pastes include timezones ("- 6:00PM CST"), others include day/time without timezone.
        if ('@' in line or 'vs' in line) and re.search(r"\b[A-Z]{2,3}\b", line):
            match_at = re.search(r'([A-Z]{3})\s*@\s*([A-Z]{3})', line)
            match_vs = re.search(r'([A-Z]{3})\s+vs\s+([A-Z]{3})', line)
            if match_at:
                current_game = {
                    'away': match_at.group(1),
                    'home': match_at.group(2)
                }
                # Best-effort opponent for player card lines.
                if current_team:
                    current_opponent = match_at.group(2) if current_team == match_at.group(1) else match_at.group(1)
            elif match_vs:
                # We only need the set of teams for sanity checks; treat the first team as "home".
                current_game = {
                    'away': match_vs.group(2),
                    'home': match_vs.group(1)
                }
                if current_team:
                    current_opponent = match_vs.group(2) if current_team == match_vs.group(1) else match_vs.group(1)
        
        # Detect player name (only immediately after the explicit marker)
        if expect_player_name:
            # e.g., "Devin Booker"
            current_player = line
            current_team = None
            current_opponent = None
            expect_player_name = False
            skip_current_player = is_excluded_player(current_player)
            continue

        # Heuristic for multi-player pastes that don't include the explicit marker:
        #   <PlayerName>[Demon|Goblin|Taco]
        #   <TEAM> - <POS>
        # This can occur even when we're already inside another player's section.
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if re.match(r"^[A-Z]{2,3}\s*-\s*", next_line) and not re.search(r"\d", line):
            if line.lower() not in {"trending"}:
                # Strip common suffix tags even when they are appended without a space.
                m = re.search(r"(goblin|demon|taco)\s*$", line, flags=re.IGNORECASE)
                if m:
                    line = re.sub(r"(goblin|demon|taco)\s*$", "", line, flags=re.IGNORECASE).strip()

                if current_player != line:
                    current_player = line
                    current_team = None
                    current_game = None
                    current_opponent = None
                    skip_current_player = is_excluded_player(current_player)
                    continue
        
        # Detect team context from matchup line (older UI paste format)
        if current_player and ('vs' in line or '@' in line) and re.search(r"\b[A-Z]{2,3}\b", line):
            # e.g., "PHX @ DET - 6:00PM CST" or "DET vs PHX - 6:00PM CST"
            match_vs = re.search(r'([A-Z]{3})\s+vs\s+([A-Z]{3})', line)
            if match_vs:
                current_team = match_vs.group(1)
                current_opponent = match_vs.group(2)
            else:
                match_at = re.search(r'([A-Z]{3})\s+@\s+([A-Z]{3})', line)
                if match_at:
                    # In the Underdog UI, player cards commonly show their team first in "TEAM @ OPP".
                    current_team = match_at.group(1)
                    current_opponent = match_at.group(2)
        
        # Detect stat lines (number followed by stat name)
        # Most pastes include a clean numeric line (e.g. "22.5"). Some Windows pastes occasionally
        # concatenate two numeric lines (e.g. "31.524.5"); in that case, take the first value.
        stat_value = None
        if re.match(r'^\d+\.?\d*$', line):
            stat_value = float(line)
        elif line.count('.') == 2 and re.match(r'^\d+\.\d+\d+\.\d+$', line):
            # Heuristic: split after the first decimal digit (common: X.YZ.W)
            dot = line.find('.')
            cut = dot + 2
            try:
                stat_value = float(line[:cut])
            except Exception:
                stat_value = None

        if stat_value is not None:

            # Hard exclude certain players from ever entering analysis.
            if skip_current_player:
                continue
            # Next line should be the stat name
            if i + 1 < len(lines):
                stat_name = lines[i + 1].strip()
                
                # Check for Higher/Lower on subsequent lines
                has_higher = False
                has_lower = False
                
                for j in range(i + 2, min(i + 10, len(lines))):
                    check_line = lines[j].strip()
                    # Underdog uses "Higher/Lower" in some views and "More/Less" in others.
                    if 'Higher' in check_line or check_line.lower() == 'more':
                        has_higher = True
                    if 'Lower' in check_line or check_line.lower() == 'less':
                        has_lower = True
                    if re.match(r'^\d+\.?\d*$', check_line):  # Next stat
                        break
                
                # Map stat names
                stat_key = map_stat_name(stat_name)
                
                if current_player and current_team and stat_key:
                    matchup_away = current_game.get('away') if current_game else None
                    matchup_home = current_game.get('home') if current_game else None

                    # Best-effort opponent derived from matchup
                    opponent = current_opponent
                    if (not opponent) and matchup_away and matchup_home:
                        opponent = matchup_home if current_team == matchup_away else matchup_away

                    if has_higher:
                        plays.append({
                            'player': current_player,
                            'team': current_team,
                            'opponent': opponent or 'UNK',
                            'stat': stat_key,
                            'line': stat_value,
                            'direction': 'higher',
                            'matchup_away': matchup_away,
                            'matchup_home': matchup_home,
                        })
                    if has_lower:
                        plays.append({
                            'player': current_player,
                            'team': current_team,
                            'opponent': opponent or 'UNK',
                            'stat': stat_key,
                            'line': stat_value,
                            'direction': 'lower',
                            'matchup_away': matchup_away,
                            'matchup_home': matchup_home,
                        })
    
    return {
        'date': date.today().isoformat(),
        'league': 'NBA',
        'plays': plays
    }

def map_stat_name(stat_name):
    """Map Underdog stat names to our format."""
    s = (stat_name or "").strip().lower()

    # Explicitly skip markets we do not model (to avoid mis-parsing them as full-game points).
    if any(
        k in s
        for k in [
            "1q",
            "1h",
            "first 5",
            "fantasy",
            "fg attempted",
            "ft made",
            "3s attempted",
            "double doubles",
            "triple doubles",
            "offensive rebounds",
            "blocks + steals",
        ]
    ):
        return None

    # Core modeled stats (exact match)
    if s == "points":
        return "points"
    if s == "rebounds":
        return "rebounds"
    if s == "assists":
        return "assists"
    if s in {"3-pointers made", "3-pointers"}:
        return "3pm"
    if s == "turnovers":
        return "turnovers"

    # Composite stats (we can parse them, but the risk gates may block them)
    if s == "pts + rebs + asts":
        return "pra"
    if s == "points + rebounds":
        return "pts+reb"
    if s == "points + assists":
        return "pts+ast"
    if s == "rebounds + assists":
        return "reb+ast"

    return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Parse pasted Underdog slate text to JSON")
    parser.add_argument("--output", default="nba_tonight_slate.json", help="Output JSON filename")
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()

    print("Paste your Underdog slate below, then press Ctrl+Z (Windows) or Ctrl+D (Unix), then Enter:")
    print()

    # Read from stdin
    import sys
    slate_text = sys.stdin.read()

    result = parse_underdog_slate(slate_text)
    if args.date:
        result["date"] = args.date

    output_file = args.output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    print(f"\nParsed {len(result['plays'])} props")
    print(f"Saved to: {output_file}")
