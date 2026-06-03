# Gate 与失败处理

你必须在以下条件触发时暂停并向用户展示产物或失败信息：

| Gate | XS | S | M | L | 行为 |
|------|----|---|---|---|------|
| post-spec | 跳过 | 可选 | 必选 | 必选 | 展示 `requirements.md`，等待用户审核确认 |
| post-design | 跳过 | 跳过 | 可选（仅高风险） | 必选 | 展示 `design.md`，确认关键设计与风险控制 |
| post-plan | 跳过 | 跳过 | 可选（仅高风险） | 必选 | 展示 `tasks.md`，确认拆解、依赖与 verify 命令 |
| verify-fail | 按失败触发 | 按失败触发 | 按失败触发 | 按失败触发 | 展示失败详情，询问重试或放弃 |
| retry-limit | 按阈值触发 | 按阈值触发 | 按阈值触发 | 按阈值触发 | `retry_count == 3` 时强制展示升级 / 降级 / 中止三选一；`retry_count >= 4` 时禁止静默回 BUILD |
| partial-pass | 按需触发 | 按需触发 | 按需触发 | 按需触发 | 展示剩余问题、影响范围与建议后续动作，确认是否允许继续进入 SHIP |
| pre-commit | 必选 | 必选 | 必选 | 必选 | 在提交前确认提交粒度、验证状态、剩余风险 |
| pre-ship | 跳过 | 跳过 | 跳过 | 必选 | 强制执行 review 后才能提交 |

## 使用原则
- M 级默认只保留 `post-spec` 与 `pre-commit` 两个必选 gate；只有设计风险高、依赖复杂或用户显式要求时，才补 `post-design` / `post-plan`。
- L 级保持完整 gate 链路，不主动裁剪。
- XS/S 如果目标清晰且风险低，可以跳过中间审核 gate，但不能跳过最终验证与 `pre-commit`。

## 失败处理
- 验证失败时，必须展示失败详情，而不是笼统地说“没通过”。
- 当 `retry_count` 达到 3 次仍未通过时，必须触发 `retry-limit` gate，向用户说明阻塞点与三选一方案，不得继续无限重试。
- 当 `retry_count >= 4` 时，禁止再回 BUILD，只允许升级、降级或中止。
- 如果用户选择放弃，必须把 `_meta.yaml` 标记为 `abandoned`，并执行归档流程，同时更新根级 `.specs/STATE.md`。
- 如果 VERIFY 为 `partial-pass`，必须记录剩余问题与用户确认结果，不能静默当作完全通过。
