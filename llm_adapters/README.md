# LLM Evidence Adapters

Structured LLM integration for the Dynamic Truth Engine. LLMs act as **evidence interpreters**, not decision makers.

## Architecture

```
LLM Adapter Layer
├── DeepSeekAdapter (Cloud API)
├── LlamaCppAdapter (Local deterministic)
└── VLLMAdapter (GPU batch processing)

All produce → EvidenceBundle → Truth Engine
```

## Quick Start

### 1. DeepSeek API (Recommended for Development)

```python
from llm_adapters import DeepSeekAdapter

# Set your API key in .env
# DEEPSEEK_API_KEY=your_key_here

adapter = DeepSeekAdapter()

evidence = adapter.generate_evidence(
    player_id="lebron_james",
    player_name="LeBron James",
    team="LAL",
    game_context={"quarter": 2, "score_diff": -5},
    recent_performance=[
        {"points": 28, "minutes": 35, "usage": 25},
        {"points": 32, "minutes": 38, "usage": 28}
    ]
)

if evidence:
    print(f"Minutes projection: {evidence.minutes_signal.value}")
```

### 2. Llama.cpp (Deterministic Production)

```python
from llm_adapters import LlamaCppAdapter

# Requires llama-cli and model file
adapter = LlamaCppAdapter()

evidence = adapter.generate_evidence(
    player_id="lebron_james",
    player_name="LeBron James",
    team="LAL",
    game_context={"quarter": 2},
    recent_performance=[{"points": 28}]
)
```

### 3. vLLM (High-Throughput Live)

```python
from llm_adapters import VLLMAdapter

# Requires GPU and vLLM
adapter = VLLMAdapter()

# Batch processing for multiple players
players_data = [
    {
        "player_id": "lebron_james",
        "player_name": "LeBron James",
        "team": "LAL",
        "game_context": {"quarter": 2},
        "recent_performance": [{"points": 28}]
    }
]

evidence_bundles = adapter.generate_evidence_batch(players_data)
```

## Evidence Schema

All adapters produce structured JSON matching `evidence_schema.json`:

```json
{
  "player_id": "string",
  "evidence_type": "commentary",
  "timestamp": "ISO datetime",
  "confidence": 0.0-1.0,
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
    },
    "fatigue_indicator": {
      "value": 0.3,
      "confidence": 0.6,
      "reasoning": "Normal rest, no back-to-backs"
    },
    "injury_concern": {
      "value": false,
      "confidence": 0.9,
      "reasoning": "No injury reports, full participation"
    }
  },
  "decay_half_life_minutes": 30,
  "source_attribution": "deepseek-coder"
}
```

## Installation & Setup

### DeepSeek API
```bash
pip install requests python-dotenv
# Set DEEPSEEK_API_KEY in .env
```

### Llama.cpp
```bash
# Install llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make

# Download model (example)
# wget https://huggingface.co/deepseek-ai/deepseek-coder-6.7b-instruct/resolve/main/model.gguf

# Set paths in .env
# LLAMA_MODEL_PATH=./models/deepseek-coder.gguf
# LLAMA_CLI_PATH=./llama.cpp/llama-cli
```

### vLLM
```bash
pip install vllm
# Requires CUDA-compatible GPU
# Set VLLM_MODEL in .env
```

## Integration with Truth Engine

```python
from truth_engine import TruthEngine
from llm_adapters import DeepSeekAdapter

# Initialize components
engine = TruthEngine()
llm_adapter = DeepSeekAdapter()

# Generate evidence
evidence = llm_adapter.generate_evidence(
    player_id="lebron_james",
    player_name="LeBron James",
    team="LAL",
    game_context=game_state,
    recent_performance=player_history
)

# Submit to truth engine (if evidence passes validation)
if evidence and evidence.integrity_score > 0.5:
    engine.submit_evidence(evidence)
```

## Safety & Governance

- **LLM ≠ Decision Maker**: Evidence only, never direct projections
- **Confidence Gating**: Low-confidence evidence is ignored
- **Source Attribution**: All evidence tagged with generation source
- **Deterministic Seeds**: Reproducible results for testing
- **Rate Limiting**: Built into adapters to prevent API abuse

## Testing

```bash
# Run adapter tests
python -m pytest llm_adapters/test_adapters.py -v

# Test integration
python -c "
from llm_adapters import DeepSeekAdapter
adapter = DeepSeekAdapter()
# Test with mock data
"
```

## Performance Characteristics

| Adapter | Latency | Throughput | Deterministic | Offline |
|---------|---------|------------|---------------|---------|
| DeepSeek | 1-3s | Low | No | No |
| Llama.cpp | 5-30s | Low | Yes (seeded) | Yes |
| vLLM | 0.5-2s | High (batched) | Yes (seeded) | No |

## Troubleshooting

### DeepSeek API Issues
- Check API key in `.env`
- Verify API quota/limits
- Test with simple prompt first

### Llama.cpp Issues
- Ensure model file exists and is readable
- Check llama-cli path and permissions
- Test with smaller model first

### vLLM Issues
- Verify CUDA installation
- Check GPU memory availability
- Start with smaller batch sizes

## Next Steps

After LLM evidence generation works:

1. **Phase B**: Live PBP ingestion + Evidence Router
2. **Phase C**: PlayerNode diagnostics + quarantine enforcement
3. **Integration**: Connect evidence flow to truth engine updates