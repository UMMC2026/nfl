import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.nfl_analyzer import NFLAnalyzer, NFLGame, NFLProp
from engine.nfl_ai_integration import NFL_AIAnalyzer
from formatters.nfl_formatter import NFLFormatter

def run_nfl_pipeline(slate: dict, output_dir: str = "outputs", enable_under_first_lens=True, enable_failure_lens=True):
    print(f"[NFL PIPELINE] Starting analysis for {len(slate.get('games', []))} games")
    games = []
    for game_data in slate.get("games", []):
        games.append(NFLGame(
            away=game_data.get("away"),
            home=game_data.get("home"),
            datetime=game_data.get("datetime", "")
        ))
    props = []
    for prop_data in slate.get("props", []):
        props.append(NFLProp(
            player=prop_data.get("player"),
            team=prop_data.get("team"),
            stat=prop_data.get("stat"),
            line=float(prop_data.get("line", 0)),
            direction=prop_data.get("direction", "More")
        ))
    print("[NFL PIPELINE] Running math engine...")
    analyzer = NFLAnalyzer()
    math_analysis = analyzer.analyze_slate(games, props)
    print("[NFL PIPELINE] Running AI analysis...")
    ai_analyzer = NFL_AIAnalyzer()
    ai_analysis = ai_analyzer.generate_comprehensive_analysis(slate)
    combined_analysis = {
        **math_analysis,
        "ai_commentary": ai_analysis.get("ollama_commentary", {}),
        "ai_probabilities": ai_analysis.get("deepseek_analysis", {})
    }
    print("[NFL PIPELINE] Formatting cheatsheet...")
    formatter = NFLFormatter()
    cheatsheet = formatter.format_cheatsheet(
        combined_analysis, slate,
        enable_under_first_lens=enable_under_first_lens,
        enable_failure_lens=enable_failure_lens
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"NFL_CHEATSHEET_{timestamp}.txt"
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cheatsheet)
    print(f"[NFL PIPELINE] Output written to {output_path}")
    print(f"[NFL PIPELINE] Analysis complete: {len(math_analysis.get('qualified_props', []))} qualified props")
    return output_path
