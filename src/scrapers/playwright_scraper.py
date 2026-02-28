#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""src/scrapers/playwright_scraper.py

FUOOM Scraper Pipeline v2.1 (Truth-Enforced)

This module provides:
- Persistent profile scraping for DraftKings / PrizePicks / Underdog
- Immutable raw artifacts + SHA256 checksums
- Fail-fast behavior when a platform returns zero parsed props (auth/render issues)

Important:
- This is *prop line ingestion*, not pick recommendations.
- Parsing uses the repo's proven vertical-text parser to reduce DOM brittleness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except Exception as e:  # pragma: no cover
    sync_playwright = None
    PlaywrightTimeout = Exception
    _import_err = e

# Reuse the working extraction logic already in this repo.
from ingestion.prop_ingestion_pipeline import smart_extract_props
from src.parsers.prizepicks_parser import PrizePicksParser
from src.sources.odds_api import OddsApiError, oddsapi_fetch_player_props, oddsapi_sport_key_for_tag


def _looks_like_props_text(text: str) -> bool:
    """Heuristic to decide if the page has rendered a prop board yet."""
    if not text:
        return False
    t = text.lower()
    # Direction controls are a strong indicator across DK/UD/PP.
    if not any(w in t for w in ("higher", "lower", "more", "less", "over", "under")):
        return False
    # Lines are numeric and frequent once boards render.
    import re

    if re.search(r"\b\d+(?:\.\d+)?\b", t) is None:
        return False
    return True


def _poll_body_text(page, *, timeout_ms: int = 25000, poll_ms: int = 1200) -> str:
    """Poll body text until it looks like rendered props or time runs out."""
    deadline = time.time() + (timeout_ms / 1000)
    last = ""
    while time.time() < deadline:
        try:
            last = page.inner_text("body")
        except Exception:
            last = ""
        if _looks_like_props_text(last):
            return last
        try:
            page.mouse.wheel(0, 2500)
        except Exception:
            pass
        try:
            page.wait_for_timeout(poll_ms)
        except Exception:
            time.sleep(poll_ms / 1000)
    return last


def _write_debug_artifacts(output_dir: Path, *, platform: str, sport: str, page, body_text: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dbg_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Always try to save text even if screenshot fails.
    try:
        dbg_txt = output_dir / f"debug_{platform}_{sport}_{dbg_ts}.body.txt"
        dbg_txt.write_text((body_text or "")[:500000], encoding="utf-8")
    except Exception:
        pass

    try:
        dbg_png = output_dir / f"debug_{platform}_{sport}_{dbg_ts}.png"
        page.screenshot(path=str(dbg_png), full_page=True)
    except Exception:
        pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_sha256_sidecar(payload_text: str, artifact_path: Path) -> Path:
    checksum = _sha256_text(payload_text)
    sidecar = artifact_path.with_suffix(artifact_path.suffix + ".sha256")
    sidecar.write_text(f"{checksum}  {artifact_path.name}\n", encoding="utf-8")
    return sidecar


def _normalize_player_name(name: str) -> str:
    # Basic unicode normalization (e.g., Jokić → Jokic) without external deps.
    n = unicodedata.normalize("NFKD", name)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return " ".join(n.split()).strip()


@dataclass
class PlatformConfig:
    name: str
    url: str
    required: bool = False


class FUOOMScraper:
    def __init__(
        self,
        profile_dir: str = "./chrome_profile",
        output_dir: str = "./data/raw/scraped",
        headless: bool = True,
        fail_fast: bool = True,
        platforms: Optional[Dict[str, PlatformConfig]] = None,
    ):
        self.profile_dir = Path(profile_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.fail_fast = fail_fast

        default_platforms: Dict[str, PlatformConfig] = {
            # NOTE: DK sportsbook DOM is more brittle; Pick6 is more stable for this repo.
            "draftkings": PlatformConfig("draftkings", "https://pick6.draftkings.com", required=True),
            # PrizePicks frequently presents a human-verification gate. Treat as optional so the
            # end-to-end pipeline can still run from other sources.
            "prizepicks": PlatformConfig("prizepicks", "https://app.prizepicks.com", required=False),
            "underdog": PlatformConfig("underdog", "https://underdogfantasy.com/pick-em", required=False),
            # No-scrape alternative (The Odds API). Optional; requires ODDS_API_KEY.
            "oddsapi": PlatformConfig("oddsapi", "https://api.the-odds-api.com", required=False),
        }

        self.platforms = platforms or default_platforms

    def scrape_all_platforms(self, sport: str = "NBA") -> Dict[str, Path]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results: Dict[str, Path] = {}

        api_platforms = {k: v for k, v in self.platforms.items() if k == "oddsapi"}
        browser_platforms = {k: v for k, v in self.platforms.items() if k != "oddsapi"}

        any_success = False

        # --- No-scrape source: The Odds API (optional) ---
        for platform_name, cfg in api_platforms.items():
            print(f"\n→ Ingesting {platform_name.upper()} (API)…")
            try:
                artifact_path = self._scrape_oddsapi(sport=sport, timestamp=timestamp, source_url=cfg.url)
                results[platform_name] = artifact_path
                any_success = True
                print(f"  ✔ Saved API props → {artifact_path.name}")
            except Exception as e:
                self._write_debug_artifacts_api(platform=platform_name, sport=sport, timestamp=timestamp, error=str(e))
                if self.fail_fast and cfg.required:
                    raise
                print(f"  ⚠ {platform_name} ingest error (skipped): {e}")

        # --- Browser sources (Playwright) ---
        if browser_platforms:
            if sync_playwright is None:
                raise RuntimeError(
                    f"Playwright import failed: {_import_err}. "
                    "Run using the repo venv (.venv), or use the Odds API ingest option."
                )

            self.profile_dir.mkdir(exist_ok=True)

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    viewport={"width": 1920, "height": 1080},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )

                for platform_name, cfg in browser_platforms.items():
                    print(f"\n→ Scraping {platform_name.upper()}…")

                    # Use a fresh tab per platform to prevent cross-site redirect loops
                    # (especially after logins) from interrupting later navigations.
                    page = context.new_page()
                    try:
                        page.bring_to_front()
                    except Exception:
                        pass

                    body_text = ""
                    props: List[dict] = []

                    try:
                        # Navigate with retry logic
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                page.goto(cfg.url, timeout=90000, wait_until="domcontentloaded")
                                # Some sites keep XHRs open; don't hard-require networkidle.
                                try:
                                    page.wait_for_load_state("domcontentloaded", timeout=45000)
                                except Exception:
                                    pass
                                break
                            except PlaywrightTimeout:
                                if attempt == max_retries - 1:
                                    raise
                                print(f"  Retry {attempt + 1}/{max_retries}…")
                                time.sleep(2)

                        # Load more content (lazy lists)
                        for _ in range(6):
                            try:
                                page.mouse.wheel(0, 3500)
                                page.wait_for_timeout(400)
                            except Exception:
                                break

                        # Poll for rendered text (PrizePicks is especially dynamic).
                        body_text = _poll_body_text(page, timeout_ms=30000)
                        if not body_text:
                            try:
                                body_text = page.inner_text("body")
                            except Exception:
                                body_text = ""

                        # Platform-specific parsing
                        if platform_name == "prizepicks":
                            # PrizePicks often renders a minimal body shell; use DOM extraction.
                            pp = PrizePicksParser(debug_dir="./data/debug", debug=True)
                            props = pp.parse(page, sport=sport).props
                        else:
                            # Always try parsing first; some sites show "Log in" UI text even when authenticated.
                            props = smart_extract_props(body_text, platform_name)

                        # Authentication / render heuristics
                        if len(props) == 0:
                            lowered = (body_text or "").lower()
                            auth_markers = ["log in", "sign in", "create account", "verification", "captcha"]
                            if any(m in lowered for m in auth_markers):
                                msg = (
                                    f"Authentication likely required for {platform_name}. "
                                    "Run scripts/setup_chrome_profile.py"
                                )
                                _write_debug_artifacts(
                                    self.output_dir,
                                    platform=platform_name,
                                    sport=sport,
                                    page=page,
                                    body_text=body_text,
                                )
                                if self.fail_fast and cfg.required:
                                    raise RuntimeError(msg)
                                print(f"  ⚠ {msg}")

                        # Normalize player names (for downstream cross-platform reconciliation)
                        for prop in props:
                            if prop.get("player"):
                                prop["player"] = _normalize_player_name(str(prop["player"]))

                        if len(props) == 0:
                            _write_debug_artifacts(
                                self.output_dir,
                                platform=platform_name,
                                sport=sport,
                                page=page,
                                body_text=body_text,
                            )

                            msg = (
                                f"{platform_name} returned 0 parsed props. Likely DOM/render/auth issue. "
                                f"Debug artifacts saved under {self.output_dir}"
                            )

                            if self.fail_fast and cfg.required:
                                raise RuntimeError(msg)
                            print(f"  ⚠ {msg}")
                            continue

                        artifact_path = self._save_props(
                            props=props,
                            platform=platform_name,
                            sport=sport,
                            timestamp=timestamp,
                            source_url=cfg.url,
                        )

                        results[platform_name] = artifact_path
                        any_success = True
                        print(f"  ✔ Saved {len(props)} props → {artifact_path.name}")

                    except Exception as e:
                        # Best-effort debug capture
                        try:
                            if not body_text:
                                body_text = page.inner_text("body")
                        except Exception:
                            pass
                        _write_debug_artifacts(
                            self.output_dir,
                            platform=platform_name,
                            sport=sport,
                            page=page,
                            body_text=body_text,
                        )

                        if self.fail_fast and cfg.required:
                            raise
                        print(f"  ⚠ {platform_name} scrape error (skipped): {e}")

                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass

                context.close()

        if self.fail_fast and not any_success:
            raise RuntimeError("All platforms failed; no ingestion artifacts were produced.")

        return results

    def _write_debug_artifacts_api(self, *, platform: str, sport: str, timestamp: str, error: str) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        dbg_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            path = self.output_dir / f"debug_{platform}_{sport}_{dbg_ts}.error.txt"
            path.write_text(f"timestamp={timestamp}\nerror={error}\n", encoding="utf-8")
        except Exception:
            pass

    def _save_raw_payload(self, *, payload: dict, platform: str, sport: str, timestamp: str) -> Path:
        filename = f"raw_payload_{platform}_{sport}_{timestamp}.json"
        filepath = self.output_dir / filename
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        filepath.write_text(text, encoding="utf-8")
        _write_sha256_sidecar(text, filepath)
        return filepath

    def _scrape_oddsapi(self, *, sport: str, timestamp: str, source_url: str) -> Path:
        sport_key = oddsapi_sport_key_for_tag(sport)
        if not sport_key:
            raise OddsApiError(f"No Odds API sport_key mapping for sport tag: {sport}")

        regions = os.getenv("ODDS_API_REGIONS") or "us_dfs"
        markets = [m.strip() for m in (os.getenv("ODDS_API_MARKETS") or "player_points").split(",") if m.strip()]
        bookmakers_env = os.getenv("ODDS_API_BOOKMAKERS")
        bookmakers = None
        if bookmakers_env is not None:
            bookmakers = [b.strip() for b in bookmakers_env.split(",") if b.strip()]

        max_events = os.getenv("ODDS_API_MAX_EVENTS")
        max_events_i = int(max_events) if (max_events and max_events.strip()) else None

        props, meta = oddsapi_fetch_player_props(
            sport=sport,
            sport_key=sport_key,
            regions=regions,
            markets=markets,
            bookmakers=bookmakers,
            max_events=max_events_i,
        )

        # Normalize player names for downstream reconciliation.
        for prop in props:
            if prop.get("player"):
                prop["player"] = _normalize_player_name(str(prop["player"]))

        save_raw = (os.getenv("ODDS_API_SAVE_RAW") or "1").strip() not in {"0", "false", "no"}
        raw_path = None
        if save_raw:
            raw_path = self._save_raw_payload(payload=meta, platform="oddsapi", sport=sport, timestamp=timestamp)

        artifact_path = self._save_props(
            props=props,
            platform="oddsapi",
            sport=sport,
            timestamp=timestamp,
            source_url=source_url,
            metadata_extra={
                "regions": regions,
                "markets": ",".join(markets),
                "bookmakers": ",".join(bookmakers) if bookmakers else None,
                "raw_payload_artifact": raw_path.name if raw_path else None,
                "quota": (meta.get("quota") if isinstance(meta, dict) else None),
            },
        )

        if len(props) == 0:
            raise RuntimeError("Odds API returned 0 parsed props. Check ODDS_API_* settings and quotas.")

        return artifact_path

    def _save_props(
        self,
        props: List[dict],
        platform: str,
        sport: str,
        timestamp: str,
        source_url: str,
        metadata_extra: Optional[dict] = None,
    ) -> Path:
        filename = f"raw_props_{platform}_{sport}_{timestamp}.json"
        filepath = self.output_dir / filename

        output = {
            "metadata": {
                "platform": platform,
                "sport": sport,
                "scraped_at": timestamp,
                "scraped_at_utc": _utc_now_iso(),
                "scraper_version": "2.1.0",
                "sop_compliance": "v2.1",
                "prop_count": len(props),
                "source_url": source_url,
            },
            "props": [],
        }

        if metadata_extra:
            # Merge non-null keys only.
            for k, v in metadata_extra.items():
                if v is not None:
                    output["metadata"][k] = v

        for p in props:
            # Ensure a consistent minimal schema
            output["props"].append(
                {
                    "platform": platform,
                    "sport": sport,
                    "player": p.get("player"),
                    "stat": p.get("stat"),
                    "line": p.get("line"),
                    "direction": p.get("direction"),
                    "scraped_at": output["metadata"]["scraped_at_utc"],
                    "raw": p.get("raw"),
                }
            )

        payload = json.dumps(output, indent=2, ensure_ascii=False)
        filepath.write_text(payload, encoding="utf-8")
        _write_sha256_sidecar(payload, filepath)
        return filepath


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="FUOOM Multi-Platform Scraper (Playwright)")
    parser.add_argument("--sport", default="NBA", help="Sport tag to stamp into artifacts (default: NBA)")
    parser.add_argument("--profile", default="./chrome_profile", help="Persistent profile directory")
    parser.add_argument("--output", default="./data/raw/scraped", help="Output directory for raw artifacts")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser")
    parser.add_argument("--no-fail-fast", action="store_true", help="Do not raise on anomalies")

    args = parser.parse_args(argv)

    scraper = FUOOMScraper(
        profile_dir=args.profile,
        output_dir=args.output,
        headless=not args.headed,
        fail_fast=not args.no_fail_fast,
    )

    results = scraper.scrape_all_platforms(sport=args.sport)

    print("\n" + "=" * 60)
    print("SCRAPE COMPLETE")
    print("=" * 60)
    for platform, path in results.items():
        print(f"  {platform}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
