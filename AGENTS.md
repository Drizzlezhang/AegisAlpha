# AGENTS.md — Aegis 2.0 Engineering Constitution

> **作用域**：整个 Aegis 2.0 工程的全局开发规范。所有分支、所有子 Agent、所有 PR 都必须遵循。
> **位置**：仓库根目录 `/AGENTS.md`
> **优先级**：本文件优先于任何分支文档；如有冲突以本文件为准；如本文件需要修改，必须发起独立 PR 并由 owner 评审。
> **版本**：v1.2（与 PRD v1.2 / tech-arch v1.2 同步；新增 Smart Money / Fund Flow / Options Strategist 升级、Agent Registry、Dual Pipeline、entry_mode、双维度反馈等约束）

---

## 1. 项目背景（每个 Agent 上下文必读）

Aegis 2.0 是一个**个人美股/期权交易决策辅助系统**,定位为「顾问」而非「执行者」。系统每日盘前 + 盘后两次批处理 Pipeline,输出结构化推荐到 Telegram,用户自行执行交易并回填结果,系统通过 Thesis Cards 形成反馈闭环。

### 1.1 核心交易策略上下文（v1.2 已与 PRD 对齐）

| 策略 / 仓位 | entry_mode | 说明 |
|---|---|---|
| QQQ 主仓正股 | `passive` | 长期持有,不主动择时;只跑 **Lightweight Pipeline**(规则巡检+健康分),不进 Full 推理 |
| QQQ LEAPS Call | `active_left` / `active_right` | 10–30% OTM,DTE 12 个月+,最多持 6 个月,**不 roll 只平仓**;支持左侧分批抄底 + 右侧趋势确认跟随两种入场范式 |
| Covered Call (CC) | `cc` | 仅在「震荡 + 阻力 + 高 IV」三条件同时满足时卖;受 Risk Gate 拦截 |
| Sell Put | `sell_put` | 暂时不主推,框架预留 |

**核心场景**:用户的 LEAPS Buy Call 90% 走左侧分批抄底/右侧趋势跟随两种范式,系统必须能区分并匹配对应的入场/止损/批次策略。

### 1.2 用户**不做**的事(黑名单约束)

- meme 股、小市值、中概股
- 短期 Buy Call(**所有 Call 均为 LEAPS**)
- 赌财报方向
- 盘中监控/推送(Lightweight Pipeline 是「定时巡检」不是「实时盯盘」)
- LEAPS roll
- 移动端适配(支持 iPad 横屏即可)
- 多用户/认证

### 1.3 关联文档(修改前必读)

- `docs/2.0-prd.md` — 产品需求文档(**v1.2**)
- `docs/tech-arch.md` — 技术架构文档(**v1.2**)
- `docs/design.md` — **前端设计规范**(**v1.0**,前端开发必读)

---

## 2. 技术栈(不允许擅自更换)

| 层 | 技术 | 版本约束 |
|---|---|---|
| 编排框架 | LangGraph + LangChain Core | ≥0.2 / ≥0.3 |
| LLM 网关 | new-api 中转站(OpenAI 兼容协议) | 最多 3 个模型,通过 model 参数切换 |
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0 | Python 3.11 / 3.12 |
| 包管理 | **uv**(不接受 pip / poetry / conda) | latest |
| 数据库 | SQLite(业务) + ChromaDB(向量) + Parquet(行情) | — |
| 迁移 | Alembic | ≥1.13 |
| 调度 | APScheduler 常驻进程(**Full + Lightweight + trigger_check 三套 cron**) | ≥3.10 |
| 推送 | python-telegram-bot v20+ | 单向推送,无双向交互 |
| HTTP | httpx (async) | ≥0.27 |
| 重试 | tenacity | ≥8.3 |
| 日志 | loguru | ≥0.7 |
| 配置 | pydantic-settings + YAML(Jinja2 for prompts) | — |
| CLI | **Typer**(含 `aegis scaffold agent/tool` 子命令) | ≥0.12 |
| 前端 | Next.js App Router + Tailwind + shadcn/ui | 15 / v4 |
| 图表 | Recharts | latest |
| 表格 | TanStack Table v8 | — |
| DAG | ReactFlow | latest |
| 测试 | pytest + pytest-asyncio + pytest-mock | ≥8 |
| Lint | ruff + mypy | latest |

**违反清单**:
- ✗ requests(用 httpx)
- ✗ logging 标准库(用 loguru)
- ✗ Pydantic v1(必须 v2)
- ✗ openai SDK 直接调用(必须通过 `aegis.llm.client.LLMClient`)
- ✗ 手写 Graph 装配代码(M2+ 必须走 `aegis.registry.graph_builder`,禁止 hardcode StateGraph 节点)

---

## 3. 仓库结构与文件位置规范

```
aegis/
├── AGENTS.md                       # 本文件(全局规范)
├── README.md                       # 项目入口(快速开始)
├── Makefile
├── docker-compose.yml
├── .gitignore
├── .env.example                    # 根级别引用 backend/.env
├── docs/
│   ├── prd.md            # v1.2
│   ├── tech-arch.md      # v1.2
│   └── sprints/m{N}/               # 每个 Milestone 的开发文档
├── backend/                        # Python 后端
│   ├── pyproject.toml
│   ├── aegis/                      # 主包
│   │   ├── agents/                 # 15 个 Agent(含 Smart Money / Fund Flow / Options Strategist)
│   │   │   ├── base.py             # BaseAgent + AgentManifest 引用
│   │   │   ├── smart_money_agent.py
│   │   │   ├── fund_flow_agent.py
│   │   │   ├── options_strategist_agent.py
│   │   │   ├── passive_health_check_agent.py
│   │   │   └── ...
│   │   ├── registry/               # 【M2+ 新增】Tool + Agent Registry
│   │   │   ├── tool_registry.py
│   │   │   ├── agent_registry.py
│   │   │   └── graph_builder.py    # manifest-driven 装配
│   │   ├── calculators/            # 纯计算模块(无 LLM、无 IO)
│   │   ├── memory/                 # 四层 Memory 系统
│   │   ├── tools/                  # Tool Adapters + 分类子包
│   │   │   ├── flows/              # 资金流(ETF / Sector / Smart Money)
│   │   │   ├── liquidity/          # 宏观流动性(ON RRP / TGA / DFII10 / DXY)
│   │   │   ├── options_chain/      # OI / GEX / Unusual Whales
│   │   │   └── ...
│   │   ├── pipeline/               # State + Graph + Runner
│   │   │   ├── state.py            # PipelineState(v1.2 schema)
│   │   │   ├── graph_full.py       # Full Pipeline 装配入口
│   │   │   ├── graph_lightweight.py # Lightweight Pipeline
│   │   │   ├── router.py           # 按 entry_mode 分流
│   │   │   └── trigger_runner.py   # pending_triggers 小时巡检
│   │   ├── models/                 # SQLAlchemy 模型(含 positions.entry_mode / pending_triggers / thesis_cards v1.2 字段)
│   │   ├── api/                    # FastAPI 路由
│   │   ├── llm/                    # LLM 客户端封装
│   │   ├── notifier/               # Telegram 推送(含 Lightweight / Trigger 前缀)
│   │   ├── utils/                  # circuit_breaker / retry / logging / settings
│   │   └── cli.py                  # Typer 入口(含 `scaffold` 子命令)
│   ├── config/
│   │   ├── tools.yaml              # Tool Registry 配置(含 tags 字段)
│   │   ├── agents.yaml             # Agent manifest 配置(权重 + 模型 + parallel_group + pipeline_mode)
│   │   ├── rules.yaml              # 交易规则配置(含 delta_dollars_budget / dynamic_stop_loss 等)
│   │   ├── schedule.yaml           # APScheduler 配置(full / lightweight / trigger_check)
│   │   └── prompts/                # Jinja2 prompt 模板
│   ├── alembic/                    # 数据库迁移
│   ├── data/                       # SQLite + Parquet + ChromaDB 数据(git ignore)
│   └── tests/
│       ├── foundation/             # Sprint-0 契约测试(含 AgentManifest schema)
│       ├── tools/                  # 分支 A
│       ├── calculators/            # 分支 B
│       ├── agents/                 # 各 Agent 单测(含新增 3 Agent)
│       ├── registry/               # 【新增】graph_builder / manifest 装配测试
│       ├── integration/            # Agent 间集成(含 Full + Lightweight 联调)
│       ├── e2e/                    # 端到端
│       └── fixtures/               # 共享测试数据
├── frontend/                       # Next.js 前端(M2 起开始填充)
└── scripts/                        # 一次性脚本(数据迁移、smoke test)
```

### 文件归属规则

| 文件类型 | 必须位置 |
|---|---|
| SQLAlchemy 模型 | `backend/aegis/models/{domain}.py` |
| LangGraph Agent | `backend/aegis/agents/{agent_name}.py` |
| **AgentManifest 定义** | Agent 文件内 class-level `manifest: AgentManifest = ...` |
| 纯计算函数 | `backend/aegis/calculators/{module}.py` |
| 外部数据源 Adapter | `backend/aegis/tools/{category}/{source}.py` |
| **Registry 模块** | `backend/aegis/registry/{tool,agent,graph_builder}.py` |
| Prompt 模板 | `backend/config/prompts/{purpose}_{role}.j2` |
| 业务配置 | `backend/config/*.yaml`(**进 git**) |
| 密钥/Token | `backend/.env`(**不进 git**) |
| 测试 fixture | `backend/tests/fixtures/{ticker}_{period}.{ext}` |

---

## 4. 契约层(**冻结**,修改需 owner 评审)

### 4.1 PipelineState Schema

- 文件:`backend/aegis/pipeline/state.py`
- 修改规则:**新增字段允许**(添加 `Optional` + 默认值),**删除/重命名禁止**
- v1.2 已新增字段(向后兼容,不破坏 M1 代码):
  - `pipeline_mode: Literal["full","lightweight"] = "full"`
  - `tickers_holdings_active: list[str] = []`
  - `tickers_holdings_passive: list[str] = []`
  - `entry_mode: dict[str, Literal["passive","active_left","active_right","cc","sell_put"]] = {}`
  - `extensions: dict[str, dict[str, Any]] = {}` — **新 Agent 写自己产出的指定槽位**
  - `pending_triggers: list[PendingTrigger] = []`
  - `passive_health_alerts: list[HealthAlert] = []`
  - `health_scores: dict[str, float] = {}`
  - `delta_dollars_delta: float = 0.0`
- 任何变更必须同步更新 `docs/tech-arch.md` 4.1 节

### 4.2 BaseAgent 接口

- 文件:`backend/aegis/agents/base.py`
- 抽象方法签名禁止变更:`async def run(self, state: PipelineState) -> PipelineState`
- v1.2 新增类级别属性(强制):`manifest: ClassVar[AgentManifest]` — 任何新 Agent 必须声明
- v1.2 新增 helper 方法:`write_extension(state, key, value)` / `read_extension(state, key)` — 写自定义产出请走 extensions slot,**禁止往 state 上直接挂未声明字段**

### 4.3 MemoryInterface

- 文件:`backend/aegis/memory/interface.py`
- 5 个方法签名冻结:`read / write / search / summarize / archive_scratchpad`
- v1.2 不变,长期记忆新增 `kol_post_hoc_attribution` / `judgment_vs_execution_breakdown` 由 WeightAdapter 通过现有接口写入

### 4.4 BaseTool + ToolResult

- 文件:`backend/aegis/tools/base.py`
- `ToolResult` 字段冻结:`success / data / error / source / cached`
- v1.2 新增 Tool 注册要求:`tags: list[str]`(用于 Agent 按能力检索 Tool)

### 4.5 LLMClient

- 文件:`backend/aegis/llm/client.py`
- 所有 LLM 调用必须通过此客户端,**不允许直接 import openai SDK**

### 4.6 【v1.2 新增】AgentManifest 契约

- 文件:`backend/aegis/registry/agent_registry.py`
- AgentManifest 字段冻结:
  - `name: str` — 唯一 ID(对应 `agents.yaml` key)
  - `version: str` — 语义化版本
  - `requires: list[str]` — 依赖的 state 字段或上游 Agent 输出 key
  - `provides: list[str]` — 写入 state 的字段或 extensions key
  - `tags: list[str]` — 能力标签(如 `["signal","options","macro"]`)
  - `llm_dependency: bool` — 是否需要 LLM(决定能否进 Lightweight Pipeline)
  - `parallel_group: Optional[str]` — 同组 Agent 可并行执行
  - `pipeline_mode: Literal["full","lightweight","both"]`
  - `enabled: bool = True`
- 修改 AgentManifest schema 必须 `[CONTRACT]` 前缀 PR + owner 评审

---

## 5. 编码规范

### 5.1 Python 通用

- **类型注解强制**:所有公开函数、类方法必须有完整 type hints(参数 + 返回值)
- **Pydantic v2 优先**:业务模型、配置、API 入参出参用 Pydantic,不用 dataclass / dict
- **async/await 一致性**:IO/LLM 调用必须 async;纯计算保持 sync
- **不允许全局可变状态**:通过依赖注入(Agent 构造接收 memory/tools/config)
- **行长 100 列**(ruff 默认)
- **import 顺序**:标准库 → 第三方 → 本地,ruff isort 自动整理
- **写 state 必须走 helper**:新 Agent 写自定义产出走 `self.write_extension(state, key, value)`,禁止 `state.foo = bar` 给未声明字段

### 5.2 命名

| 类型 | 规范 | 示例 |
|---|---|---|
| 模块文件 | snake_case | `smart_money_agent.py` |
| 类 | PascalCase + Agent 后缀 | `SmartMoneyAgent` |
| 函数 | snake_case,动词开头 | `compute_smart_money_score` |
| 常量 | UPPER_SNAKE_CASE | `MAX_DELTA_BUDGET_PCT = 0.30` |
| 私有 | 单下划线前缀 | `_check_iv_crush` |
| YAML key | snake_case | `failure_threshold` |
| Manifest tag | snake_case | `smart_money`, `fund_flow`, `options_strategy` |
| DB 表 | snake_case 复数 | `thesis_cards`, `pending_triggers` |
| DB 字段 | snake_case 单数 | `entry_thesis`, `entry_mode`, `judgment_score` |

### 5.3 错误处理

- **业务层禁止裸 except**:必须捕获具体异常或使用 `except Exception as e: logger.exception(...)`
- **Agent 内异常不外抛**:写入 `state.error_flags`,Pipeline 继续
- **Tool 异常不外抛**:返回 `ToolResult(success=False, error=...)`
- **LLM 异常**:tenacity 重试 1 次后,写入 error_flags,跳过该 Agent
- **Lightweight Pipeline 容错**:任何单 Agent 失败不阻断巡检,在 Telegram 加 ⚠️ 标记继续

### 5.4 日志规范

- 使用 loguru,不用标准 logging
- 级别约定:
  - `DEBUG` — 中间计算结果、prompt 内容
  - `INFO` — Agent 启动/完成、推荐生成
  - `WARNING` — Fallback 触发、数据 stale、Lightweight 健康分降级
  - `ERROR` — Agent 失败、Tool 不可用(同步推 Telegram)
  - `CRITICAL` — Pipeline 整体失败 / Delta 预算超限拦截
- 错误日志必须 `logger.exception(...)` 保留 traceback

### 5.5 注释与 docstring

- 所有公开函数/类必须有 docstring(Google 风格)
- 契约层文件首行必须标注:`"""Frozen at M{N}. Changes require owner review."""`
- 复杂算法(Wyckoff / GEX / WeightAdapter / DeltaBudget / SmartMoneyScore)必须有算法说明注释
- 每个 Agent 类必须有 `manifest` class-level 字段 + 紧邻的 module docstring 说明输入输出

### 5.6 前端规范（强制）

- **所有前端代码必须遵循 `docs/design.md`**,该文件是前端视觉风格的唯一权威
- 颜色引用必须走 `--aegis-*` CSS 变量或 `aegis-*` Tailwind class,**禁止 hardcode hex/hsl 值**
- 组件优先复用 shadcn/ui + 自定义覆盖主题,禁止引入额外 UI 库（如 Ant Design / Chakra / MUI）
- 图标仅使用 Lucide Icons,禁止混用其他图标库
- 信号色(bull/bear/neutral/blocked)必须语义使用,不得自行发明涨跌配色
- 图表配色走 `frontend/lib/design-tokens.ts` 中的 `CHART_COLORS` 常量
- 不支持 < 768px 屏宽,无需做移动端适配
- 每个前端 PR 合并前必须通过 Design System 质量检查清单(见 design.md Section 11)

---

## 6. Git 工作流

### 6.1 分支策略

- `main` — 受保护,仅由 release PR 合入
- `develop` — 集成分支,所有功能分支基于此分出
- `feat/m{N}-{branch-name}` — 功能分支(如 `feat/m2-smart-money`)
- `fix/{issue}` — 修复分支
- `chore/{topic}` — 杂项(CI、文档)

### 6.2 Commit 规范

采用 Conventional Commits:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

| type | 用途 |
|---|---|
| feat | 新功能 |
| fix | 修复 |
| refactor | 重构(无行为变更) |
| test | 测试新增/修改 |
| docs | 文档 |
| chore | 构建、依赖、CI |
| perf | 性能 |

scope 用模块名:`feat(tools): add unusual_whales adapter`、`feat(agents): add smart_money_agent`、`feat(registry): manifest-driven graph builder`

### 6.3 PR 规范

每个 PR 必须:
1. 关联一个分支文档(`docs/sprints/m{N}/branch-X-*.md`)
2. 通过对应 `tests/{domain}/` 测试
3. 通过 `ruff check` + `ruff format --check` + `mypy`
4. 不引入未在 `pyproject.toml` 声明的依赖
5. 不修改契约层(除非 PR 标题含 `[CONTRACT]` 并 owner 评审)
6. 不提交 `.env` / `data/` / `__pycache__/`
7. PR 描述模板见 `.github/PULL_REQUEST_TEMPLATE.md`
8. **新增 Agent 必须同时提交 `agents.yaml` manifest 注册 + 单测**;**新增 Tool 必须同时提交 `tools.yaml` 注册(含 tags)+ 单测**

### 6.4 合并策略

- Squash merge(保持 develop 历史线性)
- 分支合并 develop 前必须先 rebase 最新 develop

---

## 7. 测试规范

### 7.1 测试金字塔

| 层 | 占比 | 位置 |
|---|---|---|
| 单测 | 70% | `tests/{domain}/test_*.py` |
| 集成 | 20% | `tests/integration/` |
| E2E | 10% | `tests/e2e/` |

### 7.2 强制单测清单(**必须 100% 通过才能合并**)

| 模块 | 必测项 |
|---|---|
| `calculators/greeks.py` | Call/Put 各 3 边界 case |
| `calculators/stop_loss.py` | PRD 8.1 全部 stop_loss 场景(含 v1.2 支撑位动态止损) |
| `calculators/delta_budget.py` | 增量预算超限 / 临界 / 充足 3 case(v1.2 新增) |
| `agents/risk_gate_agent.py` | 7 规则 + Δ 预算 + IV crush 共 ≥10 case |
| `agents/smart_money_agent.py` | 高分位 / 中性 / 低分位 + 数据缺失 fallback 共 ≥4 case(v1.2) |
| `agents/fund_flow_agent.py` | ETF 净流入 / 流出 / sector rotation 至少 3 case(v1.2) |
| `agents/options_strategist_agent.py` | 左侧分批 / 右侧跟随 / CC / 数据不足 各 1 case(v1.2) |
| `agents/passive_health_check_agent.py` | 健康 / 预警 / 严重背离 3 case(v1.2) |
| `registry/graph_builder.py` | manifest 装配 / 缺失依赖报错 / parallel_group 并行 共 3 case(v1.2) |
| `utils/circuit_breaker.py` | 三态转换 3 case |
| `agents/debate_agent.py` | 提前结束 + 跑满 + JSON 解析失败 共 3 case |

### 7.3 测试约定

- 文件名 `test_{module}.py`
- 函数名 `test_{behavior}_{scenario}`(例:`test_smart_money_score_high_percentile_buy_bias`)
- 使用 `pytest.approx` 比较浮点
- LLM 调用必须用 `MockLLMClient`,禁止真实 API 调用
- Tool 调用必须用 Mock,禁止真实外部请求
- 异步测试用 `pytest-asyncio` 的 `@pytest.mark.asyncio`
- fixture 共享放 `tests/fixtures/`,加载用 `pytest fixture`
- **Lightweight Pipeline 集成测试必须验证「不调用任何 LLMClient」**(用 mock spy)

### 7.4 覆盖率目标

- M1:≥60%
- M2:≥70%
- M3+:≥80%

---

## 8. 配置与密钥

### 8.1 环境变量(`.env`)

仅用于密钥与环境差异。所有 key 在 `.env.example` 中提供模板。

**核心字段**:

```bash
# LLM
LLM_BASE_URL=https://your-new-api-gateway/v1
LLM_API_KEY=sk-xxx
LLM_MODEL_PRIMARY=gpt-4o
LLM_MODEL_MINI=gpt-4o-mini

# 券商
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
LONGBRIDGE_APP_KEY=
LONGBRIDGE_APP_SECRET=
LONGBRIDGE_ACCESS_TOKEN=
TIGER_PRIVATE_KEY=
TIGER_TIGER_ID=

# 数据源 — 基础
ALPHA_VANTAGE_API_KEY=
FRED_API_KEY=
TAVILY_API_KEY=
STOCKTWITS_ACCESS_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
X_BEARER_TOKEN=

# 数据源 — v1.2 新增
UNUSUAL_WHALES_API_KEY=
MARKET_CHAMELEON_API_KEY=
BARCHART_API_KEY=
FINVIZ_API_KEY=
# ETF Flows / Sector Flows / CBOE 数据通常走免费源或合并到 Alpha Vantage / FRED,见 tools.yaml

# 推送
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 路径
DATA_DIR=./data
CHROMA_PERSIST_DIR=./data/chroma
```

### 8.2 业务配置(`config/*.yaml`)

- 进 git
- 修改需要 PR + 评审
- 加载用 PyYAML safe_load
- 校验用 Pydantic 模型
- **`tools.yaml` 必须含 `tags` 字段**;**`agents.yaml` 必须含每个 Agent 的 manifest 字段映射(parallel_group / pipeline_mode / llm_dependency)**

### 8.3 Prompt 模板(`config/prompts/*.j2`)

- 进 git
- Jinja2 v3 语法
- 文件首行注释标注「Frozen at M{N} v{X}」
- 修改 Debate prompt 必须保留 Judge JSON schema 完整性
- v1.2 新增 prompt:`options_strategist_left_entry.j2` / `options_strategist_right_follow.j2` / `smart_money_synthesis.j2`

---

## 9. Memory 系统使用约束

### 9.1 四层访问规则

| 层 | Agent 何时用 |
|---|---|
| Working | Pipeline 内 Agent 间传递推理过程(写 Scratchpad / state.extensions) |
| Short-term | 引用近期分析(如前次 Debate 结论、上一次 Smart Money 评分) |
| Long-term | 因子权重历史、KOL 历史表现、统计摘要、**双维度(judgment / execution)历史分** |
| Episodic | Thesis Cards 完整生命周期(含 entry_mode / re_entry_flagged / thesis_valid_status) |

### 9.2 接口使用

- **所有 Agent 通过 `MemoryInterface` 访问**,禁止直接操作 SQLite/ChromaDB
- Scratchpad 写入必须人类可读(不是 JSON dump)
- 长期数据写入必须指定 TTL 或显式标记永久
- **WeightAdapter 必须分别更新 judgment_score 与 execution_score 两个维度**,不能合并成单一打分

### 9.3 观察期约束(首 30 天)

- WeightAdapter 必须先检查 `_is_in_observation_period()`
- 观察期内 Thesis Card 照常生成、用户照常打分(双维度),但权重不更新
- 观察期结束后历史数据**回填**进入权重计算(不丢弃)
- v1.2 新增:KOL post-hoc attribution 在观察期内也持续记录,仅在观察期结束后启动调权

---

## 10. Tool Registry 使用约束

### 10.1 调用规则

- 所有外部数据源访问必须通过 `tools.get(name).fetch(**kwargs)` 或 `tools.find_by_tag(tag)`
- 禁止在 Agent 内 import 具体 Tool 类
- 禁止在 Agent 内直接 import httpx 调用外部 API

### 10.2 新增 Tool 流程

1. 实现 `BaseTool` 子类(位于 `backend/aegis/tools/{category}/{source}.py`)
2. 在 `config/tools.yaml` 注册,**必须含**:`name / class / category / tags / fallback / circuit_breaker / rate_limit / bound_agents`
3. 编写 `tests/tools/test_{name}.py`(含 fixture-based mock + circuit_breaker 测试)
4. 文档:在 PR 描述中说明数据契约 + 响应 schema 样例
5. 若新增 v1.2 类别(flows / liquidity / options_chain),必须在 `tools.yaml` 的 `categories` section 注册类别名

---

## 11. LLM 调用约束

### 11.1 模型选择

| 用途 | 模型 |
|---|---|
| Debate Bull/Bear | `LLM_MODEL_PRIMARY`(默认 gpt-4o) |
| Debate Judge | `LLM_MODEL_MINI`(默认 gpt-4o-mini) |
| 各 LLM Analyst(M2+) | `LLM_MODEL_MINI` |
| Smart Money / Fund Flow 综合判断 | `LLM_MODEL_MINI` |
| Options Strategist S2 | `LLM_MODEL_PRIMARY`(决策路径关键) |
| Research Manager / Portfolio Orchestrator | `LLM_MODEL_PRIMARY` |
| 摘要、压缩 | `LLM_MODEL_MINI` |

### 11.2 调用规范

- 必须通过 `aegis.llm.client.LLMClient`
- 必须从 `config/prompts/*.j2` 加载模板,**禁止 hardcode prompt**
- temperature 默认 0.7,Judge 用 0.3,Strategist 用 0.5
- 结构化输出用 `response_format="json"`,必须 schema 校验
- 失败重试 1 次,仍失败写 error_flag
- **Lightweight Pipeline 内所有 Agent 必须 `llm_dependency=False`**;若新 Agent 需要 LLM,只能进 Full Pipeline

### 11.3 成本意识

- 每个 Agent 的 token 消耗写入 `agent_runs.token_used`
- 重复 prompt 应使用 short-term cache(M2+ 实现)
- Lightweight Pipeline 不消耗 token(零 LLM 调用是设计目标)

---

## 12. 风控约束(系统级硬规则)

以下规则在 Risk Gate Agent 实现,**任何 Agent 输出都必须经过 Risk Gate**:

| 规则 | 拦截 |
|---|---|
| 总仓位 > 80% | 阻止 buy/add |
| 现金 < 20% | 阻止 buy/add |
| 黑名单标的 | 阻止任何推荐 |
| LEAPS DTE < 12 个月 | 阻止 LEAPS Call 新建仓 |
| VIX > 30 或日涨幅 > 20% | 阻止所有新建仓 |
| FOMC/CPI/NFP 前 24h | 阻止 LEAPS Call 新建仓 |
| 标的财报前 48h | 阻止该标的新建仓 |
| **Δ Dollars 单日增量 > NAV × 30%**(v1.2) | 拦截超额部分,按优先级保留高分推荐 |
| **IV crush guard**(v1.2):标的 IV 分位 > 90 且推荐为 LEAPS Buy | 标记警告(不一定拦截,看 entry_mode) |
| **post-close 冷却**(v1.2):同标的同 strike LEAPS 平仓后 X 天内 | 阻止再次开仓,除非 thesis 重新校验通过 |
| **支撑位动态止损**(v1.2):active_left 仓位必须设置 support-based stop_loss | 校验缺失则阻止建仓推荐 |

被拦截的推荐**不丢弃**,移入 `state.blocked_recommendations`,附 `block_reason`,Telegram 推送时单独展示。

---

## 13. 推送规范(Telegram)

- 纯文本 + emoji,禁止 Markdown 加粗(兼容性)
- 单条 4000 字符自动拆分
- 前缀分类:
  - `🧪 [Beta]` — 全局前缀(M1-M3 阶段)
  - `📊` — 新建仓推荐
  - `⚙️` — 持仓操作
  - `⚠️` — 被拦截推荐 / 健康预警
  - `❗` — 错误告警
  - `🌅` — 盘前 Full Pipeline
  - `🌆` — 盘后 Full Pipeline
  - **`🔍` — Lightweight Pipeline(passive 持仓巡检)**(v1.2)
  - **`⏰` — Pending Trigger 触发**(v1.2)
- 错误告警与业务推送同 chat_id,前缀区分

---

## 14. 文档规范

### 14.1 必须维护的文档

| 文档 | 更新时机 |
|---|---|
| `docs/prd.md` | 需求变更,版本号递增(当前 v1.2) |
| `docs/tech-arch.md` | 架构变更,版本号递增(当前 v1.2) |
| `docs/design.md` | 前端视觉/组件规范变更,版本号递增(当前 v1.0) |
| `README.md` | 每个 Milestone 完成 |
| `AGENTS.md`(本文件) | 全局规范变更,独立 PR(当前 v1.2) |

### 14.2 PR 必须更新的文档

- 新增 Agent:tech-arch Section 4 + `agents.yaml` + 单测(manifest 必备)
- 新增数据源:prd Section 4.1 + tech-arch Section 6 + `tools.yaml`(含 tags)
- 新增交易规则:prd Section 8 + `rules.yaml` + Risk Gate 单测
- 修改契约:PR 标题加 `[CONTRACT]`,更新 tech-arch Section 4.1 / 4.6 / 10
- 新增 Lightweight Agent:必须验证 `llm_dependency=False` + 写到 `agents.yaml` 的 lightweight 分组

---

## 15. 子 Agent 调度约定(Tree CLI)

### 15.1 子 Agent 定义位置

各 Milestone 的子 Agent 定义放在 `.claude/agents/m{N}-{branch}.md`,frontmatter 字段:

```yaml
---
name: m2-smart-money
description: 触发条件描述(包含关键词)
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---
```

### 15.2 调用约定

- 主 session 通过 `Use the m{N}-{branch} agent to ...` 触发
- 每个子 Agent 自带分支文档引用,主 session 不重复粘贴文档
- 子 Agent 必须读完关联的分支文档再开始动手

### 15.3 子 Agent 行为约束

- 不允许跨分支修改文件(如 `m2-smart-money` 不能改 `agents/debate_agent.py`)
- 不允许修改契约层(除非主 session 明示并 owner 评审)
- 必须在结束前跑自己分支的测试集
- 必须输出简短工作总结(变更文件清单 + 测试结果)
- 新增 Agent 子分支必须包含:Agent 代码 + manifest + `agents.yaml` 注册 + 单测 + prompt 模板 四件套

---

## 16. 性能与资源约束

- 单次 Full Pipeline 总时长目标 ≤ 5 分钟(M1 单标的)/ ≤ 15 分钟(M2 全持仓 active)
- **单次 Lightweight Pipeline ≤ 60 秒**(全部 passive 持仓巡检,v1.2)
- 单 Agent 时长 ≤ 60 秒(计算类)/ ≤ 90 秒(LLM 类)
- 内存峰值 ≤ 2GB(本地 Mac 部署目标)
- SQLite 体积 ≤ 5GB(超过触发归档)
- Parquet 单文件 ≤ 100MB(QQQ 2 年日线约 20KB,无压力)

---

## 17. 安全与隐私

- `.env` 必须在 `.gitignore` 中
- API key 不允许 hardcode、不允许日志输出、不允许写入 DB
- Telegram chat_id 视为敏感信息,仅在 .env
- 用户交易数据仅本地存储,不上传任何外部服务
- 第三方依赖更新前检查 CVE(用 `pip-audit` 或 GitHub Dependabot)
- v1.2 新增数据源(Unusual Whales / Market Chameleon / Barchart)API key 同样适用上述约束

---

## 18. Milestone 推进规则

- 当前 Milestone 必须满足全部验收标准才能启动下一个
- 不允许把当前 Milestone 的任务推迟到下一个(要么完成,要么明确从 PRD 删除)
- 每个 Milestone 完成后:
  1. 合 develop → main
  2. 打 tag `v0.{N}.0-m{N}`
  3. 更新 `README.md` 的 Milestone 状态
  4. Telegram 推送一条「Milestone N 上线」通知

### 18.1 v1.2 各 Milestone 新增范围速查

| Milestone | v1.2 新增重点 |
|---|---|
| M1 | entry_mode 字段落库 + Lightweight Pipeline 雏形 + passive 巡检 MVP |
| M2 | Smart Money Agent + Fund Flow Agent + Options Strategist S2 升级 + 10 个新数据源接入 |
| M3 | 双维度反馈(judgment / execution)落地 + KOL post-hoc attribution + Δ Dollars 预算执行 |
| M4 | Agent Registry 完整化 + `aegis scaffold` CLI + ReactFlow DAG 可视化 |

---

## 19. 不允许的行为(红线)

| 行为 | 说明 |
|---|---|
| 跳过测试 | 任何 PR 必须自带测试 |
| 直接推 main | 必须走 PR + develop |
| 修改契约不评审 | 必须 `[CONTRACT]` 前缀 + owner approve |
| 提交密钥 | 任何 key/token 进 git 立即 revoke + rotate |
| 引入新 LLM 协议 | M1-M3 仅 OpenAI 兼容协议 + new-api |
| Hardcode prompt | 必须 Jinja2 模板 |
| Agent 直接调外部 API | 必须通过 Tool Registry |
| 跨分支修改 | 子 Agent 不允许跨分支修改文件 |
| 提交大文件 | > 5MB 文件必须先讨论 |
| 引入 Pydantic v1 / requests / logging | 已被替代 |
| **新增 Agent 不写 manifest**(v1.2) | 必须声明 `AgentManifest` 类属性 + 同步 `agents.yaml` 注册 |
| **Agent 直接挂未声明字段到 PipelineState**(v1.2) | 必须写 `state.extensions[agent_name]` 或先发 `[CONTRACT]` PR 新增字段 |
| **passive 持仓走 Full Pipeline**(v1.2) | 必须经 `pipeline.router` 分流,passive 走 Lightweight |
| **Lightweight Agent 触发 LLM 调用**(v1.2) | `llm_dependency=False` 是硬约束,违反则 CI 失败 |
| **hardcode StateGraph 节点装配**(v1.2 起,M2+) | 必须走 `registry.graph_builder.build_*` |
| **前端 hardcode 色值**(v1.2) | 必须走 `--aegis-*` 变量或 `design-tokens.ts`,禁止裸写 hex/hsl |
| **前端引入非指定 UI/图标库**(v1.2) | 仅 shadcn/ui + Lucide Icons,禁止 MUI / Ant Design / FontAwesome |
| **前端不遵循 design.md 提交**(v1.2) | 必须通过 Section 11 质量检查清单 |

---

## 20. 联系与升级

- Owner: 张毛雨
- 紧急联系: Telegram bot 收到错误推送即代表 owner 已感知
- 本文件升级流程: 独立 PR + 标题 `[AGENTS]` + owner 评审 + 全员通知

---

**最后约定**: 当你(任何子 Agent 或人类开发者)面对模糊场景时,按以下优先级决策:

1. 本文件 > 分支文档 > 个人判断
2. 安全 > 正确性 > 性能 > 美观
3. 「不做」清单 > 「做」清单
4. 用户的硬规则 > 系统的优化建议
5. 拒绝执行 > 错误执行
6. **契约稳定 > 功能新增**(v1.2 强化):新增字段、新增 Agent、新增 Tool 都是「加法」,删改既有契约是「减法」,减法必须 owner 评审

如遇本文件未覆盖的情况,**停下来问 owner**,不要自行扩展规则。
