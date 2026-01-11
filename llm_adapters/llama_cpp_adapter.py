"""
Llama.cpp Adapter for Truth Engine Evidence Generation

Uses local Llama model via llama.cpp for deterministic, offline evidence generation.
Provides reproducible results for production safety.
"""

import subprocess
import json
import tempfile
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from pathlib import Path
from dataclasses import dataclass

# Import truth engine components
from truth_engine.evidence import EvidenceBundle, EvidenceSignal, EvidenceType, EvidenceSource

logger = logging.getLogger(__name__)


@dataclass
class LlamaConfig:
    """Configuration for llama.cpp execution."""
    model_path: str  # Path to GGUF model file
    executable_path: str = "llama-cli"  # Path to llama-cli executable
    context_size: int = 2048
    threads: int = 4
    temperature: float = 0.1
    seed: int = 42  # Fixed seed for reproducibility
    max_tokens: int = 1000


class LlamaCppAdapter:
    """
    Adapter for llama.cpp to generate evidence using local models.

    Provides deterministic, reproducible evidence generation for production safety.
    """

    def __init__(self, config: Optional[LlamaConfig] = None):
        if config is None:
            # Default configuration - expects model in standard location
            config = LlamaConfig(
                model_path=os.getenv("LLAMA_MODEL_PATH", "./models/deepseek-coder.gguf"),
                executable_path=os.getenv("LLAMA_CLI_PATH", "llama-cli"),
                seed=int(os.getenv("LLAMA_SEED", "42"))  # Deterministic seed
            )

        if not os.path.exists(config.model_path):
            raise FileNotFoundError(f"Model file not found: {config.model_path}")

        if not self._check_llama_cli(config.executable_path):
            raise RuntimeError(f"llama-cli not found or not executable: {config.executable_path}")

        self.config = config
        self.schema_path = Path(__file__).parent / "evidence_schema.json"

        # Load evidence schema for prompt construction
        with open(self.schema_path, 'r') as f:
            self.evidence_schema = json.load(f)

    def _check_llama_cli(self, executable_path: str) -> bool:
        """Check if llama-cli is available and executable."""
        try:
            result = subprocess.run(
                [executable_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def generate_evidence(self,
                         player_id: str,
                         player_name: str,
                         team: str,
                         game_context: Dict[str, Any],
                         recent_performance: List[Dict[str, Any]],
                         prompt_template: str = "default") -> Optional[EvidenceBundle]:
        """
        Generate evidence bundle using local llama.cpp model.

        Args:
            player_id: Unique player identifier
            player_name: Player's display name
            team: Team abbreviation
            game_context: Current game state
            recent_performance: Recent games data
            prompt_template: Which prompt template to use

        Returns:
            EvidenceBundle if successful, None if generation fails
        """

        try:
            # Generate structured prompt
            prompt = self._build_evidence_prompt(
                player_name, team, game_context, recent_performance, prompt_template
            )

            # Call llama.cpp
            llm_response = self._call_llama_cpp(prompt)

            # Parse and validate response
            evidence_data = self._parse_llm_response(llm_response)

            if evidence_data:
                # Convert to EvidenceBundle
                return self._create_evidence_bundle(player_id, evidence_data)
            else:
                logger.warning(f"Failed to generate valid evidence for {player_name}")
                return None

        except Exception as e:
            logger.error(f"Error generating evidence for {player_name}: {e}")
            return None

    def _build_evidence_prompt(self,
                              player_name: str,
                              team: str,
                              game_context: Dict[str, Any],
                              recent_performance: List[Dict[str, Any]],
                              template: str) -> str:
        """Build structured prompt for llama model."""

        # System prompt for consistent behavior
        system_prompt = """You are an expert NBA analyst providing evidence-based assessment for player performance projections. You must respond with valid JSON only, no additional text."""

        user_prompt = f"""
PLAYER: {player_name} ({team})
GAME CONTEXT: {json.dumps(game_context, indent=2)}
RECENT PERFORMANCE (last 5 games): {json.dumps(recent_performance, indent=2)}

Analyze this player's likely performance in the current game based on:
1. Recent statistical trends
2. Game context (quarter, score differential, pace)
3. Player's typical response to similar situations

Provide your analysis in STRICT JSON format matching this schema:
{json.dumps(self.evidence_schema, indent=2)}

CRITICAL REQUIREMENTS:
- confidence values must be between 0.0 and 1.0
- All reasoning fields must explain your analysis
- evidence_type should be "commentary" for this analysis
- timestamp should be current ISO format: {datetime.now().isoformat()}
- decay_half_life_minutes indicates how long this evidence remains relevant
- source_attribution should be "llama-cpp-local"

Focus on these key projections:
- minutes_projection: Expected minutes (0-48)
- usage_projection: Expected usage rate (0-100)
- fatigue_indicator: Fatigue level (0.0-1.0, higher = more fatigued)
- injury_concern: Boolean + confidence for injury risk

Be conservative with confidence scores - only assign >0.8 for very clear patterns.

Respond with JSON only:
"""

        # Combine system and user prompts in chat format
        full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>"

        return full_prompt

    def _call_llama_cpp(self, prompt: str) -> str:
        """Execute llama.cpp with the prompt."""

        # Create temporary file for prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Build command
            cmd = [
                self.config.executable_path,
                "-m", self.config.model_path,
                "-f", prompt_file,
                "-n", str(self.config.max_tokens),
                "-c", str(self.config.context_size),
                "-t", str(self.config.threads),
                "--temp", str(self.config.temperature),
                "-s", str(self.config.seed),  # Fixed seed for reproducibility
                "--no-display-prompt"
            ]

            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )

            if result.returncode != 0:
                logger.error(f"llama-cli failed: {result.stderr}")
                return ""

            return result.stdout.strip()

        finally:
            # Clean up temporary file
            try:
                os.unlink(prompt_file)
            except:
                pass

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse and validate LLM response from llama.cpp."""

        try:
            # Find JSON in response (llama might add extra text)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in llama response")
                return None

            json_str = response[start_idx:end_idx]
            evidence_data = json.loads(json_str)

            # Basic validation against schema
            required_fields = ["player_id", "evidence_type", "timestamp", "confidence", "signals"]
            if not all(field in evidence_data for field in required_fields):
                logger.error("Missing required fields in llama response")
                return None

            # Validate confidence ranges
            if not (0.0 <= evidence_data["confidence"] <= 1.0):
                logger.error("Invalid confidence value")
                return None

            return evidence_data

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse llama response: {e}")
            return None

    def _create_evidence_bundle(self, player_id: str, evidence_data: Dict[str, Any]) -> EvidenceBundle:
        """Convert validated evidence data to EvidenceBundle."""

        timestamp = datetime.fromisoformat(evidence_data["timestamp"])

        bundle = EvidenceBundle(
            player_id=player_id,
            evidence_type=EvidenceType.COMMENTARY,
            timestamp=timestamp,
            source_confidences={"llama-cpp": evidence_data["confidence"]}
        )

        # Add signals (same logic as DeepSeek adapter)
        signals = evidence_data.get("signals", {})

        if "minutes_projection" in signals:
            mp = signals["minutes_projection"]
            bundle.minutes_signal = EvidenceSignal(
                value=mp["value"],
                confidence=mp["confidence"],
                strength=evidence_data["confidence"],
                timestamp=timestamp,
                source=EvidenceSource.ANALYST,
                metadata={
                    "reasoning": mp.get("reasoning", ""),
                    "source": "llama-cpp-local",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        if "usage_projection" in signals:
            up = signals["usage_projection"]
            bundle.usage_signal = EvidenceSignal(
                value=up["value"],
                confidence=up["confidence"],
                strength=evidence_data["confidence"],
                timestamp=timestamp,
                source=EvidenceSource.ANALYST,
                metadata={
                    "reasoning": up.get("reasoning", ""),
                    "source": "llama-cpp-local",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        if "fatigue_indicator" in signals:
            fi = signals["fatigue_indicator"]
            bundle.fatigue_signal = EvidenceSignal(
                value=fi["value"],
                confidence=fi["confidence"],
                strength=evidence_data["confidence"],
                timestamp=timestamp,
                source=EvidenceSource.ANALYST,
                metadata={
                    "reasoning": fi.get("reasoning", ""),
                    "source": "llama-cpp-local",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        if "injury_concern" in signals:
            ic = signals["injury_concern"]
            bundle.injury_signal = EvidenceSignal(
                value=ic["value"],
                confidence=ic["confidence"],
                strength=evidence_data["confidence"],
                timestamp=timestamp,
                source=EvidenceSource.ANALYST,
                metadata={
                    "reasoning": ic.get("reasoning", ""),
                    "source": "llama-cpp-local",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        bundle.game_context = evidence_data.get("game_context", {})
        bundle.integrity_score = evidence_data["confidence"]

        return bundle


# Convenience function for quick evidence generation
def generate_player_evidence_llama(player_id: str,
                                  player_name: str,
                                  team: str,
                                  game_context: Dict[str, Any],
                                  recent_performance: List[Dict[str, Any]]) -> Optional[EvidenceBundle]:
    """
    Quick function to generate evidence using llama.cpp.

    Requires llama-cli and model file to be available.
    """

    adapter = LlamaCppAdapter()
    return adapter.generate_evidence(
        player_id, player_name, team, game_context, recent_performance
    )


if __name__ == "__main__":
    # Example usage (requires llama-cli and model)
    try:
        adapter = LlamaCppAdapter()

        test_context = {
            "quarter": 2,
            "score_differential": -3,
            "pace": "normal",
            "game_script": "close"
        }

        test_performance = [
            {"points": 28, "minutes": 35, "usage": 25},
            {"points": 32, "minutes": 38, "usage": 28},
            {"points": 25, "minutes": 33, "usage": 22}
        ]

        evidence = adapter.generate_evidence(
            "lebron_james", "LeBron James", "LAL",
            test_context, test_performance
        )

        if evidence:
            print(f"Generated evidence for {evidence.player_id}")
            print(f"Minutes projection: {evidence.minutes_signal.value if evidence.minutes_signal else 'None'}")
        else:
            print("Failed to generate evidence")

    except Exception as e:
        print(f"Setup error: {e}")
        print("Make sure llama-cli is installed and model file exists")