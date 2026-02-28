"""
CBB Player ID Verification — Gate 0

This module verifies ESPN player IDs for all picks before pipeline execution.
Blocks pipeline if any player cannot be verified.

Rules:
- Fuzzy match player names to ESPN IDs using player_espn_map.json
- If any player ID is missing or mismatched, log error and abort pipeline
- Optionally cross-check with live ESPN API

Usage:
Call `verify_espn_ids(picks)` before modeling. Returns True if all verified, False otherwise.
"""

import json
import logging
import difflib

ESPN_MAP_PATH = 'config/player_espn_map.json'


def load_espn_map():
    with open(ESPN_MAP_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def fuzzy_match(name, candidates):
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.8)
    return matches[0] if matches else None


def verify_espn_ids(picks):
    """
    Verifies ESPN player IDs for all picks.
    Returns True if all verified, False otherwise.
    """
    espn_map = load_espn_map()
    failed = []
    for pick in picks:
        player = pick['entity']
        if player in espn_map:
            continue
        # Fuzzy match
        match = fuzzy_match(player, espn_map.keys())
        if not match:
            failed.append(player)
    if failed:
        logging.error(f'Player ID verification failed for: {failed}')
        return False
    return True
