def kelly_fraction(p, odds):
    return max((p * odds - 1) / (odds - 1), 0)

def decay_adjusted_kelly(raw_p, exec_p, odds, half_life):
    base = kelly_fraction(exec_p, odds)
    if half_life is None:
        return base * 0.5
    if half_life < 5:
        return base * 0.3
    if half_life < 10:
        return base * 0.6
    return base

KELLY_CAPS = {
    "underdog": 0.25,
    "prizepicks": 0.35,
    "sleeper": 0.15
}

def capped_kelly(kelly, platform):
    return min(kelly, KELLY_CAPS[platform])

def final_stake(bankroll, p_raw, p_exec, odds, half_life, platform):
    kelly = decay_adjusted_kelly(p_raw, p_exec, odds, half_life)
    return bankroll * capped_kelly(kelly, platform)
