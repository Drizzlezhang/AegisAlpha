<!-- STATE.md schema_version: 1 -->
<!-- 字段顺序固定,模型新增内容必须落在已有段落内,禁止打乱顺序 -->

# State

## Current
- **change_id**: <id>
- **size**: <XS|S|M|L>
- **current_stage**: <0-CHANGE|1-SPEC|2-DESIGN|3-PLAN|4-BUILD|5-VERIFY|5-LITE|6-SHIP>
- **status**: <in_progress|blocked|partial_pass|completed|abandoned>
- **updated_at**: <ISO8601>

## Next Action
<一行描述下一步必须做什么,新会话恢复时优先读这一行>

## Open Questions
- [ ] <未决问题 1,带阻塞标签>

## Risks
- <当前已识别风险,2-5 行>

## Recent Changes
<!-- 最多保留 10 条,先进先出。每条 1 行,格式:[ISO8601] stage → action -->
- [2026-05-13T10:00:00+08:00] 1-SPEC → drafted requirements.md
- [2026-05-13T10:30:00+08:00] 2-DESIGN → completed design.md, post-design gate passed
- [2026-05-13T11:00:00+08:00] 3-PLAN → tasks.md created with 5 waves

## Notes
<!-- 可在此追加自由形式上下文。若旧 change 缺少 Recent Changes 段,先补空段再继续流程。abandoned 时在此段下追加 `## Abandonment Reason` 子段并记录一行原因。 -->
<自由形式,模型可写任意上下文备忘>
