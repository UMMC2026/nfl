#!/usr/bin/env python3
#! pyright: reportMissingImports=false, reportUnknownMemberType=false, reportUnknownArgumentType=false

from __future__ import annotations

"""src/validation/validate_scraped_data.py

Scraped data validation gate (SOP §2.2 style).

Validates and merges raw prop artifacts from multiple platforms.
Outputs a Parquet file in `data/processed/` plus a JSON summary and checksum.

This gate is conservative and supports fail-fast by default.
"""

import argparse
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd  # type: ignore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_sha256_sidecar(file_path: Path) -> Path:
    digest = _sha256_bytes(file_path.read_bytes())
    sidecar = file_path.with_suffix(file_path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {file_path.name}\n", encoding="utf-8")
    return sidecar


def _normalize_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", str(name))
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return " ".join(n.split()).strip()


def _normalize_stat(stat: str) -> str:
    s = str(stat).strip().lower()
    s = s.replace("pts + rebs + asts", "pra")
    s = s.replace("points", "points")
    s = s.replace("rebounds", "rebounds")
    s = s.replace("assists", "assists")
    s = s.replace("3-pointers made", "3pm")
    s = s.replace("threes made", "3pm")
    s = s.replace("shots on goal", "sog")
    # Soccer naming (keep underscores to match downstream analyzers)
    s = s.replace("shots on target", "shots_on_target")
    return s


@dataclass
class ValidationConfig:
    require_platforms: int = 1
    max_age_hours: float = 2.0
    fail_on_discrepancy: bool = True
    allow_discrepancies: bool = False


class ScrapedDataValidator:
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()

        # tolerance thresholds by stat (line spread allowed across platforms)
        self.tolerance_thresholds = {
            "points": 1.5,
            "rebounds": 1.0,
            "assists": 1.0,
            "3pm": 0.5,
            "pra": 2.5,
            "sog": 0.5,
            "saves": 2.0,
            "aces": 1.0,
            # Soccer (lines tend to be in 0.5 increments)
            "shots": 1.0,
            "shots_on_target": 1.0,
        }

        # basic rationality bounds by stat
        self.bounds = {
            "points": (0.0, 100.0),
            "rebounds": (0.0, 40.0),
            "assists": (0.0, 30.0),
            "3pm": (0.0, 15.0),
            "pra": (0.0, 150.0),
            "sog": (0.0, 15.0),
            "saves": (0.0, 80.0),
            "aces": (0.0, 40.0),
            # Soccer (conservative; prevents obvious scrape/API corruption)
            "shots": (0.0, 20.0),
            "shots_on_target": (0.0, 12.0),
        }

    def validate_scrape_batch(self, file_paths: Dict[str, Path]) -> Tuple[pd.DataFrame, Dict]:
        if len(file_paths) < self.config.require_platforms:
            raise RuntimeError(
                f"Need >= {self.config.require_platforms} platform files, got {len(file_paths)}"
            )

        dfs: List[pd.DataFrame] = []
        meta: Dict[str, dict] = {}

        for platform, path in file_paths.items():
            data = json.loads(path.read_text(encoding="utf-8"))
            meta[platform] = data.get("metadata", {})
            df = pd.DataFrame(data.get("props", []))
            if df.empty:
                raise RuntimeError(f"Platform {platform} produced 0 props: {path.name}")
            df["platform"] = platform
            dfs.append(df)

        combined = pd.concat(dfs, ignore_index=True)

        # Normalize
        combined["player_normalized"] = combined["player"].astype(str).apply(_normalize_name)
        combined["stat_normalized"] = combined["stat"].astype(str).apply(_normalize_stat)

        # Coerce numeric
        combined["line"] = pd.to_numeric(combined["line"], errors="coerce")

        # Gate: Timestamp freshness
        # prefer explicit field if present, else use now
        # Force UTC parsing to keep comparisons sane.
        combined["scraped_at"] = pd.to_datetime(
            combined.get("scraped_at", _utc_now().isoformat()),
            errors="coerce",
            utc=True,
        )
        oldest = combined["scraped_at"].min()
        if pd.notna(oldest):
            age = _utc_now() - oldest.to_pydatetime()
            if age > timedelta(hours=self.config.max_age_hours):
                raise RuntimeError(f"Data is stale: oldest scrape {oldest} (age {age})")

        # Gate: Rationality bounds
        bad_bounds = []
        for stat, (lo, hi) in self.bounds.items():
            s = combined[combined["stat_normalized"] == stat]
            if s.empty:
                continue
            bad = s[(s["line"].isna()) | (s["line"] < lo) | (s["line"] > hi)]
            if not bad.empty:
                bad_bounds.append((stat, bad[["platform", "player_normalized", "line"]].head(10).to_dict("records")))

        if bad_bounds:
            raise RuntimeError(f"Line rationality check failed for stats: {[s for s, _ in bad_bounds]}")

        # Gate: Cross-platform line agreement
        discrepancies = []
        grouped = combined.groupby(["player_normalized", "stat_normalized"], dropna=False)  # type: ignore
        for (player, stat), grp in grouped:  # type: ignore
            if grp["platform"].nunique() < 2:
                continue
            lines = grp["line"].dropna().astype(float).to_numpy()
            if len(lines) < 2:
                continue
            tol = self.tolerance_thresholds.get(str(stat), 1.0)
            spread = float(lines.max() - lines.min())
            if spread > tol:
                discrepancies.append(
                    {
                        "player": player,
                        "stat": stat,
                        "spread": spread,
                        "tolerance": tol,
                        "lines": grp[["platform", "line"]].to_dict(orient="records"),  # type: ignore
                    }
                )

        if discrepancies and self.config.fail_on_discrepancy and not self.config.allow_discrepancies:
            raise RuntimeError(f"Cross-platform discrepancies found: {len(discrepancies)} groups")

        summary = {
            "generated_at_utc": _utc_now().isoformat(),
            "platforms": sorted(list(file_paths.keys())),
            "total_rows": int(len(combined)),
            "players": int(combined["player_normalized"].nunique()),
            "stats": sorted(combined["stat_normalized"].dropna().unique().tolist()),
            "discrepancy_groups": int(len(discrepancies)),
            "discrepancies": discrepancies[:200],
            "source_files": {k: v.name for k, v in file_paths.items()},
            "metadata": meta,
        }

        return combined, summary


def _latest_files(scrape_dir: Path, sport: str, platforms: Optional[List[str]] = None) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    allow = [p.strip().lower() for p in (platforms or []) if p.strip()]
    candidates = ["draftkings", "prizepicks", "underdog", "oddsapi"]
    if allow:
        candidates = [p for p in candidates if p in allow]

    for platform in candidates:
        files = sorted(scrape_dir.glob(f"raw_props_{platform}_{sport}_*.json"))
        if files:
            out[platform] = files[-1]
    return out


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Validate scraped props (Gate)")
    p.add_argument("--sport", default="NBA")
    p.add_argument("--scrape-dir", default="./data/raw/scraped")
    p.add_argument("--out-dir", default="./data/processed")
    p.add_argument("--allow-discrepancies", action="store_true")
    p.add_argument(
        "--platforms",
        default="",
        help="Comma-separated platform allowlist (e.g. 'oddsapi' or 'draftkings,prizepicks,underdog').",
    )

    args = p.parse_args(argv)

    scrape_dir = Path(args.scrape_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    platforms = [x.strip().lower() for x in str(args.platforms or "").split(",") if x.strip()]
    files = _latest_files(scrape_dir, args.sport, platforms=platforms or None)
    if not files:
        raise SystemExit("No scraped data found. Run the scraper first.")

    cfg = ValidationConfig(
        require_platforms=1,
        max_age_hours=2.0,
        fail_on_discrepancy=True,
        allow_discrepancies=bool(args.allow_discrepancies),
    )

    validator = ScrapedDataValidator(cfg)
    df, summary = validator.validate_scrape_batch(files)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    parquet_path = out_dir / f"validated_props_{args.sport}_{ts}.parquet"
    df.to_parquet(parquet_path, index=False)
    _write_sha256_sidecar(parquet_path)

    summary_path = out_dir / f"validated_props_{args.sport}_{ts}.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_sha256_sidecar(summary_path)

    print(f"✅ Validation complete: {parquet_path}")
    print(f"  Summary: {summary_path}")
    print(f"  Rows: {len(df)} | Players: {df['player_normalized'].nunique()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
