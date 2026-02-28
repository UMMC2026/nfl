#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""scripts/inspect_prizepicks.py

Interactive PrizePicks DOM inspector.

Goal:
- Open PrizePicks using the repo's Playwright persistent profile
- Count elements for a set of likely selectors
- Print samples of text content
- Save a text report under data/debug/

This does NOT bypass auth. If you're logged out or gated, the report will show it.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from playwright.sync_api import sync_playwright
except Exception as e:  # pragma: no cover
    sync_playwright = None
    _import_err = e


REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = (REPO_ROOT / "chrome_profile").resolve()
DEBUG_DIR = (REPO_ROOT / "data" / "debug").resolve()


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _selector_scan(page, patterns: Dict[str, List[str]]) -> Tuple[Dict[str, int], List[str]]:
    found: Dict[str, int] = {}
    lines: List[str] = []

    for category, selectors in patterns.items():
        lines.append(f"\n{category}:")
        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                count = len(els)
                if count:
                    found[sel] = count
                    lines.append(f"  ✓ {sel:<55} → {count} elements")
                    # sample text
                    try:
                        sample = (els[0].inner_text() or "").strip().replace("\n", " ")
                        if sample:
                            lines.append(f"    Sample: {sample[:120]}{'…' if len(sample) > 120 else ''}")
                    except Exception:
                        pass
                else:
                    lines.append(f"  ✗ {sel:<55} → 0 elements")
            except Exception as e:
                lines.append(f"  ⚠ {sel:<55} → Error: {e}")

    return found, lines


def inspect_prizepicks() -> int:
    if sync_playwright is None:
        print(
            f"Playwright import failed: {_import_err}\n"
            "Run with the repo venv: .venv\\Scripts\\python.exe scripts\\inspect_prizepicks.py"
        )
        return 2

    PROFILE_DIR.mkdir(exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" PRIZEPICKS SELECTOR INSPECTOR")
    print("=" * 70)
    print("\nOpens PrizePicks in a visible browser and scans DOM selectors.")
    print(f"Profile: {PROFILE_DIR}")
    print(f"Output:  {DEBUG_DIR}")

    report_path = DEBUG_DIR / f"prizepicks_inspection_{_now_tag()}.txt"

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = context.new_page()

        print("\n→ Loading PrizePicks…")
        page.goto("https://app.prizepicks.com", wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)

        # Try to click NBA tab if visible.
        print("→ Attempting to navigate to NBA…")
        nba_selectors = [
            'button:has-text("NBA")',
            'div[role="tab"]:has-text("NBA")',
            'a:has-text("NBA")',
            '[data-sport="NBA"]',
        ]
        for sel in nba_selectors:
            try:
                el = page.query_selector(sel)
                if el:
                    el.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        # Let React render + lazy-load lists
        for _ in range(6):
            try:
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(700)
            except Exception:
                break

        patterns = {
            "Projection / prop containers": [
                '[data-test*="projection"]',
                '[data-testid*="projection"]',
                '[class*="projection"]',
                '[class*="Projection"]',
                '[class*="stat"]',
                '[class*="Stat"]',
                '[class*="card"]',
                '[class*="Card"]',
                'div[role="article"]',
            ],
            "Buttons (look for MORE/LESS)": [
                'button:has-text("More")',
                'button:has-text("Less")',
                'button:has-text("MORE")',
                'button:has-text("LESS")',
            ],
        }

        found, scan_lines = _selector_scan(page, patterns)

        # Bot / human verification detection (informational)
        human_gate_lines: List[str] = []
        try:
            body_lower = (page.inner_text("body") or "").lower()
        except Exception:
            body_lower = ""
        markers = [
            "confirm you're human",
            "press and hold",
            "not a bot",
            "reference id",
            "please try again",
        ]
        if any(m in body_lower for m in markers):
            human_gate_lines.append("\n⚠ Human verification gate detected (press-and-hold / not-a-bot).")
            human_gate_lines.append("   Complete the challenge manually in this browser, then re-run the inspector.")

        header = [
            "PRIZEPICKS SELECTOR INSPECTION RESULTS",
            "=" * 70,
            f"Timestamp: {datetime.now().isoformat()}",
            f"URL:       {page.url}",
            f"Title:     {page.title()}",
            "",
            "DOM SCAN RESULTS",
            "=" * 70,
        ]

        # Recommendations: top selectors by count.
        rec_lines = ["", "RECOMMENDATIONS", "=" * 70]
        if found:
            top = sorted(found.items(), key=lambda kv: kv[1], reverse=True)[:8]
            rec_lines.append("Most promising selectors (highest element counts):")
            for i, (sel, n) in enumerate(top, start=1):
                rec_lines.append(f"  {i}. {sel}  → {n} elements")
        else:
            rec_lines.append("No matching elements found.")
            rec_lines.append("Likely causes:")
            rec_lines.append("  - Logged out / gated / captcha")
            rec_lines.append("  - App shell rendered but props not loaded")
            rec_lines.append("  - Different DOM than expected")

        # Save screenshot + html for offline analysis.
        try:
            shot = DEBUG_DIR / f"prizepicks_inspection_{_now_tag()}.png"
            page.screenshot(path=str(shot), full_page=True)
        except Exception:
            shot = None

        try:
            html = DEBUG_DIR / f"prizepicks_inspection_{_now_tag()}.html"
            html.write_text(page.content(), encoding="utf-8")
        except Exception:
            html = None

        text = "\n".join(header + scan_lines + human_gate_lines + rec_lines)
        report_path.write_text(text, encoding="utf-8")

        print("\n" + "\n".join(header + scan_lines + human_gate_lines + rec_lines))
        print(f"\n✓ Report saved: {report_path}")
        if shot:
            print(f"✓ Screenshot:   {shot}")
        if html:
            print(f"✓ HTML dump:    {html}")

        print("\nBrowser will stay open for manual inspection.")
        input("Press Enter here to close…")

        context.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(inspect_prizepicks())
