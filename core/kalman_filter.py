import numpy as np

class KalmanFilter:
    """
    Simple Kalman filter for player stat smoothing.
    Use for points, minutes, usage, targets, etc.
    """
    def __init__(self, initial_mean, initial_var, process_var=1.0, measurement_var=1.0):
        self.mean = initial_mean
        self.var = initial_var
        self.process_var = process_var
        self.measurement_var = measurement_var

    def update(self, observed):
        pred_mean = self.mean
        pred_var = self.var + self.process_var
        kalman_gain = pred_var / (pred_var + self.measurement_var)
        self.mean = pred_mean + kalman_gain * (observed - pred_mean)
        self.var = (1 - kalman_gain) * pred_var
        return self.mean, self.var, kalman_gain

# Example usage:
# kf = KalmanFilter(initial_mean=20, initial_var=5)
# for obs in [22, 18, 25, 19]:
#     mu, sigma, K = kf.update(obs)
#     print(f"Filtered mean: {mu:.2f}, variance: {sigma:.2f}, Kalman gain: {K:.2f}")
