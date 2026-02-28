"""
Quick NHL Slate Processor — Process pasted slate directly
Uses REAL 2025-26 player season averages for Poisson modeling
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sports.nhl.nhl_menu import (
    parse_underdog_paste,
    deduplicate_props,
    analyze_slate,
    NHLSlate,
    print_slate_summary,
    print_playable_picks,
)
from sports.nhl.player_stats import (
    SKATER_STATS_2026,
    GOALIE_STATS_2026,
    get_player_stats,
)
from datetime import date

SLATE_TEXT = """
Jonathan MarchessaultDemon
NSH - F
Jonathan Marchessault
vs STL Mon 7:08pm
2.5
SOG
More
Trending
748
Rickard Rakell
PIT - F
Rickard Rakell
vs OTT Mon 6:08pm
2.5
SOG
Less
More
Trending
636
Jordan KyrouGoblin
STL - F
Jordan Kyrou
@ NSH Mon 7:08pm
1.5
SOG
More
Trending
492
Cole CaufieldDemon
MTL - F
Cole Caufield
@ MIN Mon 6:38pm
0.5
Goals
More
Trending
411
Roman JosiGoblin
NSH - D
Roman Josi
vs STL Mon 7:08pm
1.5
SOG
More
Trending
267
Rasmus Sandin
WSH - D
Rasmus Sandin
vs NYI Mon 6:08pm
1.5
Blocked Shots
Less
More
Trending
266
MacKenzie Weegar
CGY - D
MacKenzie Weegar
vs TOR Mon 9:08pm
2.5
SOG
Less
More
Trending
238
Justin Faulk
STL - D
Justin Faulk
@ NSH Mon 7:08pm
1.5
Blocked Shots
Less
More
Trending
227
Macklin CelebriniGoblin
SJ - F
Macklin Celebrini
@ CHI Mon 7:38pm
2.5
SOG
More
Trending
198
Anthony ManthaDemon
PIT - F
Anthony Mantha
vs OTT Mon 6:08pm
0.5
Goals
More
Trending
174
Wyatt JohnstonGoblin
DAL - F
Wyatt Johnston
vs WPG Mon 7:38pm
1.5
SOG
More
Trending
158
Jason RobertsonGoblin
DAL - F
Jason Robertson
vs WPG Mon 7:38pm
1.5
SOG
More
Trending
152
Brady TkachukDemon
OTT - F
Brady Tkachuk
@ PIT Mon 6:08pm
0.5
Goals
More
Trending
127
Macklin CelebriniDemon
SJ - F
Macklin Celebrini
@ CHI Mon 7:38pm
0.5
Goals
More
Brady Tkachuk
@ PIT Mon 6:08pm
2.5
SOG
More
Trending
748
Dylan CozensGoblin
OTT - F
Dylan Cozens
@ PIT Mon 6:08pm
1.5
SOG
More
Erik KarlssonGoblin
PIT - D
Erik Karlsson
vs OTT Mon 6:08pm
1.5
SOG
More
Evgeni MalkinGoblin
PIT - F
Evgeni Malkin
vs OTT Mon 6:08pm
1.5
SOG
More
Jake SandersonGoblin
OTT - D
Jake Sanderson
@ PIT Mon 6:08pm
1.5
SOG
More
Sidney CrosbyGoblin
PIT - F
Sidney Crosby
vs OTT Mon 6:08pm
1.5
SOG
More
Drake BathersonGoblin
OTT - F
Drake Batherson
@ PIT Mon 6:08pm
1.5
SOG
More
Matthew TkachukGoblin
FLA - F
Matthew Tkachuk
vs BUF Mon 6:08pm
2.5
SOG
More
Tage ThompsonGoblin
BUF - F
Tage Thompson
@ FLA Mon 6:08pm
2.5
SOG
More
Sam BennettGoblin
FLA - F
Sam Bennett
vs BUF Mon 6:08pm
2.5
SOG
More
Rasmus DahlinGoblin
BUF - D
Rasmus Dahlin
@ FLA Mon 6:08pm
1.5
SOG
More
Carter VerhaegheGoblin
FLA - F
Carter Verhaeghe
vs BUF Mon 6:08pm
1.5
SOG
More
Alex TuchGoblin
BUF - F
Alex Tuch
@ FLA Mon 6:08pm
1.5
SOG
More
Owen PowerDemon
BUF - D
Owen Power
@ FLA Mon 6:08pm
1.5
SOG
More
Alex OvechkinGoblin
WSH - F
Alex Ovechkin
vs NYI Mon 6:08pm
2.5
SOG
More
Bo HorvatGoblin
NYI - F
Bo Horvat
@ WSH Mon 6:08pm
2.5
SOG
More
Jakob ChychrunGoblin
WSH - D
Jakob Chychrun
vs NYI Mon 6:08pm
2.5
SOG
More
Aliaksei ProtasGoblin
WSH - F
Aliaksei Protas
vs NYI Mon 6:08pm
1.5
SOG
More
Dylan StromeGoblin
WSH - F
Dylan Strome
vs NYI Mon 6:08pm
1.5
SOG
More
Mathew BarzalGoblin
NYI - F
Mathew Barzal
@ WSH Mon 6:08pm
1.5
SOG
More
Cole CaufieldGoblin
MTL - F
Cole Caufield
@ MIN Mon 6:38pm
2.5
SOG
More
Kirill KaprizovGoblin
MIN - F
Kirill Kaprizov
vs MTL Mon 6:38pm
2.5
SOG
More
Matt BoldyGoblin
MIN - F
Matt Boldy
vs MTL Mon 6:38pm
1.5
SOG
More
Nick SuzukiGoblin
MTL - F
Nick Suzuki
@ MIN Mon 6:38pm
1.5
SOG
More
Mats ZuccarelloGoblin
MIN - F
Mats Zuccarello
vs MTL Mon 6:38pm
1.5
SOG
More
Brock FaberGoblin
MIN - D
Brock Faber
vs MTL Mon 6:38pm
1.5
SOG
More
Ivan DemidovGoblin
MTL - F
Ivan Demidov
@ MIN Mon 6:38pm
1.5
SOG
More
Juraj SlafkovskyGoblin
MTL - F
Juraj Slafkovsky
@ MIN Mon 6:38pm
1.5
SOG
More
Filip ForsbergGoblin
NSH - F
Filip Forsberg
vs STL Mon 7:08pm
2.5
SOG
More
Jimmy SnuggerudGoblin
STL - F
Jimmy Snuggerud
@ NSH Mon 7:08pm
1.5
SOG
More
Steven StamkosGoblin
NSH - F
Steven Stamkos
vs STL Mon 7:08pm
1.5
SOG
More
Justin FaulkGoblin
STL - D
Justin Faulk
@ NSH Mon 7:08pm
1.5
SOG
More
Luke EvangelistaGoblin
NSH - F
Luke Evangelista
vs STL Mon 7:08pm
1.5
SOG
More
Pavel BuchnevichGoblin
STL - F
Pavel Buchnevich
@ NSH Mon 7:08pm
1.5
SOG
More
Connor BedardGoblin
CHI - F
Connor Bedard
vs SJ Mon 7:38pm
2.5
SOG
More
Tyler BertuzziGoblin
CHI - F
Tyler Bertuzzi
vs SJ Mon 7:38pm
1.5
SOG
More
Tyler ToffoliGoblin
SJ - F
Tyler Toffoli
@ CHI Mon 7:38pm
1.5
SOG
More
Will SmithGoblin
SJ - F
Will Smith
@ CHI Mon 7:38pm
1.5
SOG
More
William EklundGoblin
SJ - F
William Eklund
@ CHI Mon 7:38pm
1.5
SOG
More
Kyle ConnorGoblin
WPG - F
Kyle Connor
@ DAL Mon 7:38pm
2.5
SOG
More
Mark ScheifeleGoblin
WPG - F
Mark Scheifele
@ DAL Mon 7:38pm
1.5
SOG
More
Mikko RantanenGoblin
DAL - F
Mikko Rantanen
vs WPG Mon 7:38pm
1.5
SOG
More
Roope HintzGoblin
DAL - F
Roope Hintz
vs WPG Mon 7:38pm
1.5
SOG
More
Josh MorrisseyGoblin
WPG - D
Josh Morrissey
@ DAL Mon 7:38pm
1.5
SOG
More
Miro HeiskanenGoblin
DAL - D
Miro Heiskanen
vs WPG Mon 7:38pm
1.5
SOG
More
Thomas HarleyGoblin
DAL - D
Thomas Harley
vs WPG Mon 7:38pm
1.5
SOG
More
Nathan MacKinnonGoblin
COL - F
Nathan MacKinnon
vs DET Mon 8:08pm
3.5
SOG
More
Alex DeBrincatGoblin
DET - F
Alex DeBrincat
@ COL Mon 8:08pm
2.5
SOG
More
Cale MakarGoblin
COL - D
Cale Makar
vs DET Mon 8:08pm
2.5
SOG
More
Brent BurnsGoblin
COL - D
Brent Burns
vs DET Mon 8:08pm
1.5
SOG
More
Ross ColtonGoblin
COL - F
Ross Colton
vs DET Mon 8:08pm
1.5
SOG
More
Artturi LehkonenGoblin
COL - F
Artturi Lehkonen
vs DET Mon 8:08pm
1.5
SOG
More
Valeri NichushkinGoblin
COL - F
Valeri Nichushkin
vs DET Mon 8:08pm
1.5
SOG
More
Moritz SeiderGoblin
DET - D
Moritz Seider
@ COL Mon 8:08pm
1.5
SOG
More
Patrick KaneGoblin
DET - F
Patrick Kane
@ COL Mon 8:08pm
1.5
SOG
More
Lucas RaymondGoblin
DET - F
Lucas Raymond
@ COL Mon 8:08pm
1.5
SOG
More
Dylan GuentherGoblin
UTA - F
Dylan Guenther
vs VAN Mon 8:38pm
2.5
SOG
More
Clayton KellerGoblin
UTA - F
Clayton Keller
vs VAN Mon 8:38pm
1.5
SOG
More
Nick SchmaltzGoblin
UTA - F
Nick Schmaltz
vs VAN Mon 8:38pm
1.5
SOG
More
Evander KaneGoblin
VAN - F
Evander Kane
@ UTA Mon 8:38pm
1.5
SOG
More
Filip ChytilGoblin
VAN - F
Filip Chytil
@ UTA Mon 8:38pm
1.5
SOG
More
JJ PeterkaGoblin
UTA - F
JJ Peterka
vs VAN Mon 8:38pm
1.5
SOG
More
Mikhail SergachevGoblin
UTA - D
Mikhail Sergachev
vs VAN Mon 8:38pm
1.5
SOG
More
Barrett HaytonGoblin
UTA - F
Barrett Hayton
vs VAN Mon 8:38pm
1.5
SOG
More
Nazem KadriGoblin
CGY - F
Nazem Kadri
vs TOR Mon 9:08pm
2.5
SOG
More
Matt CoronatoGoblin
CGY - F
Matt Coronato
vs TOR Mon 9:08pm
1.5
SOG
More
Mikael BacklundGoblin
CGY - F
Mikael Backlund
vs TOR Mon 9:08pm
2.5
SOG
More
John TavaresGoblin
TOR - F
John Tavares
@ CGY Mon 9:08pm
1.5
SOG
More
Yegor SharangovichGoblin
CGY - F
Yegor Sharangovich
vs TOR Mon 9:08pm
1.5
SOG
More
Bobby McMannGoblin
TOR - F
Bobby McMann
@ CGY Mon 9:08pm
1.5
SOG
More
William NylanderGoblin
TOR - F
William Nylander
@ CGY Mon 9:08pm
1.5
SOG
More
"""

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  NHL SLATE ANALYSIS - February 2, 2026")
    print("  [HOCKEY] Using REAL 2025-26 Season Statistics")
    print("=" * 60)
    
    # Show stats module status
    print(f"\n  📊 Player Stats Loaded: {len(SKATER_STATS_2026)} skaters, {len(GOALIE_STATS_2026)} goalies")
    
    # Parse props
    props = parse_underdog_paste(SLATE_TEXT)
    props = deduplicate_props(props)
    
    print(f"  📋 Parsed {len(props)} unique props")
    
    # Show which players have real stats
    found = 0
    for p in props:
        if get_player_stats(p.player):
            found += 1
    print(f"  ✅ Real stats found for {found}/{len(props)} props ({found/len(props)*100:.0f}%)")
    
    # Create and analyze slate
    slate = NHLSlate(
        date=date.today().strftime("%Y-%m-%d"),
        props=props,
        games={},
    )
    
    slate = analyze_slate(slate)
    
    # Print results
    print_slate_summary(slate)
    print_playable_picks(slate)
    
    # Show top picks by tier with real stats detail
    strong = [p for p in slate.props if p.tier == "STRONG"]
    lean = [p for p in slate.props if p.tier == "LEAN"]
    
    print("\n" + "=" * 60)
    print("  TOP PICKS SUMMARY (with Real Season Averages)")
    print("=" * 60)
    
    if strong:
        print(f"\n  🟢 STRONG PICKS ({len(strong)}):")
        for p in sorted(strong, key=lambda x: x.model_prob or 0, reverse=True)[:15]:
            tag = f" [{p.tag}]" if p.tag else ""
            stats = get_player_stats(p.player)
            if stats and p.stat == "SOG":
                avg_str = f"(Avg: {stats.sog_avg:.1f})"
            elif stats and p.stat == "Goals":
                avg_str = f"(Avg: {stats.goals_avg:.2f})"
            else:
                avg_str = ""
            print(f"     • {p.player}{tag} {p.stat} {p.direction} {p.line} {avg_str} → {p.model_prob:.1%}")
    
    if lean:
        print(f"\n  🟡 LEAN PICKS ({len(lean)}):")
        for p in sorted(lean, key=lambda x: x.model_prob or 0, reverse=True)[:10]:
            tag = f" [{p.tag}]" if p.tag else ""
            stats = get_player_stats(p.player)
            if stats and p.stat == "SOG":
                avg_str = f"(Avg: {stats.sog_avg:.1f})"
            elif stats and p.stat == "Goals":
                avg_str = f"(Avg: {stats.goals_avg:.2f})"
            else:
                avg_str = ""
            print(f"     • {p.player}{tag} {p.stat} {p.direction} {p.line} {avg_str} → {p.model_prob:.1%}")
    
    # Show model calibration info
    print("\n" + "-" * 60)
    print("  📈 MODEL NOTES:")
    print("     • SOG props use real 2025-26 per-game averages")
    print("     • Goals props use Poisson with season goals/game")
    print("     • Defensemen SOG naturally lower (1.4-2.4 range)")
    print("     • Top forwards: MacKinnon (4.2), Ovechkin (3.8), Kaprizov (3.8)")
    print("-" * 60)
    
    print("\n" + "=" * 60)
    print("  ⚠️  REMINDER: Goalie confirmation REQUIRED for saves props")
    print("=" * 60 + "\n")
