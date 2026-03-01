"""
mlb/mlb_menu.py
───────────────
MLB Baseball Props v1.0 — Statcast + Odds API

Menu:
  [1] Ingest MLB Slate    — Paste Underdog/DraftKings MLB props
  [A] Odds API Ingest     — Auto-fetch MLB props (no manual paste)
  [2] Analyze MLB Slate   — Run Normal-CDF probability analysis
  [V] View Results        — Show latest MLB analysis
  [R] Export Report       — Save human-readable report
  [T] Send to Telegram    — Broadcast picks
  [9] Settings            — Toggle modes
  [0] Exit / Back

Stats supported:
  hits, home_runs, rbi, runs, stolen_bases, strikeouts_batter
  total_bases, walks, pitcher_strikeouts, pitcher_outs, hits_allowed
  earned_runs_allowed, fantasy_points
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
_HERE        = Path(__file__).resolve().parent
PROJECT_ROOT = _HERE.parent
OUTPUTS_DIR  = PROJECT_ROOT / "outputs" / "mlb"
MLB_SETTINGS = PROJECT_ROOT / ".mlb_analyzer_settings.json"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Normal CDF (no scipy required)
# ─────────────────────────────────────────────────────────────────────────────
import math

def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def prob_hit(line: float, direction: str, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0 if (direction == "higher" and mu > line) else (1.0 if (direction == "lower" and mu < line) else 0.5)
    z = (mu - line) / sigma
    return _norm_cdf(z) if direction == "higher" else _norm_cdf(-z)

# ─────────────────────────────────────────────────────────────────────────────
# Stat configuration
# ─────────────────────────────────────────────────────────────────────────────

# key → (display_name, season_mu, season_sigma, is_pitcher)
MLB_STAT_DEFAULTS: Dict[str, Tuple[str, float, float, bool]] = {
    "hits":                      ("Hits",                    1.10, 0.90, False),
    "home_runs":                 ("Home Runs",               0.14, 0.37, False),
    "rbi":                       ("RBI",                     0.65, 0.90, False),
    "runs":                      ("Runs",                    0.55, 0.78, False),
    "stolen_bases":               ("Stolen Bases",            0.12, 0.36, False),
    "strikeouts_batter":          ("Strikeouts (Batter)",     0.85, 0.95, False),
    "total_bases":                ("Total Bases",             1.55, 1.30, False),
    "walks":                     ("Walks",                   0.32, 0.55, False),
    "pitcher_strikeouts":        ("Pitcher Strikeouts",      5.50, 2.20, True),
    "pitcher_outs":              ("Pitcher Outs",            14.5, 3.80, True),
    "hits_allowed":              ("Hits Allowed",            5.60, 2.50, True),
    "earned_runs_allowed":       ("ER Allowed",              2.65, 1.90, True),
    "fantasy_points":            ("Fantasy Points",          20.0, 12.0, False),
}

STAT_ALIASES: Dict[str, str] = {
    # Batter
    "h":                   "hits",
    "hit":                 "hits",
    "hr":                  "home_runs",
    "home run":            "home_runs",
    "home runs":           "home_runs",
    "homerun":             "home_runs",
    "homeruns":            "home_runs",
    "rbi":                 "rbi",
    "rbis":                "rbi",
    "run":                 "runs",
    "sb":                  "stolen_bases",
    "stolen base":         "stolen_bases",
    "stolen bases":        "stolen_bases",
    "k":                   "strikeouts_batter",
    "strikeout":           "strikeouts_batter",
    "strikeouts":          "strikeouts_batter",
    "batter strikeouts":   "strikeouts_batter",
    "hitter strikeouts":   "strikeouts_batter",
    "tb":                  "total_bases",
    "total base":          "total_bases",
    "total bases":         "total_bases",
    "bb":                  "walks",
    "walk":                "walks",
    "bases on balls":      "walks",
    "fantasy":             "fantasy_points",
    "fantasy points":      "fantasy_points",
    "fantasy pts":         "fantasy_points",
    # Pitcher
    "pitcher k":           "pitcher_strikeouts",
    "pitcher ks":          "pitcher_strikeouts",
    "pitcher strikeout":   "pitcher_strikeouts",
    "strikeouts pitcher":  "pitcher_strikeouts",
    "pitching strikeouts": "pitcher_strikeouts",
    "outs recorded":       "pitcher_outs",
    "pitcher outs":        "pitcher_outs",
    "hits allowed":        "hits_allowed",
    "ha":                  "hits_allowed",
    "earned runs":         "earned_runs_allowed",
    "er":                  "earned_runs_allowed",
    "era":                 "earned_runs_allowed",
    "earned runs allowed": "earned_runs_allowed",
}

DEFAULT_SETTINGS = {
    "soft_gates": True,
    "min_confidence": 55,
    "default_league": "MLB",
    "telegram_channel": "",
}


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

def load_settings() -> dict:
    if MLB_SETTINGS.exists():
        try:
            return {**DEFAULT_SETTINGS, **json.loads(MLB_SETTINGS.read_text())}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(s: dict):
    MLB_SETTINGS.write_text(json.dumps(s, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_player_stats_mlbapi(player_name: str, stat_key: str) -> Tuple[float, float, int]:
    """Fetch L10-game averages from MLB Stats API.
    Returns (mu, sigma, n_games).
    """
    try:
        import urllib.request
        import json as _json

        search_url = (
            f"https://statsapi.mlb.com/api/v1/people/search"
            f"?names={urllib.parse.quote(player_name)}&sportId=1"
        )
        with urllib.request.urlopen(search_url, timeout=6) as r:
            res = _json.loads(r.read())

        people = res.get("people", [])
        if not people:
            return 0.0, 0.0, 0

        pid = people[0]["id"]
        group = "pitching" if MLB_STAT_DEFAULTS.get(stat_key, ("", 0, 0, False))[3] else "hitting"

        stats_url = (
            f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
            f"?stats=gameLog&leagueListId=mlb_hist&season={datetime.now().year}&sportId=1&group={group}&limit=10"
        )
        with urllib.request.urlopen(stats_url, timeout=6) as r:
            sdata = _json.loads(r.read())

        splits = []
        for stat_block in sdata.get("stats", []):
            splits.extend(stat_block.get("splits", []))

        field_map = {
            "hits":                "hits",
            "home_runs":           "homeRuns",
            "rbi":                 "rbi",
            "runs":                "runs",
            "stolen_bases":        "stolenBases",
            "strikeouts_batter":   "strikeOuts",
            "total_bases":         "totalBases",
            "walks":               "baseOnBalls",
            "pitcher_strikeouts":  "strikeOuts",
            "pitcher_outs":        "outs",
            "hits_allowed":        "hits",
            "earned_runs_allowed": "earnedRuns",
        }

        api_field = field_map.get(stat_key)
        if not api_field or not splits:
            return 0.0, 0.0, 0

        vals = []
        for sp in splits[-10:]:
            v = sp.get("stat", {}).get(api_field)
            if v is not None:
                try:
                    vals.append(float(v))
                except Exception:
                    pass

        if not vals:
            return 0.0, 0.0, 0

        mu    = sum(vals) / len(vals)
        var   = sum((x - mu) ** 2 for x in vals) / len(vals)
        sigma = math.sqrt(var) if var > 0 else mu * 0.5
        return mu, sigma, len(vals)

    except Exception:
        return 0.0, 0.0, 0


def _fetch_statcast(player_name: str, stat_key: str) -> Tuple[float, float, int]:
    """Try pybaseball Statcast for batter/pitcher stats. Returns (mu, sigma, n)."""
    try:
        import pybaseball as pb
        from pybaseball import playerid_lookup

        parts = player_name.strip().split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
        else:
            return 0.0, 0.0, 0

        lookup = playerid_lookup(last, first)
        if lookup.empty:
            return 0.0, 0.0, 0

        pid = int(lookup.iloc[0]["key_mlbam"])
        season = datetime.now().year
        start = f"{season}-03-01"
        end   = datetime.now().strftime("%Y-%m-%d")

        is_pitcher = MLB_STAT_DEFAULTS.get(stat_key, ("", 0, 0, False))[3]

        if is_pitcher:
            df = pb.pitching_stats_range(start, end)
            df = df[df["IDfg"].astype(str).str.contains(str(pid), na=False)]
            if df.empty:
                return 0.0, 0.0, 0
            col_map = {
                "pitcher_strikeouts": "SO",
                "hits_allowed":       "H",
                "earned_runs_allowed": "ER",
                "pitcher_outs":       "IPouts",
            }
        else:
            df = pb.batting_stats_range(start, end)
            df = df[df["IDfg"].astype(str).str.contains(str(pid), na=False)]
            if df.empty:
                return 0.0, 0.0, 0
            col_map = {
                "hits":              "H",
                "home_runs":         "HR",
                "rbi":               "RBI",
                "runs":              "R",
                "stolen_bases":      "SB",
                "strikeouts_batter": "SO",
                "total_bases":       "TB",
                "walks":             "BB",
            }

        col = col_map.get(stat_key)
        if col and col in df.columns:
            vals = df[col].dropna().astype(float).tolist()[-10:]
            if vals:
                mu    = sum(vals) / len(vals)
                var   = sum((x - mu) ** 2 for x in vals) / max(len(vals) - 1, 1)
                sigma = math.sqrt(var) if var > 0 else mu * 0.5
                return mu, sigma, len(vals)

        return 0.0, 0.0, 0

    except Exception:
        return 0.0, 0.0, 0


def hydrate_mlb_stat(player: str, stat_key: str) -> Tuple[float, float, int, str]:
    """Get mu, sigma, n, source for a player/stat.
    Priority: pybaseball (Statcast) → MLB Stats API → league-average defaults.
    """
    # Try Statcast (pybaseball)
    mu, sigma, n = _fetch_statcast(player, stat_key)
    if n >= 5:
        return mu, sigma, n, "Statcast"

    # Try MLB Stats API
    mu2, sigma2, n2 = _fetch_player_stats_mlbapi(player, stat_key)
    if n2 >= 3:
        return mu2, sigma2, n2, "MLB_API"

    # Fallback: league-average defaults
    defaults = MLB_STAT_DEFAULTS.get(stat_key, ("Unknown", 1.0, 0.8, False))
    def_mu, def_sigma = defaults[1], defaults[2]
    return def_mu, def_sigma, 0, "DEFAULT"


def _get_mlb_games_today() -> List[dict]:
    """Return today's MLB games from MLB Stats API."""
    try:
        import urllib.request
        import json as _json
        import urllib.parse

        today = datetime.now().strftime("%Y-%m-%d")
        url   = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=team"

        with urllib.request.urlopen(url, timeout=8) as r:
            data = _json.loads(r.read())

        games = []
        for date_block in data.get("dates", []):
            for g in date_block.get("games", []):
                away = g.get("teams", {}).get("away", {}).get("team", {}).get("abbreviation", "?")
                home = g.get("teams", {}).get("home", {}).get("team", {}).get("abbreviation", "?")
                t    = g.get("gameDate", "")
                games.append({"away": away, "home": home, "time": t, "source": "mlb_api"})
        return games
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Props Parser
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_stat(text: str) -> Optional[str]:
    clean = text.strip().lower()
    # 1. Exact canonical key match (handles "home_runs", "pitcher_strikeouts", etc.)
    if clean in MLB_STAT_DEFAULTS:
        return clean
    # 2. Normalize underscores → spaces then try canonical keys
    clean_spaced = clean.replace("_", " ")
    for key in MLB_STAT_DEFAULTS:
        if key.replace("_", " ") == clean_spaced:
            return key
    # 3. Alias matching — short aliases (≤3 chars) must be an exact match;
    #    longer aliases may appear as substrings.
    for alias in sorted(STAT_ALIASES.keys(), key=len, reverse=True):
        if len(alias) <= 3:
            # Exact match only (avoids "er" matching "higher", "h" matching word-internal)
            if clean_spaced == alias or clean == alias:
                return STAT_ALIASES[alias]
        else:
            if alias in clean_spaced:
                return STAT_ALIASES[alias]
    return None


def parse_mlb_lines(text: str) -> List[dict]:
    """Parse Underdog/DK MLB prop paste into structured picks list."""
    picks   = []
    lines   = [l.strip() for l in text.strip().splitlines() if l.strip()]

    current_player    = None
    current_stat      = None   # stat found on its own line (multi-line format)
    current_direction = None   # direction found before line value

    i = 0
    def _emit(player, stat_key, line_val, dir_val):
        """Append a validated pick to picks."""
        if not player or not stat_key or line_val is None:
            return
        junk_kw = {"athlete", "avatar", "yes", "no", "more picks", "higher", "lower"}
        if any(kw in player.lower() for kw in junk_kw):
            return
        picks.append({
            "player":    player,
            "team":      "MLB",
            "position":  "P" if MLB_STAT_DEFAULTS.get(stat_key, ("", 0, 0, False))[3] else "B",
            "stat":      stat_key,
            "line":      line_val,
            "direction": dir_val or "higher",
            "raw":       f"{player} | {stat_key} {line_val}",
        })

    while i < len(lines):
        line = lines[i]

        # ── Skip garbage ─────────────────────────────────────────────────────
        if re.match(r"^\d+:\d+\s*(am|pm|et|ct|pt|cst|est)", line, re.I):
            i += 1
            continue
        if re.search(r"\bvs\.?\b|\b@\b", line, re.I) and not re.search(
            r"(hit|hr|rbi|run|sb|k|walk|str|base|era|out|pitch)", line, re.I
        ):
            i += 1
            continue

        line_lower = line.lower()

        # ── Direction keyword on this line ────────────────────────────────────
        direction = None
        for pat, dv in [
            (r"\bhigher\b|\bmore\b|\bover\b", "higher"),
            (r"\blower\b|\bless\b|\bunder\b", "lower"),
        ]:
            if re.search(pat, line_lower):
                direction = dv
                break

        # ── Number extraction ─────────────────────────────────────────────────
        nums = re.findall(r"\d+\.?\d*", line)

        # ── Stat key on this line ─────────────────────────────────────────────
        stat = _normalize_stat(line)

        # ══ CASE 1: Single-line format  "Gerrit Cole  pitcher_strikeouts 6.5 over" ══
        if nums and stat and current_player:
            _emit(current_player, stat, float(nums[-1]), direction)
            current_stat = None
            current_direction = None
            i += 1
            continue

        # ══ CASE 1b: Fully-inline line includes player name + stat + number ══
        # e.g. "Aaron Judge home_runs 0.5 higher" with no prior current_player
        if nums and stat and not current_player:
            # Strip numbers / stat / direction words to recover player name
            raw_player = line
            raw_player = re.sub(r"\b" + re.escape(stat.replace("_", " ")) + r"\b", "", raw_player, flags=re.I)
            raw_player = re.sub(r"\b" + re.escape(stat) + r"\b", "", raw_player, flags=re.I)
            raw_player = re.sub(r"\d+\.?\d*", "", raw_player)
            raw_player = re.sub(r"\b(higher|lower|more|less|over|under)\b", "", raw_player, flags=re.I)
            raw_player = raw_player.strip(" ,|:-")
            if len(raw_player) > 2:
                _emit(raw_player, stat, float(nums[-1]), direction)
                current_player = raw_player
                current_stat = None
                current_direction = None
            i += 1
            continue

        # ══ CASE 2: Direction-only line — tag the most-recent relevant pick ══
        if direction and not nums and not stat:
            if picks and picks[-1]["player"] == current_player:
                picks[-1]["direction"] = direction
            else:
                current_direction = direction
            i += 1
            continue

        # ══ CASE 3: Stat-only line (multi-line format, stat before or after number) ══
        if not nums and stat and direction is None:
            current_stat = stat
            i += 1
            continue

        # ══ CASE 4: Number-only line ══
        if nums and not stat and not direction:
            try:
                line_val = float(nums[-1])
            except ValueError:
                i += 1
                continue
            if current_player and current_stat:
                # Stat already seen → emit immediately
                _emit(current_player, current_stat, line_val, current_direction)
                current_stat = None
                current_direction = None
            else:
                # Stat not yet seen — look ahead one line for stat
                j = i + 1
                if j < len(lines):
                    ahead_stat = _normalize_stat(lines[j].strip())
                    ahead_dir  = None
                    for pat, dv in [
                        (r"\bhigher\b|\bmore\b|\bover\b", "higher"),
                        (r"\blower\b|\bless\b|\bunder\b", "lower"),
                    ]:
                        if re.search(pat, lines[j].strip().lower()):
                            ahead_dir = dv
                            break
                    if ahead_stat and current_player:
                        _emit(current_player, ahead_stat, line_val, ahead_dir or current_direction)
                        current_stat = None
                        current_direction = None
                        i = j + 1
                        continue
            i += 1
            continue

        # ══ CASE 5: Player name (no nums, no stat, no direction) ══
        if not nums and not stat and len(line) > 3 and direction is None:
            words = line.split()
            if all(
                w[0].isupper() or w[0].isdigit() or w in {"Jr.", "Sr.", "II", "III", "IV"}
                for w in words if w
            ) and not any(
                kw in line_lower for kw in ["higher", "lower", "more", "less", "over", "under"]
            ):
                current_player    = line
                current_stat      = None
                current_direction = None
                i += 1
                continue

        # ══ CASE 6: Fallback scan-ahead — only when direction is also absent ══
        # Line has no nums, no stat, no direction → maybe an unrecognised player name
        # with its props scattered across the next several lines.
        if not nums and not stat and direction is None:
            potential_player = line
            j = i + 1
            found_line_val  = None
            found_stat_fb   = None
            found_dir_fb    = None

            while j < min(i + 10, len(lines)):
                nxt       = lines[j].strip()
                nxt_lower = nxt.lower()

                # Stop if we hit what looks like another player name block separator
                if re.match(r"^[A-Z]{2,3}\s*[-–]\s*[A-Z]{1,4}$", nxt):
                    break

                # Stat first (before numeric check – handles stat-before-number order)
                if found_stat_fb is None:
                    s = _normalize_stat(nxt)
                    if s:
                        found_stat_fb = s
                        j += 1
                        continue

                # Numeric line value
                if found_line_val is None and re.match(r"^\d+\.?\d*$", nxt):
                    try:
                        found_line_val = float(nxt)
                    except ValueError:
                        pass
                    j += 1
                    continue

                # Direction
                if found_dir_fb is None:
                    for pat, dv in [
                        (r"\bhigher\b|\bmore\b|\bover\b", "higher"),
                        (r"\blower\b|\bless\b|\bunder\b", "lower"),
                    ]:
                        if re.search(pat, nxt_lower):
                            found_dir_fb = dv
                            break

                if found_line_val is not None and found_stat_fb and found_dir_fb:
                    break
                j += 1

            if found_line_val is not None and found_stat_fb:
                _emit(potential_player, found_stat_fb, found_line_val, found_dir_fb)
                current_player    = potential_player
                current_stat      = None
                current_direction = None
                i = j + 1
                continue

        i += 1

    return picks


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze_mlb_picks(picks: List[dict]) -> List[dict]:
    """Hydrate stats and compute hit probability for each pick."""
    results = []
    for p in picks:
        player = p["player"]
        stat   = p["stat"]
        line   = p["line"]
        direction = p["direction"]

        print(f"  Hydrating {player} / {stat}...", end=" ", flush=True)
        mu, sigma, n, source = hydrate_mlb_stat(player, stat)

        if n == 0:
            print(f"DEFAULT (no data)")
        else:
            print(f"μ={mu:.2f} σ={sigma:.2f} n={n} [{source}]")

        prob = prob_hit(line, direction, mu, sigma)

        grade = (
            "A" if prob >= 0.65
            else "B" if prob >= 0.58
            else "C" if prob >= 0.52
            else "D"
        )
        action = {"A": "STRONG", "B": "LEAN", "C": "CONSIDER", "D": "FADE"}[grade]

        results.append({
            **p,
            "mu":       round(mu, 3),
            "sigma":    round(sigma, 3),
            "n_games":  n,
            "source":   source,
            "probability": round(prob, 4),
            "grade":    grade,
            "action":   action,
        })

    results.sort(key=lambda x: x["probability"], reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Report helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_report_text(results: List[dict], label: str) -> str:
    lines = [
        "=" * 70,
        f"  MLB PROPS ANALYSIS — {label}",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 70,
        "",
        f"{'PLAYER':26} {'STAT':22} {'LINE':>6} {'DIR':6} {'PROB':>6} {'G':2} {'ACTION'}",
        "-" * 80,
    ]

    for r in results:
        stat_disp = MLB_STAT_DEFAULTS.get(r["stat"], (r["stat"],))[0]
        prob_str  = f"{r['probability']*100:.1f}%"
        lines.append(
            f"{r['player']:26} {stat_disp:22} {r['line']:>6.1f} "
            f"{r['direction']:6} {prob_str:>6} {r['grade']:2} {r['action']}"
        )

    strong = [r for r in results if r["action"] == "STRONG"]
    lean   = [r for r in results if r["action"] == "LEAN"]

    lines += [
        "-" * 80,
        f"\nSUMMARY: {len(strong)} STRONG | {len(lean)} LEAN | {len(results)} Total",
        "",
    ]

    if strong:
        lines.append("TOP PLAYS:")
        for s in strong[:6]:
            stat_disp = MLB_STAT_DEFAULTS.get(s["stat"], (s["stat"],))[0]
            lines.append(
                f"  ★ {s['player']} {stat_disp} {s['direction']} {s['line']} "
                f"({s['probability']*100:.1f}%) [n={s['n_games']}, src={s['source']}]"
            )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────────────────────

def _send_mlb_telegram(results: List[dict], label: str):
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            print("  [!] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in .env")
            return

        strong = [r for r in results if r["action"] in ("STRONG", "LEAN")][:10]
        if not strong:
            print("  [!] No STRONG/LEAN picks to send.")
            return

        lines_out = [
            f"⚾ *MLB PROPS — {label}*",
            f"_{datetime.now().strftime('%b %d %Y %H:%M')}_",
            "",
        ]
        for r in strong:
            stat_disp = MLB_STAT_DEFAULTS.get(r["stat"], (r["stat"],))[0]
            emoji = "🔥" if r["action"] == "STRONG" else "✅"
            lines_out.append(
                f"{emoji} *{r['player']}* — {stat_disp} {r['direction'].upper()} {r['line']} "
                f"({r['probability']*100:.0f}%)"
            )

        msg = "\n".join(lines_out)

        import urllib.request, urllib.parse
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text":    msg,
            "parse_mode": "Markdown",
        }).encode()
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            resp = json.loads(r.read())
            if resp.get("ok"):
                print(f"  [✓] Sent {len(strong)} picks to Telegram.")
            else:
                print(f"  [!] Telegram error: {resp}")
    except Exception as e:
        print(f"  [!] Telegram send failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Odds API Ingest
# ─────────────────────────────────────────────────────────────────────────────

def odds_api_ingest_mlb() -> List[dict]:
    """Fetch MLB props from The Odds API."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        api_key = (os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY") or "").strip()
        if not api_key:
            print("  [!] ODDS_API_KEY not set in .env")
            return []
    except ImportError:
        api_key = os.getenv("ODDS_API_KEY", "").strip()
        if not api_key:
            print("  [!] ODDS_API_KEY not set")
            return []

    import urllib.request, urllib.parse

    SPORT    = "baseball_mlb"
    MARKETS  = "batter_hits,batter_home_runs,batter_rbis,batter_runs_scored," \
               "batter_stolen_bases,batter_strikeouts,batter_total_bases," \
               "pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed," \
               "pitcher_earned_runs"

    url = (
        f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
        f"?apiKey={api_key}&regions=us&markets={MARKETS}&oddsFormat=american"
    )

    print(f"  Calling Odds API for MLB props...", end=" ", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        print(f"OK ({len(data)} events)")
    except Exception as e:
        print(f"FAILED — {e}")
        return []

    market_to_stat = {
        "batter_hits":             "hits",
        "batter_home_runs":        "home_runs",
        "batter_rbis":             "rbi",
        "batter_runs_scored":      "runs",
        "batter_stolen_bases":     "stolen_bases",
        "batter_strikeouts":       "strikeouts_batter",
        "batter_total_bases":      "total_bases",
        "pitcher_strikeouts":      "pitcher_strikeouts",
        "pitcher_outs":            "pitcher_outs",
        "pitcher_hits_allowed":    "hits_allowed",
        "pitcher_earned_runs":     "earned_runs_allowed",
    }

    picks = []
    seen  = set()

    for event in data:
        for bm in event.get("bookmakers", [])[:1]:      # first bookmaker only
            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                stat = market_to_stat.get(mkey)
                if not stat:
                    continue
                for outcome in market.get("outcomes", []):
                    player    = outcome.get("description", "")
                    direction = "higher" if outcome.get("name", "").lower() == "over" else "lower"
                    line      = outcome.get("point", 0)
                    key       = (player, stat, line, direction)
                    if key in seen:
                        continue
                    seen.add(key)
                    is_pitcher = MLB_STAT_DEFAULTS.get(stat, ("", 0, 0, False))[3]
                    picks.append({
                        "player":    player,
                        "team":      "MLB",
                        "position":  "P" if is_pitcher else "B",
                        "stat":      stat,
                        "line":      line,
                        "direction": direction,
                        "raw":       f"{player} {stat} {line} {direction} [OddsAPI]",
                    })

    print(f"  Parsed {len(picks)} props from Odds API.")
    return picks


# ─────────────────────────────────────────────────────────────────────────────
# Menu actions
# ─────────────────────────────────────────────────────────────────────────────

def clear_screen():
    print("\033[2J\033[H", end="", flush=True)


def _print_header():
    print("\n" + "=" * 70)
    print("  ⚾  MLB BASEBALL PROPS ANALYZER v1.0  (Statcast + Odds API)")
    print("=" * 70)


def _print_menu(settings: dict):
    mc = settings.get("min_confidence", 55)
    sg = "ON" if settings.get("soft_gates") else "OFF"
    print(f"""
  SoftGates={sg} | MinConf={mc}%

  ┌─────────────────────────────────────────────────────────────┐
  │  INGEST                                                     │
  │  [1]  Ingest MLB Slate     — Paste Underdog / DK props      │
  │  [A]  Odds API Ingest      — Auto-fetch MLB props           │
  │                                                             │
  │  ANALYSIS                                                   │
  │  [2]  Analyze MLB Slate    — Statcast + MLB API probs       │
  │  [V]  View Results         — Show latest analysis           │
  │                                                             │
  │  OUTPUT                                                     │
  │  [R]  Export Report        — Save text report               │
  │  [T]  Send to Telegram     — Broadcast top picks            │
  │                                                             │
  │  [9]  Settings             — Toggle options                 │
  │  [0]  Exit / Back                                           │
  └─────────────────────────────────────────────────────────────┘
""")


def _action_ingest_paste(settings: dict) -> List[dict]:
    clear_screen()
    _print_header()
    games = _get_mlb_games_today()
    if games:
        print("\n  Today's MLB Games:")
        for g in games[:12]:
            print(f"    {g['away']} @ {g['home']}")
    else:
        print("\n  (No live game data — check MLB API)")

    print("\n" + "-" * 70)
    print("  Paste Underdog MLB lines below. Type  END  when done:")
    print("-" * 70)

    raw_lines = []
    while True:
        try:
            ln = input()
            if ln.strip().upper() == "END":
                break
            raw_lines.append(ln)
        except (EOFError, KeyboardInterrupt):
            break

    picks = parse_mlb_lines("\n".join(raw_lines))

    if not picks:
        print("\n  [!] No valid picks parsed.")
        input("\nPress Enter to continue...")
        return []

    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"mlb_manual_{ts}"
    _save_slate(picks, label, settings)
    _display_picks(picks)
    return picks


def _action_odds_api(settings: dict) -> List[dict]:
    clear_screen()
    _print_header()
    print("\n  🛰️  MLB ODDS API INGEST\n")
    picks = odds_api_ingest_mlb()
    if not picks:
        input("\nPress Enter to continue...")
        return []
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"mlb_oddsapi_{ts}"
    _save_slate(picks, label, settings)
    _display_picks(picks)
    return picks


def _save_slate(picks: List[dict], label: str, settings: dict):
    fpath = OUTPUTS_DIR / f"mlb_slate_{label}.json"
    fpath.write_text(json.dumps({"label": label, "picks": picks}, indent=2))
    settings["last_slate"] = str(fpath)
    settings["last_label"] = label
    save_settings(settings)
    print(f"\n  [✓] Saved {len(picks)} picks → {fpath.name}")


def _display_picks(picks: List[dict]):
    print(f"\n  Parsed {len(picks)} picks:\n")
    for p in picks:
        stat_disp = MLB_STAT_DEFAULTS.get(p["stat"], (p["stat"],))[0]
        print(f"    {p['player']:26} {stat_disp:22} {p['line']:>6.1f}  {p['direction']}")
    input("\nPress Enter to continue...")


def _action_analyze(settings: dict) -> Optional[List[dict]]:
    clear_screen()
    _print_header()

    slate_path = settings.get("last_slate")
    if not slate_path or not Path(slate_path).exists():
        print("\n  [!] No slate loaded. Run [1] Ingest first.")
        input("\nPress Enter to continue...")
        return None

    data  = json.loads(Path(slate_path).read_text())
    picks = data.get("picks", [])
    label = data.get("label", "unknown")

    print(f"\n  Analyzing {len(picks)} picks from: {label}\n")
    results = analyze_mlb_picks(picks)

    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    r_path = OUTPUTS_DIR / f"mlb_analysis_{label}.json"
    r_path.write_text(json.dumps({"label": label, "results": results}, indent=2))
    settings["last_analysis"] = str(r_path)
    save_settings(settings)

    # Display
    print("\n" + "=" * 80)
    print(f"  {'PLAYER':26} {'STAT':22} {'LINE':>6} {'DIR':6} {'PROB':>6} {'G':2} {'ACTION'}")
    print("-" * 80)
    for r in results:
        stat_disp = MLB_STAT_DEFAULTS.get(r["stat"], (r["stat"],))[0]
        print(
            f"  {r['player']:26} {stat_disp:22} {r['line']:>6.1f} "
            f"{r['direction']:6} {r['probability']*100:>5.1f}% {r['grade']:2} {r['action']}"
        )
    print("-" * 80)

    strong = [r for r in results if r["action"] == "STRONG"]
    lean   = [r for r in results if r["action"] == "LEAN"]
    print(f"\n  SUMMARY: {len(strong)} STRONG | {len(lean)} LEAN | {len(results)} Total")

    if strong:
        print("\n  TOP PLAYS:")
        for s in strong[:6]:
            stat_disp = MLB_STAT_DEFAULTS.get(s["stat"], (s["stat"],))[0]
            print(
                f"    ★ {s['player']} {stat_disp} {s['direction']} {s['line']} "
                f"({s['probability']*100:.1f}%) [n={s['n_games']}, {s['source']}]"
            )

    input("\nPress Enter to continue...")
    return results


def _action_view(settings: dict):
    clear_screen()
    _print_header()
    files = sorted(OUTPUTS_DIR.glob("mlb_analysis_*.json"), reverse=True)
    if not files:
        print("\n  No analysis files found. Run [2] first.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  {len(files)} analysis file(s):\n")
    for i, f in enumerate(files[:8], 1):
        print(f"    [{i}] {f.name}")

    choice = input("\n  Select (Enter = latest): ").strip()
    try:
        idx      = int(choice) - 1 if choice else 0
        selected = files[idx]
    except Exception:
        selected = files[0]

    data    = json.loads(selected.read_text())
    results = data.get("results", [])
    label   = data.get("label", "unknown")

    print(f"\n  {label}  ({len(results)} picks)\n")
    for r in results:
        stat_disp = MLB_STAT_DEFAULTS.get(r["stat"], (r["stat"],))[0]
        print(
            f"  {r['player']:26} {stat_disp:22} {r['line']:>6.1f} "
            f"{r['direction']:6} {r['probability']*100:>5.1f}% {r['grade']}"
        )
    input("\nPress Enter to continue...")


def _action_export(settings: dict):
    clear_screen()
    _print_header()

    analysis_path = settings.get("last_analysis")
    if not analysis_path or not Path(analysis_path).exists():
        files = sorted(OUTPUTS_DIR.glob("mlb_analysis_*.json"), reverse=True)
        if not files:
            print("\n  [!] No analysis to export. Run [2] first.")
            input("\nPress Enter to continue...")
            return
        analysis_path = str(files[0])

    data    = json.loads(Path(analysis_path).read_text())
    results = data.get("results", [])
    label   = data.get("label", "unknown")

    report_text = _build_report_text(results, label)
    rpt_path    = OUTPUTS_DIR / f"mlb_report_{label}.txt"
    rpt_path.write_text(report_text, encoding="utf-8")

    print(report_text)
    print(f"\n  [✓] Saved report → {rpt_path}")
    input("\nPress Enter to continue...")


def _action_telegram(settings: dict):
    clear_screen()
    _print_header()

    analysis_path = settings.get("last_analysis")
    if not analysis_path or not Path(analysis_path).exists():
        files = sorted(OUTPUTS_DIR.glob("mlb_analysis_*.json"), reverse=True)
        if not files:
            print("\n  [!] No analysis to send. Run [2] Analyze first.")
            input("\nPress Enter to continue...")
            return
        analysis_path = str(files[0])

    data    = json.loads(Path(analysis_path).read_text())
    results = data.get("results", [])
    label   = data.get("label", "unknown")

    print(f"\n  Sending {label} to Telegram...")
    _send_mlb_telegram(results, label)
    input("\nPress Enter to continue...")


def _action_settings(settings: dict):
    while True:
        clear_screen()
        _print_header()
        print(f"""
  [1]  Soft Gates:      {'ON' if settings.get('soft_gates') else 'OFF'}
  [2]  Min Confidence: {settings.get('min_confidence', 55)}%
  [0]  Back
""")
        ch = input("  Toggle: ").strip()
        if ch == "0":
            break
        elif ch == "1":
            settings["soft_gates"] = not settings.get("soft_gates", True)
            save_settings(settings)
        elif ch == "2":
            val = input("  Min confidence (0-100): ").strip()
            try:
                settings["min_confidence"] = max(0, min(100, int(val)))
                save_settings(settings)
            except ValueError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    settings = load_settings()

    while True:
        clear_screen()
        _print_header()
        _print_menu(settings)

        choice = input("  Select option: ").strip().upper()

        if choice == "0":
            break
        elif choice == "1":
            _action_ingest_paste(settings)
        elif choice == "A":
            _action_odds_api(settings)
        elif choice == "2":
            _action_analyze(settings)
        elif choice == "V":
            _action_view(settings)
        elif choice == "R":
            _action_export(settings)
        elif choice == "T":
            _action_telegram(settings)
        elif choice == "9":
            _action_settings(settings)
        else:
            print("  [!] Unknown option. Try again.")
            import time; time.sleep(0.7)


if __name__ == "__main__":
    main()
