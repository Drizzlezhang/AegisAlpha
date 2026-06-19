"""ObservationPeriodManager — 30-day observation period lifecycle.

During the observation period (first 30 days after the earliest ThesisCard),
weights are NOT updated. After the period ends, historical data is backfilled.
"""

from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.orm import Session

from aegis.memory.thesis_store import ThesisStore
from aegis.memory.weight_adapter import WeightAdapter
from aegis.memory.weight_store import WeightStore
from aegis.utils.settings import settings

OBSERVATION_PERIOD_DAYS: int = settings.OBSERVATION_PERIOD_DAYS  # 30


class ObservationPeriodManager:
    """Manages the 30-day observation period lifecycle."""

    def __init__(
        self,
        weight_store: WeightStore,
        thesis_store: ThesisStore,
        weight_adapter: WeightAdapter,
    ) -> None:
        self._weight_store = weight_store
        self._thesis_store = thesis_store
        self._weight_adapter = weight_adapter

    def is_in_observation_period(self, session: Session) -> bool:
        """Check if we are still within the observation period.

        Returns True if:
          - No ThesisCard exists yet (treat as observation period)
          - The earliest ThesisCard is less than OBSERVATION_PERIOD_DAYS old
        """
        first_card_date = self._thesis_store.get_first_card_date(session)
        if first_card_date is None:
            logger.debug("ObservationPeriod: no cards yet, in observation period")
            return True

        # Ensure timezone-aware comparison
        if first_card_date.tzinfo is None:
            first_card_date = first_card_date.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        age_days = (now - first_card_date).total_seconds() / 86400.0
        in_period = age_days < OBSERVATION_PERIOD_DAYS

        if in_period:
            remaining = OBSERVATION_PERIOD_DAYS - int(age_days)
            logger.debug(
                f"ObservationPeriod: {remaining}d remaining (first card {age_days:.1f}d ago)"
            )

        return in_period

    def check_and_transition(self, session: Session) -> bool:
        """Check if observation period just ended and trigger backfill if so.

        Returns:
            True if a transition occurred (backfill was triggered).
        """
        was_active = self._weight_store.is_observation_period_active(session)
        is_in_period = self.is_in_observation_period(session)

        if was_active and not is_in_period:
            logger.info("ObservationPeriod: period ended, triggering backfill")
            self._backfill_after_observation(session)
            return True

        if was_active:
            logger.debug("ObservationPeriod: still active, no transition")
        else:
            logger.debug("ObservationPeriod: already transitioned")

        return False

    def _backfill_after_observation(self, session: Session) -> dict[str, float]:
        """Run weight update using all historical data after observation period ends.

        Also marks all factors as observation_period_active=False.
        """
        logger.info("ObservationPeriod: backfilling weights from historical data")
        updated = self._weight_adapter.update_weights(session)

        # Mark observation period as ended for all factors
        from sqlalchemy import update

        from aegis.models.factor_weight import FactorWeight

        session.execute(update(FactorWeight).values(observation_period_active=False))
        session.commit()
        logger.info("ObservationPeriod: all factors marked as observation_period_active=False")

        return updated
