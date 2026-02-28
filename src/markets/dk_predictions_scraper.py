#!/usr/bin/env python3
"""src/markets/dk_predictions_scraper.py

Playwright-based scraper for DraftKings Predictions binary markets.

DraftKings Predictions pages show YES/NO binary outcomes with American odds:
  - Super Bowl MVP:  Sam Darnold YES +127 / NO -257
  - Golf Winner:     Hideki Matsuyama YES +285 / NO -317
  - Game Props:      Lakers to win YES -150 / NO +130

This module handles:
  1. Navigation to DK Predictions pages
  2. Vertical text extraction (reuses FUOOM's proven parser pattern)
  3. Parsing YES/NO odds pairs into BinaryMarket objects
  4. Writing raw artifacts + checksums per FUOOM SOP

Requires: Playwright, persistent Chrome profile for authenticated sessions.

Usage:
    from src.markets.dk_predictions_scraper import scrape_dk_predictions
    markets = scrape_dk_predictions(sport="NFL", category="mvp")
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except Exception:
    sync_playwright = None
    PlaywrightTimeout = Exception

# Reuse the binary markets engine for parsing and conversion
try:
    from src.markets.binary_markets import (
        BinaryMarket,
        american_to_implied,
        remove_vig_two_way,
        markets_to_json,
    )
except ImportError:
    # Allow standalone import path
    import sys
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from src.markets.binary_markets import (
        BinaryMarket,
        american_to_implied,
        remove_vig_two_way,
        markets_to_json,
    )


# ── DK Predictions URL Patterns ───────────────────────────────────

DK_PREDICTIONS_URLS = {
    # Sport → category → URL
    "NFL": {
        "default": "https://sportsbook.draftkings.com/leagues/football/nfl",
        "mvp": "https://sportsbook.draftkings.com/leagues/football/nfl",
        "game_props": "https://sportsbook.draftkings.com/leagues/football/nfl",
    },
    "NBA": {
        "default": "https://sportsbook.draftkings.com/leagues/basketball/nba",
        "game_props": "https://sportsbook.draftkings.com/leagues/basketball/nba",
    },
    "NHL": {
        "default": "https://sportsbook.draftkings.com/leagues/hockey/nhl",
    },
    "GOLF": {
        "default": "https://sportsbook.draftkings.com/leagues/golf",
    },
    "CBB": {
        "default": "https://sportsbook.draftkings.com/leagues/basketball/ncaa",
    },
}

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROME_PROFILE = PROJECT_ROOT / "chrome_profile"
RAW_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "dk_predictions"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


# ── Text Parsing ──────────────────────────────────────────────────


def _extract_prediction_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract YES/NO prediction blocks from page text.

    DK Predictions page text patterns:
        Team/Player Name
        YES +127
        NO -257

    Or spread/total format:
        Lakers -3.5
        YES -110
        NO -110

    Or winner market:
        Hideki Matsuyama
        YES +285
        NO -317
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    blocks: List[Dict[str, Any]] = []

    skip_words = [
        "sign in", "log in", "deposit", "withdraw", "rewards",
        "featured", "popular", "lobby", "my entries", "menu",
        "all sports", "live", "promotions", "same game parlay",
        "bet slip", "my bets", "help", "responsible", "terms",
    ]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip UI noise
        if any(sw in line.lower() for sw in skip_words):
            i += 1
            continue

        # Look for YES +odds pattern
        yes_match = re.match(
            r'^(?:YES|Win|Over|Home|Away)\s+([+-]?\d+)$',
            line, re.IGNORECASE
        )
        if yes_match:
            yes_odds = float(yes_match.group(1))
            entity = None

            # Look backwards for the entity name
            for j in range(i - 1, max(i - 5, -1), -1):
                candidate = lines[j].strip()
                if (len(candidate) > 2
                    and not re.match(r'^[+-]?\d+$', candidate)
                    and not re.match(r'^(YES|NO|Win|Lose|Over|Under|Home|Away)\b', candidate, re.IGNORECASE)
                    and candidate.lower() not in skip_words):
                    entity = candidate
                    break

            # Look forward for NO -odds
            no_odds = None
            if i + 1 < len(lines):
                no_match = re.match(
                    r'^(?:NO|Lose|Under)\s+([+-]?\d+)$',
                    lines[i + 1], re.IGNORECASE
                )
                if no_match:
                    no_odds = float(no_match.group(1))
                    i += 1  # consume NO line

            if entity:
                blocks.append({
                    "entity": entity,
                    "yes_odds": yes_odds,
                    "no_odds": no_odds,
                })

        i += 1

    return blocks


def parse_dk_predictions_page(
    text: str,
    *,
    sport: str = "NFL",
    category: str = "default",
) -> List[BinaryMarket]:
    """Parse DK Predictions page text into BinaryMarket objects."""

    blocks = _extract_prediction_blocks(text)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    markets: List[BinaryMarket] = []

    for block in blocks:
        entity = block["entity"]
        yes_odds = block["yes_odds"]
        no_odds = block.get("no_odds")

        yes_imp = american_to_implied(yes_odds)
        no_imp = american_to_implied(no_odds) if no_odds is not None else (1.0 - yes_imp)

        fair_yes, fair_no = remove_vig_two_way(yes_imp, no_imp)
        vig_total = yes_imp + no_imp
        vig_pct = vig_total - 1.0 if vig_total > 1.0 else 0.0

        safe_entity = re.sub(r'[^A-Za-z0-9]', '_', entity)[:40]
        mkt_id = f"dkpred_{sport}_{category}_{safe_entity}"

        # YES side
        markets.append(BinaryMarket(
            market_id=mkt_id + "_yes",
            sport=sport,
            market_type="prop_binary",
            entity=entity,
            side="yes",
            opponent_side="no",
            american_odds=yes_odds,
            implied_prob=round(yes_imp, 6),
            fair_prob=round(fair_yes, 6),
            vig_pct=round(vig_pct, 4),
            fetched_at=now_iso,
            source="DK_Predictions",
            dk_predictions_format=True,
        ))

        # NO side
        if no_odds is not None:
            markets.append(BinaryMarket(
                market_id=mkt_id + "_no",
                sport=sport,
                market_type="prop_binary",
                entity=entity,
                side="no",
                opponent_side="yes",
                american_odds=no_odds,
                implied_prob=round(no_imp, 6),
                fair_prob=round(fair_no, 6),
                vig_pct=round(vig_pct, 4),
                fetched_at=now_iso,
                source="DK_Predictions",
                dk_predictions_format=True,
            ))

    return markets


# ── Playwright Scraper ─────────────────────────────────────────────


def scrape_dk_predictions(
    *,
    sport: str = "NFL",
    category: str = "default",
    headless: bool = True,
    profile_dir: Optional[str] = None,
    url_override: Optional[str] = None,
) -> List[BinaryMarket]:
    """Scrape DraftKings Predictions page and return BinaryMarket objects.

    Args:
        sport: Sport tag (NFL, NBA, NHL, GOLF, CBB)
        category: Market category (default, mvp, game_props)
        headless: Run browser headless
        profile_dir: Chrome profile directory for authenticated sessions
        url_override: Custom URL to scrape (overrides sport/category lookup)

    Returns:
        List of BinaryMarket objects with implied and fair probabilities
    """
    if sync_playwright is None:
        raise RuntimeError("Playwright not available. Install with: pip install playwright && playwright install")

    # Resolve URL
    if url_override:
        url = url_override
    else:
        sport_urls = DK_PREDICTIONS_URLS.get(sport.upper(), {})
        url = sport_urls.get(category, sport_urls.get("default"))
        if not url:
            raise ValueError(f"No URL configured for {sport}/{category}")

    profile = Path(profile_dir) if profile_dir else CHROME_PROFILE
    profile.mkdir(parents=True, exist_ok=True)

    raw_dir = RAW_OUTPUT_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═' * 55}")
    print(f"  🎲 DK PREDICTIONS SCRAPER — {sport.upper()}")
    print(f"{'═' * 55}")
    print(f"  URL: {url}")
    print(f"  Category: {category}")

    body_text = ""
    markets: List[BinaryMarket] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=headless,
            viewport={"width": 1920, "height": 1080},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        page = context.new_page()

        try:
            # Navigate
            print("  → Navigating...")
            page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Wait for content to render
            print("  → Waiting for predictions to load...")
            time.sleep(8)

            # Scroll to load lazy content
            for scroll_i in range(8):
                page.mouse.wheel(0, 3000)
                time.sleep(0.5)

            # Extract body text
            body_text = page.inner_text("body")

            # Save raw artifact
            raw_path = raw_dir / f"dk_predictions_{sport}_{category}_{timestamp}.txt"
            raw_path.write_text(body_text[:500000], encoding="utf-8")

            # Checksum
            checksum = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
            (raw_path.with_suffix(".txt.sha256")).write_text(
                f"{checksum}  {raw_path.name}\n", encoding="utf-8"
            )

            # Screenshot
            try:
                ss_path = raw_dir / f"dk_predictions_{sport}_{category}_{timestamp}.png"
                page.screenshot(path=str(ss_path), full_page=True)
            except Exception:
                pass

            print(f"  → Raw artifact: {raw_path.name}")

            # Parse
            markets = parse_dk_predictions_page(body_text, sport=sport, category=category)
            print(f"  ✅ Parsed {len(markets)} binary market outcomes")

        except Exception as e:
            print(f"  ❌ Scrape failed: {e}")
            # Save debug artifacts
            try:
                dbg_path = raw_dir / f"debug_dk_predictions_{sport}_{timestamp}.txt"
                dbg_path.write_text(body_text[:500000] if body_text else f"Error: {e}", encoding="utf-8")
            except Exception:
                pass

        finally:
            context.close()

    # Save structured output
    if markets:
        out_path = OUTPUT_DIR / f"dk_predictions_{sport}_{category}_{timestamp}.json"
        markets_to_json(markets, out_path)
        print(f"  📁 Output: {out_path.name}")

    return markets


# ── Manual Paste Mode ──────────────────────────────────────────────


def parse_pasted_predictions(*, sport: str = "NFL") -> List[BinaryMarket]:
    """Interactive mode: paste DK Predictions text from clipboard.

    For when Playwright scraping is impractical (e.g., CAPTCHA, login wall).
    This mirrors the existing menu.py paste-based ingestion pattern.
    """
    print(f"\n{'═' * 55}")
    print(f"  📋 DK PREDICTIONS — Paste Mode ({sport})")
    print(f"{'═' * 55}")
    print("  Paste the DK Predictions page text below.")
    print("  Press Enter twice on an empty line when done.\n")

    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append("")
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break

    text = "\n".join(lines)
    if not text.strip():
        print("  ⚠ No text provided")
        return []

    markets = parse_dk_predictions_page(text, sport=sport)
    print(f"\n  ✅ Parsed {len(markets)} outcomes from pasted text")

    if markets:
        # Show preview
        yes_markets = [m for m in markets if m.side == "yes"]
        print(f"\n  {'Entity':<30} {'YES Odds':>9} {'Fair Prob':>10}")
        print(f"  {'─' * 50}")
        for m in yes_markets[:15]:
            print(f"  {m.entity[:29]:<30} {m.american_odds:>+9.0f} {m.fair_prob:>9.1%}")

    return markets


# ── CLI ────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="DraftKings Predictions Scraper")
    ap.add_argument("--sport", default="NFL")
    ap.add_argument("--category", default="default")
    ap.add_argument("--paste", action="store_true", help="Paste mode (no browser)")
    ap.add_argument("--url", default=None, help="Custom URL override")
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--visible", action="store_true", help="Show browser window")
    args = ap.parse_args()

    if args.paste:
        markets = parse_pasted_predictions(sport=args.sport.upper())
    else:
        markets = scrape_dk_predictions(
            sport=args.sport.upper(),
            category=args.category,
            headless=not args.visible,
            url_override=args.url,
        )

    if markets:
        print(f"\n  Total outcomes: {len(markets)}")
        yes_only = [m for m in markets if m.side == "yes"]
        print(f"  YES-side markets: {len(yes_only)}")
        print(f"  Avg vig: {sum(m.vig_pct for m in yes_only) / len(yes_only):.1%}" if yes_only else "")
