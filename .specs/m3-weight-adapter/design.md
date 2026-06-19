# Design: m3-weight-adapter

## 技术方案概述

WeightAdapter 是 M3 双维度反馈闭环的核心组件。它从已平仓 ThesisCard 中提取 judgment_score（1-5）、execution_score（1-5）、actual_pnl_pct，计算综合信号后通过 numpy 加权最小二乘法回归出新的因子权重，写入 factor_weights 表。首 30 天为观察期（OBSERVATION_PERIOD_DAYS=30），权重不更新；观察期结束后自动回填历史数据。

**核心数据流**：
```
ThesisCard (closed) → WeightAdapter._collect_samples()
  → composite_signal = 0.5*pnl + 0.3*judgment + 0.2*execution
  → time_decay_weight = 0.5^(age_days/90)
  → numpy weighted least squares → new_weight = clamp(1.0 + slope, 0.2, 3.0)
  → WeightStore.update_weight() → factor_weights 表
  → Pipeline runner._inject_weight_snapshot() → state.weight_snapshot
```

## 组件拆分

### 1. WeightAdapter (`backend/aegis/memory/weight_adapter.py`)
核心算法模块，纯计算，无 IO 依赖（通过注入 Store 接口解耦）。

**职责**：
- `_pnl_to_signal(pnl_pct: float) -> float` — P&L% → [-1, 1] 线性映射
- `_score_to_signal(score: int, range_max: int = 5) -> float` — 1-5 打分 → [-1, 1] 归一化
- `_composite_signal(judgment: int, execution: int, pnl_pct: float) -> float` — 三信号加权合成
- `_time_decay_weight(close_date: datetime, now: datetime) -> float` — 半衰期 90 天
- `_collect_samples(cards: list[ThesisCard]) -> dict[str, list[Sample]]` — 按 factor_name 分组收集样本
- `_weighted_regression(samples: list[Sample]) -> float | None` — numpy 加权最小二乘，返回新权重或 None
- `update_weights(session, weight_store, thesis_store) -> dict[str, float]` — 主入口：收集样本 → 回归 → 写入

**依赖**：numpy（仅用于 `np.linalg.lstsq`），不引入 scikit-learn。

### 2. WeightStore (`backend/aegis/memory/weight_store.py`)
factor_weights 表的 CRUD 封装。

**职责**：
- `get_weight(session, factor_name: str) -> float` — 返回当前权重，不存在返回 1.0
- `get_all_weights(session) -> dict[str, dict]` — 返回所有 factor 当前权重 + 元数据
- `update_weight(session, factor_name, new_weight, sample_count, changed_by="system") -> None` — 记录 previous_weight，写入新行
- `get_weight_history(session, factor_name: str | None = None) -> list[dict]` — 变更历史
- `initialize_from_config(session, config_path: str) -> None` — 从 weights.yaml 加载初始权重（仅当表为空时）
- `is_observation_period_active(session) -> bool` — 检查是否有任何 factor 处于观察期

### 3. ObservationPeriodManager (`backend/aegis/memory/observation_period.py`)
观察期生命周期管理。

**职责**：
- `get_first_card_date(session) -> datetime | None` — 查询最早 ThesisCard 的 created_at
- `is_in_observation_period(session, first_card_date: datetime | None) -> bool` — 判断是否在 30 天观察期内
- `check_and_transition(session, weight_store, weight_adapter) -> bool` — 检测观察期是否刚结束，若是则触发回填
- `backfill_after_observation(session, weight_store, weight_adapter) -> dict[str, float]` — 使用所有历史数据计算初始权重

### 4. ThesisStore (`backend/aegis/memory/thesis_store.py`)
ThesisCard 查询封装（当前不存在，需新建）。

**职责**：
- `get_closed_cards(session, since: datetime | None = None) -> list[ThesisCard]` — 查询已平仓且有双维度打分的 cards
- `get_closed_cards_by_factor(session, factor_name: str) -> list[ThesisCard]` — 按 factor 筛选（通过 factor_snapshot JSON 字段）

### 5. Scheduler (`backend/aegis/scheduler.py`)
APScheduler 常驻进程（当前不存在，需新建）。

**职责**：
- 启动 APScheduler 实例，注册两个 cron job：
  - `observation_check_job` — 每日 1:00 ET，调用 ObservationPeriodManager.check_and_transition
  - `weight_update_job` — 每周日 4:00 ET，调用 WeightAdapter.update_weights
- 从 schedule.yaml 读取 cron 配置
- 使用 SQLite 作为 job store（APScheduler SQLAlchemyJobStore）

### 6. Pipeline 集成点修改
**文件**：`backend/aegis/pipeline/runner.py`

在 `run_full()` 中，`GraphBuilder.build()` 之前注入：
```python
from aegis.memory.weight_store import WeightStore
# ...
snapshot = await _inject_weight_snapshot()
state.weight_snapshot = snapshot
```

`_inject_weight_snapshot()` 从 WeightStore.get_all_weights() 获取当前权重，写入 state.weight_snapshot。

### 7. REST API (`backend/aegis/api/routes/weights.py`)
三个端点，注册到 `/api/v1/memory` 前缀。

## API 设计

| Method | Path | Description | Response Model |
|--------|------|-------------|---------------|
| GET | `/api/v1/memory/weights` | 当前所有权重 + 观察期状态 | `WeightSnapshotResponse` |
| GET | `/api/v1/memory/weights/history` | 权重变更历史（支持 ?factor= 过滤） | `list[WeightHistoryResponse]` |
| POST | `/api/v1/memory/weights/{factor}/override` | 手动覆盖某 factor 权重 | `WeightOverrideResponse` |

**Response Schemas**（新增到 `backend/aegis/api/schemas/responses.py`）：

```python
class WeightSnapshotResponse(BaseModel):
    factors: dict[str, dict]  # {factor_name: {weight, previous_weight, sample_count, observation_period_active}}
    observation_period_active: bool
    observation_days_remaining: int | None

class WeightHistoryResponse(BaseModel):
    factor_name: str
    weight: float
    previous_weight: float | None
    changed_by: str
    sample_count: int
    updated_at: str

class WeightOverrideRequest(BaseModel):
    weight: float  # 限制 [0.2, 3.0]
    reason: str = ""

class WeightOverrideResponse(BaseModel):
    factor: str
    previous_weight: float
    new_weight: float
    changed_by: str  # "manual"
```

## 数据模型

### 已有模型（不修改）

**FactorWeight** (`backend/aegis/models/factor_weight.py`) — 字段已满足需求：
- `factor_name`, `weight`, `previous_weight`, `changed_by`, `observation_period_active`, `sample_count`, `updated_at`

**ThesisCard** (`backend/aegis/models/thesis.py`) — 读取以下字段：
- `close_date`, `actual_pnl_pct`, `judgment_score`, `execution_score`, `factor_snapshot`

### 新增内部类型（非 DB 模型）

```python
# weight_adapter.py 内部
@dataclass
class Sample:
    factor_name: str
    factor_score: float      # 该 factor 在 factor_snapshot 中的原始 score (0-100)
    outcome: float           # composite_signal 值
    time_decay_weight: float # 时间衰减权重
    close_date: datetime
```

### DB Session 管理

当前项目无统一的 DB session 管理工具。WeightAdapter 各组件通过**依赖注入**接收 SQLAlchemy `Session`，由调用方（scheduler / API route）负责创建和关闭 session。使用模式：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine(settings.DATABASE_URL)
with Session(engine) as session:
    store = WeightStore()
    weights = store.get_all_weights(session)
```

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| numpy 引入增加依赖体积 | 安装复杂度 | numpy 是 Python 数据科学生态标配，仅用 `np.linalg.lstsq`，不引入 scipy/sklearn |
| 回归数值不稳定（共线性） | 权重计算出错 | try/except 捕获 `LinAlgError`，返回默认权重 1.0，记录 WARNING 日志 |
| 观察期内无足够样本 | 观察期结束后回填仍不足 5 样本 | `_weighted_regression` 返回 None，保持当前权重不变 |
| scheduler 进程与 API 进程并发写 factor_weights | 数据竞争 | SQLite WAL 模式 + 事务隔离；scheduler 写操作在独立短事务中完成 |
| ThesisCard 缺少双维度打分 | 样本被跳过 | `_collect_samples` 过滤 `judgment_score IS NULL OR execution_score IS NULL` 的 cards |
| scheduler.py 从零创建 | 调度框架集成复杂度 | 参考 AGENTS.md 已声明的 APScheduler 技术栈，使用 SQLAlchemyJobStore |

## 回滚计划

- 删除新增文件：`weight_adapter.py`, `weight_store.py`, `observation_period.py`, `thesis_store.py`, `scheduler.py`, `weights.py` (routes)
- 从 `runner.py` 移除 `_inject_weight_snapshot` 调用
- 从 `app.py` 移除 weights router 注册
- 从 `pyproject.toml` 移除 numpy 依赖（如无其他用途）
- 从 `schedule.yaml` 移除 weight_adapter 相关 cron 配置
- `factor_weights` 表保留不删除（Sprint-0 产物）
- `models/__init__.py` 中 FactorWeight 导入保留
