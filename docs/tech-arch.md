# Aegis 2.0 — 技术架构设计文档

> **版本**: v1.2
> **日期**: 2026-06-03
> **状态**: 架构设计,待 M2 启动同步落地
> **关联文档**: aegis-2.0-prd.md v1.2
> **v1.2 变更摘要**:
> - 与 PRD v1.2 对齐:Agent 13 → 15,数据源 18 → 28
> - 新增 **Smart Money Agent / Fund Flow Agent**,Options Analyst 升级为 **Options Strategist**
> - 新增 **Agent Registry** 横向服务(H3),实现 manifest 驱动的 Graph 动态拼装
> - PipelineState 新增 `entry_mode / extensions / pending_triggers / smart_money / fund_flow` 等字段
> - 新增 **Lightweight Pipeline 子图**,passive 持仓走纯规则巡检
> - Risk Gate 新增"总 Δ 增量预算"硬规则
> - 数据库新增 Thesis Card 扩展字段(entry_mode / entry_key_assumptions / thesis_valid_status / re_entry_flagged / 执行打分)、Pending Triggers 表、Position Grading 字段
> - Tool Registry 增加 `tags` 字段,支持按能力发现工具
> - 新增 `aegis scaffold` CLI 脚手架
> - 动态止损配置化(support_based / fixed_pct)

---

## 目录

1. [架构总览](#一架构总览)
2. [目录结构](#二目录结构)
3. [数据层设计](#三数据层设计)
4. [Agent 层设计](#四agent-层设计)
5. [Memory 系统设计](#五memory-系统设计)
6. [Tool Registry + Agent Registry 设计](#六tool-registry--agent-registry-设计)
7. [API 层设计](#七api-层设计)
8. [Web 层设计](#八web-层设计)
9. [Pipeline 调度设计(Full + Lightweight)](#九pipeline-调度设计full--lightweight)
10. [接口契约定义](#十接口契约定义)
11. [开发规划](#十一开发规划)
12. [从 Aegis 1.0 迁移](#十二从-aegis-10-迁移)

---

## 一、架构总览

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        外部数据源层 (28 sources)                  │
│  yFinance │ 券商API │ FRED(含 DFII10) │ DXY │ ETF flows │ ...    │
│  Unusual Whales │ ON RRP/TGA │ HYG/LQD │ Finviz │ Barchart       │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Tool Registry (LangChain Tools + YAML + tags)
┌─────────────────────────▼───────────────────────────────────────┐
│                       Agent 层 (LangGraph)                       │
│                                                                   │
│  ┌──────────────┐  PipelineState (Pydantic + extensions)         │
│  │ DataHarvester│ ─► Universe Triage(含左侧反转触发) ──┐         │
│  └──────────────┘                                      │         │
│         │           (并行 signal 层)                   │         │
│         ├─► KOL Tracker                                │         │
│         ├─► Trend/Phase / Level / Fundamental                    │
│         ├─► Macro / Sentiment / Options Strategist S1            │
│         ├─► Smart Money Agent (新)                               │
│         └─► Fund Flow Agent (新)                                 │
│                                  │                                │
│                       ┌──────────▼──────────┐                    │
│                       │   Debate Agent      │                    │
│                       │ (含 SM / FF 论据)   │                    │
│                       └──────────┬──────────┘                    │
│                                  │                                │
│                       ┌──────────▼──────────┐                    │
│                       │ Options Strategist  │                    │
│                       │ S2 (entry_mode +    │                    │
│                       │ 场景模拟 + Roll)    │                    │
│                       └──────────┬──────────┘                    │
│                                  │                                │
│                       ┌──────────▼──────────┐                    │
│                       │  Research Manager   │                    │
│                       │ (含条件触发 + 加仓) │                    │
│                       └──────────┬──────────┘                    │
│                                  │                                │
│                       ┌──────────▼──────────┐                    │
│                       │Portfolio Orchestr.  │                    │
│                       │ (含健康度日报)      │                    │
│                       └──────────┬──────────┘                    │
│                                  │                                │
│                       ┌──────────▼──────────┐                    │
│                       │  Risk Gate (含 Δ    │                    │
│                       │  Dollars 增量预算)  │                    │
│                       └──────────┬──────────┘                    │
│                                                                   │
│  ── Lightweight Pipeline 子图(passive 持仓)                      │
│     DataHarvester → Trend/Phase(轻) → Level(轻) →                 │
│     Passive Health Check → 🔍 巡检告警                            │
│                                                                   │
│  ─────────────── 横向服务 ───────────────────────────────────── │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │ Memory     │  │ Tool       │  │ Agent Registry (新)      │  │
│  │ System     │  │ Registry   │  │ manifest 驱动 Graph 拼装 │  │
│  └────────────┘  └────────────┘  └──────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ FastAPI
┌─────────────────────────▼───────────────────────────────────────┐
│                         API 层 (FastAPI)                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP + WebSocket
┌─────────────────────────▼───────────────────────────────────────┐
│                    Web 层 (Next.js App Router)                    │
└─────────────────────────────────────────────────────────────────┘
                          │ Telegram Bot (单向推送)
┌─────────────────────────▼───────────────────────────────────────┐
│  推送层 (Telegram):🌅/🌆/📊/⚙️/⏰/🔍/⚠️/❗ 前缀分类            │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 说明 |
|---|---|
| **批处理优先** | 无盘中监控,盘前/盘后两次 Pipeline |
| **State 即契约** | LangGraph State Schema 是 Agent 间唯一数据契约 |
| **横向服务下沉** | Memory + Tool Registry + Agent Registry 共享基础设施 |
| **插拔架构(v1.2)** | YAML 驱动 + manifest 自描述 + state.extensions 动态槽位 + `aegis scaffold` 脚手架 |
| **双档运行(v1.2)** | Full(LLM) vs Lightweight(纯规则)按持仓分级路由,成本可控 |
| **可迁移存储** | SQLite + ChromaDB + Parquet,本地优先 |
| **Milestone 可用** | 每个 Milestone 交付独立可运行功能 |

---

## 二、目录结构

```
aegis-2.0/
├── backend/
│   ├── aegis/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── scheduler.py               # APScheduler 调度器
│   │   ├── cli.py                     # Typer(含 aegis scaffold)
│   │   │
│   │   ├── agents/                    # 15 Agents
│   │   │   ├── base.py                # BaseAgent + manifest 抽象
│   │   │   ├── data_harvester.py
│   │   │   ├── universe_triage.py
│   │   │   ├── kol_tracker.py
│   │   │   ├── trend_phase_analyst.py
│   │   │   ├── level_analyst.py
│   │   │   ├── fundamental_analyst.py
│   │   │   ├── macro_analyst.py
│   │   │   ├── sentiment_analyst.py
│   │   │   ├── smart_money_agent.py        # 新增
│   │   │   ├── fund_flow_agent.py          # 新增
│   │   │   ├── options_strategist.py       # 原 options_analyst 升级
│   │   │   ├── debate_agent.py
│   │   │   ├── research_manager.py
│   │   │   ├── portfolio_orchestrator.py
│   │   │   ├── risk_gate_agent.py
│   │   │   └── passive_health_check.py     # 新增(Lightweight)
│   │   │
│   │   ├── registry/                  # 插拔核心(新)
│   │   │   ├── agent_registry.py      # 读取 agents.yaml + manifest
│   │   │   ├── graph_builder.py       # 动态拼装 LangGraph
│   │   │   └── manifest.py            # AgentManifest schema
│   │   │
│   │   ├── pipeline/
│   │   │   ├── state.py               # PipelineState (v1.2)
│   │   │   ├── graph_full.py          # Full Pipeline 图
│   │   │   ├── graph_lightweight.py   # Lightweight 子图
│   │   │   ├── router.py              # 按持仓分级路由 Full/Lightweight
│   │   │   ├── runner.py
│   │   │   └── events.py
│   │   │
│   │   ├── memory/
│   │   │   ├── interface.py
│   │   │   ├── working.py
│   │   │   ├── short_term.py
│   │   │   ├── long_term.py
│   │   │   ├── episodic.py
│   │   │   ├── compressor.py
│   │   │   └── weight_adapter.py
│   │   │
│   │   ├── tools/                     # Tool Registry (28 sources)
│   │   │   ├── registry.py
│   │   │   ├── base.py
│   │   │   ├── brokers/  (futu / longbridge / tiger)
│   │   │   ├── market/   (yfinance / alpha_vantage / polygon)
│   │   │   ├── macro/    (fred / dfii10 / dxy)
│   │   │   ├── social/   (stocktwits / reddit / x_twitter)
│   │   │   ├── news/     (tavily / gdelt / yahoo_news / finviz)
│   │   │   ├── flows/    (etf_flows / sector_etf_flows)    # 新增
│   │   │   ├── liquidity/ (on_rrp / tga / hyg_lqd_spread)  # 新增
│   │   │   └── options/  (vix_term / put_call / options_flow /
│   │   │                  unusual_whales / market_chameleon / barchart / cboe)
│   │   │
│   │   ├── calculators/               # 纯计算
│   │   │   ├── greeks.py
│   │   │   ├── wyckoff.py
│   │   │   ├── delta_dollars.py
│   │   │   ├── levels.py
│   │   │   ├── volume_profile.py
│   │   │   ├── gex.py
│   │   │   ├── max_pain.py            # 新增
│   │   │   ├── gamma_flip.py          # 新增
│   │   │   ├── support_strength.py    # 新增
│   │   │   ├── stop_loss.py           # 升级(支持 support_based 模式)
│   │   │   └── scenario_pnl.py        # 新增(场景模拟)
│   │   │
│   │   ├── llm/
│   │   │   ├── client.py              # LLMClient(冻结)
│   │   │   └── schemas.py
│   │   │
│   │   ├── models/
│   │   │   ├── positions.py           # 含 entry_mode 字段
│   │   │   ├── thesis_cards.py        # v1.2 扩展字段
│   │   │   ├── recommendations.py
│   │   │   ├── pending_triggers.py    # 新增
│   │   │   ├── debates.py
│   │   │   ├── kol.py
│   │   │   └── pipeline_runs.py
│   │   │
│   │   ├── api/
│   │   │   ├── pipeline.py
│   │   │   ├── portfolio.py
│   │   │   ├── recommendations.py
│   │   │   ├── thesis.py
│   │   │   ├── debates.py
│   │   │   ├── kol.py
│   │   │   ├── memory.py
│   │   │   ├── triggers.py            # 新增(Pending Triggers)
│   │   │   ├── flows.py               # 新增(Fund Flow / Smart Money)
│   │   │   ├── config.py
│   │   │   └── ws.py
│   │   │
│   │   ├── notifier/
│   │   │   └── telegram.py
│   │   │
│   │   └── utils/
│   │       ├── circuit_breaker.py
│   │       ├── retry.py
│   │       └── logging.py
│   │
│   ├── config/
│   │   ├── tools.yaml                 # Tool 注册(含 tags)
│   │   ├── agents.yaml                # Agent 注册 + manifest
│   │   ├── rules.yaml                 # 含 v1.2 新规则
│   │   ├── schedule.yaml
│   │   └── prompts/                   # Jinja2
│   │       ├── debate_bull.j2
│   │       ├── debate_bear.j2
│   │       ├── debate_judge.j2
│   │       ├── fundamental.j2
│   │       ├── macro.j2
│   │       ├── sentiment.j2
│   │       ├── options_s1.j2
│   │       ├── options_s2.j2          # 升级:含 entry_mode / 场景模拟 prompt
│   │       ├── research_manager.j2
│   │       ├── kol_tracker.j2
│   │       ├── smart_money.j2         # 新增
│   │       └── fund_flow.j2           # 新增
│   │
│   ├── data/
│   │   ├── ohlcv/                     # Parquet
│   │   ├── flows/                     # Parquet 资金流(新)
│   │   ├── positions.db
│   │   ├── memory.db
│   │   └── pipeline.db
│   │
│   ├── alembic/
│   ├── tests/
│   │   ├── foundation/
│   │   ├── tools/
│   │   ├── calculators/
│   │   ├── agents/
│   │   ├── registry/                  # 新增(manifest / graph_builder 测试)
│   │   ├── integration/
│   │   ├── e2e/
│   │   └── fixtures/
│   │
│   ├── pyproject.toml
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                   # → /dashboard
│   │   ├── dashboard/
│   │   ├── recommendations/
│   │   ├── positions/
│   │   ├── thesis/
│   │   ├── debates/
│   │   ├── kol/
│   │   ├── memory/
│   │   ├── triggers/                  # 新增(Pending Triggers)
│   │   ├── flows/                     # 新增(Fund Flow / Smart Money)
│   │   ├── config/
│   │   └── pipeline/
│   ├── components/
│   ├── lib/
│   ├── types/
│   └── package.json
│
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## 三、数据层设计

### 3.1 数据库 Schema

#### positions.db

```sql
-- 持仓快照(v1.2 加 entry_mode + grade)
CREATE TABLE positions (
    id            INTEGER PRIMARY KEY,
    account       TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    pos_type      TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    avg_cost      REAL NOT NULL,
    current_price REAL,
    strike        REAL,
    expiry        DATE,
    option_type   TEXT,
    delta         REAL,
    gamma         REAL,
    theta         REAL,
    vega          REAL,
    iv            REAL,
    delta_dollars REAL,
    unrealized_pnl REAL,
    -- v1.2 新增
    entry_mode    TEXT,                 -- passive | active_left | active_right | cc | sell_put
    grade         TEXT,                 -- passive | active(对应 Pipeline 路由)
    thesis_card_id INTEGER,             -- 关联 Thesis Card
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Thesis Cards (v1.2 扩展字段)
CREATE TABLE thesis_cards (
    id               INTEGER PRIMARY KEY,
    ticker           TEXT NOT NULL,
    direction        TEXT NOT NULL,
    status           TEXT NOT NULL,
    open_date        DATE,
    close_date       DATE,
    -- 系统生成
    entry_thesis     TEXT,
    factor_snapshot  TEXT,
    recommended_plan TEXT,
    stop_loss_plan   TEXT,
    target_price     REAL,
    debate_id        INTEGER,
    -- 用户填写
    actual_execution TEXT,
    deviation_notes  TEXT,
    close_reason     TEXT,
    close_notes      TEXT,
    user_notes       TEXT,
    -- v1.1 判断质量
    judgment_score   INTEGER,           -- 1-5 系统判断打分
    judgment_notes   TEXT,
    -- v1.2 新增
    entry_mode       TEXT,              -- left / right / passive
    entry_key_assumptions TEXT,         -- JSON: ["QQQ 持稳 $475 支撑", ...]
    thesis_valid_status TEXT DEFAULT 'valid', -- valid / partial_broken / fully_broken
    re_entry_flagged BOOLEAN DEFAULT FALSE,   -- 平仓 30 天内重入场标记
    execution_score  INTEGER,           -- 1-5 自身执行打分(新增,与 judgment_score 分开)
    execution_notes  TEXT,
    -- 结果
    actual_pnl       REAL,
    actual_pnl_pct   REAL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_thesis_status ON thesis_cards(status);
CREATE INDEX idx_thesis_re_entry ON thesis_cards(re_entry_flagged, close_date);
```

#### pipeline.db

```sql
-- Pipeline 运行记录(v1.2 加 pipeline_mode)
CREATE TABLE pipeline_runs (
    id              INTEGER PRIMARY KEY,
    run_type        TEXT NOT NULL,      -- pre_market | post_market | manual
    pipeline_mode   TEXT NOT NULL,      -- full | lightweight  (v1.2 新)
    triggered_by    TEXT NOT NULL,
    status          TEXT NOT NULL,
    started_at      DATETIME NOT NULL,
    completed_at    DATETIME,
    duration_sec    REAL,
    ticker_count    INTEGER,
    recommendation_count INTEGER,
    error_log       TEXT
);

CREATE TABLE agent_runs (
    id              INTEGER PRIMARY KEY,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id),
    agent_name      TEXT NOT NULL,
    ticker          TEXT,
    status          TEXT NOT NULL,
    started_at      DATETIME,
    completed_at    DATETIME,
    duration_sec    REAL,
    input_summary   TEXT,
    output_summary  TEXT,
    token_used      INTEGER,
    error_msg       TEXT
);

-- 推荐记录(v1.2 加 entry_mode + delta_dollars_delta)
CREATE TABLE recommendations (
    id              INTEGER PRIMARY KEY,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id),
    ticker          TEXT NOT NULL,
    action          TEXT NOT NULL,
    urgency         TEXT NOT NULL,
    entry_mode      TEXT,                  -- v1.2: left / right / both / null(对应非新建仓)
    factor_scores   TEXT,
    debate_summary  TEXT,
    option_plans    TEXT,
    stop_loss       TEXT,
    kol_signals     TEXT,
    smart_money_summary TEXT,              -- v1.2
    fund_flow_summary   TEXT,              -- v1.2
    scenario_pnl    TEXT,                  -- v1.2: JSON 场景模拟结果
    delta_dollars_delta REAL,              -- v1.2: 推荐生效后 Δ$ 增量
    score           REAL,
    executed        BOOLEAN DEFAULT FALSE,
    thesis_card_id  INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE debates (
    id              INTEGER PRIMARY KEY,
    pipeline_run_id INTEGER,
    ticker          TEXT NOT NULL,
    rounds          INTEGER NOT NULL,
    bull_model      TEXT,
    bear_model      TEXT,
    judge_model     TEXT,
    conclusion      TEXT NOT NULL,
    judge_summary   TEXT,
    full_debate     TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- v1.2 新增:Pending Triggers(条件触发型推荐)
CREATE TABLE pending_triggers (
    id              INTEGER PRIMARY KEY,
    source_recommendation_id INTEGER REFERENCES recommendations(id),
    ticker          TEXT NOT NULL,
    trigger_type    TEXT NOT NULL,         -- price_below | price_above | rsi_below | volume_spike
    trigger_params  TEXT NOT NULL,         -- JSON: {threshold: 475, comparison: "<"}
    suggested_action TEXT NOT NULL,        -- JSON: 触发后建议方案
    valid_until     DATETIME NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | triggered | expired | cancelled
    triggered_at    DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_triggers_status ON pending_triggers(status, valid_until);
```

#### memory.db

```sql
CREATE TABLE short_term_memory (
    id         INTEGER PRIMARY KEY,
    ticker     TEXT,
    data_type  TEXT NOT NULL,
    content    TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE long_term_summary (
    id           INTEGER PRIMARY KEY,
    ticker       TEXT,
    summary_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end   DATE NOT NULL,
    content      TEXT NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE kols (
    id            INTEGER PRIMARY KEY,
    handle        TEXT NOT NULL,
    platform      TEXT NOT NULL,
    verified      BOOLEAN DEFAULT FALSE,
    trust_level   INTEGER DEFAULT 1,
    tracked_since DATE,
    notes         TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- v1.2 加 system_alignment 字段(KOL vs 系统对比)
CREATE TABLE kol_calls (
    id                 INTEGER PRIMARY KEY,
    kol_id             INTEGER REFERENCES kols(id),
    ticker             TEXT NOT NULL,
    direction          TEXT NOT NULL,
    call_price         REAL,
    call_date          DATETIME NOT NULL,
    raw_text           TEXT,
    outcome            TEXT,
    outcome_price      REAL,
    outcome_date       DATE,
    return_pct         REAL,
    -- v1.2
    system_alignment   TEXT,               -- same_direction | opposite | no_system_view
    user_followed      BOOLEAN,            -- 用户是否跟单
    miss_flag          BOOLEAN DEFAULT FALSE  -- 同向 + 系统推 + 用户没跟 → true
);

CREATE TABLE factor_weights (
    id            INTEGER PRIMARY KEY,
    factor_name   TEXT NOT NULL,
    weight        REAL NOT NULL,
    changed_by    TEXT NOT NULL,
    change_reason TEXT,
    effective_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_init (
    id               INTEGER PRIMARY KEY,
    initialized_at   DATETIME NOT NULL,
    observation_days INTEGER DEFAULT 30
);
```

### 3.2 ChromaDB Collection 设计

```python
collections = {
    "debate_history":   {"metadata_fields": ["ticker", "date", "conclusion", "pipeline_run_id"]},
    "kol_calls":        {"metadata_fields": ["kol_id", "ticker", "platform", "date"]},
    "news_articles":    {"metadata_fields": ["ticker", "source", "date", "sentiment"]},
    "smart_money_flow": {"metadata_fields": ["ticker", "date", "side", "premium_bucket"]},  # 新增
}
```

### 3.3 Parquet 文件规范

```
data/ohlcv/
└── {TICKER}.parquet      # 列: date, open, high, low, close, volume, adj_close

data/flows/               # 新增
├── etf/{TICKER}.parquet  # 列: date, net_flow_usd, aum, shares_outstanding
└── sector/{SECTOR_ETF}.parquet
```

---

## 四、Agent 层设计

### 4.1 Pipeline State Schema(v1.2)

```python
# backend/aegis/pipeline/state.py
from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime

class FactorScores(BaseModel):
    trend: Optional[float] = None
    level: Optional[float] = None
    fundamental: Optional[float] = None
    macro: Optional[float] = None
    sentiment: Optional[float] = None
    iv_percentile: Optional[float] = None
    smart_money: Optional[float] = None      # v1.2
    fund_flow: Optional[float] = None        # v1.2
    composite: Optional[float] = None

class DebateResult(BaseModel):
    conclusion: str
    confidence: float
    judge_summary: str
    bull_points: list[str]
    bear_points: list[str]
    rounds: int
    debate_id: Optional[int] = None

class OptionPlan(BaseModel):
    plan_no: int
    strategy: str                          # leaps_call | diagonal | vertical | cc(v1.2 扩展)
    strike: float
    expiry: str
    dte: int
    option_type: str
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float
    estimated_cost: float
    max_profit: Optional[float] = None
    max_loss: Optional[float] = None
    pros: list[str]
    cons: list[str]
    # v1.2
    scenario_pnl: Optional[dict] = None    # {target: ..., flat: ..., stop_loss: ...}
    liquidity_score: Optional[float] = None

class StopLossPlan(BaseModel):                # v1.2 结构化
    mode: Literal["support_based", "fixed_pct"]
    trigger_price: float
    support_level: Optional[float] = None
    drop_pct_from_entry: Optional[float] = None
    notes: str

class TickerAnalysis(BaseModel):
    ticker: str
    is_etf: bool = False
    etf_category: Optional[str] = None      # v1.2: macro_driven | gold_driven | sector
    analysis_depth: str                     # holdings_active | holdings_passive | watchlist | universe
    entry_mode: Optional[Literal["left", "right", "both", "passive"]] = None  # v1.2
    factor_scores: FactorScores = Field(default_factory=FactorScores)
    debate: Optional[DebateResult] = None
    option_plans: list[OptionPlan] = Field(default_factory=list)
    cc_timing: Optional[dict] = None
    stop_loss: Optional[StopLossPlan] = None
    kol_signals: list[dict] = Field(default_factory=list)
    recommendation: Optional[dict] = None
    error_flags: list[str] = Field(default_factory=list)

class PortfolioSnapshot(BaseModel):
    total_nav: float
    daily_pnl: float
    daily_pnl_pct: float
    total_delta_dollars: float
    cash_ratio: float
    max_concentration: float
    positions: list[dict] = Field(default_factory=list)
    health_scores: dict[str, float] = Field(default_factory=dict)   # v1.2: ticker → 0-100

class PendingTrigger(BaseModel):              # v1.2
    ticker: str
    trigger_type: str
    trigger_params: dict
    suggested_action: dict
    valid_until: datetime

class PipelineState(BaseModel):
    # 运行元信息
    run_id: int
    run_type: str
    pipeline_mode: Literal["full", "lightweight"] = "full"   # v1.2
    started_at: datetime
    pipeline_version: str = "2.0"

    # 输入分桶(v1.2)
    tickers_holdings_active:  list[str] = Field(default_factory=list)
    tickers_holdings_passive: list[str] = Field(default_factory=list)
    tickers_watchlist:        list[str] = Field(default_factory=list)
    tickers_universe_passed:  list[str] = Field(default_factory=list)

    # 市场数据
    raw_market_data: dict[str, Any] = Field(default_factory=dict)
    raw_macro_data:  dict[str, Any] = Field(default_factory=dict)
    raw_news: list[dict] = Field(default_factory=list)
    raw_kol_signals: list[dict] = Field(default_factory=list)
    market_env: dict[str, Any] = Field(default_factory=dict)   # VIX / FOMC / earnings 等

    # 各 Ticker 分析结果
    ticker_analyses: dict[str, TickerAnalysis] = Field(default_factory=dict)

    # 组合层
    portfolio: Optional[PortfolioSnapshot] = None
    delta_dollars_breakdown: dict[str, float] = Field(default_factory=dict)
    risk_violations: list[dict] = Field(default_factory=list)

    # Scratchpad
    scratchpad: dict[str, str] = Field(default_factory=dict)

    # v1.2 插拔槽位:新 Agent 可不改 schema 直接挂数据
    # 约定 key 为 agent_name(snake_case)
    extensions: dict[str, Any] = Field(default_factory=dict)

    # v1.2 Pending Triggers
    pending_triggers: list[PendingTrigger] = Field(default_factory=list)

    # 最终输出
    final_recommendations:    list[dict] = Field(default_factory=list)
    blocked_recommendations:  list[dict] = Field(default_factory=list)
    passive_health_alerts:    list[dict] = Field(default_factory=list)   # v1.2 Lightweight 产物
    output_ready: bool = False
```

### 4.2 BaseAgent 抽象类(v1.2 加 manifest)

```python
# backend/aegis/agents/base.py
from abc import ABC, abstractmethod
from aegis.pipeline.state import PipelineState
from aegis.memory.interface import MemoryInterface
from aegis.tools.registry import ToolRegistry
from aegis.registry.manifest import AgentManifest

class BaseAgent(ABC):
    # v1.2:每个 Agent 自带 manifest,Registry 据此发现/校验/拼装
    manifest: AgentManifest = AgentManifest(
        name="base",
        version="0.0.0",
        requires=[],
        provides=[],
        tags=[],
        llm_dependency=None,
    )

    def __init__(self, memory: MemoryInterface, tools: ToolRegistry, config: dict):
        self.memory = memory
        self.tools = tools
        self.config = config
        self.agent_name = self.manifest.name

    @abstractmethod
    async def run(self, state: PipelineState) -> PipelineState:
        """执行 Agent 逻辑,返回更新后的 State"""
        ...

    def write_scratchpad(self, state: PipelineState, reasoning: str) -> None:
        state.scratchpad[self.agent_name] = reasoning

    def read_scratchpad(self, state: PipelineState, agent_name: str) -> str:
        return state.scratchpad.get(agent_name, "")

    def write_extension(self, state: PipelineState, data: Any) -> None:
        """v1.2 插拔槽位写入"""
        state.extensions[self.agent_name] = data

    def read_extension(self, state: PipelineState, agent_name: str) -> Any:
        return state.extensions.get(agent_name)
```

### 4.3 LangGraph 图定义(Full + Lightweight)

```python
# backend/aegis/pipeline/graph_full.py
from langgraph.graph import StateGraph, END
from aegis.pipeline.state import PipelineState
from aegis.registry.graph_builder import GraphBuilder

def build_full_pipeline(builder: GraphBuilder) -> StateGraph:
    """v1.2:Graph 由 Registry 根据 agents.yaml + manifest 自动拼装
    手写代码仅作为兜底/可读性参考。"""
    g = builder.from_manifests(
        entry="data_harvester",
        layers=[
            ["data_harvester"],
            ["universe_triage"],
            # signal 层并行(由 manifest.parallel_group 自动分组)
            ["kol_tracker", "trend_phase_analyst", "level_analyst",
             "fundamental_analyst", "macro_analyst", "sentiment_analyst",
             "smart_money_agent", "fund_flow_agent", "options_strategist_s1"],
            ["debate_agent"],
            ["options_strategist_s2"],
            ["research_manager"],
            ["portfolio_orchestrator"],
            ["risk_gate_agent"],
        ],
        end_node="risk_gate_agent",
    )
    return g.compile()
```

```python
# backend/aegis/pipeline/graph_lightweight.py
def build_lightweight_pipeline(builder: GraphBuilder) -> StateGraph:
    g = builder.from_manifests(
        entry="data_harvester",
        layers=[
            ["data_harvester"],
            ["trend_phase_analyst", "level_analyst"],   # 轻量模式参数:跳过 GEX / Max Pain
            ["passive_health_check"],
        ],
        end_node="passive_health_check",
        mode="lightweight",     # 传给 Agent 用于裁剪逻辑
    )
    return g.compile()
```

```python
# backend/aegis/pipeline/router.py
async def route_and_run(run_id: int, run_type: str):
    """按持仓分级拆两条 Pipeline:passive 走 Lightweight, active 走 Full。"""
    holdings_active, holdings_passive = await split_holdings_by_grade()

    # Lightweight(passive)
    if holdings_passive:
        lw_state = PipelineState(..., pipeline_mode="lightweight",
                                 tickers_holdings_passive=holdings_passive)
        await lightweight_runner.run(lw_state)

    # Full(active + watchlist + universe)
    full_state = PipelineState(..., pipeline_mode="full",
                               tickers_holdings_active=holdings_active,
                               tickers_watchlist=load_watchlist(),
                               ...)
    await full_runner.run(full_state)
```

### 4.4 Debate Agent

```python
DEBATE_MODELS = {
    "bull":  "gpt-4o",
    "bear":  "gpt-4o",
    "judge": "gpt-4o-mini",
}
MAX_ROUNDS = 3
CONVERGENCE_THRESHOLD = 0.8

# v1.2: Bull/Bear prompt 自动注入 state.extensions 下所有 signal 类 Agent 的结论
# 例如 smart_money_agent / fund_flow_agent 输出作为 Bull / Bear 论据池的额外输入
```

### 4.5 Universe Triage Agent(v1.2 扩展)

```python
UNIVERSE_TRIAGE_RULES = {
    "tech_breakout":     {"weight": 1.0, "tag": "right_side"},
    "volume_anomaly":    {"weight": 0.8, "tag": "right_side"},
    "sentiment_anomaly": {"weight": 0.6, "tag": "both"},
    # v1.2 新增
    "left_reversal":     {"weight": 1.0, "tag": "left_side",
                          "conds": ["distance_from_52w_high >= 0.20",
                                    "rsi14 < 35",
                                    "near_support_band(2%)",
                                    "weekly_no_breakdown"]},
}

# v1.2: 板块滤镜 — Fund Flow / Smart Money 评分高的板块成员命中阈值降低 20%
SECTOR_BOOST_PCT = 0.20

class UniverseTriageAgent(BaseAgent):
    async def run(self, state: PipelineState) -> PipelineState:
        universe = await self._load_universe()
        sector_boost = self._compute_sector_boost(state)  # 来自 Fund Flow / Smart Money

        candidates = []
        for ticker in universe:
            score = 0
            hits = []
            mode_hint = []
            quick_data = state.raw_market_data.get(ticker, {})
            sector = self._lookup_sector(ticker)
            threshold_mult = 1.0 - (SECTOR_BOOST_PCT if sector in sector_boost else 0)

            for rule_name, rule in UNIVERSE_TRIAGE_RULES.items():
                if self._eval_rule(rule_name, quick_data, threshold_mult):
                    score += rule["weight"]
                    hits.append(rule_name)
                    mode_hint.append(rule["tag"])

            if hits:
                candidates.append({
                    "ticker": ticker, "score": score, "hits": hits,
                    "entry_mode_hint": self._reduce_mode(mode_hint),
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        passed = candidates[: self.config.get("top_n", 20)]
        state.tickers_universe_passed = [c["ticker"] for c in passed]
        # 把 entry_mode_hint 写进 ticker_analyses,供下游 Options Strategist 参考
        for c in passed:
            state.ticker_analyses[c["ticker"]] = TickerAnalysis(
                ticker=c["ticker"],
                analysis_depth="universe",
                entry_mode=c["entry_mode_hint"],
            )
        return state
```

### 4.6 Smart Money Agent(v1.2 新增)

```python
class SmartMoneyAgent(BaseAgent):
    manifest = AgentManifest(
        name="smart_money_agent",
        version="0.1.0",
        requires=["raw_market_data.options_chain", "raw_market_data.oi_history"],
        provides=["extensions.smart_money_agent"],
        tags=["signal", "options_flow"],
        llm_dependency="mini",
        parallel_group="signal_layer",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        result = {}
        for ticker in self._tickers(state):
            uw = await self.tools.get("unusual_whales").fetch(ticker=ticker)
            mc = await self.tools.get("market_chameleon").fetch(ticker=ticker)
            oi_delta = self._compute_oi_delta(state, ticker)
            f13 = await self.tools.get("sec_13f").fetch(ticker=ticker)

            score, bias = self._score(uw, mc, oi_delta, f13)
            narrative = await self._narrative_llm(ticker, uw, mc, oi_delta, f13)

            result[ticker] = {
                "smart_money_score": score,
                "direction_bias": bias,
                "unusual_options": uw.data.get("top_unusual", []),
                "oi_change_24h": oi_delta,
                "institutional_13f_delta": f13.data,
                "narrative": narrative,
            }
            # 同步写到 factor_scores 供 Debate / Research Manager
            state.ticker_analyses[ticker].factor_scores.smart_money = score

        self.write_extension(state, result)
        return state
```

### 4.7 Fund Flow Agent(v1.2 新增)

```python
class FundFlowAgent(BaseAgent):
    manifest = AgentManifest(
        name="fund_flow_agent",
        version="0.1.0",
        requires=["raw_macro_data"],
        provides=["extensions.fund_flow_agent"],
        tags=["signal", "macro_flow"],
        llm_dependency="mini",
        parallel_group="signal_layer",
    )

    async def run(self, state: PipelineState) -> PipelineState:
        etf_flows    = await self.tools.get("etf_flows").fetch(symbols=["SPY","QQQ","GLD","SLV"])
        sector_flows = await self.tools.get("sector_etf_flows").fetch()
        rrp          = await self.tools.get("fred").fetch(series="RRPONTSYD")
        tga          = await self.tools.get("fred").fetch(series="WTREGEN")
        hyg_lqd      = await self.tools.get("hyg_lqd_spread").fetch()

        liquidity     = self._classify_liquidity(rrp, tga)
        credit        = self._classify_credit(hyg_lqd)
        rotation      = self._sector_rotation(sector_flows)

        result = {
            "macro_liquidity":  liquidity,
            "credit_appetite":  credit,
            "sector_rotation":  rotation,
            "etf_flows_7d":     etf_flows.data,
            "narrative":        await self._narrative_llm(liquidity, credit, rotation),
        }
        self.write_extension(state, result)

        # 给每个 ticker 的 fund_flow 因子打分
        for ticker, ta in state.ticker_analyses.items():
            ta.factor_scores.fund_flow = self._score_for_ticker(ticker, rotation, liquidity)
        return state
```

### 4.8 Options Strategist(v1.2 升级)

```python
class OptionsStrategistAgent(BaseAgent):
    manifest = AgentManifest(
        name="options_strategist",
        version="0.2.0",     # 从 0.1 升级
        requires=["ticker_analyses.*.debate", "ticker_analyses.*.factor_scores"],
        provides=["ticker_analyses.*.option_plans", "ticker_analyses.*.entry_mode"],
        tags=["options"],
        llm_dependency="primary",
    )

    async def run_step1(self, state: PipelineState) -> PipelineState:
        """IV + IV crush 评估"""
        for ticker, ta in state.ticker_analyses.items():
            iv_data = await self._compute_iv(ticker)
            iv_crush_risk = self._assess_iv_crush(ticker, state.market_env, iv_data)
            ta.factor_scores.iv_percentile = iv_data["percentile"]
            ta.extensions = ta.extensions or {}
            # IV crush 风险结果挂在 ticker.extensions 下
            state.extensions.setdefault("options_strategist_s1", {})[ticker] = {
                "iv": iv_data, "iv_crush_risk": iv_crush_risk,
            }
        return state

    async def run_step2(self, state: PipelineState) -> PipelineState:
        for ticker, ta in state.ticker_analyses.items():
            if ta.debate is None: continue

            # 1. entry_mode 判定
            entry_mode = self._decide_entry_mode(
                debate=ta.debate,
                level=self._read_level(state, ticker),
                support_distance_pct=self._support_distance(state, ticker),
                breakout_confirmed=self._breakout_confirmed(state, ticker),
            )
            ta.entry_mode = entry_mode

            # 2. 多策略对比(每 ticker 至少 2 个方案)
            plans = self._generate_plans(
                ticker=ticker, entry_mode=entry_mode,
                iv_env=self._read_iv_env(state, ticker),
                level=self._read_level(state, ticker),
            )

            # 3. 场景模拟 + 流动性评分 + 分批建仓
            for plan in plans:
                plan.scenario_pnl = compute_scenario_pnl(plan, ta)
                plan.liquidity_score = self._liquidity(plan)
            if entry_mode == "left":
                plans = self._add_batch_entry(plans, ta)

            # 4. Roll 评估(仅对持仓中已有 LEAPS,QQQ 例外)
            if self._is_holding_leaps(state, ticker) and ticker != "QQQ":
                plans.append(self._roll_evaluation(state, ticker))

            # 5. 止损方案(支持 support_based)
            ta.stop_loss = self._build_stop_loss(entry_mode, ta, state)
            ta.option_plans = plans
        return state
```

### 4.9 Research Manager(v1.2 加深)

```python
class ResearchManagerAgent(BaseAgent):
    async def run(self, state: PipelineState) -> PipelineState:
        recs = []
        triggers = []
        for ticker, ta in state.ticker_analyses.items():
            if not ta.option_plans: continue

            # 1. 右侧假突破过滤
            if ta.entry_mode == "right" and not self._right_side_confirmed(ta, state):
                self._tag_unconfirmed(ta)

            # 2. 加仓评估(持仓中已有头寸但 < 重仓目标)
            if self._is_under_target(state, ticker):
                add_rec = self._build_add_recommendation(ticker, ta, state)
                if add_rec: recs.append(add_rec)

            # 3. 平仓冷静期检查(平仓 30 天内的标的不主动新建仓)
            if self._in_cooldown(state, ticker):
                continue

            # 4. 即时推荐
            primary = self._select_primary_plan(ta)
            rec = self._build_recommendation(ticker, ta, primary)

            # 5. 拆出"条件触发型"
            triggers.extend(self._extract_triggers(ticker, ta))

            recs.append(rec)

        # CC Timing Guard
        recs = await self._cc_timing(recs, state)

        # 排序与上限
        recs = self._rank_and_cap(recs, cap=self.config.get("max_daily", 10))
        state.final_recommendations = recs
        state.pending_triggers      = triggers
        return state
```

### 4.10 Risk Gate Agent(v1.2 加深)

```python
class RiskGateAgent(BaseAgent):
    async def run(self, state: PipelineState) -> PipelineState:
        passed, blocked = [], []
        market_block = await self._check_market_env(state)

        # 第一轮:基础规则
        for rec in state.final_recommendations:
            reason = self._check_basic(rec, state, market_block)
            if reason: blocked.append({**rec, "block_reason": reason})
            else: passed.append(rec)

        # 第二轮(v1.2):总 Δ Dollars 增量预算
        passed = self._apply_delta_budget(passed, state, blocked)

        state.final_recommendations   = passed
        state.blocked_recommendations = blocked
        return state

    def _apply_delta_budget(self, recs, state, blocked):
        budget_pct = self.config.get("delta_dollars_increment_pct", 0.30)
        budget_usd = state.portfolio.total_nav * budget_pct
        used = 0.0
        kept = []
        for rec in sorted(recs, key=lambda r: -r["score"]):
            delta_delta = rec.get("delta_dollars_delta", 0)
            if used + delta_delta <= budget_usd:
                kept.append(rec)
                used += delta_delta
            else:
                blocked.append({**rec, "block_reason": f"delta_budget_exceeded:{used + delta_delta:.0f}>{budget_usd:.0f}"})
        return kept

    async def _check_market_env(self, state) -> str | None:
        vix = state.market_env.get("vix_current")
        vix_chg = state.market_env.get("vix_daily_change_pct")
        if vix and vix > 30: return f"vix_extreme:{vix:.1f}"
        if vix_chg and vix_chg > 0.20: return f"vix_spike:{vix_chg:.1%}"
        for ev in state.market_env.get("upcoming_events", []):
            if ev["type"] in ("FOMC","CPI","NFP") and ev["hours_until"] <= 24:
                return f"macro_event_24h:{ev['type']}"
        return None
```

### 4.11 Portfolio Orchestrator(v1.2 加健康度日报)

```python
class PortfolioOrchestratorAgent(BaseAgent):
    async def run(self, state: PipelineState) -> PipelineState:
        snapshot = self._build_snapshot(state)
        # v1.2: 计算每个 active 持仓的健康分(0-100)
        for ticker in state.tickers_holdings_active:
            snapshot.health_scores[ticker] = self._compute_health(state, ticker)
        state.portfolio = snapshot
        return state

    def _compute_health(self, state, ticker) -> float:
        # 维度: thesis 有效性 / 距止损距离 / Greeks 健康度 / DTE 剩余 / 浮盈状态
        ...
```

### 4.12 Passive Health Check(v1.2 新增,仅 Lightweight)

```python
class PassiveHealthCheckAgent(BaseAgent):
    manifest = AgentManifest(
        name="passive_health_check",
        version="0.1.0",
        requires=["ticker_analyses.*.factor_scores"],
        provides=["passive_health_alerts"],
        tags=["passive", "rule_only"],
        llm_dependency=None,
    )

    async def run(self, state: PipelineState) -> PipelineState:
        alerts = []
        for ticker in state.tickers_holdings_passive:
            pos = self._get_position(state, ticker)
            # 1. 动态止损巡检
            stop_alert = self._check_dynamic_stop(state, ticker, pos)
            if stop_alert: alerts.append(stop_alert)
            # 2. DTE 巡检
            if pos.get("dte") and pos["dte"] <= 90:
                alerts.append({"ticker": ticker, "type": "leaps_dte_90", "dte": pos["dte"]})
            # 3. Theta 加速
            if self._theta_accelerating(pos):
                alerts.append({"ticker": ticker, "type": "theta_accelerating"})
        state.passive_health_alerts = alerts
        return state
```

---

## 五、Memory 系统设计

### 5.1 统一接口(冻结)

```python
class MemoryInterface:
    async def read(self, scope: str, query: dict, limit: int = 10) -> list[dict]: ...
    async def write(self, scope: str, data: dict, ttl_days: int | None = None) -> None: ...
    async def search(self, query: str, collection: str, top_k: int = 5, filter: dict | None = None) -> list[dict]: ...
    async def summarize(self, ticker: str | None, date_range: tuple[str,str], data_type: str) -> str: ...
    async def archive_scratchpad(self, scratchpad: dict[str, str], run_id: int) -> None: ...
```

### 5.2 四层 Memory 实现要点

| 层级 | 实现 | TTL | 关键操作 |
|---|---|---|---|
| **Working** | `PipelineState.scratchpad` + `state.extensions` | Pipeline 生命周期 | write_scratchpad / read_extension |
| **Short-term** | SQLite `short_term_memory` | 7-30 天 | 按 ticker + data_type 查询 |
| **Long-term** | SQLite + ChromaDB | 滚动压缩 | 超期压缩为摘要;向量检索 |
| **Episodic** | SQLite `thesis_cards` | 永久 | 完整链路记录 |

### 5.3 记忆压缩策略

```python
COMPRESSION_WINDOWS = {
    "debate":           {"full_days": 60, "compress_to": "summary"},
    "recommendation":   {"full_days": 60, "compress_to": "stats"},
    "kol_calls":        {"full_days": 90, "compress_to": "monthly_stats"},
    "regime_judgment":  {"full_days": 30, "compress_to": "weekly_snapshot"},
    "smart_money_flow": {"full_days": 60, "compress_to": "summary"},   # v1.2
    "fund_flow":        {"full_days": 60, "compress_to": "summary"},   # v1.2
}
```

### 5.4 权重自适应与观察期(v1.2 双维度反馈)

```python
class WeightAdapter:
    async def update_weights(self):
        if await self._is_in_observation_period(): return
        closed = await db.get_closed_thesis_cards()

        for factor in FACTORS:
            samples = []
            for card in closed:
                pnl_signal       = self._pnl_to_signal(card.actual_pnl_pct)
                judgment_signal  = (card.judgment_score - 3) / 2 if card.judgment_score else 0
                execution_signal = (card.execution_score - 3) / 2 if card.execution_score else 0  # v1.2
                # v1.2: 系统判断 + 自身执行分离,各自加权
                composite = (
                    0.5 * pnl_signal +
                    0.3 * judgment_signal +
                    0.2 * execution_signal
                )
                age = (today - card.close_date).days
                decay = 0.5 ** (age / DECAY_HALF_LIFE_DAYS)
                score_at_open = card.factor_snapshot.get(factor)
                if score_at_open is not None:
                    samples.append({
                        "factor_score": score_at_open,
                        "outcome": composite,
                        "weight": decay,
                    })
            new_weight = self._regression(samples)
            await db.update_factor_weight(factor, new_weight, changed_by="system")
```

---

## 六、Tool Registry + Agent Registry 设计

### 6.1 tools.yaml(v1.2 加 tags + 新增 10 数据源)

```yaml
# config/tools.yaml

tools:
  yfinance:
    module: "aegis.tools.market.yfinance"
    class: "YFinanceTool"
    priority: P0
    tags: [market, ohlcv]
    rate_limit: {calls_per_minute: 120}
    circuit_breaker: {failure_threshold: 5, recovery_timeout_sec: 60}
    fallback: alpha_vantage
    bound_agents: [data_harvester, trend_phase_analyst, level_analyst]

  fred:
    module: "aegis.tools.macro.fred"
    class: "FREDTool"
    priority: P0
    tags: [macro]
    series_whitelist: [FEDFUNDS, CPIAUCSL, UNRATE, DGS10, VIXCLS,
                       DFII10, RRPONTSYD, WTREGEN]   # v1.2: 加 DFII10 / RRP / TGA
    rate_limit: {calls_per_day: 500}
    bound_agents: [macro_analyst, fund_flow_agent]

  dxy:
    module: "aegis.tools.macro.dxy"
    class: "DXYTool"
    priority: P0
    tags: [macro, fx]
    bound_agents: [macro_analyst, fund_flow_agent]

  etf_flows:
    module: "aegis.tools.flows.etf_flows"
    class: "ETFFlowsTool"
    priority: P0
    tags: [flow, etf]
    bound_agents: [fund_flow_agent]

  sector_etf_flows:
    module: "aegis.tools.flows.sector_etf_flows"
    class: "SectorETFFlowsTool"
    priority: P0
    tags: [flow, sector]
    bound_agents: [fund_flow_agent, universe_triage]

  unusual_whales:
    module: "aegis.tools.options.unusual_whales"
    class: "UnusualWhalesTool"
    priority: P1
    tags: [options_flow, smart_money]
    rate_limit: {calls_per_minute: 60}
    bound_agents: [smart_money_agent]

  market_chameleon:
    module: "aegis.tools.options.market_chameleon"
    class: "MarketChameleonTool"
    priority: P1
    tags: [options_flow, smart_money]
    bound_agents: [smart_money_agent]

  hyg_lqd_spread:
    module: "aegis.tools.liquidity.hyg_lqd_spread"
    class: "HYGLQDSpreadTool"
    priority: P1
    tags: [credit, liquidity]
    bound_agents: [fund_flow_agent]

  finviz:
    module: "aegis.tools.news.finviz"
    class: "FinvizTool"
    priority: P1
    tags: [screener]
    bound_agents: [universe_triage]

  barchart:
    module: "aegis.tools.options.barchart"
    class: "BarchartTool"
    priority: P2
    tags: [options, backup]
    bound_agents: [options_strategist]

  # ... 其他 18 个已有 + 新增工具
```

### 6.2 agents.yaml(v1.2 新增)

```yaml
# config/agents.yaml

agents:
  - name: data_harvester
    module: aegis.agents.data_harvester
    class: DataHarvesterAgent
    enabled: true
    parallel_group: null

  - name: universe_triage
    module: aegis.agents.universe_triage
    class: UniverseTriageAgent
    enabled: true

  - name: trend_phase_analyst
    enabled: true
    parallel_group: signal_layer

  - name: smart_money_agent
    module: aegis.agents.smart_money_agent
    class: SmartMoneyAgent
    enabled: true
    parallel_group: signal_layer
    config:
      min_unusual_premium_usd: 500_000
      score_weights:
        unusual_flow: 0.4
        oi_delta:     0.3
        f13_delta:    0.3

  - name: fund_flow_agent
    module: aegis.agents.fund_flow_agent
    class: FundFlowAgent
    enabled: true
    parallel_group: signal_layer

  - name: options_strategist
    module: aegis.agents.options_strategist
    class: OptionsStrategistAgent
    enabled: true
    config:
      strategies: [leaps_call, diagonal, vertical, cc]
      iv_crush_event_window_days: 5
      iv_crush_rank_threshold: 70

  - name: passive_health_check
    module: aegis.agents.passive_health_check
    class: PassiveHealthCheckAgent
    enabled: true
    pipeline_mode: lightweight    # 仅 lightweight 启用

  # ... 其他
```

### 6.3 AgentManifest schema

```python
# backend/aegis/registry/manifest.py
from pydantic import BaseModel
from typing import Literal, Optional

class AgentManifest(BaseModel):
    name: str
    version: str
    requires: list[str] = []       # state 字段路径,如 "ticker_analyses.*.debate"
    provides: list[str] = []       # state 字段路径
    tags: list[str] = []
    llm_dependency: Optional[Literal["primary", "mini"]] = None
    parallel_group: Optional[str] = None
    pipeline_mode: Literal["full", "lightweight", "both"] = "full"
    enabled: bool = True
```

### 6.4 BaseTool + ToolResult(冻结)

```python
class ToolResult(BaseModel):
    success: bool
    data: dict | list | None = None
    error: str | None = None
    source: str
    cached: bool = False
```

### 6.5 Circuit Breaker(同 v1.1,保留)

```python
class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
```

### 6.6 `aegis scaffold` CLI(v1.2 新)

```bash
# 生成 Tool adapter 模板
aegis scaffold tool --name my_new_source --tags flow,etf

# 生成 Agent 类 + manifest + 测试模板
aegis scaffold agent --name my_new_agent --parallel-group signal_layer --llm mini
```

生成内容:
- 对应文件骨架(BaseTool/BaseAgent 子类)
- `tools.yaml` / `agents.yaml` 注册块(注释提醒手动 enable)
- `tests/tools/test_xxx.py` / `tests/agents/test_xxx.py` 空壳测试

---

## 七、API 层设计

### 7.1 路由总览(v1.2 增量已标 ⭐)

```
GET  /api/v1/pipeline/runs                 # 含 pipeline_mode 过滤
GET  /api/v1/pipeline/runs/{id}
POST /api/v1/pipeline/trigger              # 支持 mode=full|lightweight ⭐
POST /api/v1/pipeline/trigger/ticker
POST /api/v1/pipeline/trigger/agent

GET  /api/v1/portfolio/snapshot
GET  /api/v1/portfolio/greeks
GET  /api/v1/portfolio/delta-dollars
GET  /api/v1/portfolio/health              # 健康度日报 ⭐

GET  /api/v1/recommendations
GET  /api/v1/recommendations/{id}

GET  /api/v1/thesis
GET  /api/v1/thesis/{id}
POST /api/v1/thesis/{id}/close             # 接收 judgment_score + execution_score ⭐
PATCH /api/v1/thesis/{id}                  # 支持改 entry_mode / key_assumptions ⭐

GET  /api/v1/debates
GET  /api/v1/debates/{id}

GET  /api/v1/kol
GET  /api/v1/kol/{id}
POST /api/v1/kol
PATCH /api/v1/kol/{id}
DELETE /api/v1/kol/{id}

GET  /api/v1/triggers                      # Pending Triggers 列表 ⭐
DELETE /api/v1/triggers/{id}               # 取消触发 ⭐

GET  /api/v1/flows/etf                     # ETF 资金流 ⭐
GET  /api/v1/flows/sector                  # 板块轮动 ⭐
GET  /api/v1/flows/smart-money/{ticker}    # Smart Money 详情 ⭐

GET  /api/v1/memory/weights
GET  /api/v1/memory/reports
GET  /api/v1/memory/reports/{id}
GET  /api/v1/memory/patterns

GET  /api/v1/config
PATCH /api/v1/config
GET  /api/v1/config/history

WS   /ws/pipeline
WS   /ws/portfolio
```

### 7.2 WebSocket 消息协议(v1.2 加 mode)

```typescript
interface PipelineEvent {
  type: "agent_start" | "agent_complete" | "agent_failed" |
        "pipeline_complete" | "trigger_fired";   // 新增 trigger_fired
  pipeline_run_id: number;
  pipeline_mode: "full" | "lightweight";          // 新增
  agent_name?: string;
  ticker?: string;
  timestamp: string;
  data?: any;
}
```

---

## 八、Web 层设计

### 8.1 技术选型(保持 v1.1)

| 用途 | 技术 |
|---|---|
| 框架 | Next.js 15 (App Router) |
| 样式 | Tailwind CSS v4 |
| 组件库 | shadcn/ui |
| 图表 | Recharts |
| 表格 | TanStack Table v8 |
| DAG | ReactFlow |
| 状态 | Zustand |
| 数据获取 | SWR |
| 类型 | TypeScript strict |

### 8.2 v1.2 Web 增量

#### Dashboard 新增模块

- **Fund Flow Heatmap**:板块 ETF 资金流热力图(过去 7 天)
- **Smart Money 摘要 Card**:近 24h Top 5 unusual options
- **持仓健康度面板**:每个 active 持仓的健康分(0-100)排序

#### 推荐详情页新增

- **entry_mode 标签**(left / right / both)
- **多策略对比表**
- **场景模拟 P&L 图**
- **Smart Money + Fund Flow 论据块**(可折叠)

#### Thesis Card 新增字段

- `entry_mode`(可改)
- `entry_key_assumptions`(数组,可编辑)
- `thesis_valid_status`(只读,系统自动判定)
- `re_entry_flagged`(只读)
- 平仓打分弹窗扩展:**系统判断打分 + 自身执行打分** 双滑块

#### 新增页面

- `/triggers` Pending Triggers 管理
- `/flows` Fund Flow / Smart Money 总览

#### Pipeline 状态页

- 区分 Full / Lightweight 历史(Tab)
- Lightweight 历史额外展示触发的巡检告警

#### 配置面板新增分组

| 分组 | 配置项 |
|---|---|
| 持仓策略 | QQQ 锁 passive 开关、active 升级开关 |
| 动态止损 | mode 切换 + 阈值 |
| Δ 增量预算 | 上限百分比 |
| 平仓冷静期 | 默认 30 天 |
| Agent 启用 | 所有注册 Agent 开关 |

### 8.3 主题规范(同 v1.1)

```css
--bg-base:      #0f1117;
--bg-surface:   #1a1d2e;
--bg-elevated:  #252842;
--text-primary: #e8eaf0;
--text-muted:   #6b7280;
--accent-green: #22c55e;
--accent-red:   #ef4444;
--accent-blue:  #3b82f6;
--accent-amber: #f59e0b;
```

---

## 九、Pipeline 调度设计(Full + Lightweight)

### 9.1 调度配置

```yaml
# config/schedule.yaml

schedules:
  pre_market_full:
    cron: "0 8 * * 1-5"
    timezone: "America/New_York"
    run_type: "pre_market"
    mode: "full"
    enabled: true

  pre_market_lightweight:
    cron: "5 8 * * 1-5"           # 错峰 5 分钟,避免抢资源
    timezone: "America/New_York"
    run_type: "pre_market"
    mode: "lightweight"
    enabled: true

  post_market_full:
    cron: "0 17 * * 1-5"
    timezone: "America/New_York"
    run_type: "post_market"
    mode: "full"
    enabled: true

  post_market_lightweight:
    cron: "5 17 * * 1-5"
    timezone: "America/New_York"
    run_type: "post_market"
    mode: "lightweight"
    enabled: true

  trigger_check:                  # v1.2 新:每小时检查 Pending Triggers
    cron: "0 * * * 1-5"
    timezone: "America/New_York"
    run_type: "trigger_check"
    enabled: true

  memory_compression:
    cron: "0 2 * * *"
    run_type: "maintenance"
    enabled: true
```

### 9.2 Pipeline Runner

```python
class PipelineRunner:
    async def run(self, run_type: str, mode: str = "full",
                  tickers_override: list[str] | None = None) -> int:
        run_id = await db.create_pipeline_run(run_type, mode)
        await ws_manager.broadcast(PipelineEvent(type="pipeline_start", ...))

        state = PipelineState(run_id=run_id, run_type=run_type, pipeline_mode=mode, ...)

        graph = build_full_pipeline(builder) if mode == "full" else build_lightweight_pipeline(builder)

        try:
            final_state = await graph.ainvoke(state)
        except Exception as e:
            await db.mark_run_failed(run_id, str(e))
            await telegram.send_error(f"Pipeline {run_id} 失败: {e}")
            raise

        await memory.archive_scratchpad(final_state.scratchpad, run_id)
        await db.save_recommendations(run_id, final_state.final_recommendations)
        await db.save_pending_triggers(run_id, final_state.pending_triggers)   # v1.2
        await db.save_passive_alerts(run_id, final_state.passive_health_alerts)  # v1.2

        await telegram.send_pipeline_result(final_state)
        await ws_manager.broadcast(PipelineEvent(type="pipeline_complete", ...))
        return run_id
```

### 9.3 Trigger Check Runner(v1.2)

```python
# 独立小 Job,每小时扫一次 Pending Triggers
async def run_trigger_check():
    triggers = await db.list_active_triggers()
    for trigger in triggers:
        if await self._is_triggered(trigger):
            await telegram.send_trigger_fired(trigger)
            await db.mark_trigger_fired(trigger.id)
```

---

## 十、接口契约定义

> 以下契约在并行开发时**冻结**,各分支以此为准,不得单方面变更。

### 10.1 PipelineState Schema(v1.2,冻结)

| 字段 | 类型 | 填充者 | 消费者 |
|---|---|---|---|
| `pipeline_mode` | `"full" \| "lightweight"` | Runner | 全员 |
| `tickers_holdings_active` / `passive` | `list[str]` | Router | DataHarvester 起 |
| `ticker_analyses[t].entry_mode` | `Literal[left/right/both/passive]` | Universe Triage / Options Strategist S2 | Research Manager / Risk Gate / Web |
| `ticker_analyses[t].factor_scores` | `FactorScores`(含 smart_money / fund_flow) | 各 Analyst + 新 Agents | Debate / Research Manager |
| `ticker_analyses[t].debate` | `DebateResult` | Debate Agent | Options S2 / Research Manager |
| `ticker_analyses[t].option_plans[i].scenario_pnl` | `dict` | Options Strategist S2 | Web / Telegram |
| `ticker_analyses[t].stop_loss` | `StopLossPlan` | Options Strategist S2 | Risk Gate / Web |
| `extensions[agent_name]` | `Any` | 新 Agent 自填 | 任意下游(by convention) |
| `pending_triggers` | `list[PendingTrigger]` | Research Manager | Runner 持久化 / Web |
| `passive_health_alerts` | `list[dict]` | Passive Health Check | Telegram / Web |
| `portfolio.health_scores` | `dict[ticker, float]` | Portfolio Orchestrator | Web |
| `final_recommendations[].delta_dollars_delta` | `float` | Options S2 / Research Manager | Risk Gate(Δ 预算) |

**变更流程**:新增字段须 Optional + 默认值;删除/重命名须 `[CONTRACT]` PR + owner 评审。

### 10.2 AgentManifest 契约(v1.2,冻结)

每个 Agent 必须导出 `manifest: AgentManifest`,字段:
- `name / version / requires / provides / tags / llm_dependency / parallel_group / pipeline_mode / enabled`
- Graph Builder 据此校验:`requires` 字段在上游必须存在,否则启动报错。

### 10.3 Memory 接口契约(v1.0,保持)

```python
memory.read(scope, query, limit)
memory.write(scope, data, ttl_days)
memory.search(query, collection, top_k, filter)
memory.summarize(ticker, date_range, data_type)
memory.archive_scratchpad(scratchpad, run_id)
```

### 10.4 Tool Registry 契约(v1.0,保持)

```python
tool = tools.get("yfinance")
result: ToolResult = await tool.fetch(ticker="QQQ", period="2y")
# ToolResult: success / data / error / source / cached
```

---

## 十一、开发规划

### 11.1 四个 Milestone(v1.2 调整)

#### Milestone 1:单标的端到端 + Telegram + Lightweight 雏形

| 模块 | 内容 |
|---|---|
| DataHarvester | yFinance + 一个券商 API |
| 分析 Agents | Trend/Phase + Level + Options Strategist S1(纯计算) |
| Debate Agent | 三模型 |
| Options Strategist S2 | 基础合约生成(单方案;entry_mode = passive) |
| Research Manager | 单 ticker 输出 |
| Risk Gate | 核心规则 + 市场环境硬规则 |
| Memory | Working Memory + system_init 表 |
| Tool Registry | yFinance + 一个券商 Tool |
| Pipeline | Full 主线路通跑;Lightweight 可触发但只跑 DTE 巡检 |
| 推送 | Telegram 盘前推送(含被拦截推荐) |
| 存储 | SQLite 基础 + Parquet OHLCV |

**可用性**:手动触发,Telegram 收到单标的完整推荐。

#### Milestone 2:组合 + 多标的 + Smart Money + Fund Flow + Strategist 升级 + Web

| 模块 | 内容 |
|---|---|
| DataHarvester | 三账户 + ETF flows + 板块 flows + DFII10 + DXY + RRP/TGA |
| 所有分析 Agents | LLM Analyst 接入(Fundamental / Macro / Sentiment) |
| **Smart Money Agent** | Unusual Whales + OI delta + 13F |
| **Fund Flow Agent** | ETF / Sector / Liquidity / Credit |
| **Options Strategist 升级** | entry_mode + 多策略对比 + 场景模拟 + Roll + IV crush |
| Portfolio Orchestrator | Delta Dollars + 健康度日报 |
| Risk Gate | + Δ 增量预算 |
| Research Manager | + 条件触发型 + 加仓评估 + 假突破过滤 |
| APScheduler | Full + Lightweight 定时 |
| Web(P0)| Dashboard(含 Fund Flow Heatmap + Smart Money + 健康度)+ 持仓 + 推荐详情(entry_mode + 对比表 + 场景图) |
| Memory | Short-term + 部分 Long-term |

#### Milestone 3:Memory 全面 + KOL + Thesis Cards 扩展 + Universe 完整

| 模块 | 内容 |
|---|---|
| Memory | Long-term + 压缩 + ChromaDB |
| **观察期 + 权重自适应** | 系统判断 + 自身执行 双维度 |
| KOL Tracker | X/StockTwits/Reddit + 事后归因 |
| Thesis Cards | 完整生命周期 + 扩展字段(entry_mode / key_assumptions / valid_status / re_entry / 双打分) |
| Universe Triage | 三规则 + 左侧反转 + 板块滤镜 |
| Lightweight Pipeline | Passive Health Check 完整(动态止损 + Theta + DTE) |
| Web(P1)| Thesis Cards + KOL + Debate 历史 + 配置面板 + Triggers + Flows 页 |
| Memory & 回顾页 | 权重趋势 + 周月报 + KOL 事后归因报表 |

#### Milestone 4:报告 + DAG + Agent Registry / scaffold + 配置完善

| 模块 | 内容 |
|---|---|
| **Agent Registry** | 完整 manifest 驱动 graph_builder |
| **`aegis scaffold` CLI** | tool / agent 两类脚手架 |
| Memory 报告 | 月报 / 周报自动生成 + 模式分析 |
| Web(P2)| Pipeline DAG + 标的 360 + 全局搜索 |
| 配置面板 | 全量配置项 + 变更历史 |
| Debate 对比 | 同标的跨日期 |
| Skill Interface(P2 预留) | 接口定义,不实现具体 Skill |
| 错误处理 | 全量 fallback + 完整错误日志 |

### 11.2 并行分支策略

每个 Sprint 拆 3-5 个独立分支,前置:**State Schema + Memory 接口 + AgentManifest schema 冻结**。

#### Sprint 示例(以 M2 为例,v1.2 新增分支)

| 分支 | 内容 | 依赖 |
|---|---|---|
| `feat/m2-smart-money` | Smart Money Agent + Unusual Whales Tool | tool-registry, state-schema |
| `feat/m2-fund-flow` | Fund Flow Agent + ETF/Sector flows + RRP/TGA + HYG/LQD Tools | tool-registry |
| `feat/m2-strategist-upgrade` | Options Strategist S2 重写(entry_mode + 多策略 + 场景 + Roll) | calculators(scenario_pnl), level_analyst |
| `feat/m2-lightweight-pipeline` | Passive Health Check + Router 拆分 + 调度 | state-schema |
| `feat/m2-research-manager-v2` | 条件触发 + 加仓 + 假突破过滤 | strategist, portfolio |
| `feat/m2-risk-gate-delta-budget` | 总 Δ 增量预算实现 | research-manager, portfolio |

#### 并行规则

1. **State Schema + Manifest 分支**优先完成合入 `develop`
2. 各 Agent 分支通过 Mock State 独立测试
3. Memory / Tool Mock 替代真实实现
4. PR 合并前必须通过对应单测(Risk Gate / Greeks / Stop Loss / Scenario PnL / Manifest 校验为必测)

### 11.3 Sprint 节奏(参考)

| Milestone | 参考 Sprint 数 | 核心检验点 |
|---|---|---|
| M1 | 3 Sprint | Telegram 收到完整单标的推荐 + Lightweight 雏形 |
| M2 | 5 Sprint | Smart Money + Fund Flow + Strategist 全升级,Web Dashboard 可用 |
| M3 | 4 Sprint | KOL 信号入推荐,Thesis Cards 双打分完整 |
| M4 | 3 Sprint | DAG 实时动画 + scaffold CLI 可用 + 月报自动生成 |

---

## 十二、从 Aegis 1.0 迁移

### 12.1 迁移策略

新建项目,不在 1.0 代码库改造。

### 12.2 可复用模块

| 模块 | 1.0 路径(示例) | 迁移到 2.0 |
|---|---|---|
| Greeks 计算 | `utils/greeks.py` | `backend/aegis/calculators/greeks.py` |
| Wyckoff 识别 | `analyzers/wyckoff.py` | `backend/aegis/calculators/wyckoff.py` |
| 止损逻辑 | `utils/stop_loss.py` | `backend/aegis/calculators/stop_loss.py`(M2 扩展 support_based) |
| 富途 API Adapter | `brokers/futu_adapter.py` | `backend/aegis/tools/brokers/futu.py` |
| 长桥 API Adapter | `brokers/longbridge_adapter.py` | `backend/aegis/tools/brokers/longbridge.py` |
| 老虎 API Adapter | `brokers/tiger_adapter.py` | `backend/aegis/tools/brokers/tiger.py` |
| yFinance Adapter | `data/yfinance_fetcher.py` | `backend/aegis/tools/market/yfinance.py` |
| FRED Adapter | `data/fred_fetcher.py` | `backend/aegis/tools/macro/fred.py` |

### 12.3 需重写模块

| 模块 | 原因 |
|---|---|
| Pipeline 编排 | EventBus → LangGraph + Registry |
| Agent 逻辑 | 继承 BaseAgent + manifest |
| 数据模型 | 全新 Schema |
| API 层 | 从头 FastAPI |
| Web 层 | 全新 Next.js |

### 12.4 历史数据迁移

```python
# scripts/migrate_from_v1.py (M2 阶段执行)
# 1. 历史推荐 → recommendations 表
# 2. 历史持仓 → 初始 Thesis Cards 参考
# 3. Parquet OHLCV → 直接复用
```

---

## 附录

### A. 环境变量清单(v1.2 扩展)

```bash
# .env.example

# LLM
LLM_BASE_URL=https://your-api-gateway/v1
LLM_API_KEY=sk-xxx
LLM_MODEL_PRIMARY=gpt-4o
LLM_MODEL_MINI=gpt-4o-mini

# 券商
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
LONGBRIDGE_APP_KEY=xxx
LONGBRIDGE_APP_SECRET=xxx
LONGBRIDGE_ACCESS_TOKEN=xxx
TIGER_PRIVATE_KEY=xxx
TIGER_TIGER_ID=xxx

# 行情 / 宏观
ALPHA_VANTAGE_API_KEY=xxx
FRED_API_KEY=xxx
POLYGON_API_KEY=                      # 备用行情

# 社媒 / 新闻
TAVILY_API_KEY=xxx
STOCKTWITS_ACCESS_TOKEN=xxx
REDDIT_CLIENT_ID=xxx
REDDIT_CLIENT_SECRET=xxx
X_BEARER_TOKEN=xxx

# v1.2 新数据源
UNUSUAL_WHALES_API_KEY=
MARKET_CHAMELEON_API_KEY=
BARCHART_API_KEY=
FINVIZ_API_KEY=

# 推送
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# 存储
DATA_DIR=./data
CHROMA_PERSIST_DIR=./data/chroma
```

### B. 关键依赖版本

```toml
# pyproject.toml
[project]
requires-python = ">=3.11"

dependencies = [
    "langgraph>=0.2",
    "langchain-core>=0.3",
    "langchain-openai>=0.2",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "chromadb>=0.5",
    "pandas>=2.2",
    "pyarrow>=16.0",
    "apscheduler>=3.10",
    "python-telegram-bot>=20.0",
    "httpx>=0.27",
    "tenacity>=8.3",
    "loguru>=0.7",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "jinja2>=3.1",
    "pyyaml>=6.0",
    "typer>=0.12",      # v1.2 强化 CLI(scaffold)
]
```

### C. 启动命令(v1.2 增 scaffold)

```bash
aegis start                           # FastAPI + Pipeline
aegis migrate                         # 数据库迁移
aegis test
aegis run --type pre_market --mode full
aegis run --type pre_market --mode lightweight
aegis analyze --ticker QQQ
aegis scaffold tool --name xxx        # v1.2 新
aegis scaffold agent --name xxx       # v1.2 新

docker-compose up -d
```

### D. 开放决策

| 事项 | 当前状态 | 确认时机 |
|---|---|---|
| Pipeline DAG 可视化:流程图 vs 泳道 | 待定 | M4 实现前 |
| ChromaDB embedding 模型选型 | 待定 | M3 Memory 分支 |
| Universe 600 标的具体列表 | 待定 | M3 Universe 分支 |
| 月报/周报具体字段 | 待定 | M4 报告分支 |
| VPS 规格与 CI/CD | 待定 | M4 完成后 |
| Agent Registry 可视化管理 UI | 待定 | M4 后考虑 |
| Lightweight Pipeline 是 M1 即落地还是 M2 补完 | M1 雏形 + M2 完整(推荐) | M1 启动评审 |
| Unusual Whales / Market Chameleon 选哪个为主源 | 待 M2 启动调研 | M2 Sprint-0 |
