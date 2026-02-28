import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier


class SportsEnsembleModel:
    """Simple ensemble model for sports binary outcomes.

    This wraps three base learners and averages their predicted probabilities.
    """

    def __init__(self):
        self.models = {
            "logistic": LogisticRegression(max_iter=1000),
            "rf": RandomForestClassifier(n_estimators=300, n_jobs=-1),
            "xgb": XGBClassifier(eval_metric="logloss", use_label_encoder=False),
        }

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit all base models on the same data."""
        X = np.asarray(X)
        y = np.asarray(y)
        for model in self.models.values():
            model.fit(X, y)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict ensemble probabilities for the positive class."""
        X = np.asarray(X)
        probs = []
        for model in self.models.values():
            p = model.predict_proba(X)[:, 1]
            probs.append(p)
        return np.mean(probs, axis=0)

    def time_series_validate(self, X: np.ndarray, y: np.ndarray, splits: int = 5) -> float:
        """Time-series cross-validation returning mean Brier score."""
        X = np.asarray(X)
        y = np.asarray(y)
        tscv = TimeSeriesSplit(n_splits=splits)
        scores = []
        for train_idx, test_idx in tscv.split(X):
            self.fit(X[train_idx], y[train_idx])
            preds = self.predict_proba(X[test_idx])
            # Brier score
            scores.append(np.mean((preds - y[test_idx]) ** 2))
        return float(np.mean(scores))
