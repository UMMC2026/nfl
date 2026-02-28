class FailFastError(Exception):
    pass

# Valid sports for fail_fast validation
VALID_SPORTS = {"NBA", "CBB", "NFL", "PGA", "GOLF", "TENNIS", "SOCCER", "CFB", "WNBA", "MLB", "NHL"}

def fail_fast_check(
    sport,
    stat,
    game_logs,
    mu_raw,
    sigma,
    prob_raw
):
    if sport.upper() not in VALID_SPORTS:
        raise FailFastError(f"Invalid sport context: {sport}")

    if game_logs is None or len(game_logs) < 3:
        raise FailFastError("Insufficient sample size")

    if mu_raw <= 0:
        raise FailFastError("Invalid projection (mu_raw <= 0)")

    if sigma <= 0:
        raise FailFastError("Zero variance detected")

    # For CBB with NegBin model, tolerance = 0.03 (47-53% coin-flip zone)
    # NegBin produces more realistic spread so we can tighten this
    import inspect
    caller = inspect.stack()[1].filename if len(inspect.stack()) > 1 else ''
    is_cbb = 'cbb' in caller.lower()
    tolerance = 0.03 if is_cbb else 0.02
    if abs(prob_raw - 0.50) < tolerance:
        raise FailFastError("Coin-flip probability")

    return True
