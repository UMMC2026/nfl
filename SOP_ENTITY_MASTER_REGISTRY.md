# 📌 SOP: ENTITY MASTER REGISTRY (ALL SPORTS)

**Version:** 1.0  
**Effective Date:** 2026-02-07  
**Status:** ACTIVE  
**Owner:** Risk-First Quant Governance Engine  
**Scope:** ALL SPORTS (NBA, NFL, CFB, CBB, Tennis, Soccer, Golf, NHL, future)

---

## 1) Purpose

Ensure every pipeline run can **persist and reuse** a consistent, auditable record of entities (players/teams/fighters/golfers) including:

- **Stable internal ID** (always)
- **Name** (always)
- **Team + position** (when applicable)
- **Stats snapshots** (when available)
- **Archetype / specialist** (when applicable; e.g., NBA)

This SOP is designed to prevent:

- Name drift causing mismatches (e.g., “J. Smith” vs “John Smith”)
- Downstream systems lacking metadata for display, dedupe, and governance
- Loss of archetype context during export/Telegram/DB write

**Governance note:** Entity registry is **metadata only**. It must **never** override probabilities, tiers, or MC truth.

---

## 2) Definitions (Canonical)

### 2.1 Entity
A canonical object representing **one real-world subject**:

- Player (NBA/NFL/CBB/NHL/Tennis)
- Team (Soccer, some NHL markets)
- Fighter (Boxing/MMA)
- Golfer (Golf)

### 2.2 Entity ID (required)
A **stable internal identifier** used across artifacts and DB writes.

- If a trustworthy external ID exists (NBA API player_id, ESPN athlete id): store it as `external_ids.*`.
- Always compute and store an internal `entity_id` so the system still works when external IDs are missing.

**Rule:** internal `entity_id` must be deterministic (same inputs → same output).

### 2.3 Snapshot
A time-stamped record of stats/role context captured at ingest or analysis time.

---

## 3) Storage Standard

### 3.1 Primary storage (recommended)
- **SQLite cache DB** under `cache/` (fast, offline-friendly, zero deployment friction)

**Canonical path:**
- `cache/entity_master.db`

### 3.2 Optional secondary storage
- If/when required for UFA production surfaces: mirror essential fields into `ufa.db`.

**Rule:** If both are used, `cache/entity_master.db` remains the **source of truth** for entity metadata; `ufa.db` is a distribution layer.

---

## 4) Canonical Schema (logical)

### 4.1 Entity master (one row per entity)
Required columns:
- `entity_id` (TEXT, primary key)
- `sport` (TEXT)
- `entity_type` (TEXT: `player|team|fighter|golfer|other`)
- `name` (TEXT)
- `team` (TEXT nullable)
- `position` (TEXT nullable)
- `last_seen_utc` (TEXT/ISO)
- `external_ids` (JSON TEXT) — e.g., `{ "nba_api": 203999, "espn": "12345" }`
- `metadata` (JSON TEXT) — anything sport-specific

### 4.2 Entity snapshots (append-only)
- `entity_id` (TEXT)
- `captured_at_utc` (TEXT/ISO)
- `source` (TEXT) — e.g., `nba_api`, `odds_api`, `nflverse`, `tennis_props_engine`
- `payload` (JSON TEXT) — stats snapshot, minutes, usage, archetype, etc.

**Rule:** snapshots are append-only; do not rewrite history.

---

## 5) ID Rules (How to compute `entity_id`)

### 5.1 Deterministic internal ID (default)
Compute:

$$
entity\_id = sha1( sport \Vert entity\_type \Vert normalized\_name \Vert normalized\_team )[:16]
$$

Where:
- `normalized_name = lower(trim(name))`
- `normalized_team = lower(trim(team))` or empty string when not applicable

### 5.2 External IDs
If present, store them under `external_ids` and still keep the internal ID.

---

## 6) Update Protocol (When to write)

### 6.1 Ingest stage (MANDATORY if names exist)
Whenever ingest produces a slate or events list containing entity names:

- Upsert entities into the master table
- Add a snapshot with the ingest context

This applies to:
- Odds API ingests (Soccer/Tennis match winner)
- Paste-based slate ingests (Underdog/PrizePicks)
- API roster pulls (NBA/NFL/NHL)

### 6.2 Analysis/export stage (MANDATORY when archetypes/stats exist)
Whenever analysis produces model outputs per entity (μ/σ/n, archetype, specialist, role):

- Upsert any new fields into master metadata
- Add a snapshot containing:
  - mu/sigma/sample_n
  - archetype/specialist
  - any model-relevant context that is safe to store

**Hard rule:** storing the snapshot is allowed, but it must not change model math.

---

## 7) Sport-specific expectations

### NBA
- Entities: players
- External ID: NBA API `player_id` (when available)
- Position: required when available
- Archetype/specialist: expected (role layer)

### NFL / CFB / CBB
- Entities: players
- External ID: ESPN athlete id / other source when available
- Position: expected
- Archetype: optional (only if your pipeline defines it)

### Tennis
- Entities: players
- External ID: typically not available in Odds API tournament feeds
- Position: N/A
- Archetype: optional (not currently defined)

### Soccer
- Entities: teams (usually) and/or players (only if your markets are player-props)
- External ID: typically not available from odds feeds
- Position: N/A (for teams)

### NHL
- Entities: players + goalies (+ teams for some markets)
- Position: expected for players/goalies when available
- Archetype: optional

### Golf
- Entities: golfers
- Position: N/A

---

## 8) Governance / Validation Rules

### 8.1 No pipeline abort
Missing entity metadata must **never** hard-fail a run.

- If entity registry is unavailable: log a warning, continue.
- If a name cannot be normalized: store as-is and flag `metadata.name_quality="raw"`.

### 8.2 Never used to override truth
- Do not change probabilities/tier/pick_state based on registry data.
- Registry is for: dedupe, display, cross-run continuity, audit.

### 8.3 Required fields for export artifacts
When exporting governed signals (`outputs/{sport}_signals_latest.json`):

- Must include `entity` (string name)
- Should include `entity_id` (if registry is enabled)

---

## 9) Troubleshooting

### Symptom: duplicate players with small name differences
**Cause:** normalization mismatch.

**Fix:**
- Normalize names before writing.
- Add `metadata.aliases=[...]` to unify.

### Symptom: tennis Odds API has no IDs/positions
**Expected.**
- Use internal deterministic `entity_id`.

### Symptom: registry DB missing
**Fix:**
- Ensure `cache/` is writable.
- Re-run any pipeline; registry should rebuild from ingest/export.

---

## 10) Compliance

This SOP is subordinate to the repo’s governance constraints:

- Tier thresholds must come from `config/thresholds.py`
- Eligibility gating must run before optimization/Telegram/DB write
- Signals exports are the source of truth for downstream sending

**SOP violation examples:**
- Using registry metadata to bump probability
- Rewriting historical snapshots
- Blocking a run because registry is missing
