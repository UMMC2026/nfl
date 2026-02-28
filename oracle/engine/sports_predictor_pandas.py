#!/usr/bin/env python3
"""Sports Prediction Model - Ensemble ML Pipeline (pandas version)

This is an alternate ensemble model that works directly with pandas
DataFrames and includes simple feature engineering and time-series
cross-validation. It is intentionally kept separate from the
SportsEnsembleModel used by oracle_cli so it can be experimented with
safely.
"""

import warnings
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

try:
    import xgboost as xgb

    HAS_XGBOOST = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_XGBOOST = False
    print("Warning: XGBoost not installed. Install with: pip install xgboost")


class SportsPredictor:
    """Ensemble sports prediction model combining multiple ML algorithms.

    This version expects pandas DataFrames/Series for X/y and performs
    basic feature engineering (rolling stats, home/away splits, etc.).
    """

    def __init__(self, sport: str = "nba"):
        """Initialize the sports predictor.

        Args:
            sport: Sport type ("nba", "nfl", "mlb", "nhl", etc.)
        """

        self.sport = sport.lower()
        self.models: Dict[str, object] = {}
        self.weights: Dict[str, float] = {}
        self.is_fitted: bool = False

    def create_models(self) -> Dict[str, object]:
        """Create ensemble of models with simple hyperparameters."""

        models: Dict[str, object] = {
            "logistic": LogisticRegression(
                max_iter=1000,
                random_state=42,
                C=1.0,
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                random_state=42,
                n_jobs=-1,
            ),
        }

        if HAS_XGBOOST:
            models["xgboost"] = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                n_jobs=-1,
            )

        return models

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create derived features for prediction.

        Args:
            df: Raw stats dataframe

        Returns:
            DataFrame with engineered features
        """

        df = df.copy()

        # Rolling averages (last 5 games)
        for col in ["points", "assists", "rebounds", "turnovers"]:
            if col in df.columns:
                df[f"{col}_rolling_5"] = df.groupby("team_id")[col].transform(
                    lambda x: x.rolling(5, min_periods=1).mean()
                )

        # Home/away performance splits
        if "is_home" in df.columns:
            for col in ["points", "win"]:
                if col in df.columns:
                    df[f"{col}_home_avg"] = (
                        df[df["is_home"] == 1]
                        .groupby("team_id")[col]
                        .transform("mean")
                    )
                    df[f"{col}_away_avg"] = (
                        df[df["is_home"] == 0]
                        .groupby("team_id")[col]
                        .transform("mean")
                    )

        # Rest days impact
        if "days_rest" in df.columns:
            df["is_back_to_back"] = (df["days_rest"] == 0).astype(int)
            df["well_rested"] = (df["days_rest"] >= 3).astype(int)

        # Opponent strength
        if "opponent_win_pct" in df.columns:
            df["vs_winning_team"] = (df["opponent_win_pct"] > 0.5).astype(int)

        return df

    def fit(self, X: pd.DataFrame, y: pd.Series, validate: bool = True) -> Dict:
        """Fit ensemble models with time-series cross-validation.

        Args:
            X: Feature matrix (DataFrame)
            y: Target variable (1 = win, 0 = loss)
            validate: Whether to perform cross-validation

        Returns:
            Dictionary with validation metrics per base model
        """

        self.models = self.create_models()
        results: Dict[str, Dict[str, float]] = {}

        if validate:
            # Time-series cross-validation (no data leakage)
            tscv = TimeSeriesSplit(n_splits=5)

            for name, model in self.models.items():
                cv_scores = []
                cv_brier = []

                for train_idx, val_idx in tscv.split(X):
                    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

                    model.fit(X_train, y_train)

                    if hasattr(model, "predict_proba"):
                        y_pred_proba = model.predict_proba(X_val)[:, 1]
                        cv_brier.append(brier_score_loss(y_val, y_pred_proba))

                    y_pred = model.predict(X_val)
                    cv_scores.append(accuracy_score(y_val, y_pred))

                results[name] = {
                    "accuracy": float(np.mean(cv_scores)),
                    "accuracy_std": float(np.std(cv_scores)),
                    "brier_score": float(np.mean(cv_brier)) if cv_brier else None,
                }

        # Fit on full dataset
        for name, model in self.models.items():
            model.fit(X, y)

        # Calculate ensemble weights based on validation performance
        if validate and results:
            accuracies = [results[name]["accuracy"] for name in self.models.keys()]
            total_acc = sum(accuracies) or 1.0
            self.weights = {
                name: acc / total_acc
                for name, acc in zip(self.models.keys(), accuracies)
            }
        else:
            # Equal weights if no validation
            n = len(self.models) or 1
            self.weights = {name: 1.0 / n for name in self.models.keys()}

        self.is_fitted = True
        return results

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probabilities using weighted ensemble.

        Args:
            X: Feature matrix

        Returns:
            Array of positive-class probabilities
        """

        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")

        predictions = []

        for name, model in self.models.items():
            if hasattr(model, "predict_proba"):
                pred_proba = model.predict_proba(X)[:, 1]
            else:
                # Fallback to binary prediction
                pred_proba = model.predict(X).astype(float)

            # Weight by model performance
            w = self.weights.get(name, 0.0)
            predictions.append(pred_proba * w)

        # Ensemble average
        ensemble_pred = np.sum(predictions, axis=0)

        return ensemble_pred

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        """Predict binary outcomes from ensemble probabilities."""

        probabilities = self.predict_proba(X)
        return (probabilities >= threshold).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate model performance on held-out data."""

        y_pred_proba = self.predict_proba(X)
        y_pred = self.predict(X)

        metrics = {
            "accuracy": float(accuracy_score(y, y_pred)),
            "brier_score": float(brier_score_loss(y, y_pred_proba)),
            "log_loss": float(log_loss(y, y_pred_proba)),
        }

        return metrics

    def get_feature_importance(self, X: pd.DataFrame) -> pd.DataFrame | None:
        """Get aggregated feature importance across models.

        Args:
            X: Feature matrix (for column names)

        Returns:
            DataFrame with feature importances, or None if unsupported.
        """

        importances = []

        for name, model in self.models.items():
            if hasattr(model, "feature_importances_"):
                imp = model.feature_importances_
            elif hasattr(model, "coef_"):
                imp = np.abs(model.coef_[0])
            else:
                continue

            w = self.weights.get(name, 0.0)
            importances.append(imp * w)

        if not importances:
            return None

        avg_importance = np.mean(importances, axis=0)

        feature_importance_df = (
            pd.DataFrame({"feature": X.columns, "importance": avg_importance})
            .sort_values("importance", ascending=False)
            .reset_index(drop=True)
        )

        return feature_importance_df
