"""
Tests for Matchup Memory Layer
==============================

Tests player_vs_opponent.py and matchup_gates.py functionality.
"""

import pytest
import math
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json

from features.nba.player_vs_opponent import (
    MatchupRecord,
    PlayerVsOpponentStats,
    MatchupIndex,
    build_matchup_index,
    compute_matchup_adjustment,
    NBA_LEAGUE_PRIORS,
)

from features.nba.matchup_gates import (
    MatchupGate,
    MatchupGateResult,
    GateStatus,
    validate_matchup_sample,
    compute_shrinkage_weight,
    get_gate_for_stat,
)


class TestMatchupRecord:
    """Tests for MatchupRecord dataclass."""
    
    def test_basic_creation(self):
        record = MatchupRecord(
            game_id="2026-01-20_BOS",
            game_date=datetime(2026, 1, 20),
            player_id="lebron_james",
            player_name="LeBron James",
            opponent_team="BOS",
            stat_type="PTS",
            stat_value=28.0,
        )
        assert record.player_id == "lebron_james"
        assert record.stat_value == 28.0
        assert record.opponent_team == "BOS"
    
    def test_to_dict_and_back(self):
        record = MatchupRecord(
            game_id="2026-01-20_BOS",
            game_date=datetime(2026, 1, 20),
            player_id="lebron_james",
            player_name="LeBron James",
            opponent_team="BOS",
            stat_type="PTS",
            stat_value=28.0,
            line=25.5,
            hit=True,
            minutes_played=36.0,
        )
        
        d = record.to_dict()
        restored = MatchupRecord.from_dict(d)
        
        assert restored.player_id == record.player_id
        assert restored.stat_value == record.stat_value
        assert restored.hit == True
        assert restored.minutes_played == 36.0


class TestPlayerVsOpponentStats:
    """Tests for PlayerVsOpponentStats aggregation."""
    
    def test_add_records(self):
        stats = PlayerVsOpponentStats(
            player_id="curry_stephen",
            player_name="Stephen Curry",
            opponent_team="LAL",
            stat_type="3PM",
        )
        
        # Add 5 games
        for i, val in enumerate([4, 5, 3, 6, 4]):
            record = MatchupRecord(
                game_id=f"game_{i}",
                game_date=datetime(2026, 1, i + 1),
                player_id="curry_stephen",
                player_name="Stephen Curry",
                opponent_team="LAL",
                stat_type="3PM",
                stat_value=float(val),
            )
            stats.add_record(record)
        
        assert stats.games_played == 5
        assert stats.mean == 4.4  # (4+5+3+6+4)/5
        assert stats.min_value == 3
        assert stats.max_value == 6
    
    def test_bayesian_shrinkage_small_sample(self):
        """Small samples should shrink toward prior, but low variance increases trust."""
        stats = PlayerVsOpponentStats(
            player_id="test",
            player_name="Test",
            opponent_team="BOS",
            stat_type="PTS",
        )
        
        # Add just 2 games with HIGH VARIANCE values (simulates realistic uncertainty)
        for val in [20, 40]:  # High variance: std_dev = 14.14
            stats.add_record(MatchupRecord(
                game_id=f"g_{val}",
                game_date=datetime.now(),
                player_id="test",
                player_name="Test",
                opponent_team="BOS",
                stat_type="PTS",
                stat_value=float(val),
            ))
        
        # League average is 15
        stats.apply_bayesian_shrinkage(league_mean=15.0, league_std=8.0)
        
        # With only 2 games AND high variance, should shrink toward 15
        # Note: low variance data can actually trust sample more (Bayesian property)
        assert stats.shrunk_mean is not None
        assert stats.shrunk_mean < 30  # Should be pulled down from sample mean of 30
        assert stats.shrunk_mean > 15  # But not all the way to prior
        # Confidence should be low due to small sample
        assert stats.confidence < 0.5
    
    def test_bayesian_shrinkage_large_sample(self):
        """Large samples should trust sample mean more."""
        stats = PlayerVsOpponentStats(
            player_id="test",
            player_name="Test",
            opponent_team="BOS",
            stat_type="PTS",
        )
        
        # Add 15 games with consistent values
        for i in range(15):
            stats.add_record(MatchupRecord(
                game_id=f"g_{i}",
                game_date=datetime.now() - timedelta(days=i),
                player_id="test",
                player_name="Test",
                opponent_team="BOS",
                stat_type="PTS",
                stat_value=28.0 + (i % 3 - 1),  # 27, 28, 29 cycle
            ))
        
        stats.apply_bayesian_shrinkage(league_mean=15.0, league_std=8.0)
        
        # With 15 games, should be closer to sample mean (~28)
        assert stats.shrunk_mean is not None
        assert stats.shrunk_mean > 24  # Should stay near sample mean
        assert stats.shrinkage_weight > 0.6  # Higher weight on sample
    
    def test_recency_weighting(self):
        """Recent games should be weighted more heavily."""
        stats = PlayerVsOpponentStats(
            player_id="test",
            player_name="Test",
            opponent_team="BOS",
            stat_type="PTS",
        )
        
        # Old games: low values
        for i in range(5):
            stats.add_record(MatchupRecord(
                game_id=f"old_{i}",
                game_date=datetime.now() - timedelta(days=100 + i),
                player_id="test",
                player_name="Test",
                opponent_team="BOS",
                stat_type="PTS",
                stat_value=10.0,
            ))
        
        # Recent games: high values
        for i in range(3):
            stats.add_record(MatchupRecord(
                game_id=f"new_{i}",
                game_date=datetime.now() - timedelta(days=i),
                player_id="test",
                player_name="Test",
                opponent_team="BOS",
                stat_type="PTS",
                stat_value=30.0,
            ))
        
        # Simple mean: (5*10 + 3*30) / 8 = 17.5
        assert abs(stats.mean - 17.5) < 0.1
        
        # Recency-weighted should be higher (closer to recent 30s)
        assert stats.recency_weighted_mean is not None
        assert stats.recency_weighted_mean > stats.mean


class TestMatchupIndex:
    """Tests for MatchupIndex storage and lookup."""
    
    def test_add_and_retrieve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index = MatchupIndex(storage_path=Path(tmpdir))
            
            record = MatchupRecord(
                game_id="test_game",
                game_date=datetime.now(),
                player_id="player1",
                player_name="Player One",
                opponent_team="BOS",
                stat_type="PTS",
                stat_value=25.0,
            )
            index.add_record(record)
            
            stats = index.get_stats("player1", "BOS", "PTS")
            assert stats is not None
            assert stats.games_played == 1
            assert stats.mean == 25.0
    
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate index
            index = MatchupIndex(storage_path=Path(tmpdir))
            for i in range(3):
                index.add_record(MatchupRecord(
                    game_id=f"game_{i}",
                    game_date=datetime.now(),
                    player_id="player1",
                    player_name="Player One",
                    opponent_team="LAL",
                    stat_type="REB",
                    stat_value=10.0 + i,
                ))
            index.save_index()
            
            # Load fresh index
            index2 = MatchupIndex(storage_path=Path(tmpdir))
            stats = index2.get_stats("player1", "LAL", "REB")
            
            assert stats is not None
            assert stats.games_played == 3


class TestMatchupGates:
    """Tests for gate system."""
    
    def test_sample_size_gate(self):
        gate = MatchupGate(min_games=3, min_games_full=10)
        
        # Fail: too few games
        result = gate.check_sample_size(2)
        assert result.status == GateStatus.FAIL
        
        # Warn: minimum met but not full
        result = gate.check_sample_size(5)
        assert result.status == GateStatus.WARN
        
        # Pass: full sample
        result = gate.check_sample_size(12)
        assert result.status == GateStatus.PASS
    
    def test_variance_gate(self):
        gate = MatchupGate(max_cv=0.8)
        
        # Pass: low variance
        result = gate.check_variance(mean=20.0, std_dev=4.0)  # CV = 0.2
        assert result.status == GateStatus.PASS
        
        # Fail: high variance
        result = gate.check_variance(mean=10.0, std_dev=10.0)  # CV = 1.0
        assert result.status == GateStatus.FAIL
    
    def test_recency_gate(self):
        gate = MatchupGate(max_staleness_days=365)
        
        # Pass: recent
        result = gate.check_recency(datetime.now() - timedelta(days=30))
        assert result.status == GateStatus.PASS
        
        # Warn: aging
        result = gate.check_recency(datetime.now() - timedelta(days=200))
        assert result.status == GateStatus.WARN
        
        # Fail: stale
        result = gate.check_recency(datetime.now() - timedelta(days=400))
        assert result.status == GateStatus.FAIL
    
    def test_evaluate_all(self):
        gate = MatchupGate()
        
        # Good data
        can_apply, results = gate.evaluate_all(
            games_played=10,
            mean=20.0,
            std_dev=5.0,
            last_game_date=datetime.now() - timedelta(days=7),
            confidence=0.7,
        )
        assert can_apply == True
        assert all(r.status in [GateStatus.PASS, GateStatus.WARN] for r in results.values())
        
        # Bad data (too few games)
        can_apply, results = gate.evaluate_all(
            games_played=1,
            mean=20.0,
            std_dev=5.0,
            last_game_date=datetime.now(),
            confidence=0.5,
        )
        assert can_apply == False


class TestShrinkageWeight:
    """Tests for shrinkage weight calculation."""
    
    def test_zero_sample(self):
        weight = compute_shrinkage_weight(0, 10.0, 10.0)
        assert weight == 0.0
    
    def test_increasing_weight_with_sample_size(self):
        weights = []
        for n in [1, 5, 10, 20, 50]:
            w = compute_shrinkage_weight(n, 10.0, 10.0)
            weights.append(w)
        
        # Weight should monotonically increase
        for i in range(len(weights) - 1):
            assert weights[i + 1] > weights[i]
    
    def test_high_variance_reduces_weight(self):
        # Same sample size, different variance
        w_low_var = compute_shrinkage_weight(10, 5.0, 10.0)
        w_high_var = compute_shrinkage_weight(10, 30.0, 10.0)
        
        # High sample variance should reduce weight (more shrinkage)
        assert w_high_var < w_low_var


class TestComputeMatchupAdjustment:
    """Integration tests for main adjustment function."""
    
    def test_insufficient_data_returns_baseline(self):
        adjusted, confidence, lineage = compute_matchup_adjustment(
            player_id="unknown_player",
            opponent_team="BOS",
            stat_type="PTS",
            baseline_projection=20.0,
            matchup_index=MatchupIndex(storage_path=Path(tempfile.mkdtemp())),
        )
        
        assert adjusted == 20.0
        assert confidence == 0.0
        assert lineage["adjustment_applied"] == False
    
    def test_with_matchup_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index = MatchupIndex(storage_path=Path(tmpdir))
            
            # Add favorable matchup history (player averages 30 vs BOS)
            for i in range(5):
                index.add_record(MatchupRecord(
                    game_id=f"game_{i}",
                    game_date=datetime.now() - timedelta(days=i * 7),
                    player_id="star_player",
                    player_name="Star Player",
                    opponent_team="BOS",
                    stat_type="PTS",
                    stat_value=28.0 + i,
                ))
            
            adjusted, confidence, lineage = compute_matchup_adjustment(
                player_id="star_player",
                opponent_team="BOS",
                stat_type="PTS",
                baseline_projection=20.0,  # League baseline
                matchup_index=index,
                league_mean=20.0,
                league_std=8.0,
                min_games=3,
            )
            
            assert lineage["adjustment_applied"] == True
            assert lineage["games_vs_opponent"] == 5
            assert adjusted > 20.0  # Should be adjusted upward
            assert confidence > 0


class TestStatSpecificGates:
    """Tests for stat-specific gate configurations."""
    
    def test_low_volume_stats_stricter(self):
        pts_gate = get_gate_for_stat("PTS")
        blk_gate = get_gate_for_stat("BLK")
        
        # BLK should require more games
        assert blk_gate.min_games > pts_gate.min_games
        
        # BLK should allow higher CV (low-volume stats are more variable)
        assert blk_gate.max_cv > pts_gate.max_cv


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
