# 0-CHANGE — 提出变更

## 输入
- 用户的一句话描述

## 必做事项
- 捕获用户意图
- 澄清模糊描述
- 确定变更边界和影响范围
- 生成 `change-id`
- 推断 `Size`
- 创建 `.specs/<change-id>/proposal.md`

## 退出检查清单
- [ ] `proposal.md` 已创建且包含 Size 与推断依据
- [ ] 根级 `.specs/STATE.md` 已指向当前 change
- [ ] change 级 `.specs/<change-id>/STATE.md` 已按 `templates/STATE.md` 创建
- [ ] `_meta.yaml.current_stage` 已更新
- [ ] `STATE.md.Recent Changes` 已 append 本阶段摘要
