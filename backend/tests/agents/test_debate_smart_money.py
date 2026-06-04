"""Test DebateAgent smart_money_context integration — prompt rendering with smart money data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader


PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"


class TestDebateSmartMoneyContext:
    """Verify smart_money_context placeholder renders correctly in debate prompts."""

    @pytest.fixture
    def env(self) -> Environment:
        return Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))

    def test_bull_prompt_renders_smart_money_context(self, env: Environment) -> None:
        """Bull prompt should render smart_money_context when provided."""
        template = env.get_template("debate_bull.j2")
        rendered = template.render(
            ticker="QQQ",
            factor_scores=[
                {"factor": "momentum", "score": 75, "confidence": 0.8, "rationale": "Strong trend"},
            ],
            smart_money_context="Smart Money: bullish. Institutional flow shows heavy call buying.",
            fund_flow_context="",
            bull_previous=None,
            bear_previous=None,
            judge_previous=None,
        )
        assert "Smart Money: bullish" in rendered
        assert "Institutional flow shows heavy call buying" in rendered

    def test_bull_prompt_renders_empty_smart_money(self, env: Environment) -> None:
        """Bull prompt should render with empty smart_money_context (backward compat)."""
        template = env.get_template("debate_bull.j2")
        rendered = template.render(
            ticker="QQQ",
            factor_scores=[
                {"factor": "momentum", "score": 75, "confidence": 0.8, "rationale": "Strong trend"},
            ],
            smart_money_context="",
            fund_flow_context="",
            bull_previous=None,
            bear_previous=None,
            judge_previous=None,
        )
        assert "QQQ" in rendered
        assert "momentum" in rendered

    def test_bear_prompt_renders_smart_money_context(self, env: Environment) -> None:
        """Bear prompt should render smart_money_context when provided."""
        template = env.get_template("debate_bear.j2")
        rendered = template.render(
            ticker="QQQ",
            factor_scores=[
                {"factor": "valuation", "score": 30, "confidence": 0.7, "rationale": "Overvalued"},
            ],
            smart_money_context="Smart Money: bearish. Heavy put buying detected.",
            fund_flow_context="",
            bull_previous=None,
            bear_previous=None,
            judge_previous=None,
        )
        assert "Smart Money: bearish" in rendered
        assert "Heavy put buying detected" in rendered

    def test_bear_prompt_renders_empty_smart_money(self, env: Environment) -> None:
        """Bear prompt should render with empty smart_money_context (backward compat)."""
        template = env.get_template("debate_bear.j2")
        rendered = template.render(
            ticker="QQQ",
            factor_scores=[
                {"factor": "valuation", "score": 30, "confidence": 0.7, "rationale": "Overvalued"},
            ],
            smart_money_context="",
            fund_flow_context="",
            bull_previous=None,
            bear_previous=None,
            judge_previous=None,
        )
        assert "QQQ" in rendered
        assert "valuation" in rendered

    def test_smart_money_narrative_template(self, env: Environment) -> None:
        """smart_money_narrative.j2 should render with all variables."""
        template = env.get_template("smart_money_narrative.j2")
        rendered = template.render(
            ticker="QQQ",
            smart_money_score=75.5,
            direction_bias="bullish",
            unusual_options=[
                {"type": "call", "strike": 500, "expiration": "2026-07-17", "premium": 250000, "size": 500},
                {"type": "call", "strike": 510, "expiration": "2026-08-21", "premium": 180000, "size": 300},
            ],
            oi_changes={"call_oi_delta": 1500, "put_oi_delta": -800},
        )
        assert "QQQ" in rendered
        assert "75.5" in rendered
        assert "bullish" in rendered
        assert "CALL 500" in rendered
        assert "250000" in rendered
        assert "1500" in rendered
        assert "-800" in rendered
