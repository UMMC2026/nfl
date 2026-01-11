
from ufa.patches.fallback_patch import apply as _apply_fallback
_apply_fallback()

from ufa.daily_pipeline import DailyPipeline

p = DailyPipeline(picks_file="picks_hydrated_nfl.json", output_dir="outputs")
p.load_picks()
calibrated = p.process_picks()

print("player,team,stat,line,mu,sigma,recent_count,recent_values,raw_prob,calibrated_prob,display_prob,tier")
for pick in calibrated:
    mu = pick.get('mu')
    sigma = pick.get('sigma')
    rv = pick.get('recent_values') or []
    print(
        f"{pick.get('player')},{pick.get('team')},{pick.get('stat')},{pick.get('line')},"
        f"{mu if mu is not None else ''},{sigma if sigma is not None else ''},{len(rv)},\"{rv[:5]}\",{pick.get('raw_prob'):.4f},{pick.get('calibrated_prob'):.4f},{pick.get('display_prob'):.4f},{pick.get('tier')}"
    )
