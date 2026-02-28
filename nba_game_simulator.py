"""
NBA Game Simulator Proof-of-Concept
--------------------------------------------------
Simulates NBA game state evolution to derive player stat distributions for FUOOM integration.

Key Features:
- Possession chain simulation (Markov play types)
- Coaching tendency and blowout logic
- Player opportunity modeling by game context
- Monte Carlo output: full stat distribution, probability vs. market line

Integration:
1. Import GameSimulator into FUOOM pipeline
2. Instantiate with real team/player/coaching data
3. Use simulate_game() to generate MC distribution for player props
4. Use output for edge calculation, calibration, and reporting

Author: AI Quant Agent (2026)
--------------------------------------------------
"""
    # ...existing code...
    # Example usage and integration point at bottom of file
    # ...existing code...
    # Each opportunity is a Bernoulli trial for stat (e.g., points, assists)
    # Minutes played tracked for future enhancements (rotation modeling)
    # ...existing code...
    # PossessionChain models play type transitions and outcome probabilities
    # ...existing code...
    # Main simulation loop: tracks game script, pace, usage, and player stats
    # ...existing code...
    # Integration: import GameSimulator and use in FUOOM pipeline for player stat MC
import numpy as np
import random

class TeamStateModel:
    def __init__(self, name, pace, ppp, coach):
        self.name = name
        self.pace = pace  # possessions per 48 min
        self.ppp = ppp    # points per possession
        self.coach = coach

class GameState:
    def __init__(self, home_team, away_team):
        self.home_team = home_team
        self.away_team = away_team
        self.score_home = 0
        self.score_away = 0
        self.clock = 48 * 60  # seconds
        self.possession = 'home'
        self.blowout = False
    def is_final(self):
        return self.clock <= 0
    def update(self, outcome):
        if outcome['team'] == 'home':
            self.score_home += outcome['points']
        else:
            self.score_away += outcome['points']
        self.clock -= outcome['duration']
        self.possession = 'away' if self.possession == 'home' else 'home'
        # Blowout detection
        if abs(self.score_home - self.score_away) > 15 and self.clock < 6*60:
            self.blowout = True

class CoachingModel:
    def __init__(self, coach_name, tendencies):
        self.name = coach_name
        self.tendencies = tendencies
    def get_usage_rate(self, player_name, game_script):
        # Generalize for any player, fallback to default
        key = f'{player_name.lower()}_usage_{game_script}'
        return self.tendencies.get(key, self.tendencies.get('default_usage', 0.25))
    def get_pace_adjustment(self, script):
        return self.tendencies.get('pace_adjustment', {}).get(script, 0)
    def get_blowout_threshold(self):
        return self.tendencies.get('blowout_threshold', 15)

class PlayerOpportunityModel:
    def __init__(self, player_name, position, coach):
        self.name = player_name
        self.position = position
        self.coach = coach
        self.typical_minutes = 36
        self.bench_threshold_minutes = 28
        self.stats = []  # Points scored on each opportunity
        self.minutes_played = 0
        
        # Position-based scoring efficiency (points per scoring opportunity)
        # More realistic: not every touch results in a shot attempt
        self.scoring_efficiency = {
            'PG': {'shot_rate': 0.35, 'fg_pct': 0.44, 'three_rate': 0.35, 'three_pct': 0.36, 'ft_rate': 0.15},
            'SG': {'shot_rate': 0.40, 'fg_pct': 0.45, 'three_rate': 0.40, 'three_pct': 0.37, 'ft_rate': 0.12},
            'SF': {'shot_rate': 0.38, 'fg_pct': 0.46, 'three_rate': 0.32, 'three_pct': 0.35, 'ft_rate': 0.14},
            'PF': {'shot_rate': 0.42, 'fg_pct': 0.50, 'three_rate': 0.25, 'three_pct': 0.33, 'ft_rate': 0.16},
            'C':  {'shot_rate': 0.45, 'fg_pct': 0.58, 'three_rate': 0.10, 'three_pct': 0.30, 'ft_rate': 0.18}
        }
        
    def is_on_floor(self, game_state):
        # More nuanced: starters rest if blowout, or if leading/losing big
        if game_state.blowout and game_state.clock < 6*60:
            return random.random() > 0.7  # 30% chance still on floor
        return True
    
    def track_opportunity(self, possession, usage_rate, minutes_this_possession):
        """Track points scored on this opportunity based on realistic shooting model."""
        # First check if player gets the ball (usage)
        if random.random() >= usage_rate:
            self.stats.append(0)
            self.minutes_played += minutes_this_possession / 60
            return
        
        # Player has the ball - determine outcome
        eff = self.scoring_efficiency.get(self.position, self.scoring_efficiency['SF'])
        
        # Does player take a shot?
        if random.random() < eff['shot_rate']:
            # Is it a 3-pointer?
            if random.random() < eff['three_rate']:
                # 3-point attempt
                if random.random() < eff['three_pct']:
                    self.stats.append(3)
                else:
                    self.stats.append(0)
            else:
                # 2-point attempt
                if random.random() < eff['fg_pct']:
                    self.stats.append(2)
                else:
                    # Missed, but chance for free throws
                    if random.random() < 0.15:  # Foul on shot
                        ft_made = sum(1 for _ in range(2) if random.random() < 0.78)
                        self.stats.append(ft_made)
                    else:
                        self.stats.append(0)
        else:
            # No shot - pass/turnover/assist opportunity
            # Small chance for "and-1" or trip to line without shot attempt
            if random.random() < eff['ft_rate'] * 0.3:
                ft_made = sum(1 for _ in range(2) if random.random() < 0.78)
                self.stats.append(ft_made)
            else:
                self.stats.append(0)
        
        self.minutes_played += minutes_this_possession / 60
        
    @property
    def final_stats(self):
        return sum(self.stats)


# --- PossessionChain for play type transitions ---
class PossessionChain:
    """
    Models: Who gets the ball → What play type → What outcome
    """
    states = [
        'transition', 'half_court', 'post_up', 'pick_and_roll', 'isolation', 'spot_up'
    ]
    def __init__(self):
        # Markov chain transition probabilities (simplified)
        self.markov_chain = {
            'transition': {'half_court': 0.7, 'isolation': 0.1, 'pick_and_roll': 0.1, 'post_up': 0.1},
            'half_court': {'pick_and_roll': 0.4, 'post_up': 0.2, 'isolation': 0.2, 'spot_up': 0.2},
            'pick_and_roll': {'half_court': 0.5, 'isolation': 0.2, 'post_up': 0.2, 'spot_up': 0.1},
            'post_up': {'half_court': 0.6, 'isolation': 0.2, 'pick_and_roll': 0.1, 'spot_up': 0.1},
            'isolation': {'half_court': 0.7, 'pick_and_roll': 0.1, 'spot_up': 0.2},
            'spot_up': {'half_court': 0.8, 'isolation': 0.1, 'pick_and_roll': 0.1}
        }
    def next_play_type(self, current_state, game_context):
        transitions = self.markov_chain.get(current_state, {})
        states = list(transitions.keys())
        probs = list(transitions.values())
        if not states:
            return 'half_court'
        return np.random.choice(states, p=probs)
    def play_outcome(self, play_type, game_context):
        # Context-dependent outcome probabilities (simplified)
        # Example: more 3s in spot_up, more 2s in post_up, more turnovers in isolation
        if play_type == 'spot_up':
            return np.random.choice([0, 2, 3], p=[0.5, 0.2, 0.3])
        elif play_type == 'post_up':
            return np.random.choice([0, 2], p=[0.4, 0.6])
        elif play_type == 'pick_and_roll':
            return np.random.choice([0, 2, 3], p=[0.5, 0.4, 0.1])
        elif play_type == 'isolation':
            return np.random.choice([0, 2, 3], p=[0.6, 0.3, 0.1])
        elif play_type == 'transition':
            return np.random.choice([0, 2, 3], p=[0.4, 0.4, 0.2])
        else:
            return np.random.choice([0, 2, 3], p=[0.55, 0.35, 0.10])


class GameSimulator:
    def __init__(self, home_team, away_team, player_of_interest):
        self.teams = {
            'home': home_team,
            'away': away_team
        }
        self.player = player_of_interest
        self.game_state = GameState(home_team, away_team)
        self.possession_chain = PossessionChain()

    def simulate_game(self, n_sims=1000, market_line=26.5):
        player_stat_distributions = []
        for sim in range(n_sims):
            game = GameState(self.teams['home'], self.teams['away'])
            player = PlayerOpportunityModel(
                self.player.name, self.player.position, self.player.coach
            )
            play_type = 'transition'  # Start with transition
            while not game.is_final():
                # --- Determine game script for context ---
                score_diff = game.score_home - game.score_away if game.possession == 'home' else game.score_away - game.score_home
                if abs(score_diff) < 6:
                    script = 'close'
                elif score_diff > 0:
                    script = 'leading'
                else:
                    script = 'trailing'
                if game.blowout:
                    script = 'blowout'

                # --- Adjust pace for coaching tendencies ---
                pace_adj = self.teams[game.possession].coach.get_pace_adjustment(script)
                base_pace = self.teams[game.possession].pace
                # Possession duration: faster pace = shorter duration
                base_duration = 24 - (pace_adj / 2)  # crude mapping
                duration = max(12, min(24, int(random.gauss(base_duration, 2))))

                outcome, play_type = self._simulate_possession(game, play_type, duration)
                game.update(outcome)

                # --- Usage rate by context ---
                usage_rate = player.coach.get_usage_rate(player.name, script)
                # --- Player minutes adjustment for blowout ---
                if player.is_on_floor(game):
                    player.track_opportunity(outcome, usage_rate, duration)
            player_stat_distributions.append(player.final_stats)
        # Calculate probability over market line
        p_over = np.mean(np.array(player_stat_distributions) > market_line)
        return {
            'distribution': player_stat_distributions,
            'probability_over': p_over
        }

    def _simulate_possession(self, game_state, current_play_type, duration):
        team = game_state.possession
        next_play_type = self.possession_chain.next_play_type(current_play_type, game_state)
        points = self.possession_chain.play_outcome(next_play_type, game_state)
        return {
            'team': team,
            'points': points,
            'duration': duration
        }, next_play_type

# --- Example usage and integration point ---
if __name__ == "__main__":
    coach_tendencies = {
        'jokic_usage_close': 0.32,
        'jokic_usage_blowout': 0.18,
        'jokic_usage_leading': 0.28,
        'jokic_usage_trailing': 0.36,
        'default_usage': 0.25,
        'pace_adjustment': {'leading': -2.5, 'trailing': +3.2, 'close': 0, 'blowout': -4},
        'blowout_threshold': 15
    }
    coach = CoachingModel('Mike Malone', coach_tendencies)
    home_team = TeamStateModel('DEN', pace=99, ppp=1.12, coach=coach)
    away_team = TeamStateModel('BOS', pace=97, ppp=1.10, coach=coach)
    player = PlayerOpportunityModel('Jokic', 'C', coach)
    sim = GameSimulator(home_team, away_team, player)
    result = sim.simulate_game(n_sims=1000, market_line=26.5)
    print("--- NBA Game Simulator Results ---")
    print(f"Probability Jokic > 26.5: {result['probability_over']:.2f}")
    print(f"Mean: {np.mean(result['distribution']):.2f} | Std: {np.std(result['distribution']):.2f}")
    print(f"Sample: {result['distribution'][:10]}")
    # Integration: import GameSimulator and use in FUOOM pipeline for player stat MC
