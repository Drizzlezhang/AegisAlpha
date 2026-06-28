# Tasks: m3-thesis-cards

<!-- size:all -->
## 任务波次

### Wave 1（无依赖，可并行）

#### T01: 新建 ThesisStore CRUD
- 描述: 创建 `backend/aegis/storage/thesis_store.py`，实现 thesis_cards 表完整 CRUD（AsyncSession）
- read_files: 
  - `backend/aegis/models/thesis.py` (ThesisCard 模型)
  - `backend/aegis/storage/position_store.py` (参考 Store 模式)
  - `backend/aegis/memory/thesis_store.py` (确认现有接口，避免冲突)
- write_files:
  - `backend/aegis/storage/thesis_store.py` (新建)
- verify: `cd backend && python -c "from aegis.storage.thesis_store import ThesisStore; print('OK')"`
- status: done

#### T02: 新建 Thesis 校验 Prompt 模板
- 描述: 创建 `backend/config/prompts/thesis_validation.j2`，用于 LLM 校验 key_assumptions
- read_files:
  - `backend/config/prompts/research_manager_synthesis.j2` (参考 Jinja2 模板风格)
  - `docs/dev-plan/m3-branch-C-thesis-cards.md` 第 2.4 节 (prompt 模板内容)
- write_files:
  - `backend/config/prompts/thesis_validation.j2` (新建)
- verify: `cd backend && python -c "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('config/prompts')); t=env.get_template('thesis_validation.j2'); print('OK')"`
- status: done
<!-- /size:all -->

<!-- size:S+ -->
### Wave 2（依赖 Wave 1）
#### T03: 新建 ThesisService
- 描述: 创建 `backend/aegis/services/thesis_service.py`，实现完整生命周期管理
- depends_on: [T01]
- read_files:
  - `backend/aegis/storage/thesis_store.py` (T01 产物)
  - `backend/aegis/memory/service.py` (MemoryService 接口)
  - `backend/aegis/memory/weight_adapter.py` (WeightAdapter 接口)
  - `backend/aegis/memory/long_term_store.py` (LongTermStore 接口)
  - `backend/aegis/models/thesis.py` (ThesisCard 模型)
  - `docs/dev-plan/m3-branch-C-thesis-cards.md` 第 2.1 节 (ThesisService 参考实现)
- write_files:
  - `backend/aegis/services/__init__.py` (新建或更新)
  - `backend/aegis/services/thesis_service.py` (新建)
- verify: `cd backend && python -c "from aegis.services.thesis_service import ThesisService; print('OK')"`
- status: done

#### T04: 新建 ThesisService 单测
- 描述: 创建 `backend/tests/services/test_thesis_service.py`，覆盖创建/平仓/状态更新/re-entry/冷却检查
- depends_on: [T03]
- read_files:
  - `backend/aegis/services/thesis_service.py` (T03 产物)
  - `backend/aegis/models/thesis.py` (ThesisCard 模型)
  - `backend/aegis/memory/interface.py` (MemoryInterface)
  - `backend/tests/` 现有测试 (参考 mock 模式)
- write_files:
  - `backend/tests/services/__init__.py` (如不存在则新建)
  - `backend/tests/services/test_thesis_service.py` (新建)
- verify: `cd backend && python -m pytest tests/services/test_thesis_service.py -v`
- status: done

<!-- /size:S+ -->

<!-- size:M+ -->
### Wave 3（依赖 Wave 2）

#### T05: 新建 ThesisStore 单测
- 描述: 创建 `backend/tests/storage/test_thesis_store.py`，覆盖 CRUD + 查询过滤 + get_closed_with_scores + get_earliest_card
- depends_on: [T01]
- read_files:
  - `backend/aegis/storage/thesis_store.py` (T01 产物)
  - `backend/aegis/models/thesis.py` (ThesisCard 模型)
  - `backend/tests/storage/` 现有测试 (参考 DB 测试模式)
- write_files:
  - `backend/tests/storage/test_thesis_store.py` (新建)
- verify: `cd backend && python -m pytest tests/storage/test_thesis_store.py -v`
- status: done

#### T06: 新建 ThesisValidatorAgent
- 描述: 创建 `backend/aegis/agents/thesis_validator_agent.py`，独立 Agent 类（不继承 BaseAgent），每日校验活跃 Thesis 的 key_assumptions
- depends_on: [T02, T03]
- read_files:
  - `backend/aegis/services/thesis_service.py` (T03 产物)
  - `backend/aegis/llm/client.py` (LLMClient 接口)
  - `backend/config/prompts/thesis_validation.j2` (T02 产物)
  - `backend/aegis/agents/base.py` (参考 Agent 模式，但不继承)
  - `docs/dev-plan/m3-branch-C-thesis-cards.md` 第 2.3 节 (ThesisValidatorAgent 参考实现)
- write_files:
  - `backend/aegis/agents/thesis_validator_agent.py` (新建)
- verify: `cd backend && python -c "from aegis.agents.thesis_validator_agent import ThesisValidatorAgent; print('OK')"`
- status: done

#### T07: 新建 ThesisValidatorAgent 单测
- 描述: 创建 `backend/tests/agents/test_thesis_validator_agent.py`，覆盖 LLM 校验逻辑 + 状态转换规则
- depends_on: [T06]
- read_files:
  - `backend/aegis/agents/thesis_validator_agent.py` (T06 产物)
  - `backend/tests/agents/` 现有测试 (参考 Agent 测试 mock 模式)
- write_files:
  - `backend/tests/agents/test_thesis_validator_agent.py` (新建)
- verify: `cd backend && python -m pytest tests/agents/test_thesis_validator_agent.py -v`
- status: done

### Wave 4（依赖 Wave 2）

#### T08: 新建 REST API 路由
- 描述: 创建 `backend/aegis/api/routes/thesis.py`，实现 6 个端点（列表/详情/创建/平仓/更新/历史）
- depends_on: [T03]
- read_files:
  - `backend/aegis/services/thesis_service.py` (T03 产物)
  - `backend/aegis/api/routes/weights.py` (参考路由模式 + Session 管理)
  - `backend/aegis/api/deps.py` (依赖注入模式)
  - `docs/dev-plan/m3-branch-C-thesis-cards.md` 第 2.5 节 (REST API 参考实现)
- write_files:
  - `backend/aegis/api/routes/thesis.py` (新建)
- verify: `cd backend && python -c "from aegis.api.routes.thesis import router; print('OK')"`
- status: done

#### T09: 新建 REST API 单测
- 描述: 创建 `backend/tests/api/test_thesis_api.py`，覆盖全部 6 个端点 + 错误处理 + 分页
- depends_on: [T08]
- read_files:
  - `backend/aegis/api/routes/thesis.py` (T08 产物)
  - `backend/tests/api/` 现有测试 (参考 API 测试模式)
- write_files:
  - `backend/tests/api/test_thesis_api.py` (新建)
- verify: `cd backend && python -m pytest tests/api/test_thesis_api.py -v`
- status: done

### Wave 5（依赖 Wave 2+3+4，集成）

#### T10: Research Manager 冷却检查集成
- 描述: 修改 `backend/aegis/agents/research_manager_agent.py`，在 `_synthesize()` 中新增 `has_active_thesis()` 检查
- depends_on: [T03]
- read_files:
  - `backend/aegis/agents/research_manager_agent.py` (现有代码)
  - `backend/aegis/services/thesis_service.py` (T03 产物)
- write_files:
  - `backend/aegis/agents/research_manager_agent.py` (修改)
- verify: `cd backend && python -m pytest tests/agents/ -k "research_manager" -v`
- status: done

#### T11: Pipeline runner 集成 — 自动创建 Thesis
- 描述: 修改 `backend/aegis/pipeline/runner.py`，新增 `_post_recommendation_hook()` 自动创建 ThesisCard
- depends_on: [T03]
- read_files:
  - `backend/aegis/pipeline/runner.py` (现有代码)
  - `backend/aegis/services/thesis_service.py` (T03 产物)
- write_files:
  - `backend/aegis/pipeline/runner.py` (修改)
- verify: `cd backend && python -c "from aegis.pipeline.runner import run_full; print('OK')"`
- status: done

#### T12: 注册 API router + 更新 deps
- 描述: 修改 `backend/aegis/api/app.py` 注册 thesis router，修改 `backend/aegis/api/deps.py` 添加 `get_thesis_service()` 工厂函数
- depends_on: [T08]
- read_files:
  - `backend/aegis/api/app.py` (现有 router 注册)
  - `backend/aegis/api/deps.py` (现有依赖注入)
  - `backend/aegis/api/routes/thesis.py` (T08 产物)
- write_files:
  - `backend/aegis/api/app.py` (修改)
  - `backend/aegis/api/deps.py` (修改)
- verify: `cd backend && python -c "from aegis.api.app import app; print('OK')"`
- status: done

#### T13: 更新 agents.yaml + schedule.yaml
- 描述: 修改 `backend/config/agents.yaml`（thesis_validator 改为 pipeline_mode: full, enabled: true），修改 `backend/config/schedule.yaml`（新增 thesis_validation + thesis_re_entry_check cron jobs）
- depends_on: [T06]
- read_files:
  - `backend/config/agents.yaml` (现有配置)
  - `backend/config/schedule.yaml` (现有配置)
- write_files:
  - `backend/config/agents.yaml` (修改)
  - `backend/config/schedule.yaml` (修改)
- verify: `cd backend && python -c "import yaml; yaml.safe_load(open('config/agents.yaml')); yaml.safe_load(open('config/schedule.yaml')); print('OK')"`
- status: done

#### T14: 集成测试 — Thesis 完整生命周期
- 描述: 创建 `backend/tests/integration/test_thesis_lifecycle.py`，端到端测试：创建 → 校验 → 平仓 → Memory → WeightAdapter
- depends_on: [T03, T06, T08]
- read_files:
  - `backend/aegis/services/thesis_service.py` (T03 产物)
  - `backend/aegis/agents/thesis_validator_agent.py` (T06 产物)
  - `backend/aegis/api/routes/thesis.py` (T08 产物)
  - `backend/tests/integration/` 现有测试 (参考集成测试模式)
- write_files:
  - `backend/tests/integration/test_thesis_lifecycle.py` (新建)
- verify: `cd backend && python -m pytest tests/integration/test_thesis_lifecycle.py -v`
- status: done

#### T15: 集成测试 — Thesis + Memory 集成
- 描述: 创建 `backend/tests/integration/test_thesis_memory_integration.py`，验证平仓后 Episodic Memory 写入 + WeightAdapter 触发
- depends_on: [T03]
- read_files:
  - `backend/aegis/services/thesis_service.py` (T03 产物)
  - `backend/aegis/memory/long_term_store.py` (LongTermStore)
  - `backend/aegis/memory/weight_adapter.py` (WeightAdapter)
- write_files:
  - `backend/tests/integration/test_thesis_memory_integration.py` (新建)
- verify: `cd backend && python -m pytest tests/integration/test_thesis_memory_integration.py -v`
- status: done

#### T16: 全量回归测试
- 描述: 运行全部测试套件，确保无回归
- depends_on: [T04, T05, T07, T09, T10, T11, T12, T13, T14, T15]
- read_files: []
- write_files: []
- verify: `cd backend && python -m pytest tests/ -v --tb=short && ruff check aegis/ && ruff format --check aegis/ && mypy aegis/ --ignore-missing-imports`
- status: done

## 风险任务

| 任务 | 风险 | 前置条件 | 额外验证 |
|------|------|---------|---------|
| T03 (ThesisService) | WeightAdapter 同步接口适配 | 确认 `asyncio.to_thread()` 可用 | 手动测试 close_thesis 触发 WeightAdapter |
| T06 (ThesisValidatorAgent) | 独立 market data 获取 | 确认 Tool Registry 可用 | 手动测试 LLM 校验流程 |
| T10 (Research Manager) | 冷却检查影响现有推荐流程 | 回归测试通过 | 对比修改前后推荐数量 |
| T11 (Pipeline runner) | 自动创建 Thesis 可能影响 Pipeline 性能 | runner 现有测试通过 | 测量 Pipeline 总耗时变化 |

## 回滚任务
- 若 T10 导致推荐数量异常下降：revert `research_manager_agent.py` 修改，保留其他文件
- 若 T11 导致 Pipeline 超时：将 `_post_recommendation_hook` 改为异步非阻塞
- 若 T03 close_thesis 中 WeightAdapter 调用失败：改为仅记录日志，由定时 cron job 统一更新
- 全部回滚：删除所有新建文件 + `git checkout` 修改文件 + revert YAML 配置
<!-- /size:M+ -->

<!-- size:L -->
## Alternatives Considered

### 任务拆分粒度
- **方案 A**: 按文件拆分（当前方案）— 每个文件一个任务，依赖清晰
- **方案 B**: 按功能拆分（创建/平仓/校验各一个任务）— 跨文件，依赖复杂
- **决策**: 方案 A，每个任务对应 1-2 个文件，verify 命令明确

### Wave 顺序
- **方案 A**: Store → Service → Agent/API → Integration（当前方案）
- **方案 B**: Store + Service → Agent → API → Integration（Agent 和 API 并行）
- **决策**: 方案 A，Agent 和 API 都依赖 Service，可并行（Wave 3 和 Wave 4）

## Migration Plan
1. 按 Wave 顺序执行：Wave 1 → Wave 2 → Wave 3+4 (并行) → Wave 5
2. 每个 Wave 完成后运行该 Wave 的 verify 命令
3. Wave 5 完成后运行 T16 全量回归
4. 部署顺序：代码部署 → YAML 配置更新 → 重启 APScheduler → 验证

## Observability
- T03: ThesisService 关键方法添加 loguru INFO 日志
- T06: ThesisValidatorAgent 添加校验数量/状态变更/LLM token 消耗日志
- T08: REST API 通过 FastAPI 内置 access log
- T11: Pipeline runner hook 添加创建成功/失败计数日志
- T16: 全量回归测试输出覆盖率报告
<!-- /size:L -->
