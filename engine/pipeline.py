def run_pipeline(league, slate, output_dir, enable_under_first_lens=True, enable_failure_lens=True):
    print(f"[PIPELINE] Running pipeline for league={league}, slate={slate}, output_dir={output_dir}")
    print(f"[PIPELINE] UNDER-first lens: {enable_under_first_lens}, Failure Lens: {enable_failure_lens}")
    import os
    os.makedirs(output_dir, exist_ok=True)
    # Use the new NFL pipeline for full analysis and formatting
    from pipeline.nfl_pipeline import run_nfl_pipeline
    output_path = run_nfl_pipeline(slate, output_dir, enable_under_first_lens=enable_under_first_lens, enable_failure_lens=enable_failure_lens)
    print(f"[PIPELINE] Output written to {output_path}")
