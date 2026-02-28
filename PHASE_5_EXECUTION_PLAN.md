# Phase 5 Execution Plan (Option A + D)

Date: 2026-02-05

This phase is intentionally split into two parallel streams:

- **5A — Subscriber Dashboards**: turn the system into something users can *consume*, trust, and self-serve.
- **5D — Enterprise Infrastructure**: make runs repeatable, auditable, and safe to scale.

No governance rules change in Phase 5. Monte Carlo remains the truth source; presentation layers do not override probabilities.

---

## 5A — Subscriber Dashboards (12-week track)

### Weeks 1–2: MVP dashboard hardening (read-only)
- Add light API protection for dashboard JSON endpoints (API key / public mode).
- Add sport filter + time window filter for pick history and calibration plots.
- Add “run inventory” view: list latest reports/edges artifacts by sport.

**Exit gate:** dashboard runs locally with zero manual DB tweaks; API endpoints return JSON in <1s on local DB.

### Weeks 3–4: Shareable snapshots + attribution
- Shareable “snapshot” pages that render a frozen view (not live DB queries).
- Add performance attribution slices: by stat, direction, tier, archetype/specialist.

**Exit gate:** can generate a share page without leaking internal DB.

### Weeks 5–6: Subscriber tier shaping (same logic as Telegram)
- Reuse existing tier shaping rules to show what each subscriber tier can see.
- Implement “what changed since last run” view.

**Exit gate:** tier shaping matches bot output rules on the same dataset.

### Weeks 7–9: Reliability + UX
- Caching for heavy endpoints.
- “Data freshness” and “stale cache” indicators.
- Add export buttons (CSV/JSON) for user self-service.

### Weeks 10–12: Ops + documentation
- Add diagnostics page (DB size, unresolved picks, last run timestamps, error counts).
- Document deployment paths (local, single VM, container).

---

## 5D — Enterprise Infrastructure (16-week track)

### Weeks 1–2: Data integrity + legacy sync
- Migrate/bridge legacy `calibration_history.csv` into `cache/pick_history.db`.
- Add an audit log artifact for every sync.

**Exit gate:** legacy CSV data is visible in dashboard via SQLite.

### Weeks 3–5: Run registry + artifacts
- Introduce a “run registry” record for each pipeline run (sport, run_id, timestamp, outputs produced).
- Standardize artifact naming & indexing.

### Weeks 6–8: Gate-first CI checks
- Add smoke checks for core pipeline modules.
- Add validation scripts that can run headless.

### Weeks 9–12: Multi-sport harmonization
- Normalize sport naming + stat naming across signals outputs.
- Ensure pick logging/resolution works identically across NBA/Tennis/CBB/NHL/Soccer.

### Weeks 13–16: Scale + deployment
- Containerize dashboard + worker (optional).
- Add clear runbooks (backup/restore, incident triage, key rotation).

---

## Success Metrics (Phase 5)

- **Operational:** dashboard always loads; no “missing file” surprises.
- **Data integrity:** no duplicate picks; resolution is idempotent.
- **Calibration:** ability to compute calibration report from SQLite alone.
- **Auditability:** every sync/run leaves a timestamped artifact in `outputs/audit/`.
