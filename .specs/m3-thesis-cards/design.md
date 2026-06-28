# Design: m3-thesis-cards

<!-- size:all -->
## 技术方案概述

M3 Branch C 实现 Thesis Cards 完整生命周期管理。核心架构为三层：

```
REST API (FastAPI) ──→ ThesisService ──→ ThesisStore (storage/thesis_store.py)
                            │                    │
                            ├──→ MemoryService ──→ LongTermStore (episodic)
                            │
                            └──→ WeightAdapter (sync, via Session)

ThesisValidatorAgent (standalone cron job)
    ──→ LLMClient (mini)
    ──→ ThesisService.update_valid_status()
    ──→ 独立获取 market data（不依赖 PipelineState）

ThesisReEntryChecker (standalone cron job)
    ──→ ThesisService.check_re_entry()
```

关键设计约束：
- 所有 DB 访问通过 Store 层（ThesisStore / LongTermStore）
- 所有 LLM 调用通过 LLMClient
- 不修改 PipelineState / MemoryInterface / ThesisCard 模型（Sprint-0 冻结）
- 不修改 BaseAgent 构造函数签名

## 组件拆分

### 1. ThesisStore (`backend/aegis/storage/thesis_store.py`) — 新建

**职责**: thesis_cards 表完整 CRUD，使用 SQLAlchemy AsyncSession

**注意**: 与现有 `backend/aegis/memory/thesis_store.py`（WeightAdapter 使用的只读查询接口）区分：
- `aegis.memory.thesis_store.ThesisStore` — 只读，同步 Session，供 WeightAdapter 使用
- `aegis.storage.thesis_store.ThesisStore` — 完整 CRUD，AsyncSession，供 ThesisService 使用

**接口**:
```
create(card_data: dict) → int
get_by_id(thesis_id: int) → ThesisCard | None
get_active(ticker: str | None = None) → list[ThesisCard]
get_closed_with_scores() → list[dict]  # 跨 session 安全的 dict 列表
get_recently_closed(ticker: str, days: int) → list[ThesisCard]
get_earliest_card() → ThesisCard | None
update(thesis_id: int, data: dict) → None
close(thesis_id: int, close_data: dict) → None  # 委托给 update
list_all(filters: dict | None, limit: int, offset: int) → list[ThesisCard]
```

**依赖**: `session_factory: Callable[[], AsyncSession]`

### 2. ThesisService (`backend/aegis/services/thesis_service.py`) — 新建

**职责**: Thesis Card 生命周期业务逻辑编排

**依赖注入**:
```
ThesisService(
    thesis_store: ThesisStore,        # storage/thesis_store.py
    memory: MemoryService,            # 用于 episodic 写入（实际走 LongTermStore）
    weight_adapter: WeightAdapter,    # 平仓后触发权重更新
    long_term_store: LongTermStore,   # episodic memory 实际写入目标
    session_factory: Callable[[], Session],  # 供 WeightAdapter 同步调用
)
```

**公开方法**:
```
create_from_recommendation(recommendation, weight_snapshot, user_confirmed) → int
close_thesis(thesis_id, close_price, judgment_score, execution_score, close_reason) → dict
update_valid_status(thesis_id, new_status, broken_assumptions) → None
check_re_entry(ticker) → bool
get_active_theses(ticker=None) → list[dict]
get_closed_with_scores() → list[dict]
has_active_thesis(ticker) → bool
```

### 3. ThesisValidatorAgent (`backend/aegis/agents/thesis_validator_agent.py`) — 新建

**职责**: 每日校验所有活跃 Thesis 的 key_assumptions

**设计决策**: 不继承 BaseAgent，作为独立类实现。原因：
- GraphBuilder 用 `agent_cls(memory={}, tools={}, config={})` 实例化，无法注入 thesis_service 和 llm_client
- 此 Agent 需要 LLM 调用，不能放入 Lightweight Pipeline
- 作为独立 cron job 运行更合适

**接口**:
```
class ThesisValidatorAgent:
    def __init__(self, thesis_service: ThesisService, llm_client: LLMClient)
    async def validate_all(self) → dict[str, dict]  # {ticker: validation_result}
    async def _validate_assumptions(thesis, current_data) → dict
```

**数据获取**: 不依赖 PipelineState。通过 Tool Registry 获取当前市场数据（价格、趋势、支撑/阻力等）。

### 4. ThesisReEntryChecker (`backend/aegis/services/thesis_service.py` 内或独立) — 新建

**职责**: 每日扫描已平仓 ≥30 天的 Thesis，标记 re_entry_flagged

**接口**:
```
class ThesisReEntryChecker:
    def __init__(self, thesis_service: ThesisService)
    async def run() → dict[str, bool]  # {ticker: flagged}
```

### 5. REST API (`backend/aegis/api/routes/thesis.py`) — 新建

**职责**: Thesis CRUD + 平仓打分 + 校验历史查询

**端点**:
```
GET    /api/v1/thesis                   # 列表（过滤+分页）
GET    /api/v1/thesis/{id}              # 详情
POST   /api/v1/thesis                   # 手动创建
POST   /api/v1/thesis/{id}/close        # 平仓+打分
PATCH  /api/v1/thesis/{id}              # 部分更新
GET    /api/v1/thesis/{id}/history      # 校验历史
```

**依赖注入**: 通过 FastAPI Depends 注入 ThesisService（需在 deps.py 中添加工厂函数）

### 6. 修改现有组件

| 文件 | 修改内容 |
|------|---------|
| `agents/research_manager_agent.py` | `_synthesize()` 中新增 `has_active_thesis()` 检查，在 `_in_cooldown()` 之前执行 |
| `pipeline/runner.py` | 新增 `_post_recommendation_hook()` 自动创建 ThesisCard |
| `api/app.py` | 注册 thesis router |
| `api/deps.py` | 新增 `get_thesis_service()` 工厂函数 |
| `config/agents.yaml` | thesis_validator: `pipeline_mode: full`, `enabled: true` |
| `config/schedule.yaml` | 新增 thesis_validation + thesis_re_entry_check cron jobs |
<!-- /size:all -->

<!-- size:S+ -->
## API 设计

### Request/Response Models

```python
# 创建
class ThesisCreateRequest(BaseModel):
    ticker: str
    direction: Literal["long", "short_put", "cc"]
    entry_mode: Literal["active_left", "active_right", "passive"] = "active_right"
    entry_price: float
    target_price: float | None = None
    stop_price: float | None = None
    key_assumptions: list[str] = []

# 平仓
class ThesisCloseRequest(BaseModel):
    close_price: float
    judgment_score: int = Field(ge=1, le=5)
    execution_score: int = Field(ge=1, le=5)
    close_reason: Literal["stop_hit", "target_reached", "thesis_broken", "manual"] = "manual"

# 更新
class ThesisUpdateRequest(BaseModel):
    target_price: float | None = None
    stop_price: float | None = None
    key_assumptions: list[str] | None = None
    entry_mode: str | None = None

# 列表响应
class ThesisListResponse(BaseModel):
    items: list[dict]
    limit: int
    offset: int

# 平仓响应
class ThesisCloseResponse(BaseModel):
    thesis_id: int
    pnl_pct: float
    new_weights: dict[str, float]
```

### 端点详细设计

| 方法 | 路径 | 请求体 | 响应 | 错误 |
|------|------|--------|------|------|
| GET | `/api/v1/thesis` | Query: status, ticker, direction, limit, offset | `ThesisListResponse` | — |
| GET | `/api/v1/thesis/{id}` | — | `dict` (card_to_dict) | 404 |
| POST | `/api/v1/thesis` | `ThesisCreateRequest` | `{id, message}` 201 | 409 (重复) |
| POST | `/api/v1/thesis/{id}/close` | `ThesisCloseRequest` | `ThesisCloseResponse` | 400 (已平仓/无效分) |
| PATCH | `/api/v1/thesis/{id}` | `ThesisUpdateRequest` | `{message}` | 404 / 400 (已平仓) |
| GET | `/api/v1/thesis/{id}/history` | — | `{thesis_id, history}` | 404 |
<!-- /size:S+ -->

<!-- size:M+ -->
## 数据模型

### ThesisCard（已冻结，Sprint-0 创建）

```
thesis_cards
├── id: INTEGER PK
├── ticker: VARCHAR(20) INDEX
├── direction: VARCHAR(20)          # long | short_put | cc
├── entry_mode: VARCHAR(20)         # active_left | active_right | passive
├── entry_date: DATETIME
├── entry_price: FLOAT
├── target_price: FLOAT?
├── stop_price: FLOAT?
├── key_assumptions: JSON           # list[str]
├── thesis_valid_status: VARCHAR(20) # valid | partial_broken | fully_broken
├── re_entry_flagged: BOOLEAN
├── factor_snapshot: JSON           # {factor_name: score}
├── close_date: DATETIME?
├── close_price: FLOAT?
├── actual_pnl_pct: FLOAT?
├── judgment_score: INTEGER?        # 1-5
├── execution_score: INTEGER?       # 1-5
├── close_reason: VARCHAR(100)?
├── created_at: DATETIME
└── updated_at: DATETIME
```

### Episodic Memory 写入格式（LongTermStore）

```python
{
    "ticker": "QQQ",
    "data_type": "episodic_thesis",
    "content": {
        "thesis_id": 1,
        "ticker": "QQQ",
        "direction": "long",
        "entry_date": "2026-06-20T...",
        "entry_price": 450.0,
        "close_price": 480.0,
        "actual_pnl_pct": 0.0667,
        "judgment_score": 4,
        "execution_score": 3,
        "close_reason": "target_reached",
        "factor_snapshot": {"trend_phase": 75, "smart_money": 60},
        "key_assumptions": ["QQQ above 200MA", "tech sector momentum"],
        "holding_days": 45,
    },
    "original_date": datetime.now(UTC),
}
```

### 状态转换图

```
thesis_valid_status:
  valid ──→ partial_broken ──→ fully_broken
    │                              │
    └──────────────────────────────┘  (可直接从 valid → fully_broken)
  
  禁止: fully_broken → partial_broken → valid (单向不可逆)

ThesisCard 生命周期:
  [创建] ──→ active (close_date=NULL)
    │            │
    │            ├── 每日校验 → valid_status 可能变化
    │            │
    │            └── [平仓] → closed (close_date!=NULL)
    │                              │
    │                              ├── Episodic Memory 写入
    │                              ├── WeightAdapter 触发
    │                              │
    │                              └── 30天后 → re_entry_flagged (条件满足时)
```

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| WeightAdapter.update_weights 是同步方法 | close_thesis 需创建 Session 调用 | 在 close_thesis 中用 `run_in_executor` 包装同步调用 |
| 两个 ThesisStore 类命名冲突 | import 路径混淆 | 明确文档约定：`aegis.storage.thesis_store` vs `aegis.memory.thesis_store` |
| ThesisValidatorAgent 需独立获取 market data | 增加 cron job 复杂度 | 复用 Tool Registry 获取数据，不重复实现 |
| Research Manager 冷却检查影响现有推荐 | 可能减少推荐数量 | 仅新增 has_active_thesis 检查，不修改现有逻辑 |
| close_thesis 中 Memory 写入失败 | 平仓数据未入 Memory | Memory 写入为 best-effort，失败记录日志不阻断平仓 |
| 并发平仓同一 thesis | 重复写入 | close_thesis 先检查 close_date IS NULL，第二次请求抛 ValueError |
<!-- /size:M+ -->

<!-- size:L -->
## 架构决策记录（ADR）

### ADR-1: ThesisValidatorAgent 作为独立 cron job
- **状态**: accepted
- **上下文**: dev plan 将 ThesisValidatorAgent 配置为 `pipeline_mode: lightweight`，但校验 key_assumptions 需要 LLM 调用。Lightweight Pipeline 的设计目标是零 LLM 调用（AGENTS.md 第 11.2 节）。同时，Lightweight Pipeline 只跑 passive 持仓，而活跃 Thesis 可能包含 active 持仓。
- **决策**: ThesisValidatorAgent 作为独立 cron job 运行，不经过任何 Pipeline。通过 APScheduler 每日定时触发，独立获取 market data，独立调用 LLM。
- **后果**:
  - 需要独立的 market data 获取逻辑（复用 Tool Registry）
  - 不依赖 PipelineState，校验结果不写入 state.extensions
  - agents.yaml 中 thesis_validator 改为 `pipeline_mode: full, enabled: true`（仅注册，实际不通过 GraphBuilder 调用）

### ADR-2: Episodic Memory 通过 LongTermStore 写入
- **状态**: accepted
- **上下文**: dev plan 使用 `MemoryService.write("episodic", ...)`，但 MemoryService 的 episodic scope 是 no-op（不持久化）。修改 MemoryInterface 需要契约层变更。
- **决策**: close_thesis 直接调用 `LongTermStore.insert()` 写入，data_type="episodic_thesis"。不修改 MemoryInterface。
- **后果**:
  - ThesisService 需要额外依赖 LongTermStore
  - Episodic 数据与 long-term 数据存在同一张表，通过 data_type 区分
  - 未来如需独立 episodic 存储，可迁移 data_type="episodic_thesis" 记录

### ADR-3: ThesisValidatorAgent 不继承 BaseAgent
- **状态**: accepted
- **上下文**: GraphBuilder 用 `agent_cls(memory={}, tools={}, config={})` 实例化 Agent，无法注入 thesis_service 和 llm_client。修改 BaseAgent 构造函数签名是契约层变更。
- **决策**: ThesisValidatorAgent 作为独立类实现，不继承 BaseAgent，不通过 GraphBuilder 装配。由 cron job 直接实例化和调用。
- **后果**:
  - 不能复用 GraphBuilder 的并行执行、错误处理、WebSocket 事件
  - 需要自行实现错误处理和日志
  - agents.yaml 中保留注册仅用于文档目的

### ADR-4: WeightAdapter 同步接口适配
- **状态**: accepted
- **上下文**: `WeightAdapter.update_weights(session: Session)` 是同步方法，需要 SQLAlchemy Session。`ThesisService.close_thesis()` 是 async 方法。
- **决策**: 在 close_thesis 中使用 `asyncio.to_thread()` 或 `loop.run_in_executor()` 包装同步调用。创建独立的 Session 传入 WeightAdapter。
- **后果**:
  - close_thesis 需要 `session_factory` 依赖（同步 Session）
  - 与 ThesisStore 的 AsyncSession 是两条独立的数据库连接
  - 参考现有 `api/routes/weights.py` 中的 `_get_session()` 模式

### ADR-5: 两个 ThesisStore 共存策略
- **状态**: accepted
- **上下文**: `aegis/memory/thesis_store.py` 已存在（WeightAdapter 使用的只读查询接口，同步 Session）。新需求需要完整 CRUD + AsyncSession。
- **决策**: 新建 `aegis/storage/thesis_store.py`，两个类通过 import 路径区分。不修改现有 `memory/thesis_store.py`。
- **后果**:
  - 两个同名类需要明确的 import 约定
  - 未来可考虑将 memory/thesis_store.py 的方法合并到 storage/thesis_store.py，但不在本次变更范围

## Alternatives Considered

### A1: close_thesis 中 WeightAdapter 调用方式
- **方案 A**: `asyncio.to_thread(weight_adapter.update_weights, session)` — 推荐
- **方案 B**: 为 WeightAdapter 新增 async wrapper — 需要修改 Branch B 代码
- **方案 C**: 不在 close_thesis 中触发，由定时 cron job 统一更新 — 延迟反馈
- **决策**: 方案 A，最小侵入

### A2: ThesisValidatorAgent market data 获取
- **方案 A**: 通过 Tool Registry 获取 — 推荐，复用现有基础设施
- **方案 B**: 直接调用 yfinance/httpx — 违反 AGENTS.md 规范
- **方案 C**: 要求调用方传入 market data dict — 增加 cron job 复杂度
- **决策**: 方案 A

### A3: API 依赖注入方式
- **方案 A**: FastAPI Depends + deps.py 工厂函数 — 推荐，与现有模式一致
- **方案 B**: 在路由文件中直接创建 — 不可测试
- **方案 C**: 全局 singleton — 违反无全局可变状态原则
- **决策**: 方案 A，参考 `api/routes/weights.py` 的 `_get_session()` 模式

## Migration Plan

1. 部署新代码（所有新建文件 + 修改文件）
2. 更新 `config/agents.yaml`：thesis_validator 改为 `pipeline_mode: full, enabled: true`
3. 更新 `config/schedule.yaml`：新增两个 cron jobs
4. 重启 APScheduler 进程
5. 验证步骤：
   - 通过 API 手动创建 ThesisCard
   - 等待 thesis_validation cron 触发，检查校验结果
   - 通过 API 平仓，验证 P&L + Memory 写入 + WeightAdapter 触发
   - 等待 thesis_re_entry_check cron 触发，验证 re_entry_flagged
6. 无需数据迁移（thesis_cards 表已存在）
7. 回滚：删除新建文件 + revert 修改文件 + revert YAML 配置

## Observability

- **日志**: 所有关键操作使用 loguru
  - `logger.info(f"Thesis {id} created for {ticker}")`
  - `logger.info(f"Thesis {id} closed: PnL={pnl_pct:.2%}, J={judgment}, E={execution}")`
  - `logger.info(f"ThesisValidator: {n} theses checked, {m} status changes")`
  - `logger.error(f"Thesis {id} memory write failed: {e}")` (best-effort)
- **Metrics**: 
  - 活跃 Thesis 数量
  - 每日校验数量 / 状态变更数量
  - 平仓 P&L 分布
  - WeightAdapter 更新频率
- **Alerting**: 
  - WeightAdapter 更新失败 → ERROR 日志
  - Memory 写入失败 → WARNING 日志（best-effort）
  - 重复创建被阻止 → INFO 日志
<!-- /size:L -->
