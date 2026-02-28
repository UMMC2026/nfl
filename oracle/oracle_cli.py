"""Oracle CLI wrapper for training and scoring sports models.

Usage examples (from repo root with venv active):

  python -m oracle.oracle_cli train \
      --train-csv data/train.csv \
      --target-col hit \
      --model-out models/oracle_nba.pkl

  python -m oracle.oracle_cli predict \
      --model models/oracle_nba.pkl \
      --input-csv data/today_features.csv \
      --output-csv outputs/oracle_today.csv \
      --decimal-odds 1.8
"""

import argparse
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Local imports (package-relative)
from engine.sports_ml_model import SportsEnsembleModel
from engine.probability_calculator import expected_value, kelly_fraction


def _load_dataframe(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    return pd.read_csv(p)


def cmd_train(args: argparse.Namespace) -> None:
    df = _load_dataframe(args.train_csv)
    if args.target_col not in df.columns:
        raise ValueError(f"target_col '{args.target_col}' not in columns: {list(df.columns)}")

    y = df[args.target_col].values
    X = df.drop(columns=[args.target_col]).values

    model = SportsEnsembleModel()

    if args.cv_splits and args.cv_splits > 1:
        brier = model.time_series_validate(X, y, splits=args.cv_splits)
        print(f"Time-series CV Brier score: {brier:.4f}")

    # Fit on full data
    model.fit(X, y)

    out_path = Path(args.model_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(model, f)

    print(f"[OK] Saved model to {out_path}")


def cmd_predict(args: argparse.Namespace) -> None:
    model_path = Path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with open(model_path, "rb") as f:
        model: SportsEnsembleModel = pickle.load(f)

    df = _load_dataframe(args.input_csv)
    X = df.values

    probs = model.predict_proba(X)
    df_out = df.copy()
    df_out["prob"] = probs

    # Optional EV / Kelly if decimal odds provided
    if args.decimal_odds is not None:
        dec = float(args.decimal_odds)
        df_out["ev"] = [expected_value(p, dec) for p in probs]
        if args.kelly_fraction is not None:
            frac = float(args.kelly_fraction)
        else:
            frac = 0.25
        df_out["kelly"] = [kelly_fraction(p, dec, fraction=frac) for p in probs]

    out_path = Path(args.output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_path, index=False)
    print(f"[OK] Wrote predictions to {out_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Oracle CLI for sports ML ensemble")
    sub = parser.add_subparsers(dest="command", required=True)

    # Train
    p_train = sub.add_parser("train", help="Train ensemble model from CSV")
    p_train.add_argument("--train-csv", required=True, help="Training CSV path")
    p_train.add_argument("--target-col", required=True, help="Name of target column (0/1)")
    p_train.add_argument("--model-out", required=True, help="Output path for pickled model")
    p_train.add_argument("--cv-splits", type=int, default=0, help="Optional time-series CV splits (0 to skip)")
    p_train.set_defaults(func=cmd_train)

    # Predict
    p_pred = sub.add_parser("predict", help="Score features with trained model")
    p_pred.add_argument("--model", required=True, help="Path to pickled model")
    p_pred.add_argument("--input-csv", required=True, help="Input feature CSV")
    p_pred.add_argument("--output-csv", required=True, help="Output CSV with probabilities")
    p_pred.add_argument("--decimal-odds", type=float, help="Optional decimal odds for EV/Kelly calculation")
    p_pred.add_argument("--kelly-fraction", type=float, help="Fractional Kelly (default 0.25 if odds given)")
    p_pred.set_defaults(func=cmd_predict)

    return parser


def main(argv: Optional[list] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
