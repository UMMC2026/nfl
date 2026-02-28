"""
Fetch Jeff Sackmann ATP/WTA match data (permitted source).
Downloads latest match CSVs for rolling stat calculations.

Usage:
    python tennis/scripts/fetch_sackmann_data.py --year 2026
    python tennis/scripts/fetch_sackmann_data.py --year 2026 --tour wta
"""

import argparse
import urllib.request
from pathlib import Path
from datetime import datetime

TENNIS_DATA_DIR = Path(__file__).parent.parent / "data"
TENNIS_DATA_DIR.mkdir(exist_ok=True)

SACKMANN_BASE_URL = "https://raw.githubusercontent.com/JeffSackmann"

REPO_MAP = {
    "atp": "tennis_atp",
    "wta": "tennis_wta",
}


def fetch_matches(tour: str, year: int):
    """Download match CSV for specified tour and year."""
    repo = REPO_MAP.get(tour.lower())
    if not repo:
        print(f"[ERROR] Invalid tour: {tour}. Use 'atp' or 'wta'.")
        return False
    
    filename = f"{tour.lower()}_matches_{year}.csv"
    url = f"{SACKMANN_BASE_URL}/{repo}/master/{filename}"
    output_path = TENNIS_DATA_DIR / filename
    
    print(f"[FETCH] Downloading {tour.upper()} {year} matches...")
    print(f"        URL: {url}")
    
    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"[✓] Saved to: {output_path}")
        
        # Verify file
        if output_path.exists() and output_path.stat().st_size > 0:
            line_count = len(output_path.read_text(encoding="utf-8").splitlines())
            print(f"[✓] {line_count} lines ({output_path.stat().st_size} bytes)")
            return True
        else:
            print("[ERROR] File is empty or missing")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to download: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch Sackmann tennis data")
    parser.add_argument("--year", type=int, default=datetime.now().year, 
                        help="Year to fetch (default: current year)")
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="both",
                        help="Tour to fetch (atp, wta, or both)")
    
    args = parser.parse_args()
    
    print("\n=== SACKMANN DATA FETCHER ===")
    print(f"Year: {args.year}")
    print(f"Tour: {args.tour.upper()}\n")
    
    success = True
    
    if args.tour in ["atp", "both"]:
        success &= fetch_matches("atp", args.year)
    
    if args.tour in ["wta", "both"]:
        success &= fetch_matches("wta", args.year)
    
    print("\n" + "="*40)
    if success:
        print("✓ FETCH COMPLETE")
        print("\nNext step: Run update_stats_from_sackmann.py")
    else:
        print("✗ FETCH FAILED")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
