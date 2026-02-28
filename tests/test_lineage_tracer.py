"""
Tests for Probability Lineage Tracer
====================================

Tests full audit trail functionality for probability adjustments.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from truth_engine.lineage_tracer import (
    ProbabilityLineageTracer,
    ProbabilityLineage,
    LineageEntry,
    LineageSource,
    record_lineage_step,
)


class TestLineageEntry:
    """Tests for individual lineage entries."""
    
    def test_basic_entry(self):
        entry = LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.BASELINE,
            input_prob=0.0,
            output_prob=0.55,
            adjustment_factor=1.0,
            confidence=0.9,
            reason="Monte Carlo baseline",
        )
        
        assert entry.source == LineageSource.BASELINE
        assert entry.output_prob == 0.55
    
    def test_to_dict_and_back(self):
        entry = LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.MATCHUP_MEMORY,
            input_prob=0.55,
            output_prob=0.58,
            adjustment_factor=1.055,
            confidence=0.7,
            reason="Favorable BOS matchup",
            metadata={"games_vs_opponent": 8},
        )
        
        d = entry.to_dict()
        restored = LineageEntry.from_dict(d)
        
        assert restored.source == LineageSource.MATCHUP_MEMORY
        assert restored.adjustment_factor == 1.055
        assert restored.metadata["games_vs_opponent"] == 8


class TestProbabilityLineage:
    """Tests for lineage chain tracking."""
    
    def test_add_entries(self):
        lineage = ProbabilityLineage(
            edge_id="edge_123",
            player_id="lebron_james",
            stat_type="PTS",
            line=25.5,
            direction="HIGHER",
        )
        
        # Add baseline
        lineage.add_entry(LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.BASELINE,
            input_prob=0.0,
            output_prob=0.55,
            adjustment_factor=1.0,
            confidence=0.9,
            reason="MC baseline",
        ))
        
        assert lineage.initial_prob == 0.0  # First input
        assert lineage.final_prob == 0.55
        assert lineage.adjustment_count == 1
        
        # Add matchup adjustment
        lineage.add_entry(LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.MATCHUP_MEMORY,
            input_prob=0.55,
            output_prob=0.58,
            adjustment_factor=1.055,
            confidence=0.7,
            reason="BOS favorable",
        ))
        
        assert lineage.final_prob == 0.58
        assert lineage.adjustment_count == 2
        assert abs(lineage.total_adjustment - 1.055) < 0.001
    
    def test_cap_tracking(self):
        lineage = ProbabilityLineage(
            edge_id="test",
            player_id="test",
            stat_type="PTS",
            line=25.5,
            direction="HIGHER",
        )
        
        lineage.add_entry(LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.BASELINE,
            input_prob=0.0,
            output_prob=0.85,
            adjustment_factor=1.0,
            confidence=0.9,
            reason="MC baseline",
        ))
        
        # Add cap
        lineage.add_entry(LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.GATE_CAP,
            input_prob=0.85,
            output_prob=0.75,
            adjustment_factor=0.882,
            confidence=1.0,
            reason="Core cap applied",
        ))
        
        assert lineage.was_capped == True
        assert lineage.cap_applied == 0.75
    
    def test_lineage_hash(self):
        lineage = ProbabilityLineage(
            edge_id="test",
            player_id="test",
            stat_type="PTS",
            line=25.5,
            direction="HIGHER",
        )
        
        lineage.add_entry(LineageEntry(
            timestamp=datetime.now(),
            source=LineageSource.BASELINE,
            input_prob=0.0,
            output_prob=0.55,
            adjustment_factor=1.0,
            confidence=0.9,
            reason="test",
        ))
        
        hash1 = lineage.get_lineage_hash()
        
        # Hash should be deterministic
        hash2 = lineage.get_lineage_hash()
        assert hash1 == hash2
        
        # Hash should be 12 chars
        assert len(hash1) == 12


class TestProbabilityLineageTracer:
    """Tests for the main tracer class."""
    
    def test_start_and_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = ProbabilityLineageTracer(storage_path=Path(tmpdir))
            
            # Start lineage
            tracer.start_lineage("edge_1", "player_1", "PTS", 25.5, "HIGHER")
            
            # Record adjustments
            tracer.record_adjustment(
                "edge_1",
                LineageSource.BASELINE,
                0.0, 0.55, 1.0, 0.9,
                "MC baseline"
            )
            
            tracer.record_adjustment(
                "edge_1",
                LineageSource.HOME_AWAY,
                0.55, 0.57, 1.036, 0.8,
                "Home advantage"
            )
            
            lineage = tracer.get_lineage("edge_1")
            
            assert lineage is not None
            assert lineage.adjustment_count == 2
            assert lineage.final_prob == 0.57
    
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate tracer
            tracer1 = ProbabilityLineageTracer(storage_path=Path(tmpdir))
            tracer1.start_lineage("edge_1", "player_1", "PTS", 25.5, "HIGHER")
            tracer1.record_adjustment(
                "edge_1", LineageSource.BASELINE,
                0.0, 0.55, 1.0, 0.9, "test"
            )
            path = tracer1.save_session("test_session.json")
            
            # Load in new tracer
            tracer2 = ProbabilityLineageTracer(storage_path=Path(tmpdir))
            tracer2.load_session("test_session.json")
            
            lineage = tracer2.get_lineage("edge_1")
            assert lineage is not None
            assert lineage.final_prob == 0.55
    
    def test_summary_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = ProbabilityLineageTracer(storage_path=Path(tmpdir))
            
            # Add several lineages
            for i in range(5):
                tracer.start_lineage(f"edge_{i}", f"player_{i}", "PTS", 25.5, "HIGHER")
                tracer.record_adjustment(
                    f"edge_{i}", LineageSource.BASELINE,
                    0.0, 0.55 + i * 0.02, 1.0, 0.9, "baseline"
                )
                tracer.record_adjustment(
                    f"edge_{i}", LineageSource.MATCHUP_MEMORY,
                    0.55 + i * 0.02, 0.57 + i * 0.02, 1.036, 0.7, "matchup"
                )
            
            report = tracer.generate_summary_report()
            
            assert report["total_lineages"] == 5
            assert report["total_adjustments"] == 10
            assert "source_breakdown" in report
            assert report["source_breakdown"]["baseline"] == 5
            assert report["source_breakdown"]["matchup_memory"] == 5


class TestRecordLineageStep:
    """Tests for convenience function."""
    
    def test_with_tracer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = ProbabilityLineageTracer(storage_path=Path(tmpdir))
            tracer.start_lineage("edge_1", "player_1", "PTS", 25.5, "HIGHER")
            
            prob = record_lineage_step(
                tracer, "edge_1", LineageSource.BASELINE,
                0.0, 0.55, 0.9, "baseline"
            )
            
            assert prob == 0.55
            
            lineage = tracer.get_lineage("edge_1")
            assert lineage.final_prob == 0.55
    
    def test_without_tracer(self):
        # Should work even without tracer (returns output_prob)
        prob = record_lineage_step(
            None, "edge_1", LineageSource.BASELINE,
            0.0, 0.55, 0.9, "baseline"
        )
        
        assert prob == 0.55


class TestLineageSources:
    """Tests for different lineage source types."""
    
    def test_all_sources_valid(self):
        # Ensure all enum values are valid
        sources = [
            LineageSource.BASELINE,
            LineageSource.MATCHUP_MEMORY,
            LineageSource.INJURY_REPORT,
            LineageSource.PACE,
            LineageSource.REST_DAYS,
            LineageSource.HOME_AWAY,
            LineageSource.MINUTES,
            LineageSource.USAGE,
            LineageSource.WEATHER,
            LineageSource.RECENCY,
            LineageSource.CORRELATION,
            LineageSource.GATE_CAP,
            LineageSource.MANUAL_OVERRIDE,
        ]
        
        for source in sources:
            assert source.value is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
