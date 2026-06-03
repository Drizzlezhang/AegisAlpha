# 接入流程

当 `devkit-init` 判定为接入档位时，项目已有手写 AI 配置但尚未纳入 DevKit 管理。本文件描述接入流程的边界规则与执行步骤。

## 触发条件
- `.devkit/project.yaml` 不存在
- 项目存在任一用户手写 AI 配置：
  - `CLAUDE.md` 存在且不含 `<!-- devkit-managed:start -->`
  - `.cursorrules` 或 `.cursor/rules/` 存在
  - `.claude/skills/` 或 `skills/` 目录存在且非空
  - `.specs/` 目录存在

## 执行步骤
1. 跑 `DEVKIT_INIT_TIER=adopt node bin/detect.js`
2. 探测已有手写文件，但不覆写
3. 生成 `.devkit/project.yaml`，`installed_skills` 条目标 `managed_by: user`
4. `CLAUDE.md` 使用 append + 标记块策略：不覆盖用户手写区域，在文件末尾追加受管块
5. 已有 skill 登记到 `project.yaml.ai_configs.installed_skills`，标注 `managed_by: user`（DevKit 不接管生命周期）

## 标记块协议
- DevKit 管理的内容用 `<!-- devkit-managed:start ... -->` ~ `<!-- devkit-managed:end -->` 包裹
- 标记块外内容为用户手写区域，DevKit 永不修改
- 标记块内内容在每次安装/同步时由 `writeManagedBlock` 函数整体替换
- 标记块损坏（start/end 不配对）时报错并指出行号，不静默修复

## 合并预览
接入档位下，写入 `CLAUDE.md` 前必须先输出 diff 预览，用户确认后才执行写入。

## 边界规则
- 用户已装 skill 视为白名单，不触发冗余告警（见 `docs/redundancy-policy.md`）
- 接入时不修改 `.cursorrules`、`.cursor/rules/` 或其他宿主配置文件
- 接入完成后，`managed_by: user` 的 skill 不受 DevKit 版本管理与同步策略影响，除非用户显式要求接管
