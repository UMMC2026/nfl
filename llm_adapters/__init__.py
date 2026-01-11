"""
LLM Adapters for Truth Engine Evidence Generation

This package provides adapters for different LLM backends to generate
structured evidence for the truth engine. LLMs act as evidence interpreters,
not decision makers.

Available adapters:
- DeepSeekAdapter: Cloud API-based generation
- LlamaCppAdapter: Local llama.cpp execution (deterministic)
- VLLMAdapter: GPU-accelerated batch processing

All adapters produce EvidenceBundle objects that integrate with the truth engine.
"""

from .deepseek_adapter import DeepSeekAdapter, generate_player_evidence
from .llama_cpp_adapter import LlamaCppAdapter, generate_player_evidence_llama
from .vllm_adapter import VLLMAdapter, generate_player_evidence_vllm

__all__ = [
    "DeepSeekAdapter",
    "LlamaCppAdapter",
    "VLLMAdapter",
    "generate_player_evidence",
    "generate_player_evidence_llama",
    "generate_player_evidence_vllm"
]