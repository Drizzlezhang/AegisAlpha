# M1 Fix Plan — Post-Review Hotfix

> **分支**: `fix/m1-post-review`
> **基于**: `develop` (commit b764343)
> **优先级**: P1（合入 main 前必须完成）
> **估时**: 0.5 天
> **前置**: M1 全分支 code review 通过

---

## 1. Review 总结

**236 tests PASSED / ruff PASSED / 所有 7 个分支功能完整**

但存在以下需要修复的问题，按严重程度排列：

---

## 2. 必修项（Must Fix）

### 2.1 `pyproject.toml` Python 版本约束过严

**文件**: `backend/pyproject.toml` line 5
**现状**: `requires-python = ">=3.11,<3.13"`
**问题**: Python 3.13 已正式发布且稳定，所有依赖均兼容。当前约束导致 `uv sync` / `pip install -e .` 在 3.13 环境直接报错。
**修复**:

```toml
requires-python = ">=3.11,<3.14"
```

### 2.2 yFinance 适配器缺少 options chain + fundamentals 方法

**文件**: `backend/aegis/tools/market/yfinance_adapter.py`
**现状**: 仅支持 `history` / `quote` / `earnings_date` 三种 method
**Plan 要求**: yfinance 应覆盖 OHLCV + **options chain** + **fundamentals**
**影响**: Branch D 的 OptionsStrategistS1 需要 options chain 数据；无 fundamentals 数据源会影响后续分析质量
**修复**:

```python
# 新增两个 method 分支:

# 1. options chain
elif method == "options_chain":
    ticker_obj = yf.Ticker(ticker)
    expirations = ticker_obj.options  # list[str]
    chains = []
    for exp in expirations[:max_expirations]:  # 取前 N 个到期日
        chain = ticker_obj.option_chain(exp)
        calls = chain.calls.to_dict("records")
        puts = chain.puts.to_dict("records")
        chains.append({"expiration": exp, "calls": calls, "puts": puts})
    return ToolResult(success=True, data={"ticker": ticker, "chains": chains}, source="yfinance")

# 2. fundamentals
elif method == "fundamentals":
    ticker_obj = yf.Ticker(ticker)
    info = ticker_obj.info
    return ToolResult(success=True, data={
        "ticker": ticker,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "beta": info.get("beta"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }, source="yfinance")
```

**测试补充**:

```python
# tests/tools/test_yfinance.py 新增:
def test_fetch_options_chain_success(self): ...
def test_fetch_options_chain_empty(self): ...
def test_fetch_fundamentals_success(self): ...
```

**tools.yaml 更新**: yfinance 的 tags 添加 `options_chain` 和 `fundamentals`

### 2.3 ToolRegistry 缺少 `register()` 方法

**文件**: `backend/aegis/tools/registry.py`
**现状**: 所有 Tool 注册通过 `load_from_yaml()` 内部完成，无公开 API 动态注册
**影响**: 后续分支（M2+）需要动态注册 Tool（如测试注入、运行时加载插件）
**修复**:

```python
def register(self, name: str, tool: BaseTool, config: dict[str, Any] | None = None) -> None:
    """Programmatically register a tool (for testing / dynamic plugins)."""
    proxy = ToolProxy(
        name=name,
        tool=tool,
        tags=config.get("tags", []) if config else [],
        rate_limiter=...,
        circuit_breaker=...,
    )
    self._tools[name] = proxy
```

### 2.4 Full Pipeline 中 PortfolioOrchestrator 位置错误

**文件**: `backend/aegis/pipeline/graph_full.py`
**现状**: 拓扑为 `DataHarvester → TrendPhase → Level → OptionsS1 → Debate → OptionsS2 → ResearchManager → **PortfolioOrchestrator** → RiskGate → END`
**Plan 要求**: PortfolioOrchestrator 应在 DataHarvester 之后立即执行（它负责分流 tickers 和 entry_mode，其他 Agent 依赖这些数据）
**正确拓扑**:

```
DataHarvester → PortfolioOrchestrator → TrendPhase → Level → OptionsS1
→ Debate → OptionsS2 → ResearchManager → RiskGate → END
```

**修复**: 调整 `graph_full.py` edge 顺序

### 2.5 Lightweight Pipeline 缺少 PortfolioOrchestrator 节点

**文件**: `backend/aegis/pipeline/graph_lightweight.py`
**现状**: `DataHarvester → TrendPhase → Level → health_check → END`
**Plan 要求**: `DataHarvester → **PortfolioOrchestrator** → health_check → END`（TrendPhase 和 Level 是可选的，但 Portfolio 是必要的——它提供 positions 和 tickers_holdings_passive）
**修复**: 在 DataHarvester 之后插入 PortfolioOrchestrator 节点

### 2.6 `datetime.utcnow()` 废弃警告（115 处）

**文件**: `backend/aegis/pipeline/state.py` line 中 `BlockedRecommendation.blocked_at`
**现状**: pytest 产生 115 个 DeprecationWarning（`datetime.datetime.utcnow() is deprecated`）
**原因**: `default_factory=datetime.utcnow` 在 Python 3.12+ 触发警告
**修复**:

```python
from datetime import datetime, timezone

class BlockedRecommendation(BaseModel):
    blocked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 3. 建议修复项（Should Fix）

### 3.1 Calculators 重复代码：`trend.py` / `levels.py` 与正式模块

**文件**: `backend/aegis/calculators/trend.py` 和 `backend/aegis/calculators/levels.py`
**问题**:
- `trend.py` 含 `detect_wyckoff_phase()` 返回 raw dict，与 `wyckoff.py` 的 Pydantic 版本重复
- `levels.py` 含 `compute_volume_profile()` 返回 raw dict，与 `volume_profile.py` 重复
- 这两个文件没有测试
**修复方案**: 
- 删除 `trend.py` 中的 `detect_wyckoff_phase`，改为 `from aegis.calculators.wyckoff import detect_wyckoff_phase`
- 删除 `levels.py` 中的 `compute_volume_profile`，改为 `from aegis.calculators.volume_profile import compute_volume_profile`
- 保留 `trend.py` 中的 `compute_trend_score`（独有功能）和 `levels.py` 中的 `find_support_resistance`（独有功能）
- 为保留的函数补写单测

### 3.2 pyproject.toml 与 ruff.toml 配置重复

**文件**: `backend/pyproject.toml` [tool.ruff] + `backend/ruff.toml`
**修复**: 删除 `ruff.toml`，保留 `pyproject.toml` 中的配置（集中管理）

### 3.3 Makefile typecheck 路径错误

**文件**: `Makefile`
**现状**: `cd backend && mypy backend/aegis`（双重嵌套路径）
**修复**: `cd backend && mypy aegis`

### 3.4 `backend/aegis/__init__.py` 添加版本号

```python
__version__ = "0.1.0"
```

### 3.5 `alembic.ini` 硬编码数据库 URL

**修复**: 改为占位符 `sqlalchemy.url = driver://user:pass@localhost/dbname`

### 3.6 补充 `__init__.py` 文件

以下目录缺少 `__init__.py`：
- `backend/tests/foundation/`
- `backend/tests/calculators/`

### 3.7 stop_loss 缺少 `entry_price=0` 边界测试

**文件**: `backend/tests/calculators/test_stop_loss.py`
**修复**: 添加测试用例验证 `entry_price=0` 时的行为

### 3.8 Fixture JSON 文件未被测试引用

**文件**: `backend/tests/fixtures/` 下有 14 个 JSON 文件，但大部分测试使用 inline mock
**修复**: 重构测试加载 fixture 文件而非 inline 构造（可选，不阻塞）

---

## 4. 非阻塞已知限制（M2 跟进）

| 项目 | 说明 | 跟进时间 |
|---|---|---|
| Full Pipeline 全序执行 | 代码注释已标注 "M1: parallel requires Annotated reducers" | M2 |
| Telegram 不在 Graph 内 | 通知在 runner 层外部发送，不是 graph node | 可接受 |
| CLI schedule 命名差异 | `schedule-start` vs spec 的 `schedule` | 低优 |
| Lightweight 含 TrendPhase + Level | 超出 spec 但功能合理（passive 也需要信号） | 可接受 |

---

## 5. 文件变更清单

| 文件 | 操作 |
|---|---|
| `backend/pyproject.toml` | 修改 requires-python + 删除 [tool.ruff] |
| `backend/ruff.toml` | 删除 |
| `backend/aegis/tools/market/yfinance_adapter.py` | 新增 options_chain + fundamentals |
| `backend/aegis/tools/registry.py` | 新增 register() 方法 |
| `backend/aegis/pipeline/graph_full.py` | 调整 PortfolioOrchestrator 位置 |
| `backend/aegis/pipeline/graph_lightweight.py` | 插入 PortfolioOrchestrator 节点 |
| `backend/aegis/pipeline/state.py` | 修复 utcnow 废弃 |
| `backend/aegis/calculators/trend.py` | 删除重复 wyckoff，补 import |
| `backend/aegis/calculators/levels.py` | 删除重复 volume_profile，补 import |
| `backend/aegis/__init__.py` | 添加 __version__ |
| `backend/alembic.ini` | URL 改占位符 |
| `Makefile` | 修复 typecheck 路径 |
| `backend/config/tools.yaml` | yfinance tags 添加 options_chain + fundamentals |
| `backend/tests/tools/test_yfinance.py` | 新增 3 个测试 |
| `backend/tests/calculators/test_stop_loss.py` | 新增 entry=0 边界测试 |
| `backend/tests/calculators/test_trend.py` | 新建 |
| `backend/tests/calculators/test_levels.py` | 新建 |
| `backend/tests/foundation/__init__.py` | 新建 |
| `backend/tests/calculators/__init__.py` | 新建（如不存在） |

---

## 6. 验收清单

- [ ] `pip install -e ".[dev]"` 在 Python 3.13 上通过
- [ ] `ruff check .` 通过
- [ ] `pytest tests/` 全绿（含新增测试），0 DeprecationWarning
- [ ] yFinance `options_chain` + `fundamentals` 方法可用
- [ ] Full Pipeline 拓扑：DataHarvester → Portfolio → TrendPhase → Level → ...
- [ ] Lightweight Pipeline 含 PortfolioOrchestrator 节点
- [ ] `calculators/trend.py` 和 `levels.py` 无重复函数
- [ ] PR 描述："M1 post-review fixes — Python 3.13 兼容 + pipeline 拓扑修正 + yfinance 补全"

---

## 7. 不允许做的事

- 不新增 Agent
- 不修改契约层（state.py 的 utcnow 修复除外）
- 不改 Agent 业务逻辑
- 不改测试预期结果（只补测试）
