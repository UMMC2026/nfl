"""
Tennis Edge Scoring
===================
Score and rank tennis edges for final output.

Simple scoring: edge * confidence_factor
No Kelly in v1 (match winner is binary, not prop-based)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"
CONFIG_FILE = TENNIS_DIR / "tennis_config.json"

CONFIG = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}


def load_latest_edges() -> Dict:
    """Load latest tennis edges."""
    latest_file = OUTPUTS_DIR / "tennis_edges_latest.json"
    if latest_file.exists():
        return json.loads(latest_file.read_text())
    return None


def score_edge(edge: Dict) -> float:
    """
    Calculate final score for an edge.
    
    Score = edge * tier_multiplier
    """
    tier = str(edge.get("tier", "AVOID") or "AVOID").upper()
    if edge.get("blocked") or tier in {"NO_PLAY", "AVOID", "BLOCKED"}:
        return 0.0
    
    raw_edge = edge.get("edge", 0)
    
    # Tier multipliers
    # Canonical tiers per config/thresholds.py
    tier_mult = {
        "SLAM": 2.0,
        "STRONG": 1.5,
        "LEAN": 1.0,
        "AVOID": 0.0,
        "NO_PLAY": 0.0,
        "BLOCKED": 0.0,
    }
    
    multiplier = tier_mult.get(tier, 0.0)
    return raw_edge * multiplier


def rank_edges(edges: List[Dict]) -> List[Dict]:
    """Score and rank all edges."""
    
    for edge in edges:
        edge["score"] = score_edge(edge)
    
    # Sort by score descending
    playable = [e for e in edges if e.get("score", 0) > 0]
    playable.sort(key=lambda x: x["score"], reverse=True)
    
    # Assign rank
    for i, edge in enumerate(playable, 1):
        edge["rank"] = i
    
    return edges


def score_all_edges(edges_file: Path = None) -> List[Dict]:
    """Score all edges in a file."""
    
    if edges_file:
        data = json.loads(edges_file.read_text())
    else:
        data = load_latest_edges()
    
    if not data:
        print("✗ No edges found")
        return []
    
    edges = data.get("edges", [])
    scored_edges = rank_edges(edges)

    # Playable edges: scored > 0
    playable = [e for e in scored_edges if e.get("score", 0) > 0]
    playable.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Save scored output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = OUTPUTS_DIR / f"tennis_scored_{timestamp}.json"
    
    output = {
        "sport": "TENNIS",
        "scored_at": datetime.now().isoformat(),
        "total_edges": len(edges),
        "playable_count": len(playable),
        "slam_count": sum(1 for e in playable if str(e.get("tier") or "").upper() == "SLAM"),
        "strong_count": sum(1 for e in playable if str(e.get("tier") or "").upper() == "STRONG"),
        "lean_count": sum(1 for e in playable if str(e.get("tier") or "").upper() == "LEAN"),
        "blocked_count": sum(1 for e in scored_edges if e.get("blocked")),
        "avoid_count": sum(1 for e in scored_edges if str(e.get("tier") or "").upper() in {"AVOID", "NO_PLAY"} and not e.get("blocked")),
        "edges": scored_edges,
    }
    
    output_file.write_text(json.dumps(output, indent=2))
    
    # Also save as latest
    latest_file = OUTPUTS_DIR / "tennis_scored_latest.json"
    latest_file.write_text(json.dumps(output, indent=2))
    
    print(f"✓ Scored {len(playable)} playable edges")
    print(f"  SLAM: {output['slam_count']} | STRONG: {output['strong_count']} | LEAN: {output['lean_count']}")
    print(f"  → {output_file}")
    
    return playable


def print_scored_summary(edges: List[Dict]):
    """Print scored edges summary."""
    print("\n" + "=" * 60)
    print("TENNIS SCORED EDGES")
    print("=" * 60)
    
    strong = [e for e in edges if e.get("tier") == "STRONG"]
    lean = [e for e in edges if e.get("tier") == "LEAN"]
    
    if strong:
        print(f"\n🔥 STRONG PLAYS ({len(strong)})")
        print("-" * 40)
        for e in strong:
            print(f"  #{e.get('rank', '?')} {e['player']} to beat {e['opponent']}")
            print(f"      {e['surface']} {e['round']} | P={e['probability']:.1%} | Edge={e['edge']:+.1%}")
            print(f"      Line: {e.get('line', '?')} | Score: {e['score']:.4f}")
            print()
    
    if lean:
        print(f"\n📊 LEAN PLAYS ({len(lean)})")
        print("-" * 40)
        for e in lean:
            print(f"  #{e.get('rank', '?')} {e['player']} to beat {e['opponent']}")
            print(f"      {e['surface']} {e['round']} | P={e['probability']:.1%} | Edge={e['edge']:+.1%}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    edges = score_all_edges()
    print_scored_summary(edges)
