"""
NFL Prop Analyzer - Conference Championship Edition
Analyzes NFL props using role mapping, team context, and probability calculations.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nfl_team_context import get_nfl_team_context, get_nfl_matchup_context, NFL_TEAM_CONTEXT


def assign_tier(probability: float) -> str:
    """Assign confidence tier based on probability (Super Bowl calibration)."""
    if probability >= 0.80:
        return "SLAM"
    elif probability >= 0.70:
        return "STRONG"
    elif probability >= 0.60:
        return "LEAN"
    else:
        return "NO_PLAY"


def load_nfl_role_mapping() -> Dict:
    """Load NFL role mapping from JSON."""
    with open("nfl_role_mapping.json", "r") as f:
        return json.load(f)


def get_player_info(player: str, role_mapping: Dict) -> Optional[Dict]:
    """Get player team and position from role mapping."""
    classifications = role_mapping.get("player_classifications", {})
    return classifications.get(player)


def is_stat_allowed(position: str, stat: str, role_mapping: Dict) -> bool:
    """Check if stat is allowed for player's position."""
    permissions = role_mapping.get("stat_permissions", {})
    allowed = permissions.get(position, [])
    
    # Normalize stat key
    stat_lower = stat.lower().replace(" ", "_")
    stat_map = {
        "pass yards": "pass_yds",
        "rush yards": "rush_yds",
        "rec yards": "rec_yds",
        "receiving yards": "rec_yds",
        "rushing yards": "rush_yds",
        "passing yards": "pass_yds",
        "pass_yards": "pass_yds",
        "rush_yards": "rush_yds",
        "rec_yards": "rec_yds",
    }
    stat_key = stat_map.get(stat_lower, stat_lower)
    
    return stat_key in allowed


def calculate_nfl_probability(
    player: str,
    stat: str,
    line: float,
    direction: str,
    player_info: Dict,
    role_mapping: Dict
) -> float:
    """
    Calculate probability for NFL prop.
    Uses historical data + positional priors.
    """
    position = player_info.get("position", "")
    team = player_info.get("team", "")
    
    # Get confidence cap for stat type
    caps = role_mapping.get("confidence_caps", {})
    
    # Determine cap based on stat (UPDATED FOR SUPER BOWL - Feb 2026)
    if "td" in stat.lower():
        max_conf = caps.get("touchdown", 0.78)  # Increased from 0.55
    elif stat.lower() in ["pass_yds", "rush_yds", "rec_yds", "receptions"]:
        max_conf = caps.get("core", 0.85)  # Increased from 0.70
    else:
        max_conf = caps.get("alt", 0.82)  # Increased from 0.65
    
    # Try to hydrate real stats
    try:
        from hydrators.nfl_stat_hydrator import hydrate_nfl_stat
        result = hydrate_nfl_stat(player, stat, team=team, season=2025, games=10)
        
        if result.get("samples", 0) >= 3 and result.get("mean") is not None:
            mu = result["mean"]
            sigma = result.get("std_dev", mu * 0.25) or (mu * 0.25)
            
            from scipy.stats import norm
            if direction.lower() in ["higher", "more", "over"]:
                prob = 1 - norm.cdf(line, loc=mu, scale=sigma)
            else:
                prob = norm.cdf(line, loc=mu, scale=sigma)
            
            # Apply cap
            prob = min(prob, max_conf)
            return max(prob, 0.01)
    except Exception as e:
        print(f"[HYDRATE] Failed for {player}/{stat}: {e}")
    
    # Fallback: position-based prior
    priors = {
        "QB": {"pass_yds": 0.52, "pass_tds": 0.45, "rush_yds": 0.48},
        "RB": {"rush_yds": 0.52, "receptions": 0.50, "rec_yds": 0.48},
        "WR": {"rec_yds": 0.52, "receptions": 0.50, "rec_tds": 0.40},
        "TE": {"rec_yds": 0.50, "receptions": 0.52, "rec_tds": 0.38},
    }
    
    pos_priors = priors.get(position, {})
    stat_key = stat.lower().replace(" ", "_")
    base_prob = pos_priors.get(stat_key, 0.50)
    
    return min(base_prob, max_conf)


def analyze_nfl_slate(slate_data: List[Dict], role_mapping: Dict) -> List[Dict]:
    """
    Analyze full NFL slate with probabilities and matchup context.
    """
    results = []
    
    for prop in slate_data:
        player = prop.get("player", "")
        stat = prop.get("stat", "")
        line = prop.get("line", 0)
        direction = prop.get("direction", "")
        
        # Get player info
        player_info = get_player_info(player, role_mapping)
        
        if not player_info:
            results.append({
                **prop,
                "probability": 0.0,
                "decision": "BLOCKED",
                "reason": "Player not in role mapping"
            })
            continue
        
        position = player_info.get("position", "")
        team = player_info.get("team", "")
        
        # Check stat permission
        if not is_stat_allowed(position, stat, role_mapping):
            results.append({
                **prop,
                "probability": 0.0,
                "decision": "BLOCKED",
                "reason": f"Stat {stat} not allowed for {position}"
            })
            continue
        
        # Calculate probability
        prob = calculate_nfl_probability(
            player, stat, line, direction, player_info, role_mapping
        )
        
        # Assign tier based on probability
        tier = assign_tier(prob)
        
        # Determine decision
        if tier in ["SLAM", "STRONG"]:
            decision = "PLAY"
        elif tier == "LEAN":
            decision = "LEAN"
        else:
            decision = "PASS"
        
        results.append({
            **prop,
            "team": team,
            "position": position,
            "probability": prob,
            "tier": tier,
            "decision": decision,
            "reason": None
        })
    
    return results


def format_nfl_report(analyzed: List[Dict], matchup: str = "") -> str:
    """Format NFL analysis into readable report."""
    lines = []
    
    if matchup:
        lines.append(f"=== NFL ANALYSIS: {matchup} ===")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
    
    # Group by team
    by_team = {}
    for pick in analyzed:
        team = pick.get("team", "UNK")
        by_team.setdefault(team, []).append(pick)
    
    for team, picks in by_team.items():
        # Get team context
        ctx = get_nfl_team_context(team)
        
        lines.append(f"TEAM: {team}")
        if ctx:
            lines.append(f"  Off Rank: #{ctx.off_rank} | Def Rank: #{ctx.def_rank}")
            lines.append(f"  📝 {ctx.notes}")
        lines.append("")
        
        # Sort by probability
        plays = [p for p in picks if p.get("decision") == "PLAY"]
        leans = [p for p in picks if p.get("decision") == "LEAN"]
        blocked = [p for p in picks if p.get("decision") == "BLOCKED"]
        
        plays.sort(key=lambda x: x.get("probability", 0), reverse=True)
        leans.sort(key=lambda x: x.get("probability", 0), reverse=True)
        
        if plays:
            lines.append("  🎯 PLAY Picks:")
            for i, p in enumerate(plays[:5], 1):
                prob = p.get("probability", 0) * 100
                lines.append(f"    {i}) {p['player']} ({p['position']}) {p['stat']} {p['direction']} {p['line']} — {prob:.1f}%")
        
        if leans:
            lines.append("  📊 LEAN Picks:")
            for i, p in enumerate(leans[:5], 1):
                prob = p.get("probability", 0) * 100
                lines.append(f"    {i}) {p['player']} ({p['position']}) {p['stat']} {p['direction']} {p['line']} — {prob:.1f}%")
        
        if blocked:
            lines.append(f"  ⛔ Blocked: {len(blocked)} props (missing data/position mismatch)")
        
        lines.append("")
    
    return "\n".join(lines)


def main():
    """Main entry point for NFL analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NFL Prop Analyzer")
    parser.add_argument("--slate", type=str, help="Path to slate JSON file")
    parser.add_argument("--teams", type=str, help="Comma-separated team codes (e.g., KC,BUF)")
    parser.add_argument("--output", type=str, default="outputs", help="Output directory")
    args = parser.parse_args()
    
    # Load role mapping
    role_mapping = load_nfl_role_mapping()
    print(f"Loaded {len(role_mapping.get('player_classifications', {}))} NFL players")
    
    if args.slate:
        # Load and analyze slate
        with open(args.slate, "r") as f:
            slate_data = json.load(f)
        
        if isinstance(slate_data, dict):
            slate_data = slate_data.get("plays", slate_data.get("props", []))
        
        analyzed = analyze_nfl_slate(slate_data, role_mapping)
        report = format_nfl_report(analyzed, os.path.basename(args.slate))
        
        print(report)
        
        # Save output
        os.makedirs(args.output, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = os.path.join(args.output, f"NFL_ANALYSIS_{timestamp}.txt")
        with open(output_path, "w") as f:
            f.write(report)
        print(f"\nSaved to: {output_path}")
    
    elif args.teams:
        # Show team context
        teams = [t.strip().upper() for t in args.teams.split(",")]
        for team in teams:
            ctx = get_nfl_team_context(team)
            if ctx:
                print(f"\n=== {team} ===")
                print(f"Offense: #{ctx.off_rank} (Pass: #{ctx.pass_off_rank}, Rush: #{ctx.rush_off_rank})")
                print(f"Defense: #{ctx.def_rank} (Pass: #{ctx.pass_def_rank}, Rush: #{ctx.rush_def_rank})")
                print(f"Scheme: {ctx.scheme.value}")
                print(f"Pace: {ctx.plays_per_game} plays/game")
                print(f"Notes: {ctx.notes}")
                if ctx.dome:
                    print("🏟️ Dome stadium")
                if ctx.altitude:
                    print("🏔️ Altitude factor")
            else:
                print(f"\n{team}: Not found")
    
    else:
        # Show Conference Championship matchups
        print("=== NFL CONFERENCE CHAMPIONSHIPS ===")
        print()
        
        matchups = [
            ("BUF", "KC", "AFC Championship"),
            ("WSH", "PHI", "NFC Championship"),
        ]
        
        for away, home, title in matchups:
            print(f"{'='*50}")
            print(f"{title}: {away} @ {home}")
            print(f"{'='*50}")
            
            ctx = get_nfl_matchup_context(away, home)
            
            away_ctx = ctx.get("away", {})
            home_ctx = ctx.get("home", {})
            
            print(f"\n{away} (Away):")
            print(f"  Offense: #{away_ctx.get('off_rank')} | Defense: #{away_ctx.get('def_rank')}")
            print(f"  📝 {away_ctx.get('notes')}")
            
            print(f"\n{home} (Home):")
            print(f"  Offense: #{home_ctx.get('off_rank')} | Defense: #{home_ctx.get('def_rank')}")
            print(f"  📝 {home_ctx.get('notes')}")
            if home_ctx.get("dome"):
                print("  🏟️ Dome game")
            
            print(f"\n🎯 Matchup Analysis:")
            print(f"  {ctx.get('matchup_notes', 'Neutral matchup')}")
            print()


if __name__ == "__main__":
    main()
