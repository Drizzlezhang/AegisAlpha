# Tasks: add-m1-calculators

## 任务波次

### Wave 1（基础层，无代码依赖）

#### T01: 创建共享 Pydantic 模型
- 描述: 创建 `backend/aegis/calculators/models.py`，定义 GreeksResult / StopLossResult / WyckoffResult / GexResult / VolumeProfileResult 五个 Pydantic BaseModel
- read_files: `design.md` 数据模型节
- write_files: `backend/aegis/calculators/models.py`
- verify: `cd backend && uv run python -c "from aegis.calculators.models import GreeksResult, StopLossResult, WyckoffResult, GexResult, VolumeProfileResult; print('OK')"`
- status: pending

#### T02: 创建测试 Fixtures
- 描述: 创建 `backend/tests/fixtures/QQQ_options_chain.json`（含 strike/option_type/open_interest/gamma 列）和 `backend/tests/fixtures/QQQ_6m_ohlcv.json`（含 open/high/low/close/volume 列，约 126 行日线数据）
- read_files: `design.md` 算法设计节（GEX/Volume Profile 数据格式）
- write_files: `backend/tests/fixtures/QQQ_options_chain.json`, `backend/tests/fixtures/QQQ_6m_ohlcv.json`
- verify: `cd backend && uv run python -c "import json; d=json.load(open('tests/fixtures/QQQ_options_chain.json')); assert 'strike' in d[0]; d2=json.load(open('tests/fixtures/QQQ_6m_ohlcv.json')); assert 'close' in d2[0]; print('OK')"`
- status: pending

### Wave 2（简单计算模块，依赖 Wave 1）

#### T03: Greeks Calculator + 测试
- 描述: 实现 `compute_greeks()` 和 `compute_implied_volatility()`，含 Black-Scholes 公式与 Newton-Raphson 迭代。测试覆盖 Call/Put 各 3 边界 case (deep ITM/ATM/deep OTM)
- depends_on: [T01]
- read_files: `design.md` Greeks 算法节, `backend/aegis/calculators/models.py`
- write_files: `backend/aegis/calculators/greeks.py`, `backend/tests/calculators/test_greeks.py`
- verify: `cd backend && uv run pytest tests/calculators/test_greeks.py -v`
- status: pending

#### T04: Stop Loss Calculator + 测试
- 描述: 实现 `compute_stop_loss()`，支持 fixed_pct(8%) 和 support_based(支撑位-2%) 两种模式。测试覆盖 fixed_pct 标准/边界 + support_based 标准/无 support_level 抛 ValueError
- depends_on: [T01]
- read_files: `design.md` Stop Loss 算法节, `backend/aegis/calculators/models.py`
- write_files: `backend/aegis/calculators/stop_loss.py`, `backend/tests/calculators/test_stop_loss.py`
- verify: `cd backend && uv run pytest tests/calculators/test_stop_loss.py -v`
- status: pending

### Wave 3（复杂计算模块，依赖 Wave 1 + Wave 2 fixtures）

#### T05: Wyckoff Phase Detector + 测试
- 描述: 实现 `detect_wyckoff_phase()`，基于价格趋势/成交量趋势/波动率/量价背离的启发式算法。测试覆盖 4 相位各 1 case
- depends_on: [T01, T02]
- read_files: `design.md` Wyckoff 算法节, `backend/aegis/calculators/models.py`, `backend/tests/fixtures/QQQ_6m_ohlcv.json`
- write_files: `backend/aegis/calculators/wyckoff.py`, `backend/tests/calculators/test_wyckoff.py`
- verify: `cd backend && uv run pytest tests/calculators/test_wyckoff.py -v`
- status: pending

#### T06: GEX Calculator + 测试
- 描述: 实现 `compute_gex()`，含 GEX 聚合、Gamma Flip 线性插值、Max Pain 计算。测试覆盖 gamma_flip + max_pain 验证
- depends_on: [T01, T02]
- read_files: `design.md` GEX 算法节, `backend/aegis/calculators/models.py`, `backend/tests/fixtures/QQQ_options_chain.json`
- write_files: `backend/aegis/calculators/gex.py`, `backend/tests/calculators/test_gex.py`
- verify: `cd backend && uv run pytest tests/calculators/test_gex.py -v`
- status: pending

#### T07: Volume Profile Calculator + 测试
- 描述: 实现 `compute_volume_profile()`，含成交量分布直方图、POC、Value Area(70%)。测试覆盖 POC + VA 上下界验证
- depends_on: [T01, T02]
- read_files: `design.md` Volume Profile 算法节, `backend/aegis/calculators/models.py`, `backend/tests/fixtures/QQQ_6m_ohlcv.json`
- write_files: `backend/aegis/calculators/volume_profile.py`, `backend/tests/calculators/test_volume_profile.py`
- verify: `cd backend && uv run pytest tests/calculators/test_volume_profile.py -v`
- status: pending

### Wave 4（集成验证，依赖 Wave 2 + Wave 3）

#### T08: 全量测试 + Lint 验证
- 描述: 运行全部 calculators 测试 + ruff + mypy，确保 13 条 AC 全部通过
- depends_on: [T03, T04, T05, T06, T07]
- read_files: 无新增
- write_files: 无（仅验证）
- verify: `cd backend && uv run pytest tests/calculators/ -v && uv run ruff check aegis/calculators/ && uv run mypy aegis/calculators/`
- status: pending

## 风险任务

| 任务 | 风险 | 缓解 |
|------|------|------|
| T03 Greeks | 浮点精度在极端参数下可能不满足 `pytest.approx` | 使用 `rel=1e-4` 宽松容差；参考已知解析解验证 |
| T05 Wyckoff | 启发式算法边界 case 可能误判 | 返回 confidence 字段；低置信度标记 unknown |
| T06 GEX | options_chain 列名依赖，fixture 格式需精确对齐 | 函数内做列名校验；fixture 先于代码创建 |

## 回滚任务
- 删除 `backend/aegis/calculators/greeks.py`, `stop_loss.py`, `wyckoff.py`, `gex.py`, `volume_profile.py`, `models.py`
- 删除 `backend/tests/calculators/` 目录
- 删除 `backend/tests/fixtures/QQQ_options_chain.json`, `QQQ_6m_ohlcv.json`
- 恢复 `backend/aegis/calculators/__init__.py` 到原始状态
