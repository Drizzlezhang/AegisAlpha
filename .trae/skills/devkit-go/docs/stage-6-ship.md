# 6-SHIP — 提交发布

## 输入
- 验证通过的代码变更
- `proposal.md`

## 必做事项
- 生成符合 conventional commits 的 commit message
- 根据 Size 判断是否需要先经过 `pre-commit` gate
- 检查本次变更是否需要同步更新 README.md（参考 `docs/readme-update-check.md`）
- 执行 `git commit`
- 提示用户是否继续 push 或创建 PR
- 将 `_meta.yaml` 标记为 `completed`

## 退出检查清单
- [ ] commit message 已准备或已提交
- [ ] `_meta.yaml.status` 已更新为最终状态
- [ ] `.specs/STATE.md` 与当前 change 同步
- [ ] `_meta.yaml.last_next` 已更新
- [ ] `_meta.yaml.schema_version == 2`
- [ ] `STATE.md.Recent Changes` 已 append 本阶段摘要
- [ ] 已检查 README.md 是否需要同步更新

## 产物要求
- git commit hash
- `_meta.yaml` 中 `status: completed`

## 规则
1. commit message 必须是 conventional commits 风格。
2. 如果 Size ≥ L，必须先经过 review gate，再允许提交。
3. 如果 Size ≥ S，提交前必须经过 `pre-commit` 确认，明确本次提交粒度、验证状态与剩余风险。
4. XS：允许单提交直接交付。
5. S：默认单提交；若实现和验证记录明显可分，则允许拆为两个提交，但不得制造无意义碎片。
6. M/L：默认按可审阅逻辑拆分提交，避免把多个独立主题压进一个 commit。
7. 提交后要向用户展示 commit hash。
8. push 和创建 PR 只提示，不默认执行，除非用户明确要求。
9. 若 VERIFY 结果为 `partial-pass`，必须在 `pre-commit` 中再次确认用户接受剩余问题，才能提交。
