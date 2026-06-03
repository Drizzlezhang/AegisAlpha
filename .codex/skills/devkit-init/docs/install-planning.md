# 安装规划

你必须按“按需、不重复、功能互补、不过度暴露 skill”的原则规划增强能力。

## 前置依赖检查
在使用本文件前，你必须已读取：
- `docs/project-analysis.md`
- `docs/bytedcli-policy.md`

如果命中空项目 / 一句话需求场景，还必须结合 `docs/baseline-bootstrap.md` 一起判断安装清单。

## project.yaml 联动
如果 `.devkit/project.yaml` 已存在，你必须把它视为安装规划的共享元信息池：
- 优先复用 `project.language`、`project.framework`、`project.scale`、`byted_signals` 与 `ai_configs` 字段，而不是重复做整仓推断。
- 当安装新的 skill 后，应把 skill 名追加到 `ai_configs.installed_skills`，保持该字段与实际安装结果一致。
- 如果 `project.yaml` 缺失、过期或 fingerprint 失效，先重新执行 detect，再继续安装规划。

## 候选来源
你可以从以下来源中选择最合适的项目，也可以使用官方市场中的高质量项目或任何通过 `npx` / `npm` 可安装的 coding skill：
- 官方 skill / plugin 市场
- GitHub `claude-code` topic、官方市场排行榜、趋势榜单中的高质量项目
- `https://github.com/obra/superpowers`
- `https://github.com/mattpocock/skills`
- `https://github.com/addyosmani/agent-skills`
- `https://github.com/anthropics/skills`
- `https://github.com/forrestchang/andrej-karpathy-skills`

## 动态发现策略
当静态候选列表无法覆盖当前项目需求时，你必须执行动态发现，而不是直接输出“暂无建议”：
1. 优先检查官方市场的最新排行、精选或搜索结果。
2. 再搜索 GitHub 中与 `claude-code`、`claude skill`、`coding skill` 等主题相关的趋势项目。
3. 对每个候选项标注可信度等级：
   - **官方**：官方市场、官方组织或官方维护项目
   - **高可信**：高星、活跃维护、社区广泛使用的项目
   - **一般**：个人维护或信息不足的项目
4. 当候选来源可信度不足时，必须显式提醒安全与维护风险，而不是默认推荐。

## 规划时必须考虑
- 当前项目技术栈最缺什么，而不是“别人常装什么”
- 是否已存在等效能力
- 是否会与现有 skill / plugin / MCP 职责重叠
- 是否会让 skill 列表膨胀，导致模型暴露过多无关能力
- 安装后是否需要额外配置、登录、token、权限、hooks
- 候选项是否有固定版本、活跃维护者与明确安装入口

## 版本固定与安全提示
- 默认优先固定到明确版本，而不是无条件使用 `latest`。
- 如果必须使用 `latest`，你必须说明原因（例如仅有官方推荐入口、不提供版本选择、临时验证场景）。
- 对需要执行远程脚本、全局写入、登录授权、token 注入、hooks 改写的项目，必须显式提示安全影响。
- 如果来源可信度为“一般”，必须提醒用户先审查仓库、安装脚本与权限需求。

## 同名 skill / 冲突处理规则
当存在同名或近似同名 skill / plugin / MCP 时，你必须执行以下判断：
1. 先比较来源可信度：官方 > 高可信 > 一般。
2. 再比较维护活跃度、最近更新时间、安装复杂度与当前项目贴合度。
3. 如果两个候选项名字相同但实现不同，必须在安装清单中显式说明“冲突项”与保留原因。
4. 未经用户确认，不得同时安装两个同名或高重叠候选项。

## 可选安装方式
- `npx <package>` 执行安装
- `npm install` 后执行安装脚本
- 从官方市场安装
- `git clone` 后复制相关文件到 `.claude/skills/`
- MCP server：`claude mcp add --transport <stdio|http> <name> [-- <command> [args...]]`
- MCP server（手动）：编辑 `.mcp.json`（项目级）或 `~/.claude.json`（用户级）

## 空项目兜底规则
如果命中空项目基础保障模式，安装清单不能为空。

此时你必须：
- 说明当前是空项目 / 一句话需求场景
- 切换到 baseline bootstrap 逻辑
- 至少给出一组基础保障能力
- 将 `caveman` 作为默认标准安装候选，说明它用于控制 token/context 开销

## 标准安装建议
### 默认标准安装：caveman
在空项目、上下文敏感项目、长对话开发场景下，默认将 [caveman](https://github.com/JuliusBrussee/caveman) 纳入标准安装清单，除非当前环境已具备等效能力。

你必须说明：
- 安装原因：降低 token 消耗、控制上下文膨胀、改善长流程协作成本
- 推荐配置依据：语言、框架、仓库规模、项目复杂度
- 安装后验证方式：如 `caveman --version` 或等效可执行性检查

### 复杂项目推荐安装：grill-me
当项目被判断为复杂项目（M/L 级别、多模块、多人协作、需求模糊度高）时，默认将 [grill-me](https://skills.sh/mattpocock/skills/grill-me) 加入推荐安装清单。

你必须说明：
- 安装原因：在需求澄清、SPEC、PLAN 阶段提供深度追问能力，减少返工
- 触发条件：M/L 级别、跨模块变更、多人协作、需求不清晰
- 它是复杂项目推荐项，而不是所有项目的默认强装项

## 安装前强制交互确认
执行任何安装前，必须先展示“计划安装清单”，至少包含：
- 名称
- 类型（skill / plugin / MCP / CLI）
- 安装方式
- 安装原因
- 来源与可信度
- 推荐版本或版本策略
- 是否与现有能力重叠
- 是否涉及全局影响
- 是否存在同名或近似冲突项

未确认不得安装。

## 安装后验证清单
每个安装动作完成后，都必须立即执行与该动作对应的验证，而不是只报告“安装完成”。

至少包括：
- CLI：检查可执行性与版本，例如 `bytedcli --version`、`caveman --version`
- skill：检查目标目录下是否正确落盘 `SKILL.md`、`docs/` 与必要模板
- MCP：检查配置是否已写入预期位置，并确认配置结构合法；执行 `claude mcp list` 确认 server 已注册；或检查 `.mcp.json` / `~/.claude.json` 中对应配置存在且结构合法
- plugin / 市场安装：检查是否出现在宿主可识别的已安装列表中，或能被对应命令/配置读取

你必须在收尾输出中展示：
- 每个安装项的验证命令或验证动作
- 验证结果（通过 / 失败）
- 失败时的明确错误信息
- 重试建议
- 回滚建议

## 回滚 / 卸载策略
如果安装后发现某个能力不可用、冲突或不符合预期，你必须提供回滚或卸载建议，而不是只提示“手动处理”。

至少包括：
- 删除已复制到 `.claude/skills/` 的 skill 目录
- 移除对应的 MCP 配置段
- 取消市场 / plugin 安装或禁用配置
- 撤销全局安装命令（如 `npm uninstall -g <package>`）
- 如涉及配置文件修改，说明需要回滚哪些文件与字段

如果自动回滚风险较高，你必须明确说明原因，并先征求用户确认。

## 标记块协议

DevKit 写入 `CLAUDE.md` 时使用标记块隔离受管内容与用户手写内容：

- 受管块由 `<!-- devkit-managed:start version=N generated_at=ISO8601 -->` 与 `<!-- devkit-managed:end -->` 包裹
- 标记块外为用户手写区域，DevKit 永不修改
- 标记块内内容在安装/同步时由 `install.js` 的 `writeManagedBlock` 函数整体替换
- 标记块损坏（start/end 不配对）时报错并指出行号，不静默修复
- 已有 `CLAUDE.md` 但无标记块时，追加受管块到文件末尾，不覆盖原文
- 已有 `CLAUDE.md` 且已有标记块时，只替换块内内容
