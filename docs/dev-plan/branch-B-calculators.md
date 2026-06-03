# Branch B — Calculators — Plan Prompt

> **分支**: `feat/m1-calculators`
> **估时**: 4 天
> **依赖**: Sprint-0 完成
> **子 Agent**: `m1-calculators`
> **前置阅读**: `AGENTS.md` 第 5 节 + `docs/aegis-2.0-prd.md` Section 8 + `docs/aegis-2.0-tech-arch.md` Section 4(Options/Risk Gate)

---

## 目标

实现所有 M1 需要的纯计算模块(无 LLM、无 IO、sync 函数),为 Agents 提供确定性数值计算。

## 范围

### In Scope

1. **Greeks Calculator** — Black-Scholes + 隐含波动率牛顿法
2. **Stop Loss Calculator** — 固定百分比(8%) + 支撑位动态止损(support_based 模式,M1 实现框架,M2 集成真实支撑位)
3. **Wyckoff Phase Detector** — 基于量价关系识别 Accumulation / Distribution / Markup / Markdown
4. **GEX Calculator** — Gamma Exposure 聚合(by strike) + Gamma Flip / Max Pain
5. **Volume Profile** — 成交量分布 + POC(Point of Control) + Value Area

### v1.2 新增要求

- `stop_loss.py` 必须支持 `mode: Literal["fixed_pct", "support_based"]` 参数
  - `fixed_pct`: 传统固定 8% 止损
  - `support_based`: 接受 `support_level: float` 参数,止损设在支撑位下方 2%(M1 先硬编码 2%,M2 可配置化)
- 所有 calculator 函数签名必须有完整 type hints + Google-style docstring
- 计算结果用 Pydantic BaseModel 包装(不返回裸 dict)

## 文件清单

```
backend/aegis/calculators/
├── __init__.py
├── greeks.py            # compute_greeks(option_type, S, K, T, r, sigma, q=0) → GreeksResult
├── stop_loss.py         # compute_stop_loss(entry_price, mode, support_level=None) → StopLossResult
├── wyckoff.py           # detect_wyckoff_phase(ohlcv_df) → WyckoffResult
├── gex.py               # compute_gex(options_chain_df, spot) → GexResult
├── volume_profile.py    # compute_volume_profile(ohlcv_df, bins=50) → VolumeProfileResult
└── models.py            # 所有结果 Pydantic model (GreeksResult / StopLossResult / ...)

backend/tests/calculators/
├── test_greeks.py              # Call/Put 各 3 边界(deep ITM/ATM/deep OTM)
├── test_stop_loss.py           # fixed_pct + support_based + edge cases
├── test_wyckoff.py             # 4 phase fixture data
├── test_gex.py                 # gamma_flip / max_pain
└── test_volume_profile.py      # POC / value_area

backend/tests/fixtures/
├── QQQ_options_chain.json      # GEX 测试用
└── QQQ_6m_ohlcv.json           # Wyckoff + Volume Profile 测试用
```

## 必测项(AGENTS.md 7.2 强制)

| 模块 | Case |
|---|---|
| greeks.py | deep ITM call / ATM call / deep OTM call / deep ITM put / ATM put / deep OTM put |
| stop_loss.py | fixed_pct 标准 / fixed_pct 边界(entry=0) / support_based 标准 / support_based 无 support_level 抛 ValueError |

## 验收

- [ ] 所有函数纯 sync,无 import httpx / asyncio / LLMClient
- [ ] 返回值全部为 Pydantic BaseModel(不是裸 dict/tuple)
- [ ] `stop_loss.py` 支持 `mode="support_based"` 参数
- [ ] pytest 全绿 + `pytest.approx` 浮点比较
- [ ] ruff + mypy 通过
