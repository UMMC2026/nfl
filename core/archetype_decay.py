ARCHETYPES = {
    "CATCH_SHOOT_3": {"base_half_life": 6},
    "USAGE_SCORER": {"base_half_life": 5},
    "RIM_PROTECTOR": {"base_half_life": 10},
    "REBOUND_SCHEME_BIG": {"base_half_life": 12},
    "ASSIST_DEPENDENT_GUARD": {"base_half_life": 7},
    "SECONDARY_HANDLER": {"base_half_life": 8}
}

def archetype_half_life(archetype, observed_half_life):
    base = ARCHETYPES[archetype]["base_half_life"]
    if observed_half_life is None:
        return base * 0.7
    return 0.6 * observed_half_life + 0.4 * base
