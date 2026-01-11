"""Production-Optimized Ollama Validator
Fast, reliable, non-blocking validation for NBA prop system
"""

import os
import json
import time
import sqlite3
import threading
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import logging
from enum import Enum

# Configure logging (sanitize output for Windows consoles)
Path("logs/ollama").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/ollama/production.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    VALID = "valid"
    QUESTIONABLE = "questionable"
    INVALID = "invalid"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of Ollama validation"""

    player: str
    stat_type: str
    reported_value: float
    validation_status: ValidationStatus
    confidence: float  # 0.0 to 1.0
    corrected_value: Optional[float] = None
    corrected_team: Optional[str] = None
    reasoning: Optional[str] = None
    response_time_ms: Optional[int] = None
    model_used: Optional[str] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""

        data = asdict(self)
        data["validation_status"] = self.validation_status.value
        if self.timestamp:
            data["timestamp"] = self.timestamp.isoformat()
        return data


class OllamaProductionValidator:
    """Production-grade validator with caching, batching and health checks."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        model: str = "mistral",
        max_workers: int = 4,
        cache_ttl_hours: int = 24,
    ) -> None:
        # Load configuration
        if config_path is None:
            config_path = Path("config/ollama/config.json")
        self.config = self._load_config(config_path)

        # Model configuration
        # Default to a model that is likely already pulled (adjustable via env/config)
        self.model = model
        self.fallback_model = "mistral"
        self.max_workers = max_workers
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # Connection pool
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_connections = 0
        self.max_connections = max_workers * 2

        # Cache setup
        self.cache_dir = Path("cache/ollama")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_db = self.cache_dir / "validation_cache.db"
        self._init_cache_db()

        # Performance tracking
        self.metrics: Dict[str, Any] = {
            "total_requests": 0,
            "cache_hits": 0,
            "timeouts": 0,
            "avg_response_time_ms": 0,
        }

        # Pre-loaded knowledge base (common players)
        self.knowledge_base = self._load_knowledge_base()

        # Background health monitor
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitor,
            daemon=True,
            name="OllamaHealthMonitor",
        )
        self.health_monitor_thread.start()

        logger.info("Ollama Production Validator initialized with model: %s", model)
        logger.info("Cache TTL: %sh, Max workers: %s", cache_ttl_hours, max_workers)

    # ==================== PUBLIC API ====================

    def validate_pick_sync(self, pick: Dict[str, Any], timeout: int = 5) -> ValidationResult:
        """Synchronous validation - returns within timeout or defaults."""

        start_time = time.time()
        try:
            cache_key = self._generate_cache_key(pick)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self.metrics["cache_hits"] += 1
                cached_result.response_time_ms = int((time.time() - start_time) * 1000)
                return cached_result

            kb_result = self._check_knowledge_base(pick)
            if kb_result:
                self._save_to_cache(cache_key, kb_result)
                kb_result.response_time_ms = int((time.time() - start_time) * 1000)
                return kb_result

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._query_ollama_detailed, pick)
                try:
                    ollama_response = future.result(timeout=timeout)
                    response_time = int((time.time() - start_time) * 1000)

                    validation_result = self._parse_ollama_response(pick, ollama_response)
                    validation_result.response_time_ms = response_time
                    validation_result.model_used = self.model
                    validation_result.timestamp = datetime.now()

                    self._save_to_cache(cache_key, validation_result)
                    self._update_metrics(success=True, response_time=response_time)
                    return validation_result
                except TimeoutError:
                    logger.warning("Ollama timeout for %s", pick.get("player", "Unknown"))
                    self.metrics["timeouts"] += 1
                    return self._create_timeout_result(pick)
        except Exception as e:  # noqa: BLE001
            logger.error("Validation error for %s: %s", pick.get("player", "Unknown"), e)
            return self._create_error_result(pick, str(e))
        finally:
            self.metrics["total_requests"] += 1

    async def validate_pick_async(self, pick: Dict[str, Any]) -> ValidationResult:
        """Asynchronous validation - for batch processing."""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, lambda: self.validate_pick_sync(pick, timeout=7))

    def validate_batch(
        self,
        picks: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None,
    ) -> List[ValidationResult]:
        """Validate multiple picks in parallel."""

        if max_concurrent is None:
            max_concurrent = self.max_workers

        results: List[ValidationResult] = []
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_pick = {
                executor.submit(
                    self.validate_pick_sync,
                    pick,
                    timeout=self.config["timeouts"].get("detailed", 15),
                ): pick
                for pick in picks
            }
            for future in as_completed(future_to_pick):
                pick = future_to_pick[future]
                try:
                    # Allow enough time per pick, aligned with detailed timeout
                    result = future.result(timeout=self.config["timeouts"].get("detailed", 15) + 2)
                    results.append(result)
                except Exception as e:  # noqa: BLE001
                    logger.error("Batch validation failed for %s: %s", pick.get("player"), e)
                    results.append(self._create_error_result(pick, str(e)))
        return results

    def quick_validate(self, pick: Dict[str, Any]) -> Tuple[bool, str]:
        """Ultra-fast validation (under a couple seconds)."""

        if self._has_obvious_issue(pick):
            return False, pick.get("team", "UNK")

        kb_result = self._check_knowledge_base(pick)
        if kb_result and kb_result.validation_status == ValidationStatus.INVALID:
            return False, kb_result.corrected_team or pick.get("team", "UNK")

        try:
            prompt = self._generate_quick_prompt(pick)
            result = subprocess.run(
                ["ollama", "run", self.fallback_model, prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config["timeouts"]["quick"],
            )
            if "unreasonable" in result.stdout.lower() or "invalid" in result.stdout.lower():
                return False, pick.get("team", "UNK")
        except Exception:  # noqa: BLE001
            pass

        return True, pick.get("team", "UNK")

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""

        total = self.metrics["total_requests"] or 1
        success_rate = ((total - self.metrics["timeouts"]) / total) * 100
        cache_hit_rate = (self.metrics["cache_hits"] / total) * 100

        return {
            **self.metrics,
            "success_rate_percent": round(success_rate, 1),
            "cache_hit_rate_percent": round(cache_hit_rate, 1),
            "active_connections": self.active_connections,
            "model": self.model,
            "cache_size_mb": self._get_cache_size_mb(),
            "cache_entries": self._get_cache_count(),
        }

    def warmup_cache(self, common_players: Optional[List[str]] = None) -> None:
        """Warm up cache with common players in the background."""

        if common_players is None:
            common_players = [
                "Jonas Valanciunas",
                "Giannis Antetokounmpo",
                "Joel Embiid",
                "Nikola Jokic",
                "Stephen Curry",
                "LeBron James",
            ]

        logger.info("Warming up cache with %d players", len(common_players))

        warmup_picks = [
            {"player": p, "stat": "points", "mu": 15.0, "team": "UNK"}
            for p in common_players
        ]

        threading.Thread(
            target=self.validate_batch,
            args=(warmup_picks[:3], 2),
            daemon=True,
            name="CacheWarmup",
        ).start()

    # ==================== PRIVATE METHODS ====================

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load or create configuration."""

        default_config: Dict[str, Any] = {
            "timeouts": {"quick": 2, "standard": 5, "detailed": 8},
            "models": {
                "quick": "tinyllama:1.1b-chat-q4_0",
                "standard": "phi:2.7b-q4_0",
                "detailed": "mistral:7b-instruct-q4_0",
            },
            "cache": {"enabled": True, "ttl_hours": 24, "max_size_mb": 100},
            "validation": {
                "require_min_confidence": 0.6,
                "auto_correct_teams": True,
                "log_all_validations": False,
            },
        }

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config = json.loads(json.dumps(default_config))
            self._deep_merge(config, user_config)
            return config

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        return default_config

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _init_cache_db(self) -> None:
        conn = sqlite3.connect(self.cache_db)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_cache (
                cache_key TEXT PRIMARY KEY,
                player TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                validation_result TEXT NOT NULL,
                model_used TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """CREATE INDEX IF NOT EXISTS idx_player_stat
            ON validation_cache(player, stat_type)"""
        )
        cur.execute(
            """CREATE INDEX IF NOT EXISTS idx_expires
            ON validation_cache(expires_at)"""
        )
        conn.commit()
        conn.close()

    def _load_knowledge_base(self) -> Dict[str, Any]:
        kb_path = Path("config/ollama/knowledge_base.json")
        if kb_path.exists():
            with open(kb_path, "r", encoding="utf-8") as f:
                return json.load(f)

        default_kb: Dict[str, Any] = {
            "players": {
                "Jonas Valanciunas": {
                    "team": "NOP",
                    "stats": {
                        "points": {"avg": 16.5, "min": 10, "max": 25},
                        "rebounds": {"avg": 10.8, "min": 6, "max": 16},
                        "assists": {"avg": 3.2, "min": 1, "max": 6},
                    },
                },
                "Giannis Antetokounmpo": {
                    "team": "MIL",
                    "stats": {
                        "points": {"avg": 31.5, "min": 20, "max": 45},
                        "rebounds": {"avg": 11.7, "min": 8, "max": 16},
                        "assists": {"avg": 9.1, "min": 5, "max": 13},
                    },
                },
            }
        }
        kb_path.parent.mkdir(parents=True, exist_ok=True)
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(default_kb, f, indent=2)
        return default_kb

    def _generate_cache_key(self, pick: Dict[str, Any]) -> str:
        key_parts = [
            pick.get("player", ""),
            pick.get("stat", ""),
            str(pick.get("mu", "")),
            str(pick.get("team", "")),
        ]
        key_string = "_".join(key_parts)
        return hashlib.md5(key_string.encode("utf-8")).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[ValidationResult]:
        if not self.config["cache"]["enabled"]:
            return None

        conn = sqlite3.connect(self.cache_db)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT validation_result, model_used
            FROM validation_cache
            WHERE cache_key = ? AND expires_at > datetime('now')
            """,
            (cache_key,),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE validation_cache SET access_count = access_count + 1 WHERE cache_key = ?",
                (cache_key,),
            )
            conn.commit()
        conn.close()

        if not row:
            return None

        validation_json, model_used = row
        validation_dict = json.loads(validation_json)
        return ValidationResult(
            player=validation_dict.get("player", ""),
            stat_type=validation_dict.get("stat_type", ""),
            reported_value=validation_dict.get("reported_value", 0),
            validation_status=ValidationStatus(validation_dict.get("validation_status")),
            confidence=validation_dict.get("confidence", 0.5),
            corrected_value=validation_dict.get("corrected_value"),
            corrected_team=validation_dict.get("corrected_team"),
            reasoning=validation_dict.get("reasoning"),
            model_used=model_used,
        )

    def _save_to_cache(self, cache_key: str, result: ValidationResult) -> None:
        if not self.config["cache"]["enabled"]:
            return
        expires_at = datetime.now() + self.cache_ttl
        conn = sqlite3.connect(self.cache_db)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO validation_cache
            (cache_key, player, stat_type, validation_result, model_used, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                result.player,
                result.stat_type,
                json.dumps(result.to_dict()),
                result.model_used,
                expires_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def _check_knowledge_base(self, pick: Dict[str, Any]) -> Optional[ValidationResult]:
        player_name = pick.get("player", "")
        stat_type = pick.get("stat", "")
        reported_value = pick.get("mu")
        reported_team = pick.get("team", "UNK")

        players = self.knowledge_base.get("players", {})
        if player_name not in players:
            return None

        player_data = players[player_name]
        correct_team = player_data.get("team", reported_team)
        team_correct = reported_team == correct_team or reported_team == "UNK"

        stats = player_data.get("stats", {})
        if stat_type in stats and reported_value is not None:
            stat_range = stats[stat_type]
            min_val = stat_range.get("min", 0)
            max_val = stat_range.get("max", 100)
            avg_val = stat_range.get("avg", (min_val + max_val) / 2)

            if reported_value < min_val or reported_value > max_val:
                return ValidationResult(
                    player=player_name,
                    stat_type=stat_type,
                    reported_value=reported_value,
                    validation_status=ValidationStatus.INVALID,
                    confidence=0.9,
                    corrected_value=avg_val,
                    corrected_team=None if team_correct else correct_team,
                    reasoning=f"Value outside expected range [{min_val}-{max_val}]",
                )
            if abs(reported_value - avg_val) > (max_val - min_val) * 0.3:
                return ValidationResult(
                    player=player_name,
                    stat_type=stat_type,
                    reported_value=reported_value,
                    validation_status=ValidationStatus.QUESTIONABLE,
                    confidence=0.7,
                    corrected_value=avg_val,
                    corrected_team=None if team_correct else correct_team,
                    reasoning=f"Value differs significantly from expected average {avg_val}",
                )

        if not team_correct:
            return ValidationResult(
                player=player_name,
                stat_type=stat_type,
                reported_value=reported_value or 0.0,
                validation_status=ValidationStatus.QUESTIONABLE,
                confidence=0.8,
                corrected_team=correct_team,
                reasoning=f"Team should be {correct_team}, not {reported_team}",
            )
        return None

    def _query_ollama_detailed(self, pick: Dict[str, Any]) -> str:
        prompt = self._generate_detailed_prompt(pick)
        try:
            self.active_connections += 1
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config["timeouts"]["detailed"],
            )
            if result.returncode == 0:
                return (result.stdout or "").strip()
            # Sanitize stderr so Windows consoles don't choke on spinner/braille chars
            safe_err = (result.stderr or "").encode("ascii", "backslashreplace").decode("ascii")
            logger.error("Ollama error: %s", safe_err)
            return ""
        except subprocess.TimeoutExpired:
            logger.warning("Ollama timeout for %s", pick.get("player"))
            return "timeout"
        finally:
            self.active_connections -= 1

    def _generate_quick_prompt(self, pick: Dict[str, Any]) -> str:
        return f"""
Quick NBA validation (answer yes/no):
Player: {pick.get('player')}
Stat: {pick.get('stat')}
Average: {pick.get('mu')}
Team: {pick.get('team', 'unknown')}

Is this reasonable? Answer: yes or no
""".strip()

    def _generate_detailed_prompt(self, pick: Dict[str, Any]) -> str:
        return f"""
You are an NBA data validation expert. Analyze this player data:

Player: {pick.get('player')}
Position: {pick.get('position', 'unknown')}
Team: {pick.get('team', 'unknown')}
Statistic: {pick.get('stat')}
Reported Average: {pick.get('mu')}
Standard Deviation: {pick.get('sigma', 'unknown')}

Please validate:
1. Is the team correct for the 2025-26 season?
2. Is the reported average reasonable for this player?
3. If not reasonable, what would be a reasonable average?
4. Confidence level in your assessment (high/medium/low)

Return JSON format:
{{
  "team_correct": true/false,
  "correct_team": "XXX" (if team_correct is false),
  "average_reasonable": true/false,
  "reasonable_average": number (if average_reasonable is false),
  "confidence": "high/medium/low",
  "reasoning": "brief explanation"
}}
""".strip()

    def _parse_ollama_response(self, pick: Dict[str, Any], response: str) -> ValidationResult:
        if not response or response == "timeout":
            return self._create_timeout_result(pick)

        try:
            import re

            m = re.search(r"\{.*\}", response, re.DOTALL)
            if not m:
                raise ValueError("no JSON block found")
            data = json.loads(m.group(0))

            if data.get("average_reasonable", True) and data.get("team_correct", True):
                status = ValidationStatus.VALID
            elif not data.get("average_reasonable", True):
                status = ValidationStatus.INVALID
            else:
                status = ValidationStatus.QUESTIONABLE

            confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            confidence = confidence_map.get(data.get("confidence", "low"), 0.5)

            return ValidationResult(
                player=pick.get("player", ""),
                stat_type=pick.get("stat", ""),
                reported_value=pick.get("mu", 0.0),
                validation_status=status,
                confidence=confidence,
                corrected_value=data.get("reasonable_average"),
                corrected_team=data.get("correct_team"),
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to parse Ollama response: %s", e)
            return ValidationResult(
                player=pick.get("player", ""),
                stat_type=pick.get("stat", ""),
                reported_value=pick.get("mu", 0.0),
                validation_status=ValidationStatus.QUESTIONABLE,
                confidence=0.5,
                reasoning="Could not parse Ollama response",
            )

    def _has_obvious_issue(self, pick: Dict[str, Any]) -> bool:
        mu = pick.get("mu")
        if mu is None:
            return False
        stat_type = pick.get("stat", "")
        ranges = {
            "points": (0, 60),
            "rebounds": (0, 25),
            "assists": (0, 15),
            "pts+reb+ast": (0, 80),
        }
        for name, (min_val, max_val) in ranges.items():
            if name in stat_type:
                return mu < min_val or mu > max_val
        return False

    def _create_timeout_result(self, pick: Dict[str, Any]) -> ValidationResult:
        return ValidationResult(
            player=pick.get("player", ""),
            stat_type=pick.get("stat", ""),
            reported_value=pick.get("mu", 0.0),
            validation_status=ValidationStatus.TIMEOUT,
            confidence=0.3,
            reasoning="Ollama validation timeout",
        )

    def _create_error_result(self, pick: Dict[str, Any], error: str) -> ValidationResult:
        return ValidationResult(
            player=pick.get("player", ""),
            stat_type=pick.get("stat", ""),
            reported_value=pick.get("mu", 0.0),
            validation_status=ValidationStatus.ERROR,
            confidence=0.0,
            reasoning=f"Validation error: {error}",
        )

    def _update_metrics(self, success: bool, response_time: int) -> None:
        total = self.metrics["total_requests"] or 1
        self.metrics["avg_response_time_ms"] = (
            (self.metrics["avg_response_time_ms"] * (total - 1) + response_time) / total
        )

    def _get_cache_size_mb(self) -> float:
        if self.cache_db.exists():
            return self.cache_db.stat().st_size / (1024 * 1024)
        return 0.0

    def _get_cache_count(self) -> int:
        conn = sqlite3.connect(self.cache_db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM validation_cache")
        count = cur.fetchone()[0]
        conn.close()
        return count

    def _health_monitor(self) -> None:
        while True:
            time.sleep(60)
            try:
                test = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
                if test.returncode != 0:
                    logger.warning("Ollama health check failed")
                self._cleanup_cache()
            except Exception as e:  # noqa: BLE001
                logger.error("Health monitor error: %s", e)

    def _cleanup_cache(self) -> None:
        conn = sqlite3.connect(self.cache_db)
        cur = conn.cursor()
        cur.execute("DELETE FROM validation_cache WHERE expires_at <= datetime('now')")
        deleted = cur.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            logger.info("Cleaned up %d expired cache entries", deleted)
