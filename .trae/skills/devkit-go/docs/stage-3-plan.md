# 3-PLAN — 任务拆解

渲染规则见 `bin/render-template.js`；阶段切换输出形式见 `docs/workflow-overview.md` 的“阶段切换仪式”。

## 输入
- `design.md`

## 必做事项
- 将设计拆成可执行原子任务
- 标注依赖关系与优先级
- 分成可并行的波次
- 每个任务都必须带 `verify` 命令
- 明确每个任务读哪些文件、写哪些文件

## 退出检查清单
- [ ] `tasks.md` 已创建且带 verify 命令
- [ ] `_meta.yaml.current_stage` 已更新
- [ ] `.specs/STATE.md` 与当前 change 同步
- [ ] `_meta.yaml.last_next` 已更新
- [ ] `_meta.yaml.schema_version == 2`
- [ ] `STATE.md.Recent Changes` 已 append 本阶段摘要
