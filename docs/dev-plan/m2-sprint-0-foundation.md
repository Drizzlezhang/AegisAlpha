# M2 Sprint-0 Foundation — Plan Prompt

> **分支**: `feat/m2-sprint0-foundation`
> **估时**: 2 天
> **优先级**: P0（阻塞所有 M2 分支）
> **子 Agent**: `m2-foundation`
> **前置**: M1 fix plan 已合入 main

---

## 1. 目标

1. 合入 M1 post-review fix
2. PipelineState 升级到 v1.3（新增 M2 字段）
3. FastAPI 骨架 + REST API 路由结构
4. graph_builder 框架（manifest-driven 动态装配）
5. 短期 Memory 表结构 + SQLAlchemy model
6. 新数据源 API Key 全部注册到 settings / .env.example

---

## 2. 交付物清单

### 2.1 M1 Fix 合入

将 `fix/m1-post-review` 的所有修复合入 develop：
- Python 版本约束 `<3.14`
- yFinance options_chain + fundamentals
- ToolRegistry.register()
- Full/Lightweight Pipeline 拓扑修正
- datetime.utcnow 修复
- Calculators 重复代码清理
- 配置统一 + __version__ + alembic 占位

### 2.2 PipelineState v1.3

```python
# 新增字段
smart_money_data: dict[str, dict[str, Any]] = {}
fund_flow_data: dict[str, dict[str, Any]] = {}
trigger_conditions: list[dict[str, Any]] = []
broker_positions: dict[str, list[dict[str, Any]]] = {}
strategy_comparisons: dict[str, list[dict[str, Any]]] = {}
scenario_pnl: dict[str, dict[str, Any]] = {}
```

### 2.3 FastAPI 骨架

```
backend/aegis/api/
├── __init__.py
├── app.py              # FastAPI app 实例 + CORS
├── deps.py             # 依赖注入（settings, memory, registry）
├── routes/
│   ├── __init__.py
│   ├── pipeline.py     # GET /api/v1/pipeline/latest, POST /api/v1/pipeline/run
│   ├── positions.py    # GET /api/v1/positions
│   ├── recommendations.py  # GET /api/v1/recommendations
│   ├── triggers.py     # GET/POST/DELETE /api/v1/triggers
│   ├── health.py       # GET /api/v1/health
│   └── agents.py       # GET /api/v1/agents (manifest 列表)
└── schemas/
    ├── __init__.py
    └── responses.py    # Pydantic response models
```

- CORS 允许 `localhost:3000`
- 无认证（私有部署）
- 所有响应使用 Pydantic schema

### 2.4 graph_builder 框架

```python
# backend/aegis/pipeline/graph_builder.py
class GraphBuilder:
    """Manifest-driven dynamic graph assembly."""
    
    def build(self, agents_yaml: str, pipeline_mode: str) -> StateGraph:
        """
        1. 读取 agents.yaml
        2. 按 pipeline_mode 过滤 enabled agents
        3. 按 requires/provides 推导依赖关系
        4. 同 parallel_group 的 agents fan-out
        5. 返回 compiled StateGraph
        """
```

M2 Sprint-0 只搭框架 + 单测验证 M1 的 9 个 Agent 能被正确装配。Branch F 补全并行逻辑。

### 2.5 短期 Memory SQLAlchemy Model

```python
# backend/aegis/models/memory.py
class ShortTermMemory(Base):
    __tablename__ = "short_term_memory"
    id: int                    # PK
    ticker: str                # 索引
    data_type: str             # "trend" / "debate" / "smart_money" / ...
    content: JSON              # 原始数据
    created_at: datetime       # 自动
    expires_at: datetime       # created_at + TTL
    pipeline_id: str           # 来源 Pipeline
```

- TTL: 7-30 天（按 data_type 可配）
- Alembic migration: `001_add_short_term_memory.py`

### 2.6 Settings + .env.example 更新

新增 key（含 M2 全部新数据源）：
```
UNUSUAL_WHALES_API_KEY=
MARKET_CHAMELEON_API_KEY=
BARCHART_API_KEY=
FINVIZ_API_KEY=
ETF_FUND_FLOW_SOURCE=etfdb          # etfdb / wisesheets
FUTU_TRADE_ENV=SIMULATE             # SIMULATE / REAL
LONGBRIDGE_REGION=us
TIGER_ACCOUNT=
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
MEMORY_SHORT_TTL_DAYS=14
```

---

## 3. 测试要求

| 文件 | 测试点 |
|---|---|
| `test_state_v13.py` | v1.3 新增字段存在 + 类型正确 |
| `test_graph_builder.py` | manifest 解析 + 依赖排序 + M1 agents 装配 |
| `test_api_health.py` | FastAPI app 启动 + /api/v1/health 返回 200 |
| `test_api_routes.py` | 各路由返回正确 schema（mock 数据） |
| `test_memory_model.py` | ShortTermMemory CRUD + TTL 过期 |

---

## 4. 验收清单

- [ ] M1 fix 全部合入，pytest 全绿
- [ ] PipelineState v1.3 字段完整
- [ ] `uvicorn aegis.api.app:app` 启动成功
- [ ] `/api/v1/health` 返回 `{"status": "ok"}`
- [ ] GraphBuilder 可装配 M1 的 9 个 Agent
- [ ] Alembic migration 可正向 + 反向
- [ ] `.env.example` 包含所有 M2 新 key

---

## 5. 不允许做的事

- 不实现具体新 Agent（A/B 分支的事）
- 不实现券商 SDK 对接（C 分支的事）
- 不实现前端代码（D 分支的事）
- 不实现 graph_builder 的并行 fan-out（F 分支的事）
- 不实现完整 Memory 读写逻辑（只建表）
