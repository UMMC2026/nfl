from sports.cbb.cbb_archetypes import CBB_SPECIALIST_STATS

def attach_cbb_stat_averages(props, player_stats_dict):
    for prop in props:
        player = prop.get("player")
        stat_averages = {}
        stats = player_stats_dict.get(player, {})
        for stat in CBB_SPECIALIST_STATS:
            stat_averages[stat] = stats.get(stat, 0)
        prop["cbb_stat_averages"] = stat_averages
    return props

def assign_cbb_specialist_flags(props):
    stat_values = {stat: [] for stat in CBB_SPECIALIST_STATS}
    for prop in props:
        avgs = prop.get("cbb_stat_averages", {})
        for stat in CBB_SPECIALIST_STATS:
            val = avgs.get(stat)
            if isinstance(val, (int, float)):
                stat_values[stat].append(val)
    thresholds = {stat: sorted(vals, reverse=True)[max(0, int(0.2*len(vals))-1)] if vals else 0 for stat, vals in stat_values.items()}
    for prop in props:
        avgs = prop.get("cbb_stat_averages", {})
        flags = []
        for stat, flag in CBB_SPECIALIST_STATS.items():
            if avgs.get(stat, 0) >= thresholds[stat]:
                flags.append(flag)
        if flags:
            prop["cbb_specialist_flags"] = flags
    return props
