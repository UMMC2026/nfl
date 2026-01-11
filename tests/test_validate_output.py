import importlib.util
import os
from datetime import datetime, timedelta, timezone

# Load the validate_output module directly from scripts/validate_output.py so tests
# don't rely on scripts/ being a package.
spec = importlib.util.spec_from_file_location(
    "validate_output",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "validate_output.py"),
)
validate_output = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_output)


BASE_EDGE = {
    "edge_id": "NFL_20260111_TEST_PLAYER_1",
    "sport": "NFL",
    "game_id": "20260111_KC_BUF",
    "entity": "Test Player",
    "market": "passing_yards",
    "line": 250.5,
    "direction": "OVER",
    "probability": 0.65,
    "tier": "STRONG",
    "data_sources": ["nflfastR", "ESPN"],
    "injury_verified": True,
    "correlated": False,
    "snap_pct": 0.75,
    "game_status": "FINAL",
    # set end time in the past by 60 minutes
    "game_end_ts": (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat(),
}


def test_valid_edge_passes():
    ok, errors = validate_output.validate_edges([BASE_EDGE], allow_time_skip=False)
    assert ok, f"Validation unexpectedly failed: {errors}"


def test_duplicate_edge_id_fails():
    e1 = dict(BASE_EDGE)
    e2 = dict(BASE_EDGE)
    e2["edge_id"] = e1["edge_id"]
    ok, errors = validate_output.validate_edges([e1, e2])
    assert not ok
    assert any("Duplicate edge_id" in s for s in errors)


def test_missing_data_sources_fails():
    e = dict(BASE_EDGE)
    e["data_sources"] = ["nflfastR"]
    ok, errors = validate_output.validate_edges([e])
    assert not ok
    assert any("must have at least 2 data_sources" in s for s in errors)


def test_td_prob_exceeds_cap_fails():
    e = dict(BASE_EDGE)
    e["market"] = "receiving_tds"
    e["probability"] = 0.70
    ok, errors = validate_output.validate_edges([e])
    assert not ok
    assert any("td_max" in s for s in errors)


def test_multiple_primary_edges_fails():
    e1 = dict(BASE_EDGE)
    e2 = dict(BASE_EDGE)
    e2["edge_id"] = "NFL_20260111_TEST_PLAYER_2"
    ok, errors = validate_output.validate_edges([e1, e2])
    assert not ok
    assert any("Multiple primary edges" in s for s in errors)


def test_missing_injury_verified_fails():
    e = dict(BASE_EDGE)
    e["injury_verified"] = False
    ok, errors = validate_output.validate_edges([e])
    assert not ok
    assert any("injury_verified" in s for s in errors)


def test_missing_snap_pct_fails():
    e = dict(BASE_EDGE)
    del e["snap_pct"]
    ok, errors = validate_output.validate_edges([e])
    assert not ok
    assert any("missing snap_pct" in s for s in errors)


def test_tier_mismatch_fails():
    e = dict(BASE_EDGE)
    e["probability"] = 0.9
    e["tier"] = "STRONG"
    ok, errors = validate_output.validate_edges([e])
    assert not ok
    assert any("tier mismatch" in s for s in errors)
