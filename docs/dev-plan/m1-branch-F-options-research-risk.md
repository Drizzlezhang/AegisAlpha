# Branch F — Options S2 + Research Manager + Risk Gate — Plan Prompt

> **分支**: `feat/m1-orchestration`
> **估时**: 5 天
> **依赖**: Branch B(calculators) + D(analysts) + E(debate) 完成
> **子 Agent**: `m1-orchestration`
> **前置阅读**: `AGENTS.md` 第 12 节 + `docs/aegis-2.0-tech-arch.md` Section 4.4/4.6/4.7/4.9

---

## 目标

实现决策链后半段:Options Strategist S2(合约方案生成) → Research Manager(推荐排序) → Risk Gate(硬规则拦截)。

## 范围

### Options Strategist Step 2

- 输入: debate_result + options_step1 候选 + levels(support/resistance)
- LLM 调用(gpt-4o): 生成最终合约方案 + rationale
- **v1.2 新增**:
  - 输出含 `entry_mode` 标记(M1 固定为 `"passive"`,因为只分析 QQQ;M2 升级为左右侧判断)
  - 计算 `stop_loss` 时调用 `calculators.stop_loss(mode="support_based", support_level=levels.support_levels[0])` 如有支撑位;否则 fallback 到 `fixed_pct`
  - 输出 `delta_dollars_delta` 估算(该合约增加多少 Delta 暴露)
- Prompt: `config/prompts/options_strategist_s2.j2`
- manifest: `pipeline_mode="full"`, `llm_dependency=True`

### Research Manager

- 输入: options_step2 + debate_results + portfolio
- 输出: `state.recommendations` 排序列表(按 urgency + score)
- **v1.2 新增**:
  - 每个 recommendation 含 `delta_dollars_delta` 字段(从 Options S2 传入)
  - `pending_triggers` 预留:M1 不实现条件触发,但写入 `state.pending_triggers = []` 占位
- LLM 调用(gpt-4o): 最终推荐文案生成
- Prompt: `config/prompts/research_manager_synthesis.j2`
- manifest: `pipeline_mode="full"`, `llm_dependency=True`

### Risk Gate

- 输入: `state.recommendations`
- 输出: 通过的留在 `state.recommendations`;被拦截的移入 `state.blocked_recommendations`
- **7 + 1 规则(M1)**:
  1. 总仓位 > 80% → 阻止 buy/add
  2. 现金 < 20% → 阻止 buy/add
  3. 黑名单标的 → 阻止任何
  4. LEAPS DTE < 12 月 → 阻止新建 LEAPS
  5. VIX > 30 或日涨幅 > 20% → 阻止所有新建
  6. FOMC/CPI/NFP 前 24h → 阻止 LEAPS
  7. 财报前 48h → 阻止该标的
  8. **支撑位动态止损校验**(v1.2): active_left 推荐必须含 stop_loss(support_based);缺失则阻止
- **v1.2 预留(M1 不实现)**:
  - Δ Dollars 增量预算(M2 落地,M1 仅在 rules.yaml 声明 `delta_dollars_budget_pct: 0.30`)
  - IV crush guard(M2)
  - post-close 冷却(M2)
- LLM: 无
- manifest: `pipeline_mode="full"`, `llm_dependency=False`

## 文件清单

```
backend/aegis/agents/
├── options_strategist_s2_agent.py
├── research_manager_agent.py
└── risk_gate_agent.py

backend/config/prompts/
├── options_strategist_s2.j2
└── research_manager_synthesis.j2

backend/config/
└── rules.yaml                     # Risk Gate 规则 + delta_dollars_budget_pct 预留

backend/tests/agents/
├── test_options_strategist_s2.py  # 合约生成 + stop_loss 模式选择
├── test_research_manager.py       # 排序逻辑 + pending_triggers 占位
└── test_risk_gate.py              # ≥10 case(7 规则 + support_based 校验 + 边界)

backend/tests/fixtures/
├── risk_gate_vix_spike.json
├── risk_gate_earnings_upcoming.json
└── risk_gate_position_limit.json
```

## 必测项(AGENTS.md 7.2 强制)

| 模块 | Case |
|---|---|
| risk_gate | 7 规则各 1 case + support_based 缺失拦截 + 全通过 + 边界(正好 80%) = ≥10 case |

## 验收

- [ ] Options S2 输出含 `stop_loss.mode` + `delta_dollars_delta`
- [ ] Research Manager 输出 `recommendations` 按 urgency × score 排序
- [ ] Risk Gate 8 规则全部可验证
- [ ] `rules.yaml` 含 `delta_dollars_budget_pct: 0.30` 声明(M1 不消费)
- [ ] pytest 全绿
