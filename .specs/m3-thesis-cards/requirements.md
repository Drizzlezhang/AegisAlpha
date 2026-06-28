# Requirements: m3-thesis-cards

<!-- size:all -->
## 功能需求

### FR-1: Thesis 自动创建（推荐→ThesisCard）
- **Given**: Pipeline 输出一个通过 Risk Gate 的 Recommendation，用户确认执行
- **When**: 调用 `ThesisService.create_from_recommendation(recommendation, weight_snapshot)`
- **Then**: 
  - 检查同 ticker 无活跃 Thesis（冷却检查），有则抛出 `ValueError`
  - 从 recommendation 提取 ticker/direction/entry_price/target_price/stop_price/key_assumptions/entry_mode
  - 设置 `entry_date=now(UTC)`, `thesis_valid_status="valid"`, `re_entry_flagged=False`
  - 写入 `factor_snapshot`（从 `state.weight_snapshot` 传入）
  - 调用 `ThesisStore.create()` 持久化，返回新 thesis_id

### FR-2: Thesis 平仓与双维度打分
- **Given**: 一个活跃的 ThesisCard（close_date 为 NULL）
- **When**: 调用 `ThesisService.close_thesis(thesis_id, close_price, judgment_score, execution_score, close_reason)`
- **Then**:
  - 校验 judgment_score/execution_score 在 1-5 范围内
  - 校验 thesis 存在且未平仓
  - 按 direction 计算 P&L：long=(close-entry)/entry, short_put/cc=(entry-close)/entry
  - 更新 thesis_cards 表：close_date, close_price, actual_pnl_pct, judgment_score, execution_score, close_reason
  - 写入 Episodic Memory（含 thesis_id, ticker, direction, entry/close price, pnl, scores, factor_snapshot, key_assumptions, holding_days）
  - 触发 WeightAdapter 重新计算权重
  - 返回 `{thesis_id, pnl_pct, new_weights}`

### FR-3: Thesis 校验状态更新
- **Given**: 一个活跃的 ThesisCard
- **When**: ThesisValidatorAgent 调用 `ThesisService.update_valid_status(thesis_id, new_status, broken_assumptions)`
- **Then**:
  - 校验 new_status ∈ {valid, partial_broken, fully_broken}
  - 已平仓的 thesis 不更新（直接返回）
  - 状态只升不降：valid(0) → partial_broken(1) → fully_broken(2)，回退请求被忽略
  - 如有 broken_assumptions，在 key_assumptions 中对应项前追加 `[BROKEN]` 标记
  - 调用 `ThesisStore.update()` 持久化

### FR-4: Re-entry 检查
- **Given**: 一个 ticker 有已平仓的 ThesisCard
- **When**: 调用 `ThesisService.check_re_entry(ticker)` 或定时 Job 扫描
- **Then**:
  - 若该 ticker 已有活跃 Thesis → 返回 False
  - 查询近 90 天内平仓的 ThesisCard
  - 若平仓 ≥30 天 且 judgment_score ≥3 → 标记 `re_entry_flagged=True`，返回 True
  - 否则返回 False

### FR-5: ThesisStore CRUD
- **Given**: SQLAlchemy AsyncSession factory
- **When**: 调用 ThesisStore 各方法
- **Then**:
  - `create(card_data)` → 创建 ThesisCard 记录，返回 id
  - `get_by_id(thesis_id)` → 返回 ThesisCard 或 None
  - `get_active(ticker=None)` → 返回 close_date IS NULL 的 ThesisCard 列表，可选按 ticker 过滤
  - `get_closed_with_scores()` → 返回已平仓且有双打分的 dict 列表（跨 session 安全）
  - `get_recently_closed(ticker, days)` → 返回指定 ticker 近 N 天平仓的 ThesisCard
  - `get_earliest_card()` → 返回最早创建的 ThesisCard（供观察期检查）
  - `update(thesis_id, data)` → 部分更新字段，自动设置 updated_at
  - `close(thesis_id, close_data)` → 平仓操作（委托给 update）
  - `list_all(filters, limit, offset)` → 支持 status/ticker/direction 过滤 + 分页

### FR-6: ThesisValidatorAgent
- **Given**: 活跃 ThesisCard 列表 + 当前市场数据
- **When**: Agent 在 Pipeline 中执行 `run(state)`
- **Then**:
  - 从 ThesisService 获取所有活跃 Thesis
  - 对每个 Thesis，从 `state.ticker_analyses` 获取当前市场数据
  - 若无当前数据则跳过该 ticker
  - 调用 LLM (mini) 校验每个 key_assumption 是否仍然成立
  - 根据 broken_count 判定新状态：0→valid, ≤半数→partial_broken, >半数→fully_broken
  - 调用 `ThesisService.update_valid_status()` 更新
  - 将校验结果写入 `state.thesis_validation_results`
  - **注意**: 此 Agent 需要 LLM 调用，不能放入 Lightweight Pipeline（零 LLM 约束）。应作为独立 cron job 或放入 Full Pipeline 的 post-processing 阶段

### FR-7: REST API
- **Given**: FastAPI router 挂载到 `/api/v1/thesis`
- **When**: 客户端发送 HTTP 请求
- **Then**:
  - `GET /` → 列出 ThesisCard，支持 status/ticker/direction 过滤 + limit/offset 分页
  - `GET /{thesis_id}` → 获取单个 ThesisCard 详情
  - `POST /` → 手动创建 ThesisCard（罕见场景），返回 201
  - `POST /{thesis_id}/close` → 平仓 + 双维度打分，触发 Memory + WeightAdapter
  - `PATCH /{thesis_id}` → 部分更新（target_price/stop_price/key_assumptions/entry_mode）
  - `GET /{thesis_id}/history` → 获取校验历史（从 Long-term Memory 查询）

### FR-8: Research Manager 冷却检查集成
- **Given**: Research Manager 正在为 ticker 生成推荐
- **When**: 调用 `ThesisService.has_active_thesis(ticker)`
- **Then**:
  - 若返回 True → 跳过该 ticker 的推荐生成（已有活跃 Thesis）
  - 若返回 False → 正常生成推荐
  - 此检查在现有 `_in_cooldown()` 之前执行，作为第一道过滤

### FR-9: APScheduler 集成
- **Given**: APScheduler 常驻进程
- **When**: 到达 cron 触发时间
- **Then**:
  - `thesis_validation` job：每日定时执行 ThesisValidatorAgent，校验所有活跃 Thesis
  - `thesis_re_entry_check` job：每日定时扫描已平仓 ≥30 天的 Thesis，标记 re_entry_flagged

### FR-10: Pipeline 集成 — 自动创建 Thesis
- **Given**: Full Pipeline 执行完毕，用户确认推荐
- **When**: Pipeline runner 的 post-processing hook 执行
- **Then**:
  - 对每个 accepted recommendation 调用 `ThesisService.create_from_recommendation()`
  - 创建结果写入 `state.thesis_cards[ticker]`
  - 冷却冲突等错误不中断 Pipeline，记录到 state.thesis_cards 的 error 字段

## 验收标准与验证方式

| AC | 验证方式 |
|----|---------|
| AC-1: 推荐确认后自动创建 ThesisCard（含 factor_snapshot） | `test_thesis_service.py::test_create_from_recommendation` — mock ThesisStore，验证 create 被调用且参数正确 |
| AC-2: 同标的活跃 Thesis 存在时阻止重复创建 | `test_thesis_service.py::test_create_duplicate_active` — mock get_active 返回已有记录，验证抛出 ValueError |
| AC-3: ThesisValidatorAgent 校验 key_assumptions | `test_thesis_validator_agent.py::test_validate_assumptions` — mock LLMClient 返回 JSON，验证状态判定逻辑 |
| AC-4: thesis_valid_status 单向转换（不回退） | `test_thesis_service.py::test_valid_status_no_rollback` — 尝试 fully_broken→valid，验证状态不变 |
| AC-5: 平仓 P&L 正确计算（long/short_put/cc） | `test_thesis_service.py::test_close_pnl_calculation` — 参数化测试三种方向，验证 pnl_pct |
| AC-6: 平仓后双维度打分写入 | `test_thesis_service.py::test_close_scores_persisted` — 验证 close 调用含 judgment_score + execution_score |
| AC-7: 平仓后写入 Episodic Memory | `test_thesis_service.py::test_close_writes_memory` — mock MemoryService.write，验证 episodic scope 被调用 |
| AC-8: 平仓后触发 WeightAdapter | `test_thesis_service.py::test_close_triggers_weight_adapter` — mock WeightAdapter.update_weights，验证被调用 |
| AC-9: re_entry_flagged 条件判定 | `test_thesis_service.py::test_check_re_entry` — 参数化：≥30天+score≥3→True, <30天→False, 有活跃→False |
| AC-10: REST API 全部端点 | `test_thesis_api.py` — HTTPX async client 测试全部 6 个端点 + 错误场景 |
| AC-11: Research Manager 冷却检查 | `test_research_manager.py::test_active_thesis_cooldown` — mock has_active_thesis 返回 True，验证推荐被跳过 |
| AC-12: ThesisStore CRUD 完整性 | `test_thesis_store.py` — 测试 create/get_by_id/get_active/get_closed_with_scores/update/close/list_all |

<!-- /size:all -->

<!-- size:S+ -->
## 用户故事

- **As a** 交易者, **I want** 每次执行推荐后自动创建 Thesis Card, **So that** 我能追踪每笔交易的完整生命周期和决策依据
- **As a** 交易者, **I want** 平仓时对系统判断和我的执行分别打分, **So that** 系统能区分"判断错了"还是"我执行错了"
- **As a** 交易者, **I want** 系统每日自动校验持仓 Thesis 的假设是否仍然成立, **So that** 我能及时发现逻辑失效的持仓
- **As a** 交易者, **I want** 平仓 30 天后同标的再次出现信号时系统提醒我, **So that** 我不会错过曾经赚钱的机会
- **As a** 开发者, **I want** 通过 REST API 管理 Thesis Cards, **So that** 前端和外部工具能查询和操作 Thesis 数据
<!-- /size:S+ -->

<!-- size:M+ -->
## 非功能需求

### NFR-1: 性能
- ThesisStore 单次查询 ≤ 100ms（SQLite 本地）
- ThesisValidatorAgent 单次 LLM 调用 ≤ 10s（含重试）
- REST API 单端点响应 ≤ 200ms（不含 LLM 调用）

### NFR-2: 可靠性
- ThesisValidatorAgent LLM 调用失败不中断 Pipeline，写入 error_flags
- ThesisStore 数据库操作失败抛出明确异常，由上层 Service 处理
- close_thesis 中 Memory 写入失败不阻断平仓操作（Memory 写入为 best-effort）

### NFR-3: 可测试性
- 所有 LLM 调用通过 LLMClient 接口，测试用 Mock
- 所有 DB 操作通过 ThesisStore 接口，测试用 Mock
- ThesisService 通过依赖注入接收 ThesisStore/MemoryService/WeightAdapter

### NFR-4: 契约兼容性
- 不修改 PipelineState 字段定义（Sprint-0 已冻结，v1.4）
- 不修改 MemoryInterface 签名（Sprint-0 已冻结，v1.1）
- 不修改 ThesisCard 模型字段（Sprint-0 已冻结）
- 不修改 BaseAgent 构造函数签名 `__init__(self, memory, tools, config)`

## 边界场景

### Edge-1: 空活跃 Thesis 列表
- ThesisValidatorAgent 运行时无活跃 Thesis → 直接返回，state.thesis_validation_results 为空 dict

### Edge-2: 同一 ticker 多次推荐
- Pipeline 对同一 ticker 生成多个推荐 → 仅第一个成功创建 ThesisCard，后续因冷却检查被拒绝

### Edge-3: 平仓时 Memory 写入失败
- MemoryService.write("episodic", ...) 抛出异常 → 平仓操作已完成（DB 已更新），Memory 写入失败记录日志但不回滚

### Edge-4: WeightAdapter 更新失败
- WeightAdapter.update_weights() 抛出异常 → close_thesis 应捕获并记录，不阻断平仓结果返回

### Edge-5: key_assumptions 为空列表
- ThesisCard 创建时 key_assumptions=[] → ThesisValidatorAgent 跳过该校验（无假设可校验），状态保持 valid

### Edge-6: 并发平仓
- 同一 thesis 被两次 close 请求 → 第二次请求检测到 close_date 已非 NULL，抛出 ValueError

### Edge-7: ThesisValidatorAgent 与 Lightweight Pipeline 冲突
- 当前 agents.yaml 中 thesis_validator 配置为 `pipeline_mode: lightweight` 且 `llm_dependency: true`
- 这违反了 Lightweight Pipeline 零 LLM 约束
- **解决方案**: 将 thesis_validator 改为 `pipeline_mode: full`，作为独立 cron job 运行（不通过 Lightweight Pipeline）

### Edge-8: 现有 ThesisStore 命名冲突
- `backend/aegis/memory/thesis_store.py` 已存在（WeightAdapter 使用的只读查询接口）
- 新的 CRUD ThesisStore 放在 `backend/aegis/storage/thesis_store.py`
- 两个类通过 import 路径区分，不冲突

### Edge-9: WeightAdapter 接口不匹配
- 现有 `WeightAdapter.update_weights(session: Session)` 是同步方法，需要 SQLAlchemy Session
- `ThesisService.close_thesis()` 需要适配：创建 Session → 调用 sync update_weights → 关闭 Session
- 或为 WeightAdapter 新增 async wrapper

### Edge-10: BaseAgent 构造函数限制
- GraphBuilder 用 `agent_cls(memory={}, tools={}, config={})` 实例化 Agent
- ThesisValidatorAgent 需要 `thesis_service` 和 `llm_client` 作为构造参数
- **解决方案**: ThesisValidatorAgent 不从 BaseAgent 继承，或通过 config dict 传入依赖，或在 `__init__` 中自行创建

## 回滚计划
- 新文件均为独立模块，删除即可回滚
- Research Manager 修改为增量（新增 has_active_thesis 检查），可 feature flag 控制
- agents.yaml 和 schedule.yaml 修改可 revert
- 数据库表 thesis_cards 已由 Sprint-0 创建，无需回滚 DDL

## 数据/权限影响
- 无新增数据库表（thesis_cards 已由 Sprint-0 创建）
- 无新增环境变量
- 无权限变更
<!-- /size:M+ -->

<!-- size:L -->
## Alternatives Considered

### A1: ThesisValidatorAgent 放在 Lightweight vs Full Pipeline
- **方案 A**: 放入 Lightweight Pipeline（当前 agents.yaml 配置）
  - 优点：与 passive health check 一起执行，减少 cron job
  - 缺点：违反 Lightweight Pipeline 零 LLM 约束，需要 LLM 调用
- **方案 B**: 放入 Full Pipeline 的 post-processing 阶段
  - 优点：LLM 调用合规，可复用 Full Pipeline 的市场数据
  - 缺点：Full Pipeline 只跑 active tickers，passive 持仓的 Thesis 不会被校验
- **方案 C**: 独立 cron job（推荐）
  - 优点：不依赖 Pipeline 上下文，可校验所有活跃 Thesis；LLM 调用独立管理
  - 缺点：需要独立的 market data 获取逻辑
- **决策**: 方案 C — 独立 cron job，每日定时执行

### A2: Episodic Memory 写入方式
- **方案 A**: 通过 MemoryService.write("episodic", ...)（当前 dev plan）
  - 缺点：MemoryService 的 episodic scope 是 no-op（不持久化）
- **方案 B**: 通过 LongTermStore 直接写入，标记 data_type="episodic_thesis"
  - 优点：复用现有 LongTermStore，数据实际持久化
- **方案 C**: 扩展 MemoryService 支持 episodic scope
  - 优点：接口语义正确
  - 缺点：需要修改 MemoryInterface 实现（契约层变更）
- **决策**: 方案 B — 通过 LongTermStore 写入，data_type="episodic_thesis"。不修改 MemoryInterface

### A3: ThesisValidatorAgent 依赖注入方式
- **方案 A**: 修改 BaseAgent 构造函数签名
  - 缺点：契约层变更，影响所有 Agent
- **方案 B**: 通过 config dict 传入 thesis_service 和 llm_client
  - 优点：不修改 BaseAgent 签名
  - 缺点：config dict 类型不安全
- **方案 C**: ThesisValidatorAgent 不继承 BaseAgent，独立实现
  - 优点：完全自主的依赖管理
  - 缺点：不能通过 GraphBuilder 自动装配
- **决策**: 方案 C — 独立 Agent 类，通过 cron job 直接调用，不经过 GraphBuilder

## Migration Plan
- 无需数据迁移（thesis_cards 表已存在）
- 无需配置迁移（新增 YAML 条目为增量）
- 部署步骤：
  1. 部署新代码（ThesisService + ThesisStore + ThesisValidatorAgent + API）
  2. 更新 agents.yaml（thesis_validator 改为 pipeline_mode: full, enabled: true）
  3. 更新 schedule.yaml（新增 thesis_validation + thesis_re_entry_check cron jobs）
  4. 重启 APScheduler 进程
  5. 验证：手动创建 Thesis → 等待 cron 触发校验 → API 查询结果

## Observability
- ThesisService 关键操作记录 loguru INFO 日志：create/close/update_valid_status/check_re_entry
- ThesisValidatorAgent 每次校验记录：校验数量、状态变更数量、LLM token 消耗
- close_thesis 记录：PnL、双维度打分、WeightAdapter 更新结果
- REST API 请求通过 FastAPI 内置 access log
- 错误统一写入 state.error_flags（Pipeline 内）或 loguru ERROR（cron job 内）

## 排除范围（Out of Scope）
- 前端 Thesis Cards 管理页面（Branch F）
- KOL post-hoc attribution 数据写入（Branch D）
- WeightAdapter 观察期逻辑修改（Branch B 已实现）
- Memory 存储层修改（Branch A 已实现）
- PipelineState 字段新增/修改
- MemoryInterface 签名变更
- ThesisCard 模型字段变更
- 手动创建无来源 Thesis（必须关联 Recommendation）
- 盘中实时 Thesis 校验（仅每日批量）
<!-- /size:L -->
