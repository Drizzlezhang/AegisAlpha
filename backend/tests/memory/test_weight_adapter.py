"""Tests for WeightAdapter signal computation and sample collection."""

from datetime import UTC, datetime

import pytest

from aegis.memory.weight_adapter import (
    MIN_SAMPLES,
    WEIGHT_MAX,
    WEIGHT_MIN,
    Sample,
    WeightAdapter,
)
from aegis.memory.weight_store import WeightStore
from aegis.memory.thesis_store import ThesisStore


class TestPnlToSignal:
    """AC-12: P&L signal boundary values."""

    def test_zero_pnl(self):
        assert WeightAdapter.pnl_to_signal(0.0) == 0.0

    def test_positive_20_pct(self):
        assert WeightAdapter.pnl_to_signal(20.0) == 1.0

    def test_negative_20_pct(self):
        assert WeightAdapter.pnl_to_signal(-20.0) == -1.0

    def test_positive_50_pct_clamped(self):
        assert WeightAdapter.pnl_to_signal(50.0) == 1.0

    def test_negative_50_pct_clamped(self):
        assert WeightAdapter.pnl_to_signal(-50.0) == -1.0

    def test_positive_10_pct(self):
        assert WeightAdapter.pnl_to_signal(10.0) == pytest.approx(0.5)

    def test_negative_10_pct(self):
        assert WeightAdapter.pnl_to_signal(-10.0) == pytest.approx(-0.5)


class TestScoreToSignal:
    """1-5 score normalization to [-1, 1]."""

    def test_score_1(self):
        assert WeightAdapter.score_to_signal(1) == -1.0

    def test_score_3(self):
        assert WeightAdapter.score_to_signal(3) == 0.0

    def test_score_5(self):
        assert WeightAdapter.score_to_signal(5) == 1.0

    def test_score_2(self):
        assert WeightAdapter.score_to_signal(2) == pytest.approx(-0.5)

    def test_score_4(self):
        assert WeightAdapter.score_to_signal(4) == pytest.approx(0.5)


class TestCompositeSignal:
    """AC-1: composite_signal = 0.5*pnl + 0.3*judgment + 0.2*execution."""

    def test_all_neutral(self):
        # judgment=3 → 0.0, execution=3 → 0.0, pnl=0% → 0.0
        result = WeightAdapter.composite_signal(judgment=3, execution=3, pnl_pct=0.0)
        assert result == pytest.approx(0.0)

    def test_all_positive(self):
        # judgment=5 → 1.0, execution=5 → 1.0, pnl=20% → 1.0
        # 0.5*1.0 + 0.3*1.0 + 0.2*1.0 = 1.0
        result = WeightAdapter.composite_signal(judgment=5, execution=5, pnl_pct=20.0)
        assert result == pytest.approx(1.0)

    def test_all_negative(self):
        # judgment=1 → -1.0, execution=1 → -1.0, pnl=-20% → -1.0
        # 0.5*(-1.0) + 0.3*(-1.0) + 0.2*(-1.0) = -1.0
        result = WeightAdapter.composite_signal(judgment=1, execution=1, pnl_pct=-20.0)
        assert result == pytest.approx(-1.0)

    def test_mixed_signals(self):
        # judgment=4 → 0.5, execution=2 → -0.5, pnl=10% → 0.5
        # 0.5*0.5 + 0.3*0.5 + 0.2*(-0.5) = 0.25 + 0.15 - 0.10 = 0.30
        result = WeightAdapter.composite_signal(judgment=4, execution=2, pnl_pct=10.0)
        assert result == pytest.approx(0.30)


class TestTimeDecay:
    """AC-2: time decay half-life 90 days."""

    def test_zero_days(self):
        now = datetime(2026, 6, 19, tzinfo=UTC)
        close = datetime(2026, 6, 19, tzinfo=UTC)
        assert WeightAdapter.time_decay_weight(close, now) == pytest.approx(1.0)

    def test_90_days(self):
        now = datetime(2026, 6, 19, tzinfo=UTC)
        close = datetime(2026, 3, 21, tzinfo=UTC)  # ~90 days
        assert WeightAdapter.time_decay_weight(close, now) == pytest.approx(0.5, rel=0.05)

    def test_180_days(self):
        now = datetime(2026, 6, 19, tzinfo=UTC)
        close = datetime(2025, 12, 21, tzinfo=UTC)  # ~180 days
        assert WeightAdapter.time_decay_weight(close, now) == pytest.approx(0.25, rel=0.05)

    def test_naive_datetime(self):
        now = datetime(2026, 6, 19, tzinfo=UTC)
        close = datetime(2026, 6, 19)  # naive
        result = WeightAdapter.time_decay_weight(close, now)
        assert result == pytest.approx(1.0)


class TestWeightedRegression:
    """AC-5: weight clamping [0.2, 3.0]."""

    def test_insufficient_samples(self):
        samples = [
            Sample("trend", 50.0, 0.5, 1.0, datetime.now(UTC))
            for _ in range(MIN_SAMPLES - 1)
        ]
        assert WeightAdapter._weighted_regression(samples) is None

    def test_flat_line(self):
        """All same outcome → slope ≈ 0 → weight ≈ 1.0."""
        samples = [
            Sample("trend", float(i * 10), 0.0, 1.0, datetime.now(UTC))
            for i in range(10)
        ]
        result = WeightAdapter._weighted_regression(samples)
        assert result is not None
        assert result == pytest.approx(1.0, abs=0.1)

    def test_positive_correlation(self):
        """Higher factor_score → higher outcome → positive slope."""
        samples = [
            Sample("trend", 20.0, -0.5, 1.0, datetime.now(UTC)),
            Sample("trend", 40.0, -0.2, 1.0, datetime.now(UTC)),
            Sample("trend", 60.0, 0.1, 1.0, datetime.now(UTC)),
            Sample("trend", 80.0, 0.4, 1.0, datetime.now(UTC)),
            Sample("trend", 100.0, 0.7, 1.0, datetime.now(UTC)),
        ]
        result = WeightAdapter._weighted_regression(samples)
        assert result is not None
        assert result > 1.0  # positive slope

    def test_negative_correlation(self):
        """Higher factor_score → lower outcome → negative slope."""
        samples = [
            Sample("trend", 20.0, 0.5, 1.0, datetime.now(UTC)),
            Sample("trend", 40.0, 0.2, 1.0, datetime.now(UTC)),
            Sample("trend", 60.0, -0.1, 1.0, datetime.now(UTC)),
            Sample("trend", 80.0, -0.4, 1.0, datetime.now(UTC)),
            Sample("trend", 100.0, -0.7, 1.0, datetime.now(UTC)),
        ]
        result = WeightAdapter._weighted_regression(samples)
        assert result is not None
        assert result < 1.0  # negative slope

    def test_weight_clamped_min(self):
        """Extreme negative slope → weight clamped to 0.2."""
        samples = [
            Sample("trend", 20.0, 1.0, 1.0, datetime.now(UTC)),
            Sample("trend", 40.0, 0.5, 1.0, datetime.now(UTC)),
            Sample("trend", 60.0, -0.5, 1.0, datetime.now(UTC)),
            Sample("trend", 80.0, -1.0, 1.0, datetime.now(UTC)),
            Sample("trend", 100.0, -1.0, 1.0, datetime.now(UTC)),
        ]
        result = WeightAdapter._weighted_regression(samples)
        assert result is not None
        assert result >= WEIGHT_MIN

    def test_weight_clamped_max(self):
        """Extreme positive slope → weight clamped to 3.0."""
        samples = [
            Sample("trend", 20.0, -1.0, 1.0, datetime.now(UTC)),
            Sample("trend", 40.0, -0.5, 1.0, datetime.now(UTC)),
            Sample("trend", 60.0, 0.5, 1.0, datetime.now(UTC)),
            Sample("trend", 80.0, 1.0, 1.0, datetime.now(UTC)),
            Sample("trend", 100.0, 1.0, 1.0, datetime.now(UTC)),
        ]
        result = WeightAdapter._weighted_regression(samples)
        assert result is not None
        assert result <= WEIGHT_MAX
