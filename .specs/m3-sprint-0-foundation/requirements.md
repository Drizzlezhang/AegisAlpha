# Requirements: m3-sprint-0-foundation

## 功能需求

### FR-1: M2 遗留 Smart Money 测试修复
- Given: Smart Money Agent 评分已归一化到 0-100 范围
- When: 运行 `test_smart_money_agent.py` 中的 3 个测试
- Then: `test_score_bullish_high_confidence` 期望值 85.0，`test_score_bearish` 期望值 82.0，`test_score_oi_capped_at_30` 期望值 100.0，全部通过

### FR-2: PipelineState v1.4 契约扩展
- Given: PipelineState v1.3 已定义
- When: 在 `state.py` 末尾新增 5 个 M3 字段
- Then: `thesis_cards`、`kol_signals`、`universe_candidates`、`weight_snapshot`、`thesis_validation_results` 字段存在，default 均为空容器，v1.3 字段不受影响

### FR-3: DB Schema — 5 张新表
- Given: SQLAlchemy Base 已定义
- When: 创建 `models/thesis.py`、`models/kol.py`、`models/long_term_memory.py`、`models/factor_weight.py`
- Then: ThesisCard、KOLSource、KOLCall、LongTermMemory、FactorWeight 五个模型可被导入，字段与 dev plan 一致

### FR-4: models/__init__.py 更新
- Given: 4 个新 model 文件已创建
- When: 更新 `models/__init__.py`
- Then: 所有 7 个模型（含已有 ShortTermMemory）均可从 `aegis.models` 导入

### FR-5: MemoryInterface v1.1 签名扩展
- Given: MemoryInterface v1.0 已冻结
- When: 更新 `memory/interface.py` 签名
- Then: `read` 新增 `limit` 参数（默认 10），`search` 新增 `filter` 参数（默认 None），`summarize` 新增 `data_type` 参数（默认 ""），所有新参数有默认值，M2 代码无需修改

### FR-6: agents.yaml 新增 3 个 Agent
- Given: agents.yaml 已有 M1+M2 Agent 注册
- When: 追加 universe_triage / kol_tracker / thesis_validator
- Then: 3 个 Agent 均 enabled=false，含完整 manifest 字段（name/version/requires/provides/tags/llm_dependency/parallel_group/pipeline_mode）

### FR-7: 4 个配置文件新增
- Given: config/ 目录存在
- When: 创建 universe_watchlist.yaml / kol_sources.yaml / memory.yaml / weights.yaml
- Then: 4 个文件内容与 dev plan 一致，YAML 格式合法

### FR-8: Settings 更新
- Given: settings.py 已有 M1+M2 配置
- When: 新增 M3 环境变量字段
- Then: CHROMA_PERSIST_DIR / EMBEDDING_MODEL / STOCKTWITS_ACCESS_TOKEN / REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / X_BEARER_TOKEN / MEMORY_SHORT_TTL_DAYS / MEMORY_COMPRESSION_ENABLED / OBSERVATION_PERIOD_DAYS / UNIVERSE_SCAN_TOP_N / UNIVERSE_SCAN_ENABLED 字段存在且有默认值

### FR-9: .env.example 更新
- Given: .env.example 已有 M1+M2 key
- When: 追加 M3 新 key
- Then: 含 ChromaDB / KOL / Memory / Universe 相关 key，均有注释说明

### FR-10: Alembic 迁移
- Given: 5 张新表模型已定义
- When: 运行 `alembic revision --autogenerate -m "M3: add thesis, KOL, memory, weight tables"`
- Then: 生成迁移文件，upgrade() 创建 5 张表 + 索引，downgrade() 删除 5 张表

### FR-11: AGENTS.md v1.3 更新
- Given: AGENTS.md v1.2
- When: 更新版本号 + Section 9.1 + Section 18.1 + 新增 M3 约束规则
- Then: 版本号 v1.3，含 6 条 M3 新约束规则

## 验收标准与验证方式

| AC | 验证方式 |
|----|---------|
| AC-1: Smart Money 3 个测试修复，全量测试全绿 | `pytest tests/agents/test_smart_money_agent.py -v` 3 个测试通过；`pytest tests/ -v` 全量通过 |
| AC-2: PipelineState v1.4 新字段存在且 default 为空 | 单元测试：实例化 PipelineState，断言 5 个新字段存在且值为空容器 |
| AC-3: 5 张新表模型可导入且字段正确 | 单元测试：导入 ThesisCard/KOLSource/KOLCall/LongTermMemory/FactorWeight，断言 __tablename__ 和关键字段存在 |
| AC-4: models/__init__.py 导出所有模型 | `python -c "from aegis.models import ThesisCard, KOLSource, KOLCall, LongTermMemory, FactorWeight"` 无 ImportError |
| AC-5: MemoryInterface v1.1 签名向后兼容 | 单元测试：mock 实现新接口，断言 M2 风格调用（不传新参数）不报错 |
| AC-6: agents.yaml 含 3 个新 Agent（enabled=false） | YAML 解析检查：universe_triage/kol_tracker/thesis_validator 存在且 enabled=false |
| AC-7: 4 个配置文件 YAML 合法 | `python -c "import yaml; yaml.safe_load(open(f))"` 对 4 个文件均不抛异常 |
| AC-8: settings.py 含 M3 新 key | `python -c "from aegis.utils.settings import settings; assert settings.CHROMA_PERSIST_DIR"` 无 AttributeError |
| AC-9: .env.example 含 M3 新 key | grep 检查：CHROMA_PERSIST_DIR / EMBEDDING_MODEL / STOCKTWITS_ACCESS_TOKEN 等 key 存在 |
| AC-10: Alembic upgrade + downgrade 可逆 | `alembic upgrade head && alembic downgrade -1` 无错误 |
| AC-11: AGENTS.md v1.3 版本号 + 新约束 | grep 检查：版本号 "v1.3"，含 "M3 新增约束规则" 段落 |
| AC-12: ruff + mypy 全绿 | `ruff check` + `mypy` 对变更文件无错误 |

## 用户故事
- As a M3 developer, I want PipelineState v1.4 to have thesis/kol/weight fields, so that downstream agents can read/write M3 data without modifying the contract again.
- As a M3 developer, I want 5 new DB tables created via Alembic, so that Thesis Cards, KOL tracking, long-term memory, and factor weights have persistent storage.
- As a M2 developer, I want MemoryInterface v1.1 to be backward-compatible, so that my existing code doesn't break.
- As a pipeline operator, I want new agents registered (disabled) in agents.yaml, so that I can see what's planned for M3 without affecting current runs.

## 非功能需求

### NFR-1: 向后兼容
- PipelineState v1.4 新增字段不破坏 v1.3 序列化
- MemoryInterface v1.1 新参数均有默认值
- M2 所有测试在变更后仍全绿

### NFR-2: DB 迁移可逆
- Alembic upgrade 创建 5 张表 + 索引
- Alembic downgrade 删除 5 张表
- 迁移不触及已有表

### NFR-3: 配置完整性
- 所有新 YAML 文件格式合法
- 所有新 settings key 有默认值
- .env.example 与 settings.py 字段一一对应

## 边界场景

### Edge-1: PipelineState v1.3 序列化兼容
- 旧 PipelineState JSON（无 v1.4 字段）反序列化到 v1.4 → 新字段使用 default 值，不报错

### Edge-2: Alembic 在空数据库上运行
- 全新 SQLite 数据库 → `alembic upgrade head` 创建所有表（含 M1+M2+M3），无外键冲突

### Edge-3: 新 Agent enabled=false 不影响 Pipeline
- GraphBuilder 加载 agents.yaml → enabled=false 的 Agent 不出现在拓扑排序中

### Edge-4: MemoryInterface 旧调用方式
- `memory.read(scope="short", query={})` 不传 limit → 使用默认值 10，不报错

## 回滚计划
- PipelineState v1.4 → 删除 5 个新字段即可回退到 v1.3
- DB 表 → `alembic downgrade -1` 删除 5 张表
- MemoryInterface → 删除新参数恢复 v1.0 签名
- 配置文件 → 删除 4 个新 YAML 文件
- agents.yaml → 删除 3 个新 Agent 条目
- AGENTS.md → revert 到 v1.2

## 数据/权限影响
- 新增 5 张 SQLite 表（thesis_cards / kol_sources / kol_calls / long_term_memory / factor_weights）
- 无现有表结构变更
- 无新增外部依赖包
- 无 API key 新增（KOL key 已在 .env.example 中预留但非必须）
