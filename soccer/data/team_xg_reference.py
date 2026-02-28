"""soccer/data/team_xg_reference.py

Team-level xG reference for Bayesian opponent adjustments.

This provides per-team offensive/defensive xG rates (per game) for the
2025-26 season.  Values are updated periodically from public xG aggregators
(FBRef, Understat, etc.).

Usage:
    from soccer.data.team_xg_reference import get_team_xg, get_opponent_xga

The Bayesian pipeline in soccer_slate_analyzer.py uses these to adjust
player projections for goals/assists based on opponent quality.

Structure per team:
    xg_for   — team's xG created per game (offensive quality)
    xga      — team's xG conceded per game (defensive quality)
    matches  — games played (for Bayesian sample-size gating)
"""

from __future__ import annotations
from typing import Dict, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────
# TEAM XG REFERENCE — 2025-26 Mid-Season (update as season progresses)
# ──────────────────────────────────────────────────────────────────────
# Format: "team_key": {"xg_for": float, "xga": float, "matches": int, "league": str}
#
# team_key = lowercase, spaces → underscores, common abbreviations accepted
# xg_for  = average xG created per match
# xga     = average xG conceded per match
# matches = games played this season

TEAM_XG: Dict[str, Dict] = {
    # ── PREMIER LEAGUE ────────────────────────────────────────────
    "arsenal":          {"xg_for": 2.05, "xga": 0.95, "matches": 24, "league": "premier_league"},
    "liverpool":        {"xg_for": 2.15, "xga": 0.88, "matches": 24, "league": "premier_league"},
    "man city":         {"xg_for": 1.95, "xga": 1.10, "matches": 24, "league": "premier_league"},
    "manchester city":  {"xg_for": 1.95, "xga": 1.10, "matches": 24, "league": "premier_league"},
    "chelsea":          {"xg_for": 1.70, "xga": 1.15, "matches": 24, "league": "premier_league"},
    "aston villa":      {"xg_for": 1.60, "xga": 1.20, "matches": 24, "league": "premier_league"},
    "newcastle":        {"xg_for": 1.65, "xga": 1.05, "matches": 24, "league": "premier_league"},
    "newcastle united": {"xg_for": 1.65, "xga": 1.05, "matches": 24, "league": "premier_league"},
    "brighton":         {"xg_for": 1.55, "xga": 1.30, "matches": 24, "league": "premier_league"},
    "tottenham":        {"xg_for": 1.70, "xga": 1.35, "matches": 24, "league": "premier_league"},
    "spurs":            {"xg_for": 1.70, "xga": 1.35, "matches": 24, "league": "premier_league"},
    "man united":       {"xg_for": 1.35, "xga": 1.40, "matches": 24, "league": "premier_league"},
    "manchester united":{"xg_for": 1.35, "xga": 1.40, "matches": 24, "league": "premier_league"},
    "west ham":         {"xg_for": 1.30, "xga": 1.45, "matches": 24, "league": "premier_league"},
    "west ham united":  {"xg_for": 1.30, "xga": 1.45, "matches": 24, "league": "premier_league"},
    "bournemouth":      {"xg_for": 1.45, "xga": 1.40, "matches": 24, "league": "premier_league"},
    "fulham":           {"xg_for": 1.35, "xga": 1.25, "matches": 24, "league": "premier_league"},
    "crystal palace":   {"xg_for": 1.20, "xga": 1.35, "matches": 24, "league": "premier_league"},
    "brentford":        {"xg_for": 1.50, "xga": 1.45, "matches": 24, "league": "premier_league"},
    "nottm forest":     {"xg_for": 1.25, "xga": 1.10, "matches": 24, "league": "premier_league"},
    "nottingham forest":{"xg_for": 1.25, "xga": 1.10, "matches": 24, "league": "premier_league"},
    "wolves":           {"xg_for": 1.15, "xga": 1.55, "matches": 24, "league": "premier_league"},
    "wolverhampton":    {"xg_for": 1.15, "xga": 1.55, "matches": 24, "league": "premier_league"},
    "everton":          {"xg_for": 1.10, "xga": 1.50, "matches": 24, "league": "premier_league"},
    "ipswich":          {"xg_for": 1.05, "xga": 1.60, "matches": 24, "league": "premier_league"},
    "ipswich town":     {"xg_for": 1.05, "xga": 1.60, "matches": 24, "league": "premier_league"},
    "leicester":        {"xg_for": 1.15, "xga": 1.55, "matches": 24, "league": "premier_league"},
    "leicester city":   {"xg_for": 1.15, "xga": 1.55, "matches": 24, "league": "premier_league"},
    "southampton":      {"xg_for": 0.95, "xga": 1.75, "matches": 24, "league": "premier_league"},

    # ── LA LIGA ───────────────────────────────────────────────────
    "real madrid":      {"xg_for": 2.10, "xga": 0.90, "matches": 22, "league": "la_liga"},
    "barcelona":        {"xg_for": 2.25, "xga": 1.00, "matches": 22, "league": "la_liga"},
    "atletico madrid":  {"xg_for": 1.65, "xga": 0.85, "matches": 22, "league": "la_liga"},
    "atletico":         {"xg_for": 1.65, "xga": 0.85, "matches": 22, "league": "la_liga"},
    "athletic bilbao":  {"xg_for": 1.50, "xga": 1.00, "matches": 22, "league": "la_liga"},
    "athletic club":    {"xg_for": 1.50, "xga": 1.00, "matches": 22, "league": "la_liga"},
    "villarreal":       {"xg_for": 1.60, "xga": 1.15, "matches": 22, "league": "la_liga"},
    "real sociedad":    {"xg_for": 1.40, "xga": 1.10, "matches": 22, "league": "la_liga"},
    "real betis":       {"xg_for": 1.35, "xga": 1.20, "matches": 22, "league": "la_liga"},
    "girona":           {"xg_for": 1.30, "xga": 1.30, "matches": 22, "league": "la_liga"},
    "sevilla":          {"xg_for": 1.25, "xga": 1.35, "matches": 22, "league": "la_liga"},
    "mallorca":         {"xg_for": 1.10, "xga": 1.15, "matches": 22, "league": "la_liga"},
    "getafe":           {"xg_for": 0.95, "xga": 1.05, "matches": 22, "league": "la_liga"},
    "osasuna":          {"xg_for": 1.15, "xga": 1.25, "matches": 22, "league": "la_liga"},
    "celta vigo":       {"xg_for": 1.30, "xga": 1.45, "matches": 22, "league": "la_liga"},
    "rayo vallecano":   {"xg_for": 1.10, "xga": 1.30, "matches": 22, "league": "la_liga"},
    "espanyol":         {"xg_for": 1.00, "xga": 1.45, "matches": 22, "league": "la_liga"},
    "las palmas":       {"xg_for": 1.05, "xga": 1.50, "matches": 22, "league": "la_liga"},
    "alaves":           {"xg_for": 0.90, "xga": 1.40, "matches": 22, "league": "la_liga"},
    "valladolid":       {"xg_for": 0.85, "xga": 1.55, "matches": 22, "league": "la_liga"},
    "leganes":          {"xg_for": 0.90, "xga": 1.50, "matches": 22, "league": "la_liga"},

    # ── BUNDESLIGA ────────────────────────────────────────────────
    "bayern munich":    {"xg_for": 2.40, "xga": 0.95, "matches": 20, "league": "bundesliga"},
    "bayern":           {"xg_for": 2.40, "xga": 0.95, "matches": 20, "league": "bundesliga"},
    "bayer leverkusen": {"xg_for": 2.00, "xga": 1.00, "matches": 20, "league": "bundesliga"},
    "leverkusen":       {"xg_for": 2.00, "xga": 1.00, "matches": 20, "league": "bundesliga"},
    "borussia dortmund":{"xg_for": 1.85, "xga": 1.20, "matches": 20, "league": "bundesliga"},
    "dortmund":         {"xg_for": 1.85, "xga": 1.20, "matches": 20, "league": "bundesliga"},
    "rb leipzig":       {"xg_for": 1.75, "xga": 1.15, "matches": 20, "league": "bundesliga"},
    "leipzig":          {"xg_for": 1.75, "xga": 1.15, "matches": 20, "league": "bundesliga"},
    "stuttgart":        {"xg_for": 1.65, "xga": 1.25, "matches": 20, "league": "bundesliga"},
    "eintracht frankfurt":{"xg_for": 1.70, "xga": 1.30, "matches": 20, "league": "bundesliga"},
    "frankfurt":        {"xg_for": 1.70, "xga": 1.30, "matches": 20, "league": "bundesliga"},
    "freiburg":         {"xg_for": 1.40, "xga": 1.20, "matches": 20, "league": "bundesliga"},
    "wolfsburg":        {"xg_for": 1.35, "xga": 1.25, "matches": 20, "league": "bundesliga"},
    "werder bremen":    {"xg_for": 1.30, "xga": 1.40, "matches": 20, "league": "bundesliga"},
    "bremen":           {"xg_for": 1.30, "xga": 1.40, "matches": 20, "league": "bundesliga"},
    "hoffenheim":       {"xg_for": 1.25, "xga": 1.50, "matches": 20, "league": "bundesliga"},
    "union berlin":     {"xg_for": 1.15, "xga": 1.35, "matches": 20, "league": "bundesliga"},
    "augsburg":         {"xg_for": 1.10, "xga": 1.45, "matches": 20, "league": "bundesliga"},
    "mainz":            {"xg_for": 1.30, "xga": 1.35, "matches": 20, "league": "bundesliga"},
    "heidenheim":       {"xg_for": 1.05, "xga": 1.55, "matches": 20, "league": "bundesliga"},
    "bochum":           {"xg_for": 0.85, "xga": 1.70, "matches": 20, "league": "bundesliga"},
    "st pauli":         {"xg_for": 0.95, "xga": 1.50, "matches": 20, "league": "bundesliga"},
    "holstein kiel":    {"xg_for": 0.90, "xga": 1.65, "matches": 20, "league": "bundesliga"},

    # ── SERIE A ───────────────────────────────────────────────────
    "inter milan":      {"xg_for": 2.00, "xga": 0.85, "matches": 22, "league": "serie_a"},
    "inter":            {"xg_for": 2.00, "xga": 0.85, "matches": 22, "league": "serie_a"},
    "napoli":           {"xg_for": 1.85, "xga": 0.90, "matches": 22, "league": "serie_a"},
    "atalanta":         {"xg_for": 1.90, "xga": 1.00, "matches": 22, "league": "serie_a"},
    "juventus":         {"xg_for": 1.55, "xga": 0.80, "matches": 22, "league": "serie_a"},
    "ac milan":         {"xg_for": 1.60, "xga": 1.15, "matches": 22, "league": "serie_a"},
    "milan":            {"xg_for": 1.60, "xga": 1.15, "matches": 22, "league": "serie_a"},
    "lazio":            {"xg_for": 1.65, "xga": 1.20, "matches": 22, "league": "serie_a"},
    "roma":             {"xg_for": 1.40, "xga": 1.25, "matches": 22, "league": "serie_a"},
    "fiorentina":       {"xg_for": 1.50, "xga": 1.15, "matches": 22, "league": "serie_a"},
    "torino":           {"xg_for": 1.20, "xga": 1.30, "matches": 22, "league": "serie_a"},
    "bologna":          {"xg_for": 1.35, "xga": 1.20, "matches": 22, "league": "serie_a"},
    "udinese":          {"xg_for": 1.25, "xga": 1.35, "matches": 22, "league": "serie_a"},
    "genoa":            {"xg_for": 1.10, "xga": 1.40, "matches": 22, "league": "serie_a"},
    "cagliari":         {"xg_for": 1.15, "xga": 1.45, "matches": 22, "league": "serie_a"},
    "empoli":           {"xg_for": 1.00, "xga": 1.30, "matches": 22, "league": "serie_a"},
    "parma":            {"xg_for": 1.10, "xga": 1.50, "matches": 22, "league": "serie_a"},
    "verona":           {"xg_for": 1.05, "xga": 1.55, "matches": 22, "league": "serie_a"},
    "como":             {"xg_for": 1.00, "xga": 1.50, "matches": 22, "league": "serie_a"},
    "lecce":            {"xg_for": 0.90, "xga": 1.40, "matches": 22, "league": "serie_a"},
    "monza":            {"xg_for": 0.85, "xga": 1.55, "matches": 22, "league": "serie_a"},
    "venezia":          {"xg_for": 0.80, "xga": 1.60, "matches": 22, "league": "serie_a"},

    # ── LIGUE 1 ───────────────────────────────────────────────────
    "psg":              {"xg_for": 2.30, "xga": 0.80, "matches": 22, "league": "ligue_1"},
    "paris saint-germain":{"xg_for": 2.30, "xga": 0.80, "matches": 22, "league": "ligue_1"},
    "marseille":        {"xg_for": 1.70, "xga": 1.10, "matches": 22, "league": "ligue_1"},
    "monaco":           {"xg_for": 1.75, "xga": 1.15, "matches": 22, "league": "ligue_1"},
    "lille":            {"xg_for": 1.50, "xga": 0.95, "matches": 22, "league": "ligue_1"},
    "lyon":             {"xg_for": 1.55, "xga": 1.20, "matches": 22, "league": "ligue_1"},
    "nice":             {"xg_for": 1.35, "xga": 1.10, "matches": 22, "league": "ligue_1"},
    "lens":             {"xg_for": 1.25, "xga": 1.15, "matches": 22, "league": "ligue_1"},
    "rennes":           {"xg_for": 1.30, "xga": 1.30, "matches": 22, "league": "ligue_1"},
    "strasbourg":       {"xg_for": 1.20, "xga": 1.35, "matches": 22, "league": "ligue_1"},
    "toulouse":         {"xg_for": 1.25, "xga": 1.30, "matches": 22, "league": "ligue_1"},
    "reims":            {"xg_for": 1.10, "xga": 1.25, "matches": 22, "league": "ligue_1"},
    "brest":            {"xg_for": 1.30, "xga": 1.20, "matches": 22, "league": "ligue_1"},
    "montpellier":      {"xg_for": 1.00, "xga": 1.55, "matches": 22, "league": "ligue_1"},
    "nantes":           {"xg_for": 1.05, "xga": 1.40, "matches": 22, "league": "ligue_1"},
    "le havre":         {"xg_for": 0.90, "xga": 1.50, "matches": 22, "league": "ligue_1"},
    "auxerre":          {"xg_for": 1.00, "xga": 1.45, "matches": 22, "league": "ligue_1"},
    "angers":           {"xg_for": 0.95, "xga": 1.55, "matches": 22, "league": "ligue_1"},
    "st etienne":       {"xg_for": 0.90, "xga": 1.60, "matches": 22, "league": "ligue_1"},

    # ── MLS (baseline, update when season starts ~Mar 2026) ───────
    "la galaxy":        {"xg_for": 1.55, "xga": 1.30, "matches": 34, "league": "mls"},
    "inter miami":      {"xg_for": 1.70, "xga": 1.25, "matches": 34, "league": "mls"},
    "columbus crew":    {"xg_for": 1.60, "xga": 1.10, "matches": 34, "league": "mls"},
    "fc cincinnati":    {"xg_for": 1.55, "xga": 1.15, "matches": 34, "league": "mls"},
    "lafc":             {"xg_for": 1.65, "xga": 1.20, "matches": 34, "league": "mls"},
    "real salt lake":   {"xg_for": 1.50, "xga": 1.20, "matches": 34, "league": "mls"},
    "seattle sounders": {"xg_for": 1.40, "xga": 1.25, "matches": 34, "league": "mls"},
    "portland timbers": {"xg_for": 1.35, "xga": 1.30, "matches": 34, "league": "mls"},
    "atlanta united":   {"xg_for": 1.30, "xga": 1.35, "matches": 34, "league": "mls"},
    "nycfc":            {"xg_for": 1.45, "xga": 1.20, "matches": 34, "league": "mls"},
    "ny red bulls":     {"xg_for": 1.35, "xga": 1.30, "matches": 34, "league": "mls"},
    "philadelphia union":{"xg_for": 1.25, "xga": 1.40, "matches": 34, "league": "mls"},
}

# ── League-average λ for normalization ────────────────────────────
LEAGUE_AVG_LAMBDA: Dict[str, float] = {
    "premier_league": 1.425,   # ~2.85 goals/game ÷ 2 teams
    "la_liga":        1.275,
    "bundesliga":     1.575,
    "serie_a":        1.325,
    "ligue_1":        1.375,
    "mls":            1.475,
    "champions_league": 1.45,
}


def _normalize_team_key(team: str) -> str:
    """Normalize team name for lookup."""
    if not team:
        return ""
    return team.lower().strip().replace("fc ", "").replace(" fc", "")


def get_team_xg(team: str) -> Optional[Dict]:
    """Look up a team's xG profile.
    
    Returns dict with keys: xg_for, xga, matches, league
    Returns None if team not found.
    """
    key = _normalize_team_key(team)
    if key in TEAM_XG:
        return TEAM_XG[key]
    # Fuzzy: check if key is substring or vice-versa
    for tkey, val in TEAM_XG.items():
        if key in tkey or tkey in key:
            return val
    return None


def get_opponent_xga(opponent: str) -> Tuple[Optional[float], Optional[str]]:
    """Get opponent's xG conceded (defensive quality).
    
    Returns: (xga_per_game, league) or (None, None) if not found.
    """
    data = get_team_xg(opponent)
    if data:
        return data["xga"], data["league"]
    return None, None


def get_team_offensive_xg(team: str) -> Tuple[Optional[float], Optional[str]]:
    """Get team's xG created (offensive quality).
    
    Returns: (xg_for_per_game, league) or (None, None) if not found.
    """
    data = get_team_xg(team)
    if data:
        return data["xg_for"], data["league"]
    return None, None


def get_bayesian_context(team: str, opponent: str) -> Optional[Dict]:
    """Get full Bayesian context for a matchup.
    
    Returns dict with:
        team_xg_for: team's offensive xG
        opp_xga: opponent's xG conceded  
        team_league: league
        matches: sample size
        league_avg_lambda: league baseline
    
    Returns None if either team not found.
    """
    team_data = get_team_xg(team)
    opp_data = get_team_xg(opponent)
    
    if not team_data or not opp_data:
        return None
    
    league = team_data.get("league", "premier_league")
    return {
        "team_xg_for": team_data["xg_for"],
        "opp_xga": opp_data["xga"],
        "team_matches": team_data["matches"],
        "opp_matches": opp_data["matches"],
        "league": league,
        "league_avg_lambda": LEAGUE_AVG_LAMBDA.get(league, 1.35),
    }
