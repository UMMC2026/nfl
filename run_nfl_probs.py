from ufa.daily_pipeline import DailyPipeline

def main():
    pipeline = DailyPipeline(picks_file="picks_hydrated_nfl.json", output_dir="outputs")
    pipeline.load_picks()
    calibrated = pipeline.process_picks()

    # Print a compact CSV of relevant fields
    print("player,team,stat,line,direction,raw_prob,calibrated_prob,display_prob,tier")
    for p in calibrated:
        print(f"{p.get('player')},{p.get('team')},{p.get('stat')},{p.get('line')},{p.get('direction')},{p.get('raw_prob'):.4f},{p.get('calibrated_prob'):.4f},{p.get('display_prob'):.4f},{p.get('tier')}")

if __name__ == '__main__':
    main()
