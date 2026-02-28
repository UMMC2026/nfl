import pytest

from nba.stat_specialists import (
    StatSpecialistClassifier,
    StatSpecialistType,
    apply_specialist_confidence_governance,
)


class TestStatSpecialistGovernance:
    def test_governance_never_increases_confidence(self):
        conf, meta = apply_specialist_confidence_governance(
            stat="PTS",
            line=12.5,
            confidence_percent=52.0,
            specialist=StatSpecialistType.CATCH_AND_SHOOT_3PM,
        )
        assert conf == 52.0
        assert meta["ceiling_applied"] is False

    def test_microwave_pts_cap_and_dampen(self):
        conf, meta = apply_specialist_confidence_governance(
            stat="PTS",
            line=15.5,
            confidence_percent=80.0,
            specialist=StatSpecialistType.BENCH_MICROWAVE,
        )
        # Cap 55% then apply 0.95 volatility dampening => 52.25%
        assert conf == pytest.approx(52.25, rel=1e-6)
        assert meta["ceiling"] == 55.0
        assert meta["ceiling_applied"] is True

    def test_catch_and_shoot_3pm_caps_to_70(self):
        conf, meta = apply_specialist_confidence_governance(
            stat="3PM",
            line=2.5,
            confidence_percent=88.0,
            specialist=StatSpecialistType.CATCH_AND_SHOOT_3PM,
        )
        assert conf == 70.0
        assert meta["ceiling"] == 70.0

    def test_big_man_3pm_3p5_plus_is_hard_avoid(self):
        conf, meta = apply_specialist_confidence_governance(
            stat="3PM",
            line=3.5,
            confidence_percent=77.0,
            specialist=StatSpecialistType.BIG_MAN_3PM,
        )
        assert conf <= 62.0
        assert meta["hard_avoid"] is True
        assert meta["hard_avoid_reason"] == "BIG_MAN_3PM_3.5_PLUS_AVOID"


class TestStatSpecialistClassifier:
    def test_bench_microwave_feature_rule_classifies(self):
        cls = StatSpecialistClassifier(mapping={})
        out = cls.classify(
            "Some Bench Gunner",
            stat="PTS",
            prop={"bench_minutes_rate": 0.85, "usage_volatility": 0.80},
        )
        assert out.specialist == StatSpecialistType.BENCH_MICROWAVE
        assert out.source in {"manual", "engine"}
