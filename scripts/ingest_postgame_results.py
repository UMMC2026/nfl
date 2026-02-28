#!/usr/bin/env python3
"""scripts/ingest_postgame_results.py

Convenient CLI wrapper for automated postgame result ingestion.

Usage:
    python scripts/ingest_postgame_results.py --sport nba
    python scripts/ingest_postgame_results.py --sport nhl --days 2
    python scripts/ingest_postgame_results.py --sport tennis --dry-run
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sources.odds_api_results import main

if __name__ == "__main__":
    main()
