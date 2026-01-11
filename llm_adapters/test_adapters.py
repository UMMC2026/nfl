"""
Unit tests for LLM Evidence Adapters

Tests structured evidence generation and integration with truth engine.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Import adapters
from llm_adapters.deepseek_adapter import DeepSeekAdapter, DeepSeekConfig
from llm_adapters.llama_cpp_adapter import LlamaCppAdapter, LlamaConfig
from llm_adapters.vllm_adapter import VLLMAdapter, VLLMConfig

# Import truth engine components
from truth_engine.evidence import EvidenceBundle, EvidenceType, EvidenceSource


class TestDeepSeekAdapter:
    """Test DeepSeek API adapter."""

    @pytest.fixture
    def mock_api_response(self):
        """Mock successful API response."""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "player_id": "test_player",
                        "evidence_type": "commentary",
                        "timestamp": "2024-01-06T12:00:00",
                        "confidence": 0.75,
                        "signals": {
                            "minutes_projection": {
                                "value": 35.5,
                                "confidence": 0.8,
                                "reasoning": "Consistent with recent games"
                            },
                            "usage_projection": {
                                "value": 28.0,
                                "confidence": 0.7,
                                "reasoning": "Slight increase due to matchup"
                            }
                        },
                        "decay_half_life_minutes": 30,
                        "source_attribution": "deepseek-coder"
                    })
                }
            }]
        }

    @pytest.fixture
    def adapter(self):
        """Create adapter with mock config."""
        config = DeepSeekConfig(api_key="test_key")
        return DeepSeekAdapter(config)

    def test_initialization_success(self):
        """Test successful adapter initialization."""
        config = DeepSeekConfig(api_key="test_key")
        adapter = DeepSeekAdapter(config)
        assert adapter.config.api_key == "test_key"

    def test_initialization_missing_key(self):
        """Test failure when API key is missing."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="DeepSeek API key not found"):
                DeepSeekAdapter()

    @patch('llm_adapters.deepseek_adapter.requests.post')
    def test_generate_evidence_success(self, mock_post, adapter, mock_api_response):
        """Test successful evidence generation."""
        mock_post.return_value.json.return_value = mock_api_response

        evidence = adapter.generate_evidence(
            player_id="lebron_james",
            player_name="LeBron James",
            team="LAL",
            game_context={"quarter": 2},
            recent_performance=[{"points": 28}]
        )

        assert evidence is not None
        assert evidence.player_id == "lebron_james"
        assert evidence.evidence_type == EvidenceType.COMMENTARY
        assert evidence.minutes_signal is not None
        assert evidence.minutes_signal.value == 35.5
        assert evidence.minutes_signal.confidence == 0.8

    @patch('llm_adapters.deepseek_adapter.requests.post')
    def test_generate_evidence_api_failure(self, mock_post, adapter):
        """Test handling of API failures."""
        mock_post.side_effect = Exception("API Error")

        evidence = adapter.generate_evidence(
            player_id="lebron_james",
            player_name="LeBron James",
            team="LAL",
            game_context={"quarter": 2},
            recent_performance=[{"points": 28}]
        )

        assert evidence is None

    def test_parse_invalid_json_response(self, adapter):
        """Test parsing of invalid JSON response."""
        invalid_response = {"choices": [{"message": {"content": "not json"}}]}

        result = adapter._parse_llm_response(invalid_response)
        assert result is None

    def test_parse_missing_required_fields(self, adapter):
        """Test parsing response with missing required fields."""
        invalid_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({"confidence": 0.5})  # Missing required fields
                }
            }]
        }

        result = adapter._parse_llm_response(invalid_response)
        assert result is None


class TestLlamaCppAdapter:
    """Test llama.cpp adapter."""

    @pytest.fixture
    def mock_llama_response(self):
        """Mock successful llama.cpp response."""
        return json.dumps({
            "player_id": "test_player",
            "evidence_type": "commentary",
            "timestamp": "2024-01-06T12:00:00",
            "confidence": 0.8,
            "signals": {
                "minutes_projection": {
                    "value": 38.0,
                    "confidence": 0.85,
                    "reasoning": "Strong recent trend"
                }
            },
            "decay_half_life_minutes": 30,
            "source_attribution": "llama-cpp-local"
        })

    @pytest.fixture
    def adapter(self, tmp_path):
        """Create adapter with mock config."""
        # Create a mock model file
        model_file = tmp_path / "test_model.gguf"
        model_file.write_text("mock model")

        config = LlamaConfig(
            model_path=str(model_file),
            executable_path="echo"  # Mock executable
        )

        with patch.object(LlamaCppAdapter, '_check_llama_cli', return_value=True):
            return LlamaCppAdapter(config)

    @patch('llm_adapters.llama_cpp_adapter.subprocess.run')
    def test_generate_evidence_success(self, mock_run, adapter, mock_llama_response):
        """Test successful evidence generation."""
        mock_run.return_value = Mock(returncode=0, stdout=mock_llama_response)

        evidence = adapter.generate_evidence(
            player_id="lebron_james",
            player_name="LeBron James",
            team="LAL",
            game_context={"quarter": 2},
            recent_performance=[{"points": 28}]
        )

        assert evidence is not None
        assert evidence.player_id == "lebron_james"
        assert evidence.minutes_signal.value == 38.0

    def test_initialization_missing_model(self):
        """Test failure when model file doesn't exist."""
        config = LlamaConfig(model_path="/nonexistent/model.gguf")
        with pytest.raises(FileNotFoundError):
            LlamaCppAdapter(config)

    @patch('llm_adapters.llama_cpp_adapter.subprocess.run')
    def test_llama_cli_not_found(self, mock_run, tmp_path):
        """Test handling when llama-cli is not available."""
        mock_run.side_effect = FileNotFoundError()

        # Create a fake model file
        model_file = tmp_path / "fake_model.gguf"
        model_file.write_text("mock model")

        config = LlamaConfig(
            model_path=str(model_file),
            executable_path="nonexistent-cli"
        )

        with pytest.raises(RuntimeError, match="llama-cli not found"):
            LlamaCppAdapter(config)


class TestVLLMAdapter:
    """Test vLLM adapter."""

    @pytest.fixture
    def mock_vllm_response(self):
        """Mock successful vLLM response."""
        return json.dumps({
            "confidence": 0.7,
            "signals": {
                "minutes_projection": {
                    "value": 36.0,
                    "confidence": 0.75,
                    "reasoning": "Balanced recent performance"
                },
                "usage_projection": {
                    "value": 26.0,
                    "confidence": 0.7,
                    "reasoning": "Consistent with role"
                }
            }
        })

    @pytest.fixture
    def adapter(self):
        """Create adapter with mocked vLLM."""
        pytest.skip("vLLM not available in test environment")

    def test_initialization_vllm_unavailable(self):
        """Test failure when vLLM is not available."""
        with patch('llm_adapters.vllm_adapter.VLLM_AVAILABLE', False):
            with pytest.raises(ImportError, match="vLLM not available"):
                VLLMAdapter()

    def test_generate_evidence_batch(self, adapter, mock_vllm_response):
        """Test batch evidence generation."""
        # Mock the batch response
        mock_output = Mock()
        mock_output.outputs = [Mock(text=mock_vllm_response)]
        adapter.llm.generate.return_value = [mock_output]

        players_data = [{
            "player_id": "lebron_james",
            "player_name": "LeBron James",
            "team": "LAL",
            "game_context": {"quarter": 2},
            "recent_performance": [{"points": 28}]
        }]

        results = adapter.generate_evidence_batch(players_data)

        assert len(results) == 1
        assert results[0] is not None
        assert results[0].player_id == "lebron_james"


class TestEvidenceBundleCreation:
    """Test EvidenceBundle creation from LLM responses."""

    def test_create_bundle_with_all_signals(self):
        """Test creating bundle with all signal types."""
        adapter = DeepSeekAdapter(DeepSeekConfig(api_key="test"))

        evidence_data = {
            "player_id": "test",
            "evidence_type": "commentary",
            "timestamp": "2024-01-06T12:00:00",
            "confidence": 0.8,
            "signals": {
                "minutes_projection": {"value": 35, "confidence": 0.8, "reasoning": "test"},
                "usage_projection": {"value": 25, "confidence": 0.7, "reasoning": "test"},
                "fatigue_indicator": {"value": 0.3, "confidence": 0.6, "reasoning": "test"},
                "injury_concern": {"value": False, "confidence": 0.9, "reasoning": "test"}
            },
            "decay_half_life_minutes": 30,
            "source_attribution": "test"
        }

        bundle = adapter._create_evidence_bundle("test_player", evidence_data)

        assert bundle.player_id == "test_player"
        assert bundle.minutes_signal is not None
        assert bundle.usage_signal is not None
        assert bundle.fatigue_signal is not None
        assert bundle.injury_signal is not None
        assert bundle.integrity_score == 0.8

    def test_create_bundle_minimal_signals(self):
        """Test creating bundle with minimal signals."""
        adapter = DeepSeekAdapter(DeepSeekConfig(api_key="test"))

        evidence_data = {
            "player_id": "test",
            "evidence_type": "commentary",
            "timestamp": "2024-01-06T12:00:00",
            "confidence": 0.6,
            "signals": {},
            "decay_half_life_minutes": 30,
            "source_attribution": "test"
        }

        bundle = adapter._create_evidence_bundle("test_player", evidence_data)

        assert bundle.player_id == "test_player"
        assert bundle.minutes_signal is None
        assert bundle.usage_signal is None
        assert bundle.integrity_score == 0.6


if __name__ == "__main__":
    pytest.main([__file__])