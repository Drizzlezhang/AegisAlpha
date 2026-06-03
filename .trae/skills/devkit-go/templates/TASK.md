# Tasks: {{change-id}}

<!-- size:all -->
## 任务波次

### Wave 1（无依赖，可并行）
#### T01: ...
- 描述: ...
- read_files: [...]
- write_files: [...]
- verify: `<可执行的验证命令>`
- status: pending
<!-- /size:all -->

<!-- size:S+ -->
### Wave 2（依赖 Wave 1）
#### T02: ...
- 描述: ...
- depends_on: [T01]
- read_files: [...]
- write_files: [...]
- verify: `<可执行的验证命令>`
- status: pending
<!-- /size:S+ -->

<!-- size:M+ -->
## 风险任务
- 标记高风险任务、前置条件与额外验证动作

## 回滚任务
- 记录需要保留的回滚步骤或补救动作
<!-- /size:M+ -->

<!-- size:L -->
## Alternatives Considered
- 说明为何不采用其他拆解方式

## Migration Plan
- 记录跨阶段迁移、发布或协作顺序

## Observability
- 记录关键埋点、日志或监控补充任务
<!-- /size:L -->
