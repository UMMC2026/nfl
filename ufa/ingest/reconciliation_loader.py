"""
Manual reconciliation CSV loader.
Ingests results from data/reconciliation_results.csv
Validates against existing picks, then updates results_tracker.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional


class ReconciliationLoader:
    """Load and validate manual reconciliation results from CSV."""
    
    def __init__(self, csv_path: str = "data/reconciliation_results.csv"):
        self.csv_path = Path(csv_path)
        self.errors = []
        self.warnings = []
    
    def load_csv(self) -> list:
        """Load CSV and return list of result dicts."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {self.csv_path}")
        
        results = []
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                try:
                    result = self._validate_row(row, row_num)
                    if result:
                        results.append(result)
                except ValueError as e:
                    self.errors.append(f"Row {row_num}: {str(e)}")
        
        return results
    
    def _validate_row(self, row: dict, row_num: int) -> Optional[dict]:
        """Validate and normalize a single CSV row."""
        
        # Required fields
        required = ['date', 'player', 'stat', 'result', 'actual_value']
        for field in required:
            if not row.get(field, '').strip():
                raise ValueError(f"Missing required field: {field}")
        
        # Validate date format
        try:
            datetime.strptime(row['date'], '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {row['date']} (use YYYY-MM-DD)")
        
        # Validate result value
        result = row['result'].strip().upper()
        if result not in ['HIT', 'MISS', 'PUSH']:
            raise ValueError(f"Invalid result: {result} (must be HIT/MISS/PUSH)")
        
        # Validate actual_value is numeric
        try:
            actual = float(row['actual_value'])
        except ValueError:
            raise ValueError(f"Invalid actual_value: {row['actual_value']} (must be numeric)")
        
        # Return normalized result
        return {
            'date': row['date'],
            'player': row['player'].strip(),
            'team': row.get('team', '').strip(),
            'stat': row['stat'].strip().lower(),
            'result': result,
            'actual_value': actual,
            'notes': row.get('notes', '').strip(),
        }
    
    def validate_against_picks(self, tracked_picks: list) -> tuple:
        """
        Cross-check CSV results against existing picks.
        Returns: (matches_found, mismatches)
        """
        matches = 0
        mismatches = 0
        
        for result in self.load_csv():
            found = False
            for pick in tracked_picks:
                if (pick['player'].lower() == result['player'].lower() and
                    pick['stat'].lower() == result['stat'].lower() and
                    pick.get('date') == result['date']):
                    matches += 1
                    found = True
                    break
            
            if not found:
                self.warnings.append(
                    f"No pick found for {result['player']} {result['stat']} "
                    f"on {result['date']}"
                )
                mismatches += 1
        
        return matches, mismatches
    
    def apply_to_tracker(self, tracker) -> dict:
        """
        Apply all CSV results to ResultsTracker.
        Returns stats dict.
        """
        results = self.load_csv()
        applied = 0
        failed = 0
        
        for result in results:
            try:
                tracker.update_result(
                    date=result['date'],
                    player=result['player'],
                    stat=result['stat'],
                    result=result['result'],
                    actual_value=result['actual_value']
                )
                applied += 1
            except Exception as e:
                self.errors.append(f"Failed to apply {result['player']}: {str(e)}")
                failed += 1
        
        return {
            'applied': applied,
            'failed': failed,
            'warnings': len(self.warnings),
            'errors': self.errors,
        }
