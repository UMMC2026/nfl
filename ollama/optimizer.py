"""Production-oriented Ollama helper with basic caching and batching.

This module is optional and is NOT wired into the core pipeline by
default. It is intended for offline / manual validation tasks where
slightly higher latency is acceptable but we want to avoid paying for
repeat prompts.

Example usage:

    from ollama.optimizer import OllamaOptimizer
    import json

    picks = json.load(open("picks_hydrated.json", encoding="utf-8"))[:10]
    opt = OllamaOptimizer(model="tinyllama")
    validated = opt.batch_validate_picks(picks, max_workers=3)

    json.dump(validated, open("ollama_validated.json", "w", encoding="utf-8"), indent=2)

This keeps all the heavier / more experimental logic isolated from the
thin, synchronous validator used in the main pipeline.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class CacheConfig:
    ttl: timedelta = timedelta(hours=24)
    dir: Path = Path("cache/ollama")


class OllamaOptimizer:
    """Optimized Ollama integration with simple SQLite-backed cache.

    Notes:
      - This is best-effort only; cache failures never stop validation.
      - Designed for small batches (tens of picks), not huge jobs.
    """

    def __init__(
        self,
        model: str = "tinyllama",
        cache_ttl_hours: int = 24,
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.model = model
        self.cache_cfg = CacheConfig(
            ttl=timedelta(hours=cache_ttl_hours),
            dir=cache_dir or Path("cache/ollama"),
        )
        self.cache_cfg.dir.mkdir(parents=True, exist_ok=True)
        self.cache_db = self.cache_cfg.dir / "ollama_cache.db"
        self._init_cache_db()

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _init_cache_db(self) -> None:
        try:
            conn = sqlite3.connect(self.cache_db)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    query_hash TEXT PRIMARY KEY,
                    response   TEXT,
                    model      TEXT,
                    created_at TEXT,
                    expires_at TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _cache_key(self, prompt: str) -> str:
        return md5(f"{self.model}:{prompt}".encode("utf-8")).hexdigest()

    def _get_cached_response(self, prompt: str) -> Optional[str]:
        key = self._cache_key(prompt)
        try:
            conn = sqlite3.connect(self.cache_db)
            cur = conn.cursor()
            cur.execute(
                "SELECT response, expires_at FROM cache WHERE query_hash = ?",
                (key,),
            )
            row = cur.fetchone()
        except Exception:
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not row:
            return None

        response, expires_at = row
        try:
            if datetime.fromisoformat(expires_at) <= datetime.now():
                return None
        except Exception:
            # If parsing fails, treat as expired but keep row.
            return None
        return response

    def _cache_response(self, prompt: str, response: str) -> None:
        key = self._cache_key(prompt)
        expires_at = datetime.now() + self.cache_cfg.ttl
        try:
            conn = sqlite3.connect(self.cache_db)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO cache (
                    query_hash, response, model, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key,
                    response,
                    self.model,
                    datetime.now().isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()
        except Exception:
            # Cache write failures are non-fatal.
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Core Ollama query + parsing
    # ------------------------------------------------------------------

    def query_ollama(
        self,
        prompt: str,
        *,
        timeout: int = 10,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Query Ollama with optional caching.

        Returns raw text response or None on failure/timeout.
        """

        if use_cache:
            cached = self._get_cached_response(prompt)
            if cached is not None:
                print(f"📦 Ollama cache hit ({self.model}): {prompt[:48]}…")
                return cached

        try:
            start = time.time()
            proc = subprocess.run(
                ["ollama", "run", self.model],
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
            )
            elapsed = time.time() - start
            out = (proc.stdout or "").strip()
            if out:
                print(f"⚡ Ollama ({self.model}) responded in {elapsed:.1f}s")
                if use_cache:
                    self._cache_response(prompt, out)
                return out
        except subprocess.TimeoutExpired:
            print(f"⏰ Ollama ({self.model}) timeout after {timeout}s")
        except FileNotFoundError:
            print("❌ Ollama binary not found on PATH")
        except Exception as e:  # noqa: BLE001
            print(f"❌ Ollama ({self.model}) error: {e}")

        return None

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _build_validation_prompt(self, pick: Dict[str, Any]) -> str:
        player = pick.get("player")
        stat = pick.get("stat")
        mu = pick.get("mu")
        team = pick.get("team", "UNKNOWN")

        return f"""
NBA data check (answer JSON only).

Player: {player}
Stat: {stat}
Reported average: {mu}
Team: {team}

Tasks:
  1. Tell me if this average looks roughly reasonable for this player.
  2. If the team code looks wrong, provide the corrected team abbreviation.

Respond with a single JSON object ONLY in this schema:
{{
  "reasonable": true or false,
  "correct_team": "3-letter team code or null",
  "confidence": "high" | "medium" | "low"
}}
""".strip()

    def _extract_json_dict(self, text: str) -> Optional[Dict[str, Any]]:
        """Best-effort extraction of a JSON object from model output."""

        text = text.strip()
        if not text:
            return None

        # Strip Markdown fences if present.
        if text.startswith("```"):
            parts = text.split("```", 2)
            if len(parts) == 3:
                # middle part may contain language tag; use the tail.
                candidate = parts[1].strip()
                if candidate.startswith("{"):
                    text = candidate
                else:
                    text = parts[2].strip()

        # First try plain JSON load.
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # Fallback: find the first {...} block.
        import re

        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def validate_pick(
        self,
        pick: Dict[str, Any],
        *,
        timeout: int = 8,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Validate a single pick with an Ollama-backed prompt.

        Returns a copy of the pick enriched with advisory fields:
          - ollama_validated: bool
          - is_reasonable: bool
          - correct_team: Optional[str]
          - validation_confidence: str
          - ollama_snippet: Optional[str]
          - validation_error: Optional[str]
        """

        prompt = self._build_validation_prompt(pick)
        raw = self.query_ollama(prompt, timeout=timeout, use_cache=use_cache)

        enriched: Dict[str, Any] = dict(pick)
        if raw is None:
            enriched.update(
                {
                    "ollama_validated": False,
                    "is_reasonable": True,
                    "correct_team": None,
                    "validation_confidence": "low",
                    "ollama_snippet": None,
                    "validation_error": "no_response",
                }
            )
            return enriched

        parsed = self._extract_json_dict(raw)
        if parsed is None:
            enriched.update(
                {
                    "ollama_validated": False,
                    "is_reasonable": True,
                    "correct_team": None,
                    "validation_confidence": "low",
                    "ollama_snippet": raw[:120] + ("..." if len(raw) > 120 else ""),
                    "validation_error": "parse_failed",
                }
            )
            return enriched

        enriched.update(
            {
                "ollama_validated": True,
                "is_reasonable": bool(parsed.get("reasonable", True)),
                "correct_team": parsed.get("correct_team"),
                "validation_confidence": parsed.get("confidence", "low"),
                "ollama_snippet": raw[:120] + ("..." if len(raw) > 120 else ""),
                "validation_error": None,
            }
        )
        return enriched

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def batch_validate_picks(
        self,
        picks: Iterable[Dict[str, Any]],
        *,
        max_workers: int = 3,
        timeout_per_pick: int = 8,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Validate multiple picks in parallel using a thread pool.

        Returns a list of enriched pick dicts. Order is preserved.
        """

        picks_list = list(picks)
        results: List[Optional[Dict[str, Any]]] = [None] * len(picks_list)

        def _task(idx: int, p: Dict[str, Any]) -> None:
            try:
                results[idx] = self.validate_pick(
                    p,
                    timeout=timeout_per_pick,
                    use_cache=use_cache,
                )
            except Exception as e:  # noqa: BLE001
                enriched = dict(p)
                enriched.update(
                    {
                        "ollama_validated": False,
                        "is_reasonable": True,
                        "correct_team": None,
                        "validation_confidence": "low",
                        "ollama_snippet": None,
                        "validation_error": f"exception:{type(e).__name__}",
                    }
                )
                results[idx] = enriched

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_task, i, p) for i, p in enumerate(picks_list)]
            for _ in as_completed(futures):
                # We don't need per-future result; _task populates `results`.
                pass

        # Replace any still-None entries with the original pick.
        final: List[Dict[str, Any]] = []
        for original, res in zip(picks_list, results):
            final.append(res or original)
        return final
