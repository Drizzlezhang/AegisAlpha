# Requirements: add-m1-calculators

## 功能需求

### FR-1: Greeks Calculator (Black-Scholes + Implied Volatility)
- **Given**: 期权类型(call/put)、标的价格 S、行权价 K、到期时间 T、无风险利率 r、波动率 sigma、股息率 q
- **When**: 调用 `compute_greeks(option_type, S, K, T, r, sigma, q=0)`
- **Then**: 返回 `GreeksResult`(Pydantic BaseModel)，包含 delta/gamma/theta/vega/rho 五项 Greeks 值，以及 `implied_volatility` 牛顿法反推结果

### FR-2: Stop Loss Calculator
- **Given**: 入场价 `entry_price`、止损模式 `mode`、可选支撑位 `support_level`
- **When**: 调用 `compute_stop_loss(entry_price, mode, support_level=None)`
- **Then**: 返回 `StopLossResult`(Pydantic BaseModel)，包含 `stop_price` 和 `stop_pct`
  - `mode="fixed_pct"`: 止损价 = entry_price × (1 - 8%)
  - `mode="support_based"`: 止损价 = support_level × (1 - 2%)，若 `support_level` 为 None 则抛 `ValueError`

### FR-3: Wyckoff Phase Detector
- **Given**: OHLCV DataFrame(含 open/high/low/close/volume 列)
- **When**: 调用 `detect_wyckoff_phase(ohlcv_df)`
- **Then**: 返回 `WyckoffResult`(Pydantic BaseModel)，包含当前相位(Accumulation/Distribution/Markup/Markdown)及置信度

### FR-4: GEX Calculator
- **Given**: options_chain DataFrame(含 strike/option_type/open_interest/gamma 列) + 现货价格 spot
- **When**: 调用 `compute_gex(options_chain_df, spot)`
- **Then**: 返回 `GexResult`(Pydantic BaseModel)，包含总 GEX、Gamma Flip 点位、Max Pain 点位、按 strike 聚合的 GEX 分布

### FR-5: Volume Profile Calculator
- **Given**: OHLCV DataFrame(含 high/low/close/volume 列) + bins 参数
- **When**: 调用 `compute_volume_profile(ohlcv_df, bins=50)`
- **Then**: 返回 `VolumeProfileResult`(Pydantic BaseModel)，包含 POC(Point of Control)、Value Area High/Low、成交量分布直方图

## 验收标准与验证方式

| AC | 验证方式 |
|----|---------|
| AC-1: 所有函数纯 sync，无 import httpx/asyncio/LLMClient | `grep -r "import httpx\|import asyncio\|LLMClient" backend/aegis/calculators/` 返回空 |
| AC-2: 返回值全部为 Pydantic BaseModel | 每个计算函数返回类型注解检查 + `isinstance(result, BaseModel)` 单测断言 |
| AC-3: `stop_loss.py` 支持 `mode="support_based"` | 单测 `test_stop_loss_support_based_standard` 验证 |
| AC-4: `stop_loss.py` 无 support_level 时抛 ValueError | 单测 `test_stop_loss_support_based_missing_level_raises` 验证 |
| AC-5: Greeks deep ITM/ATM/deep OTM Call 各 1 case | `test_greeks.py` 中 3 个 call case，`pytest.approx` 浮点比较 |
| AC-6: Greeks deep ITM/ATM/deep OTM Put 各 1 case | `test_greeks.py` 中 3 个 put case，`pytest.approx` 浮点比较 |
| AC-7: Stop Loss fixed_pct 标准 + 边界(entry=0) | `test_stop_loss.py` 中 2 个 case |
| AC-8: Wyckoff 4 相位各 1 case | `test_wyckoff.py` 中 4 个 fixture-based case |
| AC-9: GEX gamma_flip + max_pain 计算 | `test_gex.py` 中验证 gamma_flip 点位与 max_pain 点位 |
| AC-10: Volume Profile POC + Value Area | `test_volume_profile.py` 中验证 POC 与 VA 上下界 |
| AC-11: pytest 全绿 | `cd backend && uv run pytest tests/calculators/ -v` 全部通过 |
| AC-12: ruff + mypy 通过 | `cd backend && uv run ruff check aegis/calculators/ && uv run mypy aegis/calculators/` 零错误 |
| AC-13: 所有函数有完整 type hints + Google-style docstring | mypy strict 模式 + 人工 review docstring |

## 用户故事
- As a Risk Gate Agent developer, I want deterministic Greeks and Stop Loss calculations so that I can enforce risk rules without LLM dependency.
- As an Options Strategist Agent developer, I want GEX and Wyckoff phase detection so that I can incorporate gamma exposure and market structure into entry decisions.
- As a Pipeline developer, I want all calculator results as typed Pydantic models so that downstream agents can rely on schema-validated outputs.

## 非功能需求

### NFR-1: 性能
- 单次 Greeks 计算 ≤ 1ms
- 单次 Wyckoff 相位检测(6 个月日线数据) ≤ 100ms
- 单次 GEX 聚合(全期权链) ≤ 500ms

### NFR-2: 代码质量
- 所有公开函数必须有完整 type hints(参数 + 返回值)
- 所有公开函数必须有 Google-style docstring
- 契约层文件首行标注 `"""Frozen at M1. Changes require owner review."""`

### NFR-3: 无副作用
- 所有函数纯 sync，不发起网络请求
- 不读写文件系统
- 不依赖全局可变状态

## 边界场景

### Edge-1: Greeks 极端参数
- T → 0(到期日): theta 应趋近于极大值，不应除零
- sigma → 0: delta 应趋近于阶跃函数(ITM→1, OTM→0)
- S >> K (deep ITM call): delta → 1, gamma → 0

### Edge-2: Stop Loss 边界
- entry_price = 0: 应抛 ValueError 或返回合理错误
- support_level > entry_price(support_based 模式): 止损价可能高于入场价，应明确行为

### Edge-3: Wyckoff 数据不足
- ohlcv_df 行数 < 20: 应返回低置信度结果或抛明确异常

### Edge-4: GEX 空期权链
- options_chain_df 为空: 应返回零 GEX 结果而非崩溃

### Edge-5: Volume Profile 单日数据
- ohlcv_df 仅 1 行: POC = 当日收盘价，VA = 当日高低点

## 回滚计划
- calculators 模块为纯增量，不修改现有代码，回滚只需删除 `backend/aegis/calculators/` 下新增文件及对应测试

## 数据/权限影响
- 无数据库变更
- 无权限变更
- 新增 2 个测试 fixture 文件(QQQ_options_chain.json, QQQ_6m_ohlcv.json)
