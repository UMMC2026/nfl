"""
NBA Schema Lock + Hash Guard
Schema is law. Logic is opinion. Commentary is style.
Law never changes.
"""
import hashlib
import json

# --- 1. Canonical NBA Schema (Pure JSON Schema) ---
NBA_SCHEMA_V1 = {
    "game_id": "string",
    "date": "string",
    "home_team": "string",
    "away_team": "string",
    "venue": "string",
    "start_time": "string",
    "status": "string",
    "home_score": "integer",
    "away_score": "integer",
    "injuries": "array",
    "props": "array",
    "team_stats": "object",
    "narrative": "string"
}

# --- 2. Immutable Schema Hash ---
def compute_schema_hash(schema: dict) -> str:
    return hashlib.sha256(
        json.dumps(schema, sort_keys=True).encode()
    ).hexdigest()

CANONICAL_HASH = compute_schema_hash(NBA_SCHEMA_V1)

# --- 3. Schema Validator ---
def validate_schema(output_json: dict, sport: str) -> tuple[bool, str]:
    """
    Validates that output_json matches NBA schema exactly.
    Returns (is_valid, error_message)
    """
    required_keys = set(NBA_SCHEMA_V1.keys())
    actual_keys = set(output_json.keys())
    extra_keys = actual_keys - required_keys
    if extra_keys:
        return False, f"SCHEMA DRIFT: {sport} added keys {extra_keys}"
    missing_keys = required_keys - actual_keys
    if missing_keys:
        return False, f"SCHEMA VIOLATION: {sport} missing keys {missing_keys}"
    # Type checking
    type_map = {
        "string": str,
        "integer": int,
        "array": list,
        "object": dict
    }
    for key, expected_type in NBA_SCHEMA_V1.items():
        actual_value = output_json[key]
        if not isinstance(actual_value, type_map[expected_type]):
            return False, f"TYPE MISMATCH: {key} expected {expected_type}, got {type(actual_value).__name__}"
    return True, "VALID"

# --- 4. Hash Guard (Schema File Only) ---
def enforce_schema_hash():
    if compute_schema_hash(NBA_SCHEMA_V1) != CANONICAL_HASH:
        raise RuntimeError("NBA canonical schema modified. Law never changes.")

# --- 5. NBA Pass-through Guard ---
def nba_pass_through_guard(raw_data: dict, sport: str):
    is_valid, error = validate_schema(raw_data, sport)
    if not is_valid:
        raise RuntimeError(f"NBA DATA CORRUPTED: {error}")
    return raw_data
