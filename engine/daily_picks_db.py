"""
Cross-Sport Daily Picks Database
=================================
Every sport saves its TOP 5 picks here after analysis.
Unified parlay builder pulls from ALL sports.

Usage:
    # After any sport analysis:
    from engine.daily_picks_db import save_top_picks
    save_top_picks(edges, sport="NBA", top_n=5)
    
    # Build cross-sport parlays:
    from engine.daily_picks_db import build_cross_sport_parlays
    parlays = build_cross_sport_parlays()
"""

from __future__ import annotations

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

# =============================================================================
# DATABASE PATH
# =============================================================================

DB_PATH = Path("cache/daily_picks.db")


# =============================================================================
# AUTO-IMPORT HELPERS (from existing analysis outputs)
# =============================================================================

def _coerce_prob_to_unit_interval(prob: Any) -> Optional[float]:
    """Return probability as float in [0,1], or None if unavailable."""
    if prob is None:
        return None
    try:
        p = float(prob)
    except Exception:
        return None
    # Accept either 0-1 or 0-100 formats.
    if p > 1.0:
        p = p / 100.0
    if p < 0.0 or p > 1.0:
        return None
    return p


def _extract_edges_from_nfl_analysis(payload: Any) -> List[Dict[str, Any]]:
    """Extract a canonical-ish edges list from nfl_menu-style JSON outputs."""
    if isinstance(payload, dict):
        rows = payload.get("results") or payload.get("edges") or payload.get("signals") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    if not isinstance(rows, list):
        return []

    try:
        from config.thresholds import implied_tier
    except Exception:
        implied_tier = None  # type: ignore

    canonical_tiers = {
        "SLAM", "STRONG", "LEAN", "SPEC", "AVOID",
        "NO_PLAY", "NO PLAY",
        "REJECTED", "BLOCKED", "SKIP",
    }

    edges: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue

        player = r.get("player") or r.get("entity") or ""
        stat = r.get("stat") or r.get("market") or ""
        line = r.get("line", 0)
        direction = (r.get("direction") or "").lower().strip()

        # nfl_menu stores 0-1 probability.
        p_unit = _coerce_prob_to_unit_interval(r.get("probability", r.get("p_hit", r.get("confidence"))))
        if p_unit is None:
            continue

        declared = (r.get("tier") or r.get("confidence_tier") or "").upper().strip()
        grade = (r.get("grade") or "").upper().strip()

        tier = declared
        if tier not in canonical_tiers:
            # If the source uses letter grades (A/B/...), convert to canonical tier
            # based on probability and preserve the grade as a risk tag.
            if implied_tier is not None:
                tier = implied_tier(p_unit, sport="NFL")
            else:
                tier = "AVOID"

        risk_tags: List[str] = []
        if grade and grade != tier and grade not in canonical_tiers:
            risk_tags.append(f"GRADE_{grade}")

        edges.append({
            "sport": "NFL",
            "player": player,
            "stat": stat,
            "line": line,
            "direction": direction,
            "probability": p_unit,
            "tier": tier or "AVOID",
            "team": r.get("team", ""),
            "opponent": r.get("opponent", r.get("opp", "")),
            "edge_id": r.get("edge_id", r.get("id", "")),
            "pick_state": r.get("pick_state", "OPTIMIZABLE"),
            "risk_tags": risk_tags,
        })

    return edges


def try_autosave_nfl_from_outputs(date_str: str = None, top_n: int = 5) -> int:
    """If NFL picks aren't saved for date_str, attempt to import them from outputs/.

    This keeps NFL model code untouched (NFL v1.0 stays frozen), while allowing the
    cross-sport parlay system to include NFL when an NFL analysis file exists.
    """
    init_db()
    if date_str is None:
        date_str = date.today().isoformat()

    def _delete_existing() -> None:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("DELETE FROM daily_picks WHERE date = ? AND sport = ?", (date_str, "NFL"))
            conn.commit()
        finally:
            conn.close()

    # Already saved? Usually do nothing. If tiers look non-canonical (e.g. 'A'), refresh.
    existing = get_daily_picks(date_str=date_str, sport="NFL", min_probability=0)
    if existing:
        canonical = {"SLAM", "STRONG", "LEAN", "SPEC", "AVOID", "NO_PLAY", "NO PLAY"}
        noncanonical = [p for p in existing if str(p.get("tier", "")).upper().strip() not in canonical]
        if not noncanonical:
            return 0
        _delete_existing()

    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        return 0

    # Preferred source: nfl_menu outputs
    nfl_files = sorted(outputs_dir.glob("nfl_analysis_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    # Fallback: daily_pipeline debug output
    if not nfl_files:
        nfl_files = sorted(outputs_dir.glob("edge_analysis_NFL.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not nfl_files:
        return 0

    latest = nfl_files[0]
    try:
        file_date = datetime.fromtimestamp(latest.stat().st_mtime).date().isoformat()
    except Exception:
        file_date = None

    # Guardrail: only auto-import if the latest file was produced today (same date_str).
    if file_date and file_date != date_str:
        return 0

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return 0

    edges = _extract_edges_from_nfl_analysis(payload)
    if not edges:
        return 0

    try:
        return save_top_picks(edges, sport="NFL", top_n=top_n, date_str=date_str)
    except Exception:
        return 0


# =============================================================================
# SCHEMA
# =============================================================================

def init_db():
    """Initialize the daily picks database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            sport TEXT NOT NULL,
            player TEXT NOT NULL,
            stat TEXT NOT NULL,
            line REAL NOT NULL,
            direction TEXT NOT NULL,
            probability REAL NOT NULL,
            tier TEXT NOT NULL,
            rank INTEGER NOT NULL,
            edge_id TEXT,
            team TEXT,
            opponent TEXT,
            game_time TEXT,
            risk_tags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, sport, player, stat, direction)
        )
    """)
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_date_sport ON daily_picks(date, sport)
    """)
    
    conn.commit()
    conn.close()


# =============================================================================
# SAVE PICKS
# =============================================================================

def save_top_picks(
    edges: List[Dict],
    sport: str,
    top_n: int = 5,
    date_str: str = None
) -> int:
    """
    Save top N picks for a sport to the daily database.
    
    Args:
        edges: List of edge dicts from analysis
        sport: Sport identifier (NBA, NHL, Tennis, CBB, NFL, Golf, Soccer)
        top_n: Number of top picks to save (default 5)
        date_str: Date string (default: today)
        
    Returns:
        Number of picks saved
    """
    init_db()
    
    if date_str is None:
        date_str = date.today().isoformat()
    
    # Filter to playable picks
    playable = [
        e for e in edges
        if e.get("tier", "").upper() not in {"NO_PLAY", "NO PLAY", "AVOID", "REJECTED"}
        and e.get("pick_state", "OPTIMIZABLE").upper() != "REJECTED"
    ]
    
    # Sort by probability descending
    def get_prob(e):
        p = e.get("probability", e.get("p_hit", e.get("confidence", 0)))
        if isinstance(p, (int, float)):
            return float(p) if p > 1 else float(p) * 100
        return 0
    
    sorted_edges = sorted(playable, key=get_prob, reverse=True)[:top_n]
    
    conn = sqlite3.connect(str(DB_PATH))
    saved = 0
    
    for rank, edge in enumerate(sorted_edges, 1):
        player = edge.get("player", edge.get("entity", ""))
        stat = edge.get("stat", edge.get("market", ""))
        line = float(edge.get("line", 0))
        direction = edge.get("direction", "").lower()
        prob = get_prob(edge)
        if prob <= 1:
            prob *= 100
        tier = edge.get("tier", edge.get("confidence_tier", ""))
        
        risk_tags = edge.get("risk_tags", [])
        if not risk_tags:
            risk_tags = edge.get("risk", {}).get("risk_tags", [])
        risk_tags_str = ",".join(risk_tags) if risk_tags else ""
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO daily_picks 
                (date, sport, player, stat, line, direction, probability, tier, rank,
                 edge_id, team, opponent, game_time, risk_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str,
                sport.upper(),
                player,
                stat,
                line,
                direction,
                prob,
                tier,
                rank,
                edge.get("edge_id", edge.get("id", "")),
                edge.get("team", ""),
                edge.get("opponent", edge.get("opp", "")),
                edge.get("game_time", ""),
                risk_tags_str,
            ))
            saved += 1
        except Exception as e:
            print(f"  Warning: Could not save {player} {stat}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"  ✅ Saved {saved} top picks for {sport.upper()} ({date_str})")
    return saved


# =============================================================================
# LOAD PICKS
# =============================================================================

def get_daily_picks(
    date_str: str = None,
    sport: str = None,
    min_probability: float = 55.0
) -> List[Dict]:
    """
    Get picks from the daily database.
    
    Args:
        date_str: Date to fetch (default: today)
        sport: Filter by sport (default: all sports)
        min_probability: Minimum probability filter
        
    Returns:
        List of pick dicts
    """
    init_db()
    
    if date_str is None:
        date_str = date.today().isoformat()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    query = """
        SELECT * FROM daily_picks 
        WHERE date = ? AND probability >= ?
    """
    params = [date_str, min_probability]
    
    if sport:
        query += " AND sport = ?"
        params.append(sport.upper())
    
    query += " ORDER BY probability DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    picks = []
    for row in rows:
        pick = dict(row)
        # Parse risk_tags back to list
        if pick.get("risk_tags"):
            pick["risk_tags"] = pick["risk_tags"].split(",")
        else:
            pick["risk_tags"] = []
        picks.append(pick)
    
    return picks


def get_all_sports_today(date_str: str = None) -> Dict[str, List[Dict]]:
    """Get today's picks grouped by sport."""
    if date_str is None:
        date_str = date.today().isoformat()
    
    all_picks = get_daily_picks(date_str=date_str, min_probability=0)
    
    by_sport = {}
    for pick in all_picks:
        sport = pick["sport"]
        if sport not in by_sport:
            by_sport[sport] = []
        by_sport[sport].append(pick)
    
    return by_sport


# =============================================================================
# CROSS-SPORT PARLAY BUILDER
# =============================================================================

def _is_game_pick(pick: Dict[str, Any]) -> bool:
    """Heuristic: determine whether a pick is a *game-level* market.

    We store only a free-text `stat` in the daily DB, so we infer via keywords.
    Examples we want to treat as game picks:
      - Moneyline / Match Winner / 1X2
      - Spread / Puck Line / Handicap
      - Totals / Team Totals

    Note: This is intentionally permissive; it's used only as a diversity
    constraint ("at least one game pick") not for eligibility.
    """
    stat = (pick.get("stat") or "").strip().lower()
    player = (pick.get("player") or "").strip().lower()

    # Some systems store game markets with team names as `player`
    if player in {"game", "match", "moneyline", "ml"}:
        return True

    keywords = (
        "moneyline",
        "ml",
        "match winner",
        "match_winner",
        "winner",
        "1x2",
        "spread",
        "handicap",
        "puck line",
        "puckline",
        "line",
        "total",
        "team total",
        "totals",
        # Tennis / match-level totals
        "games_played",
        "sets_played",
        "total games",
        "total_games",
        "total sets",
        "total_sets",
        "over/under",
        "over under",
    )

    return any(k in stat for k in keywords)

def build_cross_sport_parlays(
    date_str: str = None,
    legs: int = 3,
    min_probability: float = 58.0,
    max_same_sport: int = 2,
    require_multi_sport: bool = True,
    one_per_sport: bool = True,
    require_game_pick: bool = False,
) -> List[Dict]:
    """
    Build parlays using picks from multiple sports.
    
    Args:
        date_str: Date to use (default: today)
        legs: Number of legs per parlay
        min_probability: Minimum probability per leg
        max_same_sport: Max picks from same sport in one parlay
        require_multi_sport: Require at least 2 different sports
        one_per_sport: Try to include one pick from each saved sport
        
    Returns:
        List of parlay dicts with combined probability
    """
    from itertools import combinations, product
    
    picks = get_daily_picks(date_str=date_str, min_probability=min_probability)
    
    if len(picks) < legs:
        return []
    
    # Group picks by sport
    by_sport = {}
    for p in picks:
        sport = p["sport"]
        if sport not in by_sport:
            by_sport[sport] = []
        by_sport[sport].append(p)
    
    # Sort each sport's picks by probability
    for sport in by_sport:
        by_sport[sport] = sorted(by_sport[sport], key=lambda x: x["probability"], reverse=True)
    
    valid_parlays = []
    available_sports = list(by_sport.keys())
    
    # Strategy 1: If one_per_sport and enough sports, try to get one from each
    if one_per_sport and len(available_sports) >= legs:
        # Use top pick from each sport, then combinations
        for sport_combo in combinations(available_sports, legs):
            # Get top 3 from each sport in combo
            sport_picks = [by_sport[s][:3] for s in sport_combo]
            
            # Generate all combinations (one from each sport)
            for combo in product(*sport_picks):
                players = [p["player"].lower() for p in combo]
                if len(players) != len(set(players)):
                    continue

                if require_game_pick and not any(_is_game_pick(p) for p in combo):
                    continue
                
                combined_prob = 1.0
                for pick in combo:
                    prob = pick["probability"]
                    if prob > 1:
                        prob /= 100
                    combined_prob *= prob
                
                valid_parlays.append({
                    "legs": list(combo),
                    "leg_count": legs,
                    "sports": list(sport_combo),
                    "sport_count": len(sport_combo),
                    "combined_probability": round(combined_prob, 4),
                    "combined_pct": f"{combined_prob * 100:.1f}%",
                })
    
    # Strategy 2: If fewer sports than legs, or add mixed parlays
    if len(available_sports) < legs or len(valid_parlays) < 10:
        # Sort all picks by probability
        all_sorted = sorted(picks, key=lambda x: x["probability"], reverse=True)
        
        for combo in combinations(all_sorted[:25], legs):
            sports = [p["sport"] for p in combo]
            sport_counts = {}
            for s in sports:
                sport_counts[s] = sport_counts.get(s, 0) + 1
            
            if any(count > max_same_sport for count in sport_counts.values()):
                continue
            
            if require_multi_sport and len(set(sports)) < 2:
                continue
            
            players = [p["player"].lower() for p in combo]
            if len(players) != len(set(players)):
                continue

            if require_game_pick and not any(_is_game_pick(p) for p in combo):
                continue
            
            combined_prob = 1.0
            for pick in combo:
                prob = pick["probability"]
                if prob > 1:
                    prob /= 100
                combined_prob *= prob
            
            valid_parlays.append({
                "legs": list(combo),
                "leg_count": legs,
                "sports": list(set(sports)),
                "sport_count": len(set(sports)),
                "combined_probability": round(combined_prob, 4),
                "combined_pct": f"{combined_prob * 100:.1f}%",
            })
    
    # Remove duplicates and sort by combined probability
    seen = set()
    unique_parlays = []
    for p in valid_parlays:
        key = tuple(sorted([
            f"{l.get('sport','')}|{l.get('player','')}|{l.get('stat','')}|{l.get('line','')}|{l.get('direction','')}"
            for l in p["legs"]
        ]))
        if key not in seen:
            seen.add(key)
            unique_parlays.append(p)
    
    unique_parlays = sorted(
        unique_parlays,
        key=lambda x: (x["sport_count"], x["combined_probability"]),
        reverse=True
    )
    
    return unique_parlays[:10]  # Top 10


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

def print_daily_summary(date_str: str = None):
    """Print summary of today's picks across all sports."""
    if date_str is None:
        date_str = date.today().isoformat()

    # QoL: If NFL was analyzed but not saved to the daily DB, auto-import.
    # This keeps XP truly "cross-sport" without requiring manual save steps.
    try:
        try_autosave_nfl_from_outputs(date_str=date_str, top_n=5)
    except Exception:
        pass
    
    by_sport = get_all_sports_today(date_str)
    
    print("\n" + "=" * 70)
    print(f"  📊 DAILY PICKS SUMMARY — {date_str}")
    print("=" * 70)
    
    if not by_sport:
        print("\n  No picks saved for today.")
        print("  Run analysis for each sport first.")
        return
    
    total = 0
    for sport in sorted(by_sport.keys()):
        picks = by_sport[sport]
        total += len(picks)
        
        sport_emoji = {
            "NBA": "🏀",
            "NHL": "🏒",
            "NFL": "🏈",
            "CBB": "🎓",
            "TENNIS": "🎾",
            "GOLF": "⛳",
            "SOCCER": "⚽",
        }.get(sport, "🎯")
        
        print(f"\n  {sport_emoji} {sport} ({len(picks)} picks)")
        print("  " + "-" * 50)
        
        for pick in picks:
            player = pick["player"][:15]
            stat = pick["stat"][:8]
            direction = "O" if pick["direction"] in ["higher", "over"] else "U"
            prob = pick["probability"]
            tier = pick["tier"][:6]
            
            print(f"    #{pick['rank']} {player:<15} {stat:<8} {pick['line']:>5.1f} {direction} | {prob:.0f}% | {tier}")
    
    print(f"\n  TOTAL: {total} picks across {len(by_sport)} sports")


def print_cross_sport_parlays(date_str: str = None, legs: int = 3):
    """Print suggested cross-sport parlays."""
    if date_str is None:
        date_str = date.today().isoformat()

    # Ensure NFL is present if an NFL analysis exists for today.
    try:
        try_autosave_nfl_from_outputs(date_str=date_str, top_n=5)
    except Exception:
        pass

    parlays = build_cross_sport_parlays(date_str=date_str, legs=legs)
    
    print("\n" + "=" * 70)
    print(f"  🎯 CROSS-SPORT PARLAYS ({legs}-LEG)")
    print("=" * 70)
    
    if not parlays:
        print("\n  Not enough picks from multiple sports.")
        print("  Run analysis for more sports first.")
        return
    
    for i, parlay in enumerate(parlays[:5], 1):
        sports_str = " + ".join(parlay["sports"])
        print(f"\n  #{i} — {parlay['combined_pct']} ({sports_str})")
        print("  " + "-" * 50)
        
        for leg in parlay["legs"]:
            sport = leg["sport"]
            player = leg["player"][:15]
            stat = leg["stat"][:8]
            direction = "OVER" if leg["direction"] in ["higher", "over"] else "UNDER"
            line = leg["line"]
            prob = leg["probability"]
            
            emoji = {"NBA": "🏀", "NHL": "🏒", "TENNIS": "🎾", "CBB": "🎓", 
                     "NFL": "🏈", "GOLF": "⛳", "SOCCER": "⚽"}.get(sport, "🎯")
            
            print(f"    {emoji} {player:<15} {stat:<8} {direction} {line} ({prob:.0f}%)")


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    # Demo with sample data
    print("Testing Daily Picks Database...")
    
    # Sample NBA picks
    nba_edges = [
        {"player": "Nikola Jokic", "stat": "rebounds", "line": 12.5, "direction": "higher", "probability": 0.72, "tier": "SLAM"},
        {"player": "Tyrese Maxey", "stat": "points", "line": 25.5, "direction": "higher", "probability": 0.68, "tier": "STRONG"},
        {"player": "LeBron James", "stat": "assists", "line": 8.5, "direction": "higher", "probability": 0.65, "tier": "STRONG"},
    ]
    
    # Sample NHL picks
    nhl_edges = [
        {"player": "Connor McDavid", "stat": "points", "line": 1.5, "direction": "higher", "probability": 0.66, "tier": "STRONG"},
        {"player": "Auston Matthews", "stat": "shots", "line": 4.5, "direction": "higher", "probability": 0.62, "tier": "LEAN"},
    ]
    
    # Sample Tennis picks
    tennis_edges = [
        {"player": "Jannik Sinner", "stat": "match_winner", "line": -150, "direction": "higher", "probability": 0.70, "tier": "STRONG"},
        {"player": "Carlos Alcaraz", "stat": "total_games", "line": 22.5, "direction": "higher", "probability": 0.64, "tier": "LEAN"},
    ]
    
    # Save to DB
    save_top_picks(nba_edges, "NBA", top_n=5)
    save_top_picks(nhl_edges, "NHL", top_n=5)
    save_top_picks(tennis_edges, "TENNIS", top_n=5)
    
    # Print summary
    print_daily_summary()
    
    # Print cross-sport parlays
    print_cross_sport_parlays(legs=3)
    print_cross_sport_parlays(legs=2)
