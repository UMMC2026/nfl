"""
Parlay suggestion builder - generates optimal multi-leg combinations
from today's highest-confidence picks.
"""
import json
from pathlib import Path
from typing import List, Dict, Tuple


def load_hydrated_picks(filepath: str = "picks_hydrated.json") -> List[Dict]:
    """Load all hydrated picks with confidence scores."""
    with open(filepath, 'r') as f:
        return json.load(f)


def get_game_id(pick: Dict) -> str:
    """Extract game identifier from pick."""
    return f"{pick.get('team', 'UNK')}"


def build_safe_2leg(picks: List[Dict]) -> List[Tuple[Dict, Dict]]:
    """Build 2-leg parlays from highest confidence picks (75%+)."""
    high_conf = [p for p in picks if p.get('prob_display', 0) >= 0.75]
    
    if len(high_conf) < 2:
        return []
    
    # Sort by confidence
    high_conf.sort(key=lambda x: x.get('prob_display', 0), reverse=True)
    
    # Create combinations from different teams
    parlays = []
    for i in range(len(high_conf)):
        for j in range(i + 1, len(high_conf)):
            if get_game_id(high_conf[i]) != get_game_id(high_conf[j]):
                parlays.append((high_conf[i], high_conf[j]))
                if len(parlays) >= 5:  # Return top 5
                    return parlays
    
    return parlays


def build_value_3leg(picks: List[Dict]) -> List[Tuple[Dict, Dict, Dict]]:
    """Build 3-leg parlays from solid confidence picks (65%+)."""
    solid_conf = [p for p in picks if p.get('prob_display', 0) >= 0.65]
    
    if len(solid_conf) < 3:
        return []
    
    solid_conf.sort(key=lambda x: x.get('prob_display', 0), reverse=True)
    
    parlays = []
    for i in range(len(solid_conf)):
        for j in range(i + 1, len(solid_conf)):
            for k in range(j + 1, len(solid_conf)):
                # Ensure different teams/game times
                teams = {get_game_id(solid_conf[i]), get_game_id(solid_conf[j]), get_game_id(solid_conf[k])}
                if len(teams) >= 2:  # At least 2 different teams
                    parlays.append((solid_conf[i], solid_conf[j], solid_conf[k]))
                    if len(parlays) >= 5:
                        return parlays
    
    return parlays


def build_flex_4leg(picks: List[Dict]) -> List[Tuple[Dict, Dict, Dict, Dict]]:
    """Build 4-leg parlays with mixed confidence (55%+)."""
    mixed_conf = [p for p in picks if p.get('prob_display', 0) >= 0.55]
    
    if len(mixed_conf) < 4:
        return []
    
    mixed_conf.sort(key=lambda x: x.get('prob_display', 0), reverse=True)
    
    parlays = []
    # Prefer high-confidence + diversified approach
    top_3 = mixed_conf[:3]
    remaining = mixed_conf[3:]
    
    for fourth in remaining[:5]:
        teams = {get_game_id(p) for p in top_3 + [fourth]}
        if len(teams) >= 2:
            parlays.append(tuple(top_3 + [fourth]))
            if len(parlays) >= 3:
                return parlays
    
    return parlays


def calculate_parlay_probability(picks: List[Dict]) -> float:
    """Calculate combined probability of multi-leg parlay."""
    prob = 1.0
    for pick in picks:
        prob *= pick.get('prob_display', 0.5)
    return prob


def format_parlay(picks: List[Dict]) -> str:
    """Format parlay for display."""
    lines = []
    for i, pick in enumerate(picks, 1):
        player = pick.get('player', 'Unknown')[:20]
        direction = pick.get('direction', 'OVER')
        line = pick.get('line', 0)
        stat = pick.get('stat', '')[:12]
        conf = pick.get('prob_display', 0) * 100
        lines.append(f"  Leg {i}: {player} {direction:5} {line:5.1f} {stat:12} [{conf:.0f}%]")
    
    combined_prob = calculate_parlay_probability(picks)
    lines.append(f"  Combined Probability: {combined_prob*100:.1f}%")
    return "\n".join(lines)


def generate_parlay_suggestions(picks: List[Dict]) -> Dict:
    """Generate all parlay suggestions."""
    return {
        'safe_2leg': build_safe_2leg(picks),
        'value_3leg': build_value_3leg(picks),
        'flex_4leg': build_flex_4leg(picks),
    }


if __name__ == "__main__":
    picks = load_hydrated_picks()
    
    # Filter for only high-confidence picks
    picks = [p for p in picks if p.get('prob_display', 0) >= 0.50]
    
    suggestions = generate_parlay_suggestions(picks)
    
    print("\n" + "="*70)
    print("  PARLAY SUGGESTIONS FOR TODAY")
    print("="*70)
    
    if suggestions['safe_2leg']:
        print("\n🔒 SAFE 2-LEG (75%+ confidence each):")
        print("-" * 70)
        for parlay in suggestions['safe_2leg'][:3]:
            print(format_parlay(parlay))
            print()
    else:
        print("\n🔒 SAFE 2-LEG: No eligible picks (need 2+ at 75%+)")
    
    if suggestions['value_3leg']:
        print("\n💰 VALUE 3-LEG (65%+ confidence):")
        print("-" * 70)
        for parlay in suggestions['value_3leg'][:3]:
            print(format_parlay(parlay))
            print()
    else:
        print("\n💰 VALUE 3-LEG: No eligible picks (need 3+ at 65%+)")
    
    if suggestions['flex_4leg']:
        print("\n🎲 FLEX 4-LEG (55%+ confidence, diversified):")
        print("-" * 70)
        for parlay in suggestions['flex_4leg'][:2]:
            print(format_parlay(parlay))
            print()
    else:
        print("\n🎲 FLEX 4-LEG: No eligible picks (need 4+ at 55%+)")
