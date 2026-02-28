"""
NBA SYSTEM DIAGNOSTIC - Full Health Check
==========================================
Checks all components for drift, errors, and proper configuration
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("  NBA SYSTEM DIAGNOSTIC - Full Health Check")
print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

errors = []
warnings = []
passed = []

# =============================================================================
# 1. TEAM CONTEXT - Check for stale/incorrect data
# =============================================================================
print("\n[1] TEAM CONTEXT CHECK...")

try:
    from nba_team_context import NBA_TEAM_CONTEXT
    
    # Check ATL - should NOT mention Trae Young
    atl = NBA_TEAM_CONTEXT.get("ATL")
    if atl:
        if "Trae Young" in atl.notes:
            errors.append("ATL team context still mentions Trae Young (TRADED to SAS)")
        else:
            passed.append("ATL context updated (no Trae Young)")
        print(f"   ATL notes: {atl.notes[:60]}...")
    else:
        errors.append("ATL not found in NBA_TEAM_CONTEXT")
    
    # Check SAS - should mention Trae Young
    sas = NBA_TEAM_CONTEXT.get("SAS")
    if sas:
        if "Trae" in sas.notes:
            passed.append("SAS context includes Trae Young")
        else:
            warnings.append("SAS context may need update to include Trae Young")
        print(f"   SAS notes: {sas.notes[:60]}...")
    else:
        errors.append("SAS not found in NBA_TEAM_CONTEXT")
    
    # Check all 30 teams exist
    expected_teams = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
                      "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
                      "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"]
    missing = [t for t in expected_teams if t not in NBA_TEAM_CONTEXT]
    if missing:
        errors.append(f"Missing teams in context: {missing}")
    else:
        passed.append(f"All 30 NBA teams present in context")
        
except Exception as e:
    errors.append(f"Team context import failed: {e}")

# =============================================================================
# 2. STAT MAPPING - Verify NBA stat keys
# =============================================================================
print("\n[2] STAT MAPPING CHECK...")

try:
    from ufa.ingest.stat_map import NBA_STAT_KEYS
    
    required_stats = ["points", "rebounds", "assists", "3pm", "pts+reb+ast", "pts+ast"]
    missing_stats = [s for s in required_stats if s not in NBA_STAT_KEYS]
    
    if missing_stats:
        errors.append(f"Missing stat keys: {missing_stats}")
    else:
        passed.append(f"All required stat keys present ({len(NBA_STAT_KEYS)} total)")
    
    # Check for dunks (we added it)
    if "dunks" in NBA_STAT_KEYS:
        warnings.append("dunks stat uses FGM proxy (not accurate for dunks)")
    
    print(f"   Available stats: {list(NBA_STAT_KEYS.keys())[:10]}...")
    
except Exception as e:
    errors.append(f"Stat mapping import failed: {e}")

# =============================================================================
# 3. NBA API - Test data hydration
# =============================================================================
print("\n[3] NBA API HYDRATION CHECK...")

try:
    from ufa.ingest.hydrate import hydrate_recent_values
    
    # Test with known player
    test_player = "Giannis Antetokounmpo"
    values = hydrate_recent_values("NBA", test_player, "points", nba_season="2024-25")
    
    if values and len(values) >= 5:
        avg = sum(values) / len(values)
        passed.append(f"NBA API working - {test_player} avg {avg:.1f} pts ({len(values)} games)")
        print(f"   {test_player}: {values[:5]}... (avg: {avg:.1f})")
    else:
        errors.append(f"NBA API returned insufficient data for {test_player}")
        
except Exception as e:
    errors.append(f"NBA API hydration failed: {e}")

# =============================================================================
# 4. PROBABILITY ENGINE - Test calculations
# =============================================================================
print("\n[4] PROBABILITY ENGINE CHECK...")

try:
    from ufa.analysis.prob import prob_hit
    
    # Test with known values
    test_values = [25, 28, 22, 30, 27]  # avg = 26.4
    
    # Over 24.5 should be high probability
    p_over = prob_hit(24.5, "higher", recent_values=test_values)
    # Under 24.5 should be low probability  
    p_under = prob_hit(24.5, "lower", recent_values=test_values)
    
    if p_over > 0.5 and p_under < 0.5:
        passed.append(f"Probability engine working correctly (O24.5={p_over:.1%}, U24.5={p_under:.1%})")
        print(f"   Test values avg=26.4: O24.5={p_over:.1%}, U24.5={p_under:.1%}")
    else:
        errors.append(f"Probability calculation unexpected: O={p_over}, U={p_under}")
        
    # Verify probabilities sum to ~1
    if abs(p_over + p_under - 1.0) > 0.01:
        warnings.append(f"Probabilities don't sum to 1: {p_over + p_under}")
        
except Exception as e:
    errors.append(f"Probability engine failed: {e}")

# =============================================================================
# 5. PAYOUT TABLES - Verify structure
# =============================================================================
print("\n[5] PAYOUT TABLES CHECK...")

try:
    from ufa.analysis.payouts import power_table, flex_table
    
    pt = power_table()
    ft = flex_table()
    
    if hasattr(pt, 'payout_units') and pt.payout_units:
        passed.append(f"Power table loaded ({len(pt.payout_units)} leg options)")
        print(f"   Power table legs: {list(pt.payout_units.keys())}")
    else:
        errors.append("Power table missing payout_units")
        
    if hasattr(ft, 'payout_units') and ft.payout_units:
        passed.append(f"Flex table loaded ({len(ft.payout_units)} leg options)")
    else:
        errors.append("Flex table missing payout_units")
        
except Exception as e:
    errors.append(f"Payout tables failed: {e}")

# =============================================================================
# 6. ENTRY BUILDER - Test optimization
# =============================================================================
print("\n[6] ENTRY BUILDER CHECK...")

try:
    from ufa.optimizer.entry_builder import build_entries
    from ufa.analysis.payouts import power_table
    
    test_picks = [
        {"player": "Player A", "team": "ATL", "stat": "points", "p_hit": 0.65},
        {"player": "Player B", "team": "MIL", "stat": "points", "p_hit": 0.62},
        {"player": "Player C", "team": "ATL", "stat": "rebounds", "p_hit": 0.58},
        {"player": "Player D", "team": "MIL", "stat": "assists", "p_hit": 0.55},
    ]
    
    entries = build_entries(
        picks=test_picks,
        payout_table=power_table(),
        legs=3,
        min_teams=2,
        max_player_legs=1
    )
    
    if entries and len(entries) > 0:
        passed.append(f"Entry builder working ({len(entries)} entries generated)")
        print(f"   Generated {len(entries)} entries, top EV: {entries[0]['ev_units']:.3f}")
    else:
        errors.append("Entry builder returned no entries")
        
except Exception as e:
    errors.append(f"Entry builder failed: {e}")

# =============================================================================
# 7. OLLAMA / AI INTEGRATION
# =============================================================================
print("\n[7] OLLAMA / AI CHECK...")

try:
    import requests
    
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    if r.status_code == 200:
        models = r.json().get("models", [])
        model_names = [m["name"] for m in models]
        passed.append(f"Ollama running with {len(models)} models")
        print(f"   Available models: {model_names[:5]}")
        
        # Check for deepseek
        if any("deepseek" in m.lower() for m in model_names):
            passed.append("DeepSeek model available")
        else:
            warnings.append("DeepSeek model not found - install with: ollama pull deepseek-r1:1.5b")
    else:
        errors.append(f"Ollama returned status {r.status_code}")
        
except requests.exceptions.ConnectionError:
    errors.append("Ollama not running - start with: ollama serve")
except Exception as e:
    errors.append(f"Ollama check failed: {e}")

# =============================================================================
# 8. SETTINGS CHECK
# =============================================================================
print("\n[8] SETTINGS CHECK...")

try:
    settings_path = Path(".analyzer_settings.json")
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        print(f"   Settings: {settings}")
        
        if settings.get("ai_report") == True:
            passed.append("AI Report ENABLED")
        else:
            warnings.append("AI Report DISABLED - enable in menu [9] Settings")
            
        if settings.get("soft_gates") == True:
            passed.append("Soft gates enabled")
        if settings.get("quant_modules") == True:
            passed.append("Quant modules enabled")
    else:
        warnings.append("Settings file not found - using defaults")
        
except Exception as e:
    errors.append(f"Settings check failed: {e}")

# =============================================================================
# 9. OUTPUT DIRECTORY CHECK
# =============================================================================
print("\n[9] OUTPUT DIRECTORY CHECK...")

try:
    outputs = Path("outputs")
    if outputs.exists():
        json_files = list(outputs.glob("*.json"))
        txt_files = list(outputs.glob("*.txt"))
        
        # Check for today's files
        today = datetime.now().strftime("%Y%m%d")
        today_files = [f for f in json_files + txt_files if today in f.name]
        
        passed.append(f"Outputs directory: {len(json_files)} JSON, {len(txt_files)} TXT files")
        if today_files:
            passed.append(f"Today's outputs: {len(today_files)} files")
            print(f"   Recent: {[f.name for f in today_files[:3]]}")
        else:
            warnings.append("No outputs generated today")
    else:
        errors.append("Outputs directory missing")
        
except Exception as e:
    errors.append(f"Output check failed: {e}")

# =============================================================================
# 10. ROSTER VALIDATION
# =============================================================================
print("\n[10] ROSTER VALIDATION CHECK...")

try:
    from engine.roster_gate import load_roster_map
    
    roster_map = load_roster_map()
    if roster_map and len(roster_map) > 0:
        passed.append(f"Roster map loaded ({len(roster_map)} players)")
        
        # Check if Trae Young is mapped to SAS
        trae_team = roster_map.get("Trae Young")
        if trae_team == "SAS":
            passed.append("Trae Young correctly mapped to SAS")
        elif trae_team == "ATL":
            errors.append("Trae Young still mapped to ATL - roster needs update!")
        elif trae_team:
            warnings.append(f"Trae Young mapped to {trae_team}")
        else:
            warnings.append("Trae Young not in roster map")
            
    else:
        warnings.append("Roster map empty or not loaded")
        
except ImportError:
    warnings.append("Roster gate module not available")
except Exception as e:
    warnings.append(f"Roster validation skipped: {e}")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("  DIAGNOSTIC SUMMARY")
print("=" * 70)

print(f"\n  ✅ PASSED: {len(passed)}")
for p in passed:
    print(f"     • {p}")

print(f"\n  ⚠️  WARNINGS: {len(warnings)}")
for w in warnings:
    print(f"     • {w}")

print(f"\n  ❌ ERRORS: {len(errors)}")
for e in errors:
    print(f"     • {e}")

# Overall status
print("\n" + "-" * 70)
if errors:
    print("  STATUS: ❌ SYSTEM HAS ERRORS - FIX REQUIRED")
elif warnings:
    print("  STATUS: ⚠️  SYSTEM OPERATIONAL WITH WARNINGS")
else:
    print("  STATUS: ✅ SYSTEM HEALTHY - ALL CHECKS PASSED")
print("-" * 70 + "\n")

# Exit code
sys.exit(1 if errors else 0)
