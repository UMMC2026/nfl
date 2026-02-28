"""Quick pipeline test: run CBB pipeline and check probability diversity."""
import sys, os
os.environ["CBB_OFFLINE"] = "1"
sys.path.insert(0, '.')

from sports.cbb.cbb_main import run_full_pipeline
result = run_full_pipeline(skip_ingest=True)
