#!/usr/bin/env python3
"""
Ollama Commentary Generator for Jan 4 NBA Slate
Adds AI analysis layer to Monte Carlo results
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

def run_ollama_commentary():
    """Generate Ollama AI commentary for the slate"""
    
    prompt = """You are a professional sports betting analyst. Analyze this NBA slate data and provide strategic commentary.

JAN 4, 2026 NBA 8-GAME SLATE MC RESULTS:
- DET @ CLE (1:00 PM): 12 props, 5.4 avg hits (45%)
- MIL @ SAC (8:00 PM): 9 props, 5.6 avg hits (62%) STRONGEST
- MEM @ LAL (8:30 PM): 10 props, 4.6 avg hits (46%)
- IND @ ORL (2:00 PM): 10 props, 4.6 avg hits (46%)
- DEN @ BKN (2:30 PM): 9 props, 4.1 avg hits (46%)
- NOP @ MIA (5:00 PM): 9 props, 3.7 avg hits (41%)
- MIN @ WAS (5:00 PM): 8 props, 3.7 avg hits (46%)
- OKC @ PHX (7:00 PM): 9 props, 3.6 avg hits (40%)

INDIVIDUAL EDGES:
- Shai Gilgeous-Alexander OVER 31.5 Pts (72%)
- Luka Doncic OVER 34.5 Pts (70%)
- Anthony Edwards OVER 30.5 Pts (68%)
- Giannis OVER 29.5 Pts (67%)

Provide 2-3 sentences on:
1. Slate composition and directional bias
2. Key risk factors (injuries, depth changes)
3. Recommended entry strategy for parlays"""
    
    try:
        result = subprocess.run(
            ["ollama", "run", "mistral", prompt],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Ollama error: {result.stderr}"
    
    except FileNotFoundError:
        return "Ollama not installed or not in PATH"
    except subprocess.TimeoutExpired:
        return "Ollama request timeout (>90s)"
    except Exception as e:
        return f"Error: {e}"

def save_commentary(commentary: str):
    """Save commentary to file"""
    output_file = Path("outputs") / f"OLLAMA_COMMENTARY_JAN4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# JAN 4 NBA SLATE - OLLAMA AI ANALYSIS\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(commentary)
    
    return output_file

# Main execution
if __name__ == "__main__":
    print("Generating Ollama commentary...")
    commentary = run_ollama_commentary()
    print(f"\n{commentary}\n")
    
    output_path = save_commentary(commentary)
    print(f"OK Saved: {output_path}")
