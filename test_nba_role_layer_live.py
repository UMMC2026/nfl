"""
Test NBA Role Layer with actual IND vs ATL slate data
Shows what role normalization would apply to real picks
"""

import json
from pathlib import Path
from nba.role_scheme_normalizer import RoleSchemeNormalizer, format_normalization_report

def main():
    print("=" * 80)
    print("NBA ROLE LAYER - LIVE TEST WITH IND vs ATL SLATE")
    print("=" * 80)
    print()
    
    # Load the actual slate data
    slate_path = Path("outputs/IND_ATL1262026_USERPASTE_20260126.json")
    if not slate_path.exists():
        print(f"❌ Slate file not found: {slate_path}")
        return
    
    slate_data = json.loads(slate_path.read_text())
    picks = slate_data.get("plays", [])
    
    print(f"📊 Loaded {len(picks)} picks from slate")
    print()
    
    # Load player stats (simulated - in real pipeline this comes from stats cache)
    # For this demo, we'll use known player stats
    player_stats = {
        "Pascal Siakam": {
            "minutes_l10_avg": 34.2,
            "minutes_l10_std": 3.1,
            "usage_rate_l10": 28.5,
            "team": "IND",
            "opponent": "UNK"
        },
        "Jalen Johnson": {
            "minutes_l10_avg": 34.8,
            "minutes_l10_std": 4.2,
            "usage_rate_l10": 24.3,
            "team": "ATL",
            "opponent": "IND"
        },
        "Onyeka Okongwu": {
            "minutes_l10_avg": 28.6,
            "minutes_l10_std": 6.8,
            "usage_rate_l10": 18.2,
            "team": "ATL",
            "opponent": "IND"
        },
        "CJ McCollum": {
            "minutes_l10_avg": 24.3,
            "minutes_l10_std": 8.5,
            "usage_rate_l10": 22.4,
            "team": "ATL",
            "opponent": "IND"
        },
        "Luke Kennard": {
            "minutes_l10_avg": 18.2,
            "minutes_l10_std": 7.9,
            "usage_rate_l10": 16.8,
            "team": "ATL",
            "opponent": "IND"
        },
        "Andrew Nembhard": {
            "minutes_l10_avg": 32.4,
            "minutes_l10_std": 3.8,
            "usage_rate_l10": 19.5,
            "team": "IND",
            "opponent": "UNK"
        },
        "T.J. McConnell": {
            "minutes_l10_avg": 22.1,
            "minutes_l10_std": 5.2,
            "usage_rate_l10": 15.3,
            "team": "IND",
            "opponent": "UNK"
        },
    }
    
    # Initialize normalizer
    normalizer = RoleSchemeNormalizer()
    
    # Get unique players from slate
    players_in_slate = set()
    for pick in picks:
        player = pick.get("player", "")
        if player:
            players_in_slate.add(player)
    
    print(f"🎯 Testing {len(players_in_slate)} unique players")
    print()
    print("=" * 80)
    
    # Analyze each player
    results = []
    for player_name in sorted(players_in_slate):
        if player_name not in player_stats:
            print(f"\n⚠️  {player_name}: No stats available (skipped)")
            continue
        
        stats = player_stats[player_name]
        
        # Run normalization
        result = normalizer.normalize(
            player_name=player_name,
            team=stats["team"],
            opponent=stats["opponent"],
            minutes_l10_avg=stats["minutes_l10_avg"],
            minutes_l10_std=stats["minutes_l10_std"],
            usage_rate_l10=stats["usage_rate_l10"],
            game_context={"spread": 0.0}  # Simulated neutral spread
        )
        
        results.append((player_name, result))
        
        # Display result
        print()
        print("─" * 80)
        print(f"PLAYER: {player_name}")
        print("─" * 80)
        print(f"  Archetype: {result.archetype.value}")
        print(f"  Base Confidence Cap: {result.archetype.value} → {_get_archetype_cap(result.archetype.value)}%")
        print(f"  Applied Adjustment: {result.confidence_cap_adjustment:+.1f}%")
        print(f"  Final Effective Cap: {_get_archetype_cap(result.archetype.value) + result.confidence_cap_adjustment:.1f}%")
        print()
        print(f"  Parameter Adjustments:")
        print(f"    Minutes:  {stats['minutes_l10_avg']:.1f} → {stats['minutes_l10_avg'] * result.minutes_adjustment:.1f} ({result.minutes_adjustment:.1%})")
        print(f"    Variance: {stats['minutes_l10_std']:.1f} → {stats['minutes_l10_std'] * result.variance_adjustment:.1f} ({result.variance_adjustment:.1%})")
        print(f"    Usage:    {stats['usage_rate_l10']:.1f}% → {stats['usage_rate_l10'] * result.usage_adjustment:.1f}% ({result.usage_adjustment:.1%})")
        print()
        print(f"  Flags ({len(result.flags)}):")
        if result.flags:
            for flag in result.flags:
                print(f"    - {flag}")
        else:
            print(f"    (none - most stable profile)")
        print()
        print(f"  Metadata:")
        for key, value in result.metadata.items():
            print(f"    {key}: {value}")
    
    # Summary statistics
    print()
    print("=" * 80)
    print("SUMMARY: ARCHETYPE DISTRIBUTION")
    print("=" * 80)
    
    archetypes = {}
    for player_name, result in results:
        arch = result.archetype.value
        if arch not in archetypes:
            archetypes[arch] = []
        archetypes[arch].append(player_name)
    
    for archetype, players in sorted(archetypes.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{archetype} ({len(players)} players):")
        for player in players:
            print(f"  - {player}")
    
    # Impact analysis
    print()
    print("=" * 80)
    print("IMPACT ANALYSIS")
    print("=" * 80)
    
    high_penalty = [r for r in results if r[1].confidence_cap_adjustment <= -10]
    moderate_penalty = [r for r in results if -10 < r[1].confidence_cap_adjustment <= -5]
    low_penalty = [r for r in results if -5 < r[1].confidence_cap_adjustment <= 0]
    no_penalty = [r for r in results if r[1].confidence_cap_adjustment == 0]
    
    print(f"\n🔴 HIGH PENALTY (≤-10%): {len(high_penalty)} players")
    for player_name, result in high_penalty:
        print(f"  {player_name}: {result.confidence_cap_adjustment:+.1f}% ({result.archetype.value})")
    
    print(f"\n🟡 MODERATE PENALTY (-10% to -5%): {len(moderate_penalty)} players")
    for player_name, result in moderate_penalty:
        print(f"  {player_name}: {result.confidence_cap_adjustment:+.1f}% ({result.archetype.value})")
    
    print(f"\n🟢 LOW PENALTY (-5% to 0%): {len(low_penalty)} players")
    for player_name, result in low_penalty:
        print(f"  {player_name}: {result.confidence_cap_adjustment:+.1f}% ({result.archetype.value})")
    
    print(f"\n✅ NO PENALTY (0%): {len(no_penalty)} players")
    for player_name, result in no_penalty:
        print(f"  {player_name}: {result.confidence_cap_adjustment:+.1f}% ({result.archetype.value})")
    
    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("📋 NEXT STEPS:")
    print("   1. This shows what the Role Layer WOULD do in daily_pipeline.py")
    print("   2. To see it in production, run:")
    print("      .venv\\Scripts\\python.exe daily_pipeline.py --league NBA --input-file <hydrated_picks.json>")
    print("   3. Output will include nba_role_archetype, nba_confidence_cap_adjustment, nba_role_flags")
    print()

def _get_archetype_cap(archetype_name: str) -> float:
    """Get base confidence cap for archetype"""
    caps = {
        "PRIMARY_USAGE_SCORER": 72.0,
        "SECONDARY_WING": 70.0,
        "CONNECTOR_STARTER": 68.0,
        "ROLE_PLAYER": 65.0,
        "BENCH_MICROWAVE": 62.0,
        "BIG": 65.0,
        "STAR_GUARD": 70.0,
    }
    return caps.get(archetype_name, 68.0)

if __name__ == "__main__":
    main()
