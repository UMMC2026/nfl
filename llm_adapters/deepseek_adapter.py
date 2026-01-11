"""
DeepSeek LLM Adapter for Truth Engine Evidence Generation

Integrates DeepSeek-Coder API to generate structured evidence for player projections.
LLM acts as evidence interpreter, not decision maker.
"""

import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from dataclasses import dataclass
import os
from pathlib import Path

# Import truth engine components
from truth_engine.evidence import EvidenceBundle, EvidenceSignal, EvidenceType, EvidenceSource

logger = logging.getLogger(__name__)


@dataclass
class DeepSeekConfig:
    """Configuration for DeepSeek API."""
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-coder"
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 30


class DeepSeekAdapter:
    """
    Adapter for DeepSeek-Coder API to generate evidence for truth engine.

    LLM provides structured evidence interpretation, never direct decisions.
    """

    def __init__(self, config: Optional[DeepSeekConfig] = None):
        if config is None:
            config = DeepSeekConfig(
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-coder")
            )

        if not config.api_key:
            raise ValueError("DeepSeek API key not found. Set DEEPSEEK_API_KEY environment variable.")

        self.config = config
        self.schema_path = Path(__file__).parent / "evidence_schema.json"

        # Load evidence schema for validation
        with open(self.schema_path, 'r') as f:
            self.evidence_schema = json.load(f)

    def generate_evidence(self,
                         player_id: str,
                         player_name: str,
                         team: str,
                         game_context: Dict[str, Any],
                         recent_performance: List[Dict[str, Any]],
                         prompt_template: str = "default") -> Optional[EvidenceBundle]:
        """
        Generate evidence bundle for a player using DeepSeek analysis.

        Args:
            player_id: Unique player identifier
            player_name: Player's display name
            team: Team abbreviation
            game_context: Current game state (quarter, score, etc.)
            recent_performance: Recent games performance data
            prompt_template: Which prompt template to use

        Returns:
            EvidenceBundle if successful, None if generation fails
        """

        try:
            # Generate structured prompt
            prompt = self._build_evidence_prompt(
                player_name, team, game_context, recent_performance, prompt_template
            )

            # Call DeepSeek API
            llm_response = self._call_deepseek_api(prompt)

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
        """Build structured prompt for DeepSeek based on template."""

        base_prompt = f"""
You are an expert NBA analyst providing evidence-based assessment for player performance projections.

PLAYER: {player_name} ({team})
GAME CONTEXT: {json.dumps(game_context, indent=2)}
RECENT PERFORMANCE (last 5 games): {json.dumps(recent_performance, indent=2)}

Your task is to analyze this player's likely performance in the current game based on:
1. Recent statistical trends
2. Game context (quarter, score differential, pace)
3. Player's typical response to similar situations

Provide your analysis in STRICT JSON format matching this schema:
{json.dumps(self.evidence_schema, indent=2)}

CRITICAL REQUIREMENTS:
- confidence values must be between 0.0 and 1.0
- All reasoning fields must explain your analysis
- evidence_type should be "commentary" for this analysis
- timestamp should be current ISO format
- decay_half_life_minutes indicates how long this evidence remains relevant
- source_attribution should be "deepseek-coder"

Focus on these key projections:
- minutes_projection: Expected minutes (0-48)
- usage_projection: Expected usage rate (0-100)
- fatigue_indicator: Fatigue level (0.0-1.0, higher = more fatigued)
- injury_concern: Boolean + confidence for injury risk

Be conservative with confidence scores - only assign >0.8 for very clear patterns.
"""

        return base_prompt.strip()

    def _call_deepseek_api(self, prompt: str) -> Dict[str, Any]:
        """Make API call to DeepSeek."""

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {
                "role": "system",
                "content": "You are an expert NBA analyst. Always respond with valid JSON that matches the provided schema exactly. Never include explanatory text outside the JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        data = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"}  # Force JSON response
        }

        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=self.config.timeout
        )

        response.raise_for_status()
        return response.json()

    def _parse_llm_response(self, api_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse and validate LLM response."""

        try:
            content = api_response["choices"][0]["message"]["content"]

            # Parse JSON
            evidence_data = json.loads(content)

            # Basic validation against schema
            required_fields = ["player_id", "evidence_type", "timestamp", "confidence", "signals"]
            if not all(field in evidence_data for field in required_fields):
                logger.error("Missing required fields in LLM response")
                return None

            # Validate confidence ranges
            if not (0.0 <= evidence_data["confidence"] <= 1.0):
                logger.error("Invalid confidence value")
                return None

            return evidence_data

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None

    def _create_evidence_bundle(self, player_id: str, evidence_data: Dict[str, Any]) -> EvidenceBundle:
        """Convert validated evidence data to EvidenceBundle."""

        timestamp = datetime.fromisoformat(evidence_data["timestamp"])

        # Create evidence signals from LLM projections
        signals = evidence_data.get("signals", {})

        bundle = EvidenceBundle(
            player_id=player_id,
            evidence_type=EvidenceType.COMMENTARY,
            timestamp=timestamp,
            source_confidences={"deepseek": evidence_data["confidence"]}
        )

        # Add minutes signal
        if "minutes_projection" in signals:
            mp = signals["minutes_projection"]
            bundle.minutes_signal = EvidenceSignal(
                value=mp["value"],
                confidence=mp["confidence"],
                strength=evidence_data["confidence"],  # Use overall confidence as strength
                timestamp=timestamp,
                source=EvidenceSource.ANALYST,
                metadata={
                    "reasoning": mp.get("reasoning", ""),
                    "source": "deepseek-coder",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        # Add usage signal
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
                    "source": "deepseek-coder",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        # Add fatigue signal
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
                    "source": "deepseek-coder",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        # Add injury signal
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
                    "source": "deepseek-coder",
                    "decay_half_life": evidence_data.get("decay_half_life_minutes", 30)
                }
            )

        # Add game context
        bundle.game_context = evidence_data.get("game_context", {})

        # Set integrity score based on LLM confidence
        bundle.integrity_score = evidence_data["confidence"]

        return bundle


# Convenience function for quick evidence generation
def generate_player_evidence(player_id: str,
                           player_name: str,
                           team: str,
                           game_context: Dict[str, Any],
                           recent_performance: List[Dict[str, Any]]) -> Optional[EvidenceBundle]:
    """
    Quick function to generate evidence for a player.

    Usage:
        evidence = generate_player_evidence(
            "lebron_james", "LeBron James", "LAL",
            {"quarter": 2, "score_diff": -5},
            [{"points": 28, "minutes": 35}, ...]
        )
    """

    adapter = DeepSeekAdapter()
    return adapter.generate_evidence(
        player_id, player_name, team, game_context, recent_performance
    )


if __name__ == "__main__":
    # Example usage
    adapter = DeepSeekAdapter()

    # Test with sample data
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