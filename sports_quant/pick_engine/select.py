from typing import List, Dict

MIN_CONF_DEFAULT = 0.60


def select_picks(sim_results: List[Dict], min_conf: float = MIN_CONF_DEFAULT) -> List[Dict]:
    """Filter simulation outputs by confidence and sort by expected edge descending."""
    filtered = [r for r in sim_results if r.get("confidence", 0.0) >= min_conf]
    return sorted(filtered, key=lambda r: r.get("expected_value", 0.0), reverse=True)
