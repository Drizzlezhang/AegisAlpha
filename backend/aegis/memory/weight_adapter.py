"""WeightAdapter — dual-dimension feedback → weighted regression → factor weight adaptation.

Algorithm:
  1. Collect closed ThesisCards with judgment_score (1-5), execution_score (1-5), actual_pnl_pct
  2. Compute composite_signal = 0.5*pnl_signal + 0.3*judgment_signal + 0.2*execution_signal
  3. Apply time decay: decay = 0.5^(age_days / 90)
  4. Group samples by factor_name (from factor_snapshot)
  5. For each factor with >= 5 samples: numpy weighted least squares
     → new_weight = clamp(1.0 + slope, 0.2, 3.0)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from loguru import logger

from sqlalchemy.orm import Session

from aegis.memory.thesis_store import ThesisStore
from aegis.memory.weight_store import WeightStore
from aegis.models.thesis import ThesisCard

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HALF_LIFE_DAYS: float = 90.0
MIN_SAMPLES: int = 5
WEIGHT_MIN: float = 0.2
WEIGHT_MAX: float = 3.0
DEFAULT_WEIGHT: float = 1.0

# Composite signal coefficients
PNL_COEFF: float = 0.5
JUDGMENT_COEFF: float = 0.3
EXECUTION_COEFF: float = 0.2


@dataclass
class Sample:
    """A single data point for weighted regression."""

    factor_name: str
    factor_score: float  # original factor score from factor_snapshot (0-100)
    outcome: float  # composite_signal value in [-1, 1]
    time_decay_weight: float  # 0.5^(age_days / 90)
    close_date: datetime


class WeightAdapter:
    """Core algorithm: collect samples, compute signals, run weighted regression."""

    def __init__(self, weight_store: WeightStore, thesis_store: ThesisStore) -> None:
        self._weight_store = weight_store
        self._thesis_store = thesis_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_weights(self, session: Session) -> dict[str, float]:
        """Main entry point: collect samples, regress, update weights.

        Returns:
            Dict of {factor_name: new_weight} for factors that were updated.
        """
        cards = self._thesis_store.get_closed_cards(session)
        if not cards:
            logger.info("WeightAdapter: no closed cards, keeping current weights")
            return {}

        samples_by_factor = self._collect_samples(cards)
        updated: dict[str, float] = {}

        for factor_name, samples in samples_by_factor.items():
            if len(samples) < MIN_SAMPLES:
                logger.debug(
                    f"WeightAdapter: {factor_name} has {len(samples)} samples, "
                    f"need {MIN_SAMPLES}, skipping"
                )
                continue

            new_weight = self._weighted_regression(samples)
            if new_weight is None:
                logger.warning(
                    f"WeightAdapter: regression failed for {factor_name}, keeping current weight"
                )
                continue

            current = self._weight_store.get_weight(session, factor_name)
            if abs(new_weight - current) < 0.001:
                logger.debug(f"WeightAdapter: {factor_name} weight unchanged ({current:.3f})")
                continue

            self._weight_store.update_weight(
                session,
                factor_name=factor_name,
                new_weight=round(new_weight, 4),
                sample_count=len(samples),
                changed_by="system",
            )
            updated[factor_name] = new_weight
            logger.info(
                f"WeightAdapter: {factor_name} {current:.3f} → {new_weight:.3f} (n={len(samples)})"
            )

        return updated

    # ------------------------------------------------------------------
    # Signal computation (public for testability)
    # ------------------------------------------------------------------

    @staticmethod
    def pnl_to_signal(pnl_pct: float) -> float:
        """Map P&L% to [-1, 1].

        >= +20% → 1.0, 0% → 0.0, <= -20% → -1.0, linear interpolation between.
        Values beyond ±20% are clamped.
        """
        if pnl_pct >= 20.0:
            return 1.0
        if pnl_pct <= -20.0:
            return -1.0
        return pnl_pct / 20.0

    @staticmethod
    def score_to_signal(score: int, range_max: int = 5) -> float:
        """Normalize a 1..range_max score to [-1, 1].

        1 → -1.0, range_max → +1.0, midpoint → 0.0.
        """
        if range_max <= 1:
            return 0.0
        return 2.0 * (score - 1) / (range_max - 1) - 1.0

    @staticmethod
    def composite_signal(judgment: int, execution: int, pnl_pct: float) -> float:
        """Compute weighted composite signal.

        composite = 0.5 * pnl_signal + 0.3 * judgment_signal + 0.2 * execution_signal
        """
        pnl_sig = WeightAdapter.pnl_to_signal(pnl_pct)
        j_sig = WeightAdapter.score_to_signal(judgment)
        e_sig = WeightAdapter.score_to_signal(execution)
        return PNL_COEFF * pnl_sig + JUDGMENT_COEFF * j_sig + EXECUTION_COEFF * e_sig

    @staticmethod
    def time_decay_weight(close_date: datetime, now: datetime | None = None) -> float:
        """Compute time decay: 0.5^(age_days / 90).

        Args:
            close_date: When the position was closed.
            now: Reference time (defaults to UTC now).

        Returns:
            Decay factor in (0, 1].
        """
        if now is None:
            now = datetime.now(UTC)
        # Ensure both are offset-aware or both naive
        if close_date.tzinfo is None and now.tzinfo is not None:
            close_date = close_date.replace(tzinfo=UTC)
        elif close_date.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        age_days = (now - close_date).total_seconds() / 86400.0
        if age_days < 0:
            age_days = 0.0
        return float(0.5 ** (age_days / HALF_LIFE_DAYS))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _collect_samples(self, cards: list[ThesisCard]) -> dict[str, list[Sample]]:
        """Group closed cards by factor_name from factor_snapshot.

        Each card contributes one Sample per factor in its factor_snapshot.
        """
        now = datetime.now(UTC)
        samples_by_factor: dict[str, list[Sample]] = {}

        for card in cards:
            if not card.factor_snapshot:
                continue
            # These are guaranteed non-None by ThesisStore.get_closed_cards filter
            assert card.judgment_score is not None
            assert card.execution_score is not None
            assert card.actual_pnl_pct is not None
            assert card.close_date is not None

            outcome = self.composite_signal(
                card.judgment_score, card.execution_score, card.actual_pnl_pct
            )
            decay = self.time_decay_weight(card.close_date, now)

            for factor_name, factor_score in card.factor_snapshot.items():
                if not isinstance(factor_score, (int, float)):
                    continue
                sample = Sample(
                    factor_name=factor_name,
                    factor_score=float(factor_score),
                    outcome=outcome,
                    time_decay_weight=decay,
                    close_date=card.close_date,
                )
                samples_by_factor.setdefault(factor_name, []).append(sample)

        return samples_by_factor

    @staticmethod
    def _weighted_regression(samples: list[Sample]) -> float | None:
        """Weighted least squares: outcome ~ factor_score.

        Uses numpy.linalg.lstsq with sample weights = time_decay_weight.
        Returns new_weight = clamp(1.0 + slope, 0.2, 3.0), or None on failure.
        """
        if len(samples) < MIN_SAMPLES:
            return None

        n = len(samples)
        # Design matrix: [factor_score, 1] for each sample
        x_mat = np.column_stack(
            [
                np.array([s.factor_score for s in samples]),
                np.ones(n),
            ]
        )
        y_vec = np.array([s.outcome for s in samples])
        w_vec = np.array([s.time_decay_weight for s in samples])

        # Weighted least squares: multiply X and y by sqrt(w)
        sqrt_w = np.sqrt(w_vec)
        x_w = x_mat * sqrt_w[:, np.newaxis]
        y_w = y_vec * sqrt_w

        try:
            result = np.linalg.lstsq(x_w, y_w, rcond=None)
            slope = float(result[0][0])  # coefficient for factor_score
        except np.linalg.LinAlgError:
            logger.warning("WeightAdapter: LinAlgError in weighted regression")
            return None

        new_weight = 1.0 + slope
        clamped = max(WEIGHT_MIN, min(WEIGHT_MAX, new_weight))
        return clamped
