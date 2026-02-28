"""
TOTAL GAMES ENGINE v2 — Structural Model
=========================================
Fast, deterministic Total Games edge generator following the essential execution order:

Phase 1: Automatic Context Resolution
  - Infer Bo3/Bo5 from line (>33.5 = Bo5)
  - Resolve surface from tournament lookup

Phase 2: Structural Total Games Model
  - E[Total Games] = E[sets] × E[games/set]
  - Surface-dependent baselines
  - Rating gap heuristics

Phase 3: Line Comparison & Decision Gate
  - Δ ≥ +2.0 → OVER
  - Δ ≤ -2.0 → UNDER
  - |Δ| < 1.0 → NO_PLAY

Phase 4: Batch Slate Processor
  - Top 5 Overs + Top 5 Unders
  - Blocked / No-Play list
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# -----------------------------------------------------------------------------
# TOURNAMENT → SURFACE LOOKUP (Static Table)
# -----------------------------------------------------------------------------

TOURNAMENT_SURFACE_MAP = {
    # Grand Slams
    "australian open": "HARD",
    "aus open": "HARD",
    "ao": "HARD",
    "french open": "CLAY",
    "roland garros": "CLAY",
    "rg": "CLAY",
    "wimbledon": "GRASS",
    "us open": "HARD",
    "uso": "HARD",
    # ATP 1000
    "indian wells": "HARD",
    "miami": "HARD",
    "miami open": "HARD",
    "monte carlo": "CLAY",
    "monte-carlo": "CLAY",
    "madrid": "CLAY",
    "madrid open": "CLAY",
    "rome": "CLAY",
    "italian open": "CLAY",
    "internazionali": "CLAY",
    "canada": "HARD",
    "canadian open": "HARD",
    "rogers cup": "HARD",
    "national bank open": "HARD",
    "cincinnati": "HARD",
    "shanghai": "HARD",
    "paris": "INDOOR",
    "paris masters": "INDOOR",
    "bercy": "INDOOR",
    # ATP 500
    "rotterdam": "INDOOR",
    "dubai": "HARD",
    "acapulco": "HARD",
    "barcelona": "CLAY",
    "queen's": "GRASS",
    "queens": "GRASS",
    "halle": "GRASS",
    "hamburg": "CLAY",
    "washington": "HARD",
    "citi open": "HARD",
    "tokyo": "HARD",
    "japan open": "HARD",
    "beijing": "HARD",
    "china open": "HARD",
    "vienna": "INDOOR",
    "basel": "INDOOR",
    # ATP 250 (common)
    "adelaide": "HARD",
    "auckland": "HARD",
    "brisbane": "HARD",
    "doha": "HARD",
    "qatar open": "HARD",
    "sofia": "INDOOR",
    "montpellier": "INDOOR",
    "marseille": "INDOOR",
    "delray beach": "HARD",
    "dallas": "INDOOR",
    "houston": "CLAY",
    "marrakech": "CLAY",
    "estoril": "CLAY",
    "munich": "CLAY",
    "geneva": "CLAY",
    "lyon": "CLAY",
    "stuttgart": "CLAY",  # WTA is indoor, ATP clay
    "eastbourne": "GRASS",
    "mallorca": "GRASS",
    "newport": "GRASS",
    "atlanta": "HARD",
    "los cabos": "HARD",
    "umag": "CLAY",
    "kitzbuhel": "CLAY",
    "gstaad": "CLAY",
    "winston-salem": "HARD",
    "winston salem": "HARD",
    "chengdu": "HARD",
    "zhuhai": "HARD",
    "metz": "INDOOR",
    "astana": "INDOOR",
    "nur-sultan": "INDOOR",
    "stockholm": "INDOOR",
    "antwerp": "INDOOR",
    # WTA 1000
    "doha wta": "HARD",
    "qatar wta": "HARD",
    "charleston": "CLAY",
    "san diego": "HARD",
    "wuhan": "HARD",
    "guadalajara": "HARD",
    # Common WTA
    "hobart": "HARD",
    "linz": "INDOOR",
    "luxembourg": "INDOOR",
    "birmingham": "GRASS",
    "nottingham": "GRASS",
    "bad homburg": "GRASS",
    "berlin": "GRASS",
    # Next Gen / Finals
    "atp finals": "INDOOR",
    "turin": "INDOOR",
    "wta finals": "INDOOR",
    "nitto atp finals": "INDOOR",
}

# Seasonal heuristics (month-based fallback)
MONTH_SURFACE_FALLBACK = {
    1: "HARD",   # Jan: Australian swing
    2: "HARD",   # Feb: indoor/hard mix
    3: "HARD",   # Mar: Indian Wells, Miami
    4: "CLAY",   # Apr: clay swing starts
    5: "CLAY",   # May: Madrid, Rome, RG qualies
    6: "GRASS",  # Jun: grass season
    7: "HARD",   # Jul: grass ends, US swing
    8: "HARD",   # Aug: US Open series
    9: "HARD",   # Sep: US Open, Asia
    10: "INDOOR", # Oct: European indoor
    11: "INDOOR", # Nov: ATP Finals
    12: "HARD",  # Dec: off-season exhibitions
}


# -----------------------------------------------------------------------------
# SURFACE BASELINES (E[Games per Set])
# -----------------------------------------------------------------------------

# Surface-dependent expected games per set
SURFACE_GAMES_PER_SET = {
    "HARD": 9.9,    # Range: 9.6–10.2
    "CLAY": 9.5,    # Range: 9.2–9.8
    "GRASS": 10.85, # Range: 10.5–11.2
    "INDOOR": 10.5, # Range: 10.2–10.8
}


# -----------------------------------------------------------------------------
# DATA CLASSES
# -----------------------------------------------------------------------------

@dataclass
class MatchCandidate:
    player_a: str
    player_b: str
    line: float
    allowed_directions: Set[str] = field(default_factory=lambda: {"OVER", "UNDER"})
    tournament: Optional[str] = None


@dataclass
class TotalGamesEdge:
    player_a: str
    player_b: str
    line: float
    surface: str
    best_of: int
    expected_total: float
    delta: float
    direction: str
    action: str  # STRONG, LEAN, NO_PLAY, BLOCKED
    tour: str = "ATP"  # ATP or WTA
    block_reason: Optional[str] = None
    e_sets: float = 0.0
    e_games_per_set: float = 0.0


# -----------------------------------------------------------------------------
# PHASE 1: CONTEXT RESOLUTION
# -----------------------------------------------------------------------------

def infer_best_of_from_line(line: float, is_wta: bool = False, is_grand_slam: bool = False) -> int:
    """
    Infer Bo3 vs Bo5 from the total games line and context.
    
    Rules:
    - WTA is ALWAYS Bo3
    - ATP at Grand Slams is ALWAYS Bo5
    - ATP non-Grand Slam: If line > 33.5 → Bo5, else Bo3
    
    Key insight:
    - Bo5 mismatch lines can be 28-33 (3-0 expected)
    - Bo5 competitive lines are 37-43
    - Bo3 ceiling ≈ 39 games (rare)
    """
    if is_wta:
        return 3
    if is_grand_slam:
        return 5  # ATP Grand Slam = always Bo5
    return 5 if line > 33.5 else 3


def is_wta_player(name: str) -> bool:
    """
    Heuristic to detect WTA (women's) players.
    
    Known WTA first names / last names.
    """
    wta_names = {
        # First names
        "iga", "aryna", "coco", "elena", "jessica", "emma", "maria", "petra",
        "karolina", "paula", "qinwen", "zheng", "belinda", "madison", "jelena",
        "naomi", "caroline", "victoria", "daria", "donna", "marketa", "barbora",
        "anastasia", "anna", "veronika", "elise", "danielle", "ajla", "mirra",
        "beatriz", "diane", "dayana", "harriet", "katie", "yulia", "tamara",
        "leylah", "amanda", "sloane", "peyton", "magda", "lucia", "katerina",
        "xinyu", "linda", "elina", "diana", "maddison", "laura", "taylah",
        "varvara", "nikola", "julia", "moyuka", "marie", "ashlyn",
        # Last names
        "wang", "bencic", "keys", "ostapenko", "swiatek", "rybakina",
        "sabalenka", "gauff", "pegula", "bouzkova", "kalinskaya", "anisimova",
        "siniakova", "mertens", "uchijima", "grabher", "gracheva", "bartunkova",
        "krueger", "marcinko", "stearns", "noskova", "preston", "inglis",
        "siegemund", "svitolina", "shnaider",
    }
    
    lower = name.lower()
    parts = lower.split()
    
    for part in parts:
        if part in wta_names:
            return True
    
    return False


def detect_tour(player_a: str, player_b: str) -> str:
    """
    Detect if match is ATP or WTA.
    
    Returns: 'WTA', 'ATP', or 'UNKNOWN'
    """
    if is_wta_player(player_a) or is_wta_player(player_b):
        return "WTA"
    return "ATP"


def is_grand_slam_context(tournament: Optional[str], surface: str, month: int) -> bool:
    """
    Detect if this is a Grand Slam based on tournament name or date heuristics.
    
    Grand Slams:
    - Australian Open: January, HARD
    - French Open: May-June, CLAY
    - Wimbledon: June-July, GRASS
    - US Open: August-September, HARD
    """
    if tournament:
        t_lower = tournament.lower()
        gs_keywords = ["australian open", "french open", "roland garros", 
                       "wimbledon", "us open", "grand slam", "ao", "rg", "uso"]
        if any(kw in t_lower for kw in gs_keywords):
            return True
    
    # Date-based heuristics
    if month == 1 and surface == "HARD":
        return True  # Australian Open
    if month in (5, 6) and surface == "CLAY":
        return True  # French Open
    if month in (6, 7) and surface == "GRASS":
        return True  # Wimbledon
    if month in (8, 9) and surface == "HARD":
        # Could be US Open or USO Series - be conservative
        return False  # Many hard court events in Aug/Sep
    
    return False


def extract_tournament_from_text(raw_text: str) -> Optional[str]:
    """Extract tournament name from paste if present."""
    text = raw_text.lower()
    
    # Look for explicit tournament markers
    patterns = [
        r"tournament:\s*([^\n]+)",
        r"event:\s*([^\n]+)",
        r"@\s*(\w+\s+open)",
        r"@\s*(australian open|french open|wimbledon|us open)",
    ]
    
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    
    return None


def resolve_surface(
    raw_text: str,
    tournament: Optional[str] = None,
    surface_override: Optional[str] = None,
    use_month_fallback: bool = True,
) -> Optional[str]:
    """
    Resolve surface using priority order:
    1. Explicit override
    2. Tournament lookup
    3. Text detection
    4. Month-based fallback (if enabled)
    """
    valid = {"HARD", "CLAY", "GRASS", "INDOOR"}
    
    # Priority 1: Override
    if surface_override:
        s = surface_override.strip().upper()
        if s in valid:
            return s
    
    # Priority 2: Tournament lookup
    if tournament:
        t_lower = tournament.lower().strip()
        if t_lower in TOURNAMENT_SURFACE_MAP:
            return TOURNAMENT_SURFACE_MAP[t_lower]
        # Partial match
        for key, surf in TOURNAMENT_SURFACE_MAP.items():
            if key in t_lower or t_lower in key:
                return surf
    
    # Priority 3: Text detection
    text_upper = raw_text.upper()
    for s in valid:
        if f"SURFACE: {s}" in text_upper or f"SURFACE={s}" in text_upper:
            return s
    
    # Priority 4: Month-based fallback (January 2026)
    if use_month_fallback:
        month = datetime.now().month
        return MONTH_SURFACE_FALLBACK.get(month, "HARD")
    
    return None


# -----------------------------------------------------------------------------
# PHASE 2: STRUCTURAL MODEL
# -----------------------------------------------------------------------------

def estimate_expected_sets(best_of: int, rating_gap: float = 0.0) -> float:
    """
    Estimate expected number of sets based on format and rating gap.
    
    rating_gap: Normalized 0-1 scale (0 = even, 1 = huge mismatch)
    
    For Bo3:
      - Favorite vs underdog → E[sets] ≈ 2.1–2.3
      - Even match → E[sets] ≈ 2.6–2.8
    
    For Bo5:
      - Mismatch → E[sets] ≈ 3.2–3.6
      - Even → E[sets] ≈ 4.0–4.4
    """
    if best_of == 3:
        # Range: 2.0 (3-0 sweep) to 3.0 (always 3 sets)
        # Baseline even match: 2.7
        # Mismatch (rating_gap=1): 2.15
        base = 2.7
        adjustment = -0.55 * rating_gap  # More mismatch = fewer sets
        return max(2.0, min(3.0, base + adjustment))
    else:  # Bo5
        # Range: 3.0 (3-0 sweep) to 5.0 (always 5 sets)
        # Baseline even match: 4.2
        # Mismatch (rating_gap=1): 3.3
        base = 4.2
        adjustment = -0.9 * rating_gap
        return max(3.0, min(5.0, base + adjustment))


def estimate_games_per_set(surface: str, closeness: float = 0.5) -> float:
    """
    Estimate expected games per set based on surface and match closeness.
    
    closeness: 0-1 scale (0 = mismatch, 1 = very even)
    """
    base = SURFACE_GAMES_PER_SET.get(surface, 9.9)
    
    # Closer matches tend to have more games (tiebreaks, tight sets)
    # Range: ±0.5 games based on closeness
    adjustment = (closeness - 0.5) * 1.0
    
    return base + adjustment


def compute_expected_total(
    surface: str,
    best_of: int,
    rating_gap: float = 0.0,
) -> Tuple[float, float, float]:
    """
    Compute expected total games using structural formula.
    
    E[Total Games] = E[sets] × E[games per set]
    
    Returns: (expected_total, e_sets, e_games_per_set)
    """
    closeness = 1.0 - rating_gap  # Invert for closeness metric
    
    e_sets = estimate_expected_sets(best_of, rating_gap)
    e_games_per_set = estimate_games_per_set(surface, closeness)
    
    expected_total = e_sets * e_games_per_set
    
    return expected_total, e_sets, e_games_per_set


def estimate_rating_gap(player_a: str, player_b: str, line: float = 0.0, best_of: int = 3) -> float:
    """
    Estimate rating gap from player names and LINE context.
    
    Returns: 0-1 scale (0 = even, 1 = huge mismatch)
    
    KEY INSIGHT: The line itself encodes the book's view of competitiveness.
    - Bo3: Line ~20-22 = even, Line ~17-18 = mismatch, Line ~25+ = competitive
    - Bo5: Line ~38-42 = even, Line ~28-32 = big mismatch, Line ~33-37 = moderate
    
    Heuristics (in priority order):
    1. Line-based inference (most reliable)
    2. Qualifier/Unknown vs established
    3. Seed indicators in name
    4. Default
    """
    # LINE-BASED RATING GAP INFERENCE (most reliable)
    if line > 0:
        if best_of == 3:
            # Bo3 typical range: 17-27 games
            # Even match line: ~21-23
            # Mismatch line: ~17-19
            if line <= 18.5:
                return 0.55  # Big favorite expected
            elif line <= 20.0:
                return 0.40  # Solid favorite
            elif line <= 22.5:
                return 0.25  # Slight edge
            elif line <= 24.5:
                return 0.15  # Very even
            else:
                return 0.10  # Likely competitive / tiebreaky
        else:  # Bo5
            # Bo5 typical range: 26-45 games
            # Even match line: ~38-42
            # Mismatch line: ~26-32
            if line <= 28.5:
                return 0.60  # Huge mismatch (3-0 expected)
            elif line <= 32.5:
                return 0.45  # Big favorite
            elif line <= 35.5:
                return 0.30  # Moderate favorite
            elif line <= 38.5:
                return 0.20  # Slight edge
            elif line <= 41.5:
                return 0.10  # Very even
            else:
                return 0.05  # Extremely competitive
    
    # FALLBACK: Name-based heuristics
    a_lower = player_a.lower()
    b_lower = player_b.lower()
    
    # Check for qualifiers
    qual_markers = ("qualifier", " q ", "(q)", "qual")
    a_qual = any(m in a_lower for m in qual_markers)
    b_qual = any(m in b_lower for m in qual_markers)
    
    if a_qual != b_qual:
        return 0.55  # Qualifier vs non-qualifier
    
    if a_qual and b_qual:
        return 0.15  # Both qualifiers = fairly even
    
    # Check for seed markers like [1], (2), etc.
    seed_pat = r"[\[\(](\d+)[\]\)]"
    a_seed = re.search(seed_pat, player_a)
    b_seed = re.search(seed_pat, player_b)
    
    if a_seed and b_seed:
        a_num = int(a_seed.group(1))
        b_num = int(b_seed.group(1))
        diff = abs(a_num - b_num)
        return min(0.7, diff * 0.05)  # Larger seed gap = bigger mismatch
    
    if a_seed and not b_seed:
        s = int(a_seed.group(1))
        return min(0.5, 0.4 - s * 0.02)  # Higher seed = bigger favorite
    
    if b_seed and not a_seed:
        s = int(b_seed.group(1))
        return min(0.5, 0.4 - s * 0.02)
    
    # Default: assume slight mismatch (typical for most matches)
    return 0.3


# -----------------------------------------------------------------------------
# PHASE 3: DECISION GATE
# -----------------------------------------------------------------------------

def apply_decision_gate(
    expected: float,
    line: float,
    allowed_directions: Set[str],
) -> Tuple[str, str]:
    """
    Apply decision rules based on delta.
    
    Δ = E[Total Games] - Line
    
    - Δ ≥ +2.0 → OVER (LEAN if Δ < 3.0, STRONG if Δ ≥ 3.0)
    - Δ ≤ -2.0 → UNDER (LEAN if Δ > -3.0, STRONG if Δ ≤ -3.0)
    - |Δ| < 1.0 → NO_PLAY
    - 1.0 ≤ |Δ| < 2.0 → NO_PLAY (marginal, not actionable)
    
    Returns: (direction, action)
    """
    delta = expected - line
    
    # Check direction availability
    over_ok = "OVER" in allowed_directions
    under_ok = "UNDER" in allowed_directions
    
    if delta >= 2.0 and over_ok:
        action = "STRONG" if delta >= 3.0 else "LEAN"
        return "OVER", action
    
    if delta <= -2.0 and under_ok:
        action = "STRONG" if delta <= -3.0 else "LEAN"
        return "UNDER", action
    
    # Marginal / no edge
    if abs(delta) < 1.0:
        return "NONE", "NO_PLAY"
    
    # 1.0 ≤ |Δ| < 2.0: direction exists but not actionable
    if delta > 0 and over_ok:
        return "OVER", "NO_PLAY"
    if delta < 0 and under_ok:
        return "UNDER", "NO_PLAY"
    
    return "NONE", "NO_PLAY"


# -----------------------------------------------------------------------------
# PHASE 4: BATCH PROCESSOR
# -----------------------------------------------------------------------------

def parse_slate_paste(raw_text: str) -> List[MatchCandidate]:
    """
    Parse raw slate paste into match candidates.
    
    Supports Underdog "Total Games" format.
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    candidates: List[MatchCandidate] = []
    
    current_player: Optional[str] = None
    current_opponent: Optional[str] = None
    
    def clean_name(s: str) -> str:
        s = s.strip()
        s = re.sub(r"goblin$", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"demon$", "", s, flags=re.IGNORECASE).strip()
        return s
    
    def is_time_line(s: str) -> bool:
        return bool(re.search(r"\b(wed|thu|fri|sat|sun|mon|tue)\b", s, flags=re.IGNORECASE)) and (
            s.startswith("@") or s.lower().startswith("vs")
        )
    
    def extract_opponent(s: str) -> Optional[str]:
        s = s.strip()
        if s.startswith("@"):
            s = s[1:].strip()
        elif s.lower().startswith("vs"):
            s = s[2:].strip()
        s = re.sub(r"\b(wed|thu|fri|sat|sun|mon|tue)\b.*$", "", s, flags=re.IGNORECASE).strip()
        return clean_name(s) if s else None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        low = line.lower()
        
        # Capture opponent from time line
        if is_time_line(line):
            current_opponent = extract_opponent(line)
            i += 1
            continue
        
        # Try to parse a numeric line
        try:
            value = float(line)
        except ValueError:
            value = None
        
        if value is not None:
            # Lookahead for "Total Games"
            if i + 1 < len(lines) and lines[i + 1].strip().lower() == "total games":
                allowed: Set[str] = set()
                
                # Scan for Less/More
                j = i + 2
                while j < len(lines):
                    nxt = lines[j].strip().lower()
                    if nxt in ("less", "more"):
                        allowed.add("UNDER" if nxt == "less" else "OVER")
                        j += 1
                        continue
                    # Stop at next block
                    if re.fullmatch(r"\d+(?:\.\d+)?", lines[j].strip()):
                        break
                    if lines[j].strip().endswith("- Player"):
                        break
                    if is_time_line(lines[j]):
                        break
                    j += 1
                
                if current_player and current_opponent:
                    candidates.append(MatchCandidate(
                        player_a=clean_name(current_player),
                        player_b=clean_name(current_opponent),
                        line=value,
                        allowed_directions=allowed or {"OVER", "UNDER"},
                    ))
                i = j
                continue
        
        # Update current player
        if line.endswith("- Player"):
            nm = clean_name(line.replace("- Player", ""))
            if nm:
                current_player = nm
            i += 1
            continue
        
        # Accept as player name if not noise
        noise = {"trending", "player", "total games", "less", "more"}
        if low not in noise and not line.startswith("@") and not low.startswith("vs"):
            if not re.fullmatch(r"\d+(?:\.\d+)?", line) and len(line) >= 3:
                current_player = clean_name(line)
        
        i += 1
    
    return candidates


def process_slate(
    raw_text: str,
    surface_override: Optional[str] = None,
    tournament: Optional[str] = None,
    max_per_side: int = 5,
) -> Dict:
    """
    Full batch processing pipeline:
    1. Parse candidates
    2. Infer Bo3/Bo5 per match
    3. Resolve surface
    4. Compute expected totals
    5. Apply decision gates
    6. Return top 5 Overs + top 5 Unders
    """
    # Extract tournament from text if not provided
    if not tournament:
        tournament = extract_tournament_from_text(raw_text)
    
    # Resolve surface (with January fallback = HARD)
    surface = resolve_surface(raw_text, tournament, surface_override, use_month_fallback=True)
    
    if not surface:
        surface = "HARD"  # Ultimate fallback
    
    # Parse candidates
    candidates = parse_slate_paste(raw_text)
    
    # Detect Grand Slam context
    month = datetime.now().month
    is_grand_slam = is_grand_slam_context(tournament, surface, month)
    
    edges: List[TotalGamesEdge] = []
    
    for c in candidates:
        # Detect tour (ATP vs WTA)
        tour = detect_tour(c.player_a, c.player_b)
        is_wta = (tour == "WTA")
        
        # Phase 1: Infer Bo3/Bo5 from line + tour + Grand Slam context
        best_of = infer_best_of_from_line(c.line, is_wta=is_wta, is_grand_slam=(is_grand_slam and not is_wta))
        
        # Phase 2: Compute expected total
        # Use the LINE to infer rating gap (most reliable signal from books)
        rating_gap = estimate_rating_gap(c.player_a, c.player_b, line=c.line, best_of=best_of)
        expected, e_sets, e_games = compute_expected_total(surface, best_of, rating_gap)
        
        delta = expected - c.line
        
        # Phase 3: Apply decision gate
        direction, action = apply_decision_gate(expected, c.line, c.allowed_directions)
        
        edges.append(TotalGamesEdge(
            player_a=c.player_a,
            player_b=c.player_b,
            line=c.line,
            surface=surface,
            best_of=best_of,
            expected_total=round(expected, 1),
            delta=round(delta, 1),
            direction=direction,
            action=action,
            tour=tour,
            e_sets=round(e_sets, 2),
            e_games_per_set=round(e_games, 2),
        ))
    
    # Split by action
    playable = [e for e in edges if e.action in ("STRONG", "LEAN")]
    no_play = [e for e in edges if e.action == "NO_PLAY"]
    blocked = [e for e in edges if e.action == "BLOCKED"]
    
    # Split playable by direction
    overs = sorted(
        [e for e in playable if e.direction == "OVER"],
        key=lambda e: e.delta,
        reverse=True
    )[:max_per_side]
    
    unders = sorted(
        [e for e in playable if e.direction == "UNDER"],
        key=lambda e: e.delta  # More negative = stronger under
    )[:max_per_side]
    
    return {
        "engine": "TOTAL_GAMES_ENGINE_v2",
        "generated_at": datetime.now().isoformat(),
        "surface": surface,
        "tournament": tournament,
        "is_grand_slam": is_grand_slam,
        "total_candidates": len(candidates),
        "summary": {
            "playable": len(playable),
            "no_play": len(no_play),
            "blocked": len(blocked),
        },
        "top_overs": [_edge_to_dict(e) for e in overs],
        "top_unders": [_edge_to_dict(e) for e in unders],
        "no_play_list": [_edge_to_dict(e) for e in no_play],
    }


def _edge_to_dict(e: TotalGamesEdge) -> Dict:
    return {
        "match": f"{e.player_a} vs {e.player_b}",
        "line": e.line,
        "expected": e.expected_total,
        "delta": e.delta,
        "direction": e.direction,
        "action": e.action,
        "tour": e.tour,
        "best_of": e.best_of,
        "surface": e.surface,
        "e_sets": e.e_sets,
        "e_games_per_set": e.e_games_per_set,
    }


def print_results(output: Dict) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 85)
    print("TOTAL GAMES ENGINE v2 — STRUCTURAL MODEL")
    print("=" * 85)
    gs_str = " [GRAND SLAM]" if output.get('is_grand_slam') else ""
    print(f"Surface: {output['surface']} | Tournament: {output.get('tournament') or 'Unknown'}{gs_str}")
    print(f"Candidates: {output['total_candidates']} | Playable: {output['summary']['playable']} | No-Play: {output['summary']['no_play']}")
    print("-" * 85)
    print(f"{'MATCH':<40} | {'LINE':>5} | {'EXPECT':>6} | {'DELTA':>6} | {'ACTION':<12}")
    print("-" * 85)
    
    if output["top_overs"]:
        print("\n[OVERS]")
        for e in output["top_overs"]:
            action_str = f"{e['direction']} ({e['action']})"
            print(f"{e['match']:<40} | {e['line']:>5.1f} | {e['expected']:>6.1f} | {e['delta']:>+6.1f} | {action_str:<12}")
    
    if output["top_unders"]:
        print("\n[UNDERS]")
        for e in output["top_unders"]:
            action_str = f"{e['direction']} ({e['action']})"
            print(f"{e['match']:<40} | {e['line']:>5.1f} | {e['expected']:>6.1f} | {e['delta']:>+6.1f} | {action_str:<12}")
    
    if not output["top_overs"] and not output["top_unders"]:
        print("\n(No actionable edges found)")
    
    print("=" * 85)


def save_output(output: Dict) -> Path:
    """Save output to JSON file."""
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = OUTPUTS_DIR / f"total_games_v2_{ts}.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    
    latest = OUTPUTS_DIR / "total_games_v2_latest.json"
    latest.write_text(json.dumps(output, indent=2), encoding="utf-8")
    
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Total Games Engine v2 — Structural Model")
    parser.add_argument("--paste-file", type=str, help="Path to slate paste file")
    parser.add_argument("--surface", type=str, help="Override surface (HARD/CLAY/GRASS/INDOOR)")
    parser.add_argument("--tournament", type=str, help="Tournament name for surface lookup")
    parser.add_argument("--max-per-side", type=int, default=5, help="Max edges per direction")
    parser.add_argument("--json", action="store_true", help="Output JSON only (no table)")
    
    args = parser.parse_args()
    
    if args.paste_file:
        raw = Path(args.paste_file).read_text(encoding="utf-8")
    else:
        print("\nPaste slate (Enter twice when done):")
        lines = []
        empty = 0
        while empty < 2:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip():
                empty += 1
            else:
                empty = 0
                lines.append(line)
        raw = "\n".join(lines)
    
    output = process_slate(
        raw_text=raw,
        surface_override=args.surface,
        tournament=args.tournament,
        max_per_side=args.max_per_side,
    )
    
    out_path = save_output(output)
    
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print_results(output)
        print(f"\nSaved: {out_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
