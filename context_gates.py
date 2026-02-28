"""
CONTEXTUAL RISK GATES
Coaching, rest, injuries, game dynamics
Facts beyond raw probability
"""

import json
from pathlib import Path

# ========================================
# CONTEXT GATE 1: BACK-TO-BACK FATIGUE
# ========================================
def gate_back_to_back(player: str, team: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C1 - Block if team is on back-to-back (fatigue risk)
    
    Facts: Players on 2nd night of B2B average:
    - 8-12% lower scoring
    - 15% higher injury risk
    - Reduced minutes if blowout develops
    """
    if game_context is None:
        game_context = {}
    
    rest_data = game_context.get("rest_advantage", {}).get(team, {})
    
    if rest_data.get("back_to_back", False):
        return False, f"BLOCKED: {team} on back-to-back (fatigue + injury risk)"
    
    return True, "PASS"


# ========================================
# CONTEXT GATE 2: HEAVY MINUTES LOAD
# ========================================
def gate_heavy_minutes(player: str, team: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C2 - Block if player played 38+ minutes in last game (rest risk)
    
    Facts: Players with 38+ minutes in last game:
    - Coaches often reduce minutes next game
    - Higher fatigue = lower efficiency
    - Increased DNP-Rest risk
    """
    if game_context is None:
        game_context = {}
    
    rest_data = game_context.get("rest_advantage", {}).get(team, {})
    last_game_mins = rest_data.get("last_game_minutes", {})
    
    player_mins = last_game_mins.get(player, 0)
    
    if player_mins >= 38:
        return False, f"BLOCKED: {player} played {player_mins} min last game (rest risk)"
    
    return True, "PASS"


# ========================================
# CONTEXT GATE 3: INJURY REPORT
# ========================================
def gate_injury_status(player: str, team: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C3 - Block if player is on injury report (ANY status)
    
    Facts: Players listed as Questionable/Probable/GTD:
    - May play limited minutes
    - May have performance restrictions
    - DNP risk exists
    """
    if game_context is None:
        game_context = {}
    
    injury_report = game_context.get("injury_report", {}).get(team, [])
    
    if player in injury_report:
        return False, f"BLOCKED: {player} on injury report (health uncertainty)"
    
    return True, "PASS"


# ========================================
# CONTEXT GATE 4: COACHING MINUTE LIMITS
# ========================================
def gate_minute_limit(player: str, team: str, stat: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C4 - Warn if player has known minute restriction from coach
    
    Facts: Coaches set minute limits for:
    - Injury recovery (returning players)
    - Rest management (veterans)
    - Development (rookies on timeshare)
    """
    if game_context is None:
        game_context = {}
    
    coaching = game_context.get("coaching_tendencies", {})
    
    for coach, data in coaching.items():
        if data.get("team") == team:
            minute_limits = data.get("minute_limits", {})
            
            if player in minute_limits:
                limit = minute_limits[player]
                # Warning, not block - but note the constraint
                return True, f"WARNING: {player} has {limit} min limit (coach policy)"
    
    return True, "PASS"


# ========================================
# CONTEXT GATE 5: REST ADVANTAGE MISMATCH
# ========================================
def gate_rest_mismatch(player: str, team: str, opponent: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C5 - Block if team is at significant rest disadvantage
    
    Facts: Team with less rest:
    - Lower 4Q scoring (fatigue)
    - Higher foul rate
    - Reduced defensive efficiency
    """
    if game_context is None:
        game_context = {}
    
    rest_data = game_context.get("rest_advantage", {})
    
    team_rest = rest_data.get(team, {}).get("days_rest", 1)
    opp_rest = rest_data.get(opponent, {}).get("days_rest", 1)
    
    rest_diff = opp_rest - team_rest
    
    # If opponent has 2+ more days rest
    if rest_diff >= 2:
        return False, f"BLOCKED: {team} at rest disadvantage ({team_rest}d vs {opp_rest}d)"
    
    return True, "PASS"


# ========================================
# CONTEXT GATE 6: TRAVEL FATIGUE
# ========================================
def gate_travel_distance(team: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C6 - Block if team traveled 2000+ miles (cross-country fatigue)
    
    Facts: Teams on long road trips (2000+ miles):
    - 5-8% lower scoring
    - Reduced pace
    - Higher turnover rate
    """
    if game_context is None:
        game_context = {}
    
    rest_data = game_context.get("rest_advantage", {}).get(team, {})
    travel_miles = rest_data.get("travel_distance_miles", 0)
    
    if travel_miles >= 2000:
        return False, f"BLOCKED: {team} traveled {travel_miles} miles (cross-country fatigue)"
    
    return True, "PASS"


# ========================================
# CONTEXT GATE 7: PACE MISMATCH
# ========================================
def gate_pace_mismatch(team: str, stat: str, game_context: dict = None) -> tuple[bool, str]:
    """
    C7 - Warn if stat relies on pace and pace is significantly lower
    
    Facts: Volume stats (PRA, assists, 3PM) suffer when:
    - Expected pace < 95 (slow game)
    - Team's preferred pace much higher than opponent
    """
    if game_context is None:
        game_context = {}
    
    pace_data = game_context.get("game_dynamics", {}).get("pace_matchup", {})
    expected_pace = pace_data.get("expected_pace", 100)
    
    volume_stats = ["pra", "pr", "pa", "ra", "assists", "3pm"]
    
    if stat.lower() in volume_stats and expected_pace < 95:
        return True, f"WARNING: Slow pace game ({expected_pace}) hurts volume stats"
    
    return True, "PASS"


# ========================================
# MASTER CONTEXT CHECK
# ========================================
def run_context_gates(player: str, team: str, opponent: str, stat: str, game_context: dict = None) -> dict:
    """
    Run all context gates to identify coaching/rest/injury risks
    
    Args:
        player: Player name
        team: Player's team
        opponent: Opponent team
        stat: Stat being bet
        game_context: Optional game context data (coaching, rest, injuries)
    
    Returns:
        {
            'hard_blocks': [list of blocking reasons],
            'warnings': [list of warning reasons],
            'all_clear': bool
        }
    """
    hard_blocks = []
    warnings = []
    
    # If game_context provided, use it; otherwise use dummy data
    if game_context is None:
        # Load from default file if exists
        try:
            import json
            with open("game_context.json") as f:
                game_context = json.load(f)
        except:
            game_context = {}
    
    # C1: Back-to-back
    passed, reason = gate_back_to_back(player, team, game_context)
    if not passed:
        hard_blocks.append(reason)
    
    # C2: Heavy minutes
    passed, reason = gate_heavy_minutes(player, team, game_context)
    if not passed:
        hard_blocks.append(reason)
    
    # C3: Injury report
    passed, reason = gate_injury_status(player, team, game_context)
    if not passed:
        hard_blocks.append(reason)
    
    # C4: Minute limits
    passed, reason = gate_minute_limit(player, team, stat, game_context)
    if "WARNING" in reason:
        warnings.append(reason)
    
    # C5: Rest mismatch
    passed, reason = gate_rest_mismatch(player, team, opponent, game_context)
    if not passed:
        hard_blocks.append(reason)
    
    # C6: Travel fatigue
    passed, reason = gate_travel_distance(team, game_context)
    if not passed:
        hard_blocks.append(reason)
    
    # C7: Pace mismatch
    passed, reason = gate_pace_mismatch(team, stat, game_context)
    if "WARNING" in reason:
        warnings.append(reason)
    
    return {
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "all_clear": len(hard_blocks) == 0
    }
