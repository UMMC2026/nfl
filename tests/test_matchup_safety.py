"""
Unit tests for Matchup Safety Module (SOP v2.3)

Tests:
1. Safety level classification (SAFE/CAUTIOUS/DANGEROUS)
2. Weighting math calculations
3. Pick enrichment
4. Probability engine integration
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from core.matchup_safety import (
    MatchupSafetyLevel,
    MatchupWeightMath,
    MatchupSafetyResult,
    classify_matchup_safety,
    compute_matchup_safety,
    enrich_pick_with_matchup_safety,
    integrate_matchup_into_probability,
)


class TestMatchupSafetyClassification(unittest.TestCase):
    """Test safety level classification logic."""
    
    def test_safe_classification_meets_all_criteria(self):
        """SAFE requires: ≥5 games, confidence ≥0.5, variance ratio <2.0"""
        level, risks = classify_matchup_safety(
            games_vs_opponent=6,
            confidence=0.6,
            variance_ratio=1.5,
            has_recent_game=True,
        )
        self.assertEqual(level, MatchupSafetyLevel.SAFE)
        self.assertEqual(len(risks), 0)
    
    def test_safe_downgrade_to_cautious_if_stale(self):
        """SAFE should downgrade to CAUTIOUS if no recent game."""
        level, risks = classify_matchup_safety(
            games_vs_opponent=6,
            confidence=0.6,
            variance_ratio=1.5,
            has_recent_game=False,  # No recent game
        )
        self.assertEqual(level, MatchupSafetyLevel.CAUTIOUS)
        self.assertIn("No game vs OPP in last 60 days", risks)
    
    def test_cautious_with_moderate_sample(self):
        """CAUTIOUS for 3-4 games with moderate confidence."""
        level, risks = classify_matchup_safety(
            games_vs_opponent=4,
            confidence=0.4,
            variance_ratio=2.5,
            has_recent_game=True,
        )
        self.assertEqual(level, MatchupSafetyLevel.CAUTIOUS)
    
    def test_dangerous_small_sample(self):
        """DANGEROUS for <3 games."""
        level, risks = classify_matchup_safety(
            games_vs_opponent=2,
            confidence=0.8,
            variance_ratio=1.0,
            has_recent_game=True,
        )
        self.assertEqual(level, MatchupSafetyLevel.DANGEROUS)
        self.assertTrue(any("Small sample" in r for r in risks))
    
    def test_dangerous_high_variance(self):
        """DANGEROUS for high variance ratio ≥3.0."""
        level, risks = classify_matchup_safety(
            games_vs_opponent=5,
            confidence=0.6,
            variance_ratio=3.5,
            has_recent_game=True,
        )
        self.assertEqual(level, MatchupSafetyLevel.DANGEROUS)
        self.assertTrue(any("High variance" in r for r in risks))
    
    def test_dangerous_low_confidence(self):
        """DANGEROUS for very low confidence <0.3."""
        level, risks = classify_matchup_safety(
            games_vs_opponent=5,
            confidence=0.2,
            variance_ratio=1.5,
            has_recent_game=True,
        )
        self.assertTrue(any("Low confidence" in r for r in risks))


class TestMatchupWeightMath(unittest.TestCase):
    """Test weighting math calculations and formatting."""
    
    def test_math_string_generation(self):
        """Test that math string is properly formatted."""
        math = MatchupWeightMath(
            baseline_projection=22.5,
            matchup_sample_mean=18.2,
            league_mean=21.0,
            games_vs_opponent=4,
            sample_std_dev=3.1,
            league_std_dev=4.5,
            prior_strength=5.0,
            shrinkage_weight=0.44,
            shrunk_mean=19.8,
            adjustment_factor=0.88,
            confidence=0.55,
            adjusted_projection=19.8,
        )
        
        math_str = math.to_math_string()
        
        # Check key components are present
        self.assertIn("Baseline: 22.5", math_str)
        self.assertIn("vs OPP: 18.2", math_str)
        self.assertIn("4 games", math_str)
        self.assertIn("Shrinkage", math_str)
        self.assertIn("Factor = ", math_str)
        self.assertIn("Adjusted:", math_str)
    
    def test_compact_string_generation(self):
        """Test compact representation."""
        math = MatchupWeightMath(
            baseline_projection=22.5,
            matchup_sample_mean=18.2,
            games_vs_opponent=4,
            shrinkage_weight=0.44,
            adjustment_factor=0.88,
            adjusted_projection=19.8,
        )
        
        compact = math.to_compact_string()
        
        self.assertIn("18.2pts", compact)
        self.assertIn("4g", compact)
        self.assertIn("0.44", compact)
        self.assertIn("0.88", compact)
    
    def test_compact_string_no_data(self):
        """Test compact string when no matchup data."""
        math = MatchupWeightMath(games_vs_opponent=0)
        compact = math.to_compact_string()
        self.assertEqual(compact, "No matchup data")
    
    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        math = MatchupWeightMath(
            baseline_projection=22.5,
            adjustment_factor=0.88,
            confidence=0.55,
        )
        
        d = math.to_dict()
        
        self.assertEqual(d["baseline_projection"], 22.5)
        self.assertEqual(d["adjustment_factor"], 0.88)
        self.assertEqual(d["confidence"], 0.55)


class TestMatchupSafetyResult(unittest.TestCase):
    """Test safety result formatting."""
    
    def test_report_line_safe(self):
        """Test report line for SAFE matchup."""
        result = MatchupSafetyResult(
            safety_level=MatchupSafetyLevel.SAFE,
            safety_flag="SAFE",
            games_vs_opponent=6,
            confidence=0.65,
            adjustment_factor=0.92,
            adjustment_applied=True,
        )
        
        line = result.to_report_line()
        
        self.assertIn("🟢", line)  # Green emoji
        self.assertIn("SAFE", line)
        self.assertIn("6g", line)
        self.assertIn("65%", line)
        self.assertIn("0.92x", line)
    
    def test_report_line_dangerous(self):
        """Test report line for DANGEROUS matchup."""
        result = MatchupSafetyResult(
            safety_level=MatchupSafetyLevel.DANGEROUS,
            safety_flag="DANGEROUS",
            games_vs_opponent=2,
            confidence=0.2,
            adjustment_applied=False,
        )
        
        line = result.to_report_line()
        
        self.assertIn("🔴", line)  # Red emoji
        self.assertIn("DANGEROUS", line)
        self.assertIn("N/A", line)  # Not applied
    
    def test_report_line_unknown(self):
        """Test report line for UNKNOWN (no data)."""
        result = MatchupSafetyResult(
            safety_level=MatchupSafetyLevel.UNKNOWN,
            safety_flag="UNKNOWN",
            games_vs_opponent=0,
        )
        
        line = result.to_report_line()
        
        self.assertIn("⚪", line)  # White emoji
        self.assertIn("No matchup history", line)


class TestComputeMatchupSafety(unittest.TestCase):
    """Test main compute_matchup_safety function."""
    
    def test_no_data_returns_unknown(self):
        """When no matchup data, return UNKNOWN."""
        result = compute_matchup_safety(
            player_id="test_player",
            opponent_team="OPP",
            stat_type="PTS",
            baseline_projection=22.5,
            matchup_stats=None,
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.UNKNOWN)
        self.assertFalse(result.adjustment_applied)
    
    def test_empty_games_returns_unknown(self):
        """When games_played=0, return UNKNOWN."""
        result = compute_matchup_safety(
            player_id="test_player",
            opponent_team="OPP",
            stat_type="PTS",
            baseline_projection=22.5,
            matchup_stats={"games_played": 0},
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.UNKNOWN)
    
    def test_safe_matchup_computes_math(self):
        """Test that SAFE matchup computes proper weighting math."""
        matchup_stats = {
            "games_played": 6,
            "mean": 18.0,
            "std_dev": 3.0,
            "shrunk_mean": 19.0,
            "shrinkage_weight": 0.55,
            "confidence": 0.6,
            "last_game_date": (datetime.now() - timedelta(days=30)).isoformat(),
        }
        
        result = compute_matchup_safety(
            player_id="test_player",
            opponent_team="OPP",
            stat_type="PTS",
            baseline_projection=22.5,
            matchup_stats=matchup_stats,
            league_mean=20.0,
            league_std=5.0,
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.SAFE)
        self.assertTrue(result.adjustment_applied)
        self.assertIsNotNone(result.math)
        self.assertAlmostEqual(result.math.baseline_projection, 22.5)
        self.assertAlmostEqual(result.math.matchup_sample_mean, 18.0)


class TestEnrichPickWithMatchupSafety(unittest.TestCase):
    """Test pick enrichment function."""
    
    def test_enriches_basic_pick(self):
        """Test that pick gets enriched with matchup fields."""
        pick = {
            "player": "Test Player",
            "player_id": "test_123",
            "opponent": "LAL",
            "stat_type": "PTS",
            "projection": 22.5,
        }
        
        enriched = enrich_pick_with_matchup_safety(pick)
        
        # Check new fields exist
        self.assertIn("matchup_safety_flag", enriched)
        self.assertIn("matchup_safety_level", enriched)
        self.assertIn("matchup_report_line", enriched)
    
    def test_handles_missing_fields_gracefully(self):
        """Test that missing fields don't cause crashes."""
        pick = {"player": "Test Player"}  # Minimal pick
        
        enriched = enrich_pick_with_matchup_safety(pick)
        
        self.assertIn("matchup_safety_flag", enriched)
        self.assertEqual(enriched["matchup_safety_flag"], "UNKNOWN")


class TestIntegrateMatchupIntoProbability(unittest.TestCase):
    """Test probability engine integration."""
    
    def test_safe_matchup_applies_full_adjustment(self):
        """SAFE matchup should apply full adjustment factor."""
        matchup_stats = {
            "games_played": 6,
            "mean": 18.0,
            "std_dev": 3.0,
            "shrunk_mean": 19.0,
            "shrinkage_weight": 0.55,
            "confidence": 0.6,
            "last_game_date": (datetime.now() - timedelta(days=30)).isoformat(),
        }
        
        adj_mu, adj_sigma, result = integrate_matchup_into_probability(
            mu=22.5,
            sigma=4.0,
            player_id="test_player",
            opponent="OPP",
            stat_type="PTS",
            matchup_stats=matchup_stats,
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.SAFE)
        self.assertTrue(result.adjustment_applied)
        self.assertNotEqual(adj_mu, 22.5)  # Should be adjusted
    
    def test_dangerous_matchup_does_not_apply(self):
        """DANGEROUS matchup should NOT apply adjustment."""
        matchup_stats = {
            "games_played": 2,  # Too few games
            "mean": 25.0,
            "std_dev": 8.0,
            "shrunk_mean": 22.0,
            "shrinkage_weight": 0.2,
            "confidence": 0.2,
        }
        
        adj_mu, adj_sigma, result = integrate_matchup_into_probability(
            mu=22.5,
            sigma=4.0,
            player_id="test_player",
            opponent="OPP",
            stat_type="PTS",
            matchup_stats=matchup_stats,
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.DANGEROUS)
        self.assertFalse(result.adjustment_applied)
        self.assertEqual(adj_mu, 22.5)  # Unchanged
    
    def test_dangerous_with_force_apply(self):
        """DANGEROUS matchup applies when force_apply=True."""
        matchup_stats = {
            "games_played": 2,
            "mean": 18.0,
            "std_dev": 3.0,
            "shrunk_mean": 19.0,
            "shrinkage_weight": 0.2,
            "confidence": 0.2,
        }
        
        adj_mu, adj_sigma, result = integrate_matchup_into_probability(
            mu=22.5,
            sigma=4.0,
            player_id="test_player",
            opponent="OPP",
            stat_type="PTS",
            matchup_stats=matchup_stats,
            force_apply=True,
        )
        
        self.assertTrue(result.adjustment_applied)
        self.assertNotEqual(adj_mu, 22.5)
    
    def test_cautious_applies_half_adjustment(self):
        """CAUTIOUS matchup should apply adjustment at 50% magnitude."""
        matchup_stats = {
            "games_played": 3,
            "mean": 18.0,
            "std_dev": 3.0,
            "shrunk_mean": 19.0,  # Factor would be 19.0/22.5 = 0.844
            "shrinkage_weight": 0.4,
            "confidence": 0.4,
            "last_game_date": (datetime.now() - timedelta(days=30)).isoformat(),
        }
        
        adj_mu, adj_sigma, result = integrate_matchup_into_probability(
            mu=22.5,
            sigma=4.0,
            player_id="test_player",
            opponent="OPP",
            stat_type="PTS",
            matchup_stats=matchup_stats,
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.CAUTIOUS)
        self.assertTrue(result.adjustment_applied)
        
        # Check that adjustment is reduced (moved toward 1.0)
        # Original factor ~0.844, half adjustment ~0.922
        self.assertGreater(result.adjustment_factor, 0.844)
        self.assertLess(result.adjustment_factor, 1.0)
    
    def test_unknown_does_not_apply(self):
        """UNKNOWN (no data) should not apply any adjustment."""
        adj_mu, adj_sigma, result = integrate_matchup_into_probability(
            mu=22.5,
            sigma=4.0,
            player_id="test_player",
            opponent="OPP",
            stat_type="PTS",
            matchup_stats=None,
        )
        
        self.assertEqual(result.safety_level, MatchupSafetyLevel.UNKNOWN)
        self.assertEqual(adj_mu, 22.5)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_zero_baseline_projection(self):
        """Handle zero baseline projection without division error."""
        matchup_stats = {
            "games_played": 5,
            "mean": 5.0,
            "shrunk_mean": 4.5,
            "shrinkage_weight": 0.5,
            "confidence": 0.5,
        }
        
        # Should not raise
        result = compute_matchup_safety(
            player_id="test",
            opponent_team="OPP",
            stat_type="PTS",
            baseline_projection=0.0,
            matchup_stats=matchup_stats,
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.adjustment_factor, 1.0)  # Default to no change
    
    def test_very_high_variance_ratio(self):
        """Handle extreme variance ratios."""
        level, risks = classify_matchup_safety(
            games_vs_opponent=10,
            confidence=0.8,
            variance_ratio=10.0,  # Very high
            has_recent_game=True,
        )
        
        self.assertEqual(level, MatchupSafetyLevel.DANGEROUS)
    
    def test_negative_values_handled(self):
        """Ensure negative values don't cause issues."""
        # This shouldn't happen in practice but should be handled
        result = compute_matchup_safety(
            player_id="test",
            opponent_team="OPP",
            stat_type="PTS",
            baseline_projection=22.5,
            matchup_stats={
                "games_played": 5,
                "mean": -5.0,  # Invalid but should handle
                "shrunk_mean": -3.0,
                "shrinkage_weight": 0.5,
                "confidence": 0.5,
            },
        )
        
        # Should not crash
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
