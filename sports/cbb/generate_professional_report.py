"""
CBB Professional Report Generator
=================================
Generates polished, export-ready reports matching NBA professional format.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Find the workspace root
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
CBB_ROOT = Path(__file__).parent
OUTPUTS_DIR = CBB_ROOT / "outputs"


def load_latest_edges() -> Optional[Dict]:
    """Load the latest CBB edges JSON file."""
    json_files = list(OUTPUTS_DIR.glob("cbb_RISK_FIRST_*.json"))
    if not json_files:
        print("  [!] No CBB edges found in outputs/")
        return None
    
    latest = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"  Loading: {latest.name}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_stat_name(stat: str) -> str:
    """Convert stat code to readable name."""
    stat_map = {
        'points': 'POINTS',
        'rebounds': 'REBOUNDS', 
        'assists': 'ASSISTS',
        '3pm': '3-POINTERS',
        'steals': 'STEALS',
        'blocks': 'BLOCKS',
        'turnovers': 'TURNOVERS',
        'pra': 'PTS+REB+AST',
        'pts+reb': 'PTS+REB',
        'pts+ast': 'PTS+AST',
        'reb+ast': 'REB+AST',
        'pr': 'PTS+REB',
        'pa': 'PTS+AST',
        'ra': 'REB+AST',
    }
    return stat_map.get(stat.lower(), stat.upper())


def get_tier_emoji(tier: str) -> str:
    """Get emoji for tier."""
    tier_map = {
        'SLAM': '🔥',
        'STRONG': '✅',
        'LEAN': '📊',
        'SKIP': '⚠️',
        'NO_PLAY': '❌',
    }
    return tier_map.get(tier.upper(), '•')

def has_real_opponent(edge: Dict) -> bool:
    """Return True if edge has a non-placeholder opponent value.

    Governance: until schedule/opponent mapping is reliable, any edge with
    missing/"UNK" opponent must not be treated as actionable.
    """
    opp = (edge.get('opponent') or "").strip().upper()
    return bool(opp) and opp != "UNK"


def generate_professional_report(edges_data: Dict) -> str:
    """Generate a professional CBB report."""
    
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # CBB JSON uses 'picks' not 'edges'
    edges = edges_data.get('picks', edges_data.get('edges', []))
    metadata = edges_data.get('metadata', {})
    
    # Governance helper: tier + context (must have real opponent)
    def is_actionable_edge(e: Dict) -> bool:
        tier = e.get('tier', '').upper()
        if tier not in ['SLAM', 'STRONG', 'LEAN']:
            return False
        return has_real_opponent(e)

    # Separate actionable from skipped (context-aware)
    actionable = [e for e in edges if is_actionable_edge(e)]
    skipped = [e for e in edges if not is_actionable_edge(e)]
    
    # Sort actionable by probability (handle both decimal and percentage)
    def get_prob(e):
        p = e.get('probability', 0)
        return p if p > 1 else p * 100
    actionable.sort(key=get_prob, reverse=True)
    
    # Group by team
    teams = {}
    for edge in edges:
        team = edge.get('team', 'UNK')
        if team not in teams:
            teams[team] = {'edges': [], 'roster': {}}
        teams[team]['edges'].append(edge)
    
    # Build report
    lines = []
    
    # ============== HEADER ==============
    lines.append("╔════════════════════════════════════════════════════════════════════╗")
    lines.append("║          PROFESSIONAL CBB ANALYSIS REPORT                          ║")
    lines.append("║                   COLLEGE BASKETBALL                               ║")
    lines.append("╠════════════════════════════════════════════════════════════════════╣")
    lines.append(f"║  Generated: {timestamp:<53}║")
    lines.append("║  System: UNDERDOG ANALYSIS — Risk-First Quant Engine (Poisson)    ║")
    lines.append("╚════════════════════════════════════════════════════════════════════╝")
    lines.append("")
    
    # Governance note for missing opponent context
    missing_context_actionable = [
        e for e in edges
        if e.get('tier', '').upper() in ['SLAM', 'STRONG', 'LEAN'] and not has_real_opponent(e)
    ]
    
    # Count UNK opponents for diagnostics
    total_unk = sum(1 for e in edges if not has_real_opponent(e))
    total_tiered = sum(1 for e in edges if e.get('tier', '').upper() in ['SLAM', 'STRONG', 'LEAN'])

    if missing_context_actionable and not actionable:
        lines.append("╔══════════════════════════════════════════════════════════════════════╗")
        lines.append("║                  ⚠️  NO ACTIONABLE PICKS AVAILABLE                   ║")
        lines.append("╚══════════════════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append(f"   Total picks analyzed: {len(edges)}")
        lines.append(f"   Picks with tier assigned (LEAN/STRONG): {total_tiered}")
        lines.append(f"   Picks with opponent='UNK' (blocked by governance): {total_unk}")
        lines.append("")
        lines.append("   WHY PICKS WERE BLOCKED:")
        lines.append("   CBB analysis requires opponent context for:")
        lines.append("     • KenPom SOS (Strength of Schedule) adjustments")
        lines.append("     • Blowout protection (40% of CBB games)")
        lines.append("     • Conference phase detection (variance multipliers)")
        lines.append("")
        lines.append("   SOLUTIONS:")
        lines.append("   1. Use OddsAPI ingestion (menu option [8])")
        lines.append("      → Automatically extracts opponent from event metadata")
        lines.append("      → Requires ODDS_API_KEY in .env file")
        lines.append("")
        lines.append("   2. Fix paste format to include matchup lines:")
        lines.append("      → Supported formats:")
        lines.append("        • 'DUKE @ UNC' or 'Duke vs North Carolina'")
        lines.append("        • 'vs UNC' or '@ FLA' (opponent only)")
        lines.append("        • 'Player Name (MIA @ FLA)' (in parentheses)")
        lines.append("        • 'MIA/FLA' (slash separator)")
        lines.append("")
        lines.append("   📖 Documentation: sports/cbb/docs/INGESTION_GUIDE.md")
        lines.append("")
    elif missing_context_actionable:
        lines.append(f"⚠️ NOTE: {len(missing_context_actionable)} of {total_tiered} tiered picks removed due to missing opponent context.")
        lines.append(f"   ({total_unk} total picks with opponent='UNK', blocked by governance)")
        lines.append("   Edges with 'UNKNOWN OPPONENT (NO_KENPOM_OPP)' are shown for context only.")
        lines.append("   💡 TIP: Use OddsAPI ingestion (menu [8]) for automatic opponent extraction.")
        lines.append("")

    # ============== STAT KEY ==============
    lines.append("STAT KEY (college basketball):")
    lines.append("   PTS=Points | REB=Rebounds | AST=Assists | STL=Steals | BLK=Blocks | TOV=Turnovers")
    lines.append("   3PM=3-pointers made | PRA=PTS+REB+AST | PR=PTS+REB | PA=PTS+AST | RA=REB+AST")
    lines.append("")
    
    # ============== TOP PLAYS ==============
    lines.append("=" * 70)
    lines.append("🎯 TOP PLAYS — SLATE LEADERS (ALL TEAMS)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("#   PLAYER                 STAT     DIR      LINE    PROB TIER     TEAM ")
    lines.append("─" * 70)
    
    for i, edge in enumerate(actionable[:15], 1):
        player = edge.get('player', 'Unknown')[:20].ljust(20)
        stat = format_stat_name(edge.get('stat', ''))[:8].ljust(8)
        direction = edge.get('direction', 'higher').upper()[:5].ljust(5)
        line = edge.get('line', 0)
        prob = edge.get('probability', 0) * 100 if edge.get('probability', 0) < 1 else edge.get('probability', 0)
        tier = edge.get('tier', 'SKIP').upper()[:6].ljust(6)
        team = edge.get('team', 'UNK')[:4].ljust(4)
        
        lines.append(f"{i:<3} {player} {stat} {direction} {line:>6}   {prob:>4.1f}% {tier} {team}")
    
    lines.append("")
    
    # ============== ACTIONABLE INSIGHTS ==============
    lines.append("=" * 70)
    lines.append("💡 ACTIONABLE INSIGHTS — QUICK REFERENCE")
    lines.append("=" * 70)
    lines.append("")
    
    overs = [e for e in actionable if e.get('direction', '').lower() in ['higher', 'over']]
    unders = [e for e in actionable if e.get('direction', '').lower() in ['lower', 'under']]
    
    lines.append("🔥 OVERS TO CONSIDER:")
    for edge in overs[:7]:
        player = edge.get('player', 'Unknown')
        stat = edge.get('stat', '').upper()
        line = edge.get('line', 0)
        prob = edge.get('probability', 0) * 100 if edge.get('probability', 0) < 1 else edge.get('probability', 0)
        tier = edge.get('tier', '')
        mu = edge.get('player_mean', edge.get('mu', 0))
        if mu == 0:
            mu = edge.get('decision_trace', {}).get('mean', {}).get('lambda', 0)
        lines.append(f"   • {player} {stat} O{line} [{tier}] ({prob:.1f}%) — μ={mu:.1f}")
    
    lines.append("")
    lines.append("🔻 UNDERS TO CONSIDER:")
    for edge in unders[:7]:
        player = edge.get('player', 'Unknown')
        stat = edge.get('stat', '').upper()
        line = edge.get('line', 0)
        prob = edge.get('probability', 0) * 100 if edge.get('probability', 0) < 1 else edge.get('probability', 0)
        tier = edge.get('tier', '')
        mu = edge.get('player_mean', edge.get('mu', 0))
        if mu == 0:
            mu = edge.get('decision_trace', {}).get('mean', {}).get('lambda', 0)
        lines.append(f"   • {player} {stat} U{line} [{tier}] ({prob:.1f}%) — μ={mu:.1f}")
    
    lines.append("")
    
    # ============== TEAM BY TEAM ==============
    lines.append("=" * 70)
    lines.append("TEAM-BY-TEAM ANALYSIS")
    lines.append("=" * 70)
    lines.append("")
    
    for team_name in sorted(teams.keys()):
        team_data = teams[team_name]
        team_edges = team_data['edges']
        team_actionable = [e for e in team_edges if is_actionable_edge(e)]
        
        # Find opponent (from first edge with a REAL opponent if available)
        opponent_raw = None
        for e in team_edges:
            opp = (e.get('opponent') or "").strip()
            if opp and opp.upper() != "UNK":
                opponent_raw = opp
                break
        opponent_display = opponent_raw or "UNKNOWN OPPONENT (NO_KENPOM_OPP)"
        
        lines.append("┌" + "─" * 68 + "┐")
        lines.append(f"│  TEAM: {team_name:<12} vs {opponent_display:<46}│")
        lines.append("└" + "─" * 68 + "┘")
        
        # Roster snapshot
        players_seen = {}
        for edge in team_edges:
            player = edge.get('player', 'Unknown')
            if player not in players_seen:
                mu = edge.get('player_mean', edge.get('mu', 0))
                if mu == 0:
                    mu = edge.get('decision_trace', {}).get('mean', {}).get('lambda', 0)
                players_seen[player] = {'mu': mu, 'stat': edge.get('stat', '')}
        
        lines.append(f"   📝 Conference matchup. College tempo and variance apply.")
        lines.append("")
        
        if team_actionable:
            lines.append("   TOP EDGES:")
            lines.append("   " + "─" * 64)
            
            team_actionable.sort(key=lambda x: x.get('probability', 0), reverse=True)
            
            for i, edge in enumerate(team_actionable[:7], 1):
                player = edge.get('player', 'Unknown')[:20].ljust(20)
                stat = format_stat_name(edge.get('stat', ''))[:8].ljust(8)
                direction = edge.get('direction', 'higher').upper()[:5].ljust(5)
                line = edge.get('line', 0)
                prob = edge.get('probability', 0) * 100 if edge.get('probability', 0) < 1 else edge.get('probability', 0)
                tier = edge.get('tier', 'SKIP').upper()[:8].ljust(8)
                
                # Get mu and calculate edge
                mu = edge.get('player_mean', edge.get('mu', 0))
                if mu == 0:
                    mu = edge.get('decision_trace', {}).get('mean', {}).get('lambda', 0)
                sigma = edge.get('sigma', 2.0)
                
                # Calculate edge (distance from line as %)
                edge_pct = abs((mu - line) / line * 100) if line != 0 else 0
                
                lines.append(f"   {i}) {player} {stat} {direction} {line:>5} — {tier} ({prob:>4.1f}%) [μ={mu:.1f}, edge={edge_pct:.1f}%]")
            if team_actionable:
                top_edge = team_actionable[0]
                commentary = top_edge.get('ai_commentary', '')
                if commentary:
                    lines.append("")
                    lines.append(f"      💡 {commentary[:100]}...")
        else:
            lines.append("   No actionable edges for this team.")
        
        lines.append("")
    
    # ============== STAT BREAKDOWN ==============
    lines.append("=" * 70)
    lines.append("📊 STAT CATEGORY BREAKDOWN")
    lines.append("=" * 70)
    lines.append("")
    
    # Group by stat
    stats = {}
    for edge in edges:
        stat = edge.get('stat', 'other').lower()
        if stat not in stats:
            stats[stat] = []
        stats[stat].append(edge)
    
    for stat_name in sorted(stats.keys()):
        stat_edges = stats[stat_name]
        actionable_stat = [e for e in stat_edges if is_actionable_edge(e)]
        avg_prob = sum(e.get('probability', 0) for e in stat_edges) / len(stat_edges) if stat_edges else 0
        if avg_prob < 1:
            avg_prob *= 100
        
        display_stat = format_stat_name(stat_name)
        lines.append(f"   {display_stat:<12} {len(stat_edges):>3} picks | {len(actionable_stat):>2} actionable | avg conf: {avg_prob:>5.1f}%")
    
    lines.append("")
    
    # ============== DETAILED PICK ANALYSIS ==============
    if actionable:
        lines.append("=" * 70)
        lines.append("🔬 DETAILED PICK ANALYSIS — ACTIONABLE PLAYS")
        lines.append("=" * 70)
        lines.append("")
        
        for i, edge in enumerate(actionable, 1):
            player = edge.get('player', 'Unknown')
            team = edge.get('team', 'UNK')
            # Normalize opponent display: hide internal 'UNK' sentinel from report readers
            raw_opp = (edge.get('opponent') or "").strip()
            opponent = raw_opp if raw_opp and raw_opp.upper() != "UNK" else "UNKNOWN OPPONENT (NO_KENPOM_OPP)"
            stat = edge.get('stat', '').upper()
            direction = edge.get('direction', 'higher')
            line = edge.get('line', 0)
            prob = edge.get('probability', 0) * 100 if edge.get('probability', 0) < 1 else edge.get('probability', 0)
            tier = edge.get('tier', 'SKIP').upper()
            
            # Get trace data
            trace = edge.get('decision_trace', {})
            mean_trace = trace.get('mean', {})
            # Prefer filtered mean if present
            filtered_mu = edge.get('filtered_mean')
            raw_mu = edge.get('player_mean', mean_trace.get('lambda', 0))
            mu = filtered_mu if filtered_mu is not None else raw_mu
            mean_source = 'Filtered (Kalman/Bayesian)' if filtered_mu is not None else edge.get('mean_source', mean_trace.get('mean_source', 'ESPN'))
            confidence_flag = edge.get('confidence_flag', mean_trace.get('confidence_flag', 'OK'))
            
            # Poisson trace
            poisson = trace.get('poisson', {})
            raw_prob = poisson.get('raw_prob', edge.get('raw_probability', prob/100))
            if raw_prob < 1:
                raw_prob *= 100
            
            # Caps
            caps = trace.get('caps', {})
            stat_cap = caps.get('stat_cap', 0.75) * 100
            global_cap = caps.get('global_cap', 0.79) * 100
            cap_hit = caps.get('cap_hit', None)
            
            # SDG info
            sdg_passed = edge.get('sdg_passed', False)
            sdg_reasons = edge.get('sdg_reasons', [])
            
            # Calculate Z-score
            sigma = 2.0  # Default for Poisson
            z_score = (line - mu) / sigma if sigma > 0 else 0
            
            # Calculate edge %
            edge_pct = abs((mu - line) / line * 100) if line != 0 else 0
            
            dir_word = "OVER" if direction.lower() in ['higher', 'over'] else "UNDER"
            dir_arrow = "▲" if dir_word == "OVER" else "▼"
            
            lines.append(f"┌{'─'*68}┐")
            lines.append(f"│  #{i} {player} ({team}) vs {opponent:<42}│")
            lines.append(f"└{'─'*68}┘")
            lines.append(f"   {dir_arrow} {stat} {dir_word} {line}   |   [{tier}] {prob:.1f}%")
            
            # Game context (spread/total) if available
            spread = edge.get('spread')
            total = edge.get('total')
            matchup = edge.get('matchup')
            if spread is not None or total is not None:
                game_context = []
                if matchup:
                    game_context.append(matchup)
                if spread is not None:
                    game_context.append(f"Spread: {spread:+.1f}")
                if total is not None:
                    game_context.append(f"Total: {total:.1f}")
                lines.append(f"   🏀 Game: {' | '.join(game_context)}")
            
            lines.append("")
            lines.append(f"   📊 MODEL PROJECTION:")
            lines.append(f"      • Player Mean (λ): {mu:.2f} ({mean_source})")
            if filtered_mu is not None:
                lines.append(f"      • Raw Mean: {raw_mu:.2f} (pre-filter)")
            lines.append(f"      • Confidence: {confidence_flag}")
            lines.append(f"      • Line: {line} | Gap: {edge_pct:.1f}% {'above' if line > mu else 'below'} mean")
            lines.append(f"      • Z-Score: {z_score:+.2f}")
            lines.append("")
            lines.append(f"   🔢 PROBABILITY TRACE:")
            lines.append(f"      • Raw Poisson: {raw_prob:.1f}%")
            lines.append(f"      • Stat Cap: {stat_cap:.0f}% | Global Cap: {global_cap:.0f}%")
            if cap_hit:
                lines.append(f"      • Cap Applied: {cap_hit}")
            lines.append(f"      • Final Probability: {prob:.1f}%")
            lines.append("")
            lines.append(f"   ✅ DECISION:")
            lines.append(f"      • Tier: {tier}")
            lines.append(f"      • SDG Status: {'PASS ✓' if sdg_passed else 'FAIL (variance concerns)'}")
            if sdg_reasons:
                lines.append(f"      • Notes: {', '.join(sdg_reasons[:2])}")
            lines.append("")
    
    # ============== SLATE SUMMARY ==============
    lines.append("=" * 70)
    lines.append("SLATE SUMMARY STATISTICS")
    lines.append("=" * 70)
    lines.append("")
    
    total = len(edges)
    lines.append(f"Total Props Analyzed: {total}")
    lines.append("")
    
    # Tier distribution
    tier_counts = {}
    for edge in edges:
        tier = edge.get('tier', 'SKIP').upper()
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    lines.append("Tier Distribution:")
    for tier, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total > 0 else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"   {tier:<12} {bar} {count:>3} ({pct:.1f}%)")
    
    lines.append("")
    
    # Direction bias
    overs_count = len([e for e in edges if e.get('direction', '').lower() in ['higher', 'over']])
    unders_count = len([e for e in edges if e.get('direction', '').lower() in ['lower', 'under']])
    total_dir = overs_count + unders_count
    over_pct = overs_count / total_dir * 100 if total_dir > 0 else 50
    under_pct = unders_count / total_dir * 100 if total_dir > 0 else 50
    
    lines.append(f"Direction Bias: {overs_count} OVER / {unders_count} UNDER ({over_pct:.1f}% / {under_pct:.1f}%)")
    lines.append("")
    
    # ============== PARLAY GUIDE ==============
    if len(actionable) >= 3:
        lines.append("=" * 70)
        lines.append("🎲 PARLAY CONSTRUCTION GUIDE")
        lines.append("=" * 70)
        lines.append("")
        
        lines.append("DIVERSIFICATION POOLS:")
        for stat_name, stat_edges in sorted(stats.items()):
            actionable_stat = [e for e in stat_edges if is_actionable_edge(e)]
            if actionable_stat:
                actionable_stat.sort(key=lambda x: x.get('probability', 0), reverse=True)
                best = actionable_stat[0].get('player', 'Unknown')
                display_stat = format_stat_name(stat_name)
                lines.append(f"   {display_stat:<12} {len(actionable_stat):>2} picks (best: {best})")
        
        lines.append("")
        
        # Sample parlay
        if len(actionable) >= 3:
            top_3 = actionable[:3]
            lines.append("SAMPLE 3-LEG POWER PLAY:")
            lines.append("   (select from different stats for diversification)")
            
            combined_prob = 1.0
            for i, edge in enumerate(top_3, 1):
                player = edge.get('player', 'Unknown')
                stat = edge.get('stat', '').upper()
                direction = 'OVER' if edge.get('direction', '').lower() in ['higher', 'over'] else 'UNDER'
                line = edge.get('line', 0)
                prob = edge.get('probability', 0)
                if prob > 1:
                    prob = prob / 100
                combined_prob *= prob
                lines.append(f"   {i}. {player} {stat} {direction} {line} ({prob*100:.1f}%)")
            
            lines.append("")
            lines.append(f"   Combined probability: {combined_prob*100:.1f}%")
            lines.append("   3-leg POWER payout: 6x")
            ev = combined_prob * 6 - 1
            lines.append(f"   Expected value: {ev:+.2f} units")
        
        lines.append("")
    
    # ============== GOVERNANCE ==============
    lines.append("=" * 70)
    lines.append("GOVERNANCE & DISCLAIMER")
    lines.append("=" * 70)
    lines.append("")
    lines.append("This report is generated by a risk-first quantitative analysis system.")
    lines.append("CBB uses POISSON probability model with stricter confidence caps than NBA.")
    lines.append("")
    lines.append("CBB-SPECIFIC NOTES:")
    lines.append("• NO SLAM tier available (max tier = STRONG @ 70%)")
    lines.append("• Global cap: 79% (vs NBA 85%)")
    lines.append("• College variance is HIGHER than NBA — expect more swings")
    lines.append("• Conference play has different dynamics than non-conference")
    lines.append("• 'UNKNOWN OPPONENT (NO_KENPOM_OPP)' = opponent/schedule not in KenPom set (non-D1/exhibition/unknown)")
    lines.append("")
    lines.append("RISK MANAGEMENT:")
    lines.append("• Never exceed 2% of bankroll on a single CBB entry")
    lines.append("• Parlays carry exponentially higher variance")
    lines.append("• Past performance does not guarantee future results")
    lines.append("")
    lines.append("For entertainment purposes only. Gamble responsibly.")
    lines.append("")
    
    # ============== FOOTER ==============
    report_id = f"CBB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    lines.append("─" * 70)
    lines.append(f"Report ID: {report_id}")
    lines.append("System: UNDERDOG ANALYSIS v2.0 — Risk-First Quant Engine (Poisson)")
    lines.append("─" * 70)
    
    return "\n".join(lines)


def export_report(report: str, filename: Optional[str] = None) -> str:
    """Export report to file."""
    if not filename:
        filename = f"CBB_PROFESSIONAL_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Save to both CBB outputs and main outputs
    cbb_path = OUTPUTS_DIR / filename
    main_path = WORKSPACE_ROOT / "outputs" / filename
    
    # Ensure directories exist
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (WORKSPACE_ROOT / "outputs").mkdir(parents=True, exist_ok=True)
    
    for path in [cbb_path, main_path]:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"  ✓ Saved: {path}")
    
    return str(main_path)


def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print("  CBB PROFESSIONAL REPORT GENERATOR")
    print("=" * 70 + "\n")
    
    # Load edges
    edges_data = load_latest_edges()
    if not edges_data:
        print("  [!] No edges data available. Run analysis first.")
        return
    
    # Generate report
    print("\n  Generating professional report...")
    report = generate_professional_report(edges_data)
    
    # Export
    print("\n  Exporting...")
    output_path = export_report(report)
    
    print(f"\n  ✅ DONE! Report saved to:")
    print(f"     {output_path}")
    
    # Show preview
    print("\n" + "=" * 70)
    print("  REPORT PREVIEW (first 50 lines):")
    print("=" * 70)
    for line in report.split("\n")[:50]:
        print(f"  {line}")
    print("  ...")
    print(f"\n  [Full report: {output_path}]")


if __name__ == "__main__":
    main()
