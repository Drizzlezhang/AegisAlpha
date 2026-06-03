# Aegis 2.0 — Milestone 1 Sprint Plan (v1.2 对齐)

> **目标**: 单标的（QQQ）端到端跑通 Full Pipeline + Lightweight Pipeline 雏形 + Telegram 推送
> **周期**: 2-3 周（取决于并行度）
> **对齐文档**: PRD v1.2 / tech-arch v1.2 / AGENTS.md v1.2 / design-system v1.0
> **本文档位置**: `docs/sprints/m1/README.md`
> **版本**: v1.2（新增 entry_mode 落库、AgentManifest、Lightweight Pipeline、state.extensions）

---

## 1. M1 范围与验收

### 1.1 In Scope

| 类别 | 内容 |
|---|---|
| 契约层 | PipelineState v1.2 完整 schema（含 entry_mode / extensions / pipeline_mode / pending_triggers 等新字段）+ BaseAgent + AgentManifest 类属性（只定义不用 graph_builder）+ MemoryInterface + BaseTool/ToolResult + LLMClient |
| 数据源 | yFinance / Alpha Vantage / FRED / Tavily — 4 个主源 |
| 纯计算 | Greeks / stop_loss(含 support_based 预留) / Wyckoff / GEX / Volume Profile |
| Agent | 7 个: DataHarvester / Trend-Phase / Level / Options Strategist(S1+S2) / Debate / Research Manager / Risk Gate |
| Pipeline | Full Pipeline（手动装配 StateGraph,M1 不走 graph_builder 但预留接口）+ Lightweight Pipeline 雏形(仅 DTE 巡检 + 基础 health score) |
| Portfolio | 简化 Portfolio Orchestrator（mock 持仓 JSON,含 entry_mode 字段） |
| 存储 | SQLite 表结构(含 positions.entry_mode / thesis_cards v1.2 字段 / pending_triggers 空表) + Parquet OHLCV |
| 推送 | Telegram 盘前 + 盘后 + Lightweight 巡检（🔍 前缀） |
| 调度 | APScheduler（Full + Lightweight 两套 cron）+ Typer CLI 手动触发 |
| Memory | Working Memory（Scratchpad + extensions 写入）+ system_init 表结构 |
| 配置 | tools.yaml(含 tags) / agents.yaml(含 manifest 字段) / rules.yaml / schedule.yaml / prompts/*.j2 |

### 1.2 Out of Scope

| 功能 | 延后到 |
|---|---|
| Smart Money Agent / Fund Flow Agent / Options Strategist 升级 | M2 |
| 多账户合并 / 富途/长桥/老虎真实对接 | M2 |
| Agent Registry + graph_builder 自动装配 | M4（M1 手动装配） |
| `aegis scaffold` CLI | M4 |
| Universe Triage 全量扫描 | M3 |
| KOL Tracker / X / Reddit / StockTwits | M3 |
| 完整四层 Memory + WeightAdapter + 观察期 | M3 |
| 双维度打分(judgment + execution) | M3 |
| Thesis Cards Web UI | M3 |
| Pending Triggers 小时巡检 | M2（M1 仅表结构） |
| Next.js 前端 | M2 起 |
| Passive Health Check 完整版 | M3（M1 仅 DTE + 基础 health score） |

### 1.3 验收标准

| # | 标准 | 验证方式 |
|---|---|---|
| 1 | `aegis run --ticker QQQ --mode pre-market` 端到端跑通 | CLI 输出 + Telegram 收到推荐 |
| 2 | `aegis run --ticker QQQ --mode lightweight` 巡检跑通 | Telegram 收到 🔍 巡检消息 |
| 3 | 全部强制单测通过 | `pytest tests/` 全绿 |
| 4 | 单次 Full Pipeline 时长 ≤ 5 分钟 | agent_timings 汇总 |
| 5 | Risk Gate 拦截可见 | 注入 mock 数据触发拦截,Telegram 显示 ⚠️ blocked |
| 6 | PipelineState 包含 v1.2 全部新字段 | test_state_contract.py 校验 |
| 7 | 每个 Agent 有 manifest 类属性 | test 校验 AgentManifest 字段完整 |
| 8 | positions mock 含 entry_mode 字段 | test_portfolio 校验 |
| 9 | LLM 调用全走 LLMClient + Jinja2 | grep 验证无直接 openai 调用 |
| 10 | ruff + mypy 全绿 | CI 检查 |
| 11 | Alembic 迁移正反向跑通 | `alembic upgrade head && alembic downgrade base` |

---

## 2. 分支拆分与依赖关系

### 2.1 拓扑图

```
Sprint-0 Foundation (契约层冻结 v1.2)
        │
        ├─→ Branch A: Tool Registry + 4 数据源
        ├─→ Branch B: Calculators (纯计算)
        ├─→ Branch C: DataHarvester + Portfolio Orchestrator(简化)
        ├─→ Branch D: Trend/Phase + Level + Options S1
        ├─→ Branch E: Debate Agent
        │
        │   (B / D / E 完成后)
        │     │
        │     ▼
        ├─→ Branch F: Options S2 + Research Manager + Risk Gate
        │
        │   (A-F 全部完成后)
        │     │
        │     ▼
        └─→ Branch G: Telegram + CLI + Lightweight 雏形 + Pipeline Runner + 集成
```

### 2.2 并行安排

| 阶段 | 可并行分支 | 阻塞 |
|---|---|---|
| Day 1 | Sprint-0 | — |
| Day 2-7 | A / B / C / D / E 全并行 | Sprint-0 完成 |
| Day 8-10 | F | B + D + E 完成 |
| Day 11-13 | G + 集成测试 | A-F 完成 |

### 2.3 分支清单

| 分支 | 子 Agent | 估时 |
|---|---|---|
| Sprint-0 | `m1-foundation` | 1 天 |
| Branch A | `m1-tools` | 5 天 |
| Branch B | `m1-calculators` | 4 天 |
| Branch C | `m1-data-agent` | 3 天 |
| Branch D | `m1-analyst` | 5 天 |
| Branch E | `m1-debate` | 4 天 |
| Branch F | `m1-orchestration` | 5 天 |
| Branch G | `m1-integration` | 3 天 |

---

## 3. 契约层（M1 冻结,v1.2）

Sprint-0 创建并冻结的文件:

| 文件 | 新增/变更(vs v1.1) |
|---|---|
| `pipeline/state.py` | 新增 `pipeline_mode` / `tickers_holdings_active|passive` / `entry_mode` / `extensions` / `pending_triggers` / `passive_health_alerts` / `health_scores` / `delta_dollars_delta` |
| `agents/base.py` | 新增 `manifest: ClassVar[AgentManifest]` 类属性 + `write_extension` / `read_extension` helper |
| `registry/agent_registry.py` | 【新文件】AgentManifest Pydantic model |
| `memory/interface.py` | 保持不变 |
| `tools/base.py` | 保持不变 |
| `llm/client.py` | 保持不变 |

---

## 4. 通用约定

- 所有分支必须先读 `AGENTS.md` v1.2
- 所有 PR 走 `develop`,禁止直推 `main`
- 子 Agent 不允许跨分支修改文件
- 每个 Agent 必须声明 `manifest` 类属性(即使 M1 不走 graph_builder)
- Agent 自定义输出走 `self.write_extension(state, key, value)`,禁止私挂未声明字段
- 测试 fixture 共享放 `backend/tests/fixtures/`
- M1 LLM 模型:`gpt-4o`(主) + `gpt-4o-mini`(mini),通过 new-api 转发

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Alpha Vantage 限频 5 次/分 | tools.yaml rate_limit + tenacity 重试 + 缓存 |
| LLM JSON 解析失败 | Debate 重试 1 次 → error_flag → Pipeline 继续 |
| yFinance 偶发 503 | fallback Alpha Vantage |
| LangGraph 学习曲线 | Sprint-0 先跑 hello-world 验证 |
| v1.2 新字段太多导致 Sprint-0 膨胀 | 新字段全部 Optional + 默认值,不影响后续分支逻辑 |
| Lightweight 与 Full 共享 Agent 代码 | Agent 内 `if state.pipeline_mode == "lightweight"` 分支处理 |

---

## 6. 子 Agent 使用方法

```
Use the m1-foundation agent to set up Sprint-0 v1.2 contract layer.
Use the m1-tools agent to implement Tool Registry with tags and 4 data sources.
Use the m1-calculators agent to implement Greeks / stop_loss(support_based) / Wyckoff / GEX / Volume Profile.
Use the m1-data-agent agent to implement DataHarvester (dual mode) and Portfolio Orchestrator (with entry_mode).
Use the m1-analyst agent to implement Trend/Phase + Level + Options S1 with manifests.
Use the m1-debate agent to implement Debate Agent with v1.2 prompt placeholders.
Use the m1-orchestration agent to implement Options S2 + Research Manager + Risk Gate (8 rules).
Use the m1-integration agent to wire up Full + Lightweight pipelines, Telegram, CLI, and run integration tests.
```
