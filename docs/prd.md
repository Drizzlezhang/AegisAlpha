# Aegis 2.0 — 产品需求文档 (PRD)

> **版本**: v1.2
> **日期**: 2026-06-03
> **状态**: 需求冻结，待技术架构同步升级到 v1.2
> **v1.2 变更摘要**:
> - 主交易场景明确为 **LEAPS Buy Call（左侧抄底 + 右侧跟随）**，覆盖个股 + ETF（QQQ/SPY/GLD/SLV）
> - 引入 **持仓分级**：passive（QQQ 长期）vs active_left（左侧）vs active_right（右侧），不同 entry_mode 走不同 Pipeline 路径
> - 横向加厚信号源：新增 **Smart Money Agent**（期权大单 / 巨鲸资金） + **Fund Flow Agent**（ETF 资金流 / 板块轮动 / 流动性）
> - 纵向加深期权分析：Options Analyst 升级为 **Options Strategist**（场景模拟 / 多策略对比 / Roll 评估 / 左右侧入场判断 / IV crush 预警 / 批量分批入场）
> - 全局插拔架构：YAML 驱动 Tool Registry + Agent Registry + state.extensions 动态字段 + BaseAgent manifest + `aegis scaffold` 脚手架 CLI
> - LEAPS 生命周期补强（L1-L12）：动态止损（支撑位 vs 固定 8%）、加仓评估、分批出场、平仓后再入场冷静期、KOL 跟单事后归因等
> - ETF 分层分析：QQQ/SPY 宏观驱动；GLD 实际利率（DFII10/TIPS）+ DXY 驱动
> - Pipeline 双档运行：Full（带 LLM 全套）vs Lightweight（纯规则巡检，针对 passive 持仓节省成本）
> - 数据源新增 #19-#28（共 10 个）：ETF 资金流、板块 ETF 资金流、Unusual Whales / Market Chameleon、OI 变动、ON RRP+TGA、HYG/LQD 信用利差、Barchart/CBOE、FRED DFII10、DXY、Finviz
> - Agent 总数 13 → 15；核心问题 19 → 21
> - **Thesis Card 新增字段**：entry_mode / entry_key_assumptions / thesis_valid_status / re_entry_flagged / 平仓时质量打分扩展为"系统判断 + 自身执行"双维度

---

## 一、产品概述

### 1.1 产品定位

Aegis 2.0 是一个 **个人美股/期权交易助手**，基于 LangGraph Multi-Agent 架构，通过多因子分析、多轮辩论和智能推荐，辅助用户做出交易决策。

**核心定位**：顾问角色，仅做强制推送建议，最终交易由用户自己执行。

**核心交易目标**：把"左侧抄底 LEAPS Buy Call"和"右侧跟随 LEAPS Buy Call"两条主线打透 — 解决用户**怕跌不敢入场 / 怕高不敢追 / 仓位偏轻**三大痛点。其他策略（CC / Sell Put）作为附属辅助。

### 1.2 核心问题（系统解决的 21 个痛点）

| # | 问题 | 解决方案 |
|---|---|---|
| 1 | 多账户持仓汇总困难 | 统一拉取富途/长桥/老虎三账户,合并展示 |
| 2 | 整体仓位和 Beta 管理缺乏依据 | Delta Dollars 统一量化风险暴露 |
| 3 | KOL 言论跟踪不及时 | KOL Tracker 自动抓取 + 验证历史表现 |
| 4 | 无法回测博主历史表现 | 系统记录喊单 → 自动追踪后续走势 → 计算胜率 |
| 5 | 主动筛选趋势板块/标的 | Universe 扫描 + 阈值过滤入深度分析 |
| 6 | 期权入场/离场价格推荐 | Options Strategist 生成具体合约方案 |
| 7 | 持仓操作建议 | Research Manager 按紧急程度排序输出 |
| 8 | 行情数据源不明确 | 28 数据源分层接入,主源 + fallback |
| 9 | 信号到决策的闭环反馈缺失 | Thesis Cards 追踪推荐→执行→结果全链路 |
| 10 | 告警与建议的区分不清 | 紧急 vs 非紧急分类推送 |
| 11 | 用户偏好/规则缺乏配置层 | 完整配置面板 |
| 12 | 多账户风险敞口无法量化 | Delta Dollars 跨账户聚合 |
| 13 | 关键事件因子遗漏 | 经济日历 + 财报日历自动纳入 |
| 14 | 支撑/压力位判断不全面 | Level Analyst 综合 call/put wall、成交量、Max Pain、Gamma Flip 等 |
| 15 | 交易逻辑记录不清导致出场变形 | Thesis Cards 结构化记录 + entry_key_assumptions 字段 |
| 16 | Universe 进入深度分析的标准不明 | Universe Triage 规则（技术突破+量能异动+情绪异动+**左侧反转触发**） |
| 17 | 极端市场环境下系统仍照常推送新建仓 | Risk Gate 市场环境硬规则 |
| 18 | 反馈闭环只看盈亏不看判断质量 | Thesis Card 关闭补打分 |
| 19 | 早期样本不足导致权重收敛噪声大 | 首 30 天观察期 |
| **20** | **LEAPS Buy Call 入场缺乏左侧/右侧明确信号区分** | Options Strategist 输出 entry_mode（left/right）+ 不同评分维度（左侧重支撑+反转;右侧重突破+强势） |
| **21** | **ETF（QQQ/SPY/GLD/SLV）与个股分析逻辑混淆** | ETF 分层分析（QQQ/SPY 走宏观+流动性主线;GLD 走实际利率+DXY 主线;跳过 Fundamental,部分跳过 Sentiment） |

### 1.3 用户画像

- 单一用户（个人交易者）
- 持有美股正股 + LEAPS Call + Covered Call + 偶尔短期期权
- 三个券商账户（富途、长桥、老虎）
- 交易标的：S&P 500 + NDX 100 + 头部 ETF（QQQ、SPY、GLD、SLV）
- 不做：meme 股、赌财报方向、小市值、中概股

### 1.4 核心交易策略

#### 1.4.1 持仓分级

| 持仓类型 | entry_mode | 系统关注度 | Pipeline 路径 |
|---|---|---|---|
| **passive**（QQQ 正股 + QQQ LEAPS） | passive | 低 — 仅健康巡检 | Lightweight Pipeline（纯规则,不调 LLM） |
| **active_left**（左侧抄底买入的 LEAPS Call） | active_left | 高 — 全 Pipeline | Full Pipeline + 左侧专属信号评分 |
| **active_right**（右侧跟随买入的 LEAPS Call） | active_right | 高 — 全 Pipeline | Full Pipeline + 右侧专属信号评分 |
| **CC / Sell Put** | cc / sell_put | 中 — 全 Pipeline,但低优先级 | Full Pipeline |

> QQQ 的正股 + LEAPS 作为长期底仓默认 passive,**只做止损巡检和 DTE 到期提醒,不每天生成新建仓推荐**;但用户手动操作 QQQ 期权时(如调整仓位/加仓/平仓部分)可临时升级为 active 跑完整分析。

#### 1.4.2 策略矩阵

| 策略 | 优先级 | 说明 |
|---|---|---|
| **LEAPS Buy Call（左侧）** | P0 主线 | 个股 + ETF（QQQ/SPY/GLD 等）。10-30% OTM,DTE 12 个月+。重支撑位 + 反转信号 + 估值合理 |
| **LEAPS Buy Call（右侧）** | P0 主线 | 个股 + ETF。重突破确认 + 趋势强势 + 量能验证。比左侧要求更严的"假突破"过滤 |
| **QQQ 正股长持** | 被动 | 不操作,仅巡检 |
| **QQQ LEAPS 长持** | 被动 | 不操作,仅 DTE 巡检和动态止损监控 |
| **Covered Call** | P2 辅助 | 震荡 + 阻力 + 高 IV 三条件齐备才卖 |
| **Sell Put** | P2 保留 | 暂不主推 |

---

## 二、系统架构概述

### 2.1 运行模式

**纯批处理架构 — 双档运行**:

| 档位 | 时间 | 适用范围 | 内容 |
|---|---|---|---|
| **Full Pipeline** | 盘前 8:00 ET / 盘后 17:00 ET | active 持仓 + Watchlist + Universe 命中标的 | 全 Agent + LLM 辩论 + 推荐生成 |
| **Lightweight Pipeline** | 与 Full 同时段 | passive 持仓（如 QQQ 底仓） | 纯规则巡检：动态止损 / DTE 到期 / 健康度评分 |
| **手动触发** | 任意 | 用户指定 ticker | 强制走 Full |

- 无盘中监控,无实时推送
- Lightweight 触发的"巡检告警"使用与 Full 推送相同的 Telegram 通道,但 emoji 前缀加 🔍 区分

### 2.2 三层架构

```
┌─────────────────────────────────────────────┐
│                 Web Layer                     │
│         Next.js + Tailwind + shadcn/ui       │
├─────────────────────────────────────────────┤
│              API Layer (FastAPI)              │
├─────────────────────────────────────────────┤
│             Agent Layer (LangGraph)           │
│  15 Agents + 2 Horizontal (Memory + Tools)  │
│  + Agent Registry (插拔)                       │
├─────────────────────────────────────────────┤
│              Data Layer                       │
│  28 Sources → SQLite + ChromaDB + Parquet    │
│  + Tool Registry (插拔)                        │
└─────────────────────────────────────────────┘
```

### 2.3 Agent 配置（13 → 15）

| # | Agent | 职责 | LLM 依赖 | v1.2 变更 |
|---|---|---|---|---|
| 1 | DataHarvester | 多源数据采集 + circuit breaker | 无 | — |
| 2 | Universe Triage | 标的快扫 + 进入深度分析筛选（含左侧反转触发） | 无（纯规则） | 新增左侧反转条件 |
| 3 | KOL Tracker | KOL 言论抓取 + ticker 提取 | mini | — |
| 4 | Trend/Phase Analyst | Wyckoff 相位 + 趋势 + 周线 + 背离 + RS 排名 | 无 | 加深 |
| 5 | Level Analyst | S/R + Volume Profile + GEX + Put Wall + Max Pain + Gamma Flip | 无 | 加深 |
| 6 | Fundamental Analyst | 估值 + 财务指标 | mini | — |
| 7 | Macro Analyst | 宏观经济 + 利率 + 流动性 | mini | 与 Fund Flow 协同 |
| 8 | Sentiment Analyst | 新闻/社媒情绪 + Fear&Greed | mini | — |
| **9** | **Smart Money Agent**（**新增**） | 期权大单 + Unusual Whales + 13F 变动 + OI 变化 → 巨鲸方向偏好 | mini | **新增** |
| **10** | **Fund Flow Agent**（**新增**） | ETF 资金流 + 板块 ETF 轮动 + ON RRP/TGA 流动性 + HYG/LQD 信用利差 | mini | **新增** |
| **11** | **Options Strategist**（原 Options Analyst 升级） | Step1: IV+IV crush 评估; Step2: 多策略对比 + 场景模拟 + Roll 评估 + entry_mode 判断 + 批量分批方案 | mini(S1) / 4o(S2) | **升级** |
| 12 | Debate Agent | 多轮 Bull vs Bear + Judge | 多模型交替 | — |
| 13 | Research Manager | 排序 + CC Timing + 条件触发推荐 + 加仓评估 + 右侧谨慎度 | 4o | 加深 |
| 14 | Portfolio Orchestrator | Delta Dollars + 仓位管理 + Δ 增量预算 | 4o | 加深 |
| 15 | Risk Gate Agent | 规则 + 市场环境 + 总 Δ 增量校验 + 拦截 | mini | 加深 |
| H1 | Memory System | 四层记忆（Working/Short/Long/Episodic） | 无 | — |
| H2 | Tool Registry | 外部工具标准化接入层（YAML 驱动） | 无 | 加深插拔 |
| H3 | **Agent Registry**（**新增**） | Agent 元信息注册 + Graph Builder 动态拼装 | 无 | **新增** |

---

## 三、Agent 层详细需求

### 3.1 Pipeline 执行流程（Full 档）

```
DataHarvester (拉取数据 + market_env)
    │
    ▼
Universe Triage (快扫 → 命中标的进入深度分析,含左侧反转触发)
    │
    │ (Holdings active 必跑 + Watchlist + Universe 命中)
    ▼
    ├──→ KOL Tracker (并行)
    ├──→ Trend/Phase Analyst (并行)
    ├──→ Level Analyst (并行)
    ├──→ Fundamental Analyst (并行, ETF跳过)
    ├──→ Macro Analyst (并行)
    ├──→ Sentiment Analyst (并行, 部分ETF简化)
    ├──→ Smart Money Agent (并行)
    ├──→ Fund Flow Agent (并行)
    └──→ Options Strategist Step1 (并行, IV+IV crush 评估)
            │
            │ (Level Analyst 完成后)
            ▼
    Debate Agent (多轮辩论, 现包含 Smart Money + Fund Flow 论据)
            │
            ▼
    Options Strategist Step2 (合约生成 + entry_mode + 场景模拟 + Roll 评估)
            │
            ▼
    Research Manager (排序 + CC Timing + 条件触发 + 加仓评估)
            │
            ▼
    Portfolio Orchestrator (Delta Dollars + 仓位校验 + Δ 增量预算)
            │
            ▼
    Risk Gate Agent (规则 + 市场环境 + 总 Δ 增量 + 最终拦截)
            │
            ▼
    推送 (Telegram + 写入 DB)
```

### 3.1.1 Lightweight Pipeline（passive 持仓）

```
DataHarvester (仅拉行情 + 持仓快照)
    │
    ▼
Trend/Phase Analyst (仅算趋势 + 关键支撑/阻力,不调 LLM)
    │
    ▼
Level Analyst (仅算 S/R,不算 GEX/Max Pain)
    │
    ▼
Passive Health Check (规则巡检)
    │  ├─ DTE ≤ 90 → 触发 LEAPS 平仓提醒
    │  ├─ 价格跌破最近支撑位 → 触发动态止损提醒
    │  └─ Theta 加速拐点 → 提醒
    ▼
推送 (🔍 巡检告警, 仅在有事件时)
```

> Lightweight 不经过 Debate / Options Strategist / Research Manager / Risk Gate,直接由 Passive Health Check 出告警。

### 3.2 分层分析深度

| 层级 | 标的范围 | Pipeline 档 | 分析深度 |
|---|---|---|---|
| Holdings - passive | QQQ 正股/LEAPS 底仓 | Lightweight | 健康巡检 |
| Holdings - active | 主动操作仓位 | Full | 全 Agent 参与 |
| Watchlist | 用户关注列表 | Full（简化:跳过 Smart Money 详细论据） | 技术 + 情绪 + 资金面 |
| Universe | ~600 标的 | 仅快扫,命中后升 Full | Universe Triage 快扫 |

#### 3.2.1 Universe Triage（v1.2 扩展）

- **输入**:~600 标的（S&P500 + NDX100 + 头部 ETF）的日线快扫数据
- **筛选规则**:以下任一命中视为"候选"
  - **技术突破（右侧触发）**:日线收盘突破 20/50 日均线 + 突破前 20 日高点
  - **量能异动**:当日成交量 > 近 20 日均量 × 2.0
  - **情绪异动**:StockTwits/Reddit 提及量 > 近 7 日均值 × 3.0
  - **左侧反转触发（新增）**:满足以下全部
    - 距 52 周高点回调 ≥ 20%
    - 当日 RSI(14) < 35
    - 价格触及 Volume Profile POC 或前期主要支撑带 ±2%
    - 周线无下降通道破位
  - **板块优先级滤镜（新增）**:Smart Money / Fund Flow Agent 评分高的板块,其成员标的命中门槛降低 20%
- **排序与上限**:候选标的按"综合异动评分"排序,取 Top N（默认 N=20,可配置）
- **输出**:进入深度分析的 ticker 列表 + 每个 ticker 的初步 entry_mode 推测（left / right / both）
- **算力上限**:Universe 通道每次 Pipeline 最多消耗 N×Agent 算力

#### 3.2.2 Smart Money Agent（新增）

- **职责**:跟踪机构和大资金动向,为决策注入"巨鲸方向偏好"
- **数据源**:
  - Unusual Whales / Market Chameleon(期权大单)
  - 券商 API OI 变动
  - SEC EDGAR 13F 季度持仓变动
  - Options Flow(P2 升 P1)
- **输出字段**:
  ```
  {
    "ticker": "QQQ",
    "smart_money_score": 0.72,  # 0-1
    "direction_bias": "bullish",  # bullish / bearish / neutral
    "unusual_options": [
      {"strike": 520, "dte": 540, "side": "call", "premium_usd": 2_500_000, "iv": 0.28}
    ],
    "oi_change_24h": {"call": +12000, "put": -3000},
    "institutional_13f_delta": {"top_5_increased": true, "net_buyers": 8},
    "narrative": "巨鲸偏多,Q4 13F 显示头部基金净加仓..."
  }
  ```
- **LLM 用途**:仅最后 narrative 拼写,score 和 bias 走规则计算
- **进入 Debate**:作为 Bull 或 Bear 论据池的额外输入

#### 3.2.3 Fund Flow Agent（新增）

- **职责**:监控大盘 / 板块 / 流动性资金流,为标的判断提供宏观背景
- **数据源**:
  - ETF 资金流(SPY / QQQ / GLD / SLV)
  - 板块 ETF 资金流(XLK / XLE / XLF / XBI / XLV / XLY / XLI / XLP / XLU / XLRE)
  - FRED:ON RRP 余额 / TGA 余额(流动性指标)
  - HYG / LQD 信用利差(风险偏好)
- **输出字段**:
  ```
  {
    "macro_liquidity": "expanding",  # expanding / neutral / tightening
    "credit_appetite": "risk_on",    # risk_on / neutral / risk_off
    "sector_rotation": {
      "into": ["XLK", "XLY"],
      "out_of": ["XLU", "XLP"]
    },
    "etf_flows_7d": {
      "QQQ": +2_300_000_000,
      "SPY": +800_000_000,
      "GLD": -150_000_000
    },
    "narrative": "..."
  }
  ```
- **下游消费**:Macro Analyst 取宏观结论,Research Manager 取板块优先级,Universe Triage 取板块滤镜

#### 3.2.4 Options Strategist（原 Options Analyst 升级）

**Step 1（与其他分析 Agent 并行）**:
- IV percentile 评估
- **IV crush 风险评估（新增）**:大事件(财报/FOMC/CPI)前 5 个交易日内 + 当前 IV rank > 70 → 标 `iv_crush_risk: high`,并附"建议事件后再入场"

**Step 2（Debate 之后,依赖 Level Analyst 输出）**:
- **entry_mode 判断（新增）**:
  - 左侧:Debate 判定为"反转" + Level Analyst 支撑强度 high + 距支撑位 ≤ 3%
  - 右侧:Debate 判定为"突破" + 突破后回测确认 + 量能放大
  - 不明:both（用户自选）
- **多策略对比（新增）**:对每个推荐 ticker,生成至少 2 个方案对比
  - 方案 A: LEAPS Call(主推)
  - 方案 B: Diagonal Spread / Vertical Spread(高 IV 环境)
  - 输出对比表(成本 / 最大盈利 / 最大亏损 / Greeks / 适用场景)
- **场景模拟(新增)**:每个方案模拟 3 个价格场景的 P&L:
  - 目标价(thesis 验证)
  - 当前价 ±0(横盘 30 / 60 / 90 天 Theta 衰减)
  - 止损价
- **Roll 评估(新增)**:针对持仓中已有的 LEAPS(QQQ 例外,QQQ 仅平仓不 roll),评估是否到了 roll 时机
  - 维度:DTE 剩余 / Delta 变化 / IV 环境 / thesis 有效性
  - 输出:roll / hold / close + 推荐 roll 目标
- **批量分批方案(新增)**:对左侧入场,默认输出"分 2-3 批"的具体价位 + 触发条件
- 每个方案含:strike / DTE / Greeks / 预估收益亏损 / liquidity_score

### 3.3 Debate Agent

- **参与者**:Bull(模型A)、Bear(模型B)、Judge(模型C),三个不同 LLM
- **轮次**:动态轮次 + 最大轮次上限
- **输出**:论点列表(展开)+ Judge 最终结论
- **新增论据池**:Smart Money Agent + Fund Flow Agent 的结论作为 Bull / Bear 可引用的额外论据
- **历史**:前次 Debate 作为上下文输入,提供连续性
- **触发**:active Holdings 必跑;Watchlist + Universe 过滤后的标的

### 3.4 Research Manager(v1.2 加深)

- **合并 CC Timing Guard**:判断当前标的是否适合卖 CC
  - 条件:震荡区间 + 技术阻力位 + IV 偏高(三条件同时满足)
- **排序逻辑**(紧急程度):止损预警 > 平仓提醒 > 加仓机会 > 新机会
- **每日推荐上限**:最多 10 个
- **条件触发型推荐(新增)**:除"今日马上做",还输出"等触发再做"的条件单提醒
  - 例:"QQQ 跌破 $475 提示左侧建仓,以下两天监控"
  - 写入 Pending Trigger 列表,后续 Pipeline 自动检查触发情况
- **右侧入场谨慎度(新增)**:右侧入场需额外通过假突破过滤:
  - 突破后第 1 个交易日的回测幅度 < 突破点的 50%
  - 突破日成交量 > 20 日均量 × 1.5
  - 不满足 → 标 `right_side_unconfirmed`,推荐谨慎度降级
- **加仓评估(新增)**:对 active 持仓,如果当前已有头寸 < 用户目标重仓(20%),且 thesis 仍然有效 + Debate 评分回升 → 输出"加仓建议"(独立于新建仓)
- **平仓后再入场评估(新增)**:平仓 30 天内不主动推荐同一标的新建仓,除非出现强反转信号(防止情绪化追)

### 3.5 Risk Gate Agent(v1.2 加深)

- 独立最终关卡,拦截违规建议
- **校验规则(账户/规则层)**:
  - 总仓位 ≤ 80%
  - 现金储备 ≥ 20%
  - 单标的集中度上限
  - 黑名单标的不得推荐
  - LEAPS DTE 合规性
- **市场环境硬规则**:
  - VIX 当日涨幅 > 20% 或绝对值 > 30:阻止所有新建仓推荐
  - 重大宏观事件前 24h(FOMC/CPI/NFP):阻止新建 LEAPS Call
  - 标的财报前 48h:阻止该标的新建仓(持有继续)
- **总 Delta Dollars 增量预算(新增)**:
  - 单次推荐生效后,总 Delta Dollars 增量 ≤ 当前账户净值 × 配置阈值(默认 30%)
  - 超过则按推荐评分倒序裁掉低分推荐,直到合规
- **拦截后行为**:违规建议不丢弃,移入 `blocked_recommendations`,Telegram 推送时附"拦截原因"

### 3.6 Portfolio Orchestrator

- **Delta Dollars**:统一量化多账户风险暴露(纯 USD)
- **集中度过高时**:给出具体对冲方案
- **CC 被 assign 后**:根据趋势推荐"立即重建仓位"或"等回调再建"
- **持仓健康度日报(新增)**:盘后 Pipeline 后输出每个 active 持仓的健康分(0-100)
  - 维度:thesis 有效性 / 距止损距离 / Greeks 健康度 / DTE 剩余 / 浮盈状态

### 3.7 KOL Tracker

- 平台:X / StockTwits / Reddit
- 冷启动:新 KOL 标记"unverified",不参与因子评分
- 输出:信号单独展示 + 多因子评分融合
- 高信任 KOL 和有因子支持的信号置顶
- **KOL 跟单事后归因(新增)**:每条 KOL 信号在到期时(默认 30 天后)对比:
  - 系统当时是否同向推荐
  - 若同向 + 用户跟了 → 正反馈
  - 若同向 + 用户没跟 → 标记"miss"
  - 若反向 + 用户跟了 KOL → 标记"override_system"
  - 数据进入月报"KOL vs 系统对比"段

### 3.8 ETF 分层分析(v1.2 新增)

| ETF | 主驱动 | 跳过的 Agent | 重点 Agent |
|---|---|---|---|
| QQQ / SPY | 宏观利率 + 流动性 + 板块轮动 | Fundamental | Macro + Fund Flow + Trend/Phase |
| GLD | 实际利率(DFII10 / TIPS) + DXY 美元指数 + 央行购金 | Fundamental | Macro(特化:实际利率视角) + Fund Flow |
| SLV | 工业需求 + 黄金联动 + DXY | Fundamental | Macro + Fund Flow |
| 板块 ETF(XLK/XLE 等) | 板块轮动 + 大盘 Beta | Fundamental | Fund Flow + Macro |

> 个股保留所有 Agent,ETF 按上表配置裁剪;Sentiment Analyst 对 GLD/SLV 简化(社媒讨论少),对 QQQ/SPY 保留。

### 3.9 LEAPS 生命周期(v1.2 补全 L1-L12)

| # | 阶段 | v1.2 增量 |
|---|---|---|
| L1 入场 | DTE 12 个月+,10-30% OTM | entry_mode 必填(left/right) |
| L2 持仓监控 | 每日健康度评分 | 持仓健康度日报 |
| L3 加仓判定 | 加仓评估输出 | Research Manager 加仓建议(新建仓之外) |
| L4 动态止损 | **新增**:跌破支撑位 X%(可配置)触发,而非固定 8% | 配置 `leaps.stop_loss_mode: support_based / fixed_pct` |
| L5 分批出场 | 涨到目标价 1.5×/2×/3× 时分批 | Options Strategist 输出分批建议 |
| L6 thesis 失效检测 | entry_key_assumptions 字段被破坏时触发"thesis 失效"告警 | thesis_valid_status 字段 |
| L7 DTE ≤ 90 平仓 | 已有 | — |
| L8 Theta 加速拐点 | 已有 | — |
| L9 6 个月强平 | 已有 | — |
| L10 Roll 评估 | Options Strategist 输出(QQQ 例外,只平不 roll) | — |
| L11 平仓后冷静期 | 30 天内不主动重推同标的 | re_entry_flagged 字段 |
| L12 KOL 跟单事后归因 | 月报对比 | — |

### 3.10 Memory 系统(独立认知架构)

#### 四层记忆模型

| 层级 | 职责 | 生命周期 | 存储 |
|---|---|---|---|
| **Working Memory** | Pipeline 内推理链传递 | 单次 Pipeline | LangGraph State + Scratchpad |
| **Short-term Memory** | 近期分析结论 | 7-30 天 | SQLite(热表) |
| **Long-term Memory** | 交易模式 / 权重演化 / KOL 表现 / 用户偏好 | 滚动 + 摘要 | SQLite + ChromaDB |
| **Episodic Memory** | Thesis Cards | 永久(压缩) | SQLite |

#### Working Memory 设计

- **Scratchpad**:每个 Agent 执行后将推理链写入 Scratchpad
- 下游 Agent 可读取上游 Scratchpad
- Pipeline 结束后:关键结论归档,原始推理链丢弃
- 实现方式:State 中增加 `scratchpad: dict[agent_name, str]` 字段
- **state.extensions(新增)**:State 内预留 `extensions: dict[str, Any]` 槽位,新 Agent 可不修改 schema 直接挂数据

#### Short-term Memory 设计

- 存储近期分析结论
- Debate Agent 可引用前次 Debate 结论
- 按 ticker + 时间范围 + 数据类型检索

#### Long-term Memory 设计

- **SQLite**:结构化(Thesis Cards、交易、KOL、配置、权重)
- **ChromaDB**:向量(Debate、新闻、KOL 言论)
- **滚动窗口**:

| 数据类型 | 全量保留 | 压缩后 |
|---|---|---|
| Debate | 60 天 | 摘要 |
| 推荐记录 | 60 天 | 统计摘要 |
| KOL 记录 | 90 天 | 月度统计 |
| Regime 判断 | 30 天 | 周快照 |

- **权重自适应**:全历史 + 指数衰减
- **观察期机制**:首 30 天观察期不参与权重计算
- **判断质量反馈(v1.2 扩展为双维度)**:
  - 系统判断打分(1-5):系统给出的方向 / 时机是否准确
  - 自身执行打分(1-5):用户实际执行是否到位(进出场点、仓位、止损纪律)
  - 两者分开记录,避免互相污染

#### Memory 横向服务接口

- `memory.read(scope, query)`
- `memory.write(scope, data)`
- `memory.search(query, top_k)`
- `memory.summarize(ticker, date_range)`

### 3.11 Tool Registry(YAML 驱动插拔)

#### 设计原则
- 不引入 MCP,使用 **LangChain Tools** + 自定义 Tool Registry
- **YAML 驱动**:新 Tool 注册后自动可被 Agent 引用

#### 架构

```
Tool Registry (config/tools.yaml)
    │
    ├── 券商 Tools (Futu / Longbridge / Tiger)
    ├── 行情 Tools (yFinance / Alpha Vantage / Polygon)
    ├── 宏观 Tools (FRED / 含 DFII10 / DXY)
    ├── 情绪 Tools (StockTwits / Reddit / X)
    ├── 新闻 Tools (Tavily / GDELT / Yahoo News / Finviz)
    ├── 资金面 Tools (ETF flows / 板块 ETF / 信用利差)
    ├── 期权流 Tools (Unusual Whales / Market Chameleon / Barchart / CBOE)
    └── 其他 Tools (Polymarket / SEC EDGAR / 13F)
```

#### 每个 Tool 定义
- **endpoint**:API 地址或本地函数路径
- **schema**:输入/输出 JSON Schema
- **fallback**:备用源配置
- **circuit_breaker**:失败阈值 + 熔断时间
- **rate_limit**:调用频率限制
- **tags**:用于 Agent 按能力匹配工具(如 `tags: [options_flow, smart_money]`)

#### 新增数据源流程
1. 实现 adapter(继承 BaseTool 接口)
2. 在 `config/tools.yaml` 注册
3. 绑定到对应 Agent(或通过 tags 自动匹配)
4. 无需修改 Pipeline 核心逻辑

### 3.12 Agent Registry(v1.2 新增,插拔核心)

#### 设计原则
- 每个 Agent 自带 **manifest**(name / version / requires / provides / tags / llm_dependency)
- Graph Builder 启动时读取 manifest,**动态拼装 LangGraph**,无需手写依赖图
- 新 Agent 实现 BaseAgent + 注册到 `config/agents.yaml` 即可加入 Pipeline

#### manifest 示例

```yaml
- name: smart_money_agent
  version: 0.1.0
  requires:           # 依赖上游 state 字段
    - market_data.options_chain
    - market_data.oi_history
  provides:           # 输出到 state.extensions
    - extensions.smart_money
  tags: [signal, options_flow]
  llm_dependency: mini
  enabled: true
  parallel_group: signal_layer   # 与同组 Agent 并行
```

#### state.extensions 槽位
- 新 Agent 不需要修改 PipelineState schema,直接写到 `state.extensions[agent_name]`
- Debate Agent 自动拉取所有 `extensions.*` 作为论据池

#### CLI 脚手架(`aegis scaffold`)
- `aegis scaffold tool --name xxx`:生成 Tool adapter 模板 + yaml 注册块
- `aegis scaffold agent --name xxx`:生成 Agent 类 + manifest + 测试模板

### 3.13 推送规则 (Telegram)

- **纯推送**,无双向交互
- 纯文本 + emoji
- 拆分为多条消息推送
- 前期标注 "Beta" 标签
- 错误告警同 Telegram 通道
- 盘前推送:关注点 + 行动清单
- 盘后推送:回顾 + 持仓变化
- Lightweight 巡检告警前缀 🔍
- 条件触发型推荐前缀 ⏰

### 3.14 输出模板

**模板一:新建仓推荐**
- 标的 + 方向 + **entry_mode**(left/right)
- 各因子评分
- Debate 论点列表(展开)
- **多策略对比表**(Options Strategist 输出)
- **场景模拟 P&L**(目标/横盘/止损)
- 期权方案(1-N)含 pros/cons
- 止损计划(价格 + 百分比 + DTE + **支撑位**)
- 相关 KOL 信号
- **Smart Money 偏向 + Fund Flow 板块背景**

**模板二:持仓操作建议**
- 标的 + 当前状态
- 操作建议(持有/加仓/减仓/平仓/分批平仓/roll)
- 建议理由 + **thesis_valid_status**
- 紧急程度标签

**模板三:条件触发型(新增)**
- 触发条件(价格/RSI/量能)
- 触发后建议方案
- 监控有效期

**模板四:Lightweight 巡检告警(新增)**
- 持仓 ticker
- 触发原因(动态止损 / DTE / Theta 加速)
- 建议动作

### 3.15 错误处理

| 故障类型 | 处理方式 |
|---|---|
| 数据源不可用 | 延迟重试 → 持续不可用跳过 + Telegram 通知 |
| LLM API 不可用 | 跳过该 Agent + Telegram 通知 |
| 券商 API 同步失败 | 使用上次成功数据 + 标注"可能非最新" |

---

## 四、数据层详细需求

### 4.1 数据源清单(18 → 28)

| # | 数据源 | 用途 | 优先级 |
|---|---|---|---|
| 1 | yFinance | 行情主源(日线/周线) | P0 |
| 2 | 券商 API (Futu/Longbridge/Tiger) | 持仓+交易+期权链+OI+行情 fallback | P0 |
| 3 | Alpha Vantage | 财报日历 + 基本面 | P0 |
| 4 | FRED | 宏观经济(利率/CPI/失业率) | P0 |
| 5 | StockTwits | 社媒情绪 | P0 |
| 6 | Reddit | 社区讨论 | P0 |
| 7 | Tavily | 语义新闻搜索 | P0 |
| 8 | GDELT | 全球事件流 | P0 |
| 9 | Polymarket | 预测市场 | P1 |
| 10 | X (Twitter) | KOL 言论 | P1 |
| 11 | SEC EDGAR Form 4 | Insider 交易 | P1 |
| 12 | VIX Term Structure | 波动率期限结构 | P1 |
| 13 | Put/Call Ratio | 期权情绪 | P1 |
| 14 | Fear & Greed Index | 综合情绪 | P2 |
| 15 | Economic Calendar | 经济事件 | P1 |
| 16 | Yahoo Finance News | 新闻 | P1 |
| 17 | Options Flow | 期权大单(基础) | P1(原P2提升) |
| 18 | SEC EDGAR 13F | 机构持仓季度变动 | P2 |
| **19** | **ETF 资金流(SPY/QQQ/GLD/SLV)** | Fund Flow Agent 核心 | P0 |
| **20** | **板块 ETF 资金流(XLK/XLE/XLF/XBI/XLV/XLY/XLI/XLP/XLU/XLRE)** | 板块轮动判断 | P0 |
| **21** | **Unusual Whales / Market Chameleon** | Smart Money Agent 期权大单 | P1 |
| **22** | **OI 变动(券商 API)** | Smart Money Agent OI 跟踪 | P0 |
| **23** | **FRED ON RRP + TGA 余额** | 流动性指标 | P1 |
| **24** | **HYG / LQD 信用利差** | 风险偏好 | P1 |
| **25** | **Barchart / CBOE 期权数据** | 备用期权数据源 | P2 |
| **26** | **FRED DFII10(10年期 TIPS 实际利率)** | GLD 分析核心 | P0 |
| **27** | **DXY 美元指数** | GLD/SLV 分析 + 跨资产判断 | P0 |
| **28** | **Finviz Screener** | Universe 快扫辅助 + 板块筛选 | P1 |

### 4.2 数据存储

| 存储 | 用途 |
|---|---|
| SQLite (positions.db) | 持仓、交易记录、Thesis Cards |
| SQLite (memory.db) | 记忆、KOL、规则、权重历史 |
| SQLite (pipeline.db) | Pipeline 运行记录、推荐、Debate、Pending Triggers |
| ChromaDB | 向量语义搜索 |
| Parquet 文件 | 日线行情(按 ticker 分文件)`data/ohlcv/` |
| Parquet 文件 | 资金流历史(按 ETF 分文件)`data/flows/` |

### 4.3 数据刷新策略

- Pipeline 启动时拉取一次最新持仓
- 日线数据缓存,当日首次请求时更新
- 多源 fallback:固定主源,挂了切备用源
- 初始化:回补 2 年日线数据 + 90 天资金流数据

---

## 五、Web 层详细需求

> Web 层细节与 v1.1 一致,以下仅列出 v1.2 增量。完整 Dashboard / Thesis Card / 推荐详情 / 持仓视图 / Debate 历史 / KOL 跟踪 / Memory & 回顾 / 配置面板 / Pipeline 状态 / 标的 360 视图等设计请参见 v1.1 第五章。

### 5.1 整体设计原则(保持)

- 风格:金融仪表盘(深色主题)
- 屏幕:主力 1920px + 支持 iPad 横屏 (1024px)
- 导航:左侧固定侧边栏
- 数据刷新:Pipeline 跑完后 WebSocket 通知
- 认证:不需要

### 5.2 v1.2 Web 增量

#### Dashboard 新增模块

- **Fund Flow Heatmap**:板块 ETF 资金流热力图(过去 7 天)
- **Smart Money 摘要 Card**:列出近 24h 命中的 unusual options Top 5,链接到详情
- **持仓健康度面板**:每个 active 持仓的健康分(0-100)排序

#### 推荐详情页新增

- **entry_mode 标签**(left / right / both)
- **多策略对比表**(LEAPS Call vs Diagonal vs Vertical 等)
- **场景模拟 P&L 图**
- **Smart Money + Fund Flow 论据块**(可折叠)

#### Thesis Card 字段扩展

新增可编辑字段:
- `entry_mode`(left / right,创建时自动填,可改)
- `entry_key_assumptions`(列表,如"QQQ 持稳 $475 支撑")
- `thesis_valid_status`(系统自动判定:valid / partial_broken / fully_broken)
- `re_entry_flagged`(平仓后 30 天内重入场标记)

平仓打分扩展:**系统判断打分 + 自身执行打分** 双维度。

#### Pipeline 状态页

- 区分 Full vs Lightweight 运行历史
- Pending Triggers 单独列表:展示待触发的条件单推荐

#### 配置面板新增

| 分组 | 配置项 |
|---|---|
| 持仓策略 | QQQ 是否锁为 passive、active 升级开关、Lightweight 触发时间 |
| 动态止损 | `support_based / fixed_pct` 切换 + 阈值 |
| Δ 增量预算 | 单次推荐生效后总 Delta 增量上限百分比 |
| 平仓冷静期 | 默认 30 天 |
| Agent 启用开关 | 列出所有注册 Agent,可禁用 Smart Money / Fund Flow 等以省成本 |

---

## 六、技术方案概要

### 6.1 技术栈(v1.1 保持)

| 层级 | 技术选型 |
|---|---|
| 编排框架 | LangGraph (≥0.2) + LangChain Core |
| LLM 管理 | new api 中转站,最多 3 个模型 |
| 后端 API | FastAPI |
| 前端 | Next.js (App Router) + Tailwind + shadcn/ui |
| 图表 | Recharts / Tremor |
| 数据表格 | TanStack Table |
| DAG 可视化 | ReactFlow |
| 数据库 | SQLite (SQLAlchemy + Alembic) |
| 向量库 | ChromaDB |
| 行情缓存 | Parquet 文件 |
| 调度 | APScheduler (常驻进程) |
| 推送 | python-telegram-bot (v20+) |
| HTTP 客户端 | httpx (async) |
| 重试 | tenacity |
| 日志 | loguru |
| 包管理 | uv |
| Python | 3.11 / 3.12 |

### 6.2 项目结构

- **Monorepo**:单仓库 `/backend` + `/frontend`
- **进程模型**:FastAPI + Pipeline 同进程
- **启动方式**:`aegis start` 单命令(开发)/ Docker Compose(正式)

### 6.3 配置管理

- `.env`:所有 API keys(不进 git)
- `config/*.yaml`:业务参数(进 git)
- `config/tools.yaml`:Tool 注册(YAML 驱动)
- `config/agents.yaml`:Agent 注册 + manifest
- Prompt 模板:`config/prompts/` 目录,Jinja2 + YAML

### 6.4 测试策略

- 核心模块单元测试:Risk Gate 规则、Greeks 计算、止损逻辑、Smart Money score 计算等
- Agent Registry 拼装 graph 的 e2e 测试
- 至少 1 个第三方 Agent 通过 scaffold 添加的回归测试

### 6.5 部署

- 初期:本地 Mac
- 未来:VPS 平迁

---

## 七、优先级排期

### Web 模块优先级(v1.2 微调)

| 优先级 | 模块 |
|---|---|
| **P0** | Dashboard(含 Fund Flow Heatmap + Smart Money 摘要 + 健康度) + 持仓视图 + 推荐详情(含 entry_mode + 多策略对比) + Thesis Cards(含扩展字段) |
| **P1** | Debate 历史 + KOL 跟踪 + Memory & 回顾 + 配置面板(含动态止损 / Δ 预算 / Agent 开关) + Pipeline 状态(Pending Triggers) |
| **P2** | DAG 可视化 + 全局搜索 + 标的 360 视图 + Debate 对比 |

### 数据源优先级(v1.2 扩展)

| 优先级 | 数据源 |
|---|---|
| **P0** | yFinance, 券商API, Alpha Vantage, FRED, StockTwits, Reddit, Tavily, GDELT, **ETF 资金流, 板块 ETF 资金流, OI 变动, DFII10, DXY** |
| **P1** | Polymarket, X, SEC EDGAR Form 4, VIX Term Structure, Put/Call Ratio, Economic Calendar, Yahoo Finance News, Options Flow, **Unusual Whales, ON RRP+TGA, HYG/LQD, Finviz** |
| **P2** | Fear & Greed Index, SEC EDGAR 13F, **Barchart/CBOE** |

### Milestone 排期(v1.2 调整建议)

| Milestone | 范围 | 备注 |
|---|---|---|
| **M1** | 单标的端到端 Pipeline + Telegram + Lightweight + Risk Gate 核心 | 暂不上 Smart Money / Fund Flow / Strategist 升级 |
| **M2** | 多标的 + 持仓管理 + Smart Money Agent + Fund Flow Agent + Options Strategist 升级 | 横向/纵向加深 |
| **M3** | 完整认知系统(Memory 四层 + Thesis Card 扩展字段 + 月报周报 + KOL 事后归因) | — |
| **M4** | 精细化 + 回顾 + Agent Registry / Tool Registry 插拔完善 + scaffold CLI | 插拔基础设施 |

---

## 八、约束与规则

### 8.1 交易规则(硬编码 / 可配置)

| 规则 | 默认值 | 可配置 |
|---|---|---|
| 总仓位上限 | 80% | ✓ |
| 现金储备 | ≥ 20% | ✓ |
| LEAPS 最大持有 | 6 个月 | ✓ |
| LEAPS DTE 平仓提醒 | ≤ 90 天 | ✓ |
| LEAPS OTM 范围 | 10-30% | ✓ |
| LEAPS 入场 DTE | 12 个月+ | ✓ |
| 每日推荐上限 | 10 个 | ✓ |
| 黑名单 | meme/小市值/中概 | ✓ |
| CC 条件 | 震荡+阻力+高IV 三合一 | 硬编码 |
| LEAPS 不 roll(仅 QQQ) | — | 硬编码 |
| 其他 LEAPS 可 roll | Strategist 评估 | ✓ |
| VIX 阻止新建仓阈值 | 涨幅 > 20% 或绝对值 > 30 | ✓ |
| 宏观事件前阻止 LEAPS | FOMC/CPI/NFP 前 24h | ✓ |
| 财报前阻止新建仓 | 财报前 48h | ✓ |
| 观察期长度 | 30 天 | ✓ |
| Universe Triage Top N | 20 | ✓ |
| **动态止损模式** | **support_based**(默认) / fixed_pct | ✓ |
| **动态止损支撑下穿幅度** | **3%** | ✓ |
| **固定止损百分比** | **8%** | ✓ |
| **单次 Δ Dollars 增量上限** | **账户净值 × 30%** | ✓ |
| **平仓后冷静期** | **30 天** | ✓ |
| **重仓目标百分比** | **20%** | ✓ |
| **左侧反转触发回调阈值** | **距 52 周高 ≥ 20%** | ✓ |
| **右侧突破假突破过滤** | 突破第 1 日回测 < 50% + 量能 > 1.5× 均量 | ✓ |
| **IV crush 风险阈值** | 大事件前 5 日 + IV rank > 70 | ✓ |
| **板块滤镜门槛降低幅度** | 20% | ✓ |

### 8.2 账户使用率告警

- \> 70%:预警
- \> 80%:阻止新建议

### 8.3 不做的事情

- 不做盘中监控/推送
- 不做 meme 股
- 不赌财报方向
- 不做小市值/中概
- 不做 QQQ LEAPS 的 roll(QQQ 仅平仓,其他 LEAPS 可 roll)
- 不做短期 Buy Call(所有 Call 均为 LEAPS)
- 不做移动端适配
- 不做多用户/认证
- 不下单(永远只是顾问)

---

## 九、附录

### 9.1 术语表

| 术语 | 定义 |
|---|---|
| Delta Dollars | 持仓的 Delta × 标的价格 × 合约乘数 |
| Thesis Card | 记录持仓逻辑的卡片 |
| Universe | 系统扫描的标的池(~600) |
| Wyckoff Phase | 技术分析中的市场阶段 |
| CC Timing | Covered Call 卖出时机判断 |
| GEX | Gamma Exposure |
| Max Pain | 期权到期日最大痛点价位 |
| Gamma Flip | Gamma 由正转负的临界价位 |
| DFII10 | 10 年期 TIPS 隐含的实际利率 |
| DXY | 美元指数 |
| ON RRP | 隔夜逆回购(美联储流动性指标) |
| TGA | 财政部一般账户余额 |
| entry_mode | left(左侧抄底) / right(右侧跟随) / passive(被动持有) |
| thesis_valid_status | valid / partial_broken / fully_broken |
| IV crush | 事件后 IV 急速回落导致期权价格暴跌 |

### 9.2 开放问题(后续迭代)

- Web 全局搜索的搜索引擎选型(P2 时决定)
- Debate 对比功能的交互细节(P2 时设计)
- 云迁移时的具体 VPS 规格和 CI/CD 流程
- 月报/周报的具体字段和可视化细节
- Pipeline DAG 可视化选 A(流程图) 还是 B(泳道),实现时确定
- Agent Registry 的可视化管理界面(M4 后考虑)
- Lightweight Pipeline 是否在 M1 即落地,还是 M2 再补
