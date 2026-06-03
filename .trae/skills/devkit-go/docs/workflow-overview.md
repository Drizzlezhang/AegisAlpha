# 工作流总览

## 总流程
```text
0-CHANGE → 1-SPEC → 2-DESIGN → 3-PLAN → 4-BUILD → 5-VERIFY → 6-SHIP
                                                     ↑          |
                                                     └──────────┘
                                                   （验证失败 → 重试）
```

## 调用方式
- `/devkit-go <一句话需求>`：直接启动一个新的 change。
- `/devkit-go`：如果 `.specs/STATE.md` 中存在活跃 change，则继续该 change；否则先询问用户本次要处理的一句话需求。

## 变更即文件夹
每次 `/devkit-go` 必须创建或使用如下目录：
```text
.specs/<change-id>/
├── proposal.md
├── requirements.md
├── design.md
├── tasks.md
├── verification.md
└── _meta.yaml
```

## 模板映射
- `templates/CHANGE.md` → `.specs/<change-id>/proposal.md`
- `templates/REQUIREMENT.md` → `.specs/<change-id>/requirements.md`
- `templates/DESIGN.md` → `.specs/<change-id>/design.md`
- `templates/TASK.md` → `.specs/<change-id>/tasks.md`
- `templates/VERIFICATION.md` → `.specs/<change-id>/verification.md`
- `templates/_meta.yaml` → `.specs/<change-id>/_meta.yaml`
- `templates/STATE.md` → `.specs/<change-id>/STATE.md`

模板渲染统一由 `bin/render-template.js` 执行；分段语义与失败行为以该脚本为唯一事实源。

如果项目根目录存在 `.devkit/project.yaml`，启动时还必须把它作为共享元信息输入：
- `project.scale`：作为 Size 路由的基础事实
- `project.language` / `project.framework`：作为文档与方案裁剪输入
- `context_budget`：作为默认上下文预算来源；若缺失则回退到本文件中的默认预算

如果当前 change 存在 `.specs/<change-id>/_meta.yaml`，跨会话恢复时必须优先读取其中的 `last_tldr`、`last_next`、`last_risk`、`last_progress_note`，再回读根级 `.specs/STATE.md` 与当前阶段产物。

## Context Budget
你必须默认控制上下文预算，而不是把所有历史产物重新塞回当前会话：
- 如果当前 change 的 `_meta.yaml` 存在，跨会话恢复时优先读取其中的 `last_*` 字段，再决定是否需要扩展上下文。
- 如果 `.devkit/project.yaml.context_budget` 存在，优先采用其中的预算值。
- XS/S：优先使用当前阶段主产物 + 必要上游产物，不回读整套 `.specs`
- M：默认读取当前阶段主产物 + 最近一个上游产物
- L：按阶段逐步补读，只有在关键信息缺失时才扩展上下文

当需要扩展上下文时，必须说明原因，例如：
- 当前产物缺字段
- 上下游产物结论冲突
- 用户要求回顾完整设计链路

## 阶段切换仪式

| Size | 仪式形式 | Token 预算 |
|------|---------|-----------|
| XS | 单行摘要：`<stage_name> done. Next: <next_action>.` | ≤ 50 tokens |
| S | 三行摘要：阶段成果 1 行 + 下一步 1 行 + 风险 1 行（无则省略） | ≤ 150 tokens |
| M | 完整模板：成果列表 + 下一步 + 风险 + post-gate 询问 | ≤ 500 tokens |
| L | 完整模板 + Recent Changes append + Gate 必选项展示 | ≤ 800 tokens |

- XS / S 阶段切换不得超过预算。
- M / L 必须保留完整阶段切换仪式，不得压缩为单行。

## TL;DR 约定
每次阶段完成后，建议在输出末尾附一个极短摘要，便于恢复：
- `TL;DR`: 当前完成了什么
- `Next`: 下一步做什么
- `Risk`: 当前最大剩余风险

该摘要应服务于恢复与切换，不应展开成长篇复述。

## 阶段推进模板
进入任一阶段前，你都应该用统一格式简要说明：
- `change-id`：...
- `size`：...
- `current_stage`：...
- `next_action`：...
- `read_docs`：[`docs/...`]

如果阶段被跳过，也必须明确说明跳过原因，而不是静默省略。

## 阶段退出一致性检查
每个阶段结束时，至少检查：
- 当前阶段产物是否已落盘或已明确说明为何不需要
- `_meta.yaml.current_stage` 是否已更新
- `.specs/STATE.md` 是否与当前 change 同步
- 下一阶段所需最小输入是否存在

若检查失败，不得静默进入下一阶段。
