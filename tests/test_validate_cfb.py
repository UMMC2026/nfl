import importlib.util
import os
from datetime import datetime, timedelta, timezone

spec = importlib.util.spec_from_file_location(
    "validate_cfb_output",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "validate_cfb_output.py"),
)
validate_cfb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_cfb)

BASE_EDGE = {
    "edge_id": "CFB_20260111_TEST_PLAYER_1",
    "sport": "CFB",
    "game_id": "20260111_TEAMA_TEAMB",
    "entity": "Test Player",
    "market": "receiving_tds",
    "line": 0.5,
    "direction": "OVER",
    "probability": 0.50,
    "tier": "STRONG",
    "data_sources": ["cfb_source_a", "cfb_source_b"],
    "injury_verified": True,
    "correlated": False,
    "snap_pct": 0.75,
    "game_status": "FINAL",
    "game_end_ts": (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat(),
}


def test_cfb_td_cap_fails():
    ok, errors = validate_cfb.validate_output.validate_edges([BASE_EDGE], config=validate_cfb.DEFAULT_CFB_CONFIG, allow_time_skip=False)
    assert not ok
    assert any('td_max' in s for s in errors)
