#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""src/parsers/prizepicks_parser.py

PrizePicks DOM-based parser with debug artifacts.

Why:
- PrizePicks can render a mostly-empty <body> text shell while the real prop board
  lives deeper in React components.
- We therefore extract text from likely "projection" containers via CSS selectors,
  then parse it with a vertical-format heuristic.

Output schema (compatible with FUOOM scraper raw artifact writer):
- player (str)
- stat (str)
- line (float)
- direction ("higher"|"lower")  # PrizePicks supports both; we emit both
- raw (str)
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _clean_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").split("\n") if ln.strip()]


def _looks_like_player(line: str) -> bool:
    # Similar to the repo's smart parser: allow apostrophes/hyphens.
    if len(line) < 6:
        return False
    if any(ch.isdigit() for ch in line):
        return False
    return bool(re.match(r"^[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Za-z\-\']+)+$", line))


def _parse_vertical_triplet(lines: List[str]) -> Optional[Tuple[str, float, str]]:
    """Try to parse (player, line, stat) from a card-like list of lines."""

    player: Optional[str] = None
    stat: Optional[str] = None
    line_val: Optional[float] = None

    # Player is often the first human-looking name.
    for ln in lines[:8]:
        if _looks_like_player(ln):
            player = ln
            break

    # Find a numeric line.
    for ln in lines[:15]:
        m = re.match(r"^(\d+\.?\d*)$", ln)
        if m:
            try:
                line_val = float(m.group(1))
                break
            except Exception:
                continue

    # Stat tends to follow the line number; otherwise find known stat-ish tokens.
    if line_val is not None:
        try:
            idx = lines.index(str(line_val).rstrip("0").rstrip("."))
        except Exception:
            idx = -1

        if 0 <= idx < len(lines) - 1:
            candidate = lines[idx + 1]
            # Accept non-numeric short-ish strings.
            if candidate and not re.search(r"\d", candidate) and len(candidate) <= 40:
                stat = candidate

    if stat is None:
        for ln in lines:
            if ln.lower() in {
                "points",
                "rebounds",
                "assists",
                "3-pointers made",
                "3pm",
                "fantasy points",
                "pts + rebs + asts",
                "rebounds + assists",
                "points + rebounds",
                "points + assists",
                "steals",
                "blocks",
                "shots on goal",
                "sog",
                "saves",
                "aces",
                "double faults",
            }:
                stat = ln
                break

    if not (player and stat and line_val is not None):
        return None

    stat_norm = stat.strip().lower().replace(" + ", "+").replace("-", "")
    return player.strip(), float(line_val), stat_norm


@dataclass
class PrizePicksParseResult:
    props: List[dict]
    meta: Dict[str, object]


class PrizePicksParser:
    def __init__(self, debug_dir: str = "./data/debug", debug: bool = True):
        self.debug = debug
        self.debug_dir = Path(debug_dir).resolve()
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        # Broad selectors; inspector will help refine.
        self.card_selectors = [
            '[data-test*="projection"]',
            '[data-testid*="projection"]',
            'div[class*="projection"]',
            'div[class*="Projection"]',
            'div[class*="stat"]',
            'div[class*="Stat"]',
            'div[class*="card"]',
            'div[class*="Card"]',
        ]

    def parse(self, page, sport: str = "NBA") -> PrizePicksParseResult:
        """Extract props from PrizePicks.

        We emit BOTH directions (higher/lower) because PrizePicks is inherently
        More/Less and the UI doesn't always include direction text.
        """

        # Give React time to render.
        try:
            page.wait_for_load_state("domcontentloaded", timeout=45000)
        except Exception:
            pass

        page.wait_for_timeout(1500)

        # If the site shows a human-verification gate, we cannot automate it.
        # We pause and let the user complete it manually in the headed browser.
        gate_text = ""
        try:
            gate_text = (page.inner_text("body") or "").lower()
        except Exception:
            gate_text = ""

        gate_markers = [
            "confirm you're human",
            "press and hold",
            "not a bot",
            "please try again",
            "reference id",
        ]
        gated = any(m in gate_text for m in gate_markers)
        if gated and self.debug and sys.stdin and sys.stdin.isatty():
            print("  [PrizePicks] Human verification detected in page UI.")
            print("  [PrizePicks] Please complete the on-page 'press and hold' check in the browser.")
            input("  Press Enter here AFTER verification is complete to continue parsing…")

            # After completion, wait for the gate to disappear / content to render.
            deadline = time.time() + 60
            while time.time() < deadline:
                try:
                    body_now = (page.inner_text("body") or "").lower()
                except Exception:
                    body_now = ""

                if not any(m in body_now for m in gate_markers):
                    # Give React a beat to paint the prop board.
                    try:
                        page.wait_for_timeout(1500)
                    except Exception:
                        time.sleep(1.5)
                    break

                try:
                    page.wait_for_timeout(1200)
                except Exception:
                    time.sleep(1.2)

        # Light scrolling to trigger lazy content.
        for _ in range(6):
            try:
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(700)
            except Exception:
                break

        extracted_blocks: List[str] = []
        selector_hits: Dict[str, int] = {}

        for sel in self.card_selectors:
            try:
                els = page.query_selector_all(sel)
            except Exception:
                continue

            if not els:
                continue

            selector_hits[sel] = len(els)

            # Pull text from a subset to limit time/memory.
            for el in els[:250]:
                try:
                    t = (el.inner_text() or "").strip()
                    if t and len(t) >= 8:
                        extracted_blocks.append(t)
                except Exception:
                    continue

            # If we already have lots of blocks, stop early.
            if len(extracted_blocks) >= 200:
                break

        # Parse card texts into props.
        props: List[dict] = []
        seen: set[tuple[str, str, float, str]] = set()

        for block in extracted_blocks:
            lines = _clean_lines(block)
            triplet = _parse_vertical_triplet(lines)
            if not triplet:
                continue
            player, line_val, stat = triplet

            for direction in ("higher", "lower"):
                key = (player, stat, float(line_val), direction)
                if key in seen:
                    continue
                seen.add(key)
                props.append(
                    {
                        "player": player,
                        "stat": stat,
                        "line": float(line_val),
                        "direction": direction,
                        "raw": f"{player} {stat} {line_val} {direction}",
                    }
                )

        meta: Dict[str, object] = {
            "url": getattr(page, "url", None),
            "sport": sport,
            "selector_hits": selector_hits,
            "blocks_extracted": len(extracted_blocks),
            "props_emitted": len(props),
            "human_verification_detected": bool(gated),
        }

        if self.debug and (len(props) == 0):
            self._write_debug(page, sport=sport, selector_hits=selector_hits)

        return PrizePicksParseResult(props=props, meta=meta)

    def _write_debug(self, page, *, sport: str, selector_hits: Dict[str, int]) -> None:
        ts = _now_tag()
        try:
            png = self.debug_dir / f"prizepicks_debug_{sport}_{ts}.png"
            page.screenshot(path=str(png), full_page=True)
        except Exception:
            pass

        try:
            html = self.debug_dir / f"prizepicks_debug_{sport}_{ts}.html"
            html.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass

        try:
            txt = self.debug_dir / f"prizepicks_debug_{sport}_{ts}.meta.txt"
            lines = [
                f"URL: {getattr(page, 'url', '')}",
                f"Title: {page.title() if hasattr(page, 'title') else ''}",
                "",
                "Selector hits:",
            ]
            for k, v in sorted(selector_hits.items(), key=lambda kv: kv[1], reverse=True):
                lines.append(f"  {k}: {v}")
            lines.append("")
            lines.append("Body text (first 4000 chars):")
            try:
                body = (page.inner_text("body") or "")
                body = body.replace("\r\n", "\n")
                lines.append(body[:4000])
            except Exception as e:
                lines.append(f"<failed to read body text: {e}>")
            txt.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    # Standalone smoke test (interactive).
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"Playwright import failed: {e}")
        return 2

    repo_root = Path(__file__).resolve().parents[2]
    profile_dir = (repo_root / "chrome_profile").resolve()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()
        page.goto("https://app.prizepicks.com", wait_until="domcontentloaded", timeout=90000)

        parser = PrizePicksParser(debug=True)
        res = parser.parse(page, sport="NBA")

        print("=" * 70)
        print("PRIZEPICKS PARSER RESULT")
        print("=" * 70)
        print(f"Props: {len(res.props)}")
        print(f"Meta:  {res.meta}")
        if res.props:
            for p_ in res.props[:10]:
                print(f"  {p_['player']} | {p_['stat']} | {p_['line']} | {p_['direction']}")

        input("\nPress Enter to close…")
        context.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
