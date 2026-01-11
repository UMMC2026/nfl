"""
Correlation kill-switch - prevents stacking correlated props from same player.
"""


def market_family(market: str) -> str:
    """
    Map specific markets to families to detect correlation.
    """
    market = market.lower()
    
    # Core counting stats
    if market in ["points", "assists", "rebounds"]:
        return "CORE"
    
    # Combo stats (highly correlated with core)
    if "pts+reb+ast" in market or market == "pra":
        return "PRA"
    if "pts+reb" in market or market == "pr":
        return "PR"
    if "pts+ast" in market or market == "pa":
        return "PA"
    if "reb+ast" in market or market == "ra":
        return "RA"
    
    # Shooting
    if "3pm" in market or "threes" in market:
        return "SHOOTING"
    
    # Defense
    if market in ["steals", "blocks"] or "stl+blk" in market:
        return "DEFENSE"
    
    # Turnovers (inverse correlation)
    if market == "turnovers":
        return "TOV"
    
    return market


def block_correlated(signals: list) -> list:
    """
    Filter out correlated signals from same player.
    Keeps only the highest probability signal per player per market family.
    """
    # Sort by p_hit descending so we keep best signal
    signals = sorted(signals, key=lambda x: x.get("p_hit", 0), reverse=True)
    
    seen = set()
    filtered = []

    for s in signals:
        player = s.get("player", "")
        stat = s.get("stat", "")
        family = market_family(stat)
        
        key = (player, family)
        if key in seen:
            continue
        seen.add(key)
        filtered.append(s)

    return filtered


def block_same_player_max(signals: list, max_per_player: int = 1) -> list:
    """
    Strict mode: max N signals per player regardless of market family.
    """
    signals = sorted(signals, key=lambda x: x.get("p_hit", 0), reverse=True)
    
    player_counts = {}
    filtered = []
    
    for s in signals:
        player = s.get("player", "")
        count = player_counts.get(player, 0)
        
        if count >= max_per_player:
            continue
            
        player_counts[player] = count + 1
        filtered.append(s)
    
    return filtered
