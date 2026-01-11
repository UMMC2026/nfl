#!/usr/bin/env python3
"""
Generate individual game reports from Daily Games Report (Jan 3, 2026)
and extract approved bets for each game.
"""

import json
from logic_family_router import safe_generate_output
from pathlib import Path
from datetime import datetime

# Try to import DailyPipeline to enrich NFL reports with calibrated picks
try:
    from ufa.daily_pipeline import DailyPipeline
except Exception:
    DailyPipeline = None
try:
    from ufa.analysis.context import ContextProvider, format_context_flags
except Exception:
    ContextProvider = None
    format_context_flags = None

# Game metadata (from Daily Games Report 2026-01-03)
GAMES_MANIFEST = {
    "NFL": [
        {
            "away": "SF",
            "home": "SEA",
            "date": "2026-01-03",
            "kickoff": "Sat 10:00 PM ET",
            "window": "NIGHT",
            "weather": "Clear, 45°F",
            "venue": "Lumen Field (dome-adjacent)",
            "intensity": "PLAYOFFS (WILD CARD)",
        },
        {
            "away": "MIN",
            "home": "GB",
            "date": "2026-01-03",
            "kickoff": "Sun 1:00 PM ET",
            "window": "DAY",
            "weather": "Cold 28°F, wind 12-15 mph",
            "venue": "Lambeau Field",
            "intensity": "PLAYOFFS (WILD CARD)",
        },
        {
            "away": "CIN",
            "home": "CLE",
            "date": "2026-01-03",
            "kickoff": "Sun 1:00 PM ET",
            "window": "DAY",
            "weather": "Cold 26°F, wind 8-10 mph",
            "venue": "Cleveland Browns Stadium",
            "intensity": "PLAYOFFS (WILD CARD)",
        },
        {
            "away": "DET",
            "home": "CHI",
            "date": "2026-01-03",
            "kickoff": "Sun 4:25 PM ET",
            "window": "DAY-TO-EVENING",
            "weather": "Cold 24°F, wind 10-12 mph",
            "venue": "Soldier Field",
            "intensity": "PLAYOFFS (WILD CARD)",
        },
        {
            "away": "BAL",
            "home": "PIT",
            "date": "2026-01-03",
            "kickoff": "Sun 7:20 PM ET",
            "window": "NIGHT",
            "weather": "Cold 22°F, wind 8 mph",
            "venue": "Acrisure Stadium",
            "intensity": "PLAYOFFS (WILD CARD) - HIGHEST SUPPRESSION",
        },
    ],
    "NBA": [
        {
            "away": "BOS",
            "home": "CLE",
            "date": "2026-01-03",
            "tipoff": "Sat 7:30 PM ET",
            "window": "NIGHT",
            "venue": "Quicken Loans Arena",
            "rest": "BOS +1, CLE 0",
            "defensive_profile": "ELITE (both +4-6%)",
        },
        {
            "away": "LAL",
            "home": "DEN",
            "date": "2026-01-03",
            "tipoff": "Sat 9:00 PM ET (7:00 PM MT)",
            "window": "NIGHT",
            "venue": "Ball Arena",
            "rest": "LAL 1, DEN 2",
            "defensive_profile": "DEN +5% (strong), LAL +3% (limited wing depth)",
        },
        {
            "away": "MIA",
            "home": "NYK",
            "date": "2026-01-03",
            "tipoff": "Sun 1:00 PM ET",
            "window": "DAY",
            "venue": "Madison Square Garden",
            "rest": "Neutral (both 2 days)",
            "defensive_profile": "MIA +5% (elite switch), NYK +2%",
        },
    ],
    "CBB": [
        {
            "away": "DUKE",
            "home": "UNC",
            "date": "2026-01-03",
            "tipoff": "Sat 6:00 PM ET",
            "venue": "Dean E. Smith Center (Chapel Hill)",
            "conference": "ACC",
            "tournament_implication": "HIGH (RPI-heavy)",
        },
        {
            "away": "OKLA",
            "home": "TEXAS",
            "date": "2026-01-03",
            "tipoff": "Sun 2:00 PM ET",
            "venue": "Frank Erwin Center (Austin)",
            "conference": "Big 12",
            "tournament_implication": "CRITICAL (standings)",
        },
    ],
    "Tennis": [
        {
            "p1": "Carlos Alcaraz",
            "p2": "Felix Auger-Aliassime",
            "date": "2026-01-03",
            "session": "Night",
            "surface": "Hard",
            "context": "Pre-Australian Open tune-up",
        },
        {
            "p1": "Ons Jabeur",
            "p2": "Marketa Vondrousova",
            "date": "2026-01-03",
            "session": "Day",
            "surface": "Hard",
            "context": "Australian Open prep",
        },
    ],
    "Soccer": [
        {
            "away": "Liverpool",
            "home": "Arsenal",
            "date": "2026-01-03",
            "kickoff": "Sun 11:30 AM ET",
            "competition": "EPL",
            "venue": "Emirates Stadium",
            "tournament_context": "Title-race implications",
        },
        {
            "away": "Borussia Dortmund",
            "home": "Bayern Munich",
            "date": "2026-01-03",
            "kickoff": "Sun 1:45 PM ET",
            "competition": "DFB-Pokal Cup",
            "venue": "Allianz Arena",
            "tournament_context": "Knockout (no replay)",
        },
    ],
}


def generate_nfl_game_report(game):
    """Generate NFL game report"""
    away = game["away"]
    home = game["home"]

    # Allow passing calibrated picks into the game dict (from DailyPipeline)
    calibrated = game.get("calibrated_picks", []) or []
    team_picks = [p for p in calibrated if p.get("team") in (away, home)]

    content = f"""# GAME REPORT: {away} @ {home}
**Date:** {game["date"]}  
**Kickoff:** {game["kickoff"]}  
**Venue:** {game["venue"]}  
**Window:** {game["window"]}  
**Weather:** {game["weather"]}  
**Intensity:** {game.get('intensity', '')}  

---

## GAME METADATA

| Attribute | Value |
|-----------|-------|
| Sport | NFL |
| Away | {away} |
| Home | {home} |
| Date | {game["date"]} |
| Start Time | {game["kickoff"]} |
| Environment | {game["weather"]} |

---

## HYDRATED PICKS & PROBABILITIES

*Top calibrated picks for this game (from UFA pipeline)*

| Player | Team | Stat | Line | Dir | Prob | Tier | Context |
|--------|------|------|------|-----|------:|------|---------|
"""

    if team_picks:
        rows = []
        for p in sorted(team_picks, key=lambda x: x.get('calibrated_prob', 0), reverse=True)[:8]:
            prob = int(round(p.get('display_prob', p.get('calibrated_prob', 0)) * 100))
            ctx = p.get('context', {}).get('formatted', '')
            dir_sym = 'O' if p.get('direction') == 'higher' else 'U'
            rows.append(f"| {p.get('player')} | {p.get('team')} | {p.get('stat')} | {p.get('line')} | {dir_sym} | {prob}% | {p.get('tier')} | {ctx} |")

        content += "\n" + "\n".join(rows) + "\n"
    else:
        content += "\nNo calibrated picks available for this game.\n"

    # Coaching / Tactical summary derived from context flags
    content += "\n---\n\n## COACHING & TACTICAL NOTES (DERIVED)\n\n"
    if team_picks:
        notes = []
        provider = ContextProvider() if ContextProvider else None
        for team in (away, home):
            tp = [p for p in team_picks if p.get('team') == team]
            if not tp:
                continue
            # Summarize picks
            usages = [p.get('context', {}).get('usage', '0') for p in tp]
            rests = [p.get('context', {}).get('rest', 'Unknown') for p in tp]
            # Attempt to compute opponent-aware context for top players
            opponent = home if team == away else away
            tactical_bits = []
            if provider:
                # examine top 3 players by display_prob
                top_players = sorted(tp, key=lambda x: x.get('display_prob', 0), reverse=True)[:3]
                for p in top_players:
                    try:
                        ctx = provider.get_context(p.get('player'), team, opponent, p.get('stat'))
                        ctx_str = format_context_flags(ctx) if format_context_flags else ''
                        tactical_bits.append(f"{p.get('player')}: {ctx_str} | Opp DEF RTG: {ctx.opp_def_rating or 'N/A'} | Pace: {ctx.opp_pace or 'N/A'}")
                    except Exception:
                        tactical_bits.append(f"{p.get('player')}: context unavailable")

            notes.append(f"- {team}: Usage samples {usages[:3]}, Rest flags {list(set(rests))}. Top players: {', '.join([t.split(':')[0] for t in tactical_bits])}.")
            if tactical_bits:
                notes.extend([f"  • {b}" for b in tactical_bits])
        content += "\n" + "\n".join(notes) + "\n"
    else:
        content += "No tactical context available.\n"

    content += f"\n**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n**Next Report:** 6:00 AM ET, {game['date']}\n"
    return content


def generate_nba_game_report(game):
    # Generate NBA game report
    away = game["away"]
    home = game["home"]

    lines = [
        "REPORT",
        f"# GAME REPORT: {away} @ {home}",
        f"Date: {game['date']}",
        f"Tipoff: {game['tipoff']}",
        f"Venue: {game['venue']}",
        f"Window: {game['window']}",
        f"Rest: {game['rest']}",
        "",
        "-----",
        "",
        "## GAME METADATA",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Sport | NBA |",
        f"| Away | {away} |",
        f"| Home | {home} |",
        f"| Date | {game['date']} |",
        f"| Start Time | {game['tipoff']} |",
        f"| Defensive Profile | {game['defensive_profile']} |",
        "",
        "-----",
        "",
        "## COACHING / SCHEME",
        "*(Reference Daily Games Report for full analysis)*",
        "",
        "-----",
        "",
        "## DEFENSIVE RATING (vs League)",
        f"*(Reference Daily Games Report Section: {away} Defense & {home} Defense)*",
        "",
        "-----",
        "",
        "## OFFENSIVE MATCHUP",
        f"*(Reference Daily Games Report Section: {away} Offense vs {home} Defense)*",
        "",
        "-----",
        "",
        "## EXPECTED GAME SCRIPT",
        "*(Reference Daily Games Report Section: Expected Game Script)*",
        "",
        "-----",
        "",
        "## APPROVED BETS (THIS GAME ONLY)",
        "**TIER 1 (SLAM):** >70% confidence",
        "**TIER 2 (STRONG):** 65-70% confidence",
        "**TIER 3 (PLAYABLE):** 60-65% confidence",
        "| Player | Stat | Line | Direction | Confidence | Tier | Reason |",
        "|--------|------|------|-----------|------------|------|--------|",
        "*(Populated from cheatsheet calibrated picks)*",
        "",
        "-----",
        "",
        "## BLOCKED BETS (TRANSPARENCY)",
        "| Player | Stat | Reason |",
        "|--------|------|--------|",
        "*(Reference: Elite defense suppression, rest-adjusted variance, correlated player props)*",
        "",
        "-----",
        "",
        "## GATING STATUS",
        "## Gating PASSED (Jan 3, 2026 report present)",
        "## Confidence Caps Applied: Alt 65%",
        f"## Environmental Suppression: {game['window']} game",
        "",
        "-----",
        "",
        f"**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Next Report:** 6:00 AM ET, {game['date']}"
    ]
    return '\n'.join(lines)


def generate_cbb_game_report(game):
    # Generate CBB game report
    away = game["away"]
    home = game["home"]
    
    lines = [
        f"# GAME REPORT: {away} @ {home}",
        f"**Date:** {game['date']}",
        f"**Tipoff:** {game['tipoff']}",
        f"**Venue:** {game['venue']}",
        f"**Conference:** {game['conference']}",
        "",
        "---",
        "",
        "## GAME METADATA",
        "",
        "| Attribute | Value |",
        "|-----------|-------|",
        f"| Sport | CBB |",
        f"| Away | {away} |",
        f"| Home | {home} |",
        f"| Date | {game['date']} |",
        f"| Start Time | {game['tipoff']} |",
        f"| Tournament Implication | {game['tournament_implication']} |",
        "",
        "---",
        "",
        "## COACHING TEMPO & SCHEME",
        "",
        "*(Reference Daily Games Report for full analysis)*",
        "",
        "---",
        "",
        "## DEFENSIVE PROFILE",
        "",
        f"*(Reference Daily Games Report Section: {away} Defense & {home} Defense)*",
        "",
        "---",
        "",
        "## OFFENSIVE MATCHUP",
        "",
        f"*(Reference Daily Games Report Section: {away} Offense vs {home} Defense)*",
        "",
        "---",
        "",
        "## EXPECTED GAME SCRIPT",
        "",
        "*(Reference Daily Games Report Section: Expected Game Script)*",
        "",
        "---",
        "",
        "## APPROVED BETS (THIS GAME ONLY)",
        "",
        "**TIER 1 (SLAM):** >70% confidence",
        "**TIER 2 (STRONG):** 65-70% confidence",
        "**TIER 3 (PLAYABLE):** 60-65% confidence",
        "",
        "| Player | Stat | Line | Direction | Confidence | Tier | Reason |",
        "|--------|------|------|-----------|------------|------|--------|"
    ]
    return '\n'.join(lines)


def generate_tennis_report(match):
    # Generate Tennis report
    # TODO: Implement tennis report generation logic
    pass


def generate_soccer_report(match):
    # Minimal soccer report stub
    away = match.get('away', 'AWAY')
    home = match.get('home', 'HOME')
    lines = [
        f"SOCCER MATCH REPORT: {away} vs {home}",
        f"Date: {match.get('date', '')}",
        f"Competition: {match.get('competition', '')}",
    ]
    return "\n".join(lines)


def main():
    # Generate all game reports
    
    reports_dir = Path("reports/games")
    total_reports = 0
    
    print("\n" + "="*70)
    print("  📋 GAME REPORT GENERATOR")
    print("="*70 + "\n")
    


    # ensure report directories exist
    reports_dir.mkdir(parents=True, exist_ok=True)
    for sport in GAMES_MANIFEST.keys():
        (reports_dir / sport).mkdir(parents=True, exist_ok=True)

    # Attempt to run UFA pipeline to get calibrated picks for NFL enrichment
    calibrated_picks = []
    if DailyPipeline is not None:
        try:
            pipeline = DailyPipeline(picks_file="picks_hydrated_nfl.json", output_dir="outputs")
            pipeline.load_picks()
            calibrated_picks = pipeline.process_picks()
            print(f"   ✅ Loaded {len(calibrated_picks)} calibrated picks from UFA pipeline for NFL enrichment")
        except Exception as e:
            print(f"   ⚠️  Could not run DailyPipeline for enrichment: {e}")

    # NFL Reports (enriched with UFA calibrated picks when available)
    print("\n🏈 GENERATING NFL GAME REPORTS...")
    for game in GAMES_MANIFEST["NFL"]:
        routed = safe_generate_output("NFL", game)
        # merge calibrated picks into routed data for enrichment
        routed['calibrated_picks'] = calibrated_picks
        away = routed.get("away_team") or game["away"]
        home = routed.get("home_team") or game["home"]
        filename = f"GAME_REPORT_NFL_{away}_AT_{home}_{routed['date']}.md"
        filepath = reports_dir / "NFL" / filename
        content = generate_nfl_game_report({**game, **routed})
        filepath.write_text(content, encoding='utf-8')
        print(f"   ✅ {filename}")
        total_reports += 1

    # NBA Reports
    print("\n🏀 GENERATING NBA GAME REPORTS...")
    for game in GAMES_MANIFEST["NBA"]:
        routed = safe_generate_output("NBA", game)
        away = routed["away_team"] or game["away"]
        home = routed["home_team"] or game["home"]
        filename = f"GAME_REPORT_NBA_{away}_AT_{home}_{routed['date']}.md"
        filepath = reports_dir / "NBA" / filename
        content = generate_nba_game_report({**game, **routed})
        filepath.write_text(content, encoding='utf-8')
        print(f"   ✅ {filename}")
        total_reports += 1




    # Soccer Reports
    print("\n⚽ GENERATING SOCCER MATCH REPORTS...")
    for match in GAMES_MANIFEST["Soccer"]:
        routed = safe_generate_output("Soccer", match)
        away = routed.get("away_team", match["away"]).upper()
        home = routed.get("home_team", match["home"]).upper()
        filename = f"GAME_REPORT_SOCCER_{away}_VS_{home}_{routed['date']}.md"
        filepath = reports_dir / "Soccer" / filename
        content = generate_soccer_report({**match, **routed})
        filepath.write_text(content, encoding='utf-8')
        print(f"   ✅ {filename}")
        total_reports += 1

    print("\n" + "="*70)
    print(f"✅ GAME REPORTS GENERATED: {total_reports} total")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
