# UNDERDOG ANALYSIS — User Guide

Version: 2026-02-09

This guide explains **how to use the UNDERDOG ANALYSIS system** day-to-day and outlines **the math** that drives the probabilities you see in reports like the NBA Cheat Sheet.

> Tip: You can open this file directly in **Microsoft Word** (File → Open) or paste it into a `.docx` template.

---

## 1. Big Picture

UNDERDOG ANALYSIS is a **risk-first, governance-heavy** engine for player props across multiple sports.

It’s built as a **three-layer architecture**:

1. **Truth Engine** (`truth_engine/`)
   - Computes distributions (μ, σ) and runs **10k+ Monte Carlo simulations** per pick.
   - Produces immutable probabilities in `*_RISK_FIRST_*.json`.

2. **LLM Adapters** (`llm_adapters/`)
   - Interpret evidence and generate **language-level commentary** (`EvidenceBundle`).
   - Never override Monte Carlo probabilities.

3. **Render Layer** (`render/`, `reports/`, `outputs/`)
   - Generates human-facing reports:
     - FULL_REPORT
     - CHEATSHEET
     - ENHANCED_CONTEXT
   - Enforces hard gates (tier integrity, missing fields, governance).

**Governance rule:** Monte Carlo (Truth Engine) is the **source of truth**. If any other layer disagrees, **Monte Carlo wins**.

---

## 2. Core Concepts

### 2.1 Pick State Machine

Every pick flows through a state machine:

- `RAW` → `ADJUSTED` → `VETTED` → `OPTIMIZABLE`
                        ↓              ↓
                   `REJECTED`      `REJECTED`

- **RAW**: Initial model output (distribution only).
- **ADJUSTED**: After schedule, role, and stat-specific penalties.
- **VETTED**: Informational pick; may be fragile or low-sample.
- **OPTIMIZABLE**: Eligible for Monte Carlo optimization and parlays.
- **REJECTED**: Hidden from outputs and never sent to Telegram.

Eligibility gate lives in `core/decision_governance.py` and enforces (simplified):

- If final probability < 55%: `REJECTED`
- High usage volatility: `REJECTED`
- Bench microwave scoring/assists: `REJECTED`
- Fragile archetypes: `VETTED`
- Low matchup history (< 3 games): probability × 0.85, `VETTED`
- Else: `OPTIMIZABLE`

### 2.2 Tiers (Confidence Bands)

Tier thresholds are centralized in `config/thresholds.py`:

- `TIERS = {"SLAM": 0.80, "STRONG": 0.65, "LEAN": 0.55, "AVOID": 0.0}`
- Per-sport overrides via `SPORT_TIER_OVERRIDES` (e.g., CBB, Tennis, NHL).

**Never hardcode thresholds**; always import from `config.thresholds`.

---

## 3. Daily Workflows (NBA-focused)

### 3.1 Main Entry Point

Run the interactive menu:

- Windows PowerShell:
  - `.venv\Scripts\python.exe menu.py`

Key sections you’ll use most:

- **[1] Ingest New Slate** – Paste Underdog lines.
- **[2] Analyze Slate** – Full risk-first pipeline.
- **[3] Monte Carlo** – Optimize entry combinations.
- **[4] High-Confidence OVERs (>75%)**.
- **[R] Export Report** – Generate FULL_REPORT / CHEATSHEET.
- **[H] Cheat Sheet** – Quick view of plays.
- **[P] Probability Breakdown** – Interactive breakdown of what makes up each pick’s confidence.

### 3.2 Outputs Directory

All standardized outputs live under `outputs/`:

- `{SPORT}_{REPORT_TYPE}_{YYYYMMDD}.{ext}`
- `signals_latest.json` – current run edges.
- `audit/run_{timestamp}.log` – audit log for BROADCAST runs.
- `archive/` – historical runs.

Rules:

- One run = one timestamped file (**no overwrites**).
- Each BROADCAST run must produce an audit entry.
- Edge files must include `run_id` for traceability.

---

## 4. Key Report Types

### 4.1 Risk-First JSON (`*_RISK_FIRST_*.json`)

This is the **canonical mathematical output** for a slate. Example fields per pick:

- `edge_id`, `sport`, `entity` (player), `market` (stat), `line`.
- `direction`: `higher|lower` or `over|under`.
- `mu`: recent average projection.
- `sigma`: standard deviation of the stat.
- `sample_n`: number of games in the sample.
- `raw_probability`: pre-penalty probability vs the line.
- `effective_confidence`: final probability after penalties and caps.
- `tier`: `STRONG`, `LEAN`, etc.
- `pick_state`: `OPTIMIZABLE`, `VETTED`, `REJECTED`.
- `edge_diagnostics.penalties.penalty_details`: list of applied penalties.

All other reports are **views** on this JSON.

### 4.2 NBA Cheat Sheet (`NBA_CHEATSHEET_*.txt`)

The cheat sheet is your **day-to-day decision surface**. It displays, for each pick:

- Player, Stat, Line.
- **OVER % / UNDER %** – directly from `effective_confidence`.
- Edge (difference from 50%).
- Kelly sizing suggestion (`$` column).
- Grouped by tier and direction:
  - STRONG OVERS, STRONG UNDERS.
  - LEAN OVERS, LEAN UNDERS.

It also includes a **calibration snapshot**:

- Brier score (overall calibration quality).
- Tier integrity (realized vs target hit rates).

Interpretation:

- **Trust the OVER% / UNDER% columns** as the **best mathematical estimate** after calibration and governance.
- Use the calibration snapshot to understand **how honest** those numbers have been lately.

### 4.3 FULL_REPORT (`*_FULL_REPORT_*.txt`)

The FULL_REPORT is a verbose governance- and narrative-heavy report for a given slate. It:

- References the underlying RISK_FIRST JSON (`Data Source: ...json`).
- Summarizes gates passed/failed.
- Breaks down edges and tiers by team and stat.

### 4.4 Enhanced Context Report (`ENHANCED_CONTEXT_*.txt`)

The enhanced report wraps around a FULL_REPORT and adds:

1. **Team Coaching / Scheme Context**
2. **Blowout Risk Analysis**
3. **Probability Breakdown Section (Top Picks)**
4. **Matchup Memory** (player × opponent history)
5. Original FULL_REPORT appended at the end.

The Probability Breakdown section is especially important:

- For each top governed pick, it shows:
  - Base distribution: μ, σ, sample size.
  - Raw probability vs line.
  - List of penalties/adjustments.
  - Stat calibration multiplier and direction bias.
  - Any confidence cap.
  - Final effective confidence (matches cheat sheet %).

Use this report when you want to **understand why** a pick is 70.8% instead of 61%, not to get a different number.

---

## 5. The Math (High Level)

### 5.1 Distribution Model

For each player/stat/line, the Truth Engine estimates a normal-like distribution of outcomes:

- Mean: $\mu$ (called `mu` in the data) – the **Recent Avg**.
- Standard deviation: $\sigma$ (called `sigma`).
- Sample size: $n$ (called `sample_n`).

Given a prop line $L$ and direction:

- **Over:** $P(\text{stat} > L)$
- **Under:** $P(\text{stat} < L)$

The system approximates this using a **Monte Carlo simulation**:

1. Simulate many seasons (10k+ trials) from $\mathcal{N}(\mu, \sigma)$ or a similar distribution.
2. Count how often the simulated value is above/below the line.
3. Convert that to a raw probability.

This yields `raw_probability` before any governance or calibration.

### 5.2 Data-Driven Penalties & Multipliers

Calibration lives in `config/data_driven_penalties.py`. It encodes:

- **Stat multipliers** (example values):
  - AST: 1.20 (boosted; historically over-performed).
  - 3PM: 1.06 (slight boost).
  - PTS, REB, PRA: 1.00 (neutral).
  - Combo stats like PTS+AST: 0.75 (penalized; historically over-confident).

- **Direction bias multipliers**:
  - LOWER/UNDER: ~1.03–1.05 (historically under-played, slightly boosted).
  - HIGHER/OVER: ~0.92 (historically over-bet, slightly penalized).

- **Penalty caps**:
  - `MAX_PENALTY_PERCENT = 25.0` – total penalty is bounded.
  - `MIN_CONFIDENCE_FLOOR = 50.0` – final confidence never drops below 50%.

These are learned from **calibration history** (backtested picks in `calibration_history.csv`).

Effectively, the system starts with a raw probability from Monte Carlo and then applies:

$$
P_{\text{calibrated}} = f\bigl(P_{\text{raw}}, \text{stat multiplier}, \text{direction multiplier}, \text{penalties}\bigr)
$$

where $f$ is a combination of multiplicative adjustments and caps.

### 5.3 Governance Penalties (Gates)

Governance gates layer on top of calibration to ensure **risk-first behavior**:

- **Eligibility gate** (`core/decision_governance.py`):
  - Rejects low-confidence or highly volatile picks.
  - Marks fragile picks as `VETTED`.

- **Schedule gate** (`engine/schedule_gate.py`):
  - Aborts when there are no games or schedule is invalid.

- **Roster gate** (`engine/roster_gate.py`):
  - Aborts when a player is not on the active roster.

- **Bias gate** (`engine/directional_bias_gate.py`):
  - Detects directional imbalances (e.g., too many overs).

- **Render gate** (`engine/render_gate.py`):
  - Validates output fields and tier consistency before rendering reports.

These gates can **reduce the number of picks** or downgrade them from `OPTIMIZABLE` to `VETTED`.

### 5.4 Tiers & Targets

After calibration and governance, each pick’s final probability is compared against sport-specific tier thresholds.

For NBA (default):

- `STRONG` ≈ 65%+
- `LEAN` ≈ 55–65%

The system then tracks realized hit rates by tier in `calibration_history.csv` and reports:

- Brier score (0 = perfect, 1 = worst; target ≈ 0.25).
- Tier integrity (e.g., LEAN realized 51.5% vs target 55%).

These metrics are used to refine the calibration multipliers over time.

---

## 6. How to Use the System in Practice

### 6.1 For Fast Slate Decisions

1. Run `menu.py` → `[2] Analyze Slate`.
2. Generate the **NBA CHEATSHEET** (`[H] Cheat Sheet` or via reports menu).
3. Focus on:
   - STRONG UNDERS/OVERS first.
   - LEAN plays only when they align with your own narrative.
4. Check the **calibration snapshot** at the top of the cheat sheet:
   - If `Status: [WARN] DRIFT DETECTED`, reduce aggression (size down, fewer legs).

### 6.2 For Deep Dives on a Specific Pick

1. Open the **Enhanced Context report** for that slate (`ENHANCED_CONTEXT_*.txt`).
2. Find the **Probability Breakdown** section.
3. For the pick in question, review:
   - Base μ, σ, and sample size.
   - Applied penalties (role volatility, schedule, matchup, combos).
   - Stat and direction multipliers.
   - Any cap on confidence.
4. Decide whether external context (injury news, lineup changes) supports or contradicts the model.

### 6.3 For Postgame Calibration

1. Use the results ingestion tools (`auto_verify_results.py`, etc.).
2. Update `calibration_history.csv` via the **Resolve Picks** menu / scripts.
3. Run calibration analytics:
   - `analyze_calibration.py` or related scripts.
4. Revisit `config/data_driven_penalties.py` only when enough new data justifies changes.

---

## 7. What Each Layer “Takes Accountability” For

- **Truth Engine (RISK_FIRST JSON)**
  - Accountability: **math** (μ, σ, Monte Carlo, calibration).
  - Includes: implicit team strength, some defense, some schedule effects through historical stats.

- **Governance**
  - Accountability: **risk control** (who even gets to be a pick and what state).
  - Includes: usage volatility, fragile roles, low-sample penalties, bias correction.

- **Reports (Cheat Sheet, FULL_REPORT, Enhanced Context)**
  - Accountability: **presentation and explanation**.
  - Cheat Sheet: what % the system believes after all math and governance.
  - Enhanced Context: why the system believes that number, plus qualitative context (team defense, B2B, home/away, blowout risk).

LLMs / narrative layers are **never** accountable for the probability; they only comment on it.

---

## 8. Suggested Workflow for You

1. **Start with the Cheat Sheet**
   - Use OVER% / UNDER% as your primary signal.
   - Respect tier labels (STRONG vs LEAN).

2. **Consult Enhanced Context for Edge Cases**
   - If something feels off (e.g., a 70% over that you hate), open the Probability Breakdown to see what the engine is seeing.

3. **Trust Governance When It Says "No"**
   - `REJECTED` or non-OPTIMIZABLE picks are blocked for a reason; forcing them back in breaks the risk-first design.

4. **Let Calibration Drive Changes, Not Vibes**
   - When overs or unders go on a heater or cold streak, look at calibration results.
   - Update `STAT_MULTIPLIERS` and `DIRECTION_ADJUSTMENT` based on **aggregated outcomes**, not one slate.

This keeps the system mathematically honest over time while still giving you the context you need to make human decisions.
