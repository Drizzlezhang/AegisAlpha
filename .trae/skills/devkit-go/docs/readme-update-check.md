# README 更新检查

## 触发时机

在 6-SHIP 阶段，提交前必须检查本次变更是否需要同步更新 README.md。

## 检查流程

1. 对照本次变更的 `proposal.md` 和实际 diff，判断是否命中以下任一触发信号：
   - 新增/删除/重命名公开 API 或 CLI 命令
   - 修改安装方式或依赖要求（package.json dependencies、go.mod、requirements.txt 等）
   - 新增重要 Feature（在 proposal.md 中标记为用户可感知的功能）
   - 修改项目配置格式（新增/删除/重命名配置项）
   - 变更最低运行时版本要求
   - 修改项目目录结构（新增/删除顶层目录）
   - 新增集成/MCP/插件支持

2. 如果命中任一信号：
   - 向用户提示："本次变更涉及 [具体信号]，建议同步更新 README.md 的 [具体段落]。"
   - 给出具体的更新建议（添加什么内容、修改哪个段落）
   - 如果用户同意，将 README 更新纳入本次 commit
   - 如果用户拒绝，在 `_meta.yaml` 的 `last_progress_note` 中记录 "README update deferred"

3. 如果未命中任何信号：
   - 静默跳过，不输出任何提示

## 原则

- **不强制**：README 更新是建议，不是 gate，不阻塞提交
- **精准提示**：只在确实需要时提示，避免每次 SHIP 都噪音式询问
- **最小改动**：建议的 README 更新应该是局部的、精确的，不是重写整个文件
- **可追溯**：如果用户选择延后，记录到 meta 中供后续 audit 发现
