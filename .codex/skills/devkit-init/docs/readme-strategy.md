# README 策略

## README 质量维度（参考 awesome-readme 最佳实践）

一个高质量的 README 应覆盖以下维度：

| 维度 | 权重 | 说明 |
|------|------|------|
| 标识清晰度 | ★★★ | 项目名 + 一句话描述，3 秒内能理解做什么 |
| 快速可用性 | ★★★ | 安装 + 最小示例，5 分钟内能跑起来 |
| 功能可见性 | ★★☆ | 特性列表 / 截图 / GIF，一眼知道核心能力 |
| 开发友好度 | ★★☆ | 开发环境搭建、测试、贡献流程 |
| 信息完整度 | ★☆☆ | 许可证、徽章、架构、致谢 |

## 首装生成规则

当 README.md 不存在时，devkit-init 必须：

1. 读取 `.devkit/project.yaml` 获取项目元信息（language/framework/scale/name）
2. 扫描项目根目录获取补充信号：
   - `package.json` → name/description/scripts/license
   - `Cargo.toml` / `go.mod` / `pyproject.toml` → 项目名/描述
   - `LICENSE` / `LICENSE.md` → 许可证类型
   - `.github/workflows/` → CI 配置（用于生成 badge）
   - 现有代码入口 → 推断安装/使用方式
3. 使用 `templates/README.md` 渲染骨架，填充可推断的字段
4. 对无法推断的字段保留占位符 `{placeholder}`，并在输出中提示用户补充
5. 按 project.scale 裁剪段落：
   - **XS**：仅保留 标识 + 描述 + 快速开始 + License
   - **S**：追加 Features + Development
   - **M**：追加 Documentation + Architecture
   - **L**：全段保留 + 建议补充 Contributing + Acknowledgements

## 接入优化规则

当 README.md 已存在时，devkit-init 必须：

1. 读取现有 README 内容
2. 按质量维度逐项评分（存在/缺失/质量低）
3. 输出优化建议清单，格式：
   ```
   README 质量评估：
   ✅ 标识清晰度：项目名和描述清晰
   ⚠️ 快速可用性：缺少安装命令
   ❌ 功能可见性：无特性列表和截图
   ✅ 开发友好度：有开发和测试说明
   ⚠️ 信息完整度：缺少 License 徽章

   建议补充：
   1. 在 Quick Start 段添加 `npm install` 命令
   2. 添加 Features 段列出核心功能
   3. 添加 CI badge
   ```
4. 等用户确认后再生成补充内容
5. 不触碰用户已有内容，只做追加或建议

## 巡检规则

audit 模式下：
1. 检查 README 是否存在（不存在 → 高严重度漂移）
2. 若存在，按质量维度快速评分
3. 输出缺失项和建议（不自动修改）

## 内部项目特殊处理

当 `project.yaml.is_internal == true` 时：
- 省略 Contributing 和 License 段（内部项目通常不需要）
- 增加"内部接入方式"段（如 registry 地址、内部文档链接占位）
- Badge 使用内部 CI 地址格式

## README 更新触发信号

以下变更应触发 README 更新提示（供 devkit-go SHIP 阶段使用）：
- 新增/删除/重命名 公开 API 或 CLI 命令
- 修改安装方式或依赖要求
- 新增重要 Feature
- 修改项目配置格式
- 变更最低运行时版本要求
- 修改项目目录结构
- 新增集成/MCP/插件支持
