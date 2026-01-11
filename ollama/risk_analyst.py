"""
Ollama-powered risk analyst for contextual signal evaluation.
"""

import subprocess
import json
from pathlib import Path


def load_prompt() -> str:
    """Load the risk analyst prompt."""
    prompt_path = Path(__file__).parent / "prompt.txt"
    return prompt_path.read_text()


def run_ollama(signal: dict, model: str = "llama3") -> dict:
    """
    Run Ollama risk analysis on a signal.
    
    Args:
        signal: Signal dict with probability data
        model: Ollama model to use (default: llama3)
    
    Returns:
        Signal dict enriched with ollama_notes
    """
    prompt = load_prompt()
    
    # Build context for analysis
    context = {
        "player": signal.get("player"),
        "stat": signal.get("stat"),
        "line": signal.get("line"),
        "play": signal.get("play"),
        "probability": round(signal.get("p_hit", 0) * 100, 1),
        "average": round(signal.get("mean", 0), 1),
        "std_dev": round(signal.get("std", 0), 1),
        "edge": round(signal.get("edge", 0), 1),
        "stability_score": signal.get("stability_score"),
        "stability_class": signal.get("stability_class"),
        "tier": signal.get("tier"),
    }
    
    payload = f"{prompt}\n\nINPUT:\n{json.dumps(context, indent=2)}"
    
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=payload,
            text=True,
            capture_output=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )
        
        signal["ollama_notes"] = result.stdout.strip()
        signal["ollama_error"] = None
        
    except subprocess.TimeoutExpired:
        signal["ollama_notes"] = "Analysis timed out"
        signal["ollama_error"] = "timeout"
        
    except FileNotFoundError:
        signal["ollama_notes"] = "Ollama not installed"
        signal["ollama_error"] = "not_installed"
        
    except Exception as e:
        signal["ollama_notes"] = f"Error: {str(e)}"
        signal["ollama_error"] = str(e)
    
    return signal


def batch_analyze(signals: list, model: str = "llama3") -> list:
    """
    Run Ollama analysis on a batch of signals.
    """
    analyzed = []
    for s in signals:
        analyzed.append(run_ollama(s, model))
    return analyzed


def skip_ollama(signal: dict, reason: str = "Skipped") -> dict:
    """
    Skip Ollama analysis and return signal with placeholder notes.
    Use when Ollama is not available or not needed.
    """
    signal["ollama_notes"] = reason
    signal["ollama_error"] = "skipped"
    return signal
