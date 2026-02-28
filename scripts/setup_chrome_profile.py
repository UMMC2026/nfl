#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""scripts/setup_chrome_profile.py

One-time Playwright persistent profile setup.

This opens a *persistent* Chromium context that stores cookies/session state
in `./chrome_profile`. You manually log in once to each platform.

Notes:
- This does not bypass any authentication; it just preserves your session.
- Close all normal Chrome windows first if you plan to use Chrome CDP elsewhere.
"""

from __future__ import annotations

import time
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except Exception as e:  # pragma: no cover
    sync_playwright = None
    _import_err = e


def _safe_goto(page, url: str, *, timeout_ms: int = 90000, retries: int = 3) -> None:
    """Navigate with a small amount of resilience.

    Some login flows keep redirecting in the background. If we re-use the same page
    immediately, Playwright can throw:
      "Navigation ... is interrupted by another navigation ..."
    """

    last_err: Exception | None = None
    for _ in range(max(1, retries)):
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e)
            if "interrupted by another navigation" in msg.lower():
                try:
                    # Let the page settle a bit, then stop any pending redirects.
                    page.wait_for_timeout(1500)
                    page.evaluate("window.stop()")
                except Exception:
                    pass
                continue
            raise
    if last_err is not None:
        raise last_err


def _open_login_tab(context, *, url: str, platform_name: str) -> None:
    page = context.new_page()
    page.bring_to_front()

    print(f"\n→ Opening {platform_name}...")
    _safe_goto(page, url)
    input(f"  Press Enter after logging in to {platform_name}...")

    # Prevent a still-running redirect loop from interfering with later steps.
    try:
        page.evaluate("window.stop()")
    except Exception:
        pass


def setup_persistent_profile() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    profile_dir = (repo_root / "chrome_profile").resolve()
    profile_dir.mkdir(exist_ok=True)

    if sync_playwright is None:
        raise RuntimeError(
            f"Playwright import failed: {_import_err}. "
            "Run with the repo venv: .venv\\Scripts\\python.exe scripts\\setup_chrome_profile.py"
        )

    print("=" * 60)
    print("FUOOM / UNDERDOG ANALYSIS — CHROME PROFILE SETUP")
    print("=" * 60)
    print("\nThis will open a Playwright-managed browser profile. Please:")
    print("  1) Log into DraftKings (Pick6 or Sportsbook)")
    print("  2) Log into PrizePicks")
    print("  3) Log into Underdog Fantasy")
    print("\nWhen prompted, press Enter after each login step.")
    print(f"\nProfile directory: {profile_dir}")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Open each platform in its own tab to avoid cross-navigation interruptions.
        _open_login_tab(context, url="https://pick6.draftkings.com", platform_name="DraftKings")
        _open_login_tab(context, url="https://app.prizepicks.com", platform_name="PrizePicks")
        _open_login_tab(context, url="https://underdogfantasy.com/pick-em", platform_name="Underdog")

        print("\n✅ Profile saved. Closing in 2 seconds...")
        time.sleep(2)
        context.close()

    print(f"\n✔ Profile saved to: {profile_dir}")
    print("You can now run headless scrapes using the persistent profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(setup_persistent_profile())
