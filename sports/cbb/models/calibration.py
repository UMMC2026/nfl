"""
CBB Calibration

Track predicted vs actual hit rates to calibrate model over time.
Includes triple interaction variance governor (Seed × Ref × Coach).
"""
import yaml
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json


# Seed × Ref × Coach config path
SRC_CONFIG_PATH = Path(__file__).parent / "seed_ref_coach.yaml"


def load_seed_ref_coach_config() -> dict:
    """Load triple interaction configuration."""
    if SRC_CONFIG_PATH.exists():
        with open(SRC_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {"DEFAULT": {"variance_mult": 1.0, "confidence_cap": 0.75}, "INTERACTIONS": []}


def seed_ref_coach_adjust(
    variance: float,
    confidence: float,
    seed_role: str,
    ref_profile: str,
    coach: str
) -> Tuple[float, float]:
    """
    Apply Seed × Ref × Coach triple interaction adjustment.
    
    This only adjusts VARIANCE (up/down) and CAPS confidence.
    Never adjusts mean directly.
    
    Args:
        variance: Current variance value
        confidence: Current confidence (0-1)
        seed_role: HIGH (favored) or LOW (underdog)
        ref_profile: HIGH_FOUL, NEUTRAL, or LOW_FOUL
        coach: Coach name
    
    Returns:
        (adjusted_variance, capped_confidence)
    """
    config = load_seed_ref_coach_config()
    
    # Check for matching interaction
    for rule in config.get("INTERACTIONS", []):
        when = rule.get("when", {})
        
        # Match all conditions
        if (when.get("seed_role") == seed_role and 
            when.get("ref_profile") == ref_profile and
            when.get("coach") == coach):
            
            apply = rule.get("apply", {})
            variance_mult = apply.get("variance_mult", 1.0)
            conf_cap = apply.get("confidence_cap", 0.75)
            
            return variance * variance_mult, min(confidence, conf_cap)
    
    # No match, use defaults
    defaults = config.get("DEFAULT", {})
    return (
        variance * defaults.get("variance_mult", 1.0),
        min(confidence, defaults.get("confidence_cap", 0.75))
    )


def get_ref_profile(fouls_per_min: float, baseline: float = 0.5) -> str:
    """
    Determine ref profile from foul rate.
    
    Args:
        fouls_per_min: Current fouls per minute
        baseline: Expected baseline foul rate
    
    Returns:
        HIGH_FOUL, NEUTRAL, or LOW_FOUL
    """
    ratio = fouls_per_min / baseline if baseline > 0 else 1.0
    
    if ratio > 1.10:
        return "HIGH_FOUL"
    elif ratio < 0.90:
        return "LOW_FOUL"
    else:
        return "NEUTRAL"


def get_seed_role(team_seed: int, opponent_seed: int) -> str:
    """
    Determine seed role.
    
    Args:
        team_seed: This team's seed (1-16)
        opponent_seed: Opponent's seed (1-16)
    
    Returns:
        HIGH (favored) or LOW (underdog)
    """
    if team_seed <= opponent_seed:
        return "HIGH"  # Lower number = better seed = favored
    else:
        return "LOW"


@dataclass
class CalibrationBucket:
    """Calibration data for a probability bucket"""
    bucket_min: float
    bucket_max: float
    predicted_count: int = 0
    actual_hits: int = 0
    
    @property
    def hit_rate(self) -> float:
        if self.predicted_count == 0:
            return 0.0
        return self.actual_hits / self.predicted_count
    
    @property
    def calibration_error(self) -> float:
        """Absolute difference between predicted and actual"""
        if self.predicted_count == 0:
            return 0.0
        expected = (self.bucket_min + self.bucket_max) / 2
        return abs(self.hit_rate - expected)


# Calibration storage
CALIBRATION_DIR = Path("data/cbb/calibration")

# Default buckets (stricter for CBB)
DEFAULT_BUCKETS = [
    (0.50, 0.55),
    (0.55, 0.60),
    (0.60, 0.65),
    (0.65, 0.70),
    (0.70, 0.75),
]


def calibrate_probabilities(
    edges: List[Dict],
    results: List[Dict]
) -> Dict[str, float]:
    """
    Calibrate probabilities based on historical results.
    
    Args:
        edges: Historical edges with predicted probabilities
        results: Actual outcomes
        
    Returns:
        Dict of bucket -> adjustment factor
    """
    # Initialize buckets
    buckets = {
        f"{b[0]:.2f}-{b[1]:.2f}": CalibrationBucket(b[0], b[1])
        for b in DEFAULT_BUCKETS
    }
    
    # Match edges to results and populate buckets
    results_map = {r["edge_id"]: r for r in results}
    
    for edge in edges:
        prob = edge.get("probability", 0)
        edge_id = edge.get("edge_id")
        
        # Find bucket
        bucket_key = None
        for key, bucket in buckets.items():
            if bucket.bucket_min <= prob < bucket.bucket_max:
                bucket_key = key
                break
        
        if bucket_key is None:
            continue
        
        buckets[bucket_key].predicted_count += 1
        
        # Check if hit
        result = results_map.get(edge_id)
        if result and result.get("hit", False):
            buckets[bucket_key].actual_hits += 1
    
    # Compute adjustments
    adjustments = {}
    for key, bucket in buckets.items():
        if bucket.predicted_count >= 10:  # Minimum sample
            expected = (bucket.bucket_min + bucket.bucket_max) / 2
            if bucket.hit_rate > 0:
                adjustments[key] = bucket.hit_rate / expected
            else:
                adjustments[key] = 1.0
        else:
            adjustments[key] = 1.0  # No adjustment if insufficient sample
    
    return adjustments


def load_calibration_history() -> List[Dict]:
    """Load historical calibration data."""
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    history_file = CALIBRATION_DIR / "calibration_history.json"
    
    if history_file.exists():
        with open(history_file) as f:
            return json.load(f)
    return []


def save_calibration_result(result: Dict):
    """Save calibration result to history."""
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    
    history = load_calibration_history()
    result["timestamp"] = datetime.now().isoformat()
    history.append(result)
    
    history_file = CALIBRATION_DIR / "calibration_history.json"
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def compute_brier_score(edges: List[Dict], results: List[Dict]) -> float:
    """
    Compute Brier score for probability calibration.
    
    Brier = (1/N) * Σ(predicted - actual)²
    Lower is better. Perfect = 0, random = 0.25
    """
    results_map = {r["edge_id"]: r for r in results}
    
    total_error = 0.0
    count = 0
    
    for edge in edges:
        edge_id = edge.get("edge_id")
        prob = edge.get("probability", 0.5)
        
        result = results_map.get(edge_id)
        if result is None:
            continue
        
        actual = 1.0 if result.get("hit", False) else 0.0
        total_error += (prob - actual) ** 2
        count += 1
    
    if count == 0:
        return 0.25  # No data, return baseline
    
    return total_error / count


def validate_calibration(brier_score: float, min_threshold: float = 0.22) -> bool:
    """
    Validate calibration meets minimum quality threshold.
    
    CBB threshold is stricter: 0.22 vs 0.25 baseline
    """
    return brier_score < min_threshold
