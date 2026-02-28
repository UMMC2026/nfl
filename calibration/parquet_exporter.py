"""
Parquet Export Layer — High-Performance Analytics Storage
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from calibration.unified_tracker import UnifiedCalibration

class ParquetExporter:
    def __init__(self, base_path: Path = Path("data/calibration")):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def export_predictions(self, sport: str = None):
        print("=" * 60)
        print("EXPORTING CALIBRATION DATA TO PARQUET")
        print("=" * 60)
        
        db = UnifiedCalibration(Path("calibration/picks.csv"))
        
        if not db.picks:
            print("\n❌ No picks found")
            return
        
        df = pd.DataFrame([
            {
                'pick_id': p.pick_id,
                'date': p.date,
                'sport': p.sport,
                'player': p.player,
                'stat': p.stat,
                'line': p.line,
                'direction': p.direction,
                'probability': p.probability,
                'tier': p.tier,
                'actual': p.actual,
                'hit': p.hit,
                'brier': p.brier,
                'team': p.team,
                'opponent': p.opponent,
                'lambda_player': p.lambda_player,
                'gap': p.gap,
                'z_score': p.z_score,
                'edge': p.edge,
                'model_version': p.model_version,
            }
            for p in db.picks
        ])
        
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        
        if sport:
            df = df[df['sport'] == sport]
        
        print(f"\n📊 Exporting {len(df)} picks")
        
        for sport_name, sport_df in df.groupby('sport'):
            print(f"\n   {sport_name.upper()}:")
            for (year, month), month_df in sport_df.groupby(['year', 'month']):
                if pd.isna(year) or pd.isna(month):
                    continue
                output_path = self.base_path / sport_name / str(int(year)) / f"{int(month):02d}"
                output_path.mkdir(parents=True, exist_ok=True)
                file_path = output_path / "predictions.parquet"
                month_df.drop(columns=['year', 'month']).to_parquet(
                    file_path, engine='pyarrow', compression='snappy', index=False
                )
                file_size = file_path.stat().st_size / 1024
                print(f"     {int(year)}-{int(month):02d}: {len(month_df)} picks → {file_size:.1f} KB")
        
        print(f"\n✅ Export complete to: {self.base_path}")
    
    def load_predictions(self, sport: str, start_date: str = None, end_date: str = None):
        sport_path = self.base_path / sport
        if not sport_path.exists():
            return pd.DataFrame()
        parquet_files = list(sport_path.rglob("*.parquet"))
        if not parquet_files:
            return pd.DataFrame()
        dfs = [pd.read_parquet(f) for f in parquet_files]
        combined = pd.concat(dfs, ignore_index=True)
        if start_date:
            combined = combined[combined['date'] >= start_date]
        if end_date:
            combined = combined[combined['date'] <= end_date]
        return combined

def main():
    exporter = ParquetExporter()
    exporter.export_predictions()
    print("\n✅ Parquet export complete!")

if __name__ == "__main__":
    main()
