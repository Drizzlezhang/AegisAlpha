# Change: m1-debate-agent

## 概述
实现多轮 Bull vs Bear 辩论 + Judge 裁决 Agent，输出结构化 DebateResult。

## 动机
M1 阶段需要 Debate Agent 作为信号分析链的最后一环，对 factor_scores 进行多角度辩论后输出方向性裁决。这是 Pipeline 中唯一的多角色 LLM 调用组件，也是后续 M2 Smart Money / Fund Flow 数据入辩论的前置基础。

## 影响范围
- 新增：`backend/aegis/agents/debate_agent.py`
- 新增：`backend/config/prompts/debate_bull.j2`、`debate_bear.j2`、`debate_judge.j2`
- 新增：`backend/tests/agents/test_debate_agent.py`
- 新增：`backend/tests/fixtures/debate_mock_factor_scores.json`、`debate_judge_response.json`
- 依赖：`LLMClient`、`BaseAgent`、`PipelineState`、`AgentManifest`

## 验收目标
- [ ] Bull/Bear 使用 `LLM_MODEL_PRIMARY`，Judge 使用 `LLM_MODEL_MINI`
- [ ] 所有 prompt 从 `config/prompts/*.j2` 加载，无 hardcode
- [ ] prompt 含 `{{ smart_money_context }}` / `{{ fund_flow_context }}` 预留变量
- [ ] Judge JSON schema 含 `entry_mode_hint` 预留字段
- [ ] 3 个必测 case 全绿（提前结束 / 跑满 / JSON 解析失败）
- [ ] token 消耗写入 `state.agent_timings["debate_agent"]`

## Size: S
## 推断依据
- 范围：单模块（agents），~7 文件
- 关键词：`feature`（新 Agent 开发）
- 预估文件数：7（1 Agent + 3 prompt + 1 test + 2 fixture）
- 依赖变更：无新增外部依赖，仅内部 LLMClient + BaseAgent
- 风险：局部影响，需回归测试

## 阶段序列
0 → 1 → 4 → 5 → 6
