

# Dr. Golf Bayes (Strokes Gained Architect)
"""
Strokes Gained Bayesian modeling agent.
Calculates:
- Player baseline SG:Total and decomposition (OTT, APP, ARG, PUTT)
- Course fit correlations
- Field-adjusted skill estimates
- Bayesian priors for tournament modeling
"""

import pandas as pd
import os

class DrGolfBayes:
    def __init__(self, sg_data_path=None):
        if sg_data_path is None:
            sg_data_path = os.path.join(os.path.dirname(__file__), 'sample_sg_data.csv')
        self.sg_df = pd.read_csv(sg_data_path)

    def calculate_sg_baseline(self, player_id, lookback_rounds=50):
        """
        Calculate player's baseline SG:Total and decomposition
        Returns: dict with sg_ott, sg_app, sg_arg, sg_putt, sg_total
        """
        player_data = self.sg_df[self.sg_df['player_id'] == player_id].tail(lookback_rounds)
        if player_data.empty:
            return None
        return {
            'sg_ott': player_data['sg_ott'].mean(),
            'sg_app': player_data['sg_app'].mean(),
            'sg_arg': player_data['sg_arg'].mean(),
            'sg_putt': player_data['sg_putt'].mean(),
            'sg_total': player_data['sg_total'].mean()
        }

    def estimate_course_fit(self, player_id, course_id):
        """
        Estimate course-specific advantage (percentile vs field)
        Returns: course_fit_score (0-100)
        """
        course_data = self.sg_df[self.sg_df['course_id'] == course_id]
        player_row = course_data[course_data['player_id'] == player_id]
        if player_row.empty or course_data.empty:
            return None
        player_sg = player_row['sg_total'].mean()
        percentile = (course_data['sg_total'] < player_sg).mean() * 100
        return round(percentile, 1)

    def adjust_for_field_strength(self, player_sg, field_avg_owgr):
        """
        Normalize SG for field strength differences (mock: simple adjustment)
        Returns: field_adjusted_sg
        """
        # Assume lower OWGR = stronger field, so adjust down if field is strong
        # Example: field_avg_owgr 30 = strong, 70 = weak
        if field_avg_owgr < 40:
            adj = player_sg - 0.10
        elif field_avg_owgr > 60:
            adj = player_sg + 0.10
        else:
            adj = player_sg
        return round(adj, 3)

if __name__ == "__main__":
    agent = DrGolfBayes()
    print("Dr. Golf Bayes agent ready.")
    # Example usage:
    print("SG Baseline (Scheffler):", agent.calculate_sg_baseline(1))
    print("Course Fit (Scheffler, Augusta):", agent.estimate_course_fit(1, 'augusta'))
    print("Field Adjusted SG (Scheffler, field OWGR 28.4):", agent.adjust_for_field_strength(2.8, 28.4))
