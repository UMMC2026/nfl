"""
Tennis Match Ingestion Module
=============================
Singles only. Pre-match only. Match Winner market only.

Data sources:
- Manual paste (primary)
- Tennis API (future)

Output: tennis/slates/{date}_matches.json
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Load .env from project root (best-effort). This is required for Odds API
# ingestion when launching from menus where env vars may not be preloaded.
try:
    from dotenv import load_dotenv  # type: ignore

    _PROJECT_ROOT = Path(__file__).resolve().parents[1]
    _ENV_PATH = _PROJECT_ROOT / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass


def _try_import_odds_api():
    """Best-effort import of the Odds API adapter.

    The adapter lives at `src/sources/odds_api.py`. Since `src/` is not
    necessarily installed as a package, we add it to sys.path at runtime.
    """

    try:
        import sys

        project_root = Path(__file__).resolve().parents[1]
        src_dir = project_root / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))

        from sources.odds_api import (  # type: ignore
            OddsApiClient,
            OddsApiError,
            oddsapi_sport_key_for_tag,
        )

        return OddsApiClient, OddsApiError, oddsapi_sport_key_for_tag
    except Exception:
        return None

TENNIS_DIR = Path(__file__).parent
SLATES_DIR = TENNIS_DIR / "slates"
SLATES_DIR.mkdir(exist_ok=True)


def parse_tennis_paste(raw_text: str) -> List[Dict]:
    """
    Parse pasted tennis matches.
    
    Expected format (flexible):
    Player A vs Player B | Surface | Round | Line
    OR
    Player A -135 vs Player B +115 | Hard | R1
    """
    matches = []
    lines = [l.strip() for l in raw_text.strip().split('\n') if l.strip()]
    
    for line in lines:
        match = parse_single_match(line)
        if match:
            matches.append(match)
    
    return matches


def parse_single_match(line: str) -> Optional[Dict]:
    """Parse a single match line."""
    
    # Skip headers/comments
    if line.startswith('#') or line.startswith('//'):
        return None
    
    # Extract tour if specified
    tour = "ATP"  # Default
    if "WTA" in line.upper():
        tour = "WTA"
        line = re.sub(r'\bWTA\b', '', line, flags=re.IGNORECASE)
    elif "ATP" in line.upper():
        line = re.sub(r'\bATP\b', '', line, flags=re.IGNORECASE)
    
    # Extract surface
    surface = "HARD"  # Default
    for surf in ["HARD", "CLAY", "GRASS", "INDOOR"]:
        if surf.lower() in line.lower():
            surface = surf
            line = re.sub(rf'\b{surf}\b', '', line, flags=re.IGNORECASE)
            break
    
    # Extract round
    round_match = re.search(r'\b(R1|R2|R3|R4|QF|SF|F|R16|R32|R64|R128)\b', line, re.IGNORECASE)
    round_str = round_match.group(1).upper() if round_match else "R1"
    if round_match:
        line = line[:round_match.start()] + line[round_match.end():]
    
    # Extract players and lines
    # Format: "Player A -135 vs Player B +115" or "Player A vs Player B -135/+115"
    vs_pattern = re.search(r'(.+?)\s+(?:vs\.?|v\.?)\s+(.+)', line, re.IGNORECASE)
    
    if not vs_pattern:
        return None
    
    player_a_raw = vs_pattern.group(1).strip()
    player_b_raw = vs_pattern.group(2).strip()
    
    # Extract moneylines
    line_a = extract_moneyline(player_a_raw)
    line_b = extract_moneyline(player_b_raw)
    
    # Clean player names
    player_a = re.sub(r'[+-]?\d+', '', player_a_raw).strip().strip('|').strip()
    player_b = re.sub(r'[+-]?\d+', '', player_b_raw).strip().strip('|').strip()
    
    if not player_a or not player_b:
        return None
    
    # Generate match ID
    date_str = datetime.now().strftime("%Y%m%d")
    match_id = f"{tour}_{surface}_{round_str}_{player_a[:3].upper()}_{player_b[:3].upper()}_{date_str}"
    
    return {
        "match_id": match_id,
        "tour": tour,
        "surface": surface,
        "round": round_str,
        "player_a": player_a,
        "player_b": player_b,
        "line_a": line_a,
        "line_b": line_b,
        "market": "match_winner",
        "ingested_at": datetime.now().isoformat(),
    }


def extract_moneyline(text: str) -> Optional[int]:
    """Extract American moneyline from text."""
    match = re.search(r'([+-]?\d{3,4})', text)
    if match:
        return int(match.group(1))
    return None


def moneyline_to_implied_prob(line: int) -> float:
    """Convert American moneyline to implied probability."""
    if line is None:
        return 0.50
    if line > 0:
        return 100 / (line + 100)
    else:
        return abs(line) / (abs(line) + 100)


def save_slate(matches: List[Dict], name: str = None) -> Path:
    """Save parsed matches to slate file."""
    if not name:
        name = datetime.now().strftime("%Y%m%d_%H%M")
    
    filename = SLATES_DIR / f"{name}_matches.json"
    
    slate = {
        "sport": "TENNIS",
        "generated_at": datetime.now().isoformat(),
        "match_count": len(matches),
        "matches": matches
    }
    
    filename.write_text(json.dumps(slate, indent=2))
    print(f"✓ Saved {len(matches)} matches to {filename}")
    return filename


def ingest_from_odds_api(*, tour: str = "ATP", surface: str = "HARD", max_events: Optional[int] = None) -> Optional[Path]:
    """Ingest match-winner slate from The Odds API (no-scrape).

    Notes:
    - Odds API tennis sport_keys are tournament-specific.
    - Configure via env vars added to repo root .env:
        ODDS_API_KEY
        ODDS_API_TENNIS_ATP_SPORT_KEY / ODDS_API_TENNIS_WTA_SPORT_KEY (preferred)
        ODDS_API_TENNIS_SPORT_KEY (fallback)
    - Surface is required by the repo's tennis model; Odds API does not reliably
      supply it, so we take it as an input here.
    """

    imported = _try_import_odds_api()
    if not imported:
        print("\n✗ Odds API adapter import failed")
        print("  Expected module: src/sources/odds_api.py")
        return None

    OddsApiClient, OddsApiError, oddsapi_sport_key_for_tag = imported

    tour_u = (tour or "ATP").strip().upper()
    if tour_u not in {"ATP", "WTA"}:
        print(f"\n✗ Invalid tour: {tour!r} (expected ATP or WTA)")
        return None

    surface_u = (surface or "HARD").strip().upper()
    valid_surfaces = {"HARD", "CLAY", "GRASS", "INDOOR"}
    if surface_u not in valid_surfaces:
        print(f"\n✗ Invalid surface: {surface!r} (expected one of {sorted(valid_surfaces)})")
        return None

    sport_tag = "TENNIS_ATP" if tour_u == "ATP" else "TENNIS_WTA"
    sport_key = oddsapi_sport_key_for_tag(sport_tag)
    if not sport_key:
        print("\n✗ Missing tennis Odds API sport_key mapping.")
        print("  Set ODDS_API_TENNIS_ATP_SPORT_KEY / ODDS_API_TENNIS_WTA_SPORT_KEY in .env")
        return None

    client = OddsApiClient.from_env()
    if not client:
        print("\n✗ Missing ODDS_API_KEY (or ODDSAPI_KEY) in .env")
        return None

    import os

    # NOTE: Repo-level ODDS_API_REGIONS/BOOKMAKERS are often set to DFS-focused
    # values for player props ingestion (e.g., us_dfs + underdog/prizepicks).
    # Tennis match-winner (h2h) is typically posted on standard books instead.
    # So we use tennis-specific overrides when present, else sensible defaults.
    regions = (os.getenv("ODDS_API_TENNIS_REGIONS") or os.getenv("ODDS_API_REGIONS") or "us").strip()
    if "dfs" in regions.lower():
        regions = "us"

    bookmakers = (os.getenv("ODDS_API_TENNIS_BOOKMAKERS") or "").strip() or None

    print("\n" + "=" * 60)
    print("🔌 TENNIS ODDS API INGEST (NO SCRAPE)")
    print("=" * 60)
    print(f"  tour:       {tour_u}")
    print(f"  surface:    {surface_u}")
    print(f"  sport_key:  {sport_key}")
    print(f"  regions:    {regions}")
    print(f"  bookmakers: {bookmakers or '(all)'}")

    try:
        events, _quota = client.get_events(sport_key=sport_key)
    except Exception as e:
        print(f"\n✗ Failed to list events: {e}")
        return None

    if not events:
        print("\n⚠️ No events returned for this sport_key.")
        print("   (Common causes: wrong tournament key, off-day, or odds not posted yet.)")
        return None

    if max_events is not None:
        events = events[: max(0, int(max_events))]

    matches: List[Dict] = []
    seen = set()

    for ev in events:
        ev_id = str(ev.get("id") or "").strip()
        if not ev_id:
            continue

        try:
            odds_json, _quota2 = client.get_event_odds(
                sport_key=sport_key,
                event_id=ev_id,
                regions=regions,
                markets="h2h",
                odds_format="american",
                bookmakers=bookmakers,
            )
        except Exception:
            continue

        books = odds_json.get("bookmakers") or []
        if not isinstance(books, list) or not books:
            continue

        # Find first bookmaker that has an h2h market with 2 outcomes.
        outcomes = None
        for b in books:
            mkts = b.get("markets") or []
            if not isinstance(mkts, list):
                continue
            for m in mkts:
                if str(m.get("key") or "").lower() != "h2h":
                    continue
                outs = m.get("outcomes") or []
                if isinstance(outs, list) and len(outs) >= 2:
                    outcomes = outs
                    break
            if outcomes:
                break

        if not outcomes:
            continue

        try:
            p1 = str(outcomes[0].get("name") or "").strip()
            p2 = str(outcomes[1].get("name") or "").strip()
            l1 = outcomes[0].get("price")
            l2 = outcomes[1].get("price")
            line_a = int(l1) if l1 is not None else None
            line_b = int(l2) if l2 is not None else None
        except Exception:
            continue

        if not p1 or not p2:
            continue

        key = (tour_u, surface_u, p1.lower(), p2.lower())
        if key in seen:
            continue
        seen.add(key)

        date_str = datetime.now().strftime("%Y%m%d")
        match_id = f"{tour_u}_{surface_u}_R1_{p1[:3].upper()}_{p2[:3].upper()}_{date_str}"

        matches.append(
            {
                "match_id": match_id,
                "tour": tour_u,
                "surface": surface_u,
                "round": "R1",
                "player_a": p1,
                "player_b": p2,
                "line_a": line_a,
                "line_b": line_b,
                "market": "match_winner",
                "event": odds_json.get("sport_title") or ev.get("sport_title"),
                "commence_time": odds_json.get("commence_time") or ev.get("commence_time"),
                "ingested_at": datetime.now().isoformat(),
            }
        )

    if not matches:
        print("\n⚠️ No h2h lines found for these events.")
        print("   Try adjusting ODDS_API_REGIONS / ODDS_API_BOOKMAKERS or run closer to match time.")
        return None

    name = f"oddsapi_{tour_u.lower()}_{surface_u.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}"
    return save_slate(matches, name)


def load_latest_slate() -> Optional[Dict]:
    """Load the most recent tennis slate."""
    slates = list(SLATES_DIR.glob("*_matches.json"))
    if slates:
        # IMPORTANT: do NOT rely on lexicographic filename ordering.
        # Files like "quick_analysis_matches.json" can sort after timestamped
        # slates and cause the pipeline to use stale data.
        slates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        slate_path = slates[0]
        slate = json.loads(slate_path.read_text())
        # Attach provenance for debugging/UX. Safe additive field.
        try:
            slate["_slate_file"] = str(slate_path.resolve())
            slate["_slate_mtime"] = datetime.fromtimestamp(slate_path.stat().st_mtime).isoformat()
        except Exception:
            pass
        return slate
    return None


def interactive_ingest():
    """Interactive match ingestion."""
    print("=" * 60)
    print("TENNIS MATCH INGESTION")
    print("=" * 60)

    print("\nChoose ingestion method:")
    print("  [1] Manual paste (default)")
    print("  [2] The Odds API (no-scrape) — match winner (h2h)")
    method = input("\nSelect [1/2]: ").strip() or "1"

    if method.strip() == "2":
        # Smart default tour:
        # - Many users configure only WTA tournament sport_key (e.g., Qatar Open).
        # - If ATP key is missing but WTA exists, default to WTA to avoid a false "missing mapping".
        import os

        has_atp = bool((os.getenv("ODDS_API_TENNIS_ATP_SPORT_KEY") or "").strip())
        has_wta = bool((os.getenv("ODDS_API_TENNIS_WTA_SPORT_KEY") or "").strip())
        default_tour = "WTA" if (has_wta and not has_atp) else "ATP"

        tour = (input(f"Tour [ATP/WTA] (default {default_tour}): ").strip() or default_tour).upper()
        surface = (input("Surface [HARD/CLAY/GRASS/INDOOR] (default HARD): ").strip() or "HARD").upper()
        max_events_s = input("Max events (blank = ALL events): ").strip()
        max_events = int(max_events_s) if max_events_s else None
        saved = ingest_from_odds_api(tour=tour, surface=surface, max_events=max_events)
        return saved

    print("\nPaste matches (one per line). Format examples:")
    print("  Sinner -180 vs Djokovic +150 | Hard | SF")
    print("  Swiatek vs Sabalenka | Clay | F | WTA")
    print("\nPress Enter twice when done.\n")
    
    lines = []
    empty_count = 0
    
    while empty_count < 2:
        line = input()
        if not line.strip():
            empty_count += 1
        else:
            empty_count = 0
            lines.append(line)
    
    raw_text = '\n'.join(lines)
    matches = parse_tennis_paste(raw_text)
    
    if not matches:
        print("✗ No valid matches parsed")
        return None
    
    print(f"\n✓ Parsed {len(matches)} matches:")
    for m in matches:
        line_str = f"{m['line_a']}" if m['line_a'] else "?"
        print(f"  • {m['player_a']} ({line_str}) vs {m['player_b']} | {m['surface']} {m['round']}")
    
    save = input("\nSave slate? [Y/n]: ").strip().lower()
    if save != 'n':
        return save_slate(matches)
    return None


if __name__ == "__main__":
    interactive_ingest()
