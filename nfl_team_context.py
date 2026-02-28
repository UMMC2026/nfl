"""
NFL Team Context - Offensive/Defensive Rankings, Pace, Weather Factors
Updated: January 2026 (2025-26 Season - Playoffs)

Sources: NFL.com/stats, Pro-Football-Reference, ESPN
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class OffensiveScheme(Enum):
    WEST_COAST = "west_coast"         # Short passes, YAC-focused
    AIR_RAID = "air_raid"             # Spread, high-volume passing
    SPREAD = "spread"                 # Quick reads, RPO heavy
    PRO_STYLE = "pro_style"           # Balanced, play-action
    POWER_RUN = "power_run"           # Ground-heavy, play-action
    SHANAHAN = "shanahan"             # Zone run, bootlegs


@dataclass
class NFLTeamContext:
    """Full context for an NFL team."""
    team: str
    off_rank: int              # 1-32 offensive rank (1 = best)
    def_rank: int              # 1-32 defensive rank (1 = best)
    pass_off_rank: int         # Pass offense rank
    rush_off_rank: int         # Rush offense rank
    pass_def_rank: int         # Pass defense rank
    rush_def_rank: int         # Rush defense rank
    plays_per_game: float      # Pace indicator
    scheme: OffensiveScheme    # Offensive philosophy
    
    # Context notes
    notes: str = ""
    dome: bool = False         # Indoor stadium
    altitude: bool = False     # Denver only


# NFL Team Context (2025-26 Season - Playoff Picture)
NFL_TEAM_CONTEXT: Dict[str, NFLTeamContext] = {
    # === AFC PLAYOFF TEAMS ===
    "KC": NFLTeamContext(
        team="KC", off_rank=7, def_rank=8,
        pass_off_rank=10, rush_off_rank=14,
        pass_def_rank=6, rush_def_rank=12,
        plays_per_game=64.5, scheme=OffensiveScheme.WEST_COAST,
        notes="Mahomes elite. Kelce safety valve. Balanced attack. Elite red zone.",
        dome=False
    ),
    "BUF": NFLTeamContext(
        team="BUF", off_rank=2, def_rank=10,
        pass_off_rank=3, rush_off_rank=8,
        pass_def_rank=12, rush_def_rank=8,
        plays_per_game=67.2, scheme=OffensiveScheme.SPREAD,
        notes="Josh Allen MVP. James Cook breakout. High-tempo. Cold weather.",
        dome=False
    ),
    "BAL": NFLTeamContext(
        team="BAL", off_rank=1, def_rank=4,
        pass_off_rank=8, rush_off_rank=1,
        pass_def_rank=5, rush_def_rank=3,
        plays_per_game=62.8, scheme=OffensiveScheme.POWER_RUN,
        notes="Lamar MVP. Derrick Henry dominant. Elite run game. Zay Flowers emerging.",
        dome=True
    ),
    "HOU": NFLTeamContext(
        team="HOU", off_rank=11, def_rank=15,
        pass_off_rank=12, rush_off_rank=18,
        pass_def_rank=14, rush_def_rank=16,
        plays_per_game=63.5, scheme=OffensiveScheme.SPREAD,
        notes="Stroud sophomore. Nico Collins elite. Tank Dell explosive. Joe Mixon steady.",
        dome=True
    ),
    "PIT": NFLTeamContext(
        team="PIT", off_rank=20, def_rank=3,
        pass_off_rank=22, rush_off_rank=15,
        pass_def_rank=4, rush_def_rank=2,
        plays_per_game=60.5, scheme=OffensiveScheme.PRO_STYLE,
        notes="Elite defense. T.J. Watt dominant. Russ/Fields rotation. Low-scoring games.",
        dome=False
    ),
    "DEN": NFLTeamContext(
        team="DEN", off_rank=18, def_rank=7,
        pass_off_rank=20, rush_off_rank=12,
        pass_def_rank=8, rush_def_rank=6,
        plays_per_game=62.0, scheme=OffensiveScheme.WEST_COAST,
        notes="Bo Nix rookie. Sutton WR1. Altitude factor. Strong D.",
        dome=False, altitude=True
    ),
    "LAC": NFLTeamContext(
        team="LAC", off_rank=14, def_rank=5,
        pass_off_rank=15, rush_off_rank=10,
        pass_def_rank=3, rush_def_rank=9,
        plays_per_game=61.8, scheme=OffensiveScheme.PRO_STYLE,
        notes="Herbert talent. Harbaugh scheme. Run-first shift. Elite D.",
        dome=False
    ),
    
    # === NFC PLAYOFF TEAMS ===
    "PHI": NFLTeamContext(
        team="PHI", off_rank=3, def_rank=2,
        pass_off_rank=6, rush_off_rank=2,
        pass_def_rank=2, rush_def_rank=4,
        plays_per_game=65.5, scheme=OffensiveScheme.SPREAD,
        notes="Saquon MVP candidate. Hurts dual-threat. A.J. Brown elite. Top 3 D.",
        dome=False
    ),
    "WSH": NFLTeamContext(
        team="WSH", off_rank=8, def_rank=18,
        pass_off_rank=5, rush_off_rank=20,
        pass_def_rank=20, rush_def_rank=15,
        plays_per_game=66.0, scheme=OffensiveScheme.SPREAD,
        notes="Jayden Daniels OROY. Dual-threat. Terry McLaurin WR1. Young D.",
        dome=False
    ),
    "DET": NFLTeamContext(
        team="DET", off_rank=4, def_rank=12,
        pass_off_rank=4, rush_off_rank=6,
        pass_def_rank=15, rush_def_rank=10,
        plays_per_game=68.5, scheme=OffensiveScheme.SHANAHAN,
        notes="Goff efficient. Gibbs/Montgomery elite duo. Amon-Ra PPR king. Fast pace.",
        dome=True
    ),
    "GB": NFLTeamContext(
        team="GB", off_rank=6, def_rank=14,
        pass_off_rank=7, rush_off_rank=9,
        pass_def_rank=16, rush_def_rank=11,
        plays_per_game=64.0, scheme=OffensiveScheme.WEST_COAST,
        notes="Jordan Love breakout. Josh Jacobs workhorse. Young WR corps. Cold weather.",
        dome=False
    ),
    "MIN": NFLTeamContext(
        team="MIN", off_rank=5, def_rank=6,
        pass_off_rank=2, rush_off_rank=16,
        pass_def_rank=7, rush_def_rank=5,
        plays_per_game=66.5, scheme=OffensiveScheme.SPREAD,
        notes="Darnold resurgence. Justin Jefferson WR1. Aaron Jones solid. Balanced D.",
        dome=True
    ),
    "TB": NFLTeamContext(
        team="TB", off_rank=9, def_rank=16,
        pass_off_rank=9, rush_off_rank=13,
        pass_def_rank=18, rush_def_rank=14,
        plays_per_game=64.2, scheme=OffensiveScheme.AIR_RAID,
        notes="Baker redemption. Mike Evans consistent. Bucky Irving emerging.",
        dome=True
    ),
    "LAR": NFLTeamContext(
        team="LAR", off_rank=10, def_rank=17,
        pass_off_rank=11, rush_off_rank=11,
        pass_def_rank=19, rush_def_rank=13,
        plays_per_game=65.0, scheme=OffensiveScheme.SHANAHAN,
        notes="Stafford steady. Puka Nacua elite. Kupp injury history. Kyren Williams.",
        dome=True
    ),
    "SF": NFLTeamContext(
        team="SF", off_rank=12, def_rank=9,
        pass_off_rank=14, rush_off_rank=5,
        pass_def_rank=10, rush_def_rank=7,
        plays_per_game=63.0, scheme=OffensiveScheme.SHANAHAN,
        notes="CMC injury concern. Purdy efficient. Deebo gadget. Bosa elite.",
        dome=False
    ),
    
    # === OTHER TEAMS ===
    "CIN": NFLTeamContext(
        team="CIN", off_rank=13, def_rank=22,
        pass_off_rank=1, rush_off_rank=28,
        pass_def_rank=24, rush_def_rank=20,
        plays_per_game=67.0, scheme=OffensiveScheme.SPREAD,
        notes="Burrow elite. Chase best WR. Pass-heavy. Poor run game.",
        dome=False
    ),
    "MIA": NFLTeamContext(
        team="MIA", off_rank=15, def_rank=13,
        pass_off_rank=13, rush_off_rank=7,
        pass_def_rank=11, rush_def_rank=18,
        plays_per_game=68.0, scheme=OffensiveScheme.SHANAHAN,
        notes="Tua health. Hill/Waddle speed. Achane explosive. High pace.",
        dome=True
    ),
    "SEA": NFLTeamContext(
        team="SEA", off_rank=16, def_rank=19,
        pass_off_rank=16, rush_off_rank=17,
        pass_def_rank=21, rush_def_rank=17,
        plays_per_game=64.5, scheme=OffensiveScheme.WEST_COAST,
        notes="Geno solid. DK/Lockett/JSN trio. K9 health. Rebuilding D.",
        dome=False
    ),
    "ARI": NFLTeamContext(
        team="ARI", off_rank=17, def_rank=25,
        pass_off_rank=17, rush_off_rank=19,
        pass_def_rank=26, rush_def_rank=22,
        plays_per_game=65.5, scheme=OffensiveScheme.SPREAD,
        notes="Kyler mobile. Marvin Harrison Jr. rookie. Conner steady. Poor D.",
        dome=True
    ),
    "ATL": NFLTeamContext(
        team="ATL", off_rank=19, def_rank=21,
        pass_off_rank=18, rush_off_rank=4,
        pass_def_rank=22, rush_def_rank=19,
        plays_per_game=63.5, scheme=OffensiveScheme.PRO_STYLE,
        notes="Cousins decline. Bijan elite RB. Drake London. Penix waiting.",
        dome=True
    ),
    "DAL": NFLTeamContext(
        team="DAL", off_rank=22, def_rank=24,
        pass_off_rank=21, rush_off_rank=24,
        pass_def_rank=25, rush_def_rank=21,
        plays_per_game=62.0, scheme=OffensiveScheme.SPREAD,
        notes="Dak injured. Rush backup. CeeDee elite. Regression year.",
        dome=True
    ),
    "NYJ": NFLTeamContext(
        team="NYJ", off_rank=25, def_rank=11,
        pass_off_rank=24, rush_off_rank=21,
        pass_def_rank=9, rush_def_rank=12,
        plays_per_game=61.5, scheme=OffensiveScheme.WEST_COAST,
        notes="Rodgers decline. Breece Hall talent. Garrett Wilson. Good D.",
        dome=False
    ),
    "IND": NFLTeamContext(
        team="IND", off_rank=21, def_rank=20,
        pass_off_rank=23, rush_off_rank=3,
        pass_def_rank=17, rush_def_rank=23,
        plays_per_game=64.0, scheme=OffensiveScheme.PRO_STYLE,
        notes="Richardson injury. JT elite RB. Pittman WR1. Flacco backup.",
        dome=True
    ),
    "CLE": NFLTeamContext(
        team="CLE", off_rank=30, def_rank=1,
        pass_off_rank=30, rush_off_rank=26,
        pass_def_rank=1, rush_def_rank=1,
        plays_per_game=59.5, scheme=OffensiveScheme.PRO_STYLE,
        notes="Watson injured. Winston backup. Elite D. Myles Garrett DPOY.",
        dome=False
    ),
    "JAX": NFLTeamContext(
        team="JAX", off_rank=23, def_rank=26,
        pass_off_rank=19, rush_off_rank=25,
        pass_def_rank=27, rush_def_rank=24,
        plays_per_game=65.0, scheme=OffensiveScheme.SPREAD,
        notes="Trevor regression. Etienne solid. Brian Thomas Jr. rookie WR.",
        dome=False
    ),
    "TEN": NFLTeamContext(
        team="TEN", off_rank=26, def_rank=23,
        pass_off_rank=26, rush_off_rank=22,
        pass_def_rank=23, rush_def_rank=25,
        plays_per_game=62.5, scheme=OffensiveScheme.PRO_STYLE,
        notes="Levis struggles. Pollard RB1. Hopkins traded. Rebuilding.",
        dome=False
    ),
    "NO": NFLTeamContext(
        team="NO", off_rank=24, def_rank=27,
        pass_off_rank=25, rush_off_rank=15,
        pass_def_rank=28, rush_def_rank=26,
        plays_per_game=63.0, scheme=OffensiveScheme.PRO_STYLE,
        notes="Carr inconsistent. Kamara aging. Olave talented. Injuries hurt.",
        dome=True
    ),
    "CHI": NFLTeamContext(
        team="CHI", off_rank=27, def_rank=28,
        pass_off_rank=27, rush_off_rank=23,
        pass_def_rank=29, rush_def_rank=27,
        plays_per_game=64.5, scheme=OffensiveScheme.WEST_COAST,
        notes="Caleb Williams rookie. DJ Moore, Keenan Allen WRs. Swift RB. Rebuilding.",
        dome=True
    ),
    "NE": NFLTeamContext(
        team="NE", off_rank=28, def_rank=29,
        pass_off_rank=28, rush_off_rank=27,
        pass_def_rank=30, rush_def_rank=28,
        plays_per_game=60.0, scheme=OffensiveScheme.PRO_STYLE,
        notes="Drake Maye rookie. Limited weapons. Full rebuild.",
        dome=False
    ),
    "NYG": NFLTeamContext(
        team="NYG", off_rank=29, def_rank=30,
        pass_off_rank=29, rush_off_rank=29,
        pass_def_rank=31, rush_def_rank=29,
        plays_per_game=61.0, scheme=OffensiveScheme.PRO_STYLE,
        notes="QB carousel. Malik Nabers elite rookie. Rebuilding.",
        dome=False
    ),
    "CAR": NFLTeamContext(
        team="CAR", off_rank=31, def_rank=31,
        pass_off_rank=31, rush_off_rank=30,
        pass_def_rank=32, rush_def_rank=30,
        plays_per_game=60.5, scheme=OffensiveScheme.PRO_STYLE,
        notes="Bryce Young struggles. Chuba Hubbard bright spot. Full rebuild.",
        dome=False
    ),
    "LV": NFLTeamContext(
        team="LV", off_rank=32, def_rank=32,
        pass_off_rank=32, rush_off_rank=31,
        pass_def_rank=33, rush_def_rank=31,
        plays_per_game=61.5, scheme=OffensiveScheme.WEST_COAST,
        notes="QB mess. Brock Bowers elite TE. Davante Adams traded. Rebuild.",
        dome=True
    ),
}


def get_nfl_team_context(team: str) -> Optional[NFLTeamContext]:
    """Get NFL team context by abbreviation."""
    return NFL_TEAM_CONTEXT.get(team.upper())


def get_nfl_matchup_context(away: str, home: str) -> dict:
    """Get combined matchup context for NFL game."""
    away_ctx = get_nfl_team_context(away)
    home_ctx = get_nfl_team_context(home)
    
    if not away_ctx or not home_ctx:
        return {}
    
    return {
        "away": {
            "team": away_ctx.team,
            "off_rank": away_ctx.off_rank,
            "def_rank": away_ctx.def_rank,
            "pass_off_rank": away_ctx.pass_off_rank,
            "rush_off_rank": away_ctx.rush_off_rank,
            "notes": away_ctx.notes,
        },
        "home": {
            "team": home_ctx.team,
            "off_rank": home_ctx.off_rank,
            "def_rank": home_ctx.def_rank,
            "pass_def_rank": home_ctx.pass_def_rank,
            "rush_def_rank": home_ctx.rush_def_rank,
            "notes": home_ctx.notes,
            "dome": home_ctx.dome,
        },
        "matchup_notes": _generate_matchup_notes(away_ctx, home_ctx)
    }


def _generate_matchup_notes(away: NFLTeamContext, home: NFLTeamContext) -> str:
    """Generate matchup analysis notes."""
    notes = []
    
    # Pass offense vs Pass defense
    if away.pass_off_rank <= 10 and home.pass_def_rank >= 20:
        notes.append(f"{away.team} pass offense ({away.pass_off_rank}) vs weak {home.team} pass D ({home.pass_def_rank}) → OVERS on passing")
    elif away.pass_off_rank >= 20 and home.pass_def_rank <= 10:
        notes.append(f"{away.team} weak pass offense vs elite {home.team} pass D → UNDERS on passing")
    
    # Rush offense vs Rush defense
    if away.rush_off_rank <= 10 and home.rush_def_rank >= 20:
        notes.append(f"{away.team} rush offense ({away.rush_off_rank}) vs weak {home.team} rush D ({home.rush_def_rank}) → OVERS on rushing")
    elif away.rush_off_rank >= 20 and home.rush_def_rank <= 10:
        notes.append(f"{away.team} weak rush offense vs elite {home.team} rush D → UNDERS on rushing")
    
    # Dome game
    if home.dome:
        notes.append("Dome game → controlled environment, favor passing")
    
    # Altitude (Denver)
    if home.altitude:
        notes.append("Altitude factor → can affect fatigue, kicking")
    
    return " | ".join(notes) if notes else "Neutral matchup"
