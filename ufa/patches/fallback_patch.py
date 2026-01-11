def apply():
    """Monkeypatch DailyPipeline.calculate_probability to add league-average mu/sigma fallback."""
    try:
        from ufa.daily_pipeline import DailyPipeline
        from scipy.stats import norm
    except Exception:
        return

    def calculate_probability_with_fallback(self, pick: dict) -> float:
        """Calculate probability, applying a league-average fallback for mu/sigma when missing."""
        mu = pick.get("mu")
        sigma = pick.get("sigma")
        line = pick.get("line")
        direction = pick.get("direction", "higher")

        # If mu/sigma missing or invalid, derive quick fallback:
        if mu is None or sigma is None or sigma <= 0:
            stat_l = str(pick.get('stat', '')).lower()
            try:
                # Slight bias toward the market: assume true mean ≈ 95% of line
                mu = float(line) * 0.95 if line is not None else 1.0
            except Exception:
                mu = 1.0

            count_indicators = ['td', 'attempt', 'recept', 'reception', 'sack', 'fg_made', 'kicking_points', 'rush', 'rec', 'tackle']
            yard_indicators = ['yard', 'yd']

            try:
                if any(k in stat_l for k in count_indicators):
                    sigma = max(0.5, (abs(mu) ** 0.5) * 1.2)
                elif any(k in stat_l for k in yard_indicators):
                    sigma = max(1.0, abs(mu) * 0.20)
                else:
                    sigma = max(0.5, abs(mu) * 0.15)
            except Exception:
                sigma = max(0.5, abs(mu) * 0.15)

            # Persist to pick so downstream sees values
            pick['mu'] = mu
            pick['sigma'] = sigma
            pick.setdefault('recent_values', [])

        if direction == "higher":
            return 1 - norm.cdf(line, mu, sigma)
        else:
            return norm.cdf(line, mu, sigma)

    DailyPipeline.calculate_probability = calculate_probability_with_fallback
