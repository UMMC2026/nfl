# FUOOM NBA GAME SIMULATOR - DEPLOYMENT GUIDE

## 1. FILES TO DEPLOY
- `nba_game_simulator.py`
- `fuoom_simulation_integration.py`
- `fuoom_backtest.py`
- `EXECUTIVE_SUMMARY.md`
- `QUICK_START.md`

## 2. CONFIGURATION
- Place all files in your `/outputs` or integration directory
- Ensure all dependencies (numpy, pandas, sklearn, matplotlib) are installed
- Prepare team and player stats JSONs as described in the summary

## 3. INTEGRATION STEPS
1. Import `add_simulation_to_pipeline` in your edge generation module
2. Pass your edges, team stats, and player stats to the function
3. Use `final_probability` for all tiering and filtering
4. Log and monitor new fields: `sim_probability`, `blowout_risk`, `sim_mean`, etc.

## 4. BACKTESTING
- Use `fuoom_backtest.py` to validate calibration and ROI
- Compare FUOOM-only, Simulation-only, and Blended models
- Tune blending weights as needed

## 5. DEPLOYMENT CHECKLIST
- [ ] All files in correct directory
- [ ] Team/player stats up to date
- [ ] Simulator runs without error
- [ ] Integration outputs expected fields
- [ ] Backtest shows calibration improvement
- [ ] Shadow mode logs match expectations
- [ ] Ready for A/B test or full deployment

## 6. SUPPORT
- See `EXECUTIVE_SUMMARY.md` and `QUICK_START.md` for details
- Code is documented for further extension
