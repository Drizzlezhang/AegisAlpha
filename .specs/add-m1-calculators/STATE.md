<!-- STATE.md schema_version: 1 -->
<!-- 字段顺序固定,模型新增内容必须落在已有段落内,禁止打乱顺序 -->

# State

## Current
- **change_id**: add-m1-calculators
- **size**: M
- **current_stage**: 4-BUILD
- **status**: in_progress
- **updated_at**: 2026-06-03T09:00:00+08:00

## Next Action
4-BUILD 完成。进入 5-VERIFY 阶段，运行全量测试 + lint 验证。

## Open Questions
- [ ] 无

## Risks
- 浮点精度：Greeks 计算涉及 erf/cdf，需确认 `pytest.approx` 容差设置
- Wyckoff 相位检测：基于量价关系的启发式算法，边界 case 可能模糊
- GEX 计算：依赖 options_chain 数据格式，需与 fixture 对齐

## Recent Changes
- [2026-06-03T08:00:00+08:00] 0-CHANGE → created proposal.md, size=M, stages=0→1→2→3→4→5→6
- [2026-06-03T08:05:00+08:00] 1-SPEC → drafted requirements.md with 5 FRs, 13 ACs, 5 edge cases, 3 NFRs
- [2026-06-03T08:10:00+08:00] 2-DESIGN → completed design.md, post-design gate skipped (low risk, pure incremental)
- [2026-06-03T08:15:00+08:00] 3-PLAN → tasks.md created with 4 waves, 8 tasks, post-plan gate skipped (low risk)

## Notes
基于 `docs/dev-plan/m1-branch-B-calculators.md` 创建。分支文档已明确文件清单、必测项与验收标准。
