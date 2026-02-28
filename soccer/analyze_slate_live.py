"""
Soccer Slate Quick Analyzer
===========================
Fetches real stats from API-Football and calculates probabilities.
"""

import os
import requests
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import stats as scipy_stats

# API Configuration
API_KEY = os.environ.get('RAPIDAPI_KEY', '')
API_BASE = "https://v3.football.api-sports.io"

# League IDs
LEAGUES = {
    "premier_league": 39,
    "la_liga": 140,
    "bundesliga": 78,
    "serie_a": 135,
    "ligue_1": 61,
    "mls": 253,
}


@dataclass
class PlayerProp:
    """A single player prop from the slate."""
    player: str
    team: str
    position: str
    opponent: str
    stat: str
    line: float
    direction: str = "higher"  # higher/lower


@dataclass
class PropAnalysis:
    """Analysis result for a prop."""
    player: str
    stat: str
    line: float
    direction: str
    
    # From API
    games: int
    total: int
    per_game: float
    
    # Probabilities
    prob_over: float
    prob_under: float
    recommended: str
    tier: str
    
    # Confidence
    confidence: str
    data_source: str


def fetch_player_stats(player_name: str, league_id: int = None, season: str = "2024") -> Optional[Dict]:
    """Fetch player stats from API-Football."""
    if not API_KEY:
        print(f"[!] No API key - set RAPIDAPI_KEY env var")
        return None
    
    headers = {"x-apisports-key": API_KEY}
    
    # Try multiple leagues if none specified
    leagues_to_try = [league_id] if league_id else [140, 39, 78, 135, 61]  # La Liga, EPL, Bund, Serie A, Ligue 1
    
    # Try alternate names: full, last, ASCII, lower, no accents
    import unicodedata
    def strip_accents(text):
        return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

    search_terms = [player_name]
    if ' ' in player_name:
        search_terms.append(player_name.split()[-1])  # Last name
    search_terms.append(strip_accents(player_name))
    search_terms.append(player_name.lower())
    search_terms.append(strip_accents(player_name.lower()))

    for search in search_terms:
        for lid in leagues_to_try:
            try:
                r = requests.get(
                    f"{API_BASE}/players",
                    headers=headers,
                    params={"search": search, "league": lid, "season": season},
                    timeout=10
                )
                data = r.json()
                if data.get("response"):
                    return data["response"][0]
            except Exception as e:
                continue
    print(f"[WARN] Player not found in API-Football: {player_name}")
    return None


def calculate_poisson_probability(mean: float, line: float) -> Tuple[float, float]:
    """Calculate P(X > line) and P(X < line) using Poisson distribution."""
    if mean <= 0:
        return 0.5, 0.5
    
    # For count stats (shots, passes, etc.)
    # P(X > line) = 1 - P(X <= line) = 1 - CDF(line)
    prob_under = scipy_stats.poisson.cdf(line, mean)
    prob_over = 1 - prob_under
    
    # Adjust for half-lines (e.g., 1.5)
    if line != int(line):
        # For 1.5, P(over) = P(X >= 2) = 1 - P(X <= 1)
        prob_under = scipy_stats.poisson.cdf(int(line), mean)
        prob_over = 1 - prob_under
    
    return prob_over, prob_under


def calculate_normal_probability(mean: float, std: float, line: float) -> Tuple[float, float]:
    """Calculate probabilities using normal distribution (for high-count stats like passes)."""
    if std <= 0:
        std = mean * 0.3  # Assume 30% CV if unknown
    
    z_score = (line - mean) / std
    prob_under = scipy_stats.norm.cdf(z_score)
    prob_over = 1 - prob_under
    
    return prob_over, prob_under


def get_tier(prob: float) -> str:
    """Determine tier based on probability."""
    if prob >= 0.72:
        return "STRONG"
    elif prob >= 0.60:
        return "LEAN"
    elif prob >= 0.55:
        return "SLIGHT"
    else:
        return "NO_PLAY"


def analyze_prop(prop: PlayerProp, api_key: str = None) -> Optional[PropAnalysis]:
    """Analyze a single prop using real API data."""
    global API_KEY
    if api_key:
        API_KEY = api_key
    
    # Fetch player stats
    player_data = fetch_player_stats(prop.player)
    
    if not player_data:
        return PropAnalysis(
            player=prop.player,
            stat=prop.stat,
            line=prop.line,
            direction=prop.direction,
            games=0,
            total=0,
            per_game=0.0,
            prob_over=0.5,
            prob_under=0.5,
            recommended="NO_DATA",
            tier="NO_PLAY",
            confidence="MISSING",
            data_source="none"
        )
    
    stats = player_data["statistics"][0]
    games = stats["games"]["appearences"] or 0
    
    if games == 0:
        return None
    
    # Map stat name to API field
    stat_lower = prop.stat.lower().replace(" ", "_")
    # Expanded stat mapping
    stat_mapping = {
        "passes_attempted": ("passes", "total"),
        "passes": ("passes", "total"),
        "passes_completed": ("passes", "accuracy"),
        "touches": ("passes", "total"),  # Approximation
        "shots": ("shots", "total"),
        "shots_on_target": ("shots", "on"),
        "sot": ("shots", "on"),
        "goals": ("goals", "total"),
        "assists": ("goals", "assists"),
        "goal_contributions": ("goals", "total"),  # Approximation
        "dribbles": ("dribbles", "attempts"),
        "attempted_dribbles": ("dribbles", "attempts"),
        "tackles": ("tackles", "total"),
        "crosses": ("passes", "key"),  # Approximation
        "goalie_saves": ("goals", "saves"),  # For GK
        "saves": ("goals", "saves"),
        "fouls": ("fouls", "committed"),
        "yellow_cards": ("cards", "yellow"),
        "red_cards": ("cards", "red"),
        "clearances": ("tackles", "blocks"),
    }

    # Get stat values
    if stat_lower in stat_mapping:
        category, field = stat_mapping[stat_lower]
        total = stats.get(category, {}).get(field, 0) or 0
    else:
        # Try direct lookup
        total = 0
        for cat in ["shots", "passes", "goals", "dribbles", "tackles"]:
            if stats.get(cat, {}).get("total"):
                total = stats[cat]["total"]
                break
        if total == 0:
            print(f"[WARN] Stat type not mapped/modelable: {prop.stat} for player {prop.player}")
    
    per_game = total / games if games > 0 else 0.0
    
    # Calculate probability based on stat type
    if stat_lower in ["passes", "passes_attempted", "passes_completed", "touches"]:
        # Normal distribution for high-count stats
        std = per_game * 0.25  # Assume 25% CV for passes
        prob_over, prob_under = calculate_normal_probability(per_game, std, prop.line)
    else:
        # Poisson for count stats
        prob_over, prob_under = calculate_poisson_probability(per_game, prop.line)
    
    # Determine recommendation
    if prop.direction.lower() in ["higher", "over", "more"]:
        main_prob = prob_over
        recommended = "OVER" if prob_over > 0.5 else "UNDER"
    else:
        main_prob = prob_under
        recommended = "UNDER" if prob_under > 0.5 else "OVER"
    
    tier = get_tier(main_prob)
    
    return PropAnalysis(
        player=prop.player,
        stat=prop.stat,
        line=prop.line,
        direction=prop.direction,
        games=games,
        total=total,
        per_game=per_game,
        prob_over=prob_over,
        prob_under=prob_under,
        recommended=recommended,
        tier=tier,
        confidence="HIGH" if games >= 20 else "MEDIUM" if games >= 10 else "LOW",
        data_source="api_football"
    )


def format_analysis_report(analyses: List[PropAnalysis]) -> str:
    """Format analysis results as a report."""
    lines = []
    lines.append("=" * 70)
    lines.append("⚽ SOCCER PROPS ANALYSIS (REAL DATA)")
    lines.append("=" * 70)
    
    # Group by tier
    by_tier = {"STRONG": [], "LEAN": [], "SLIGHT": [], "NO_PLAY": [], "NO_DATA": []}
    for a in analyses:
        tier = a.tier if a.tier in by_tier else "NO_DATA"
        by_tier[tier].append(a)
    
    # Show actionable first
    for tier in ["STRONG", "LEAN"]:
        if by_tier[tier]:
            lines.append(f"\n✅ [{tier}] — {len(by_tier[tier])} picks")
            lines.append("-" * 50)
            for a in sorted(by_tier[tier], key=lambda x: -max(x.prob_over, x.prob_under)):
                dir_sym = "▲" if a.recommended == "OVER" else "▼"
                prob = a.prob_over if a.recommended == "OVER" else a.prob_under
                lines.append(
                    f"  {dir_sym} {a.player} | {a.stat} {a.recommended} {a.line} | "
                    f"p={prob*100:.1f}% | avg={a.per_game:.1f}/g | n={a.games}"
                )
    
    # Show marginal
    if by_tier["SLIGHT"]:
        lines.append(f"\n⚠️ [SLIGHT EDGE] — {len(by_tier['SLIGHT'])} picks")
        for a in by_tier["SLIGHT"]:
            prob = max(a.prob_over, a.prob_under)
            lines.append(f"  {a.player} | {a.stat} {a.line} | p={prob*100:.1f}%")
    
    # Show no data
    if by_tier["NO_DATA"]:
        lines.append(f"\n❌ [NO DATA] — {len(by_tier['NO_DATA'])} picks")
        for a in by_tier["NO_DATA"]:
            lines.append(f"  {a.player} | {a.stat} {a.line}")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    import os
    os.environ['RAPIDAPI_KEY'] = '29f5fe801b18ad08ee502e5d7b4612d2'
    
    # Test props from the slate
    test_props = [
        PlayerProp("Kylian Mbappé", "Real Madrid", "Attacker", "Rayo", "SOT", 1.5, "higher"),
        PlayerProp("Kylian Mbappé", "Real Madrid", "Attacker", "Rayo", "Passes", 32.5, "higher"),
        PlayerProp("Jude Bellingham", "Real Madrid", "Midfielder", "Rayo", "Passes", 47.5, "higher"),
        PlayerProp("Vinícius Júnior", "Real Madrid", "Attacker", "Rayo", "Dribbles", 5.5, "higher"),
        PlayerProp("Ousmane Dembélé", "PSG", "Attacker", "Strasbourg", "Shots", 3.0, "higher"),
    ]
    
    print("Fetching real stats from API-Football...")
    analyses = []
    for prop in test_props:
        print(f"  → {prop.player} ({prop.stat})...")
        result = analyze_prop(prop)
        if result:
            analyses.append(result)
    
    print(format_analysis_report(analyses))
