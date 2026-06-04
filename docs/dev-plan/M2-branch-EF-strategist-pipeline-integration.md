# M2 Branch E+F — Strategist/Research/Risk 升级 + Pipeline 并行化 + Lightweight + Triggers + 集成测试

> **分支**: `feat/m2-strategist-pipeline-integration`
> **估时**: 10 天
> **优先级**: P0
> **子 Agent**: `m2-strategist-integration`
> **前置**: Branch A（Smart Money）+ Branch B（Fund Flow）+ Branch C（Broker）+ Branch D（Frontend）完成
> **前置阅读**: `AGENTS.md` v1.2 + `docs/tech-arch.md` 第 4.4-4.9 节 + `docs/prd.md` 第 3.4-3.9 节

---

## 1. 目标

本分支合并原 Branch E（Agent 升级）和 Branch F（Pipeline 集成），一次性完成 M2 后半程全部工作：

**Part 1 — Agent 升级（原 Branch E）**:
1. **Options Strategist S2**: 多策略对比 / P&L 场景模拟 / Roll 评估 / 批量分批入场 / IV crush 预警
2. **Research Manager v2**: 条件触发型推荐 / 加仓评估 / 右侧假突破过滤 / 平仓冷却期 / CC Timing Guard
3. **Risk Gate v2**: Delta Dollars 增量预算 / IV crush guard

**Part 2 — Pipeline 集成（原 Branch F）**:
4. **Pipeline 并行化**: Signal 层 Agent fan-out + Annotated state reducers + manifest-driven graph_builder
5. **Lightweight Pipeline 完善**: 动态止损 + DTE 预警 + Theta 加速检测
6. **Pending Triggers**: 每小时 cron 扫描 + 触发通知
7. **REST API 完善**: 所有 M2 新增路由实现
8. **端到端集成测试**: 验证完整 Pipeline 流程
9. **Sprint-0 遗留项修复**: 7 项

**执行顺序**: 先完成 Part 1（Agent 升级），再完成 Part 2（Pipeline 集成 + 测试）。Part 2 依赖 Part 1 的产出。

---

## 2. 交付物清单 — Part 1: Agent 升级

### 2.1 Options Strategist S1 升级（IV Crush 评估）

**修改**: `backend/aegis/agents/options_strategist_s1_agent.py`

**新增功能**: IV Crush 风险评估

```python
async def run(self, state: PipelineState) -> PipelineState:
    for ticker, ta in state.ticker_analyses.items():
        iv_data = await self._compute_iv(ticker)
        iv_crush_risk = self._assess_iv_crush(ticker, state.market_env, iv_data)
        
        ta.factor_scores.iv_percentile = iv_data["percentile"]
        self.write_extension(state, {
            ticker: {
                "iv": iv_data,
                "iv_crush_risk": iv_crush_risk,
            }
        })
    return state

def _assess_iv_crush(self, ticker: str, market_env: dict, iv_data: dict) -> dict:
    """
    IV crush 风险评估:
    - 大事件(财报/FOMC/CPI)前 5 个交易日内
    - 且当前 IV rank > 70%
    → iv_crush_risk: "high"，附 "建议事件后再入场"
    
    返回:
    {
        "level": "high" / "medium" / "low",
        "reason": str,
        "upcoming_event": str | None,
        "days_until_event": int | None,
    }
    """
```

### 2.2 Options Strategist S2 升级（核心）

**修改**: `backend/aegis/agents/options_strategist_s2_agent.py`

#### 2.2.1 entry_mode 判定

```python
def _decide_entry_mode(
    self, debate: DebateResult, level: dict,
    support_distance_pct: float, breakout_confirmed: bool
) -> str:
    """
    左侧 (active_left):
    - Debate 判定为"反转" + Level Analyst 支撑强度 high + 距支撑位 ≤ 3%
    
    右侧 (active_right):
    - Debate 判定为"突破" + 突破后回测确认 + 量能放大
    
    不明 → "both"（用户自选）
    """
```

#### 2.2.2 多策略对比

```python
def _generate_plans(
    self, ticker: str, entry_mode: str, iv_env: dict, level: dict
) -> list[OptionPlan]:
    """
    每个推荐 ticker 至少生成 2 个方案对比:
    
    方案 A: LEAPS Call（主推）
    方案 B: Diagonal Spread / Vertical Spread（高 IV 环境）
    可选 C: Covered Call (cc 模式时)
    
    每个方案包含:
    - strike / DTE / Greeks / 预估成本
    - max_profit / max_loss
    - pros / cons
    - liquidity_score
    - scenario_pnl（见 2.2.3）
    """
```

**OptionPlan 模型扩展**:
```python
class OptionPlan(BaseModel):
    plan_no: int
    strategy: str                  # leaps_call | diagonal | vertical | cc
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
    max_profit: float | None = None
    max_loss: float | None = None
    pros: list[str]
    cons: list[str]
    # v1.2 新增
    scenario_pnl: dict | None = None       # {target: ..., flat: ..., stop_loss: ...}
    liquidity_score: float | None = None
```

#### 2.2.3 场景模拟 P&L

```python
def compute_scenario_pnl(plan: OptionPlan, ta: TickerAnalysis) -> dict:
    """
    模拟 3 个价格场景:
    
    1. target: thesis 验证价位 → 计算 P&L
    2. flat: 横盘 30/60/90 天 → Theta 衰减影响
    3. stop_loss: 止损价位 → 最大亏损
    
    返回:
    {
        "target": {"price": float, "pnl": float, "pnl_pct": float},
        "flat_30d": {"price": float, "pnl": float, "theta_decay": float},
        "flat_60d": {"price": float, "pnl": float, "theta_decay": float},
        "flat_90d": {"price": float, "pnl": float, "theta_decay": float},
        "stop_loss": {"price": float, "pnl": float, "pnl_pct": float},
    }
    """
```

使用 Black-Scholes 模型计算（复用 `calculators/greeks.py`）。

#### 2.2.4 Roll 评估

```python
def _roll_evaluation(self, state: PipelineState, ticker: str) -> OptionPlan:
    """
    对持仓中已有的 LEAPS（QQQ 例外,QQQ 仅平仓不 roll）:
    
    评估维度:
    - DTE 剩余 < 180 天 → 考虑 roll
    - Delta 变化（deep ITM → roll up）
    - IV 环境（高 IV → 等 IV 回落再 roll）
    - Thesis 有效性（broken → close, not roll）
    
    输出:
    - action: "roll" / "hold" / "close"
    - roll 目标: 新 strike + 新 expiry
    - 预估 roll 成本
    """
```

#### 2.2.5 批量分批入场

```python
def _add_batch_entry(self, plans: list[OptionPlan], ta: TickerAnalysis) -> list[OptionPlan]:
    """
    左侧入场默认输出分 2-3 批的具体方案:
    
    - Batch 1: 当前价位入场 40% 仓位
    - Batch 2: 支撑位入场 40% 仓位（→ 生成 PendingTrigger）
    - Batch 3: 支撑位下方 2% 入场 20% 仓位（可选）
    
    每批附: 触发价位 + 建议数量 + 触发条件描述
    """
```

#### 2.2.6 止损方案结构化

```python
class StopLossPlan(BaseModel):
    mode: Literal["support_based", "fixed_pct"]
    trigger_price: float
    support_level: float | None = None
    drop_pct_from_entry: float | None = None
    notes: str

def _build_stop_loss(self, entry_mode: str, ta: TickerAnalysis, state: PipelineState) -> StopLossPlan:
    """
    active_left → support_based（基于 Level Analyst 的支撑位）
    active_right → fixed_pct（默认 -8%）
    """
```

### 2.3 Research Manager v2

**修改**: `backend/aegis/agents/research_manager_agent.py`

#### 2.3.1 右侧假突破过滤

```python
def _right_side_confirmed(self, ta: TickerAnalysis, state: PipelineState) -> bool:
    """
    右侧入场需额外通过假突破过滤:
    1. 突破后第 1 个交易日回测幅度 < 突破点 50%
    2. 突破日成交量 > 20 日均量 × 1.5
    
    不满足 → 标 right_side_unconfirmed，推荐谨慎度降级
    """
```

#### 2.3.2 加仓评估

```python
def _build_add_recommendation(self, ticker: str, ta: TickerAnalysis, state: PipelineState) -> dict | None:
    """
    对 active 持仓:
    - 当前已有头寸 < 用户目标重仓 (20%)
    - thesis 仍然有效
    - Debate 评分回升
    → 输出"加仓建议"（独立于新建仓）
    """
```

#### 2.3.3 平仓冷却期

```python
def _in_cooldown(self, state: PipelineState, ticker: str) -> bool:
    """
    平仓 30 天内不主动推荐同一标的新建仓
    除非出现强反转信号
    从 memory / positions.db 查询最近平仓时间
    """
```

#### 2.3.4 条件触发型推荐

```python
def _extract_triggers(self, ticker: str, ta: TickerAnalysis) -> list[dict]:
    """
    除"今日马上做"，还输出"等触发再做"的条件单提醒
    
    例: "QQQ 跌破 $475 → 提示左侧建仓"
    
    生成 PendingTrigger:
    {
        "ticker": ticker,
        "trigger_type": "price_below",    # price_below / price_above / rsi_below / volume_spike
        "trigger_params": {"threshold": 475, "comparison": "<"},
        "suggested_action": {推荐方案快照},
        "valid_until": now + 7 days,
    }
    """
```

#### 2.3.5 CC Timing Guard

```python
async def _cc_timing(self, recs: list[dict], state: PipelineState) -> list[dict]:
    """
    判断标的是否适合卖 CC:
    三条件同时满足:
    1. 震荡区间（Trend 判定为 ranging）
    2. 技术阻力位（Level Analyst 确认）
    3. IV 偏高（IV percentile > 50）
    
    满足 → 附加 CC 推荐
    不满足 → 跳过 CC 方案
    """
```

#### 2.3.6 排序逻辑

```python
def _rank_and_cap(self, recs: list[dict], cap: int = 10) -> list[dict]:
    """
    排序优先级:
    1. 止损预警（urgency: critical）
    2. 平仓提醒（urgency: high）
    3. 加仓机会（urgency: medium）
    4. 新机会（urgency: normal）
    
    同优先级内按 score 倒序
    每日上限: 最多 cap 个（默认 10）
    """
```

### 2.4 Risk Gate v2

**修改**: `backend/aegis/agents/risk_gate_agent.py`

#### 2.4.1 Delta Dollars 增量预算

```python
def _apply_delta_budget(self, recs: list[dict], state: PipelineState, blocked: list[dict]) -> list[dict]:
    """
    单次推荐生效后，总 Delta Dollars 增量 ≤ 当前账户净值 × 配置阈值（默认 30%）
    
    budget_pct = self.config.get("delta_dollars_increment_pct", 0.30)
    budget_usd = state.portfolio.total_nav * budget_pct
    
    按 score 倒序保留，超预算的低分推荐移入 blocked_recommendations
    附 block_reason: "delta_budget_exceeded:{used}>{budget}"
    """
```

#### 2.4.2 IV Crush Guard

```python
def _check_iv_crush(self, rec: dict, state: PipelineState) -> str | None:
    """
    读取 Options Strategist S1 的 iv_crush_risk 评估结果
    如果 level == "high" → 拦截
    附 block_reason: "iv_crush_risk_high:{event}_{days}d"
    """
```

#### 2.4.3 完整规则链

```python
async def run(self, state: PipelineState) -> PipelineState:
    passed, blocked = [], []
    market_block = await self._check_market_env(state)

    for rec in state.final_recommendations:
        # 第一轮: 基础规则
        reason = self._check_basic(rec, state, market_block)
        if not reason:
            reason = self._check_iv_crush(rec, state)    # 新增
        if reason:
            blocked.append(BlockedRecommendation(
                **rec, block_reason=reason,
                blocked_at=datetime.now(timezone.utc)
            ))
        else:
            passed.append(rec)

    # 第二轮: Delta Dollars 增量预算（新增）
    passed = self._apply_delta_budget(passed, state, blocked)

    state.final_recommendations = passed
    state.blocked_recommendations = blocked
    return state
```

### 2.5 Jinja2 Prompt 更新

| 文件 | 修改内容 |
|---|---|
| `prompts/options_s2_analysis.j2` | 新增 entry_mode / 多策略对比 / 场景模拟 的 prompt |
| `prompts/research_synthesis.j2` | 新增条件触发 / 加仓 / CC timing 的 prompt |
| `prompts/debate_bull.j2` | 确认 `{{ smart_money_context }}` + `{{ fund_flow_context }}` 正确渲染 |
| `prompts/debate_bear.j2` | 同上 |

### 2.6 strategy_comparisons + scenario_pnl 写入 State

```python
# Options Strategist S2 将结果写入:
state.strategy_comparisons[ticker] = [plan.model_dump() for plan in plans]
state.scenario_pnl[ticker] = {
    f"plan_{plan.plan_no}": plan.scenario_pnl for plan in plans
}
```

### 2.7 rules.yaml 更新

```yaml
# 新增/修改规则配置
risk_gate:
  delta_dollars_increment_pct: 0.30    # 新增
  iv_crush_block_threshold: "high"      # 新增
  cooldown_days: 30                     # 新增

research_manager:
  max_daily_recommendations: 10         # 新增
  right_side_volume_multiplier: 1.5     # 新增
  right_side_retrace_max_pct: 0.50      # 新增
  batch_entry_splits: 3                 # 新增
  
options_strategist:
  min_plans_per_ticker: 2               # 新增
  roll_dte_threshold: 180               # 新增
```

---

## 3. 交付物清单 — Part 2: Pipeline 集成

### 3.1 graph_builder 完整实现

**修改**: `backend/aegis/pipeline/graph_builder.py`

Sprint-0 搭建了框架，本分支补全并行 fan-out 逻辑：

```python
class GraphBuilder:
    """Manifest-driven dynamic graph assembly with parallel fan-out."""

    def from_manifests(
        self,
        entry: str,
        layers: list[list[str]],
        end_node: str,
        mode: str = "full",
    ) -> StateGraph:
        """
        1. 读取 agents.yaml
        2. 按 mode 过滤 enabled agents
        3. 按 layers 定义顺序组装
        4. 同 layer 内多个 agent → 并行 fan-out / fan-in
        5. 使用 Annotated state reducers 处理并行写入
        6. 返回 compiled StateGraph
        """

    def _build_parallel_layer(self, graph: StateGraph, agents: list[str], prev_node: str, next_node: str):
        """
        对同一 layer 的多个 agent:
        1. 从 prev_node fan-out 到所有 agent
        2. 所有 agent fan-in 到 next_node
        3. 使用 Annotated[dict, merge_dicts] reducer 处理并行写入 extensions
        """
```

### 3.2 Annotated State Reducers

**修改**: `backend/aegis/pipeline/state.py`

```python
from typing import Annotated
from langgraph.graph import add_messages  # 或自定义 reducer

def merge_dicts(left: dict, right: dict) -> dict:
    """自定义 reducer: 深度合并两个 dict（并行 agent 各自写入不同 key）"""
    merged = left.copy()
    merged.update(right)
    return merged

def merge_lists(left: list, right: list) -> list:
    """自定义 reducer: 合并两个 list"""
    return left + right

class PipelineState(BaseModel):
    # 需要并行写入的字段使用 Annotated
    extensions: Annotated[dict[str, Any], merge_dicts] = Field(default_factory=dict)
    error_flags: Annotated[list[dict], merge_lists] = Field(default_factory=list)
    agent_timings: Annotated[dict[str, float], merge_dicts] = Field(default_factory=dict)
    # 其余字段不变（只有单一 agent 写入，无冲突）
```

**注意**: 仅对并行写入的字段添加 Annotated reducer，不改变 PipelineState 的功能契约。

### 3.3 Full Pipeline 并行化

**修改**: `backend/aegis/pipeline/graph_full.py`

```python
def build_full_pipeline(builder: GraphBuilder) -> StateGraph:
    """M2: 使用 graph_builder 动态装配,信号层并行执行"""
    g = builder.from_manifests(
        entry="data_harvester",
        layers=[
            ["data_harvester"],                         # 数据采集
            ["portfolio_orchestrator"],                  # 持仓分流
            # Signal 层 — 并行 fan-out（parallel_group: signal_analysts）
            [
                "trend_phase_analyst",
                "level_analyst",
                "smart_money_agent",
                "fund_flow_agent",
                "options_strategist_s1",
            ],
            ["debate_agent"],                            # 辩论（依赖 signal 层）
            ["options_strategist_s2"],                   # 策略（依赖 debate）
            ["research_manager"],                        # 综合推荐
            ["risk_gate"],                               # 风控关卡
        ],
        end_node="risk_gate",
    )
    return g.compile()
```

**预期拓扑**:
```
DataHarvester → PortfolioOrchestrator
  → [parallel] TrendPhase / Level / SmartMoney / FundFlow / OptionsS1
  → [fan-in] DebateAgent
  → OptionsS2
  → ResearchManager
  → RiskGate
  → END
```

**性能目标**: Signal 层并行执行后，总 Pipeline 耗时 ≤ 3 分钟（`agent_timings` 验证并行）。

### 3.4 Lightweight Pipeline 完善

**修改**: `backend/aegis/pipeline/graph_lightweight.py`

```python
def build_lightweight_pipeline(builder: GraphBuilder) -> StateGraph:
    g = builder.from_manifests(
        entry="data_harvester",
        layers=[
            ["data_harvester"],
            ["portfolio_orchestrator"],
            ["trend_phase_analyst", "level_analyst"],   # 轻量模式:跳过 GEX / Max Pain
            ["passive_health_check"],
        ],
        end_node="passive_health_check",
        mode="lightweight",
    )
    return g.compile()
```

### 3.5 PassiveHealthCheckAgent 完整实现

**文件**: `backend/aegis/agents/passive_health_check_agent.py`

```python
class PassiveHealthCheckAgent(BaseAgent):
    manifest = AgentManifest(
        name="passive_health_check",
        version="0.1.0",
        requires=["ticker_analyses"],
        provides=["passive_health_alerts"],
        tags=["passive", "rule_only"],
        llm_dependency=False,
        parallel_group=None,
        pipeline_mode="lightweight",
        enabled=True,
    )

    async def run(self, state: PipelineState) -> PipelineState:
        alerts = []
        for ticker in state.tickers_holdings_passive:
            pos = self._get_position(state, ticker)
            
            # 1. 动态止损巡检
            stop_alert = self._check_dynamic_stop(state, ticker, pos)
            if stop_alert:
                alerts.append(stop_alert)
            
            # 2. DTE 巡检（LEAPS DTE ≤ 90 天预警）
            if pos.get("dte") and pos["dte"] <= 90:
                alerts.append({
                    "ticker": ticker,
                    "type": "leaps_dte_90",
                    "dte": pos["dte"],
                    "message": f"{ticker} LEAPS DTE={pos['dte']} days, consider roll or close",
                })
            
            # 3. Theta 加速检测（DTE < 60 且 Theta 日衰减 > 阈值）
            if self._theta_accelerating(pos):
                alerts.append({
                    "ticker": ticker,
                    "type": "theta_accelerating",
                    "theta": pos.get("theta"),
                    "dte": pos.get("dte"),
                    "message": f"{ticker} Theta acceleration detected, daily decay increasing",
                })
            
            # 4. 偏离度检查（现有 M1 逻辑保留）
            deviation = self._price_deviation(state, ticker, pos)
            if abs(deviation) > 0.10:
                alerts.append({
                    "ticker": ticker,
                    "type": "price_deviation",
                    "deviation_pct": deviation,
                })

        state.passive_health_alerts = alerts
        return state

    def _check_dynamic_stop(self, state, ticker, pos) -> dict | None:
        """
        根据 stop_loss 模式检查:
        - support_based: 价格 < support_level → 预警
        - fixed_pct: 价格跌幅 > threshold → 预警
        """

    def _theta_accelerating(self, pos: dict) -> bool:
        """
        DTE < 60 且:
        - Theta absolute value > 前 5 日均值 × 1.5
        - 或 Theta / Option Value > 2% 每日
        """
```

### 3.6 Pending Triggers — TriggerCheckRunner

**文件**: `backend/aegis/pipeline/trigger_runner.py`

```python
class TriggerCheckRunner:
    """每小时扫描 Pending Triggers，检查是否触发"""

    async def run(self) -> list[dict]:
        """
        1. 从 pipeline.db 查询 status='pending' 且 valid_until > now 的 triggers
        2. 对每个 trigger 检查是否满足条件
        3. 触发的 → mark_triggered + 发送 Telegram 通知
        4. 过期的 → mark_expired
        5. 返回本次触发的 triggers 列表
        """
        triggers = await self.store.list_active_triggers()
        fired = []
        for trigger in triggers:
            if self._is_triggered(trigger):
                await self.store.mark_triggered(trigger["id"])
                await self.telegram.send_trigger_fired(trigger)
                fired.append(trigger)
            elif trigger["valid_until"] < datetime.now(timezone.utc):
                await self.store.mark_expired(trigger["id"])
        return fired

    def _is_triggered(self, trigger: dict) -> bool:
        """
        根据 trigger_type 检查:
        - price_below: 当前价 < threshold
        - price_above: 当前价 > threshold
        - rsi_below: RSI(14) < threshold
        - volume_spike: 当日量 > 20 日均量 × multiplier
        """
```

### 3.7 Trigger Store

**文件**: `backend/aegis/storage/trigger_store.py`

```python
class TriggerStore:
    """Pending Triggers 的 CRUD 操作（pipeline.db）"""

    async def create_trigger(self, trigger: dict) -> int: ...
    async def list_active_triggers(self) -> list[dict]: ...
    async def mark_triggered(self, trigger_id: int) -> None: ...
    async def mark_expired(self, trigger_id: int) -> None: ...
    async def cancel_trigger(self, trigger_id: int) -> None: ...
    async def get_trigger(self, trigger_id: int) -> dict | None: ...
```

### 3.8 APScheduler 配置

**修改**: `backend/aegis/pipeline/scheduler.py`

```python
# 新增 trigger_check job（按 schedule.yaml）
scheduler.add_job(
    trigger_check_runner.run,
    CronTrigger(minute=0, day_of_week="mon-fri"),  # 每小时整点
    timezone="America/New_York",
    id="trigger_check",
)
```

### 3.9 REST API 完善

**修改**: `backend/aegis/api/routes/` 下的路由文件

Sprint-0 搭建了骨架，本分支实现所有 M2 新增路由的真实逻辑：

| 路由 | 文件 | 实现内容 |
|---|---|---|
| `POST /api/v1/pipeline/trigger` | `pipeline.py` | 手动触发 Pipeline（支持 mode=full/lightweight） |
| `GET /api/v1/portfolio/health` | `positions.py` | 返回 health_scores |
| `GET /api/v1/portfolio/delta-dollars` | `positions.py` | 返回 Delta Dollars 汇总 |
| `GET /api/v1/triggers` | `triggers.py` | 返回 active triggers 列表 |
| `DELETE /api/v1/triggers/{id}` | `triggers.py` | 取消指定 trigger |
| `GET /api/v1/flows/etf` | `flows.py`（新建） | 返回 ETF 资金流数据 |
| `GET /api/v1/flows/sector` | `flows.py` | 返回板块轮动数据 |
| `GET /api/v1/flows/smart-money/{ticker}` | `flows.py` | 返回 Smart Money 详情 |
| `GET /api/v1/agents` | `agents.py` | 返回 manifest 列表 |

**新建**: `backend/aegis/api/routes/flows.py`

### 3.10 WebSocket 实现

**文件**: `backend/aegis/api/ws.py`

```python
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

class PipelineWSManager:
    """管理 WebSocket 连接,广播 Pipeline 事件"""

    async def broadcast(self, event: PipelineEvent):
        """向所有连接的客户端广播事件"""

# Pipeline Runner 在各节点执行前后发送事件:
# - agent_start: agent 开始执行
# - agent_complete: agent 完成（含耗时）
# - agent_failed: agent 失败
# - pipeline_complete: 整个 pipeline 完成
# - trigger_fired: trigger 被触发
```

### 3.11 Telegram 模板更新

**修改**: `backend/config/prompts/telegram_*.j2`

- 新增 Smart Money + Fund Flow 数据段落
- 新增 entry_mode 标签
- 新增 trigger_fired 通知模板
- 新增 Lightweight Pipeline 的止损预警 / DTE 预警 / Theta 加速预警格式

### 3.12 Sprint-0 遗留项修复

按 `docs/dev-plan/sprint-0-review-followups.md` 修复以下 7 项：

| # | 项目 | 修复内容 |
|---|---|---|
| 1 | pyproject.toml 与 ruff.toml 配置重复 | 删除 `ruff.toml`，保留 `pyproject.toml` 中的 [tool.ruff] |
| 2 | Makefile typecheck 路径错误 | `cd backend && mypy aegis`（去掉双重嵌套） |
| 3 | `__init__.py` 添加版本号 | `__version__ = "0.2.0"`（M2 版本） |
| 4 | `alembic.ini` 硬编码数据库 URL | 改为占位符 + 从环境变量读取 |
| 5 | Generic type annotations | `dict[str, Any]` 替代 `Dict[str, Any]` 等 |
| 6 | tests 目录 `__init__.py` | 确保所有 test 子目录有 `__init__.py` |
| 7 | tools.yaml 统一配置格式 | 所有 tool 统一 rate_limit / circuit_breaker / bound_agents 格式 |

---

## 4. 测试要求

### 4.1 Part 1 单元测试（Agent 升级）

| 文件 | 测试点 |
|---|---|
| `test_options_s1_iv_crush.py` | IV crush 评估逻辑 + 事件前 5 日判定 + IV rank 阈值 |
| `test_options_s2_entry_mode.py` | 左侧/右侧/both 判定逻辑 |
| `test_options_s2_multi_strategy.py` | 多策略生成 ≥ 2 个方案 + 对比字段完整 |
| `test_options_s2_scenario_pnl.py` | 三场景 P&L 计算 + Theta 衰减 |
| `test_options_s2_roll.py` | Roll 评估维度 + QQQ 排除 + action 输出 |
| `test_options_s2_batch_entry.py` | 分批方案生成 + trigger 提取 |
| `test_research_v2_right_filter.py` | 假突破过滤逻辑 + volume 判定 |
| `test_research_v2_add_on.py` | 加仓评估条件 + 推荐生成 |
| `test_research_v2_cooldown.py` | 30 天冷却期 + 强反转信号例外 |
| `test_research_v2_triggers.py` | 条件触发提取 + PendingTrigger 格式 |
| `test_research_v2_cc_timing.py` | CC Timing Guard 三条件判定 |
| `test_research_v2_ranking.py` | 四优先级排序 + 每日上限 |
| `test_risk_gate_v2_delta.py` | Delta Dollars 预算计算 + 按 score 裁剪 |
| `test_risk_gate_v2_iv_crush.py` | IV crush guard 拦截 + block_reason 格式 |

### 4.2 Part 2 单元测试（Pipeline 集成）

| 文件 | 测试点 |
|---|---|
| `test_graph_builder_parallel.py` | 并行 fan-out + fan-in + Annotated reducer |
| `test_graph_builder_modes.py` | full / lightweight 模式切换 |
| `test_state_reducers.py` | merge_dicts + merge_lists 正确性 |
| `test_passive_health_check.py` | 动态止损 + DTE 预警 + Theta 加速 + 偏离度 |
| `test_trigger_runner.py` | 触发检查 + 过期处理 + Telegram 通知 |
| `test_trigger_store.py` | CRUD + 状态转换 |
| `test_api_flows.py` | /flows/etf + /flows/sector + /flows/smart-money |
| `test_api_triggers.py` | GET + DELETE triggers |
| `test_api_pipeline_trigger.py` | POST /pipeline/trigger + mode 参数 |
| `test_ws_pipeline.py` | WebSocket 连接 + 事件广播 |

### 4.3 端到端集成测试

| 文件 | 测试点 |
|---|---|
| `test_full_pipeline_e2e.py` | Full Pipeline 端到端: DataHarvester → ... → RiskGate，含 Smart Money + Fund Flow |
| `test_lightweight_pipeline_e2e.py` | Lightweight Pipeline 端到端: 止损 + DTE + Theta 预警 |
| `test_pipeline_parallel.py` | 验证信号层并行执行（agent_timings 证明并行） |
| `test_pipeline_error_recovery.py` | 单个 Agent 失败不阻塞 Pipeline |
| `test_trigger_lifecycle.py` | 创建 → 检查 → 触发 / 过期 / 取消 完整生命周期 |
| `test_debate_smart_money_fund_flow.py` | Debate prompt 含 smart_money_context + fund_flow_context |
| `test_delta_budget_e2e.py` | 注入超预算推荐 → blocked |
| `test_api_e2e.py` | 所有 API 路由返回正确 schema |

---

## 5. 验收清单

对应 M2 总 README 的 10 条验收标准 + 本分支附加项：

**M2 全局验收**:
- [ ] ① `aegis run --ticker QQQ --mode pre-market` 端到端跑通，含 Smart Money + Fund Flow 数据
- [ ] ② Signal 层 Agent 并行执行，总 Pipeline 耗时 ≤ 3 分钟（agent_timings 验证）
- [ ] ③ Web Dashboard 可访问 `http://localhost:3000`
- [ ] ④ 至少 1 个券商 API 实时拉取持仓（或 SIMULATE 模式）
- [ ] ⑤ Options Strategist S2 输出 ≥ 2 个策略对比 + P&L 场景
- [ ] ⑥ Pending Trigger 创建 + 每小时检查 + 触发通知
- [ ] ⑦ Lightweight Pipeline 输出动态止损状态 + DTE 预警
- [ ] ⑧ Delta Dollars 增量预算拦截生效
- [ ] ⑨ 全部测试通过 + ruff + mypy 全绿
- [ ] ⑩ Smart Money / Fund Flow 数据写入 extensions + Debate 引用

**Part 1 验收**:
- [ ] Options Strategist S1 输出 iv_crush_risk
- [ ] Options Strategist S2 输出 entry_mode + ≥ 2 个策略方案
- [ ] 每个方案含 scenario_pnl（target / flat / stop_loss）
- [ ] 持仓 LEAPS（非 QQQ）有 Roll 评估输出
- [ ] 左侧入场有分批方案
- [ ] Research Manager 输出 PendingTrigger
- [ ] 右侧假突破过滤生效
- [ ] 加仓建议生效
- [ ] 30 天冷却期生效
- [ ] CC Timing Guard 生效
- [ ] 推荐按 urgency 排序，上限 10 个
- [ ] Risk Gate Delta Dollars 预算拦截生效
- [ ] Risk Gate IV crush guard 拦截生效
- [ ] strategy_comparisons + scenario_pnl 写入 state
- [ ] rules.yaml 新增配置项完整

**Part 2 验收**:
- [ ] graph_builder 并行 fan-out / fan-in 正常工作
- [ ] Annotated state reducers 正确合并并行写入
- [ ] PassiveHealthCheckAgent 输出动态止损 + DTE + Theta 预警
- [ ] TriggerCheckRunner 每小时扫描 + 触发通知
- [ ] TriggerStore CRUD 正常
- [ ] REST API 所有 M2 新增路由可用
- [ ] WebSocket Pipeline 事件广播正常
- [ ] Telegram 消息含新数据段落
- [ ] Sprint-0 遗留 7 项全部修复
- [ ] 单测 + 集成测试全绿

---

## 6. 分支合并顺序

本分支是最后一个合入的分支，合并顺序为：

```
Sprint-0 → A (Smart Money) → B (Fund Flow) → C (Broker)
→ D (Frontend) → E+F (本分支)
```

**合并步骤**:
1. 从 develop（已包含 Sprint-0 + A + B + C）创建本分支
2. 先完成 Part 1（Agent 升级），运行单测
3. 再完成 Part 2（Pipeline 集成 + API + Triggers + Lightweight）
4. 合入 D（Frontend）的变更
5. 运行全量测试 + ruff + mypy + 集成测试
6. 修复所有冲突和集成问题
7. PR 合入 develop

---

## 7. 不允许做的事

- 不修改 PipelineState 契约字段（Sprint-0 已定义），仅添加 Annotated reducer 注解
- 不修改 Smart Money / Fund Flow Agent 业务逻辑（A/B 分支负责）
- 不修改 Broker 适配器逻辑（C 分支负责）
- 不修改前端组件逻辑（D 分支负责）
- 不实现 Universe Triage 完整扫描逻辑（M3 的事）
- 不实现 KOL Tracker（M3 的事）
- 不实现完整四层 Memory + WeightAdapter（M3 的事）
- 不实现 Pipeline DAG 可视化（M4 的事）
- 不实现 `aegis scaffold` CLI（M4 的事）
