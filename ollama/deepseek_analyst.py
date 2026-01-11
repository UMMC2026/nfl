"""
DeepSeek API-powered risk analyst for contextual signal evaluation.
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def load_prompt() -> str:
    """Load the risk analyst prompt."""
    prompt_path = Path(__file__).parent / "prompt.txt"
    if prompt_path.exists():
        return prompt_path.read_text()
    
    # Fallback prompt
    return """You are an expert sports betting analyst. Analyze this prop bet signal and provide concise insights:

1. Why this edge exists (player trends, matchup, recent performance)
2. Key risk factors to consider
3. Confidence rating (HIGH/MEDIUM/LOW)

Be specific, concise, and actionable. Max 3-4 sentences."""


def analyze_with_deepseek(signal: dict) -> dict:
    """
    Run DeepSeek API analysis on a signal.
    
    Args:
        signal: Signal dict with probability data
    
    Returns:
        Signal dict enriched with ollama_notes (AI analysis)
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    if not api_key or api_key == "your_deepseek_api_key_here":
        signal["ollama_notes"] = "DeepSeek API key not configured"
        signal["ollama_error"] = "no_api_key"
        return signal
    
    prompt = load_prompt()
    
    # Build context for analysis
    context = {
        "player": signal.get("player"),
        "team": signal.get("team"),
        "stat": signal.get("stat"),
        "line": signal.get("line"),
        "play": signal.get("play", "OVER" if signal.get("direction") == "higher" else "UNDER"),
        "probability": round(signal.get("p_hit", 0) * 100, 1),
        "average": round(signal.get("mean", 0), 1),
        "std_dev": round(signal.get("std", 0), 1),
        "edge": round(signal.get("edge", 0), 1),
        "stability_score": signal.get("stability_score"),
        "stability_class": signal.get("stability_class"),
        "tier": signal.get("tier"),
    }
    
    user_message = f"{prompt}\n\nSIGNAL DATA:\n{json.dumps(context, indent=2)}"
    
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an expert NBA betting analyst providing concise prop bet insights."},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.3,
                "max_tokens": 200
            },
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        analysis = data["choices"][0]["message"]["content"].strip()
        signal["ollama_notes"] = analysis
        signal["ollama_error"] = None
        
    except requests.Timeout:
        signal["ollama_notes"] = "Analysis timed out"
        signal["ollama_error"] = "timeout"
        
    except requests.RequestException as e:
        signal["ollama_notes"] = f"API error: {str(e)[:100]}"
        signal["ollama_error"] = "api_error"
        
    except Exception as e:
        signal["ollama_notes"] = f"Error: {str(e)[:100]}"
        signal["ollama_error"] = str(e)
    
    return signal


def batch_analyze(signals: list) -> list:
    """
    Run DeepSeek analysis on a batch of signals.
    """
    analyzed = []
    total = len(signals)
    
    for i, s in enumerate(signals, 1):
        print(f"      Analyzing {s.get('player')} ({i}/{total})...", end="\r")
        analyzed.append(analyze_with_deepseek(s))
    
    print(f"      Analyzed {len(analyzed)} signals          ")
    return analyzed


def skip_analysis(signal: dict, reason: str = "Analysis skipped") -> dict:
    """
    Skip analysis and return signal with placeholder notes.
    """
    signal["ollama_notes"] = reason
    signal["ollama_error"] = "skipped"
    return signal
