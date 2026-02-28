"""
Fix player team assignments in ingested JSON files using live ESPN API data.
Run this BEFORE analysis to ensure players are on correct teams.
"""
import json
import sys
from pathlib import Path
import time
import re
import unicodedata
import argparse


_NAME_SUFFIX_TOKENS = {"jr", "sr", "ii", "iii", "iv", "v"}
_NAME_PREFIX_GLUE = ("more", "less", "privacy")


def _strip_known_prefixes(raw: str) -> str:
    """Strip common non-name prefixes sometimes glued onto player names.

    Examples seen in outputs:
    - 'MoreTyrese Maxey' -> 'Tyrese Maxey'
    - 'PrivacyJoel Embiid' -> 'Joel Embiid'
    - 'More Jerami Grant' -> 'Jerami Grant'
    """
    s = str(raw or "").strip()
    if not s:
        return s
    # Remove spaced prefixes first
    s2 = re.sub(r"^(more|less|privacy)\s+", "", s, flags=re.IGNORECASE).strip()
    if s2 != s:
        return s2

    # Remove glued prefixes (case-insensitive)
    low = s.lower()
    for p in _NAME_PREFIX_GLUE:
        if low.startswith(p) and len(s) > len(p):
            return s[len(p):].lstrip()
    return s


def _strip_suffix_tokens_from_normalized(norm: str) -> str:
    """Remove trailing suffix tokens (jr/sr/ii/iii/...) from a normalized name."""
    s = str(norm or "").strip()
    if not s:
        return s
    parts = s.split()
    while parts and parts[-1] in _NAME_SUFFIX_TOKENS:
        parts.pop()
    return " ".join(parts).strip()


def _collapse_leading_initial_tokens(norm: str) -> str:
    """Collapse leading single-letter tokens into one token.

    Examples:
    - 'c j mccollum' -> 'cj mccollum'
    - 'g g jackson' -> 'gg jackson'
    - 'p j washington' -> 'pj washington'
    """
    s = str(norm or "").strip()
    if not s:
        return s
    parts = s.split()
    if len(parts) < 2:
        return s
    i = 0
    initials = []
    while i < len(parts) and len(parts[i]) == 1 and parts[i].isalpha():
        initials.append(parts[i])
        i += 1
    if len(initials) >= 2:
        merged = ["".join(initials)] + parts[i:]
        return " ".join(merged).strip()
    return s


def _normalize_player_name(name: str) -> str:
    """Normalize a player name for robust matching.

    Handles:
    - diacritics (e.g., 'Nikola Jokić' -> 'nikola jokic')
    - punctuation (e.g., 'C.J. McCollum' -> 'cj mccollum')
    - whitespace normalization
    """
    try:
        s = _strip_known_prefixes(str(name or "")).strip().lower()
        if not s:
            return ""
        # Strip diacritics
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        # Replace punctuation with spaces (keep letters/numbers)
        s = re.sub(r"[^a-z0-9]+", " ", s)
        # Collapse whitespace
        s = re.sub(r"\s+", " ", s).strip()
        return s
    except Exception:
        return str(name or "").strip().lower()


def _console_safe(text: str) -> str:
    """Best-effort console-safe rendering for Windows cp1252 terminals.

    - strips diacritics
    - replaces any remaining non-cp1252 characters
    """
    try:
        s = str(text or "")
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        try:
            return s.encode("cp1252", errors="replace").decode("cp1252")
        except Exception:
            # Fallback: ASCII-only
            return s.encode("ascii", errors="replace").decode("ascii")
    except Exception:
        return str(text or "")

def get_player_team_map():
    """Build a map of player name -> team abbreviation from ESPN API (reliable, no blocking)."""
    print("[*] Fetching current NBA rosters from ESPN API...")
    
    try:
        # Use the fixed ESPN roster fetcher (never blocks, no auth required)
        from engine.roster_gate import build_active_roster_map
        
        roster_map = build_active_roster_map("NBA")
        
        if not roster_map:
            print("[!] Failed to fetch rosters (returned empty map)")
            return {"exact": {}, "norm": {}}
        
        # Map BOTH exact name and normalized name -> team
        player_teams_exact: dict[str, str] = {}
        player_teams_norm: dict[str, str] = {}
        
        for player_name, team_abbr in roster_map.items():
            # Store exact name
            player_teams_exact[player_name] = team_abbr
            
            # Store normalized variants for robust matching
            key_full = _normalize_player_name(player_name)
            if key_full:
                # Full normalized
                player_teams_norm[key_full] = team_abbr

                # Initial-collapsed variant (CJ/GG/PJ/...) for robustness
                key_initials = _collapse_leading_initial_tokens(key_full)
                if key_initials and key_initials != key_full:
                    player_teams_norm[key_initials] = team_abbr

                # Suffix-stripped variants
                key_stripped = _strip_suffix_tokens_from_normalized(key_full)
                if key_stripped and key_stripped != key_full:
                    # Index without suffix so 'Jaime Jaquez' matches roster 'Jaime Jaquez Jr'
                    player_teams_norm[key_stripped] = team_abbr
                    key_stripped_initials = _collapse_leading_initial_tokens(key_stripped)
                    if key_stripped_initials and key_stripped_initials != key_stripped:
                        player_teams_norm[key_stripped_initials] = team_abbr
        
        print(
            f"[OK] Loaded {len(player_teams_exact)} active NBA players with team assignments "
            f"(normalized keys: {len(player_teams_norm)})"
        )
        return {"exact": player_teams_exact, "norm": player_teams_norm}
    
    except Exception as e:
        print(f"[!] Error fetching rosters: {e}")
        import traceback
        traceback.print_exc()
        return {"exact": {}, "norm": {}}

def fix_json_file(file_path: Path, player_teams: dict):
    """Update team assignments in a single JSON file."""
    print(f"\n[*] Processing: {file_path.name}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Failed to read {file_path}: {e}")
        return 0
    
    # Handle both list and dict formats
    # - Risk-first output: dict with 'results'
    # - Slate input: dict with 'plays' (or sometimes 'picks')
    # - Old format: flat list of props
    if isinstance(data, dict) and 'results' in data:
        props = data['results']
    elif isinstance(data, dict) and 'plays' in data:
        props = data['plays']
    elif isinstance(data, dict) and 'picks' in data:
        props = data['picks']
    elif isinstance(data, list):
        props = data
    else:
        props = data.get('props', []) if isinstance(data, dict) else []
    
    updated_count = 0
    # Reduce noise: only print each player's action once per file.
    printed_updates = set()
    printed_unknowns = set()

    exact_map = {}
    norm_map = {}
    if isinstance(player_teams, dict):
        exact_map = player_teams.get("exact") if isinstance(player_teams.get("exact"), dict) else {}
        norm_map = player_teams.get("norm") if isinstance(player_teams.get("norm"), dict) else {}
    for prop in props:
        player = prop.get('player')
        if not player:
            continue

        player_str = str(player)
        player_norm = _normalize_player_name(player_str)
        player_norm_initials = _collapse_leading_initial_tokens(player_norm)
        player_norm_stripped = _strip_suffix_tokens_from_normalized(player_norm)
        player_norm_stripped_initials = _collapse_leading_initial_tokens(player_norm_stripped)

        # Resolve team from exact or normalized lookup
        new_team = None
        # Resolve team from exact or normalized lookup
        # Try: exact -> normalized -> suffix-stripped normalized
        if player_str in exact_map:
            new_team = exact_map[player_str]
        elif player_norm and player_norm in norm_map:
            new_team = norm_map[player_norm]
        elif player_norm_initials and player_norm_initials in norm_map:
            new_team = norm_map[player_norm_initials]
        elif player_norm_stripped and player_norm_stripped in norm_map:
            new_team = norm_map[player_norm_stripped]
        elif player_norm_stripped_initials and player_norm_stripped_initials in norm_map:
            new_team = norm_map[player_norm_stripped_initials]

        # Check if player exists in NBA
        if new_team:
            old_team = prop.get('team', 'UNK')
            
            if old_team != new_team:
                prop['team'] = new_team
                updated_count += 1
                if player_str not in printed_updates:
                    print(f"  OK {_console_safe(player_str)}: {old_team} -> {new_team}")
                    printed_updates.add(player_str)
        else:
            # Mark unknown players (college players, etc.)
            # IMPORTANT: Do NOT overwrite a non-UNK team to UNK based on a failed lookup.
            # The NBA API sometimes uses diacritics/punctuation variants; we also don't want to
            # clobber other-sport slates.
            cur_team = prop.get('team', 'UNK')
            if cur_team == 'UNK' or cur_team is None:
                # Keep as UNK; just log once.
                if player_str not in printed_unknowns:
                    print(f"  WARN {_console_safe(player_str)}: Not found in NBA roster map (leaving team=UNK)")
                    printed_unknowns.add(player_str)
            else:
                if player_str not in printed_unknowns:
                    print(f"  WARN {_console_safe(player_str)}: Not found in NBA roster map (leaving team={cur_team})")
                    printed_unknowns.add(player_str)
    
    # Write back
    if updated_count > 0:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"[OK] Updated {updated_count} player teams in {file_path.name}")
        except Exception as e:
            print(f"[!] Failed to write {file_path}: {e}")
            return 0
    else:
        print(f"[NOOP] No updates needed for {file_path.name}")
    
    return updated_count

def main():
    """Fix player teams in all recent JSON files."""
    print("=" * 70)
    print("  FIX PLAYER TEAM ASSIGNMENTS")
    print("=" * 70)

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--file", default=None, help="Optional: single JSON file to update (slate or risk-first output)")
    ap.add_argument("--limit", type=int, default=20, help="When --file is not set: how many recent outputs to process")
    args, _ = ap.parse_known_args()
    
    # Get live player-team map
    player_teams = get_player_team_map()
    
    # If a target file is provided, update it directly.
    if args.file:
        target = Path(args.file)
        if not target.is_file():
            print(f"\n[!] File not found: {target}")
            return
        count = fix_json_file(target, player_teams)
        print("\n" + "=" * 70)
        print(f"[OK] Complete! Updated {count} player team assignments")
        print("=" * 70)
        return

    # Find all recent JSON files (relative to this script, not CWD)
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    json_files = sorted(outputs_dir.glob("*FROM_UD.json"), reverse=True)[: max(0, int(args.limit))]
    
    if not json_files:
        print("\n[!] No JSON files found in outputs/")
        return
    
    print(f"\n[*] Found {len(json_files)} recent JSON files to process\n")
    
    total_updated = 0
    for json_file in json_files:
        count = fix_json_file(json_file, player_teams)
        total_updated += count
    
    print("\n" + "=" * 70)
    print(f"[OK] Complete! Updated {total_updated} total player team assignments")
    print("=" * 70)

if __name__ == "__main__":
    main()
