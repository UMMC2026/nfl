import json
import os
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import cast
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from data_center.guards.roster_gate import (
    load_roster,
    apply_roster_gate,
    apply_status_downgrade,
    roster_checksum,
    roster_version,
    RosterGateError,
    get_player_status,
)
from rich.text import Text
from rich import box
from dotenv import load_dotenv

from ufa.config import settings
from ufa.analysis.prob import prob_hit
from ufa.analysis.payouts import power_table, flex_table
from ufa.analysis.ev import monte_carlo_ev
from ufa.optimizer.entry_builder import build_entries
from ufa.models.schemas import PropPick
from ufa.analysis.engine import (
    AnalysisEngine, Player, PropBet, PlayerContext,
    DefenseRanking, CorrelationGroup, Priority, PlayDirection,
    get_trend_icon, get_consistency_icon, format_play_string
)
from ufa.ingest.espn import ESPNFetcher, PlayerInfo
from ufa.ingest.sleeper import get_user as sleeper_get_user, get_user_leagues as sleeper_get_user_leagues, avatar_url as sleeper_avatar_url, SleeperError
from ufa.analysis import learning_loop, verification

load_dotenv()
app = typer.Typer(add_completion=False)
console = Console()
@app.command()
def sleeper_user(
    identifier: str = typer.Argument(..., help="Sleeper username or user_id"),
    save: str = typer.Option(None, help="Optional path to save JSON response")
):
    """Fetch a Sleeper user object by username or user_id and display core fields."""
    try:
        user = sleeper_get_user(identifier)
    except SleeperError as e:
        console.print(f"[red]Sleeper error: {e}[/red]")
        raise typer.Exit(1)

    # Render basic info
    table = Table(title="Sleeper User", box=box.ROUNDED)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for k in ("username", "user_id", "display_name", "avatar"):
        val = user.get(k)
        table.add_row(k, str(val))

    console.print(table)

    # Show avatar URLs if available
    avatar_id = user.get("avatar")
    if avatar_id:
        full_url = sleeper_avatar_url(avatar_id)
        thumb_url = sleeper_avatar_url(avatar_id, thumb=True)
        console.print(Panel.fit(f"Avatar:\nFull: {full_url}\nThumb: {thumb_url}", border_style="green"))
    else:
        console.print(Panel.fit("No avatar set", border_style="yellow"))

    if save:
        try:
            Path(save).write_text(json.dumps(user, indent=2), encoding="utf-8")
            console.print(f"[green]✓ Saved to {save}[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: could not save file: {e}[/yellow]")


@app.command()
def sleeper_leagues(
    user_id: str = typer.Argument(..., help="Sleeper user_id"),
    sport: str = typer.Option("nfl", help="Sport, e.g., nfl"),
    season: str = typer.Option("2018", help="Season year, e.g., 2018"),
    save: str = typer.Option(None, help="Optional path to save JSON response")
):
    """Fetch all Sleeper leagues for a user for a given sport and season."""
    try:
        leagues = sleeper_get_user_leagues(user_id, sport=sport, season=season)
    except SleeperError as e:
        console.print(f"[red]Sleeper error: {e}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Sleeper Leagues ({sport} {season})", box=box.ROUNDED)
    table.add_column("League Name", style="white", width=30)
    table.add_column("League ID", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Season", style="green")
    table.add_column("Draft ID", style="magenta")
    table.add_column("Avatar", style="dim")

    for lg in leagues:
        table.add_row(
            str(lg.get("name", "")),
            str(lg.get("league_id", "")),
            str(lg.get("status", "")),
            str(lg.get("season", "")),
            str(lg.get("draft_id", "")),
            str(sleeper_avatar_url(lg.get("avatar")))
        )

    console.print(table)

    if save:
        try:
            Path(save).write_text(json.dumps(leagues, indent=2), encoding="utf-8")
            console.print(f"[green]✓ Saved to {save}[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: could not save file: {e}[/yellow]")



@app.command()
def fetch(
    teams: str = typer.Option("PIT,CLE,JAX,IND", help="Comma-separated team abbreviations"),
    show_all: bool = typer.Option(False, help="Show all players, not just top stats"),
    save: str = typer.Option(None, help="Save to JSON file")
):
    """
    Fetch REAL 2024 NFL stats from ESPN for specified teams.
    """
    team_list = [t.strip().upper() for t in teams.split(",")]
    
    console.print(Panel.fit(
        "[bold cyan]ESPN NFL Data Fetcher[/]\n"
        f"Fetching real 2025 season stats for: {', '.join(team_list)}",
        border_style="cyan"
    ))
    
    fetcher = ESPNFetcher(season=2025)
    
    # Get league leaders first
    console.print("\n[yellow]Fetching 2025 season Leaders...[/]")
    
    leaders_table = Table(title="2025 NFL Season Leaders", box=box.ROUNDED)
    leaders_table.add_column("Category", style="cyan")
    leaders_table.add_column("#1", style="green")
    leaders_table.add_column("#2", style="white")
    leaders_table.add_column("#3", style="dim")
    
    for stat_type in ["rushing", "passing", "receiving"]:
        leaders = fetcher.get_season_leaders(stat_type)[:3]
        if leaders:
            leaders_table.add_row(
                stat_type.upper(),
                f"{leaders[0]['name']} ({leaders[0]['team']}) - {leaders[0]['stat']}",
                f"{leaders[1]['name']} - {leaders[1]['stat']}" if len(leaders) > 1 else "",
                f"{leaders[2]['name']} - {leaders[2]['stat']}" if len(leaders) > 2 else ""
            )
    
    console.print(leaders_table)
    
    # Get team rosters with stats
    console.print("\n[yellow]Fetching team player stats...[/]\n")
    
    all_players = {}
    
    for team in team_list:
        try:
            players = fetcher.get_team_season_stats(team)
            all_players[team] = players
            
            if players:
                # Filter to players with actual stats
                with_stats = [p for p in players if p.rush_yards > 0 or p.rec_yards > 0 or p.pass_yards > 0]
                
                table = Table(title=f"{team} Players with 2024 Stats ({len(with_stats)} active)")
                table.add_column("Player", style="white", width=22)
                table.add_column("Pos", style="cyan", width=4)
                table.add_column("Rush Yds", style="green", justify="right")
                table.add_column("Rec", style="blue", justify="right")
                table.add_column("Rec Yds", style="blue", justify="right")
                table.add_column("Pass Yds", style="magenta", justify="right")
                table.add_column("YPG", style="yellow", justify="right")
                
                # Sort by total production
                with_stats.sort(key=lambda p: p.rush_yards + p.rec_yards + p.pass_yards, reverse=True)
                
                display = with_stats if show_all else with_stats[:8]
                
                for player in display:
                    # Calculate per-game
                    total = player.rush_yards + player.rec_yards
                    ypg = total / 16 if total > 0 else 0
                    
                    table.add_row(
                        player.name,
                        player.position,
                        str(int(player.rush_yards)) if player.rush_yards else "-",
                        str(int(player.receptions)) if player.receptions else "-",
                        str(int(player.rec_yards)) if player.rec_yards else "-",
                        str(int(player.pass_yards)) if player.pass_yards else "-",
                        f"{ypg:.1f}" if ypg > 0 else "-"
                    )
                
                console.print(table)
                console.print()
        except Exception as e:
            console.print(f"[red]Error fetching {team}: {e}[/]")
    
    # Get current week games
    console.print("[yellow]Today's Games:[/]")
    games = fetcher.get_week_schedule()
    relevant_games = [g for g in games if g.home_team in team_list or g.away_team in team_list]
    
    for game in relevant_games:
        console.print(f"  {game.away_team} @ {game.home_team} - {game.status.replace('STATUS_', '')}")
    
    # Save to JSON if requested
    if save:
        output = {
            "fetched_at": datetime.now().isoformat(),
            "season": 2024,
            "teams": {}
        }
        
        for team, players in all_players.items():
            output["teams"][team] = [
                {
                    "name": p.name,
                    "position": p.position,
                    "rush_yards": p.rush_yards,
                    "receptions": p.receptions,
                    "rec_yards": p.rec_yards,
                    "pass_yards": p.pass_yards,
                    "rush_ypg": p.rush_ypg,
                    "rec_ypg": p.rec_ypg
                }
                for p in players if p.rush_yards > 0 or p.rec_yards > 0 or p.pass_yards > 0
            ]
        
        Path(save).write_text(json.dumps(output, indent=2))
        console.print(f"\n[green]✓ Saved to {save}[/]")
    
    fetcher.close()
    console.print("\n[green]✓ ESPN data fetch complete![/]")


@app.command()
def player(
    name: str = typer.Argument(..., help="Player name to search"),
    gamelog: bool = typer.Option(False, help="Show recent game log")
):
    """
    Search for a player and show their 2024 stats from ESPN.
    """
    console.print(f"\n[yellow]Searching for '{name}'...[/]\n")
    
    fetcher = ESPNFetcher(season=2025)
    
    # Search for player
    search = fetcher.search_player(name)
    
    if not search:
        console.print(f"[red]Player '{name}' not found[/]")
        fetcher.close()
        return
    
    console.print(f"[green]Found:[/] {search['name']} - {search.get('team', 'N/A')} ({search.get('position', 'N/A')})")
    
    # Get stats
    player_info = fetcher.get_player_stats_by_name(name)
    
    if player_info:
        table = Table(title=f"{player_info.name} - 2025 season Stats")
        table.add_column("Stat", style="cyan")
        table.add_column("Value", style="green", justify="right")
        
        if player_info.pass_yards > 0:
            table.add_row("Pass Yards", f"{int(player_info.pass_yards):,}")
            table.add_row("Pass TDs", str(int(player_info.pass_tds)))
        
        if player_info.rush_yards > 0:
            table.add_row("Rush Yards", f"{int(player_info.rush_yards):,}")
            table.add_row("Rush TDs", str(int(player_info.rush_tds)))
        
        if player_info.receptions > 0 or player_info.rec_yards > 0:
            table.add_row("Receptions", str(int(player_info.receptions)))
            table.add_row("Rec Yards", f"{int(player_info.rec_yards):,}")
            table.add_row("Rec TDs", str(int(player_info.rec_tds)))
        
        console.print(table)
    
    # Get game log if requested
    if gamelog and search.get('id'):
        console.print("\n[yellow]Recent Game Log:[/]")
        games = fetcher.get_player_gamelog(search['id'], limit=5)
        
        if games:
            for game in games:
                stats_str = ", ".join([f"{k}: {v}" for k, v in game.get('stats', {}).items()])
                console.print(f"  Week {game.get('week', '?')} vs {game.get('opponent', '?')}: {stats_str[:80]}")
        else:
            console.print("  [dim]No game log data available[/]")
    
    fetcher.close()



def _fetch_live_espn_data(teams: list[str], week: int = 17) -> tuple[list[Player], dict[str, DefenseRanking], list[CorrelationGroup]]:
    """
    Fetch real player data from ESPN for the specified teams.
    
    Returns:
        Tuple of (players, defense_rankings, correlation_groups)
    """
    console.print("\n[bold cyan]═══ FETCHING LIVE ESPN DATA ═══[/bold cyan]\n")
    fetcher = ESPNFetcher(season=2025)
    players = []
    
    # Get all matchups for the week
    console.print("[yellow]📅 Fetching week schedule...[/yellow]")
    games = fetcher.get_week_schedule(week)
    
    # Build matchup map
    matchups = {}
    for game in games:
        matchups[game.home_team] = game.away_team
        matchups[game.away_team] = game.home_team
    
    console.print(f"  Found {len(games)} games\n")
    
    # Defense rankings (approximate based on 2024 data - could fetch from ESPN)
    defense_rankings = {
        "CLE": DefenseRanking(rush=18, passing=20, overall=15, red_zone=12, sacks_allowed=28),
        "PIT": DefenseRanking(rush=3, passing=8, overall=5, red_zone=6, sacks_allowed=12),
        "IND": DefenseRanking(rush=28, passing=22, overall=26, red_zone=25, sacks_allowed=30),
        "JAX": DefenseRanking(rush=24, passing=28, overall=27, red_zone=28, sacks_allowed=26),
        "KC": DefenseRanking(rush=10, passing=6, overall=7, red_zone=8, sacks_allowed=10),
        "BAL": DefenseRanking(rush=5, passing=12, overall=8, red_zone=10, sacks_allowed=8),
        "BUF": DefenseRanking(rush=8, passing=4, overall=4, red_zone=5, sacks_allowed=6),
        "DET": DefenseRanking(rush=20, passing=18, overall=20, red_zone=18, sacks_allowed=20),
        "PHI": DefenseRanking(rush=2, passing=10, overall=6, red_zone=7, sacks_allowed=14),
        "MIN": DefenseRanking(rush=12, passing=5, overall=9, red_zone=11, sacks_allowed=16),
    }
    
    # Fetch players for each team
    for team in teams:
        console.print(f"[yellow]📊 Fetching {team} roster and stats...[/yellow]")
        
        opponent = matchups.get(team, "UNK")
        
        try:
            # Get starters with real stats
            starters = fetcher.get_starters(team)
            team_stats = fetcher.get_team_season_stats(team)
            
            # Build lookup for stats
            stats_lookup = {p.name: p for p in team_stats}
            
            for pos_key, player_info in starters.items():
                pos = pos_key.rstrip("0123456789")  # RB1 -> RB
                
                # Get full stats if available
                full_stats = stats_lookup.get(player_info.name, player_info)
                
                # Skip players with no meaningful stats
                if full_stats.pass_yards == 0 and full_stats.rush_yards == 0 and full_stats.rec_yards == 0:
                    continue
                
                # Determine player props based on position and stats
                props = []
                games_played = max(full_stats.games_played, 16)  # Assume 16 if not set
                
                if pos == "QB" and full_stats.pass_yards > 500:
                    avg_pass = full_stats.pass_yards / games_played
                    # Create prop around actual average
                    line = round(avg_pass / 5) * 5 - 5  # Slightly under average
                    props.append(PropBet(
                        stat="Pass Yards",
                        line=float(line),
                        prop_type="pass",
                        game_logs=[avg_pass * (0.85 + i * 0.03) for i in range(8)]  # Simulated variance
                    ))
                
                if pos == "RB" and full_stats.rush_yards > 100:
                    avg_rush = full_stats.rush_yards / games_played
                    line = round(avg_rush / 5) * 5 - 5
                    props.append(PropBet(
                        stat="Rush Yards",
                        line=float(max(line, 25)),  # Min 25 yard line
                        prop_type="rush",
                        game_logs=[avg_rush * (0.8 + i * 0.05) for i in range(8)]
                    ))
                
                if full_stats.rec_yards > 100:
                    avg_rec = full_stats.rec_yards / games_played
                    line = round(avg_rec / 5) * 5 - 5
                    props.append(PropBet(
                        stat="Rec Yards", 
                        line=float(max(line, 20)),
                        prop_type="rec",
                        game_logs=[avg_rec * (0.75 + i * 0.06) for i in range(8)]
                    ))
                
                if full_stats.receptions > 20:
                    avg_rec_count = full_stats.receptions / games_played
                    line = round(avg_rec_count * 2) / 2 - 0.5  # Round to 0.5
                    props.append(PropBet(
                        stat="Receptions",
                        line=float(max(line, 2.5)),
                        prop_type="rec_count", 
                        game_logs=[avg_rec_count * (0.8 + i * 0.05) for i in range(8)]
                    ))
                
                if props:
                    players.append(Player(
                        name=player_info.name,
                        team=team,
                        opponent=opponent,
                        position=pos,
                        props=props,
                        context=PlayerContext(
                            injury="" if player_info.status == "Active" else player_info.status
                        )
                    ))
                    console.print(f"  ✓ {player_info.name} ({pos}) - {len(props)} props")
                    
        except Exception as e:
            console.print(f"  [red]Error fetching {team}: {e}[/red]")
    
    fetcher.close()
    
    # Build correlation groups based on teams
    correlation_groups = []
    team_players = {}
    for player in players:
        if player.team not in team_players:
            team_players[player.team] = []
        team_players[player.team].append(player.name)
    
    for team, names in team_players.items():
        if len(names) > 1:
            correlation_groups.append(CorrelationGroup(
                name=f"{team} Offense",
                players=names,
                props=["Pass Yards", "Rec Yards", "Rush Yards"],
                dependency="Game script and volume dependent"
            ))
    
    console.print(f"\n[green]✓ Fetched {len(players)} players with live stats[/green]\n")
    
    return players, defense_rankings, correlation_groups

def _demo_picks():
    # Simple cross-sport demo (uses recent_values)
    return [
        PropPick(league="NBA", player="Player A", team="LAL", stat="points", line=24.5, direction="higher",
                 recent_values=[22, 28, 25, 31, 19, 26, 27, 24, 30, 21]),
        PropPick(league="NBA", player="Player B", team="BOS", stat="rebounds", line=8.5, direction="higher",
                 recent_values=[7, 10, 9, 12, 6, 8, 11, 9, 10, 7]),
        PropPick(league="NFL", player="Player C", team="KC", stat="pass_yds", line=265.5, direction="higher",
                 recent_values=[240, 310, 275, 290, 260, 315, 225, 280, 305, 250]),
        PropPick(league="CFB", player="Player D", team="TEX", stat="cfb_pass_yds", line=245.5, direction="higher",
                 recent_values=[210, 265, 290, 240, 320, 180, 275, 260, 300, 230]),
    ]

@app.command()
def rank(
    file: str = typer.Option(None, help="JSON file of picks (list[PropPick])."),
    demo: bool = typer.Option(False, help="Use built-in demo picks."),
    roster_file: str = typer.Option(None, help="Canonical roster CSV for ACTIVE gate")
):
    """Rank picks by P(hit)."""
    if demo:
        picks = _demo_picks()
    else:
        if not file:
            raise typer.BadParameter("Provide --file or --demo.")
        raw = json.loads(open(file, "r", encoding="utf-8").read())
        picks = [PropPick(**x) for x in raw]

    # ==== ROSTER GATE (HARD) ====
    roster_path = roster_file or "data_center/rosters/NBA_active_roster_current.csv"
    try:
        roster = load_roster(roster_path)
        gated = apply_roster_gate(picks, roster)  # type: ignore[arg-type]
        r_version = roster_version(roster, roster_path)
        r_checksum = roster_checksum(roster_path)
    except RosterGateError as e:
        console.print(f"[red]\n[FATAL] Roster Gate Failed: {e}[/red]")
        console.print(
            "[yellow]Hint:[/] Provide a matching roster CSV via --roster-file (slate-specific ACTIVE list).\n"
            "    Example: --roster-file \"data_center/rosters/NBA_active_roster_BOS_POR.csv\"\n"
            "Or temporarily skip with [dim]--bypass-roster[/dim] (not recommended)."
        )
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"Roster version: [bold]{r_version}[/bold]\n"
        f"Gated picks: {len(gated)} of {len(picks)}",
        border_style="yellow",
        title="Roster Gate"
    ))
    picks = cast(list[PropPick], gated)

    rows = []
    for i, p in enumerate(picks):
        p_hit = prob_hit(p.line, p.direction, recent_values=p.recent_values, mu=p.mu, sigma=p.sigma)
        # Status-weighted downgrade (optional, ON by default)
        status = get_player_status(roster, p.player)
        if status == "QUESTIONABLE":
            p_hit = max(0.0, float(p_hit) - 0.08)
        elif status == "DOUBTFUL":
            p_hit = max(0.0, float(p_hit) - 0.15)
        rows.append((i, p.league, p.player, p.team, p.stat, p.line, p.direction, float(p_hit)))

    rows.sort(key=lambda r: r[-1], reverse=True)

    t = Table(title="Ranked Picks (by P(hit))")
    for col in ["#", "League", "Player", "Team", "Stat", "Line", "Dir", "P(hit)"]:
        t.add_column(col)

    for r in rows:
        t.add_row(str(r[0]), r[1], r[2], r[3], r[4], str(r[5]), r[6], f"{r[7]:.4f}")

    console.print(t)

@app.command()
def build(
    file: str = typer.Option(None, help="JSON file of picks (list[PropPick])."),
    demo: bool = typer.Option(False, help="Use built-in demo picks."),
    format: str = typer.Option("power", help="power|flex"),
    legs: int = typer.Option(3, help="2–8 legs"),
    max_entries: int = typer.Option(25, help="How many entries to return"),
    min_teams: int = typer.Option(settings.min_teams_per_entry, help="Minimum unique teams in an entry"),
    same_team_penalty: float = typer.Option(0.0, help="0..1 penalty for repeated teams in an entry"),
    max_player_legs: int = typer.Option(1, help="Max props per player (0=unlimited)"),
    max_team_legs: int = typer.Option(0, help="Max props per team (0=unlimited)"),
    corr_penalty: float = typer.Option(0.0, help="0..1 penalty per correlated pair"),
    roster_file: str = typer.Option(None, help="Canonical roster CSV for ACTIVE gate"),
    high_thresh: float = typer.Option(0.80, help="Threshold for high-confidence hits (0..1)"),
    miss_thresh: float = typer.Option(0.40, help="Threshold for miss probability (0..1)"),
    unders_only: bool = typer.Option(False, help="Render only UNDERS in cheat sheet"),
    overs_only: bool = typer.Option(False, help="Render only OVERS in cheat sheet"),
    print_report: bool = typer.Option(False, help="Print set report and cheat sheet to terminal after saving"),
    bypass_roster: bool = typer.Option(False, help="Skip roster gate (NOT recommended)")
):
    """Build top EV entries under constraints."""
    if legs < 2 or legs > settings.max_legs:
        raise typer.BadParameter(f"legs must be between 2 and {settings.max_legs}")

    if demo:
        picks = _demo_picks()
    else:
        if not file:
            raise typer.BadParameter("Provide --file or --demo.")
        raw = json.loads(open(file, "r", encoding="utf-8").read())
        picks = [PropPick(**x) for x in raw]

    # ==== ROSTER GATE (HARD) ====
    roster_path = roster_file or "data_center/rosters/NBA_active_roster_current.csv"
    if bypass_roster:
        console.print(Panel.fit(
            "Roster Gate: BYPASSED (using provided picks as-is)",
            border_style="red",
            title="Roster Gate"
        ))
        roster = None
        r_version = "BYPASS"
        r_checksum = "-"
    else:
        try:
            roster = load_roster(roster_path)
            gated = apply_roster_gate(picks, roster)  # type: ignore[arg-type]
            # metadata
            r_version = roster_version(roster, roster_path)
            r_checksum = roster_checksum(roster_path)
        except RosterGateError as e:
            console.print(f"[red]\n[FATAL] Roster Gate Failed: {e}[/red]")
            console.print(
                "[yellow]Hint:[/] Provide a matching roster CSV via --roster-file. Example for BOS/POR:\n"
                "    --roster-file \"data_center/rosters/NBA_active_roster_BOS_POR.csv\"\n"
                "Or temporarily skip with [dim]--bypass-roster[/dim] (not recommended)."
            )
            raise typer.Exit(1)

        console.print(Panel.fit(
            f"Roster version: [bold]{r_version}[/bold]\n"
            f"Gated picks: {len(gated)} of {len(picks)}",
            border_style="yellow",
            title="Roster Gate"
        ))
        picks = cast(list[PropPick], gated)

    ranked = []
    for i, p in enumerate(picks):
        p_hit = prob_hit(p.line, p.direction, recent_values=p.recent_values, mu=p.mu, sigma=p.sigma)
        ranked.append({
            "id": i,
            "league": p.league,
            "player": p.player,
            "team": p.team,
            "opponent": p.opponent,
            "stat": p.stat,
            "line": p.line,
            "direction": p.direction,
            "p_hit": float(p_hit),
        })

    table = power_table() if format.lower() == "power" else flex_table()
    entries = build_entries(
        picks=ranked,
        payout_table=table,
        legs=legs,
        min_teams=min_teams,
        max_entries=max_entries,
        same_team_penalty=same_team_penalty,
        max_player_legs=max_player_legs,
        max_team_legs=max_team_legs,
        correlation_penalty=corr_penalty,
    )
    # Attach roster metadata to each entry
    for e in entries:
        e["roster_version"] = r_version
        e["roster_checksum"] = r_checksum
        e["roster_gate"] = "BYPASS" if bypass_roster else "PASSED"

    t = Table(title=f"Top Entries (format={format}, legs={legs})")
    for col in ["EV (units)", "Teams", "Players", "Props", "P(list)"]:
        t.add_column(col)

    for e in entries:
        t.add_row(
            f"{e['ev_units']:.4f}",
            ", ".join(e["teams"]),
            " | ".join(e["players"]),
            " | ".join(e.get("stats", [])),
            ", ".join([f"{p:.3f}" for p in e["p_list"]]),
        )

    console.print(t)
    console.print(f"\n[dim]Roster: {r_version} | checksum={r_checksum}[/dim]")

    # Persist a set report grouped by OVER/UNDER for built entries
    _write_set_report(entries, format=format, legs=legs, roster_version=r_version, roster_checksum=r_checksum, prefix="build", print_to_console=print_report)
    # Persist a cheat sheet style report as well
    _write_cheatsheet(picks, entries, format=format, legs=legs, roster_version=r_version, roster_checksum=r_checksum, prefix="build", roster=roster, high_thresh=high_thresh, miss_thresh=miss_thresh, unders_only=unders_only, overs_only=overs_only, print_to_console=print_report)


@app.command()
def simulate(
    file: str = typer.Option(None, help="JSON file of picks (list[PropPick])."),
    demo: bool = typer.Option(False, help="Use built-in demo picks."),
    format: str = typer.Option("power", help="power|flex"),
    legs: int = typer.Option(3, help="2–8 legs"),
    trials: int = typer.Option(20000, help="Monte Carlo trials"),
    roster_file: str = typer.Option(None, help="Canonical roster CSV for ACTIVE gate"),
    max_entries: int = typer.Option(1, help="Simulate top N entries (default 1)"),
    high_thresh: float = typer.Option(0.80, help="Threshold for high-confidence hits (0..1)"),
    miss_thresh: float = typer.Option(0.40, help="Threshold for miss probability (0..1)"),
    unders_only: bool = typer.Option(False, help="Render only UNDERS in cheat sheet"),
    overs_only: bool = typer.Option(False, help="Render only OVERS in cheat sheet"),
    print_report: bool = typer.Option(False, help="Print set report and cheat sheet to terminal after saving"),
    bypass_roster: bool = typer.Option(False, help="Skip roster gate (NOT recommended)")
):
    """Run Monte Carlo simulation for top EV entries built from the provided picks."""
    if legs < 2 or legs > settings.max_legs:
        raise typer.BadParameter(f"legs must be between 2 and {settings.max_legs}")

    # Load picks
    if demo:
        picks = _demo_picks()
    else:
        if not file:
            raise typer.BadParameter("Provide --file or --demo.")
        raw = json.loads(open(file, "r", encoding="utf-8").read())
        picks = [PropPick(**x) for x in raw]

    # Roster Gate
    roster_path = roster_file or "data_center/rosters/NBA_active_roster_current.csv"
    if bypass_roster:
        console.print(Panel.fit(
            "Roster Gate: BYPASSED (using provided picks as-is)",
            border_style="red",
            title="Roster Gate"
        ))
        roster = None
        r_version = "BYPASS"
        r_checksum = "-"
    else:
        try:
            roster = load_roster(roster_path)
            gated = apply_roster_gate(picks, roster)  # type: ignore[arg-type]
            r_version = roster_version(roster, roster_path)
            r_checksum = roster_checksum(roster_path)
        except RosterGateError as e:
            console.print(f"[red]\n[FATAL] Roster Gate Failed: {e}[/red]")
            console.print(
                "[yellow]Hint:[/] Provide a matching roster CSV via --roster-file (slate-specific ACTIVE list).\n"
                "    Example: --roster-file \"data_center/rosters/NBA_active_roster_BOS_POR.csv\"\n"
                "Or temporarily skip with [dim]--bypass-roster[/dim] (not recommended)."
            )
            raise typer.Exit(1)

        console.print(Panel.fit(
            f"Roster version: [bold]{r_version}[/bold]\n"
            f"Gated picks: {len(gated)} of {len(picks)}",
            border_style="yellow",
            title="Roster Gate"
        ))
        picks = cast(list[PropPick], gated)

    # Rank picks
    ranked = []
    for i, p in enumerate(picks):
        p_hit = prob_hit(p.line, p.direction, recent_values=p.recent_values, mu=p.mu, sigma=p.sigma)
        # status downgrade (optional) — only if roster available
        if roster is not None:
            status = get_player_status(roster, p.player)
            if status == "QUESTIONABLE":
                p_hit = max(0.0, float(p_hit) - 0.08)
            elif status == "DOUBTFUL":
                p_hit = max(0.0, float(p_hit) - 0.15)
        ranked.append({
            "id": i,
            "league": p.league,
            "player": p.player,
            "team": p.team,
            "stat": p.stat,
            "line": p.line,
            "direction": p.direction,
            "p_hit": float(p_hit),
        })

    table = power_table() if format.lower() == "power" else flex_table()

    # Build entries and simulate top ones
    entries = build_entries(
        picks=ranked,
        payout_table=table,
        legs=legs,
        min_teams=settings.min_teams_per_entry,
        max_entries=max_entries,
        same_team_penalty=0.0,
        max_player_legs=1,
        max_team_legs=0,
        correlation_penalty=0.0,
    )

    if not entries:
        console.print("[red]No entries could be built for simulation.[/red]")
        raise typer.Exit(1)

    # Attach roster metadata to each entry
    for e in entries:
        e["roster_version"] = r_version
        e["roster_checksum"] = r_checksum
        e["roster_gate"] = "BYPASS" if bypass_roster else "PASSED"

    sim_table = Table(title=f"Monte Carlo Simulation (format={format}, legs={legs}, trials={trials})")
    sim_table.add_column("Entry #")
    sim_table.add_column("EV (mean)")
    sim_table.add_column("Payout μ")
    sim_table.add_column("Payout σ")
    sim_table.add_column("Hits Probabilities (k: p)")

    for idx, e in enumerate(entries, start=1):
        result = monte_carlo_ev(e["p_list"], table, legs, trials=trials)
        hits_str = ", ".join([f"{k}:{v:.2f}" for k, v in sorted(result["hits_prob"].items())])
        sim_table.add_row(
            str(idx),
            f"{result['ev_mean']:.4f}",
            f"{result['payout_mean']:.3f}",
            f"{result['payout_std']:.3f}",
            hits_str,
        )

    console.print(sim_table)
    console.print(f"\n[dim]Roster: {r_version} | checksum={r_checksum}[/dim]")

    # Persist a set report grouped by OVER/UNDER for simulated entries
    _write_set_report(entries, format=format, legs=legs, roster_version=r_version, roster_checksum=r_checksum, prefix="monte_carlo", print_to_console=print_report)
    # Persist a cheat sheet style report for simulated entries
    _write_cheatsheet(picks, entries, format=format, legs=legs, roster_version=r_version, roster_checksum=r_checksum, prefix="monte_carlo", roster=roster, high_thresh=high_thresh, miss_thresh=miss_thresh, unders_only=unders_only, overs_only=overs_only, print_to_console=print_report)


@app.command()
def analyze(
    data_file: str = typer.Option(None, help="JSON file with player/prop data"),
    demo: bool = typer.Option(False, help="Use built-in demo data"),
    live: bool = typer.Option(False, help="Fetch LIVE data from ESPN"),
    teams: str = typer.Option("PIT,CLE,JAX,IND", help="Comma-separated team abbreviations for --live"),
    week: int = typer.Option(17, help="NFL week number for --live"),
    pdf: bool = typer.Option(False, help="Generate PDF report"),
    output_dir: str = typer.Option("outputs", help="Output directory for PDF"),
    validate_starters: bool = typer.Option(True, help="Validate QB starters against depth chart")
):
    """
    V2.0 Analysis with Matchup Context, Volatility, Correlations, and Value Scores.
    
    Use --live to fetch REAL data from ESPN APIs.
    Use --demo for sample data (faster, no network).
    """
    
    # ===== STARTER VALIDATION GATE =====
    # Week 17 2025 actual starters (update weekly!)
    VERIFIED_STARTERS = {
        "PIT": {"QB": "Aaron Rodgers"},      # Not Russell Wilson
        "CLE": {"QB": "Shedeur Sanders"},    # 2025 Draft pick, starting  
        "IND": {"QB": "Anthony Richardson"},  # Not Joe Flacco
        "JAX": {"QB": "Trevor Lawrence"},    # Back from IR
        "TB": {"QB": "Baker Mayfield"},
        "MIA": {"QB": "Tua Tagovailoa"},
        "NE": {"QB": "Drake Maye"},
        "NYJ": {"QB": "Aaron Rodgers"},
        "ARI": {"QB": "Kyler Murray"},
        "CIN": {"QB": "Joe Burrow"},
        "NO": {"QB": "Derek Carr"},
        "TEN": {"QB": "Will Levis"},
    }
    
    # ===== LIVE ESPN DATA =====
    if live:
        team_list = [t.strip().upper() for t in teams.split(",")]
        players, defense_rankings, correlation_groups = _fetch_live_espn_data(team_list, week)
        
        if not players:
            console.print("[red]No players found from ESPN. Check team names.[/red]")
            raise typer.Exit(1)
            
        # Validate starters for live data too
        if validate_starters:
            console.print()
            console.print("[bold yellow]═══ STARTER VALIDATION ═══[/bold yellow]")
            validated_players = []
            for player in players:
                if player.position == "QB":
                    expected_qb = VERIFIED_STARTERS.get(player.team, {}).get("QB")
                    if expected_qb and player.name != expected_qb:
                        console.print(f"  [red]✗ SKIPPED:[/red] {player.name} ({player.team} QB) - "
                                     f"Expected starter: {expected_qb}")
                        continue
                    else:
                        console.print(f"  [green]✓ VERIFIED:[/green] {player.name} ({player.team} QB)")
                validated_players.append(player)
            players = validated_players
    
    elif demo:
        # ===== DEFENSE RANKINGS (1=best, 32=worst) =====
        defense_rankings = {
            "CLE": DefenseRanking(rush=18, passing=20, overall=15, red_zone=12, sacks_allowed=28),
            "PIT": DefenseRanking(rush=3, passing=8, overall=5, red_zone=6, sacks_allowed=12),
            "IND": DefenseRanking(rush=28, passing=22, overall=26, red_zone=25, sacks_allowed=30),
            "JAX": DefenseRanking(rush=24, passing=28, overall=27, red_zone=28, sacks_allowed=26)
        }
        
        # ===== CORRELATION GROUPS (updated with correct players) =====
        correlation_groups = [
            CorrelationGroup(
                name="PIT Passing Game",
                players=["Aaron Rodgers", "George Pickens", "Pat Freiermuth"],
                props=["Pass Yards", "Rec Yards", "Receptions"],
                dependency="Pass volume dependent"
            ),
            CorrelationGroup(
                name="JAX Rush Committee",
                players=["Travis Etienne", "Tank Bigsby"],
                props=["Rush Yards", "Attempts"],
                dependency="Negative correlation - zero-sum touches"
            ),
            CorrelationGroup(
                name="PIT Defense vs CLE",
                players=["Myles Garrett", "T.J. Watt", "Nick Chubb"],
                props=["Sacks", "Rush Yards"],
                dependency="PIT D limiting CLE run = more pass rush opps"
            ),
            CorrelationGroup(
                name="IND Run Game",
                players=["Jonathan Taylor", "Michael Pittman Jr"],
                props=["Rush Yards", "Rec Yards"],
                dependency="Game script dependent"
            ),
            CorrelationGroup(
                name="JAX Passing Game",
                players=["Mac Jones", "Brian Thomas Jr", "Evan Engram"],
                props=["Pass Yards", "Rec Yards", "Receptions"],
                dependency="Game script dependent - likely trailing"
            )
        ]
        
        # ===== PLAYER DATA (VALIDATED - Position players only, no invalid QBs) =====
        players = [
            # === PITTSBURGH STEELERS (@ CLE) ===
            Player(
                name="Jaylen Warren", team="PIT", opponent="CLE", position="RB",
                props=[
                    PropBet(stat="Rush Yards", line=30.5, prop_type="rush", 
                           game_logs=[45, 38, 52, 41, 55, 33, 48, 42]),
                    PropBet(stat="Rush+Rec", line=55.5, prop_type="rush_rec",
                           game_logs=[62, 55, 71, 58, 68, 45, 61, 57])
                ],
                context=PlayerContext(injury="Hip - practicing", snap_pct=45.0)
            ),
            Player(
                name="Pat Freiermuth", team="PIT", opponent="CLE", position="TE",
                props=[
                    PropBet(stat="Receptions", line=3.5, prop_type="rec_count",
                           game_logs=[5, 4, 6, 3, 5, 4, 7, 5]),
                    PropBet(stat="Rec Yards", line=35.5, prop_type="rec",
                           game_logs=[48, 42, 55, 38, 52, 35, 61, 45])
                ]
            ),
            # NOTE: Russell Wilson REMOVED - Aaron Rodgers is PIT QB1
            # QB props require fresh data pull from verified source
            
            # === CLEVELAND BROWNS (vs PIT) ===
            # NOTE: Jameis Winston REMOVED - DTR is CLE QB1
            Player(
                name="Nick Chubb", team="CLE", opponent="PIT", position="RB",
                props=[
                    PropBet(stat="Rush Yards", line=45.5, prop_type="rush",
                           game_logs=[42, 38, 35, 28, 45, 32, 41, 30])
                ],
                context=PlayerContext(injury="Limited snap count", snap_pct=45.0)
            ),
            Player(
                name="Myles Garrett", team="CLE", opponent="PIT", position="DE",
                props=[
                    PropBet(stat="Sacks", line=0.5, prop_type="sack",
                           game_logs=[1.5, 1.0, 0.5, 2.0, 1.0, 0.0, 1.5, 1.0])
                ]
            ),
            
            # === JACKSONVILLE JAGUARS (@ IND) ===
            Player(
                name="Travis Etienne", team="JAX", opponent="IND", position="RB",
                props=[
                    PropBet(stat="Rush Yards", line=67.5, prop_type="rush",
                           game_logs=[45, 52, 38, 55, 48, 42, 61, 50]),
                    PropBet(stat="Rush+Rec", line=85.5, prop_type="rush_rec",
                           game_logs=[58, 65, 52, 72, 62, 55, 78, 61])
                ],
                context=PlayerContext(role_change="Bigsby taking more carries")
            ),
            Player(
                name="Brian Thomas Jr", team="JAX", opponent="IND", position="WR",
                props=[
                    PropBet(stat="Rec Yards", line=55.5, prop_type="rec",
                           game_logs=[72, 85, 58, 95, 68, 78, 102, 75]),
                    PropBet(stat="Receptions", line=4.5, prop_type="rec_count",
                           game_logs=[5, 6, 4, 7, 5, 6, 8, 6])
                ]
            ),
            # Mac Jones - JAX QB (Trevor Lawrence on IR)
            Player(
                name="Mac Jones", team="JAX", opponent="IND", position="QB",
                props=[
                    PropBet(stat="Pass Yards", line=195.5, prop_type="pass",
                           game_logs=[185, 210, 175, 225, 195, 205, 180, 190])
                ],
                context=PlayerContext(role_change="Starting due to Lawrence IR")
            ),
            
            # === INDIANAPOLIS COLTS (vs JAX) ===
            Player(
                name="Jonathan Taylor", team="IND", opponent="JAX", position="RB",
                props=[
                    PropBet(stat="Rush Yards", line=70.5, prop_type="rush",
                           game_logs=[125, 95, 145, 110, 135, 88, 150, 105]),
                    PropBet(stat="Rush TDs", line=0.5, prop_type="td",
                           game_logs=[2, 1, 2, 1, 1, 0, 2, 1]),
                    PropBet(stat="Rush Attempts", line=18.5, prop_type="rush_att",
                           game_logs=[22, 19, 25, 20, 23, 18, 26, 21])
                ]
            ),
            # NOTE: Joe Flacco REMOVED - Anthony Richardson is IND QB1
            Player(
                name="Michael Pittman Jr", team="IND", opponent="JAX", position="WR",
                props=[
                    PropBet(stat="Rec Yards", line=55.5, prop_type="rec",
                           game_logs=[68, 55, 82, 62, 75, 48, 85, 70]),
                    PropBet(stat="Receptions", line=5.5, prop_type="rec_count",
                           game_logs=[6, 5, 8, 6, 7, 4, 9, 7])
                ],
                context=PlayerContext(injury="OL injuries affecting pass game - Kelly out")
            )
        ]
        
        # ===== STARTER VALIDATION =====
        if validate_starters:
            console.print()
            console.print("[bold yellow]═══ STARTER VALIDATION ═══[/bold yellow]")
            validated_players = []
            for player in players:
                if player.position == "QB":
                    expected_qb = VERIFIED_STARTERS.get(player.team, {}).get("QB")
                    if expected_qb and player.name != expected_qb:
                        console.print(f"  [red]✗ SKIPPED:[/red] {player.name} ({player.team} QB) - "
                                     f"Expected starter: {expected_qb}")
                        continue
                    else:
                        console.print(f"  [green]✓ VERIFIED:[/green] {player.name} ({player.team} QB)")
                validated_players.append(player)
            players = validated_players
            
    else:
        # Load from JSON file
        if not data_file:
            console.print("[red]Error: Provide --data-file, --demo, or --live[/red]")
            raise typer.Exit(1)
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        defense_rankings = {k: DefenseRanking(**v) for k, v in data.get("defense_rankings", {}).items()}
        correlation_groups = [CorrelationGroup(**g) for g in data.get("correlation_groups", [])]
        players = []
        for p in data.get("players", []):
            context = PlayerContext(**p.get("context", {}))
            props = [PropBet(**prop) for prop in p.get("props", [])]
            players.append(Player(
                name=p["name"], team=p["team"], opponent=p["opponent"],
                position=p["position"], props=props, context=context
            ))
    
    # Initialize engine
    engine = AnalysisEngine(defense_rankings, correlation_groups)
    
    # Run analysis
    all_picks, correlations = engine.analyze_all(players)
    
    # === DISPLAY HEADER ===
    console.print()
    console.print(Panel(
        Text("UNDERDOG FANTASY ANALYSIS v2.0", style="bold white", justify="center"),
        subtitle=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        border_style="cyan"
    ))
    
    # === PRIORITY PICKS ===
    console.print()
    console.print("[bold cyan]═══ TOP PRIORITY PICKS (Value Score 70+) ═══[/bold cyan]")
    
    priority_table = Table(box=box.ROUNDED)
    priority_table.add_column("Rank", style="bold white")
    priority_table.add_column("Player", style="cyan")
    priority_table.add_column("Stat", style="white")
    priority_table.add_column("Line", style="yellow")
    priority_table.add_column("Proj", style="green")
    priority_table.add_column("Edge", style="bold")
    priority_table.add_column("Hit%", style="white")
    priority_table.add_column("Trend", style="white")
    priority_table.add_column("Value", style="bold magenta")
    priority_table.add_column("Play", style="bold")
    
    top_picks = [p for p in all_picks if p.value_score >= 70][:10]
    for i, pick in enumerate(top_picks, 1):
        edge_style = "green" if pick.edge > 0 else "red"
        play_style = "green bold" if pick.play == PlayDirection.OVER else "red bold"
        
        priority_table.add_row(
            str(i),
            f"{pick.player}",
            pick.stat,
            f"{pick.line}",
            f"{pick.adjusted_proj:.1f}",
            f"[{edge_style}]{pick.edge:+.1f}[/{edge_style}]",
            f"{pick.hit_rate:.0f}%",
            f"{get_trend_icon(pick.trend)} {pick.trend}",
            f"{pick.value_score:.0f}",
            f"[{play_style}]{pick.play.value}[/{play_style}]"
        )
    
    console.print(priority_table)
    
    # === SLAM PLAYS ===
    console.print()
    console.print("[bold green]═══ SLAM OVERS ═══[/bold green]")
    slam_overs = [p for p in all_picks if p.priority == Priority.SLAM and p.play == PlayDirection.OVER]
    for pick in slam_overs:
        console.print(f"  🔥 {pick.player} {pick.stat} OVER {pick.line} "
                     f"(Proj: {pick.adjusted_proj:.1f}, Hit: {pick.hit_rate:.0f}%, Edge: {pick.edge:+.1f})")
    
    console.print()
    console.print("[bold red]═══ SLAM UNDERS ═══[/bold red]")
    slam_unders = [p for p in all_picks if p.priority == Priority.SLAM and p.play == PlayDirection.UNDER]
    for pick in slam_unders:
        console.print(f"  ❄️ {pick.player} {pick.stat} UNDER {pick.line} "
                     f"(Proj: {pick.adjusted_proj:.1f}, Hit: {pick.hit_rate:.0f}%, Edge: {pick.edge:+.1f})")
    
    # === CORRELATION WARNINGS ===
    if correlations:
        console.print()
        console.print("[bold yellow]═══ CORRELATION WARNINGS ═══[/bold yellow]")
        for corr in correlations:
            console.print(f"  ⚠️ [yellow]{corr['group_name']}[/yellow]: "
                         f"{', '.join([f'{p[0]} ({p[1]})' for p in corr['players']])}")
            console.print(f"     └─ {corr['dependency']}")
    
    # === SUMMARY TABLE ===
    console.print()
    console.print("[bold white]═══ FULL SUMMARY ═══[/bold white]")
    
    summary_table = Table(box=box.SIMPLE)
    summary_table.add_column("Player", style="cyan")
    summary_table.add_column("Stat")
    summary_table.add_column("Line", justify="center")
    summary_table.add_column("Proj", justify="center")
    summary_table.add_column("Edge", justify="center")
    summary_table.add_column("Hit%", justify="center")
    summary_table.add_column("Consistency")
    summary_table.add_column("Matchup", justify="center")
    summary_table.add_column("Value", justify="center")
    summary_table.add_column("Play", justify="center")
    summary_table.add_column("Priority")
    
    for pick in all_picks:
        edge_style = "green" if pick.edge > 0 else "red"
        play_style = "green" if pick.play == PlayDirection.OVER else ("red" if pick.play == PlayDirection.UNDER else "white")
        priority_style = {
            Priority.SLAM: "bold green",
            Priority.STRONG: "green",
            Priority.LEAN: "yellow",
            Priority.SKIP: "dim"
        }.get(pick.priority, "white")
        
        matchup_str = f"{pick.matchup_mult:.2f}x" if pick.matchup_mult != 1.0 else "1.00x"
        
        summary_table.add_row(
            pick.player,
            pick.stat,
            f"{pick.line}",
            f"{pick.adjusted_proj:.1f}",
            f"[{edge_style}]{pick.edge:+.1f}[/{edge_style}]",
            f"{pick.hit_rate:.0f}%",
            f"{get_consistency_icon(pick.consistency)}",
            matchup_str,
            f"{pick.value_score:.0f}",
            f"[{play_style}]{pick.play.value}[/{play_style}]",
            f"[{priority_style}]{pick.priority.value}[/{priority_style}]"
        )
    
    console.print(summary_table)
    
    # === LOCK OF THE DAY ===
    if top_picks:
        lock = top_picks[0]
        console.print()
        console.print(Panel(
            f"[bold yellow]🔒 LOCK OF THE DAY 🔒[/bold yellow]\n\n"
            f"[bold white]{lock.player}[/bold white] {lock.stat} "
            f"[bold green]{lock.play.value}[/bold green] {lock.line}\n\n"
            f"Projection: {lock.adjusted_proj:.1f} | Edge: {lock.edge:+.1f} ({lock.edge_pct:+.1f}%)\n"
            f"Hit Rate: {lock.hit_rate:.0f}% | Consistency: {lock.consistency}\n"
            f"Trend: {get_trend_icon(lock.trend)} {lock.trend} | Value Score: {lock.value_score:.0f}",
            border_style="yellow"
        ))
    
    # === GENERATE PDF ===
    if pdf:
        try:
            from scripts.generate_v2_pdf_fixed import generate_pdf
            Path(output_dir).mkdir(exist_ok=True)
            # Current generator uses static analyzed data and returns path
            pdf_path = generate_pdf()
            console.print(f"\n[green]✓ PDF saved to: {pdf_path}[/green]")
        except Exception as e:
            console.print(f"\n[red]Error generating PDF: {e}[/red]")


@app.command()
def learn(
    date: str = typer.Option(None, help="Slate date (YYYY-MM-DD). If omitted, use all rows."),
    output_dir: str = typer.Option("outputs", help="Directory to write learning reports into."),
):
    """Run the calibration learning loop and write report files.

    This is presentation-only. All learning logic lives in
    `ufa.analysis.learning_loop` and the outcome labeling module.
    """

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    # Derive suffix for filenames
    if date:
        suffix = date.replace("-", "")
    else:
        suffix = datetime.now().strftime("%Y%m%d")

    # Text report (human-readable)
    try:
        report = learning_loop.format_learning_report(date_filter=date)
        txt_path = out_dir / f"learning_report_{suffix}.txt"
        txt_path.write_text(report, encoding="utf-8")
        console.print(f"[green]✓ Learning report saved to: {txt_path}[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # JSON suggestions (optional, structured summary)
    try:
        summary = learning_loop.learning_summary(date_filter=date)
        json_path = out_dir / f"learning_update_suggestions_{suffix}.json"
        json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        console.print(f"[green]✓ Learning suggestions saved to: {json_path}[/green]")
    except Exception as e:
        console.print(f"[yellow]Warning: could not write learning suggestions JSON: {e}[/yellow]")


@app.command()
def verify(
    league: str = typer.Option(..., help="League, e.g. NBA or NFL"),
    date: str = typer.Option(..., help="Slate date YYYY-MM-DD"),
    output_dir: str = typer.Option("outputs", help="Directory to write verification reports into."),
):
    """Verify post-game data correctness and learning readiness for a slate.

    This command is **diagnostic only**:

    - Does NOT write to calibration_history.csv
    - Does NOT label outcomes
    - Does NOT trigger learning
    """

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    suffix = date.replace("-", "")

    # Run core verification engine (read-only)
    summary = verification.run_verification(league=league, slate_date=date)

    # JSON log (machine-readable)
    json_payload = verification.summary_to_dict(summary)
    json_path = out_dir / f"verification_log_{suffix}.json"
    try:
        json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
        console.print(f"[green] Verification log saved to: {json_path}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to write verification log JSON: {e}[/red]")

    # Human-readable report
    report_text = verification.format_human_report(summary)
    txt_path = out_dir / f"verification_report_{suffix}.txt"
    try:
        txt_path.write_text(report_text, encoding="utf-8")
        console.print(f"[green] Verification report saved to: {txt_path}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to write verification report: {e}[/red]")


def _write_set_report(entries, format: str, legs: int, roster_version: str, roster_checksum: str, prefix: str = "", print_to_console: bool = False):
    """Write a text report to outputs/ grouping picks by OVER/UNDER for each entry.

    Each entry section lists OVER and UNDER picks separately with player, stat, line, and P(hit).
    """
    try:
        out_dir = Path("outputs")
        out_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{prefix+'_' if prefix else ''}set_report_{format}_{legs}L_{ts}.txt"
        out_path = out_dir / base

        lines_out = []
        lines_out.append(f"UNDERDOG Set Report")
        lines_out.append(f"Format: {format} | Legs: {legs}")
        lines_out.append(f"Roster: {roster_version} | checksum={roster_checksum}")
        lines_out.append("")

        for idx, e in enumerate(entries, start=1):
            lines_out.append(f"Entry #{idx} — EV: {e.get('ev_units', 0):.4f}")
            overs = []
            unders = []
            players = e.get("players", [])
            stats = e.get("stats", [])
            dirs = e.get("directions", [])
            entry_lines = e.get("lines", [])
            p_list = e.get("p_list", [])

            for i in range(len(players)):
                dirn = (dirs[i] if i < len(dirs) else "") or ""
                stat = stats[i] if i < len(stats) else ""
                line_val = entry_lines[i] if i < len(entry_lines) else ""
                p_hit_val = p_list[i] if i < len(p_list) else 0.0
                item = f"{players[i]} — {stat} {dirn.upper()} {line_val} (P={p_hit_val:.3f})"
                if dirn.lower() in ("higher", "over"):
                    overs.append(item)
                elif dirn.lower() in ("lower", "under"):
                    unders.append(item)
                else:
                    overs.append(item)

            if overs:
                lines_out.append("  OVERs:")
                for s in overs:
                    lines_out.append(f"    - {s}")
            if unders:
                lines_out.append("  UNDERs:")
                for s in unders:
                    lines_out.append(f"    - {s}")
            lines_out.append("")

        content = "\n".join(lines_out)
        out_path.write_text(content, encoding="utf-8")
        console.print(f"\n[green]✓ Set report saved to: {out_path}[/green]")
        if print_to_console:
            console.print("\n[bold cyan]═══ SET REPORT ═══[/bold cyan]")
            console.print(content)
        return str(out_path)
    except Exception as err:
        console.print(f"\n[yellow]Warning: failed to write set report: {err}[/yellow]")

def _write_cheatsheet(picks, entries, format: str, legs: int, roster_version: str, roster_checksum: str, prefix: str = "", roster=None, high_thresh: float = 0.80, miss_thresh: float = 0.40, unders_only: bool = False, overs_only: bool = False, print_to_console: bool = False):
    """Generate a cheat sheet style text report summarizing SLAM/LEAN plays from the selected entries.

    Categorization is based on P(hit) thresholds:
      - SLAM: 0.90+
      - STRONG: 0.80–0.89
      - LEAN: 0.70–0.79
    """
    try:
        out_dir = Path("outputs")
        out_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{prefix+'_' if prefix else ''}cheatsheet_{format}_{legs}L_{ts}.txt"
        out_path = out_dir / base

        # Build a lookup from (player, stat, direction, line) -> avg from recent_values if present
        def key_for_pick(p):
            return (p.player, p.stat, p.direction, p.line)

        avg_lookup = {}
        for p in picks:
            avg_val = None
            if p.recent_values:
                try:
                    avg_val = round(mean([float(x) for x in p.recent_values]), 1)
                except Exception:
                    avg_val = None
            avg_lookup[key_for_pick(p)] = avg_val

        # Collect unique legs from entries (include team info via picks lookup)
        seen = set()
        legs_out = []
        for e in entries:
            players = e.get("players", [])
            stats = e.get("stats", [])
            dirs = e.get("directions", [])
            lines_vals = e.get("lines", [])
            opponents = e.get("opponents", [])
            p_list = e.get("p_list", [])
            for i in range(len(players)):
                k = (players[i], stats[i] if i < len(stats) else "", (dirs[i] if i < len(dirs) else ""), lines_vals[i] if i < len(lines_vals) else "")
                if k in seen:
                    continue
                seen.add(k)
                # find team from original picks
                team_val = ""
                for p in picks:
                    if p.player == players[i] and p.stat == (stats[i] if i < len(stats) else "") and p.direction.upper() == ((dirs[i] if i < len(dirs) else "").upper()) and p.line == (lines_vals[i] if i < len(lines_vals) else None):
                        team_val = p.team
                        break
                legs_out.append({
                    "player": players[i],
                    "stat": stats[i] if i < len(stats) else "",
                    "direction": (dirs[i] if i < len(dirs) else "").upper(),
                    "line": lines_vals[i] if i < len(lines_vals) else "",
                    "p_hit": p_list[i] if i < len(p_list) else 0.0,
                    "avg": avg_lookup.get(k),
                    "team": team_val,
                    "opponent": opponents[i] if i < len(opponents) else "",
                })

        # If the user requests unders-only but the selection lacks explicit UNDERS,
        # derive inverse under plays from OVERs: P(UNDER) = 1 - P(OVER).
        # This helps surface high-probability UNDERS even when picks are overs-only.
        if unders_only and not overs_only:
            existing_under_keys = {(l["player"], l["stat"], "UNDER", l["line"]) for l in legs_out if l["direction"] in ("LOWER", "UNDER")}
            derived_unders = []
            for l in legs_out:
                if l["direction"] in ("HIGHER", "OVER"):
                    k = (l["player"], l["stat"], "UNDER", l["line"]) 
                    if k in existing_under_keys:
                        continue
                    try:
                        p_under = 1.0 - float(l["p_hit"]) 
                    except Exception:
                        p_under = 0.0
                    # clone and flip direction/p_hit
                    d = dict(l)
                    d["direction"] = "UNDER"
                    d["p_hit"] = p_under
                    derived_unders.append(d)
            # Extend with derived UNDERS so filters and categorization can include them
            legs_out.extend(derived_unders)

        # Optional filter: unders-only or overs-only (mutually exclusive)
        filter_note = None
        if unders_only and not overs_only:
            legs_out = [l for l in legs_out if l["direction"] in ("LOWER", "UNDER")]
            filter_note = "Filter: UNDERS ONLY"
        elif overs_only and not unders_only:
            legs_out = [l for l in legs_out if l["direction"] in ("HIGHER", "OVER")]
            filter_note = "Filter: OVERS ONLY"

        # Categorize
        slam = [l for l in legs_out if l["p_hit"] >= 0.90]
        strong = [l for l in legs_out if 0.80 <= l["p_hit"] < 0.90]
        lean = [l for l in legs_out if 0.70 <= l["p_hit"] < 0.80]

        lines_out = []
        lines_out.append("================================================================================")
        lines_out.append(f"     UNDERDOG FANTASY - {legs}-LEG {format.upper()} CHEAT SHEET")
        lines_out.append(f"     Generated: {datetime.now().strftime('%B %d, %Y')} | Roster: {roster_version}")
        if filter_note:
            lines_out.append(f"     {filter_note}")
        lines_out.append("================================================================================")
        lines_out.append("")

        def render_block(title, items):
            lines_out.append("┌" + "─" * 73 + "┐")
            lines_out.append(f"│  {title:<69}│")
            lines_out.append("├" + "─" * 73 + "┤")
            if not items:
                lines_out.append("│  (none)" + " " * 61 + "│")
            for it in items:
                avg_str = f"(Avg: {it['avg']})" if it.get("avg") is not None else ""
                conf = int(round(it["p_hit"] * 100))
                play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
                lines_out.append(
                    f"│    • {it['player']} {play} {it['line']} {it['stat']:<12}  {avg_str:<18}  [{conf}% Conf]     │"
                )
            lines_out.append("└" + "─" * 73 + "┘")
            lines_out.append("")

        render_block("SLAM PLAYS", slam)
        render_block("STRONG PLAYS", strong)
        render_block("LEAN PLAYS", lean)

        # HIGH CONFIDENCE (≥high_thresh) split by OVER/UNDER
        high_conf = [l for l in legs_out if l["p_hit"] >= float(high_thresh)]
        high_over = [l for l in high_conf if l["direction"] in ("HIGHER", "OVER")]
        high_under = [l for l in high_conf if l["direction"] in ("LOWER", "UNDER")]

        lines_out.append("================================================================================")
        lines_out.append(f"                   HIGH CONFIDENCE (≥{int(round(high_thresh*100))}%) - BY PLAY DIRECTION")
        lines_out.append("================================================================================")
        render_block(f"HIGH CONF OVERS (≥{int(round(high_thresh*100))}%)", high_over)
        render_block(f"HIGH CONF UNDERS (≥{int(round(high_thresh*100))}%)", high_under)

        # MISS RISK (≥miss_thresh) split by OVER/UNDER, using miss probability
        miss_conf = [l for l in legs_out if (1.0 - float(l["p_hit"])) >= float(miss_thresh)]
        miss_over = [l for l in miss_conf if l["direction"] in ("HIGHER", "OVER")]
        miss_under = [l for l in miss_conf if l["direction"] in ("LOWER", "UNDER")]

        lines_out.append("================================================================================")
        lines_out.append(f"                       MISS RISK (≥{int(round(miss_thresh*100))}%) - BY DIRECTION")
        lines_out.append("================================================================================")
        render_block(f"MISS RISK - OVERS (≥{int(round(miss_thresh*100))}%)", miss_over)
        render_block(f"MISS RISK - UNDERS (≥{int(round(miss_thresh*100))}%)", miss_under)

        # TOP 10 PLAYS
        lines_out.append("================================================================================")
        lines_out.append("                     TOP 10 PLAYS ACROSS SELECTION")
        lines_out.append("================================================================================")
        top10 = sorted(legs_out, key=lambda x: x["p_hit"], reverse=True)[:10]
        lines_out.append("    #   PLAYER                  TEAM   PROP            PLAY     LINE     AVG     CONF")
        lines_out.append("   " + "-" * 76)
        for i, it in enumerate(top10, start=1):
            team = it.get("team", "")
            play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
            avg_str = f"{it['avg']:.1f}" if isinstance(it.get("avg"), (int, float)) else "-"
            conf = int(round(it["p_hit"] * 100))
            lines_out.append(f"    {i:<2}  {it['player']:<22} {team:<5} {it['stat']:<14} {play:<7} {str(it['line']):<7} {avg_str:<7} {conf:>3}%")
        lines_out.append("")

        # TOP 10 OVERS and UNDERS separately
        lines_out.append("================================================================================")
        lines_out.append("                         TOP 10 OVERS | TOP 10 UNDERS")
        lines_out.append("================================================================================")
        overs_sel = [it for it in legs_out if it["direction"] in ("HIGHER", "OVER")]
        unders_sel = [it for it in legs_out if it["direction"] in ("LOWER", "UNDER")]
        top10_overs = sorted(overs_sel, key=lambda x: x["p_hit"], reverse=True)[:10]
        top10_unders = sorted(unders_sel, key=lambda x: x["p_hit"], reverse=True)[:10]

        def render_top10(title: str, items: list[dict]):
            lines_out.append("┌" + "─" * 73 + "┐")
            lines_out.append(f"│  {title:<69}│")
            lines_out.append("├" + "─" * 73 + "┤")
            if not items:
                lines_out.append("│  (none)" + " " * 61 + "│")
            for i, it in enumerate(items, start=1):
                avg_str = f"{it['avg']:.1f}" if isinstance(it.get("avg"), (int, float)) else "-"
                conf = int(round(it["p_hit"] * 100))
                play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
                lines_out.append(
                    f"│    {i:<2} {it['player']:<22} {it.get('team',''):<5} {it['stat']:<12} {play:<6} {str(it['line']):<6} avg={avg_str:<6} conf={conf:>3}%   │"
                )
            lines_out.append("└" + "─" * 73 + "┘")
            lines_out.append("")

        render_top10("TOP 10 OVERS", top10_overs)
        render_top10("TOP 10 UNDERS", top10_unders)

        # OVERS and UNDERS across selection
        lines_out.append("================================================================================")
        lines_out.append("                         OVERS & UNDERS (ALL SELECTED)")
        lines_out.append("================================================================================")
        render_block("ALL OVERS", overs_sel)
        render_block("ALL UNDERS", unders_sel)

        # GAME BLOCKS (TEAM vs OPPONENT)
        lines_out.append("================================================================================")
        lines_out.append("                           GAME-BY-GAME SUMMARY")
        lines_out.append("================================================================================")
        # Build game pairs from picks
        game_pairs = []
        seen_pairs = set()
        for p in picks:
            t = p.team
            o = p.opponent or ""
            if not t or not o:
                continue
            key = (t, o)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            game_pairs.append(key)

        # Helper to format team block
        def render_team_block(team_name: str, legs_for_team: list):
            lines_out.append("┌" + "─" * 73 + "┐")
            lines_out.append(f"│  {team_name:<69}│")
            lines_out.append("├" + "─" * 73 + "┤")
            # Split by category
            slam_t = [l for l in legs_for_team if l["p_hit"] >= 0.90]
            lean_t = [l for l in legs_for_team if 0.70 <= l["p_hit"] < 0.80]
            strong_t = [l for l in legs_for_team if 0.80 <= l["p_hit"] < 0.90]
            if slam_t:
                lines_out.append("│  SLAM PLAYS:                                                                │")
                for it in slam_t:
                    avg_str = f"(Avg: {it['avg']})" if it.get("avg") is not None else ""
                    conf = int(round(it["p_hit"] * 100))
                    play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
                    lines_out.append(f"│    ✓ {it['player']} {play} {it['line']} {it['stat']:<12}  {avg_str:<18}  [{conf}% Conf]         │")
            if strong_t:
                lines_out.append("│                                                                             │")
                lines_out.append("│  STRONG PLAYS:                                                              │")
                for it in strong_t:
                    avg_str = f"(Avg: {it['avg']})" if it.get("avg") is not None else ""
                    conf = int(round(it["p_hit"] * 100))
                    play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
                    lines_out.append(f"│    ✓ {it['player']} {play} {it['line']} {it['stat']:<12}  {avg_str:<18}  [{conf}% Conf]         │")
            if lean_t:
                lines_out.append("│                                                                             │")
                lines_out.append("│  LEAN PLAYS:                                                                │")
                for it in lean_t:
                    avg_str = f"(Avg: {it['avg']})" if it.get("avg") is not None else ""
                    conf = int(round(it["p_hit"] * 100))
                    play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
                    lines_out.append(f"│    → {it['player']} {play} {it['line']} {it['stat']:<12}  {avg_str:<18}  [{conf}% Conf]         │")
            lines_out.append("└" + "─" * 73 + "┘")
            lines_out.append("")

        game_num = 1
        for (t, o) in game_pairs:
            lines_out.append("================================================================================")
            lines_out.append(f"                         GAME {game_num}: {t} @ {o}")
            lines_out.append("================================================================================")
            legs_t = [l for l in legs_out if l.get("team") == t and (l.get("opponent") == o or not l.get("opponent"))]
            legs_o = [l for l in legs_out if l.get("team") == o and (l.get("opponent") == t or not l.get("opponent"))]
            render_team_block(t, legs_t)
            render_team_block(o, legs_o)
            game_num += 1

        # PARLAY SUGGESTIONS (simple heuristic selection)
        lines_out.append("================================================================================")
        lines_out.append("                          PARLAY SUGGESTIONS")
        lines_out.append("================================================================================")
        def pick_unique(items, n):
            chosen = []
            seen_players = set()
            for it in items:
                if it["player"] in seen_players:
                    continue
                chosen.append(it)
                seen_players.add(it["player"])
                if len(chosen) >= n:
                    break
            return chosen
        safe3 = pick_unique(slam, 3) or pick_unique(strong, 3)
        value4 = pick_unique(slam + strong, 4)
        longshot5 = pick_unique(strong + lean, 5)
        def render_parlay(title, items):
            lines_out.append("")
            lines_out.append(f"  {title}:")
            lines_out.append("  " + "─" * (len(title) + 1))
            for it in items:
                play = "OVER" if it["direction"] in ("HIGHER", "OVER") else "UNDER"
                lines_out.append(f"  • {it['player']} {play} {it['line']} {it['stat']}")
        render_parlay("SAFE 3-LEG PARLAY", safe3)
        render_parlay("VALUE 4-LEG PARLAY", value4)
        render_parlay("LONGSHOT 5-LEG", longshot5)
        lines_out.append("")

        # NOTES & WARNINGS (Roster status)
        lines_out.append("================================================================================")
        lines_out.append("                            NOTES & WARNINGS")
        lines_out.append("================================================================================")
        qd_notes = []
        if roster is not None:
            noted = set()
            for it in legs_out:
                player = it["player"]
                if player in noted:
                    continue
                status = get_player_status(roster, player)
                if status in ("QUESTIONABLE", "DOUBTFUL"):
                    noted.add(player)
                    qd_notes.append(f"  • {player} - {status}")
        if qd_notes:
            lines_out.extend(qd_notes)
        else:
            lines_out.append("  • No active questionable/doubtful statuses among selected plays")
        lines_out.append("")
        lines_out.append("================================================================================")
        lines_out.append("              GOOD LUCK! ALWAYS GAMBLE RESPONSIBLY!")
        lines_out.append("================================================================================")

        content = "\n".join(lines_out)
        out_path.write_text(content, encoding="utf-8")
        console.print(f"\n[green]✓ Cheat sheet saved to: {out_path}[/green]")
        if print_to_console:
            console.print("\n[bold magenta]═══ CHEAT SHEET ═══[/bold magenta]")
            console.print(content)
        return str(out_path)
    except Exception as err:
        console.print(f"\n[yellow]Warning: failed to write cheat sheet: {err}[/yellow]")

if __name__ == "__main__":
    app()
