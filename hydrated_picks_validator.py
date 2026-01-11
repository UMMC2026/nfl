"""Hydration-time data quality checks for hydrated picks.

This module validates picks loaded from picks_hydrated.json before they are
used to generate cheatsheets or feed learning. It focuses on simple,
transparent rules:
  - Team abbreviation is valid
  - mu is within a reasonable range for the stat type
  - sigma is non-negative and not absurdly large
  - Required fields are present

Invalid picks are written to a timestamped invalid_picks_*.json file and
excluded from downstream processing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

try:
    # Optional Ollama integration for additional context on
    # already-suspicious rows. This is advisory only and fully
    # disabled if the module is missing or the env flag is off.
    from ollama.data_validator import validate_pick_with_ollama
except Exception:  # noqa: BLE001
    validate_pick_with_ollama = None  # type: ignore[assignment]


NBA_TEAMS = {
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
}


@dataclass
class ValidationConfig:
    """Configuration for hydration validation thresholds."""

    # Reasonable ranges for primary stat types, on a per-game basis
    reasonable_ranges: Dict[str, Dict[str, float]] = None
    max_sigma: float = 20.0  # anything above this is flagged as extreme

    def __post_init__(self) -> None:
        if self.reasonable_ranges is None:
            self.reasonable_ranges = {
                "points": {"min": 0, "max": 50},
                "rebounds": {"min": 0, "max": 25},
                "assists": {"min": 0, "max": 15},
                "pts+reb+ast": {"min": 0, "max": 80},
                "pra": {"min": 0, "max": 80},
                "3pm": {"min": 0, "max": 12},
            }


class HydrationValidator:
    """Validate hydrated picks for basic data integrity.

    The goal is not to be perfect, but to cheaply catch obviously broken
    entries so they do not surface as headline edges or enter learning.
    """

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()
        # Gate Ollama usage behind an environment flag so production
        # behavior is unchanged by default. When enabled, we will only
        # call Ollama for rows that already look suspicious according
        # to the lightweight rules below, and we cap the number of
        # calls per run to keep latency bounded.
        self._ollama_enabled = (
            bool(int(os.getenv("OLLAMA_HYDRATION_ENABLED", "0")))
            and validate_pick_with_ollama is not None
        )
        self._ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
        self._ollama_max_calls = int(os.getenv("OLLAMA_HYDRATION_MAX_CALLS", "32"))
        self._ollama_calls = 0

    def validate_pick(self, pick: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of pick annotated with validation flags."""

        validated = dict(pick)
        issues: List[str] = []

        # 1. Team abbreviation sanity
        team = str(pick.get("team", "")).upper()
        if team and team not in NBA_TEAMS:
            issues.append(f"invalid_team:{team}")
            validated["validation_team_invalid"] = True

        # 2. Stat-type specific mu range
        stat = str(pick.get("stat", "")).lower()
        mu = pick.get("mu")
        if stat in self.config.reasonable_ranges and isinstance(mu, (int, float)):
            rng = self.config.reasonable_ranges[stat]
            if not (rng["min"] <= float(mu) <= rng["max"]):
                issues.append(f"mu_out_of_range:{mu}")
                validated["validation_mu_unreasonable"] = True

        # 3. Sigma sanity
        sigma = pick.get("sigma")
        if isinstance(sigma, (int, float)):
            if sigma < 0:
                issues.append(f"sigma_negative:{sigma}")
                validated["validation_sigma_invalid"] = True
            elif sigma > self.config.max_sigma:
                issues.append(f"sigma_extreme:{sigma}")
                validated["validation_sigma_high_volatility"] = True

        # 4. Required core fields
        for field in ("player", "stat", "line", "direction"):
            if pick.get(field) in (None, ""):
                issues.append(f"missing_{field}")
                validated[f"validation_missing_{field}"] = True

        # 5. Optional staleness check if timestamp is present
        ts_raw = pick.get("last_updated") or pick.get("hydrated_at")
        if ts_raw:
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                if datetime.now(ts.tzinfo or None) - ts > timedelta(days=3):
                    issues.append("stale_data")
                    validated["validation_stale"] = True
            except Exception:
                # If timestamp is malformed, we simply log it as an issue
                issues.append("invalid_timestamp")
                validated["validation_invalid_timestamp"] = True

        if issues:
            # Optionally enrich clearly suspicious rows with an
            # Ollama-based sanity check. This does NOT override the
            # local validation result; it only adds context that can
            # be inspected in the invalid_picks_*.json artifact.
            if (
                self._ollama_enabled
                and self._ollama_calls < self._ollama_max_calls
                and validate_pick_with_ollama is not None
            ):
                self._ollama_calls += 1
                ollama_result = validate_pick_with_ollama(
                    pick,
                    model=self._ollama_model,
                )
                validated["ollama_validation"] = ollama_result

            validated["validation_passed"] = False
            validated["validation_issues"] = issues
            validated["validation_checked_at"] = datetime.now().isoformat()
        else:
            validated["validation_passed"] = True

        return validated

    def filter_valid_picks(self, picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return only picks that pass validation, logging invalid ones."""

        valid: List[Dict[str, Any]] = []
        invalid: List[Dict[str, Any]] = []

        for pick in picks:
            v = self.validate_pick(pick)
            if v.get("validation_passed"):
                valid.append(v)
            else:
                invalid.append(v)

        if invalid:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = Path(f"invalid_picks_{stamp}.json")
            out.write_text(json.dumps(invalid, indent=2), encoding="utf-8")
            print(f"⚠️  HydrationValidator filtered out {len(invalid)} invalid picks → {out}")

        return valid
