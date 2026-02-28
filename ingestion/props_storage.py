"""SQLite storage for scraped prop history.

This is intentionally lightweight and dependency-free (uses stdlib sqlite3).
It stores each scrape as a 'run' plus the individual props.

No secrets are stored here. Only parsed prop fields + raw text.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "outputs" / "props_history.sqlite"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS prop_runs (
                run_id TEXT PRIMARY KEY,
                ts_utc TEXT NOT NULL,
                sites_json TEXT NOT NULL,
                total_props INTEGER NOT NULL,
                parsed_props INTEGER NOT NULL,
                meta_json TEXT
            );

            CREATE TABLE IF NOT EXISTS props (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                source TEXT,
                player TEXT,
                stat TEXT,
                line REAL,
                direction TEXT,
                parsed INTEGER,
                raw TEXT,
                created_utc TEXT NOT NULL,
                prop_key TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES prop_runs(run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_props_run_id ON props(run_id);
            CREATE INDEX IF NOT EXISTS idx_props_player_stat ON props(player, stat);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_props_run_key ON props(run_id, prop_key);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _make_run_id(output_data: Dict[str, Any]) -> str:
    # Stable-ish run_id based on timestamp + sites + count.
    base = json.dumps(
        {
            "timestamp": output_data.get("timestamp"),
            "sites": output_data.get("sites"),
            "total_props": output_data.get("total_props"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _prop_key(prop: Dict[str, Any]) -> str:
    base = json.dumps(
        {
            "source": prop.get("source"),
            "player": prop.get("player"),
            "stat": prop.get("stat"),
            "line": prop.get("line"),
            "direction": prop.get("direction"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def store_run(
    output_data: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Persist a scrape result to SQLite.

    Returns: run_id
    """
    init_db(db_path)

    run_id = output_data.get("run_id") or _make_run_id(output_data)
    ts_utc = output_data.get("timestamp") or datetime.utcnow().isoformat() + "Z"

    sites = output_data.get("sites") or []
    total_props = int(output_data.get("total_props") or 0)
    parsed_props = int(output_data.get("parsed_props") or 0)

    props: Iterable[Dict[str, Any]] = output_data.get("props") or []

    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO prop_runs(run_id, ts_utc, sites_json, total_props, parsed_props, meta_json) VALUES(?, ?, ?, ?, ?, ?)",
            (
                run_id,
                ts_utc,
                json.dumps(sites),
                total_props,
                parsed_props,
                json.dumps(meta) if meta else None,
            ),
        )

        created_utc = datetime.utcnow().isoformat() + "Z"
        for prop in props:
            key = _prop_key(prop)
            conn.execute(
                """
                INSERT OR IGNORE INTO props(
                    run_id, source, player, stat, line, direction, parsed, raw, created_utc, prop_key
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    prop.get("source"),
                    prop.get("player"),
                    prop.get("stat"),
                    prop.get("line"),
                    prop.get("direction"),
                    1 if prop.get("parsed") else 0,
                    prop.get("raw"),
                    created_utc,
                    key,
                ),
            )

        conn.commit()
        return run_id
    finally:
        conn.close()
