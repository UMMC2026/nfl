"""
TOTAL GAMES ENGINE — Core Logic
================================
Minimal, deterministic, production-ready.

No hidden data dependencies.
No guessing.
Pure structural math.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

# =========================
# CONFIG / CONSTANTS
# =========================

SURFACE_BASELINES = {
    "HARD": 9.9,
    "CLAY": 9.5,
    "GRASS": 10.8,
    "INDOOR": 10.5,
}

# Grand Slam tournaments (ATP is Bo5)
GRAND_SLAMS = {
    "australian open", "french open", "roland garros", 
    "wimbledon", "us open",
}

# WTA player name indicators (for tour detection)
WTA_INDICATORS = {
    "elena", "iga", "aryna", "coco", "naomi", "jessica", "emma",
    "belinda", "madison", "jelena", "paula", "maria", "petra",
    "caroline", "victoria", "daria", "donna", "marketa", "barbora",
    "sloane", "peyton", "amanda", "leylah", "magda", "lucia",
    "katerina", "varvara", "nikola", "julia", "moyuka", "marie",
    "rybakina", "swiatek", "sabalenka", "gauff", "pegula", "bencic",
    "keys", "ostapenko", "bouzkova", "gracheva", "bartunkova",
}

STRONG_EDGE = 3.0
LEAN_EDGE = 1.5
BO5_THRESHOLD = 33.5


# =========================
# DATA MODELS
# =========================

@dataclass
class MatchInput:
    player_1: str
    player_2: str
    total_games_line: float
    tournament: Optional[str] = None
    surface: Optional[str] = None
    date: Optional[str] = None
    rating_gap: str = "EVEN"  # EVEN | LARGE
    is_wta: Optional[bool] = None  # None = auto-detect


@dataclass
class MatchOutput:
    match_id: str
    player_1: str
    player_2: str
    tournament: str
    surface: Optional[str]
    format: str
    total_games_line: float
    expected_games: Optional[float]
    delta: Optional[float]
    direction: Optional[str]
    confidence: Optional[str]
    block_reason: Optional[str]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "player_1": self.player_1,
            "player_2": self.player_2,
            "tournament": self.tournament,
            "surface": self.surface,
            "format": self.format,
            "total_games_line": self.total_games_line,
            "expected_games": self.expected_games,
            "delta": self.delta,
            "direction": self.direction,
            "confidence": self.confidence,
            "block_reason": self.block_reason,
            "timestamp": self.timestamp,
        }


# =========================
# CORE ENGINE
# =========================

def infer_format(line: float, tournament: str = "", is_wta: bool = False) -> str:
    """
    Infer Bo3 vs Bo5 from line and context.
    
    Rules:
    1. WTA is ALWAYS Bo3
    2. ATP at Grand Slams is ALWAYS Bo5
    3. Otherwise: line > 33.5 → Bo5, else Bo3
    """
    # WTA is always Bo3
    if is_wta:
        return "Bo3"
    
    # ATP at Grand Slams is always Bo5
    if tournament and tournament.lower().strip() in GRAND_SLAMS:
        return "Bo5"
    
    # Default: infer from line
    return "Bo5" if line > BO5_THRESHOLD else "Bo3"


def detect_wta(player_1: str, player_2: str) -> bool:
    """Detect if match is WTA based on player names."""
    combined = (player_1 + " " + player_2).lower()
    for indicator in WTA_INDICATORS:
        if indicator in combined:
            return True
    return False


def surface_baseline(surface: str) -> float:
    """
    Expected games per set by surface.
    
    HARD:   9.9
    CLAY:   9.5
    GRASS: 10.8
    INDOOR: 10.5
    """
    return SURFACE_BASELINES.get(surface.upper(), 9.9)


def estimate_expected_sets(format_: str, rating_gap: str = "EVEN") -> float:
    """
    Expected sets based on format and rating gap.
    
    Bo3:
      LARGE mismatch → 2.2 sets
      EVEN → 2.7 sets
    
    Bo5:
      LARGE mismatch → 3.4 sets
      EVEN → 4.2 sets
    """
    if format_ == "Bo3":
        return 2.2 if rating_gap == "LARGE" else 2.7
    else:
        return 3.4 if rating_gap == "LARGE" else 4.2


def classify_confidence(delta: float, format_: str) -> str:
    """
    Confidence tier from edge magnitude.
    
    |Δ| ≥ 3.0 → STRONG
    |Δ| ≥ 1.5 → LEAN
    |Δ| < 1.5 → NO_PLAY
    
    Governance: Bo5 STRONG → downgrade to LEAN (variance too high)
    """
    abs_delta = abs(delta)

    if abs_delta >= STRONG_EDGE:
        conf = "STRONG"
    elif abs_delta >= LEAN_EDGE:
        conf = "LEAN"
    else:
        conf = "NO_PLAY"

    # Governance downgrade for Bo5 (variance is extreme)
    if conf == "STRONG" and format_ == "Bo5":
        return "LEAN"

    return conf


def process_match(match: MatchInput, surface: Optional[str] = None) -> MatchOutput:
    """
    Process a single match through the engine.
    
    Returns MatchOutput with all computed fields.
    """
    match_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Use provided surface or match.surface
    surf = surface or match.surface
    
    # Detect WTA if not specified
    is_wta = match.is_wta if match.is_wta is not None else detect_wta(match.player_1, match.player_2)
    
    # Infer format with full context
    format_ = infer_format(match.total_games_line, match.tournament or "", is_wta)

    # Block if no surface
    if surf is None:
        return MatchOutput(
            match_id=match_id,
            player_1=match.player_1,
            player_2=match.player_2,
            tournament=match.tournament or "",
            surface=None,
            format=format_,
            total_games_line=match.total_games_line,
            expected_games=None,
            delta=None,
            direction=None,
            confidence=None,
            block_reason="NO_SURFACE",
            timestamp=timestamp,
        )

    surf = surf.upper()
    if surf not in SURFACE_BASELINES:
        return MatchOutput(
            match_id=match_id,
            player_1=match.player_1,
            player_2=match.player_2,
            tournament=match.tournament or "",
            surface=surf,
            format=format_,
            total_games_line=match.total_games_line,
            expected_games=None,
            delta=None,
            direction=None,
            confidence=None,
            block_reason="INVALID_SURFACE",
            timestamp=timestamp,
        )

    # Core calculation
    E_sets = estimate_expected_sets(format_, match.rating_gap)
    E_games_set = surface_baseline(surf)
    expected_games = round(E_sets * E_games_set, 2)

    delta = round(expected_games - match.total_games_line, 2)
    direction = "OVER" if delta > 0 else "UNDER"
    confidence = classify_confidence(delta, format_)

    # NO_PLAY nullifies direction
    if confidence == "NO_PLAY":
        direction = None

    return MatchOutput(
        match_id=match_id,
        player_1=match.player_1,
        player_2=match.player_2,
        tournament=match.tournament or "",
        surface=surf,
        format=format_,
        total_games_line=match.total_games_line,
        expected_games=expected_games,
        delta=delta,
        direction=direction,
        confidence=confidence,
        block_reason=None,
        timestamp=timestamp,
    )


def process_slate(matches: list, surface: Optional[str] = None) -> list:
    """
    Process a list of MatchInput objects.
    
    Returns list of MatchOutput.
    """
    return [process_match(m, surface) for m in matches]
