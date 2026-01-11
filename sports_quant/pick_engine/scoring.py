def score(edge: float, confidence: float, corr_penalty: float = 1.0) -> float:
    corr_penalty = max(corr_penalty, 1e-6)
    return float((edge * confidence) / corr_penalty)
