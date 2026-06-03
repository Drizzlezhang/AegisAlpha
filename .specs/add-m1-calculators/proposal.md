# Change: add-m1-calculators

## 概述
实现 M1 所需的全部纯计算模块（Greeks、Stop Loss、Wyckoff、GEX、Volume Profile），为 Agents 提供确定性数值计算。

## 动机
Branch B 是 M1 的三大并行分支之一，负责所有纯计算逻辑。这些计算模块是 Risk Gate Agent、Options Strategist Agent 等上游 Agent 的数值基础，必须在 M1 阶段完成并冻结接口。

## 影响范围
- `backend/aegis/calculators/` — 新增 5 个计算模块 + models.py
- `backend/tests/calculators/` — 新增 5 个测试文件
- `backend/tests/fixtures/` — 新增 2 个测试数据文件
- 不修改任何现有文件（纯增量）

## 验收目标
- [ ] 5 个计算模块全部实现，函数纯 sync，无 LLM/IO 依赖
- [ ] 返回值全部为 Pydantic BaseModel
- [ ] `stop_loss.py` 支持 `mode="support_based"` 参数
- [ ] pytest 全绿，浮点比较用 `pytest.approx`
- [ ] ruff + mypy 通过
- [ ] AGENTS.md 7.2 强制单测清单全部覆盖

## Size: M
## 推断依据
- 范围：单模块 `calculators/`，5 个子模块 + models + 5 测试 + 2 fixture ≈ 12 文件
- 关键词：`实现所有 M1 需要的纯计算模块` — 新功能开发
- 预估文件数：10-15（M 范围 10-30）
- 依赖变更：仅内部，无新增外部依赖
- 风险：需回归测试，涉及 AGENTS.md 7.2 强制单测清单
- `project.yaml.scale` = M，与推断一致

## 阶段序列
0 → 1 → 2 → 3 → 4 → 5 → 6
