# Risk-First Pipeline - Master Governance Menu

## Launch Command
```bash
.venv\Scripts\python.exe hub.py
```

## Menu Structure

### SECTION 1: SLATE ACTION & SIMULATION
- **[A] ANALYZE SLATE** - Apply ESS Gates + Gating Reasons
- **[M] MONTE CARLO PRO** - Tail-Risk & Distribution Analysis
- **[I] INTERACTIVE FILTER** - Stat Selection: 1Q, DD, Defensive Stats
- **[S] STAT RANKINGS** - Global Market Inefficiencies

### SECTION 2: GOVERNANCE & FAILURE CONTROL
- **[F] FAS AUDIT** - Failure Attribution: Backfill & Heatmap
- **[E] ESS CONFIG** - Tweak Stability Weights & Tier Gates
- **[C] COACHING PROFILES** - Rotation Elasticity & Foul Tolerance
- **[X] CHAOS STRESS TEST** - Run 50-Game Monte Carlo Noise Simulation

### SECTION 3: CALIBRATION & OBSERVABILITY
- **[7] CALIBRATION** - FAS-Driven Penalty Recalibration
- **[8] THRESHOLD OPT** - Auto-Tune SLAM/STRONG ESS Cutoffs
- **[OB] OBSERVABILITY** - ESS Distribution & System Health

### SECTION 4: EXPORT & MULTI-SPORT
- **[R] GENERATE REPORTS** - PDF/CSV with ESS + Gating Explanations
- **[Y] TENNIS | [B] CBB | [F] NFL | [O] SOCCER | [Z] GOLF**
- **[Q] EXIT SYSTEM**

## Interactive Filter Sub-Menu

The [I] Interactive Filter allows you to enable/disable stat types:
- Points (PTS)
- Rebounds (REB)
- Assists (AST)
- Pts+Rebs+Asts (PRA)
- 1st Quarter Points (1Q_PTS)
- Blocks (BLK)
- Turnovers (TOV)
- Double Doubles (DD)
- Triple Doubles (TD)
- 3-Pointers Made (3PM)
- Pts+Rebs (PR)
- Pts+Asts (PA)
- Rebs+Asts (RA)

## Key Features

### State Visibility
The header shows:
- Governance Mode (DEFENSIVE/AGGRESSIVE)
- Active stats loaded
- System version

### Governance Integration
All governance modules (ESS, FAS, Chaos, Coaching) are integrated and accessible from the main menu.

### Transparency
Pick displays show:
- ESS score
- Tier (SLAM/STRONG/LEAN-A/LEAN-B/SKIP)
- Gating reason (e.g., "High Minute Variance", "Low Blowout Risk")

### Observability
Real-time system health metrics:
- ESS distribution
- Edge leakage detection
- System trust score
- Recent FAS tag frequencies

## Next Steps

1. **Integration**: Hook your existing simulation/analysis pipelines to menu options [A] and [M].
2. **FAS Backend**: Connect [F] to your database/CSV tracking for post-game audits.
3. **Reporting**: Wire [R] to your existing report generators with ESS metadata.
4. **Multi-Sport**: Ensure all sport-specific modules ([Y], [B], [F], [O], [Z]) launch correctly.
