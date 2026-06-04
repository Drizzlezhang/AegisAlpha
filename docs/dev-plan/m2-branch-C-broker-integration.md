# M2 Branch C — 多账户券商对接

> **分支**: `feat/m2-broker-integration`
> **估时**: 5 天
> **优先级**: P0
> **子 Agent**: `m2-broker`
> **前置**: M2 Sprint-0 完成
> **前置阅读**: `AGENTS.md` v1.2 + `docs/tech-arch.md` 第 4.1 节 + `docs/prd.md` 第 4.1 节

---

## 1. 目标

替换 `mock_portfolio.json` 为真实券商 API 实时持仓拉取。对接富途 (Futu OpenD)、长桥 (Longbridge SDK)、老虎 (Tiger Open API) 三家券商，统一为 `BrokerAdapter` 接口，让 PortfolioOrchestrator 从真实账户获取持仓、Greeks、Delta Dollars。

---

## 2. 交付物清单

### 2.1 BrokerAdapter 基类

**文件**: `backend/aegis/tools/brokers/base.py`

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class BrokerPosition(BaseModel):
    account: str
    ticker: str
    pos_type: str           # "stock" / "option"
    quantity: int
    avg_cost: float
    current_price: float | None = None
    strike: float | None = None
    expiry: str | None = None      # YYYY-MM-DD
    option_type: str | None = None # "call" / "put"
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    iv: float | None = None
    delta_dollars: float | None = None
    unrealized_pnl: float | None = None
    entry_mode: str | None = None  # passive / active_left / active_right / cc / sell_put
    grade: str | None = None       # passive / active

class BrokerAdapter(ABC):
    """统一券商接口"""

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """获取所有持仓"""

    @abstractmethod
    async def get_account_summary(self) -> dict:
        """获取账户总览：NAV / cash / margin"""

    @abstractmethod
    async def get_options_chain(self, ticker: str, expiry: str | None = None) -> list[dict]:
        """获取期权链（可选，作为 yFinance options_chain 的 fallback）"""

    @abstractmethod
    async def get_oi_data(self, ticker: str) -> dict:
        """获取 Open Interest 数据（可选，给 Smart Money Agent 使用）"""
```

### 2.2 富途适配器 (Futu OpenD)

**文件**: `backend/aegis/tools/brokers/futu_adapter.py`

**依赖**: `futu-api`（pip 安装）
**前置**: 本地运行 Futu OpenD 客户端

```python
class FutuAdapter(BrokerAdapter):
    """
    通过 futu-api SDK 连接 OpenD:
    - FUTU_HOST: localhost (默认)
    - FUTU_PORT: 11111 (默认)
    - FUTU_TRADE_ENV: SIMULATE / REAL（settings 控制）
    """
    
    async def get_positions(self) -> list[BrokerPosition]:
        # 使用 OpenTradeContext
        # trd_ctx.position_list_query() → 解析为 BrokerPosition 列表
        # 期权持仓需要额外调用 option_chain 获取 Greeks
        ...

    async def get_account_summary(self) -> dict:
        # trd_ctx.accinfo_query() → NAV / cash / margin
        ...

    async def get_options_chain(self, ticker: str, expiry: str | None = None) -> list[dict]:
        # qot_ctx.get_option_chain() → 标准化格式
        ...

    async def get_oi_data(self, ticker: str) -> dict:
        # 从期权链数据中提取 OI 变化
        ...
```

**注意事项**:
- `futu-api` 在 macOS ARM 上兼容性良好
- 模拟环境 `SIMULATE` 不需要真实账户，适合开发测试
- OpenD 需要本地运行，连接失败时 fallback 到 mock

### 2.3 长桥适配器 (Longbridge)

**文件**: `backend/aegis/tools/brokers/longbridge_adapter.py`

**依赖**: `longbridge`（Longbridge OpenAPI SDK）

```python
class LongbridgeAdapter(BrokerAdapter):
    """
    长桥 OpenAPI:
    - LONGBRIDGE_APP_KEY
    - LONGBRIDGE_APP_SECRET
    - LONGBRIDGE_ACCESS_TOKEN
    - LONGBRIDGE_REGION: us (settings 控制)
    """

    async def get_positions(self) -> list[BrokerPosition]:
        # TradeContext.stock_positions() → BrokerPosition
        # 期权: OptionPositionChannel 或手动遍历
        ...

    async def get_account_summary(self) -> dict:
        # TradeContext.account_balance()
        ...
```

### 2.4 老虎适配器 (Tiger)

**文件**: `backend/aegis/tools/brokers/tiger_adapter.py`

**依赖**: `tigeropen`（Tiger Open API SDK）

```python
class TigerAdapter(BrokerAdapter):
    """
    老虎 Open API:
    - TIGER_ID
    - TIGER_ACCOUNT
    - TIGER_PRIVATE_KEY_PATH
    """

    async def get_positions(self) -> list[BrokerPosition]:
        # TradeClient.get_positions() → BrokerPosition
        ...

    async def get_account_summary(self) -> dict:
        # TradeClient.get_assets()
        ...
```

### 2.5 BrokerManager（多账户聚合）

**文件**: `backend/aegis/tools/brokers/manager.py`

```python
class BrokerManager:
    """
    管理多个券商适配器,聚合持仓数据。
    """

    def __init__(self, adapters: list[BrokerAdapter]):
        self._adapters = adapters

    async def get_all_positions(self) -> list[BrokerPosition]:
        """并行查询所有券商,合并持仓列表"""
        results = await asyncio.gather(
            *[a.get_positions() for a in self._adapters],
            return_exceptions=True,
        )
        positions = []
        for adapter, result in zip(self._adapters, results):
            if isinstance(result, Exception):
                logger.warning(f"Broker {adapter.__class__.__name__} failed: {result}")
                continue
            positions.extend(result)
        return positions

    async def get_merged_summary(self) -> dict:
        """合并所有账户的 NAV / cash"""
        ...

    def aggregate_delta_dollars(self, positions: list[BrokerPosition]) -> float:
        """计算总 Delta Dollars"""
        return sum(p.delta_dollars or 0 for p in positions)
```

### 2.6 PortfolioOrchestrator 对接

**修改**: `backend/aegis/agents/portfolio_orchestrator_agent.py`

```python
# 现有逻辑: 从 mock_portfolio.json 读取持仓
# 修改为:
# 1. 优先从 BrokerManager 获取真实持仓
# 2. BrokerManager 失败时 fallback 到 mock_portfolio.json
# 3. 真实持仓写入 state.broker_positions

async def run(self, state: PipelineState) -> PipelineState:
    try:
        positions = await self.broker_manager.get_all_positions()
        summary = await self.broker_manager.get_merged_summary()
    except Exception:
        logger.warning("All brokers failed, falling back to mock portfolio")
        positions, summary = self._load_mock_portfolio()
    
    # 写入 state.broker_positions（按 account 分组）
    for pos in positions:
        state.broker_positions.setdefault(pos.account, []).append(pos.model_dump())
    
    # 构建 PortfolioSnapshot（原有逻辑）
    snapshot = self._build_snapshot(positions, summary)
    
    # v1.2: 计算 health_scores
    for ticker in state.tickers_holdings_active:
        snapshot.health_scores[ticker] = self._compute_health(state, ticker)
    
    state.portfolio = snapshot
    return state
```

### 2.7 positions.db 写入

**修改**: 在 Pipeline 完成后将 broker positions 同步到 SQLite `positions` 表（按 `docs/tech-arch.md` 的 schema）。

```python
# backend/aegis/storage/position_store.py
class PositionStore:
    async def upsert_positions(self, positions: list[BrokerPosition]) -> None:
        """批量 upsert 持仓快照到 positions.db"""
        ...
```

### 2.8 Settings 更新

Sprint-0 已在 `.env.example` 注册了以下 key，本分支需要在 `settings.py` 中添加对应 Pydantic 字段：

```python
# Futu
FUTU_HOST: str = "localhost"
FUTU_PORT: int = 11111
FUTU_TRADE_ENV: str = "SIMULATE"      # SIMULATE / REAL

# Longbridge
LONGBRIDGE_APP_KEY: str = ""
LONGBRIDGE_APP_SECRET: str = ""
LONGBRIDGE_ACCESS_TOKEN: str = ""
LONGBRIDGE_REGION: str = "us"

# Tiger
TIGER_ID: str = ""
TIGER_ACCOUNT: str = ""
TIGER_PRIVATE_KEY_PATH: str = ""

# Broker 启用开关
BROKER_ENABLED: list[str] = ["futu"]   # 默认只启用富途
```

### 2.9 Tool 注册

在 `tools.yaml` 中注册三个 Broker Tool：

```yaml
futu_broker:
  module: "aegis.tools.brokers.futu_adapter"
  class: "FutuAdapter"
  priority: P0
  tags: [broker, positions]
  rate_limit: {calls_per_minute: 30}
  circuit_breaker: {failure_threshold: 3, recovery_timeout_sec: 120}
  bound_agents: [portfolio_orchestrator]

longbridge_broker:
  module: "aegis.tools.brokers.longbridge_adapter"
  class: "LongbridgeAdapter"
  priority: P1
  tags: [broker, positions]
  rate_limit: {calls_per_minute: 30}
  circuit_breaker: {failure_threshold: 3, recovery_timeout_sec: 120}
  bound_agents: [portfolio_orchestrator]

tiger_broker:
  module: "aegis.tools.brokers.tiger_adapter"
  class: "TigerAdapter"
  priority: P2
  tags: [broker, positions]
  rate_limit: {calls_per_minute: 20}
  circuit_breaker: {failure_threshold: 3, recovery_timeout_sec: 120}
  bound_agents: [portfolio_orchestrator]
```

---

## 3. 测试要求

| 文件 | 测试点 |
|---|---|
| `test_broker_base.py` | BrokerPosition 模型 + BrokerAdapter 接口契约 |
| `test_futu_adapter.py` | Futu SDK mock + get_positions + get_account_summary + SIMULATE/REAL 切换 |
| `test_longbridge_adapter.py` | Longbridge SDK mock + 持仓解析 + 错误处理 |
| `test_tiger_adapter.py` | Tiger SDK mock + 持仓解析 + 错误处理 |
| `test_broker_manager.py` | 多账户聚合 + 部分失败 fallback + delta_dollars 计算 |
| `test_portfolio_broker.py` | PortfolioOrchestrator 使用真实 broker 数据 + mock fallback |
| `test_position_store.py` | positions.db upsert + 去重 + entry_mode/grade 字段 |

---

## 4. 验收清单

- [ ] `BrokerAdapter` 基类定义完整
- [ ] 至少 1 个券商适配器（富途）可在 SIMULATE 模式拉取持仓
- [ ] BrokerManager 聚合多账户持仓
- [ ] PortfolioOrchestrator 使用 BrokerManager 替代 mock
- [ ] BrokerManager 全部失败时 graceful fallback 到 mock_portfolio.json
- [ ] positions.db 存储持仓快照
- [ ] health_scores 正常计算
- [ ] settings.py 包含所有券商配置字段
- [ ] tools.yaml 注册所有 Broker Tool
- [ ] 单测全绿

---

## 5. 不允许做的事

- 不实现交易下单功能（Aegis 2.0 是决策系统，不自动交易）
- 不修改 PipelineState 契约
- 不实现 Smart Money / Fund Flow Agent（A/B 分支的事）
- 不实现前端持仓页面（D 分支的事）
- 不修改 Pipeline 拓扑
