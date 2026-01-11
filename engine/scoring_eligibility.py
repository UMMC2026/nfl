def is_scoring_eligible(pick, recent_values, policy, mode):
    min_games = policy["MIN_RECENT_GAMES"]

    if len(recent_values) < min_games:
        return False

    # NBA requires minutes proxy, NFL does not
    if pick["league"] == "NBA":
        if not pick.get("minutes_proxy_ok", False):
            return False

    # NFL: no minutes requirement
    return True
