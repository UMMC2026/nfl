"""Attach Oracle ensemble probabilities to risk-first props JSON.

Usage example (from repo root, venv active):

  python scripts/attach_oracle_probs.py \
      --props-json outputs/RISK_FIRST_LATEST.json \
      --oracle-csv outputs/oracle_today.csv \
      --output-json outputs/RISK_FIRST_with_oracle.json \
      --join-keys player,stat,line,direction \
      --oracle-prob-col prob

This will:
- Load the props JSON (either a list or a dict with a "results" list).
- Load the Oracle CSV (must have the join key columns + a probability column).
- For each matching row, set `prop["oracle_prob"]` to the Oracle probability
  (left as-is if >1, treated as decimal if <=1).
- Write the updated JSON to the output path.

You can then run the NBA pipeline with USE_ORACLE_PROB=1 to have
risk_first_analyzer use these probabilities as model_confidence.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


def _load_props(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    """Load props JSON; return (props_list, root_obj, mode).

    mode is "list" if the root is a list, or a key name (e.g., "results") if
    the list is nested under that key.
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data, data, "list"

    if isinstance(data, dict):
        for key in ("results", "props", "plays", "edges", "signals"):
            if key in data and isinstance(data[key], list):
                return data[key], data, key

    raise ValueError(f"Unrecognized props JSON structure in {path}")


def _build_oracle_mapping(df, join_keys: List[str], prob_col: str) -> Dict[Tuple[Any, ...], float]:
    for key in join_keys:
        if key not in df.columns:
            raise ValueError(f"Join key '{key}' not found in Oracle CSV columns: {list(df.columns)}")
    if prob_col not in df.columns:
        raise ValueError(f"oracle_prob_col '{prob_col}' not found in Oracle CSV columns: {list(df.columns)}")

    # Build tuple-keyed mapping
    keys = list(zip(*[df[k].tolist() for k in join_keys]))
    probs = df[prob_col].tolist()
    mapping: Dict[Tuple[Any, ...], float] = {}
    for k, p in zip(keys, probs):
        try:
            mapping[k] = float(p)
        except Exception:
            continue
    return mapping


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Attach Oracle probabilities to props JSON")
    parser.add_argument("--props-json", required=True, help="Input props JSON (risk-first format)")
    parser.add_argument("--oracle-csv", required=True, help="Oracle output CSV (with probabilities)")
    parser.add_argument("--output-json", required=True, help="Output JSON path")
    parser.add_argument(
        "--join-keys",
        default="player,stat,line,direction",
        help="Comma-separated column/field names to join on (default: player,stat,line,direction)",
    )
    parser.add_argument(
        "--oracle-prob-col",
        default="prob",
        help="Column name in Oracle CSV containing probabilities (default: prob)",
    )

    args = parser.parse_args(argv)

    props_path = Path(args.props_json)
    oracle_path = Path(args.oracle_csv)
    out_path = Path(args.output_json)

    props, root, mode = _load_props(props_path)
    df_oracle = pd.read_csv(oracle_path)

    join_keys = [k.strip() for k in args.join_keys.split(",") if k.strip()]
    mapping = _build_oracle_mapping(df_oracle, join_keys, args.oracle_prob_col)

    # Attach oracle_prob where keys match
    updated = 0
    for prop in props:
        if not isinstance(prop, dict):
            continue
        key = tuple(prop.get(k) for k in join_keys)
        if key in mapping:
            prop["oracle_prob"] = mapping[key]
            updated += 1

    # Write back
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "list":
        to_dump = root
    else:
        to_dump = root

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(to_dump, f, indent=2)

    print(f"[OK] Attached oracle_prob to {updated} props → {out_path}")


if __name__ == "__main__":
    main()
