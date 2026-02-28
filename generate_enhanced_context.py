#!/usr/bin/env python3
"""
Enhanced Context Report Generator
==================================
Reads existing NBA analysis and adds deep coaching/team/matchup context layer.
Now includes Matchup Memory data for player vs opponent historical performance.

Usage:
    python generate_enhanced_context.py
    python generate_enhanced_context.py --file outputs/YOUR_REPORT.txt
"""

import re
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from matchup_analytics import get_team_ratings, calculate_blowout_probability

# Enhanced coaching context (2025-26 season)
COACHING_CONTEXT = {
    "BOS": {
        "coach": "Joe Mazzulla",
        "style": "3-point bombing (48.2 3PA/gm), switching defense",
        "pace": 98.7,
        "off_scheme": "5-out spacing, Tatum/Brown isos, transition 3s",
        "def_scheme": "Switching all actions, elite versatility",
        "key_tendency": "Blows out weak teams early, pulls starters Q4 if up 15+",
        "matchup_edge": "Dominates vs poor defenses (rank 20+), struggles vs physicality",
        "rest_impact": "Minimal B2B dropoff (load managed stars)",
        "injury_notes": "Porzingis minutes managed, Horford DNP some B2Bs"
    },
    "MIA": {
        "coach": "Erik Spoelstra",
        "style": "Zone defense, grind-it-out half-court offense",
        "pace": 95.2,
        "off_scheme": "Butler-centric, heavy mid-range, zone beaters",
        "def_scheme": "2-3 zone primary, switching man when needed",
        "key_tendency": "Injury-depleted (Bam/Herro out), increased role player usage",
        "matchup_edge": "Zone confuses poor passing teams, struggles vs elite shooting",
        "rest_impact": "Heavy B2B decline (115.2 DEF_RTG on no rest)",
        "injury_notes": "Deep injury list forces extended role player minutes"
    },
    "CLE": {
        "coach": "Kenny Atkinson",
        "style": "Modern pace-and-space, Garland-Mobley PnR dominance",
        "pace": 98.1,
        "off_scheme": "Mitchell isos + Garland playmaking, elite ball movement",
        "def_scheme": "Drop coverage with Mobley, Allen rim protection",
        "key_tendency": "Best home team (18-1), struggles on West Coast road trips",
        "matchup_edge": "Destroys weak interior defenses, vulnerable vs elite wings",
        "rest_impact": "Excellent rest management (Mitchell <35 mpg)",
        "injury_notes": "Full health, deepest rotation in NBA"
    },
    "OKC": {
        "coach": "Mark Daigneault",
        "style": "Switchy defense, Shai-centric offense, elite pace control",
        "pace": 98.2,
        "off_scheme": "Shai isos, Jalen Williams versatility, Chet spacing",
        "def_scheme": "Switching 1-5, aggressive help, elite rim protection",
        "key_tendency": "Tight 8-man rotation, rarely plays bench in close games",
        "matchup_edge": "Elite vs everyone, weakness: rebounding vs big teams",
        "rest_impact": "Minute limits enforced (SGA 36 max, JDub 34 max)",
        "injury_notes": "Chet Holmgren out (hip), lineup adjustments ongoing"
    },
    "NYK": {
        "coach": "Tom Thibodeau",
        "style": "Physical defense, Brunson-heavy offense, grinding tempo",
        "pace": 96.8,
        "off_scheme": "Brunson PnR spam, KAT post-ups, Bridges spot-ups",
        "def_scheme": "Aggressive switching, physical at point of attack",
        "key_tendency": "Plays starters heavy minutes (Brunson 38+ mpg)",
        "matchup_edge": "Wears down fast teams, vulnerable to elite shooting",
        "rest_impact": "Poor B2B performance (starter fatigue)",
        "injury_notes": "Mitchell Robinson out, Hartenstein limited minutes"
    },
    "HOU": {
        "coach": "Ime Udoka",
        "style": "Fast pace, aggressive defense, young and athletic",
        "pace": 101.5,
        "off_scheme": "Sengun playmaking hub, Green/Amen slashing",
        "def_scheme": "Switching, full-court pressure, chaotic help",
        "key_tendency": "Deep 10-11 man rotation, fresh legs advantage",
        "matchup_edge": "Runs old teams off the floor, turnover prone vs vets",
        "rest_impact": "Youth advantage, excellent B2B team",
        "injury_notes": "Full health, deepest young rotation"
    },
    "GSW": {
        "coach": "Steve Kerr",
        "style": "Curry gravity + motion offense, Draymond defensive anchor",
        "pace": 98.3,
        "off_scheme": "Off-ball screens, Curry relocations, backdoor cuts",
        "def_scheme": "Switching with Draymond help, vulnerable without him",
        "key_tendency": "Elite at home (18-3), struggles on road (9-12)",
        "matchup_edge": "Curry torches poor perimeter D, needs Draymond health",
        "rest_impact": "Curry rest-managed, sits some B2Bs",
        "injury_notes": "Draymond back issues, Wiggins load managed"
    },
    "LAL": {
        "coach": "JJ Redick",
        "style": "LeBron-centric, pace-and-space modern offense",
        "pace": 99.5,
        "off_scheme": "LeBron PnR, DHO actions, transition offense",
        "def_scheme": "Switching defense, help-and-recover system",
        "key_tendency": "LeBron minutes managed (33-35 mpg), deep rotation usage",
        "matchup_edge": "LeBron playmaking elite, role players benefit from spacing",
        "rest_impact": "Poor B2B (LeBron rested frequently), load management heavy",
        "injury_notes": "LeBron load managed, young core stepping up post-trade"
    },
    "DEN": {
        "coach": "Michael Malone",
        "style": "Jokic-centric offense, methodical pace",
        "pace": 97.2,
        "off_scheme": "Jokic playmaking hub, Murray PnR, MPJ spot-ups",
        "def_scheme": "Drop coverage, Jokic improved rim protection",
        "key_tendency": "Altitude advantage at home, slow starts on road",
        "matchup_edge": "Jokic unstoppable vs weak bigs, vulnerable to speed",
        "rest_impact": "Excellent rest management (Jokic <35 mpg)",
        "injury_notes": "Full health, championship-tested rotation"
    },
    "PHX": {
        "coach": "Mike Budenholzer",
        "style": "Big 3 driven (KD/Book/Beal), space-and-shoot",
        "pace": 98.8,
        "off_scheme": "KD isos, Book PnR, Beal secondary creation",
        "def_scheme": "Drop coverage, lacking rim protection",
        "key_tendency": "Load manages Big 3, DNP rest games frequently",
        "matchup_edge": "Scoring elite when healthy, defense vulnerable",
        "rest_impact": "Heavy load management (Big 3 rarely all play B2Bs)",
        "injury_notes": "Beal injury-prone, rotation thin when stars sit"
    },
    "MEM": {
        "coach": "Taylor Jenkins",
        "style": "Fast pace, Ja-centric, physical defense",
        "pace": 102.3,
        "off_scheme": "Ja drives, JJJ spacing, transition attack",
        "def_scheme": "Switching, physical, excellent rebounding",
        "key_tendency": "Runs teams off floor, Ja usage spike without JJJ",
        "matchup_edge": "Speed kills slow teams, turnover prone",
        "rest_impact": "Young team, minimal B2B dropoff",
        "injury_notes": "JJJ returning from injury, minutes ramp-up"
    },
    "DAL": {
        "coach": "Jason Kidd",
        "style": "Luka heliocentric, Kyrie secondary creation",
        "pace": 98.9,
        "off_scheme": "Luka PnR spam, Kyrie isos, 5-out spacing",
        "def_scheme": "Drop coverage, Lively rim protection",
        "key_tendency": "Luka plays heavy minutes (37+ mpg), fatigue late",
        "matchup_edge": "Luka dominates weak perimeter D, needs Kyrie health",
        "rest_impact": "Poor B2B (Luka fatigue shows)",
        "injury_notes": "Lively minutes managed, Gafford rotation"
    },
    "SAC": {
        "coach": "Mike Brown",
        "style": "Fast pace, DeRozan mid-range, Fox speed",
        "pace": 100.5,
        "off_scheme": "Fox transition, DeRozan mid-range, Sabonis playmaking",
        "def_scheme": "Switch-heavy, undersized, vulnerable to bigs",
        "key_tendency": "Struggles vs elite teams (0-8 vs top 5)",
        "matchup_edge": "Speed advantage vs slow teams, defense weak",
        "rest_impact": "Veteran-heavy, B2B concerns (DeRozan 35 years old)",
        "injury_notes": "Monk injury affects bench scoring"
    },
    "MIN": {
        "coach": "Chris Finch",
        "style": "Edwards-driven offense, Gobert defensive anchor",
        "pace": 98.1,
        "off_scheme": "Ant isos, Randle post, NAW/Conley spacing",
        "def_scheme": "Gobert drop, switching on perimeter",
        "key_tendency": "Gobert DPOY candidate, Ant usage climbing",
        "matchup_edge": "Elite defense, offense inconsistent",
        "rest_impact": "Gobert load managed, sits some B2Bs",
        "injury_notes": "Post-KAT trade adjustment, Randle integration"
    },
    "IND": {
        "coach": "Rick Carlisle",
        "style": "Fastest pace in NBA, motion offense, weak defense",
        "pace": 102.8,
        "off_scheme": "Haliburton playmaking, Turner spacing, transition spam",
        "def_scheme": "Drop coverage, weak perimeter, allows 3s",
        "key_tendency": "Blows leads late, defense collapses Q4",
        "matchup_edge": "Scoring elite, defense bottom 5",
        "rest_impact": "Young legs, excellent B2B performance",
        "injury_notes": "Full health, rotation settled"
    },
    "ATL": {
        "coach": "Quin Snyder",
        "style": "Trae-centric offense, weak defense",
        "pace": 99.7,
        "off_scheme": "Trae PnR spam, Capela lobs, Murray spot-ups",
        "def_scheme": "Drop coverage, vulnerable perimeter",
        "key_tendency": "Trae usage spike when Jalen out",
        "matchup_edge": "Trae elite vs drop coverage, defense poor",
        "rest_impact": "Minimal B2B impact",
        "injury_notes": "Jalen Murray return imminent, Bogdanovic out"
    },
    "ORL": {
        "coach": "Jamahl Mosley",
        "style": "Elite defense, struggle to score",
        "pace": 96.2,
        "off_scheme": "Paolo creation, Franz versatility, paint attack",
        "def_scheme": "Switching 1-5, elite help, rim protection",
        "key_tendency": "Defense elite (#2 in NBA), offense bottom 10",
        "matchup_edge": "Defense suffocates weak offenses, struggles vs shooting",
        "rest_impact": "Young team, minimal fatigue",
        "injury_notes": "Paolo usage spike post-trade deadline"
    },
    "PHI": {
        "coach": "Nick Nurse",
        "style": "Embiid-centric when healthy, chaos when not",
        "pace": 98.3,
        "off_scheme": "Embiid post, Maxey PnR, Oubre slashing",
        "def_scheme": "Zone and switching hybrid",
        "key_tendency": "Injury-riddled (Embiid/George out frequently)",
        "matchup_edge": "Elite when healthy, chaos rotation when injured",
        "rest_impact": "Load manages stars heavily",
        "injury_notes": "Embiid/Paul George injury management ongoing"
    },
    "MIL": {
        "coach": "Doc Rivers",
        "style": "Giannis-Dame PnR, 5-out spacing",
        "pace": 99.2,
        "off_scheme": "Giannis drives, Dame PnR, Middleton mid-range",
        "def_scheme": "Drop with Brook Lopez, switching wings",
        "key_tendency": "Giannis/Dame heavy minutes, thin bench",
        "matchup_edge": "Elite when stars play, vulnerable when resting",
        "rest_impact": "Load manages both stars B2Bs",
        "injury_notes": "Middleton injury history, minutes managed"
    },
    "BKN": {
        "coach": "Jordi Fernandez",
        "style": "Rebuilding, young talent development",
        "pace": 99.5,
        "off_scheme": "Bridges scoring, Cam Thomas usage, young chaos",
        "def_scheme": "Switching, learning, inconsistent effort",
        "key_tendency": "Tanking mode, playing young players heavy minutes",
        "matchup_edge": "Fast pace helps young legs, defense poor",
        "rest_impact": "Youth advantage",
        "injury_notes": "Ben Simmons DNP-rest frequently"
    },
    "CHA": {
        "coach": "Charles Lee",
        "style": "LaMelo-centric, fast pace, poor defense",
        "pace": 102.8,
        "off_scheme": "LaMelo transition spam, Miller scoring",
        "def_scheme": "Aggressive switches, high pressure, leaky",
        "key_tendency": "Fastest team, gives up big games to stars",
        "matchup_edge": "Speed vs slow teams, defense worst in NBA",
        "rest_impact": "Young team, B2B neutral",
        "injury_notes": "LaMelo usage spike, rest managed"
    },
    "CHI": {
        "coach": "Billy Donovan",
        "style": "Balanced but mediocre, no clear identity",
        "pace": 98.7,
        "off_scheme": "LaVine scoring, DeRozan gone, Vucevic post",
        "def_scheme": "Drop coverage, average across the board",
        "key_tendency": "Play-in team, mediocre offense and defense",
        "matchup_edge": "No clear edge, neutral matchups",
        "rest_impact": "Veteran team, some B2B decline",
        "injury_notes": "Lonzo Ball return changes rotation"
    },
    "DET": {
        "coach": "JB Bickerstaff",
        "style": "Cade-centric, young rebuild, improved defense",
        "pace": 97.8,
        "off_scheme": "Cade creation, Ivey slashing, Duren lobs",
        "def_scheme": "Switching, improving, Duren rim protection",
        "key_tendency": "Young improving team, Cade usage climbing",
        "matchup_edge": "Beats bad teams, loses to good teams",
        "rest_impact": "Youth advantage",
        "injury_notes": "Full health, development focus"
    },
    "POR": {
        "coach": "Chauncey Billups",
        "style": "Rebuilding, Scoot/Sharpe development",
        "pace": 99.3,
        "off_scheme": "Scoot drives, Sharpe scoring, young chaos",
        "def_scheme": "Switching, young learning, inconsistent",
        "key_tendency": "Tanking, playing rookies heavy minutes",
        "matchup_edge": "None, bottom 5 team",
        "rest_impact": "Youth advantage only positive",
        "injury_notes": "Tanking mode, vets DNP-rest"
    },
    "SAS": {
        "coach": "Gregg Popovich",
        "style": "Wemby development, slow methodical",
        "pace": 96.5,
        "off_scheme": "Wemby post/perimeter hybrid, CP3 playmaking",
        "def_scheme": "Wemby rim protection, switching",
        "key_tendency": "Wemby usage climbing, defense elite with him",
        "matchup_edge": "Wemby matchup nightmare, offense struggles",
        "rest_impact": "CP3 old (39), sits B2Bs frequently",
        "injury_notes": "Wemby minutes managed (32-34 mpg)"
    },
    "TOR": {
        "coach": "Darko Rajaković",
        "style": "Rebuilding, Scottie Barnes development",
        "pace": 99.2,
        "off_scheme": "Barnes creation, Poeltl post, young learning",
        "def_scheme": "Switch-heavy, undersized frontcourt",
        "key_tendency": "Tanking, trading veterans",
        "matchup_edge": "None, bottom tier team",
        "rest_impact": "Young team, minimal fatigue",
        "injury_notes": "Trading deadline approaching, roster flux"
    },
    "UTA": {
        "coach": "Will Hardy",
        "style": "Rebuilding, Markkanen + young core",
        "pace": 98.1,
        "off_scheme": "Markkanen scoring, Sexton creation",
        "def_scheme": "Switching, young learning",
        "key_tendency": "Tanking despite Markkanen excellence",
        "matchup_edge": "None, bottom 5 team",
        "rest_impact": "Young team advantage",
        "injury_notes": "Markkanen trade rumors, plays heavy minutes"
    },
    "WAS": {
        "coach": "Brian Keefe",
        "style": "Worst team in NBA, full rebuild",
        "pace": 98.9,
        "off_scheme": "Poole volume scoring, young chaos",
        "def_scheme": "Switching, worst defense in NBA",
        "key_tendency": "Loses every game, development focus",
        "matchup_edge": "None, worst team",
        "rest_impact": "Youth only positive",
        "injury_notes": "Everyone gets minutes, tanking mode"
    },
    "NOP": {
        "coach": "Willie Green",
        "style": "Injury-riddled, BI-centric when healthy",
        "pace": 97.5,
        "off_scheme": "BI mid-range, McCollum scoring, Zion post (when healthy)",
        "def_scheme": "Switching, weak without Zion/Herb",
        "key_tendency": "Injury chaos, rotation changes nightly",
        "matchup_edge": "None when injured, elite when healthy",
        "rest_impact": "Injury more relevant than rest",
        "injury_notes": "Zion out indefinitely, massive rotation changes"
    },
    "LAC": {
        "coach": "Tyronn Lue",
        "style": "Post-Kawhi/PG, Harden-centric now",
        "pace": 97.8,
        "off_scheme": "Harden PnR, Powell lobs, balanced scoring",
        "def_scheme": "Switching, Zubac rim protection",
        "key_tendency": "Harden usage climbing, post-stars era",
        "matchup_edge": "Balanced but not elite anywhere",
        "rest_impact": "Harden old (35), load managed",
        "injury_notes": "Kawhi/PG gone, roster rebuild ongoing"
    }
}


def extract_teams_from_report(report_path):
    """Extract all unique team abbreviations from report"""
    with open(report_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Find all 3-letter team codes in parentheses
    teams = set(re.findall(r'\(([A-Z]{3})\)', content))
    return sorted(teams)


def extract_matchups_from_report(report_path):
    """Extract game matchups (team vs opponent pairs)"""
    teams = extract_teams_from_report(report_path)
    
    # For now, return unique teams - matchups could be inferred from schedule
    # In a full implementation, this would parse actual game matchups
    return teams


def generate_team_context_section(teams, ratings):
    """Generate detailed team context section"""
    lines = []
    lines.append("=" * 80)
    lines.append("TEAM COACHING & MATCHUP CONTEXT")
    lines.append("=" * 80)
    lines.append("")
    
    for team in teams:
        if team not in COACHING_CONTEXT:
            continue
            
        ctx = COACHING_CONTEXT[team]
        rtg = ratings.get(team, {})
        
        lines.append(f"+-- {team} ({'-' * (72 - len(team))})")
        lines.append(f"|")
        lines.append(f"|  Coach: {ctx['coach']}")
        lines.append(f"|  Style: {ctx['style']}")
        lines.append(f"|")
        lines.append(f"|  RATINGS (per 100 possessions)")
        lines.append(f"|    - Offensive: {rtg.get('off_rtg', 0):.1f}")
        lines.append(f"|    - Defensive: {rtg.get('def_rtg', 0):.1f}")
        lines.append(f"|    - Net:       {rtg.get('net_rtg', 0):+.1f}")
        lines.append(f"|    - Pace:      {ctx['pace']} poss/game")
        lines.append(f"|")
        lines.append(f"|  SCHEMES")
        lines.append(f"|    - Offense:  {ctx['off_scheme']}")
        lines.append(f"|    - Defense:  {ctx['def_scheme']}")
        lines.append(f"|")
        lines.append(f"|  KEY INSIGHTS")
        lines.append(f"|    - Tendency:      {ctx['key_tendency']}")
        lines.append(f"|    - Matchup Edge:  {ctx['matchup_edge']}")
        lines.append(f"|    - Rest Impact:   {ctx['rest_impact']}")
        lines.append(f"|    - Injury Status: {ctx['injury_notes']}")
        lines.append(f"|")
        lines.append("+" + "-" * 78)
        lines.append("")
    
    return lines


def generate_blowout_analysis(teams, ratings):
    """Generate blowout probability analysis for potential matchups"""
    lines = []
    lines.append("=" * 80)
    lines.append("BLOWOUT RISK ANALYSIS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("High blowout risk reduces starter minutes in Q4, affecting props.")
    lines.append("")
    
    # This is simplified - in reality you'd parse actual matchups from schedule
    # For now, just show net rating differentials
    net_ratings = [(t, ratings.get(t, {}).get('net_rtg', 0)) for t in teams if t in ratings]
    net_ratings.sort(key=lambda x: x[1], reverse=True)
    
    lines.append("NET RATING RANKINGS (higher = more likely to blow out opponents)")
    lines.append("-" * 80)
    
    for i, (team, net_rtg) in enumerate(net_ratings, 1):
        risk = "[HIGH]" if net_rtg > 8 else "[MED]" if net_rtg > 3 else "[LOW]"
        lines.append(f"  {i:2d}. {team}  {net_rtg:+6.1f}  {risk}")
    
    lines.append("")
    lines.append("WARNING: Teams with +8.0 or higher net rating often blow out weak opponents.")
    lines.append("WARNING: Starters typically sit if up 15+ points in Q4.")
    lines.append("")
    
    return lines


def extract_players_from_report(report_path):
    """Extract player names and their opponents from the report"""
    with open(report_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Pattern: Player Name (TEAM) vs OPP or Player Name (TEAM) @ OPP
    # Also look for lines like "LeBron James (LAL)" with opponent on nearby lines
    player_opponent_pairs = []
    
    # Find player entries with team codes
    player_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+\(([A-Z]{3})\)'
    matches = re.findall(player_pattern, content)
    
    # Extract matchups (TEAM vs OPP or TEAM @ OPP)
    matchup_pattern = r'([A-Z]{3})\s+(?:vs|@|VS|at)\s+([A-Z]{3})'
    matchups = re.findall(matchup_pattern, content)
    
    # Build team -> opponent mapping
    team_opponents = {}
    for home, away in matchups:
        team_opponents[home] = away
        team_opponents[away] = home
    
    # Pair players with opponents
    for player_name, team in matches:
        if team in team_opponents:
            player_opponent_pairs.append((player_name, team_opponents[team]))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_pairs = []
    for pair in player_opponent_pairs:
        if pair not in seen:
            seen.add(pair)
            unique_pairs.append(pair)
    
    return unique_pairs


def generate_matchup_memory_section(player_opponent_pairs, stat_cat="points"):
    """Generate Matchup Memory section for enhanced report"""
    lines = []
    lines.append("=" * 80)
    lines.append("MATCHUP MEMORY — Player vs Opponent Historical Performance")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Stat Category: {stat_cat.upper()}")
    lines.append("Shows how players perform against specific opponents this season.")
    lines.append("")
    
    if not player_opponent_pairs:
        lines.append("  ⚠️ No player-opponent pairs could be extracted from report")
        lines.append("")
        return lines
    
    try:
        from nba_api.stats.endpoints import playergamelog
        from nba_api.stats.static import players, teams
    except ImportError:
        lines.append("  ⚠️ nba_api not installed - Matchup Memory unavailable")
        lines.append("     Run: pip install nba_api")
        lines.append("")
        return lines
    
    stat_map = {
        "points": "PTS",
        "rebounds": "REB",
        "assists": "AST",
        "threes": "FG3M",
        "pts_rebs_asts": ["PTS", "REB", "AST"],
        "pts_rebs": ["PTS", "REB"],
        "pts_asts": ["PTS", "AST"],
    }
    
    archetype_groups = defaultdict(list)
    player_results = []
    
    print(f"  [*] Fetching matchup history for {len(player_opponent_pairs)} players...")
    
    for idx, (player_name, opponent) in enumerate(player_opponent_pairs[:30], 1):  # Limit to 30
        try:
            # Find player
            player_list = players.find_players_by_full_name(player_name)
            if not player_list:
                all_players = players.get_players()
                matches = [p for p in all_players if player_name.lower() in p['full_name'].lower()]
                if matches:
                    player_list = [matches[0]]
            
            if not player_list:
                continue
            
            player_id = player_list[0]['id']
            full_name = player_list[0]['full_name']
            
            # Get opponent team info
            team_info = teams.find_team_by_abbreviation(opponent)
            if not team_info:
                all_teams = teams.get_teams()
                for t in all_teams:
                    if t['abbreviation'].upper() == opponent.upper():
                        team_info = t
                        break
            
            if not team_info:
                continue
            
            opp_name = team_info['full_name']
            
            # Rate limit
            time.sleep(0.6)
            
            # Get game logs
            log = playergamelog.PlayerGameLog(player_id=player_id, season='2024-25')
            df = log.get_data_frames()[0]
            
            if df.empty:
                continue
            
            # Filter for matchups vs opponent
            matchup_games = df[df['MATCHUP'].str.contains(opponent, case=False, na=False)]
            
            # Calculate stats
            if isinstance(stat_map.get(stat_cat, "PTS"), list):
                cols = stat_map[stat_cat]
                matchup_avg = matchup_games[cols].sum(axis=1).mean() if len(matchup_games) > 0 else 0
                overall_avg = df[cols].sum(axis=1).mean()
            else:
                col = stat_map.get(stat_cat, "PTS")
                matchup_avg = matchup_games[col].mean() if len(matchup_games) > 0 else 0
                overall_avg = df[col].mean()
            
            # Simple archetype classification
            if overall_avg > 20:
                archetype = "PRIMARY_SCORER"
            elif overall_avg > 14:
                archetype = "SECONDARY_CREATOR"
            elif overall_avg > 8:
                archetype = "CONNECTOR_STARTER"
            else:
                archetype = "BENCH_ROLE"
            
            matchup_count = len(matchup_games)
            overall_count = len(df)
            
            if matchup_count > 0 and overall_avg > 0:
                diff = matchup_avg - overall_avg
                diff_pct = (diff / overall_avg) * 100
            else:
                diff = 0
                diff_pct = 0
            
            result = {
                "player": full_name,
                "opponent": opp_name,
                "opp_abbrev": opponent,
                "archetype": archetype,
                "overall_avg": overall_avg,
                "matchup_avg": matchup_avg,
                "matchup_games": matchup_count,
                "overall_games": overall_count,
                "diff": diff,
                "diff_pct": diff_pct,
            }
            
            player_results.append(result)
            archetype_groups[archetype].append(result)
            
            print(f"      [{idx}] {full_name}: {diff:+.1f} vs {opponent}")
            
        except Exception as e:
            continue
    
    # Generate report content
    if not player_results:
        lines.append("  ⚠️ Could not fetch matchup data for players")
        lines.append("")
        return lines
    
    # Results by archetype
    for archetype in sorted(archetype_groups.keys()):
        group = archetype_groups[archetype]
        lines.append(f"{'─' * 60}")
        lines.append(f"  🎯 {archetype} ({len(group)} players)")
        lines.append(f"{'─' * 60}")
        
        sorted_group = sorted(group, key=lambda x: x['diff'], reverse=True)
        
        for r in sorted_group:
            indicator = "🔥" if r['diff'] > 2 else ("🔻" if r['diff'] < -2 else "➖")
            sample_warning = " ⚠️" if r['matchup_games'] < 3 else ""
            # Show archetype as specialist type if present
            player_line = f"  {indicator} {r['player']:<22}"
            if r.get('archetype') and r['archetype'] != 'BENCH_ROLE':
                player_line += f" [{r['archetype']}]"
            player_line += f" vs {r['opp_abbrev']:<5}"
            lines.append(player_line)
            lines.append(f"       Season Avg: {r['overall_avg']:.1f} ({r['overall_games']} gms)")
            lines.append(f"       vs Opponent: {r['matchup_avg']:.1f} ({r['matchup_games']} gms) → {r['diff']:+.1f}{sample_warning}")
        lines.append("")
    
    # Summary section
    lines.append("=" * 80)
    lines.append("MATCHUP MEMORY SUMMARY")
    lines.append("=" * 80)
    
    overperformers = [r for r in player_results if r['diff'] > 2]
    underperformers = [r for r in player_results if r['diff'] < -2]
    
    if overperformers:
        lines.append("")
        lines.append("  🔥 MATCHUP OVERPERFORMERS (consider HIGHER):")
        for r in sorted(overperformers, key=lambda x: x['diff'], reverse=True)[:10]:
            lines.append(f"     • {r['player']} vs {r['opp_abbrev']}: +{r['diff']:.1f} ({r['archetype'][:15]})")
    
    if underperformers:
        lines.append("")
        lines.append("  🔻 MATCHUP UNDERPERFORMERS (consider LOWER):")
        for r in sorted(underperformers, key=lambda x: x['diff'])[:10]:
            lines.append(f"     • {r['player']} vs {r['opp_abbrev']}: {r['diff']:.1f} ({r['archetype'][:15]})")
    
    lines.append("")
    lines.append(f"  📊 Players analyzed: {len(player_results)}")
    lines.append(f"  📈 Archetypes covered: {len(archetype_groups)}")
    lines.append("")
    
    return lines


def _extract_risk_source_from_report(report_path):
    """Given a FULL_REPORT txt path, resolve the underlying RISK_FIRST JSON.

    Looks for a header line like:
        Data Source:    NBAMONDA1ST_RISK_FIRST_20260209_FROM_UD.json

    Returns a Path to the JSON file under outputs/ (or absolute if present),
    or None if it cannot be resolved.
    """
    report_path = Path(report_path)
    try:
        with report_path.open(encoding="utf-8", errors="replace") as f:
            # Only need header region
            header_lines = [next(f) for _ in range(80)]
    except (FileNotFoundError, StopIteration, OSError):
        return None

    json_name = None
    for line in header_lines:
        if "Data Source:" in line:
            # e.g. "  Data Source:    NBAMONDA1ST_RISK_FIRST_20260209_FROM_UD.json"
            m = re.search(r"Data Source:\s*(\S+\.json)", line)
            if m:
                json_name = m.group(1).strip()
            break

    if not json_name:
        return None

    # If the report already stores an absolute/relative path that exists, use it
    candidate = Path(json_name)
    if candidate.exists():
        return candidate

    # Otherwise assume it lives under outputs/
    candidate = Path("outputs") / json_name
    if candidate.exists():
        return candidate

    return None


def generate_probability_breakdown_section_from_full_report(full_report_path, top_n=10):
    """Build a text section mirroring menu's Probability Breakdown view.

    This is read-only: it explains how the Truth Engine and calibration stack
    arrive at each pick's final confidence. It never alters probabilities.
    """
    json_path = _extract_risk_source_from_report(full_report_path)
    if not json_path:
        return []

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    # Locate list of picks/edges
    picks = []
    if isinstance(data, list):
        picks = data
    elif isinstance(data, dict):
        for key in ("results", "picks", "edges", "data"):
            val = data.get(key)
            if isinstance(val, list) and val and isinstance(val[0], dict):
                picks = val
                break
        if not picks:
            # Fallback: first list-of-dicts value
            for val in data.values():
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    picks = val
                    break

    if not picks:
        return []

    # Filter out SKIP/BLOCKED/REJECTED per governance
    EXCLUDED_STATUSES = {"SKIP", "SKIPPED", "BLOCKED", "REJECTED"}
    valid_picks = []
    for p in picks:
        status = str(p.get("status", p.get("decision", ""))).upper()
        if status in EXCLUDED_STATUSES:
            continue
        valid_picks.append(p)

    if not valid_picks:
        return []

    # Sort by effective confidence descending (fallback to status_confidence/probability)
    def _conf(pick):
        val = pick.get(
            "effective_confidence",
            pick.get("status_confidence", pick.get("probability", 0)),
        )
        try:
            return float(val or 0)
        except Exception:
            return 0.0

    valid_picks.sort(key=_conf, reverse=True)

    lines = []
    lines.append("=" * 80)
    lines.append("PROBABILITY BREAKDOWN — What Makes Up Each Pick's Confidence")
    lines.append("=" * 80)
    lines.append("")
    lines.append(
        "This section explains how the model and calibration stack arrive at the "
        "final confidence values for the top governed picks."
    )
    lines.append("")

    for idx, pick in enumerate(valid_picks[: max(1, int(top_n))], 1):
        player = pick.get("player", "Unknown")
        team = pick.get("team", "?")
        stat = pick.get("stat", pick.get("market", "?"))
        line = pick.get("line", "?")
        direction = pick.get("direction", "higher").upper()

        # Tier/label if present
        tier = (
            pick.get("tier_label_final")
            or pick.get("tier_label")
            or pick.get("hybrid_tier")
            or pick.get("tier")
        )
        status = pick.get("status", pick.get("decision", ""))

        # Base distribution params
        mu = pick.get("mu")
        sigma = pick.get("sigma")
        if isinstance(mu, (int, float)) and isinstance(sigma, (int, float)):
            base_line = f"μ={mu:.2f}, σ={sigma:.2f}"
        else:
            base_line = f"μ={mu}, σ={sigma}"

        # Raw & final probabilities (already expressed as percents in JSON)
        raw_val = pick.get(
            "model_confidence",
            pick.get("raw_probability", pick.get("probability", 50.0)),
        )
        final_val = pick.get(
            "effective_confidence",
            pick.get("status_confidence", pick.get("probability", 0.0)),
        )
        try:
            raw_pct = float(raw_val or 0.0)
        except Exception:
            raw_pct = 0.0
        try:
            final_pct = float(final_val or 0.0)
        except Exception:
            final_pct = 0.0

        lines.append(f"[{idx}] {player} ({team}) — {stat} {direction} {line}")
        meta_bits = []
        if tier:
            meta_bits.append(f"Tier: {tier}")
        if status:
            meta_bits.append(f"Status: {status}")
        if meta_bits:
            lines.append("    " + " | ".join(meta_bits))
        lines.append(f"    📊 Base distribution: {base_line}")
        lines.append(f"    📈 Raw Probability (pre-penalties): {raw_pct:.1f}%")

        # Adjustments/penalties
        adjustments = pick.get("adjustments")
        if not adjustments:
            penalties = (
                pick.get("edge_diagnostics", {})
                .get("penalties", {})
                .get("penalty_details", [])
            )
            adjustments = penalties

        if adjustments:
            lines.append("    🔧 Adjustments / Penalties Applied:")
            for adj in adjustments:
                lines.append(f"       • {adj}")

        # Stat-specific calibration multiplier
        stat_mult_obj = pick.get("stat_multiplier")
        stat_mult_val = None
        if isinstance(stat_mult_obj, (int, float)):
            stat_mult_val = stat_mult_obj
        elif isinstance(stat_mult_obj, dict):
            stat_mult_val = stat_mult_obj.get("multiplier")

        if isinstance(stat_mult_val, (int, float)):
            lines.append(
                f"    📉 Stat Multiplier (data-driven calibration): {stat_mult_val:.2f}"
            )

        # Confidence cap if present
        cap = pick.get("confidence_cap")
        if isinstance(cap, (int, float)) and cap > 0:
            # Some configs may store cap as 0-1 or 0-100; normalize roughly
            cap_val = cap * 100 if cap <= 1 else cap
            lines.append(f"    🚫 Confidence Cap: {cap_val:.0f}%")

        lines.append(
            f"    ✅ Final Probability (post-calibration & governance): {final_pct:.1f}%"
        )
        lines.append("")

    remaining = max(0, len(valid_picks) - max(1, int(top_n)))
    if remaining:
        lines.append(f"... and {remaining} more governed picks in this slate.")
        lines.append("")

    lines.append("Note: Probabilities use Normal approximation and calibration multipliers;")
    lines.append(
        "the Truth Engine's Monte Carlo and governance layers remain the canonical "
        "source of edge quality."
    )
    lines.append("")

    return lines


def generate_enhanced_report(input_file=None, stat_cat="points"):
    """Generate enhanced report with coaching/team context and matchup memory"""
    
    # Determine input file
    if input_file is None:
        # Find latest report
        reports = sorted(Path("outputs").glob("*FULL_REPORT*.txt"))
        if not reports:
            print("X No reports found in outputs/")
            return None
        input_file = reports[-1]
    else:
        input_file = Path(input_file)
    
    if not input_file.exists():
        print(f"[X] File not found: {input_file}")
        return None
    
    print(f"[*] Reading: {input_file.name}")
    
    # Extract teams
    teams = extract_teams_from_report(input_file)
    print(f"[*] Found {len(teams)} teams: {', '.join(teams)}")
    
    # Load team ratings
    ratings = get_team_ratings()
    
    # Load original report
    with open(input_file, encoding='utf-8', errors='replace') as f:
        original_content = f.read()
    
    # Build enhanced report
    output = []
    
    # Header
    output.append("=" + "=" * 78 + "=")
    output.append(" " + " " * 78 + " ")
    output.append(" " + "ENHANCED CONTEXTUAL ANALYSIS REPORT".center(78) + " ")
    output.append(" " + "Coaching Tendencies - Team Schemes - Matchup Insights".center(78) + " ")
    output.append(" " + " " * 78 + " ")
    output.append("=" + "=" * 78 + "=")
    output.append("")
    output.append(f"  Generated:     {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    output.append(f"  Original Report: {input_file.name}")
    output.append(f"  Teams Analyzed:  {len(teams)}")
    output.append("")
    
    # Team context section
    output.extend(generate_team_context_section(teams, ratings))
    
    # Blowout analysis
    output.extend(generate_blowout_analysis(teams, ratings))

    # Probability Breakdown section (top picks confidence components)
    prob_section = generate_probability_breakdown_section_from_full_report(input_file)
    if prob_section:
        output.extend(prob_section)
    
    # Matchup Memory section - player vs opponent historical performance
    print(f"[*] Fetching Matchup Memory data for {stat_cat.upper()}...")
    player_opponent_pairs = extract_players_from_report(input_file)
    if player_opponent_pairs:
        print(f"[*] Found {len(player_opponent_pairs)} player-opponent pairs")
        output.extend(generate_matchup_memory_section(player_opponent_pairs, stat_cat=stat_cat))
    else:
        output.append("=" * 80)
        output.append("MATCHUP MEMORY — Player vs Opponent Historical Performance")
        output.append("=" * 80)
        output.append("")
        output.append("  ⚠️ No player-opponent pairs could be extracted from report")
        output.append("")
    
    # Separator before original report
    output.append("=" * 80)
    output.append("ORIGINAL ANALYSIS FOLLOWS")
    output.append("=" * 80)
    output.append("")
    output.append(original_content)
    
    # Write enhanced report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = input_file.stem.replace("_FULL_REPORT", "").replace("_20", "_")
    output_file = Path("outputs") / f"ENHANCED_CONTEXT_{label}_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print(f"\n[OK] Enhanced report saved to: {output_file}")
    print(f"[*] Total lines: {len(output)}")
    print(f"[*] Context added: {len(teams)} teams with coaching/matchup depth")
    print(f"[*] Matchup Memory: {len(player_opponent_pairs)} players analyzed")
    
    return output_file


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Generate enhanced NBA report with coaching/team context"
    )
    parser.add_argument(
        "--file", "-f",
        help="Path to existing report (default: latest in outputs/)",
        default=None
    )
    parser.add_argument(
        "--stat", "-s",
        help="Stat category for matchup memory (default: points)",
        default="points",
        choices=["points", "rebounds", "assists", "threes", "pts_rebs_asts", "pts_rebs", "pts_asts"]
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("ENHANCED CONTEXT REPORT GENERATOR")
    print("=" * 80)
    print()
    
    result = generate_enhanced_report(args.file, stat_cat=args.stat)
    
    if result:
        print("\n[DONE] Open the enhanced report to see:")
        print("  + Coaching styles and tendencies")
        print("  + Offensive/defensive schemes")
        print("  + Team pace and ratings")
        print("  + Matchup edges and weaknesses")
        print("  + Blowout risk analysis")
        print("  + Matchup Memory (player vs opponent history)")
        print("  + Rest/injury impacts")
        print("  + Your original full analysis")


if __name__ == "__main__":
    main()
