"""
Logic Family Router v1
Routes raw game data by sport to the correct logic family (basketball/football), applies family-specific transformation, and enforces NBA schema compliance.
"""
from nba_schema_guard import validate_schema, nba_pass_through_guard

# --- Logic Families ---
BASKETBALL_FAMILY = ["NBA", "CBB", "WNBA", "Soccer", "Tennis"]
FOOTBALL_FAMILY = ["NFL", "CFB"]

class SchemaViolationError(Exception):
    pass

def get_logic_family(sport: str) -> str:
    if sport in BASKETBALL_FAMILY:
        return "basketball"
    elif sport in FOOTBALL_FAMILY:
        return "football"
    else:
        raise ValueError(f"Unknown sport: {sport}")

def transform_football_to_nba(raw_data: dict, sport: str) -> dict:
    # Example transformation; customize as needed
    return {
        "game_id": raw_data.get("game_id", ""),
        "date": raw_data.get("date", ""),
        "home_team": raw_data.get("home", ""),
        "away_team": raw_data.get("away", ""),
        "venue": raw_data.get("venue", ""),
        "start_time": raw_data.get("kickoff", ""),
        "status": raw_data.get("status", "scheduled"),
        "home_score": raw_data.get("home_score", 0),
        "away_score": raw_data.get("away_score", 0),
        "injuries": raw_data.get("injury_report", []),
        "props": raw_data.get("props", []),
        "team_stats": raw_data.get("team_stats", {"home": {}, "away": {}}),
        "narrative": raw_data.get("narrative", "")
    }

def transform_basketball_to_nba(raw_data: dict, sport: str) -> dict:
    if sport == "NBA":
        # Map existing NBA daily report keys into the canonical NBA schema
        return {
            "game_id": raw_data.get("game_id", ""),
            "date": raw_data.get("date", ""),
            "home_team": raw_data.get("home", raw_data.get("home_team", "")),
            "away_team": raw_data.get("away", raw_data.get("away_team", "")),
            "venue": raw_data.get("venue", ""),
            "start_time": raw_data.get("tipoff", raw_data.get("start_time", "")),
            "status": raw_data.get("status", "scheduled"),
            "home_score": raw_data.get("home_score", 0),
            "away_score": raw_data.get("away_score", 0),
            "injuries": raw_data.get("injuries", raw_data.get("injury_report", [])),
            "props": raw_data.get("props", []),
            "team_stats": raw_data.get("team_stats", {"home": {}, "away": {}}),
            "narrative": raw_data.get("narrative", "")
        }
    return {
        "game_id": raw_data.get("game_id", ""),
        "date": raw_data.get("date", ""),
        "home_team": raw_data.get("home_team", ""),
        "away_team": raw_data.get("away_team", ""),
        "venue": raw_data.get("venue", ""),
        "start_time": raw_data.get("start_time", ""),
        "status": raw_data.get("status", "scheduled"),
        "home_score": raw_data.get("home_score", 0),
        "away_score": raw_data.get("away_score", 0),
        "injuries": raw_data.get("injuries", []),
        "props": raw_data.get("props", []),
        "team_stats": raw_data.get("team_stats", {"home": {}, "away": {}}),
        "narrative": raw_data.get("narrative", "")
    }

def apply_sport_logic(sport: str, raw_data: dict) -> dict:
    family = get_logic_family(sport)
    if family == "basketball":
        nba_output = transform_basketball_to_nba(raw_data, sport)
    elif family == "football":
        nba_output = transform_football_to_nba(raw_data, sport)
    else:
        raise ValueError(f"Unknown logic family for sport: {sport}")
    is_valid, error = validate_schema(nba_output, sport)
    if not is_valid:
        raise SchemaViolationError(error)
    return nba_output

def safe_generate_output(sport: str, raw_data: dict) -> dict:
    try:
        output = apply_sport_logic(sport, raw_data)
        is_valid, error = validate_schema(output, sport)
        if not is_valid:
            raise SchemaViolationError(error)
        return output
    except SchemaViolationError as e:
        # Rollback: return empty safe schema
        return {
            "game_id": "",
            "date": "",
            "home_team": "",
            "away_team": "",
            "venue": "",
            "start_time": "",
            "status": "scheduled",
            "home_score": 0,
            "away_score": 0,
            "injuries": [],
            "props": [],
            "team_stats": {"home": {}, "away": {}},
            "narrative": f"Schema violation detected: {str(e)}"
        }
