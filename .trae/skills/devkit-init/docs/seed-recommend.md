# 种子推荐机制

devkit-init 的 bootstrap 和 adopt 流程末尾，执行两级推荐：精选种子（优先）→ find-skill（备选）。

## 两级推荐模型

1. **精选种子**：维护在 `seeds.yaml`，由 devkit 作者人工精选，按项目特征条件匹配后优先推荐。精选种子同时包含 skill 和 MCP server 两种类型。MCP 种子额外携带 `mcp_config` 配置片段和 `requires_auth` 认证标记。
2. **find-skill / find-mcp 补充**：当精选种子不足以覆盖用户场景时，调用运行时的 find-skill 或 find-mcp 能力进行开放搜索作为备选。devkit 本身不实现调用逻辑，仅输出提示。

## 种子匹配算法

1. 读取 `.devkit/project.yaml`，提取 `project.language`、`project.scale`、`byted_signals.is_internal`。
2. 读取 `seeds.yaml`。
3. 逐条种子评估 `when` 条件（全部可选，多字段 AND 逻辑）：
   - `language`：项目的 `project.language` 数组包含该值则匹配
   - `has_file`：项目根目录 `fs.existsSync` 该文件则匹配
   - `has_dir`：项目根目录 `fs.existsSync` 该目录则匹配
   - `scale_gte`：项目规模 >= 该值（XS < S < M < L < XL）
   - `is_internal`：项目的 `byted_signals.is_internal` 等于该值则匹配
   - `when` 整体缺省 = 无条件推荐
4. 排除 `project.yaml.ai_configs.installed_skills` 中已有的 skill。
5. 按 `when` 条件数降序（条件越多越精准优先）、`priority` 升序排序，取前 8 条输出推荐列表。

## 输出格式

当有匹配种子时：

```
> 🔧 根据项目特征，推荐以下 Skills：
> 1. **superpowers** ⭐190k — TDD + 多 agent 开发方法论
>    安装：`npx skills add obra/superpowers`
> 2. **frontend-design** ⭐134k — Anthropic 官方前端设计 skill
>    安装：`/plugin install frontend-design@claude-plugins-official`
>
> 🔧 推荐 MCP Server：
> 1. **context7-mcp** ⭐55k — 实时拉取版本匹配的库文档
>    安装：`claude mcp add --transport stdio context7 -- npx -y @upstash/context7-mcp`
> 2. **github-mcp** ⭐40k — GitHub Issues/PR/代码搜索 ⚠️需配置 Token
>    安装：`claude mcp add --transport http github https://api.githubcopilot.com/mcp/`
>
> 💡 需要更多？使用 find-skill 搜索其他可用 Skill。
> 💡 需要更多 MCP Server？使用 find-mcp 或 MCP Registry 搜索更多可用 MCP Server。
```

当无匹配种子时：

```
> 💡 未找到精选推荐。使用 find-skill 搜索其他可用 Skill。
```

## find-skill / find-mcp 触发条件

- 精选种子匹配结果为 0 条时，自动提示
- 精选种子有匹配时，在列表末尾附加一行 find-skill 提示
- 用户主动要求时直接调用
- `find_mcp_hint` 始终输出，提示用户可通过 MCP Registry 搜索更多 MCP server
- MCP Registry 种子本身就是一个 MCP server，安装后可直接在 Claude Code 中搜索

## 不推荐重复已装 skill

推荐列表必须排除 `project.yaml.ai_configs.installed_skills` 中已有的 skill。

## MCP 推荐注意事项

- `requires_auth: true` 的 MCP 需在推荐时提示用户需要配置 token
- MCP 种子的 `install` 字段是 `claude mcp add` 命令，可直接执行
- MCP 和 skill 共享同一个 Top 8 推荐池，按 when 条件数和 priority 统一排序

## 优雅降级

`seeds.yaml` 不存在或格式错误时，不阻塞 bootstrap / adopt 流程，仅跳过推荐环节并输出 find-skill 提示。
