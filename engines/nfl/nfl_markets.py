"""
NFL Market Definitions - PrizePicks Complete Coverage
NFL_AUTONOMOUS v1.0 Compatible

Canonical enum for all supported NFL prop markets.
"""

from enum import Enum

class NFLMarket(Enum):
    """Normalized NFL market identifiers for engine-wide consistency."""
    
    # === PASSING ===
    PASS_YARDS = "pass_yards"
    PASS_TDS = "pass_tds"
    PASS_ATTEMPTS = "pass_attempts"
    PASS_COMPLETIONS = "pass_completions"
    COMPLETION_PCT = "completion_pct"
    INTERCEPTIONS = "interceptions"
    LONGEST_COMPLETION = "longest_completion"
    YARDS_FIRST_COMPLETION = "yards_first_completion"
    COMPLETIONS_FIRST_10 = "completions_first_10"
    HALVES_100_PASS_YARDS = "halves_100_pass_yards"
    QUARTERS_30_PASS_YARDS = "quarters_30_pass_yards"
    
    # === RUSHING ===
    RUSH_YARDS = "rush_yards"
    RUSH_ATTEMPTS = "rush_attempts"
    LONGEST_RUSH = "longest_rush"
    YARDS_PER_CARRY = "yards_per_carry"
    RUSH_YARDS_FIRST_5 = "rush_yards_first_5"
    YARDS_FIRST_RUSH = "yards_first_rush"
    HALVES_25_RUSH_YARDS = "halves_25_rush_yards"
    QUARTERS_5_RUSH_YARDS = "quarters_5_rush_yards"
    
    # === RECEIVING ===
    REC_YARDS = "receiving_yards"
    RECEPTIONS = "receptions"
    REC_TARGETS = "receiving_targets"
    LONGEST_RECEPTION = "longest_reception"
    REC_YARDS_FIRST_2 = "rec_yards_first_2"
    YARDS_FIRST_RECEPTION = "yards_first_reception"
    QUARTERS_1_RECEPTION = "quarters_1_reception"
    HALVES_25_REC_YARDS = "halves_25_rec_yards"
    
    # === COMBO / HYBRID ===
    RUSH_REC_YARDS = "rush_rec_yards"
    PASS_RUSH_YARDS = "pass_rush_yards"
    PASS_RUSH_REC_TDS = "pass_rush_rec_tds"
    RUSH_REC_TDS = "rush_rec_tds"
    
    # === DEFENSE ===
    SACKS = "sacks"
    SACKS_TAKEN = "sacks_taken"
    TACKLES_ASSISTS = "tackles_assists"
    DEF_INTERCEPTIONS = "def_interceptions"
    
    # === SPECIAL TEAMS ===
    FG_MADE = "fg_made"
    FG_50_PLUS = "fg_50_plus"
    FG_YARDS = "fg_yards"
    LONGEST_FG = "longest_fg"
    SHORTEST_FG = "shortest_fg"
    PAT_MADE = "pat_made"
    PUNTS = "punts"
    GROSS_PUNT_YARDS = "gross_punt_yards"
    LONGEST_PUNT = "longest_punt"
    SHORTEST_PUNT = "shortest_punt"
    FIRST_PUNT_YARDS = "first_punt_yards"
    PUNTS_INSIDE_20 = "punts_inside_20"
    YARDS_PER_PUNT_AVG = "yards_per_punt_avg"


# Market display names (for reports)
MARKET_DISPLAY_NAMES = {
    NFLMarket.PASS_YARDS: "Pass Yards",
    NFLMarket.PASS_TDS: "Pass TDs",
    NFLMarket.PASS_ATTEMPTS: "Pass Attempts",
    NFLMarket.PASS_COMPLETIONS: "Pass Completions",
    NFLMarket.COMPLETION_PCT: "Completion %",
    NFLMarket.INTERCEPTIONS: "INTs",
    NFLMarket.RUSH_YARDS: "Rush Yards",
    NFLMarket.RUSH_ATTEMPTS: "Rush Attempts",
    NFLMarket.LONGEST_RUSH: "Longest Rush",
    NFLMarket.YARDS_PER_CARRY: "Yards/Carry",
    NFLMarket.REC_YARDS: "Receiving Yards",
    NFLMarket.RECEPTIONS: "Receptions",
    NFLMarket.REC_TARGETS: "Targets",
    NFLMarket.LONGEST_RECEPTION: "Longest Reception",
    NFLMarket.RUSH_REC_YARDS: "Rush + Rec Yards",
    NFLMarket.PASS_RUSH_YARDS: "Pass + Rush Yards",
    NFLMarket.RUSH_REC_TDS: "Rush + Rec TDs",
    NFLMarket.SACKS: "Sacks",
    NFLMarket.SACKS_TAKEN: "Sacks Taken",
    NFLMarket.FG_MADE: "FG Made",
    NFLMarket.FG_YARDS: "FG Yards",
    NFLMarket.PUNTS: "Punts",
    NFLMarket.GROSS_PUNT_YARDS: "Gross Punt Yards",
}


# Position eligibility per market
MARKET_POSITIONS = {
    # QB markets
    NFLMarket.PASS_YARDS: ["QB"],
    NFLMarket.PASS_TDS: ["QB"],
    NFLMarket.PASS_ATTEMPTS: ["QB"],
    NFLMarket.PASS_COMPLETIONS: ["QB"],
    NFLMarket.COMPLETION_PCT: ["QB"],
    NFLMarket.INTERCEPTIONS: ["QB"],
    NFLMarket.PASS_RUSH_YARDS: ["QB"],
    
    # RB markets
    NFLMarket.RUSH_YARDS: ["RB", "QB"],
    NFLMarket.RUSH_ATTEMPTS: ["RB", "QB"],
    NFLMarket.LONGEST_RUSH: ["RB", "QB"],
    NFLMarket.YARDS_PER_CARRY: ["RB"],
    NFLMarket.RUSH_REC_YARDS: ["RB", "WR", "TE"],
    NFLMarket.RUSH_REC_TDS: ["RB", "WR", "TE"],
    
    # WR/TE markets
    NFLMarket.REC_YARDS: ["WR", "TE", "RB"],
    NFLMarket.RECEPTIONS: ["WR", "TE", "RB"],
    NFLMarket.REC_TARGETS: ["WR", "TE", "RB"],
    NFLMarket.LONGEST_RECEPTION: ["WR", "TE", "RB"],
    
    # Defense markets
    NFLMarket.SACKS: ["DL", "LB", "DB"],
    NFLMarket.TACKLES_ASSISTS: ["DL", "LB", "DB"],
    NFLMarket.DEF_INTERCEPTIONS: ["DB", "LB"],
    
    # Special teams
    NFLMarket.FG_MADE: ["K"],
    NFLMarket.FG_YARDS: ["K"],
    NFLMarket.PAT_MADE: ["K"],
    NFLMarket.PUNTS: ["P"],
    NFLMarket.GROSS_PUNT_YARDS: ["P"],
    NFLMarket.PUNTS_INSIDE_20: ["P"],
}


def is_market_valid_for_position(market: NFLMarket, position: str) -> bool:
    """Check if a market is valid for a given position."""
    valid_positions = MARKET_POSITIONS.get(market, [])
    return position in valid_positions


def get_market_from_string(market_str: str) -> NFLMarket:
    """Parse market string to NFLMarket enum (case-insensitive)."""
    market_str_normalized = market_str.lower().replace(" ", "_").replace("+", "_")
    
    # Direct mapping attempts
    try:
        return NFLMarket(market_str_normalized)
    except ValueError:
        pass
    
    # Fuzzy matching for common variations
    FUZZY_MAP = {
        "receiving_yards": NFLMarket.REC_YARDS,
        "rec_yds": NFLMarket.REC_YARDS,
        "pass_yds": NFLMarket.PASS_YARDS,
        "passing_yards": NFLMarket.PASS_YARDS,
        "rushing_yards": NFLMarket.RUSH_YARDS,
        "rush_yds": NFLMarket.RUSH_YARDS,
        "pass_td": NFLMarket.PASS_TDS,
        "passing_tds": NFLMarket.PASS_TDS,
        "touchdowns": NFLMarket.PASS_TDS,  # Context-dependent
        "ints": NFLMarket.INTERCEPTIONS,
        "int": NFLMarket.INTERCEPTIONS,
        "rush_rec_yds": NFLMarket.RUSH_REC_YARDS,
        "rush_receiving_yards": NFLMarket.RUSH_REC_YARDS,
    }
    
    return FUZZY_MAP.get(market_str_normalized, None)
