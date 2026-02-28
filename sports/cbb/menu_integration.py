def send_cbb_top7_to_telegram():
    """Send the top 7 CBB picks from the latest export report to Telegram."""
    from pathlib import Path
    import os
    import re
    from dotenv import load_dotenv
    load_dotenv()
    # Find latest export report
    outputs = sorted(Path(__file__).parent / "outputs".glob("cbb_report_export_*.txt"), reverse=True)
    if not outputs:
        print("\nNo CBB export report found. Run [R] to export a report.")
        input("\nPress Enter...")
        return
    latest = outputs[0]
    print(f"\nSource: {latest.name}")
    picks = parse_cbb_top7_from_report(str(latest))
    if not picks:
        print("\nNo picks found in report.")
        input("\nPress Enter...")
        return
    # Format message
    msg_lines = ["*CBB Top 7 Picks*\n"]
    for i, pick in enumerate(picks, 1):
        msg_lines.append(f"{i}. {pick.get('desc','')}")
        if 'stat' in pick:
            msg_lines.append(f"   {pick['stat']}")
        if 'mean' in pick:
            msg_lines.append(f"   {pick['mean']}")
        if 'note' in pick:
            msg_lines.append(f"   {pick['note']}")
    message = "\n".join(msg_lines)
    # Telegram config
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("SPORTS_BOT_TOKEN")
    chat_ids_raw = (
        os.getenv("TELEGRAM_CHAT_IDS")
        or os.getenv("TELEGRAM_BROADCAST_CHAT_IDS")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    chat_ids = [c for c in re.split(r"[\s,]+", chat_ids_raw) if c]
    if not bot_token:
        print("\n⚠️ Telegram not configured: missing TELEGRAM_BOT_TOKEN (or SPORTS_BOT_TOKEN).")
    if not chat_ids:
        print("\n⚠️ Telegram not configured: missing TELEGRAM_CHAT_ID (or TELEGRAM_CHAT_IDS).")
    else:
        print(f"\nTelegram targets configured: {len(chat_ids)}")
        if len(chat_ids) == 1:
            target = chat_ids[0]
            if target.isdigit() and not target.startswith("-"):
                print(
                    "⚠️ This looks like a personal chat ID. Only YOU will receive it.\n"
                    "   To reach subscribers, post to a Channel/Group (e.g., TELEGRAM_CHAT_ID='@yourchannel'\n"
                    "   or a -100... channel/group ID) or set TELEGRAM_CHAT_IDS with multiple targets."
                )
    confirm = input("\nSend to Telegram? (y/n): ").strip().lower()
    if confirm != "y":
        print("\nAborted.")
        input("\nPress Enter...")
        return
    # Send message
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        ok = 0
        fail = 0
        for chat_id in chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            try:
                response = requests.post(url, json=payload, timeout=15)
                if response.status_code == 200:
                    ok += 1
                else:
                    fail += 1
                    print(f"\n❌ Telegram error for chat_id={chat_id}: {response.text}")
            except Exception as e:
                fail += 1
                print(f"\n❌ Telegram send failed for chat_id={chat_id}: {e}")
        print(f"\n[✓] Sent to {ok} chats. {fail} failed.")
    except Exception as e:
        print(f"\n❌ Telegram send error: {e}")
    input("\nPress Enter...")
def parse_cbb_top7_from_report(report_path: str):
    """Parse the CBB export report and extract the top 7 picks from BEST OVERALL PICKS section."""
    picks = []
    with open(report_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    in_best = False
    current = {}
    for line in lines:
        if 'BEST OVERALL PICKS' in line:
            in_best = True
            continue
        if in_best and line.strip().startswith('╔'):
            break
        if in_best and line.strip().startswith(str(len(picks)+1)+'.'):
            # New pick
            if current:
                picks.append(current)
                if len(picks) == 7:
                    break
            current = {'desc': line.strip()}
        elif in_best and line.strip().startswith('📊'):
            current['stat'] = line.strip()
        elif in_best and line.strip().startswith('📈'):
            current['mean'] = line.strip()
        elif in_best and line.strip().startswith('💡'):
            current['note'] = line.strip()
    if current and len(picks) < 7:
        picks.append(current)
    return picks[:7]
"""
CBB Pipeline Menu Integration
------------------------------
Wires CBB into the main menu system when enabled in sport_registry.
"""

import sys
from pathlib import Path


def is_cbb_enabled() -> bool:
    """Check if CBB is enabled in sport registry."""
    import json
    registry_path = Path(__file__).parent.parent.parent / "config" / "sport_registry.json"
    
    try:
        with open(registry_path) as f:
            registry = json.load(f)
            return registry.get("CBB", {}).get("enabled", False)
    except FileNotFoundError:
        return False


def get_cbb_menu_options() -> list:
    """
    Return CBB menu options for integration.
    
    Returns list of (key, label, function) tuples.
    """
    if not is_cbb_enabled():
        return []
    
    return [
        ("C", "[CBB] College Basketball (PRODUCTION v1.0)", run_cbb_menu),
    ]


def run_cbb_menu():
    """Display CBB submenu."""
    print("\n" + "="*50)
    print("[CBB] COLLEGE BASKETBALL — PRODUCTION v1.0")
    print("="*50)
    print("\n[i] Market Gate: 12% | L10 Blend: 0.40 | Strict Caps")
    print()
    
    options = [
        ("1", "Run Daily Pipeline (dry-run)", run_daily_dry),
        ("2", "Run Daily Pipeline (full)", run_daily_full),
        ("3", "Check Session State", show_session_state),
        ("4", "Toggle Unders-Only Mode", toggle_unders_only),
        ("5", "View Exposure Summary", show_exposure),
        ("6", "Force Season Regime", force_regime),
        ("T", "Send Top 7 Picks to Telegram", send_cbb_top7_to_telegram),
        ("B", "Back to Main Menu", None),
    ]
    
    for key, label, _ in options:
        print(f"  [{key}] {label}")
    
    print()
    choice = input("Select option: ").strip().upper()
    
    for key, _, func in options:
        if choice == key:
            if func:
                func()
            return
    
    print("Invalid option.")


def run_daily_dry():
    """Run CBB daily pipeline in dry-run mode."""
    from sports.cbb.run_daily import main as run_daily_main
    print("\n🔄 Running CBB daily pipeline (DRY RUN)...")
    run_daily_main(dry_run=True)


def run_daily_full():
    """Run CBB daily pipeline in full mode."""
    from sports.cbb.run_daily import main as run_daily_main
    
    confirm = input("\n[!] Run FULL CBB pipeline? This will write outputs. (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return
    
    print("\n🔄 Running CBB daily pipeline (FULL)...")
    run_daily_main(dry_run=False)


def show_session_state():
    """Display current session state."""
    try:
        from sports.cbb.runs import get_session_summary
        summary = get_session_summary()
        
        print("\n📊 CBB Session State")
        print("-" * 30)
        print(f"  Date: {summary['date'] or 'Not started'}")
        print(f"  Record: {summary['record']}")
        print(f"  Net Units: {summary['net_units']:+.2f}u")
        print(f"  Current Streak: {summary['current_streak']}")
        print(f"  Unders-Only: {'✅ ACTIVE' if summary['unders_only'] else '❌ OFF'}")
        print(f"  Bankroll Policy: {summary['bankroll_policy']}")
        
    except Exception as e:
        print(f"\n❌ Error loading state: {e}")


def toggle_unders_only():
    """Toggle unders-only mode."""
    try:
        from sports.cbb.runs import is_unders_only, force_unders_only, clear_unders_only
        
        current = is_unders_only()
        print(f"\nCurrent: Unders-Only is {'ACTIVE' if current else 'OFF'}")
        
        if current:
            confirm = input("Turn OFF unders-only mode? (y/N): ")
            if confirm.lower() == 'y':
                clear_unders_only()
                print("✅ Unders-only mode CLEARED.")
        else:
            reason = input("Reason for enabling unders-only (or Enter to cancel): ").strip()
            if reason:
                force_unders_only(reason)
                print(f"✅ Unders-only mode ACTIVATED: {reason}")
            else:
                print("Cancelled.")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")


def show_exposure():
    """Display exposure summary."""
    try:
        from sports.cbb.runs import get_exposure_summary
        summary = get_exposure_summary()
        
        print("\n💰 CBB Exposure Summary")
        print("-" * 30)
        print(f"  Policy: {summary['policy']}")
        print(f"  Reason: {summary['policy_reason'] or 'N/A'}")
        print(f"  Daily Exposure: {summary['daily_exposure']:.1f}u / {summary['max_daily_exposure']:.1f}u")
        print(f"  Remaining: {summary['remaining']:.1f}u")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


def force_regime():
    """Force a specific season regime."""
    regimes = [
        "EARLY_SEASON",
        "MID_SEASON", 
        "LATE_SEASON",
        "CONFERENCE_TOURNAMENT",
        "NCAA_TOURNAMENT"
    ]
    
    print("\n📅 Season Regimes:")
    for i, regime in enumerate(regimes, 1):
        print(f"  [{i}] {regime}")
    
    choice = input("\nSelect regime (or Enter to auto-detect): ").strip()
    
    if not choice:
        from sports.cbb.edges.edge_gates import detect_season_regime
        regime = detect_season_regime()
        print(f"\n✅ Auto-detected regime: {regime}")
    elif choice.isdigit() and 1 <= int(choice) <= len(regimes):
        regime = regimes[int(choice) - 1]
        print(f"\n✅ Forced regime: {regime}")
        # Would need to persist this somewhere for actual use
    else:
        print("Invalid choice.")


# Export for main menu integration
__all__ = ['is_cbb_enabled', 'get_cbb_menu_options', 'run_cbb_menu']
