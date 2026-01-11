"""Ollama-backed data validation helpers for hydrated picks.

This module keeps all Ollama interaction in one place so that the
core pipeline can depend on a small, well-behaved surface area.

Usage:
    from ollama.data_validator import validate_pick_with_ollama

    result = validate_pick_with_ollama(pick)

    # result is a dict containing parsed JSON (if any) plus raw text
    # and error metadata. Callers should treat this as advisory only
    # and NEVER as ground truth.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional


def _build_prompt(pick: Dict[str, Any]) -> str:
    """Build a constrained prompt asking for JSON-only assessment.

    We ask Ollama to sanity-check the stats and team for a single pick
    and to respond with a tiny JSON object. Callers are expected to
    treat this as advisory only.
    """

    player = pick.get("player")
    stat = pick.get("stat")
    line = pick.get("line")
    mu = pick.get("mu")
    sigma = pick.get("sigma")
    team = pick.get("team")

    prompt = f"""
You are checking NBA prop data for obvious mistakes.

Input data (one pick):
  player: {player}
  team: {team}
  stat: {stat}
  line: {line}
  reported_average: {mu}
  reported_std_dev: {sigma}

Tasks:
  1. Decide if these numbers look broadly reasonable for this player and stat.
  2. If you are confident the team abbreviation is wrong, provide a corrected team.

Respond with JSON ONLY, no explanation, in this exact schema:
{{
  "is_reasonable": true or false,
  "correct_team": "3-letter team abbreviation if you are confident, otherwise null",
  "notes": "very short reason (max 140 characters)"
}}
""".strip()

    return prompt


def validate_pick_with_ollama(
    pick: Dict[str, Any],
    *,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Run an Ollama sanity check on a hydrated pick.

    This helper is deliberately defensive:
      - If Ollama is not installed or returns non-JSON, we record an error
        and return a best-effort structure instead of raising.
      - Callers should NEVER treat the result as ground truth. At most,
        use it to add context or to *further* scrutinize already-suspicious
        rows.
    """

    model = model or os.getenv("OLLAMA_MODEL", "llama3")
    timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT", "15"))

    prompt = _build_prompt(pick)

    result: Dict[str, Any] = {
        "ollama_model": model,
        "ollama_raw": None,
        "ollama_parsed": None,
        "ollama_error": None,
    }

    try:
        proc = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        output = (proc.stdout or "").strip()
        result["ollama_raw"] = output

        # Best-effort JSON parse. If the model ever wraps JSON in
        # markdown fences, strip them out first.
        text = output.strip()
        if text.startswith("```"):
            # drop first fence and language tag, then trailing fence
            parts = text.split("```", 2)
            if len(parts) == 3:
                text = parts[1].strip() or parts[2].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                result["ollama_parsed"] = parsed
            else:
                result["ollama_error"] = "non_dict_json"
        except Exception as e:  # noqa: BLE001
            result["ollama_error"] = f"json_parse_error:{type(e).__name__}"

    except subprocess.TimeoutExpired:
        result["ollama_error"] = "timeout"
    except FileNotFoundError:
        # Ollama not installed or not on PATH.
        result["ollama_error"] = "not_installed"
    except Exception as e:  # noqa: BLE001
        result["ollama_error"] = f"unexpected:{type(e).__name__}:{e}"

    return result
