# FUOOM NBA GAME SIMULATOR - QUICK START

## WHAT YOU HAVE

**4 Production Files:**
1. `nba_game_simulator.py` - Core Monte Carlo engine
2. `fuoom_simulation_integration.py` - FUOOM pipeline bridge
3. `fuoom_backtest.py` - Validation framework
4. `SIMULATION_DEPLOYMENT_GUIDE.md` - Step-by-step deployment

---

## IMMEDIATE NEXT STEPS

### Step 1: Test the Core Simulator
```bash
cd /path/to/outputs
python nba_game_simulator.py
```

### Step 2: Test Integration Module
```bash
python fuoom_simulation_integration.py
```

### Step 3: Review Deployment Guide
```bash
open SIMULATION_DEPLOYMENT_GUIDE.md
# or
cat SIMULATION_DEPLOYMENT_GUIDE.md
```

---

## BEFORE PRODUCTION: RUN BACKTEST

- Prepare historical picks CSV/DataFrame with columns:
  - date, player, stat_type, line, direction, fuoom_probability, actual_result, actual_stat_value
- Run backtest:
```python
from fuoom_backtest import SimulationBacktest
backtest = SimulationBacktest(historical_data)
results = backtest.run_full_backtest()
backtest.generate_report('backtest_results.md')
backtest.plot_calibration_curves('calibration.png')
```

---

## INTEGRATION INTO FUOOM PIPELINE

- Import `add_simulation_to_pipeline` from `fuoom_simulation_integration.py`
- Enhance your edge generation as shown in the deployment guide
- Use `final_probability` for tiering and filtering

---

## SUPPORT
- Review `EXECUTIVE_SUMMARY.md` for system overview
- Review `SIMULATION_DEPLOYMENT_GUIDE.md` for detailed steps
- Code documentation in each .py file
