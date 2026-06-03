# 运行时档位判定

`devkit-init` 触发后，必须先完成档位判定，再决定是否扫描、是否写文件以及是否进入安装流程。档位是内部判定逻辑，不是用户参数；用户始终用自然语言表达意图。

## 判定顺序

### Q1：`.devkit/project.yaml` 是否存在？
- 否：继续 Q2
- 是：继续 Q3

### Q2：项目是否已有用户手写 AI 配置？（任一满足即视为“是”）
- `CLAUDE.md` 存在且不含 `<!-- devkit-managed:start -->`
- `.cursorrules` 或 `.cursor/rules/` 存在
- `.claude/skills/` 或 `skills/` 目录存在且非空
- `.specs/` 目录存在

| Q2 结果 | 识别结果 |
|---------|----------|
| 否 | 首装 |
| 是 | 接入 |

### Q3：project.yaml 的 fingerprint 与当前实际状态是否一致？
重新计算 `package_json_hash`、`lockfile_hash`、`go_mod_hash`、`pyproject_hash`、`git_remote`；任一字段变化都视为漂移。
- 一致：继续 Q4
- 漂移：巡检

### Q4：用户当前消息是否包含维护类语义？
命中任一即视为“是”：
- 中文：`重装`、`重新`、`更新`、`检查`、`巡检`、`升级`、`同步`、`健康`、`看看现状`、`看看配置`
- 英文：`reinstall`、`update`、`check`、`sync`、`upgrade`、`audit`、`health`
- 或 `now - project.yaml.scanned_at > ttl_seconds`

| Q4 结果 | 识别结果 |
|---------|----------|
| 是 | 巡检 |
| 否 | 静默 |

## 显式覆盖规则
当用户消息明确表达以下意图时，跳过判定树直接进入对应结果：
- “重装”“清干净重来”“reinstall fresh” → 首装（先备份旧 `project.yaml`，后续实现时写入 `.devkit/project.yaml.bak.<timestamp>`）
- “只看不动”“dry run”“只检查不修改” → 巡检，且禁止进入 sync 步骤
- “这是个老项目”“已有 claude.md”“接进 devkit” → 接入

## 档位行为速查

| 识别结果 | 是否扫描 | 是否写文件 | 是否需用户确认 | 输出预算 |
|----------|----------|-----------|---------------|---------|
| 首装 | 完整扫描 | 是 | 是（安装清单） | 完整安装报告 |
| 接入 | 探测式扫描 | 仅在确认后追加或更新受管内容 | 是（合并预览） | 合并 diff |
| 巡检 | 增量对比 | 否（用户同意后才写） | 是 | 漂移报告 |
| 静默 | 仅读 yaml | 否 | 否 | ≤ 50 tokens 一行汇报 |

## 判定后的强制输出
判定完成后，必须先输出一句：
> 识别为 **<档位中文名>**，依据：<触发条件>。<下一步动作>。

示例：
> 识别为 **巡检**，依据：project.yaml 存在但 fingerprint 已变化。我将先输出漂移报告，不会修改任何文件。

## 歧义处理
当用户语义与文件状态矛盾时，只允许输出以下形式的二选一询问，不得出现“档位”二字：

> 检测到已有 devkit 配置。理解为：
> 1. 检查现状并按需更新
> 2. 清空重来
>
> 请回复 1 或 2。

## 同会话锁定
一旦识别结果确定，当前会话内默认锁定，不允许中途切换。只有用户明确表达“那就装吧”“那就同步吧”“算了”或等价意思时，才允许从巡检进入后续同步步骤或直接结束。

## 内部映射约定
以下映射只用于脚本与文档内部，不向用户暴露：
- 首装 → `bootstrap`
- 接入 → `adopt`
- 巡检 → `audit`
- 静默 → `silent`

## 环境变量约定

`bin/detect.js` 通过环境变量 `DEVKIT_INIT_TIER` 接收当前档位值，`SKILL.md` 判定完成后通过 env 传入。

| 环境变量值 | 扫描深度 | 写入行为 | 输出 |
|-----------|---------|---------|------|
| `bootstrap` | 完整 | 写入 `.devkit/project.yaml`，`managed_by: devkit` | 完整项目摘要 |
| `adopt` | 完整 + 探测已有手写文件 | 写入 `.devkit/project.yaml`，`managed_by: user` | 合并摘要 + 待登记列表 |
| `audit` | 仅重算 fingerprint | **不写文件**，输出到 stdout | 漂移报告 |
| `silent` | 仅读 `.devkit/project.yaml` | 不写文件 | 一行健康摘要 |
| 未设置 | 等同 `bootstrap` | 同 `bootstrap` | 同 `bootstrap` |

### 向下兼容
- 不设 `DEVKIT_INIT_TIER` 时，`detect.js` 行为与第三轮完全一致。
- `record-install` 子命令不受 tier 影响，始终以 `bootstrap` 模式写入。
- `managed_by` 字段在旧 `project.yaml` 中缺失时，默认视为 `devkit`。

## 漂移分级与修复策略

`audit` 模式检测到的漂移按严重度分为三级：

### 高（必须修复）
- `skills/<name>/SKILL.md` 文件缺失
- `SKILL.md` 的 `trigger: manual` 被改为其他值
- `CLAUDE.md` managed block 标记不配对

### 中（建议修复）
- `CLAUDE.md` managed block 缺少已装 skill 的章节
- `SKILL.md` frontmatter 缺少 `name` 或 `description`
- fingerprint 字段变化（`package.json` / lockfile / `go.mod` / `pyproject.toml` / `git_remote`）

### 低（可选）
- 上游版本落后（仅提示，不强制）
- 归档清理建议等

### 修复动作
| 漂移类型 | 默认动作 |
|---------|---------|
| 高 | 用户确认后强制修复（重装文件 / 还原 frontmatter） |
| 中 | 用户确认后修复（同步标记块 / rescan） |
| 低 | 仅展示，sync 默认跳过，需用户显式要求 |
