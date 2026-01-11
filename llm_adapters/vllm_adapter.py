"""
vLLM Adapter for Truth Engine Evidence Generation

Uses vLLM for high-throughput LLM inference with GPU acceleration.
Provides fast evidence generation for live betting scenarios.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import asyncio
from dataclasses import dataclass
import os

# Import truth engine components
from truth_engine.evidence import EvidenceBundle, EvidenceSignal, EvidenceType, EvidenceSource

logger = logging.getLogger(__name__)

try:
    from vllm import LLM, SamplingParams
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    logger.warning("vLLM not available. Install with: pip install vllm")


@dataclass
class VLLMConfig:
    """Configuration for vLLM execution."""
    model_name: str = "deepseek-ai/deepseek-coder-6.7b-instruct"
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 2048
    temperature: float = 0.1
    max_tokens: int = 1000
    seed: int = 42  # Fixed seed for reproducibility


class VLLMAdapter:
    """
    Adapter for vLLM to generate evidence with GPU acceleration.

    Optimized for high-throughput evidence generation in live scenarios.
    """

    def __init__(self, config: Optional[VLLMConfig] = None):
        if not VLLM_AVAILABLE:
            raise ImportError("vLLM not available. Install with: pip install vllm")

        if config is None:
            config = VLLMConfig(
                model_name=os.getenv("VLLM_MODEL", "deepseek-ai/deepseek-coder-6.7b-instruct"),
                seed=int(os.getenv("VLLM_SEED", "42"))
            )

        self.config = config
        self.schema_path = None  # Will be set when adapters are initialized

        # Initialize vLLM model (expensive operation)
        try:
            self.llm = LLM(
                model=self.config.model_name,
                tensor_parallel_size=self.config.tensor_parallel_size,
                gpu_memory_utilization=self.config.gpu_memory_utilization,
                max_model_len=self.config.max_model_len,
                seed=self.config.seed
            )

            # Set up sampling parameters
            self.sampling_params = SamplingParams(
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                seed=self.config.seed
            )

            logger.info(f"vLLM initialized with model: {self.config.model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize vLLM: {e}")
            raise

    def generate_evidence(self,
                         player_id: str,
                         player_name: str,
                         team: str,
                         game_context: Dict[str, Any],
                         recent_performance: List[Dict[str, Any]],
                         prompt_template: str = "default") -> Optional[EvidenceBundle]:
        """
        Generate evidence bundle using vLLM.

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

            # Call vLLM
            llm_response = self._call_vllm(prompt)

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

    def generate_evidence_batch(self,
                               players_data: List[Dict[str, Any]]) -> List[Optional[EvidenceBundle]]:
        """
        Generate evidence for multiple players in batch for efficiency.

        Args:
            players_data: List of dicts with player_id, player_name, team, game_context, recent_performance

        Returns:
            List of EvidenceBundle objects (or None for failures)
        """

        try:
            # Build prompts for all players
            prompts = []
            for player_data in players_data:
                prompt = self._build_evidence_prompt(
                    player_data["player_name"],
                    player_data["team"],
                    player_data["game_context"],
                    player_data["recent_performance"],
                    player_data.get("prompt_template", "default")
                )
                prompts.append(prompt)

            # Batch call vLLM
            llm_responses = self._call_vllm_batch(prompts)

            # Process responses
            results = []
            for i, response in enumerate(llm_responses):
                player_data = players_data[i]

                evidence_data = self._parse_llm_response(response)
                if evidence_data:
                    bundle = self._create_evidence_bundle(player_data["player_id"], evidence_data)
                    results.append(bundle)
                else:
                    logger.warning(f"Failed to generate evidence for {player_data['player_name']}")
                    results.append(None)

            return results

        except Exception as e:
            logger.error(f"Error in batch evidence generation: {e}")
            return [None] * len(players_data)

    def _build_evidence_prompt(self,
                              player_name: str,
                              team: str,
                              game_context: Dict[str, Any],
                              recent_performance: List[Dict[str, Any]],
                              template: str) -> str:
        """Build structured prompt for vLLM model."""

        import json as json_module

        # System prompt for consistent behavior
        system_prompt = """You are an expert NBA analyst providing evidence-based assessment for player performance projections. You must respond with valid JSON only, no additional text."""

        user_prompt = f"""
PLAYER: {player_name} ({team})
GAME CONTEXT: {json_module.dumps(game_context, indent=2)}
RECENT PERFORMANCE (last 5 games): {json_module.dumps(recent_performance, indent=2)}

Analyze this player's likely performance in the current game based on:
1. Recent statistical trends
2. Game context (quarter, score differential, pace)
3. Player's typical response to similar situations

Provide your analysis in STRICT JSON format with this structure:
{{
  "player_id": "will_be_set_by_system",
  "evidence_type": "commentary",
  "timestamp": "{datetime.now().isoformat()}",
  "confidence": 0.0,
  "signals": {{
    "minutes_projection": {{
      "value": 0,
      "confidence": 0.0,
      "reasoning": "string"
    }},
    "usage_projection": {{
      "value": 0,
      "confidence": 0.0,
      "reasoning": "string"
    }},
    "fatigue_indicator": {{
      "value": 0.0,
      "confidence": 0.0,
      "reasoning": "string"
    }},
    "injury_concern": {{
      "value": false,
      "confidence": 0.0,
      "reasoning": "string"
    }}
  }},
  "game_context": {json_module.dumps(game_context)},
  "decay_half_life_minutes": 30,
  "source_attribution": "vllm-deepseek"
}}

CRITICAL REQUIREMENTS:
- confidence values must be between 0.0 and 1.0
- All reasoning fields must explain your analysis
- Be conservative with confidence scores - only assign >0.8 for very clear patterns

Respond with JSON only:
"""

        # Use chat template format for DeepSeek
        full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>"

        return full_prompt

    def _call_vllm(self, prompt: str) -> str:
        """Execute single prompt with vLLM."""

        outputs = self.llm.generate([prompt], self.sampling_params)
        return outputs[0].outputs[0].text.strip()

    def _call_vllm_batch(self, prompts: List[str]) -> List[str]:
        """Execute multiple prompts in batch with vLLM."""

        outputs = self.llm.generate(prompts, self.sampling_params)

        responses = []
        for output in outputs:
            responses.append(output.outputs[0].text.strip())

        return responses

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse and validate LLM response from vLLM."""

        try:
            import json as json_module

            # Find JSON in response (model might add extra text)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                logger.error("No JSON found in vLLM response")
                return None

            json_str = response[start_idx:end_idx]
            evidence_data = json_module.loads(json_str)

            # Basic validation
            required_fields = ["confidence", "signals"]
            if not all(field in evidence_data for field in required_fields):
                logger.error("Missing required fields in vLLM response")
                return None

            # Validate confidence ranges
            if not (0.0 <= evidence_data["confidence"] <= 1.0):
                logger.error("Invalid confidence value")
                return None

            # Set missing fields
            evidence_data["player_id"] = "to_be_set"
            evidence_data["evidence_type"] = "commentary"
            evidence_data["timestamp"] = datetime.now().isoformat()
            evidence_data["decay_half_life_minutes"] = evidence_data.get("decay_half_life_minutes", 30)
            evidence_data["source_attribution"] = "vllm-deepseek"

            return evidence_data

        except Exception as e:
            logger.error(f"Failed to parse vLLM response: {e}")
            return None

    def _create_evidence_bundle(self, player_id: str, evidence_data: Dict[str, Any]) -> EvidenceBundle:
        """Convert validated evidence data to EvidenceBundle."""

        timestamp = datetime.fromisoformat(evidence_data["timestamp"])

        bundle = EvidenceBundle(
            player_id=player_id,
            evidence_type=EvidenceType.COMMENTARY,
            timestamp=timestamp,
            source_confidences={"vllm": evidence_data["confidence"]}
        )

        # Add signals (same logic as other adapters)
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
                    "source": "vllm-deepseek",
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
                    "source": "vllm-deepseek",
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
                    "source": "vllm-deepseek",
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
                    "source": "vllm-deepseek",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        bundle.game_context = evidence_data.get("game_context", {})
        bundle.integrity_score = evidence_data["confidence"]

        return bundle


# Convenience function for quick evidence generation
def generate_player_evidence_vllm(player_id: str,
                                 player_name: str,
                                 team: str,
                                 game_context: Dict[str, Any],
                                 recent_performance: List[Dict[str, Any]]) -> Optional[EvidenceBundle]:
    """
    Quick function to generate evidence using vLLM.

    Requires vLLM and GPU access.
    """

    adapter = VLLMAdapter()
    return adapter.generate_evidence(
        player_id, player_name, team, game_context, recent_performance
    )


if __name__ == "__main__":
    # Example usage (requires vLLM and GPU)
    try:
        adapter = VLLMAdapter()

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
        print("Make sure vLLM is installed and GPU is available")