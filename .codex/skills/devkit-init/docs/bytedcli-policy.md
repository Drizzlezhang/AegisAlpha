# bytedcli 强制策略

你必须先区分强信号与弱信号，再决定 `bytedcli` 是“直接强制安装”还是“进入确认后安装”。不要把所有内部项线索都当作同等强度处理。

## 信号分级
### 强信号
命中任一强信号时，可直接将项目判定为字节/内部/公司项目，并把 `bytedcli` 列为强制安装项：
- 用户明确说明这是字节内部、公司内部或工作项目
- git remote 明确包含 `bytedance` / `byted`
- `package.json`、`.npmrc` 或安装脚本中 registry 明确指向 `bnpm.byted.org`
- 存在 `.byted` 配置文件或其他明确的内部工程标识

### 弱信号
仅命中弱信号时，不得直接下结论，必须先进入确认交互：
- 代码中引用飞书 / Lark SDK
- monorepo 使用 rush / eden 等可能出现在内部环境的工具
- 仓库命名、目录命名、文档措辞看起来像公司内部项目，但没有更强证据
- 用户只说“工作项目”但未明确是字节体系

## 判定规则
1. 命中任一强信号：直接纳入 `bytedcli` CLI + Skill + MCP 三件套安装计划，并说明属于内部项目硬性要求。
2. 仅命中弱信号：先向用户明确说明这是“内部项目候选”，再确认是否按 bytedcli 标准能力集处理。
3. 同时命中多个弱信号：仍然先确认，但可在说明中标注“高概率内部项目候选”。
4. 强信号与弱信号同时存在：按强信号处理，不再降级为可选推荐。
5. 没有命中任何信号：不得主动把 `bytedcli` 放入安装清单。

## 必须执行的三件套
1. CLI 全局安装：
   - `npm install -g @bytedance-dev/bytedcli@latest --registry https://bnpm.byted.org`
2. Skill 安装（推荐 v0.36.0+）：
   - `bytedcli self skill install --skill bytedcli -g`
   - 若旧版本不支持，再使用备用方式：
   - `npx -y skills add git@code.byted.org:byteapi/bytedcli.git --skill bytedcli -g -y`
3. MCP 安装：
   - Claude Code：
     - `claude mcp add bytedcli --env NPM_CONFIG_REGISTRY=http://bnpm.byted.org -- npx -y @bytedance-dev/bytedcli@latest mcp`
   - Trae CLI：
     - 写入 MCP 配置：
       - `{"mcpServers":{"bytedcli":{"command":"npx","args":["-y","@bytedance-dev/bytedcli@latest","mcp"],"env":{"NPM_CONFIG_REGISTRY":"http://bnpm.byted.org"}}}}`

## 说明要求
你必须说明：`bytedcli` 提供字节研发工作流所需的代码仓库、CR、部署、监控等能力，是内部项目的标准工具链。

## 安装前交互要求
- 强信号场景：可以把 `bytedcli` 作为必选项写入安装清单，但在真正执行全局安装、写 MCP、写设置前仍需说明影响范围并获得确认。
- 弱信号场景：必须先完成“是否按字节内部项目处理”的确认，再把 `bytedcli` 放入计划安装清单。

## 安装后验证要求
至少包括：
- `bytedcli --version`
- skill 是否已出现在目标 skill 目录或宿主可识别列表中
- MCP 配置是否已写入预期位置且结构合法

如果任一步失败，你必须给出明确错误、重试建议与回滚建议。

参考来源：
- `https://skills.bytedance.net/collection/iYrkTRRY`
