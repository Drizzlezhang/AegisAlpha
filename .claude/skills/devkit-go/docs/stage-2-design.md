# 2-DESIGN — 技术设计

渲染规则见 `bin/render-template.js`；阶段切换输出形式见 `docs/workflow-overview.md` 的“阶段切换仪式”。

## 输入
- `requirements.md`

## 必做事项
- 输出技术方案概述
- 给出 API 设计（如适用）
- 给出数据模型或类型定义（如适用）
- 拆分组件或模块职责
- 记录架构决策（ADR）
- 分析风险与缓解措施

## 退出检查清单
- [ ] `design.md` 已创建且符合当前 Size 的模板裁剪结果
- [ ] `_meta.yaml.current_stage` 已更新
- [ ] `.specs/STATE.md` 与当前 change 同步
- [ ] `_meta.yaml.last_tldr` 已更新
- [ ] `_meta.yaml.last_next` 已更新
- [ ] `_meta.yaml.schema_version == 2`
- [ ] `STATE.md.Recent Changes` 已 append 本阶段摘要
