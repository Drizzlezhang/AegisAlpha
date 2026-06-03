# 项目分析

## 缓存优先硬规则
在初始化前，你必须先检查 `.devkit/project.yaml`：
1. 文件不存在：运行 `node bin/detect.js` 完整扫描并生成缓存。
2. 文件存在：
   - 如果 `scanned_at + ttl_seconds < now`，视为失效，重新扫描。
   - 如果重新计算任一 fingerprint 字段后发生变化，视为失效，重新扫描。
   - 如果用户显式要求 `--refresh`，强制重扫。
   - 否则直接使用缓存结果，跳过深度扫描。
3. 后续项目分析输出应优先复用 `project.yaml` 中的 `project.*`、`byted_signals.*` 与 `ai_configs.*` 字段；只有缓存缺字段时才补充人工扫描。

在初始化前，你必须扫描项目根目录并归纳以下信息：

## 扫描目标
- 主要语言：JavaScript / TypeScript / Python / Go / Rust / Java / Kotlin / Swift / Dart / Shell 等
- 框架：React / Vue / Next.js / Nuxt / Express / NestJS / FastAPI / Spring / Flutter / Electron 等
- 构建工具：Vite / Webpack / Turbopack / Rollup / esbuild / Cargo / Gradle / Maven 等
- 包管理器：npm / pnpm / yarn / bun / pip / poetry / uv / cargo 等
- monorepo 信号：pnpm workspace / turbo / nx / rush / lerna / bazel / eden 等
- 项目边界：单仓 / 多包 / 多应用 / 服务端 / 客户端 / CLI / SDK / 组件库

## AI 配置检测
检查是否存在并总结作用：
- `CLAUDE.md`
- `.cursorrules`
- `.windsurfrules`
- `agent.md`
- 其他明显的 AI 协作说明文件

## 项目类型识别
基于代码与目录结构判断项目属于：
- 前端
- 后端
- 全栈
- CLI
- 库 / SDK
- 移动端
- Electron
- 混合型项目

## 空项目判断
在分析阶段，你还必须判断是否命中“空项目 / 一句话需求”场景。至少检查：
- 是否缺少明确技术栈文件
- 是否缺少已有 AI 配置
- 当前目录是否几乎为空
- 用户输入是否不足以推断具体技术栈

## 输出格式
在进入下一阶段前，先给出简洁摘要：
- 技术栈判断
- 项目类型判断
- 现有 AI 配置情况
- 是否命中字节/内部项目信号
- 是否命中空项目 / 一句话需求场景
- 你认为接下来应该补的最关键协作能力
