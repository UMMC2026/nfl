# NBA stat keys - maps prop name to nba_api column(s)
# Single column stats map to string, combo stats map to list of columns to sum
NBA_STAT_KEYS = {
    # Core stats
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "3pm": "FG3M",
    "blocks": "BLK",
    "steals": "STL",
    "turnovers": "TOV",
    
    # Combo stats (will sum columns)
    "pts+reb+ast": ["PTS", "REB", "AST"],
    "pts+reb": ["PTS", "REB"],
    "pts+ast": ["PTS", "AST"],
    "stl+blk": ["STL", "BLK"],
    "reb+ast": ["REB", "AST"],
    
    # Alternate naming conventions
    "pra": ["PTS", "REB", "AST"],
    "pr": ["PTS", "REB"],
    "pa": ["PTS", "AST"],
    "ra": ["REB", "AST"],
}

# Stats that require special calculation (not simple column or sum)
NBA_SPECIAL_STATS = {
    "double_double": "dbl_dbl",   # Binary: 2+ categories >= 10
    "triple_double": "trpl_dbl",  # Binary: 3+ categories >= 10
}

# 1st Quarter stats - requires different API endpoint (PlayerGameLogs with period filter)
NBA_QUARTER_STATS = {
    "1q_pts": "PTS",
    "1q_reb": "REB",
    "1q_ast": "AST",
}

NFL_STAT_KEYS = {
    "pass_yds": "passing_yards",
    "rush_yds": "rushing_yards",
    "rec_yds": "receiving_yards",
    "receptions": "receptions",
    "pass_tds": "passing_tds",
    "rush_tds": "rushing_tds",
    "rec_tds": "receiving_tds",
}

CFB_STAT_KEYS = {
    "cfb_pass_yds": ("passing", "YDS"),
    "cfb_pass_tds": ("passing", "TD"),
    "cfb_rush_yds": ("rushing", "YDS"),
    "cfb_rush_tds": ("rushing", "TD"),
    "cfb_rec_yds": ("receiving", "YDS"),
    "cfb_receptions": ("receiving", "REC"),
    "cfb_rec_tds": ("receiving", "TD"),
}

# ESPN NFL label normalization anchored by category to avoid ambiguous keys like 'YDS' or 'TD'.
# Maps (category, label) -> normalized stat key used in our pipelines.
ESPN_NFL_LABEL_MAP = {
    ("passing", "YDS"): "pass_yds",
    ("passing", "TD"): "pass_tds",
    ("passing", "CMP"): "completions",
    ("passing", "ATT"): "pass_attempts",
    ("passing", "INT"): "interceptions",
    ("rushing", "YDS"): "rush_yds",
    ("rushing", "TD"): "rush_tds",
    ("rushing", "ATT"): "rush_attempts",
    ("receiving", "YDS"): "rec_yds",
    ("receiving", "TD"): "rec_tds",
    ("receiving", "REC"): "receptions",
    ("receiving", "TGT"): "targets",
    ("receiving", "TGTS"): "targets",
}

ESPN_LABEL_SYNONYMS = {
    # Normalize label variations found across ESPN endpoints
    "PYDS": "YDS",
    "RYDS": "YDS",
    "RECYDS": "YDS",
    "RushYds": "YDS",
    "PassYds": "YDS",
    "Rectds": "TD",
    "RTD": "TD",
    "PTD": "TD",
    "SACKS": "SCK",
}
