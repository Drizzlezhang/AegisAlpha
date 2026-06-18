"""Tests for KOLSource and KOLCall SQLAlchemy models."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aegis.models.base import Base
from aegis.models.kol import KOLCall, KOLSource


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class TestKOLSource:
    def test_create_kol_source(self, session: Session):
        """Should create and persist a KOLSource record."""
        source = KOLSource(
            name="Test Analyst",
            platform="stocktwits",
            handle="@testanalyst",
            reliability_score=0.75,
            total_calls=100,
            successful_calls=60,
        )
        session.add(source)
        session.commit()

        result = session.execute(select(KOLSource)).scalar_one()
        assert result.name == "Test Analyst"
        assert result.platform == "stocktwits"
        assert result.handle == "@testanalyst"
        assert result.reliability_score == 0.75
        assert result.total_calls == 100
        assert result.successful_calls == 60
        assert result.enabled is True

    def test_kol_source_defaults(self, session: Session):
        """Default values should be set correctly."""
        source = KOLSource(name="New", platform="x", handle="@new")
        session.add(source)
        session.commit()

        result = session.execute(select(KOLSource)).scalar_one()
        assert result.reliability_score == 0.5
        assert result.total_calls == 0
        assert result.successful_calls == 0
        assert result.enabled is True

    def test_kol_source_disabled(self, session: Session):
        """Should support disabling a source."""
        source = KOLSource(name="Disabled", platform="reddit", handle="@disabled", enabled=False)
        session.add(source)
        session.commit()

        result = session.execute(select(KOLSource)).scalar_one()
        assert result.enabled is False


class TestKOLCall:
    def test_create_kol_call(self, session: Session):
        """Should create and persist a KOLCall record."""
        call = KOLCall(
            kol_source_id=1,
            ticker="QQQ",
            direction="bullish",
            call_date=datetime(2026, 6, 15, tzinfo=UTC),
            call_price=480.0,
            source_url="https://stocktwits.com/test",
            content_snippet="QQQ looking strong",
        )
        session.add(call)
        session.commit()

        result = session.execute(select(KOLCall)).scalar_one()
        assert result.kol_source_id == 1
        assert result.ticker == "QQQ"
        assert result.direction == "bullish"
        assert result.call_price == 480.0
        assert result.attribution_status == "pending"
        assert result.source_url == "https://stocktwits.com/test"
        assert result.content_snippet == "QQQ looking strong"

    def test_kol_call_attribution(self, session: Session):
        """Should support updating attribution status and PnL."""
        call = KOLCall(
            kol_source_id=1,
            ticker="SPY",
            direction="bearish",
            call_date=datetime(2026, 5, 1, tzinfo=UTC),
            call_price=500.0,
        )
        session.add(call)
        session.commit()

        call.attribution_status = "validated"
        call.pnl_30d = -2.5
        call.pnl_60d = -5.0
        session.commit()

        result = session.execute(select(KOLCall)).scalar_one()
        assert result.attribution_status == "validated"
        assert result.pnl_30d == -2.5
        assert result.pnl_60d == -5.0

    def test_kol_call_query_by_ticker(self, session: Session):
        """Should filter by ticker."""
        session.add_all([
            KOLCall(
                kol_source_id=1, ticker="QQQ", direction="bullish",
                call_date=datetime(2026, 6, 1, tzinfo=UTC), call_price=480.0,
            ),
            KOLCall(
                kol_source_id=1, ticker="SPY", direction="bearish",
                call_date=datetime(2026, 6, 1, tzinfo=UTC), call_price=500.0,
            ),
        ])
        session.commit()

        results = session.execute(
            select(KOLCall).where(KOLCall.ticker == "QQQ")
        ).all()
        assert len(results) == 1
