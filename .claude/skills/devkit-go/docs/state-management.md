# 状态管理

## STATE.md schema(v1)

`devkit-go` 现在同时维护两层状态文件：
- 根级 `.specs/STATE.md`：全局活跃 change 指针，用于 `/devkit-go` 无参恢复入口。
- change 级 `.specs/<change-id>/STATE.md`：单个 change 的 schema 化状态文件，字段顺序固定，必须参考 `templates/STATE.md`。

change 级 `STATE.md` 必须包含以下固定段落，并保持顺序不变：
- `## Current`
- `## Next Action`
- `## Open Questions`
- `## Risks`
- `## Recent Changes`
- `## Notes`

## Recent Changes 维护规则
- 每次阶段切换或 `status` 变化时，当前阶段在退出前必须向 `.specs/<change-id>/STATE.md` 的 `## Recent Changes` append 一行摘要。
- 每条摘要格式固定为：`[ISO8601] <stage> → <action>`。
- 最多保留 10 条，超过时丢弃最早一条，保持先进先出。
- 阶段摘要由当前阶段负责追加，而不是由下一阶段读到后补记。

## schema 兼容性
- 如果旧 change 只有 free-form `STATE.md`，或缺少 `## Recent Changes` 段，不得因此中断流程。
- 读取旧 change 时，先补建缺失段落，再继续记录新的阶段摘要。
- 根级 `.specs/STATE.md` 继续保留现有 free-form 兼容写法，不强制迁移到 change 级 schema。
- 如果旧 `_meta.yaml` 仍是 `schema_version: 1`，读取时必须把 `last_tldr`、`last_next`、`last_risk`、`last_progress_note` 视为空字符串，不得因为缺字段报错。

你必须维护 `.specs/STATE.md`，至少记录：
- 当前活跃 `change-id`
- 当前阶段
- 中断原因（如有）
- 未完成任务
- 最近一次更新时间
- 最近一次恢复方式（新建 / 恢复 / 回退）

你还必须在 `.specs/<change-id>/_meta.yaml` 中维护：
- `schema_version`
- `change_id`
- `size`
- `stages`
- `current_stage`
- `status`
- `created_at`
- `updated_at`
- `retry_count`
- `last_tldr`（当前阶段 TL;DR，跨会话恢复优先读取）
- `last_next`（下一步立即动作）
- `last_risk`（当前未消解风险）
- `last_progress_note`（BUILD / VERIFY 阶段的细粒度进展锚点）
- `last_context_mode`（例如 `full` / `recovery` / `minimal`）
- `last_verified_at`（如有）

## change-id 规则
每次新变更都必须生成一个稳定、可读、文件系统安全的 `change-id`。建议格式：
- `verb-noun`
- `verb-short-topic`
- 必要时追加日期或序号避免冲突

例如：
- `fix-login-timeout`
- `add-export-command`
- `migrate-user-profile-schema`

## 恢复模式
当用户调用 `/devkit-go` 且不带参数时，你必须：
1. 检查 `.specs/STATE.md`
2. 如果有活跃 change，则总结当前阶段、未完成任务与下一步，并继续推进
3. 如果没有活跃 change，则询问一句话需求后创建新的 change

## 最小上下文恢复
当进入恢复模式时，不要一次性回读所有产物。必须按最小上下文加载：
1. 先读 `.specs/<change-id>/_meta.yaml` 全文，拿到 `last_tldr` / `last_next` / `last_risk` / `last_progress_note`
2. 再读 `.specs/STATE.md`，确认活跃 `change-id` 与 `current_stage`
3. 再根据 `current_stage` 读取当前阶段直接依赖的单个主产物
4. 只有在信息不足时，才继续补读上游产物

建议的最小加载优先级：
- `0-CHANGE`：`proposal.md`
- `1-SPEC`：`requirements.md`，缺失时回退 `proposal.md`
- `2-DESIGN`：`design.md`，缺失时回退 `requirements.md`
- `3-PLAN`：`tasks.md`，缺失时回退 `design.md`
- `4-BUILD`：`tasks.md`，缺失时按既有降级链回退
- `5-VERIFY`：`verification.md`，缺失时回退 `requirements.md` 或 `proposal.md`
- `6-SHIP`：`verification.md` + 最近一次验证结论，必要时再读 `proposal.md`

## 状态一致性检查
每次恢复或阶段切换前，都必须检查：
- `.specs/STATE.md` 的活跃 `change-id` 是否存在对应目录
- `_meta.yaml.current_stage` 与 `STATE.md` 记录是否一致
- 当前阶段所需的核心产物是否存在
- `status` 是否允许继续推进（例如 `abandoned` 不得静默恢复）
- `retry_count` 是否已达到上限

如果发现不一致：
1. 先停止自动推进
2. 明确指出哪一项状态冲突
3. 提示用户选择修正状态、恢复到上一个稳定阶段，或放弃当前 change

## Abandoned Change 处理
- 当 `_meta.yaml.status` 置为 `abandoned` 时，change 级 `.specs/<change-id>/STATE.md` 必须保留。
- 在 `## Notes` 段下追加 `## Abandonment Reason` 子段，记录放弃原因（用户决策 / 重试超限 / 需求取消）。
- 归档时优先使用 `git mv` 语义，把 `.specs/<change-id>/` 移动到 `.specs/_archive/abandoned/<change-id>/`，保留全部产物供未来参考。
- 在仓库根 `.specs/_archive/index.md`（若不存在则新建）追加一行：`- <change-id> | <abandoned_at> | <one-line reason>`。
- 默认扫描与恢复流程跳过 `.specs/_archive/`；只有用户显式要求包含 archived changes 时才回读。
- 禁止物理删除 archived change，除非用户明确要求执行删除并提交。

## 归档与清理策略
- `status: completed` 的 change，默认保留在 `.specs/<change-id>/`，不自动删除
- 当 completed / abandoned 的 change 积累过多时，可以建议归档，但不得未经确认直接删除
- 归档优先于删除；建议移动到 `.specs/_archive/abandoned/<change-id>/`
- 若用户明确要求清理，必须先说明将删除或移动哪些目录与状态文件
- 清理后要同步更新根级 `.specs/STATE.md`，避免悬挂引用
