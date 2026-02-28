"""
Golf Analysis Menu
==================
Interactive menu for golf prop analysis.

Usage:
    python golf/golf_menu.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path


# --- UNIVERSAL PROJECT ROOT IMPORT PATCH ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

GOLF_DIR = Path(__file__).parent
INPUTS_DIR = GOLF_DIR / "inputs"
OUTPUTS_DIR = GOLF_DIR / "outputs"

# Ensure directories exist
INPUTS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print menu header."""
    print("=" * 60)
    print("⛳ GOLF PGA MODULE — UNDERDOG ANALYSIS")
    print("=" * 60)
    print(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)


def print_menu():
    """Print menu options."""
    print("\nOptions:")
    print("  [1] 📋 Paste & Analyze Underdog Slate")
    print("  [2] 📂 Load Slate from File")
    print("  [3] 🎯 View Latest Analysis Report")
    print("  [4] 📊 View All Edges (JSON)")
    print("  [5] 🏌️ Player Stats Lookup")
    print("  [6] 🏆 Current Tournament Info")
    print("  [7] ⚙️  Configure API Keys")
    print("  [8] 🛰️  Odds API — Golf Outrights (Majors, no scrape)")
    print("  [P] 📝 Professional Reporting Mode")
    print("  [T] 📢 Send Top 5 Picks to Telegram")
    print("  [0] 🚪 Exit")
    print()


def option_paste_analyze():
    """Option 1: Paste and analyze slate."""
    print("\n" + "=" * 60)
    print("📋 PASTE UNDERDOG SLATE")
    print("=" * 60)
    print("\nPaste your Underdog golf props below.")
    print("When done, press Enter twice (blank line):\n")
    
    lines = []
    empty_count = 0
    
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break
    
    text = "\n".join(lines)
    
    if not text.strip():
        print("\n⚠️  No text pasted. Returning to menu.")
        return
    
    # Parse the slate
    from golf.ingest.underdog_parser import parse_underdog_golf_slate, save_parsed_slate
    
    props = parse_underdog_golf_slate(text)
    
    print(f"\n✓ Parsed {len(props)} props")
    
    if not props:
        print("⚠️  No props could be parsed. Check format.")
        return
    
    # Save parsed slate
    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    parsed_file = OUTPUTS_DIR / f"parsed_slate_{today}.json"
    save_parsed_slate(props, parsed_file)
    print(f"✓ Saved parsed slate to {parsed_file.name}")
    
    # Also save as input for pipeline
    input_file = INPUTS_DIR / "slate.txt"
    with open(input_file, "w") as f:
        f.write(text)
    print(f"✓ Saved raw slate to {input_file.name}")
    
    # Run analysis
    print("\n" + "-" * 40)
    print("Running Monte Carlo analysis...")
    print("-" * 40)
    
    from golf.run_daily import run_daily_pipeline
    result = run_daily_pipeline(slate_file=input_file, dry_run=False)
    
    if result["status"] == "SUCCESS":
        print(f"\n✓ Analysis complete!")
        print(f"  Edges: {result['edges_generated']}")
        print(f"  Optimizable: {result['edges_optimizable']}")
    else:
        print(f"\n⚠️  Analysis failed: {result['status']}")
    
    input("\nPress Enter to continue...")


def option_load_file():
    """Option 2: Load slate from file."""
    print("\n" + "=" * 60)
    print("📂 LOAD SLATE FROM FILE")
    print("=" * 60)
    
    # List available files
    txt_files = list(INPUTS_DIR.glob("*.txt"))
    
    if txt_files:
        print("\nAvailable slate files:")
        for i, f in enumerate(txt_files, 1):
            print(f"  [{i}] {f.name}")
        print(f"  [0] Cancel")
        
        choice = input("\nSelect file: ").strip()
        
        if choice == "0":
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(txt_files):
                slate_file = txt_files[idx]
            else:
                print("Invalid selection")
                return
        except ValueError:
            print("Invalid input")
            return
    else:
        print("\nNo slate files found in golf/inputs/")
        print("Create a .txt file with Underdog paste")
        input("\nPress Enter to continue...")
        return
    
    # Run analysis
    from golf.run_daily import run_daily_pipeline
    result = run_daily_pipeline(slate_file=slate_file, dry_run=False)
    
    input("\nPress Enter to continue...")


def option_view_report():
    """Option 3: View latest analysis report."""
    print("\n" + "=" * 60)
    print("🎯 LATEST ANALYSIS REPORT")
    print("=" * 60)
    
    # Find latest report
    reports = sorted(OUTPUTS_DIR.glob("golf_report_*.txt"), reverse=True)
    
    if not reports:
        print("\nNo reports found. Run analysis first.")
        input("\nPress Enter to continue...")
        return
    
    latest = reports[0]
    print(f"\nLoading: {latest.name}\n")
    
    with open(latest) as f:
        print(f.read())
    
    input("\nPress Enter to continue...")


def option_view_edges():
    """Option 4: View edges JSON."""
    print("\n" + "=" * 60)
    print("📊 EDGES JSON VIEW")
    print("=" * 60)
    
    # Find latest edges
    edges_files = sorted(OUTPUTS_DIR.glob("golf_edges_*.json"), reverse=True)
    
    if not edges_files:
        print("\nNo edges found. Run analysis first.")
        input("\nPress Enter to continue...")
        return
    
    latest = edges_files[0]
    print(f"\nLoading: {latest.name}")
    
    import json
    with open(latest) as f:
        data = json.load(f)
    
    print(f"\nTotal edges: {data.get('edge_count', 0)}")
    
    # Show optimizable edges
    edges = data.get("edges", [])
    optimizable = [e for e in edges if e.get("pick_state") == "OPTIMIZABLE"]
    
    print(f"Optimizable: {len(optimizable)}")
    print("\n" + "-" * 40)
    
    for edge in optimizable[:10]:
        print(f"\n{edge['player']} | {edge['market']} {edge['line']} {edge['direction'].upper()}")
        print(f"  Prob: {edge['probability']:.1%} | Tier: {edge['tier']}")
    
    if len(optimizable) > 10:
        print(f"\n... and {len(optimizable) - 10} more")
    
    input("\nPress Enter to continue...")


def option_player_lookup():
    """Option 5: Player stats lookup."""
    print("\n" + "=" * 60)
    print("🏌️ PLAYER STATS LOOKUP")
    print("=" * 60)
    
    player_name = input("\nEnter player name: ").strip()
    
    if not player_name:
        return
    
    print(f"\nSearching for {player_name}...")
    
    # Try DataGolf if API key available
    api_key = os.getenv("DATAGOLF_API_KEY")
    
    if api_key:
        try:
            from golf.ingest.datagolf_client import DataGolfClient
            client = DataGolfClient()
            
            player = client.get_player_skill(player_name)
            
            if player:
                print(f"\n✓ Found: {player['player_name']}")
                print(f"\n  Strokes Gained Breakdown:")
                print(f"    SG Total: {player['sg_total']:+.2f}")
                print(f"    SG OTT:   {player['sg_ott']:+.2f}")
                print(f"    SG APP:   {player['sg_app']:+.2f}")
                print(f"    SG ARG:   {player['sg_arg']:+.2f}")
                print(f"    SG Putt:  {player['sg_putt']:+.2f}")
            else:
                print(f"\n⚠️  Player '{player_name}' not found in DataGolf")
        except Exception as e:
            print(f"\n⚠️  Error: {e}")
    else:
        print("\n⚠️  DataGolf API key not configured")
        print("   Set DATAGOLF_API_KEY environment variable")
        print("   Or use option [7] to configure")
    
    input("\nPress Enter to continue...")


def option_tournament_info():
    """Option 6: Current tournament info."""
    print("\n" + "=" * 60)
    print("🏆 CURRENT TOURNAMENT INFO")
    print("=" * 60)
    
    # Try to get current tournament from DataGolf
    api_key = os.getenv("DATAGOLF_API_KEY")
    
    if api_key:
        try:
            from golf.ingest.datagolf_client import DataGolfClient
            client = DataGolfClient()
            
            preds = client.get_pre_tournament_predictions()
            
            event_name = preds.get("event_name", "Unknown")
            print(f"\n🏆 {event_name}")
            
            baseline = preds.get("baseline_preds", [])[:10]
            
            print("\n  Top 10 Win Probabilities:")
            for i, p in enumerate(baseline, 1):
                name = p.get("player_name", "Unknown")
                win = p.get("win_prob", 0) * 100
                top5 = p.get("top_5", 0) * 100
                print(f"    {i:2}. {name}: Win {win:.1f}% | Top 5: {top5:.1f}%")
        except Exception as e:
            print(f"\n⚠️  Error: {e}")
    else:
        print("\n⚠️  DataGolf API key not configured")
    
    input("\nPress Enter to continue...")


def option_configure_api():
    """Option 7: Configure API keys."""
    print("\n" + "=" * 60)
    print("⚙️  CONFIGURE API KEYS")
    print("=" * 60)
    
    print("\nCurrent configuration:")
    
    datagolf_key = os.getenv("DATAGOLF_API_KEY")
    print(f"  DATAGOLF_API_KEY: {'Set ✓' if datagolf_key else 'Not set ✗'}")
    
    print("\nTo set API keys:")
    print("  1. Create/edit .env file in project root")
    print("  2. Add: DATAGOLF_API_KEY=your_key_here")
    print("  3. Restart the application")
    print("\nGet DataGolf API key at: https://datagolf.com/api-access")
    
    input("\nPress Enter to continue...")


def option_odds_api_outrights():
    """Option 8: Odds API Golf Outrights (Majors)."""
    try:
        from golf.oddsapi_golf_ingest import interactive_run
        interactive_run()
    except Exception as e:
        print(f"\n\u26a0\ufe0f  Odds API Golf ingest failed: {e}")
        input("\nPress Enter to continue...")


def main():
    """Main menu loop."""
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    while True:
        clear_screen()
        print_header()
        print_menu()
        
        choice = input("Select option: ").strip().upper()

        if choice == "1":
            option_paste_analyze()
        elif choice == "2":
            option_load_file()
        elif choice == "3":
            option_view_report()
        elif choice == "4":
            option_view_edges()
        elif choice == "5":
            option_player_lookup()
        elif choice == "6":
            option_tournament_info()
        elif choice == "7":
            option_configure_api()
        elif choice == "8":
            option_odds_api_outrights()
        elif choice == "P":
            option_professional_report()
        elif choice == "T":
            option_send_top5_telegram()
        elif choice == "0":
            print("\n👋 Goodbye!")
            break
        else:
            print("\n⚠️  Invalid option")
            input("Press Enter to continue...")

def option_professional_report():
    """Option: Professional reporting mode."""
    print("\n" + "=" * 60)
    print("📝 PROFESSIONAL REPORTING MODE")
    print("=" * 60)
    # Find latest report
    reports = sorted(OUTPUTS_DIR.glob("golf_report_*.txt"), reverse=True)
    if not reports:
        print("\nNo reports found. Run analysis first.")
        input("\nPress Enter to continue...")
        return
    latest = reports[0]
    print(f"\nLoading: {latest.name}\n")
    with open(latest, encoding="utf-8") as f:
        content = f.read()
    # Optionally, add more formatting or summary here for professional mode
    print(content)
    input("\nPress Enter to continue...")

def option_send_top5_telegram():
    """Option: Send top 5 picks to Telegram."""
    print("\n" + "=" * 60)
    print("📢 SENDING TOP 5 PICKS TO TELEGRAM")
    print("=" * 60)
    # Find latest edges file
    import json
    edges_files = sorted(OUTPUTS_DIR.glob("golf_edges_*.json"), reverse=True)
    if not edges_files:
        print("\nNo edges found. Run analysis first.")
        input("\nPress Enter to continue...")
        return
    latest = edges_files[0]
    with open(latest, encoding="utf-8") as f:
        data = json.load(f)
    edges = data.get("edges", [])
    # Sort by probability, descending, OPTIMIZABLE only
    optimizable = [e for e in edges if e.get("pick_state") == "OPTIMIZABLE"]
    top5 = sorted(optimizable, key=lambda e: e.get("probability", 0), reverse=True)[:5]
    if not top5:
        print("No OPTIMIZABLE picks found.")
        input("\nPress Enter to continue...")
        return
    # Format message for Telegram
    # NOTE: Never use surrogate escape sequences (e.g. "\ud83c\udfc6") in Python strings.
    # They are invalid Unicode and will crash when encoding to UTF-8 for Telegram.
    msg_lines = ["🏆 GOLF TOP 5 PICKS"]
    for i, pick in enumerate(top5, 1):
        player = pick.get("player") or pick.get("entity", "?")
        stat = pick.get("market", "?")
        line = pick.get("line", "?")
        direction = pick.get("direction", "?").upper()
        prob = pick.get("probability", 0)
        tier = pick.get("tier", "?")
        msg_lines.append(f"{i}. {player} {stat} {line} {direction} | {prob:.1%} | {tier}")
    message = "\n".join(msg_lines)
    # Defensive: ensure message is valid UTF-8 encodable (Telegram requirement).
    message = message.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    # Send via telegram_push
    try:
        from telegram_push import _get_token, _get_chat_id
        import requests
        token = _get_token()
        chat_id = _get_chat_id()
        if not token or not chat_id:
            print("\n⚠️  Telegram not configured. Set SPORTS_BOT_TOKEN/TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
            input("\nPress Enter to continue...")
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        resp = requests.post(url, data=payload)
        if resp.status_code == 200:
            print("\n✓ Top 5 picks sent to Telegram!")
        else:
            print(f"\n⚠️  Telegram error: {resp.status_code}")
    except Exception as e:
        print(f"\n⚠️  Telegram send failed: {e}")
    input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
