#!/usr/bin/env python3
"""
Fetch NFL data files from nflverse/nflverse-data GitHub *release tags* and place them locally.

Why this approach:
- nflverse publishes pbp + player/team/roster data via GitHub Releases (nflverse-data).
- This script uses the GitHub API so it can discover the exact asset filenames automatically.

Examples:
  python tools/fetch_nflverse_nfl_stats.py --dest data/nfl --seasons 2018-2025 --tags pbp player_stats players rosters schedules weekly_rosters
  python tools/fetch_nflverse_nfl_stats.py --dest data/nfl --seasons 2024,2025 --tags pbp --file-type parquet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

GITHUB_API = "https://api.github.com"
REPO = "nflverse/nflverse-data"

DEFAULT_TAGS = ["pbp", "player_stats", "players", "rosters", "schedules", "weekly_rosters"]
DEFAULT_FILE_TYPE = "parquet"  # other common types: "csv", "csv.gz", "rds"

@dataclass
class Asset:
    name: str
    size: int
    browser_download_url: str
    updated_at: str

def _http_get_json(url: str, headers: Dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _stream_download(url: str, out_path: Path, headers: Dict[str, str]) -> Tuple[int, str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=headers)
    sha256 = hashlib.sha256()
    bytes_written = 0
    with urllib.request.urlopen(req) as resp, open(out_path, "wb") as f:
        total = resp.headers.get("Content-Length")
        total_i = int(total) if total and total.isdigit() else None
        chunk_size = 1024 * 1024  # 1 MB
        last_print = 0.0
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            sha256.update(chunk)
            bytes_written += len(chunk)
            now = time.time()
            if now - last_print > 0.5:
                if total_i:
                    pct = (bytes_written / total_i) * 100
                    sys.stdout.write(f"\r  -> {out_path.name}: {pct:6.2f}% ({bytes_written/1e6:,.1f} MB / {total_i/1e6:,.1f} MB)")
                else:
                    sys.stdout.write(f"\r  -> {out_path.name}: {bytes_written/1e6:,.1f} MB")
                sys.stdout.flush()
                last_print = now
    sys.stdout.write("\n")
    return bytes_written, sha256.hexdigest()

def _parse_seasons(seasons_raw: str) -> List[int]:
    seasons_raw = seasons_raw.strip()
    if re.fullmatch(r"\d{4}-\d{4}", seasons_raw):
        a, b = seasons_raw.split("-")
        a_i, b_i = int(a), int(b)
        if a_i > b_i:
            a_i, b_i = b_i, a_i
        return list(range(a_i, b_i + 1))
    if "," in seasons_raw:
        return sorted({int(x.strip()) for x in seasons_raw.split(",") if x.strip()})
    return [int(seasons_raw)]

def _asset_matches(asset_name: str, tag: str, seasons: List[int], file_type: str) -> bool:
    if file_type == "parquet":
        if not asset_name.endswith(".parquet"):
            return False
    elif file_type == "csv":
        if not asset_name.endswith(".csv"):
            return False
    elif file_type == "csv.gz":
        if not asset_name.endswith(".csv.gz"):
            return False
    else:
        if not asset_name.endswith(f".{file_type}"):
            return False
    lower = asset_name.lower()
    if tag == "pbp":
        for y in seasons:
            if (f"play_by_play_{y}" in lower) or (re.search(rf"\bpbp\b.*{y}", lower) is not None) or (f"_{y}_" in lower and "play" in lower):
                return True
        return False
    if tag in ("player_stats", "stats_player"):
        for y in seasons:
            if str(y) in lower and ("player" in lower or "stats" in lower):
                return True
        return False
    return True

def _fetch_release_assets(tag: str, headers: Dict[str, str]) -> List[Asset]:
    url = f"{GITHUB_API}/repos/{REPO}/releases/tags/{tag}"
    data = _http_get_json(url, headers=headers)
    assets = []
    for a in data.get("assets", []):
        assets.append(
            Asset(
                name=a["name"],
                size=a.get("size", 0),
                browser_download_url=a["browser_download_url"],
                updated_at=a.get("updated_at", ""),
            )
        )
    return assets

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data/nflverse", help="Destination folder (default: data/nflverse)")
    ap.add_argument("--seasons", default="2018-2025", help="Seasons as 'YYYY-YYYY' or 'YYYY,YYYY' or 'YYYY'")
    ap.add_argument("--tags", nargs="+", default=DEFAULT_TAGS, help=f"Release tags (default: {' '.join(DEFAULT_TAGS)})")
    ap.add_argument("--file-type", default=DEFAULT_FILE_TYPE, help="parquet | csv | csv.gz | etc (default: parquet)")
    ap.add_argument("--token", default=os.getenv("GITHUB_TOKEN", ""), help="Optional GitHub token to avoid rate limits")
    ap.add_argument("--dry-run", action="store_true", help="List what would be downloaded, but do not download")
    args = ap.parse_args()

    dest = Path(args.dest).resolve()
    seasons = _parse_seasons(args.seasons)
    tags = args.tags
    file_type = args.file_type

    headers = {
        "User-Agent": "ufa-fetch-nflverse/1.0",
        "Accept": "application/vnd.github+json",
    }
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    manifest = {
        "repo": REPO,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dest": str(dest),
        "seasons": seasons,
        "tags": tags,
        "file_type": file_type,
        "downloads": [],
        "errors": [],
    }

    print(f"DEST: {dest}")
    print(f"SEASONS: {seasons}")
    print(f"TAGS: {tags}")
    print(f"FILE TYPE: {file_type}")
    print()

    for tag in tags:
        print(f"=== TAG: {tag} ===")
        try:
            assets = _fetch_release_assets(tag, headers=headers)
        except Exception as e:
            err = f"Failed to fetch tag '{tag}' (GitHub API). Error: {e}"
            print("!!", err)
            manifest["errors"].append(err)
            continue

        if not assets:
            msg = f"No assets found for tag '{tag}'. (Tag may be wrong or empty.)"
            print("!!", msg)
            manifest["errors"].append(msg)
            continue

        chosen = []
        for a in assets:
            if _asset_matches(a.name, tag, seasons, file_type):
                chosen.append(a)

        if not chosen:
            msg = f"No matching assets for tag '{tag}' with seasons={seasons} and file_type={file_type}."
            print("!!", msg)
            print("   Tip: try --file-type csv.gz or broaden seasons/tags.")
            manifest["errors"].append(msg)
            continue

        tag_dir = dest / tag
        tag_dir.mkdir(parents=True, exist_ok=True)

        print(f"Matched {len(chosen)} assets.")
        for a in chosen:
            out_path = tag_dir / a.name
            rec = {
                "tag": tag,
                "name": a.name,
                "size": a.size,
                "updated_at": a.updated_at,
                "url": a.browser_download_url,
                "path": str(out_path),
                "sha256": None,
                "bytes_written": None,
            }

            if args.dry_run:
                print(f"  [DRY] {a.name} -> {out_path}")
                manifest["downloads"].append(rec)
                continue

            if out_path.exists() and out_path.stat().st_size == a.size and a.size > 0:
                print(f"  Skipping (already exists, same size): {out_path.name}")
                rec["bytes_written"] = 0
                rec["sha256"] = "SKIPPED_EXISTING_SAME_SIZE"
                manifest["downloads"].append(rec)
                continue

            print(f"  Downloading: {a.name} ({a.size/1e6:,.1f} MB)")
            try:
                bytes_written, sha = _stream_download(a.browser_download_url, out_path, headers=headers)
                rec["bytes_written"] = bytes_written
                rec["sha256"] = sha
                manifest["downloads"].append(rec)
            except Exception as e:
                err = f"Failed downloading {a.name} for tag '{tag}': {e}"
                print("!!", err)
                manifest["errors"].append(err)

        print()

    manifest_path = dest / "nflverse_manifest.json"
    dest.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written: {manifest_path}")

    if manifest["errors"]:
        print("\nCompleted with errors. See manifest for details.")
        return 2

    print("\nCompleted successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
