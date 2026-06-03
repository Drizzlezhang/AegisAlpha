# Requirements: m1-debate-agent

## 功能需求

### FR-1: 三角色 LLM 辩论
- Given: PipelineState 包含 `analyst_outputs` 中的 factor_scores
- When: DebateAgent.run(state) 被调用
- Then: Bull(gpt-4o, temp 0.7) 和 Bear(gpt-4o, temp 0.7) 交替辩论，Judge(gpt-4o-mini, temp 0.3) 每轮裁决，输出结构化 DebateResult

### FR-2: 辩论轮次控制
- Given: 辩论配置 `max_rounds=3`
- When: 辩论进行中
- Then: 最多 3 轮；若 Judge 信心 > 0.85 且连续 2 轮方向一致则提前结束

### FR-3: Prompt 模板加载
- Given: `config/prompts/debate_bull.j2`、`debate_bear.j2`、`debate_judge.j2` 存在
- When: DebateAgent 初始化
- Then: 从 Jinja2 模板加载 prompt，禁止 hardcode

### FR-4: v1.2 预留变量
- Given: Bull/Bear prompt 模板含 `{{ smart_money_context }}` / `{{ fund_flow_context }}`
- When: M1 阶段渲染 prompt
- Then: 两个变量传入空字符串，M2 阶段可替换为实际数据

### FR-5: Judge JSON Schema
- Given: Judge prompt 要求输出 JSON
- When: Judge 返回响应
- Then: 按 schema 校验（含 `direction / confidence / rationale / rounds_used / entry_mode_hint`），`entry_mode_hint` M1 可空

### FR-6: JSON 解析失败重试
- Given: Judge 返回非 JSON 或 schema 校验失败
- When: 解析失败
- Then: 重试 1 次；仍失败则写 `state.error_flags`，Pipeline 继续

### FR-7: 输出写入
- Given: 辩论完成
- When: 结果生成
- Then: 写入 `state.debate_results[ticker]`（含 direction / confidence / rationale / rounds_used），token 消耗写入 `state.agent_timings["debate_agent"]`

## 验收标准与验证方式

| AC | 验证方式 |
|----|---------|
| AC-1: Bull/Bear 使用 `LLM_MODEL_PRIMARY`，Judge 使用 `LLM_MODEL_MINI` | 单元测试：mock LLMClient.chat，断言 Bull/Bear 调用 model="gpt-4o"，Judge 调用 model="gpt-4o-mini" |
| AC-2: 所有 prompt 从 `config/prompts/*.j2` 加载，无 hardcode | 代码审查：DebateAgent 中无内联 prompt 字符串，全部通过 Jinja2 Environment 加载 |
| AC-3: prompt 含 `{{ smart_money_context }}` / `{{ fund_flow_context }}` 预留变量 | 检查 3 个 .j2 模板文件内容 |
| AC-4: Judge JSON schema 含 `entry_mode_hint` 预留字段 | 检查 debate_judge.j2 中 JSON schema 定义 |
| AC-5: 3 个必测 case 全绿（提前结束 / 跑满 / JSON 解析失败） | 运行 `uv run pytest tests/agents/test_debate_agent.py -v` |
| AC-6: token 消耗写入 `state.agent_timings["debate_agent"]` | 单元测试：mock LLMClient 返回 usage，断言 agent_timings 含 debate_agent 且值 > 0 |

## 用户故事
- As a Pipeline Runner, I want the Debate Agent to produce a directional verdict after multi-round Bull vs Bear debate, so that downstream Risk Gate has a confidence-weighted signal to work with.
- As a developer, I want the debate prompts to be externalized as Jinja2 templates, so that I can tune the debate logic without touching Python code.
- As a future M2 developer, I want `smart_money_context` and `fund_flow_context` placeholders in the prompts, so that I can inject new data sources without rewriting the debate agent.
