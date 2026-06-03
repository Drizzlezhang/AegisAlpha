# Branch D — Trend/Phase + Level + Options S1 — Plan Prompt

> **分支**: `feat/m1-analyst-agents`
> **估时**: 5 天
> **依赖**: Sprint-0 完成
> **子 Agent**: `m1-analyst`
> **前置阅读**: `AGENTS.md` + `docs/aegis-2.0-tech-arch.md` Section 4.2-4.4

---

## 目标

实现 3 个并行分析 Agent:Trend/Phase Analyst、Level Analyst、Options Strategist Step 1(纯计算筛合约)。

## 范围

### Trend/Phase Analyst

- 输入:`state.market_data[ticker]` OHLCV
- 调用:`calculators.wyckoff.detect_wyckoff_phase()` + 自研 MA/RSI/MACD trend scoring
- 输出:写入 `state.analyst_outputs[ticker]["trend_phase"]`
- LLM:无(纯计算)
- manifest: `pipeline_mode="both"`, `llm_dependency=False`, `parallel_group="signal_analysts"`

### Level Analyst

- 输入: OHLCV + GEX(如有)
- 调用:`calculators.gex` + `calculators.volume_profile` + 自研 support/resistance
- 输出:`state.analyst_outputs[ticker]["levels"]`(含 support_levels / resistance_levels)
- LLM:无
- manifest: `pipeline_mode="both"`, `llm_dependency=False`, `parallel_group="signal_analysts"`
- **v1.2 要点**: `support_levels` 将被 stop_loss(support_based) 消费,数据契约要稳定

### Options Strategist Step 1

- 输入: OHLCV + VIX + 期权链(M1 用 mock)
- 调用:`calculators.greeks` + 基础筛选逻辑(DTE / Delta / OI / Spread)
- 输出:`state.options_step1[ticker]`(候选合约列表)
- LLM:无
- manifest: `pipeline_mode="full"`, `llm_dependency=False`, `parallel_group="signal_analysts"`

### 共同要求

- 所有 Agent 使用 `self.write_extension()` 写自定义中间数据(如 `wyckoff_raw_output`)
- 失败不外抛,写 `state.error_flags`
- Prompt 模板:D 分支无 LLM 调用,不需要 prompt 文件

## 文件清单

```
backend/aegis/agents/
├── trend_phase_analyst_agent.py
├── level_analyst_agent.py
└── options_strategist_s1_agent.py

backend/tests/agents/
├── test_trend_phase_analyst.py    # bullish / bearish / sideways scenario
├── test_level_analyst.py          # support/resistance 识别 + GEX 集成
└── test_options_strategist_s1.py  # 筛选逻辑 + 空链 fallback

backend/tests/fixtures/
├── QQQ_trend_bullish.json
├── QQQ_trend_bearish.json
├── QQQ_options_chain_mock.json
└── QQQ_gex_data.json
```

## 验收

- [ ] 3 个 Agent 均 `llm_dependency=False` + `parallel_group="signal_analysts"`
- [ ] Level Analyst 输出含 `support_levels: list[float]` 可被 stop_loss 消费
- [ ] Options S1 输出结构化候选合约列表(Pydantic model)
- [ ] 所有自定义中间数据走 `write_extension`,不直接挂 state 新字段
- [ ] pytest 全绿
