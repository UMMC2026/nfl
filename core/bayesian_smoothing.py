def bayesian_shrinkage(player_mean, player_n, prior_mean, prior_n):
    """
    Bayesian shrinkage for player means.
    Args:
        player_mean (float): Player's observed mean
        player_n (int): Number of player observations
        prior_mean (float): Prior mean (e.g., position/team average)
        prior_n (int): Strength of prior (pseudo-count)
    Returns:
        float: Posterior mean
    """
    posterior_mean = (player_mean * player_n + prior_mean * prior_n) / (player_n + prior_n)
    return posterior_mean
