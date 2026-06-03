# 1-SPEC — 编写需求

渲染规则见 `bin/render-template.js`；阶段切换输出形式见 `docs/workflow-overview.md` 的“阶段切换仪式”。

## 输入
- `proposal.md`

## 必做事项
- 将 proposal 转化为结构化需求文档
- 写清功能需求与非功能需求
- 定义 Given / When / Then 验收标准
- 为每条 AC 补齐对应的“验证方式”，不得只写标准不写验证方式
- 补充边界场景
- 明确 out of scope

## 退出检查清单
- [ ] `requirements.md` 已创建且符合当前 Size 的模板裁剪结果
- [ ] `requirements.md` 中每条 AC 都包含对应验证方式
- [ ] `_meta.yaml.current_stage` 已更新
- [ ] `.specs/STATE.md` 与当前 change 同步
- [ ] `_meta.yaml.last_tldr` 已更新
- [ ] `_meta.yaml.last_next` 已更新
- [ ] `_meta.yaml.schema_version == 2`
- [ ] `STATE.md.Recent Changes` 已 append 本阶段摘要
