def hard_stop_gate(mu, sigma, line, prob):
    if sigma == 0:
        return False, "ZERO_VARIANCE"

    if mu == line and prob > 0.52:
        return False, "IMPOSSIBLE_EDGE"


    # CBB: Allow higher threshold for UNDERs due to market inflation
    import inspect
    caller = inspect.stack()[1].filename if len(inspect.stack()) > 1 else ''
    is_cbb = 'cbb' in caller.lower()
    under_threshold = 0.75 if is_cbb else 0.65
    if mu < line and prob > under_threshold:
        return False, "OVERCONFIDENT_UNDER"

    if mu > line and prob > 0.65:
        return False, "OVERCONFIDENT_OVER"

    return True, None
