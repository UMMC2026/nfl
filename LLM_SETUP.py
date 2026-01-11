"""
Quick Setup: Install Ollama + DeepSeek for Local LLM
====================================================

OPTION 1: OLLAMA (Recommended - Free, Local, Fast)
---------------------------------------------------
1. Install Ollama:
   Windows: https://ollama.com/download/windows
   
2. Install DeepSeek model:
   ollama pull deepseek-r1:1.5b
   
3. Verify:
   ollama run deepseek-r1:1.5b "Hello"
   
4. Run research assistant:
   python llm_research_assistant.py


OPTION 2: OPENAI API (Fallback - Paid, Cloud)
----------------------------------------------
1. Get API key: https://platform.openai.com/api-keys

2. Add to .env:
   OPENAI_API_KEY=sk-...
   
3. Run research assistant:
   python llm_research_assistant.py


DEMO WORKFLOW (Tonight's Slate)
--------------------------------
# Step 1: Run LLM research
python llm_research_assistant.py

# Output: llm_research_output.json
# Contains:
#   - Matchup adjustments (e.g., "Garland assists -10% B2B")
#   - Injury alerts
#   - Coaching insights
#   - Blowout probabilities

# Step 2: HUMAN REVIEW (CRITICAL)
# Open llm_research_output.json
# Validate each suggestion with historical data
# Hardcode verified insights into comprehensive_analysis_jan8.py

# Step 3: Re-run enhancement pipeline
python run_full_enhancement_complete_v2.py

# Step 4: Generate rich narratives
python llm_narrative_generator.py

# Step 5: Send to Telegram
# Copy llm_enhanced_telegram.txt → send_complete_to_telegram_jan8.py


ARCHITECTURE
------------
┌─────────────────────────────────────────┐
│  LLM RESEARCH (Pre-Game, 6-12 hrs)      │
│  - llm_research_assistant.py            │
│  - Outputs: JSON suggestions            │
└──────────────┬──────────────────────────┘
               │ HUMAN VALIDATES
               ▼
┌─────────────────────────────────────────┐
│  HARDCODED KNOWLEDGE (Curated)          │
│  - comprehensive_analysis_jan8.py       │
│  - TEAM_ANALYTICS, MATCHUP_ADJUSTMENTS  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  MATH ENGINE (Live Pipeline)            │
│  - hydrate → enhance → select → build   │
│  - NO LLM in probability calculations   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  NARRATIVES (Post-Build)                │
│  - llm_narrative_generator.py           │
│  - Rich Telegram stories                │
└─────────────────────────────────────────┘


COST COMPARISON
---------------
Ollama (Local):
  - Cost: $0 forever
  - Speed: ~2-5 sec/query
  - Model: DeepSeek R1 1.5B
  - Privacy: 100% local
  
OpenAI API:
  - Cost: ~$0.50/day (GPT-4o-mini)
  - Speed: ~1-3 sec/query
  - Model: GPT-4o-mini
  - Privacy: Cloud (encrypted)


NEXT STEPS
----------
1. Install Ollama: https://ollama.com/download/windows
2. Run: ollama pull deepseek-r1:1.5b
3. Test: python llm_research_assistant.py
4. Review: llm_research_output.json
5. Hardcode validated insights
6. Rebuild portfolio with new data
"""

# Quick installer script
import subprocess
import sys
import os

def check_ollama():
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama installed:", result.stdout.strip())
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Ollama not found")
    print("Install from: https://ollama.com/download/windows")
    return False


def check_deepseek():
    """Check if DeepSeek model is available"""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "deepseek-r1:1.5b" in result.stdout:
            print("✅ DeepSeek R1 1.5B installed")
            return True
    except:
        pass
    
    print("❌ DeepSeek model not found")
    print("Run: ollama pull deepseek-r1:1.5b")
    return False


def check_openai_key():
    """Check if OpenAI key is configured"""
    key = os.getenv("OPENAI_API_KEY", "")
    if key:
        print(f"✅ OpenAI API key configured: {key[:8]}...")
        return True
    else:
        print("⚠️ No OpenAI API key (Ollama will be used)")
        return False


if __name__ == "__main__":
    print("="*80)
    print("LLM SETUP CHECK")
    print("="*80)
    print()
    
    ollama_ok = check_ollama()
    deepseek_ok = check_deepseek() if ollama_ok else False
    openai_ok = check_openai_key()
    
    print()
    print("="*80)
    
    if deepseek_ok:
        print("✅ ALL SET! You can use Ollama (local, free)")
        print("Run: python llm_research_assistant.py")
    elif openai_ok:
        print("✅ OpenAI configured (fallback)")
        print("Run: python llm_research_assistant.py")
    else:
        print("❌ NO LLM AVAILABLE")
        print()
        print("QUICK FIX:")
        print("1. Download Ollama: https://ollama.com/download/windows")
        print("2. Install: ollama pull deepseek-r1:1.5b")
        print("3. Run: python llm_research_assistant.py")
    
    print("="*80)
