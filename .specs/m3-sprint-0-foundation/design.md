# Design: m3-sprint-0-foundation

## 技术方案概述

M3 Sprint-0 是纯基础设施铺设，不涉及业务逻辑实现。核心思路是"加法不减法"：所有变更都是新增字段/表/配置/接口参数，不修改任何已有字段的含义或类型。

## 组件拆分

### 1. PipelineState v1.4（契约层）
- **文件**: `backend/aegis/pipeline/state.py`
- **变更**: 在 v1.3 字段末尾追加 5 个 M3 字段
- **约束**: 所有新字段 default 为空容器，不修改 v1.3 字段

### 2. DB Models（数据层）
- **文件**: 4 个新 model 文件 + 1 个修改
  - `models/thesis.py` — ThesisCard（Episodic Memory）
  - `models/kol.py` — KOLSource + KOLCall
  - `models/long_term_memory.py` — LongTermMemory
  - `models/factor_weight.py` — FactorWeight
  - `models/__init__.py` — 更新导出

### 3. MemoryInterface v1.1（接口层）
- **文件**: `memory/interface.py`
- **变更**: 3 个方法签名新增可选参数（均有默认值）

### 4. Agent 注册（配置层）
- **文件**: `config/agents.yaml`
- **变更**: 追加 3 个 Agent（enabled=false）

### 5. 配置文件（配置层）
- **文件**: 4 个新 YAML
  - `config/universe_watchlist.yaml`
  - `config/kol_sources.yaml`
  - `config/memory.yaml`
  - `config/weights.yaml`

### 6. Settings + .env.example（环境层）
- **文件**: `utils/settings.py` + `.env.example`
- **变更**: 新增 M3 环境变量

### 7. Alembic 迁移
- **文件**: `alembic/versions/m3_001_*.py`
- **变更**: autogenerate 生成，手动检查

### 8. AGENTS.md v1.3（文档层）
- **文件**: `AGENTS.md`
- **变更**: 版本号 + Section 更新 + 新约束规则

### 9. M2 遗留修复
- **文件**: `tests/agents/test_smart_money_agent.py`
- **变更**: 3 个断言值更新 + 注释更新

## 数据模型

### ThesisCard（thesis_cards）
```
id: INTEGER PK
ticker: VARCHAR(20) INDEX
direction: VARCHAR(20)  -- long/short_put/cc
entry_mode: VARCHAR(20)  -- active_left/active_right/passive
entry_date: DATETIME
entry_price: FLOAT
target_price: FLOAT NULL
stop_price: FLOAT NULL
key_assumptions: JSON  -- list[str]
thesis_valid_status: VARCHAR(20) DEFAULT 'valid'  -- valid/partial_broken/fully_broken
re_entry_flagged: BOOLEAN DEFAULT FALSE
factor_snapshot: JSON
close_date: DATETIME NULL
close_price: FLOAT NULL
actual_pnl_pct: FLOAT NULL
judgment_score: INTEGER NULL  -- 1-5
execution_score: INTEGER NULL  -- 1-5
close_reason: VARCHAR(100) NULL
created_at: DATETIME
updated_at: DATETIME
```

### KOLSource（kol_sources）
```
id: INTEGER PK
name: VARCHAR(100)
platform: VARCHAR(20)  -- x/stocktwits/reddit
handle: VARCHAR(100)
reliability_score: FLOAT DEFAULT 0.5
total_calls: INTEGER DEFAULT 0
successful_calls: INTEGER DEFAULT 0
enabled: BOOLEAN DEFAULT TRUE
created_at: DATETIME
```

### KOLCall（kol_calls）
```
id: INTEGER PK
kol_source_id: INTEGER INDEX
ticker: VARCHAR(20) INDEX
direction: VARCHAR(10)  -- bullish/bearish
call_date: DATETIME
call_price: FLOAT
attribution_status: VARCHAR(20) DEFAULT 'pending'  -- pending/validated/invalidated
pnl_30d: FLOAT NULL
pnl_60d: FLOAT NULL
source_url: TEXT
content_snippet: TEXT
created_at: DATETIME
```

### LongTermMemory（long_term_memory）
```
id: INTEGER PK
ticker: VARCHAR(20) INDEX NULL
data_type: VARCHAR(50) INDEX  -- debate/recommendation/kol_calls/regime_judgment/smart_money_flow/fund_flow
content: JSON
summary: TEXT NULL
original_date: DATETIME
compressed_at: DATETIME NULL
is_compressed: BOOLEAN DEFAULT FALSE
embedding_id: VARCHAR(64) NULL  -- ChromaDB vector ID
created_at: DATETIME
```

### FactorWeight（factor_weights）
```
id: INTEGER PK
factor_name: VARCHAR(50) INDEX
weight: FLOAT
previous_weight: FLOAT NULL
changed_by: VARCHAR(20) DEFAULT 'system'  -- system/manual
observation_period_active: BOOLEAN DEFAULT TRUE
sample_count: INTEGER DEFAULT 0
updated_at: DATETIME
```

### PipelineState v1.4 新增字段
```python
thesis_cards: dict[str, Any] = Field(default_factory=dict)
kol_signals: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
universe_candidates: list[dict[str, Any]] = Field(default_factory=list)
weight_snapshot: dict[str, float] = Field(default_factory=dict)
thesis_validation_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
```

## MemoryInterface v1.1 签名变更

| 方法 | v1.0 | v1.1 | 兼容性 |
|------|------|------|--------|
| `read` | `(scope, query)` | `(scope, query, limit=10)` | ✅ 新参数有默认值 |
| `search` | `(query, top_k=5)` | `(query, collection="default", top_k=5, filter=None)` | ✅ 新参数有默认值 |
| `summarize` | `(ticker, date_range)` | `(ticker \| None, date_range, data_type="")` | ✅ ticker 改为 Optional，新参数有默认值 |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| PipelineState v1.4 序列化不兼容 | M2 流程无法反序列化旧 state | 所有新字段 default 为空容器；单元测试验证 v1.3 JSON → v1.4 反序列化 |
| Alembic autogenerate 遗漏索引 | 查询性能下降 | 手动检查迁移文件，确保 INDEX 语句存在 |
| MemoryInterface 签名变更破坏 M2 | M2 Agent 调用报错 | 所有新参数有默认值；运行 M2 全量测试验证 |
| Smart Money 测试期望值计算错误 | 测试通过但逻辑不对 | 手动验证 3 个 case 的计算过程与算法一致 |

## 回滚计划

每个变更点均可独立回退：
1. PipelineState → 删除 5 个新字段
2. DB 表 → `alembic downgrade -1`
3. MemoryInterface → 删除新参数
4. agents.yaml → 删除 3 个 Agent 条目
5. 配置文件 → 删除 4 个新 YAML
6. settings.py → 删除 M3 key
7. .env.example → 删除 M3 key
8. AGENTS.md → git revert
