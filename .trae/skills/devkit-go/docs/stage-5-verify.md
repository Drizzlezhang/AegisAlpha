# 5-VERIFY — 测试验证

渲染规则见 `bin/render-template.js`；阶段切换输出形式见 `docs/workflow-overview.md` 的“阶段切换仪式”。

## 输入
- 代码变更
- 优先读取 `requirements.md`
- 若 XS 或 `requirements.md` 缺失，则回退读取 `proposal.md`

## 验证模式
- `5-lite`：仅用于 XS。执行最小必要验证，例如受影响命令、核心测试、关键手动路径或最小 lint/typecheck 子集，并记录为什么采用轻量验证。
- `5-full`：用于 S/M/L。执行完整测试、lint、类型检查，并逐条对照验收标准核验。

## 必做事项
- 运行测试、lint、类型检查或等效最小验证
- 按 `requirements.md` 中 AC 的“验证方式”列逐条核验，不新增未在 SPEC 中声明的验证方式
- 形成结构化验证记录
- 如果验证失败，回退到 `4-BUILD` 重试，最多 3 次
- 每次失败都必须增加 `_meta.yaml` 的 `retry_count`
- 如果存在少量非阻塞问题但主路径已通过，可标记为 `partial-pass`

## 重试上限决策

`_meta.yaml.retry_count` 在每次 VERIFY 失败回 BUILD 时 +1。

| retry_count | 默认动作 |
|------------|---------|
| 0-2 | 直接回 BUILD，并把失败原因记录到 `STATE.md` 的 `## Notes` |
| 3 | **强制 gate**：触发 `retry-limit`，展示升级 / 降级 / 中止三选一，等待用户决策 |
| ≥4 | 禁止再回 BUILD，只允许升级 / 降级 / 中止 |

### 三选一定义
1. **升级（escalate）**：Size 上调一档（XS→S，S→M，M→L），重新补齐新 Size 所需的 SPEC / DESIGN / PLAN 必填段，并将 `retry_count` 清零。
2. **降级（reduce-scope）**：把验收标准拆成“已通过”和“延后”，当前 change 以 `partial-pass` 进入 SHIP，延后部分新建 change。
3. **中止（abandon）**：把 `_meta.yaml.status` 置为 `abandoned`，并执行 state-management 中定义的归档流程。

## partial-pass 规则
只有在以下条件同时满足时，才允许使用 `partial-pass`：
1. 主路径与核心验收标准已通过。
2. 未通过项不影响当前交付目标的可用性。
3. 剩余问题已被明确记录，可继续修复或后续跟进。
4. 进入 SHIP 前必须向用户展示剩余问题并获得确认。

若不满足以上条件，必须按 `verify-fail` 处理，不得滥用 `partial-pass`。

## 退出检查清单
- [ ] `verification.md` 已创建并包含结构化验证记录
- [ ] `verification.md` 已按 AC 与验证方式逐条对账
- [ ] `_meta.yaml.current_stage` 与 `retry_count` 已更新
- [ ] `.specs/STATE.md` 与当前 change 同步
- [ ] `_meta.yaml.last_next` 已更新
- [ ] `_meta.yaml.last_progress_note` 已更新
- [ ] `_meta.yaml.schema_version == 2`
- [ ] `STATE.md.Recent Changes` 已 append 本阶段摘要

## 产物要求
创建 `.specs/<change-id>/verification.md`，参考 `templates/VERIFICATION.md` 结构。

## 输出要求
`verification.md` 必须至少包括：
- 验证时间
- 验证模式（`5-lite` 或 `5-full`）
- AC 对账说明
- 验收标准逐条验证表
- 单元测试结果
- Lint 结果
- 类型检查结果
- 是否通过（`pass` / `partial-pass` / `fail`）
- 失败项或剩余问题（如有）
- 建议操作
