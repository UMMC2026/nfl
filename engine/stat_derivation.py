COMPOSITE_MAP = {
    "rush_rec_tds": ["rush_tds", "rec_tds"],
    "rush_rec_yds": ["rush_yds", "rec_yds"]
}

def derive_composite(stat_key, atomic_values):
    if stat_key not in COMPOSITE_MAP:
        raise ValueError("Not a composite stat")
    components = COMPOSITE_MAP[stat_key]
    return sum(atomic_values.get(c, 0) for c in components)
