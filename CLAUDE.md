# CLAUDE.md

<!-- 用户手写区域:devkit 不会修改 -->

## 项目概述

Aegis 2.0 — 个人美股/期权交易决策辅助系统。Multi-Agent 架构，盘前+盘后批处理 Pipeline，输出推荐到 Telegram。

## 核心约束（开发前必读）

### 技术栈（不可替换）
- **后端**: Python 3.11+ / FastAPI / LangGraph + LangChain / SQLAlchemy 2.0 / Pydantic v2
- **包管理**: uv（不接受 pip/poetry/conda）
- **前端**: Next.js 15 App Router + Tailwind v4 + shadcn/ui + Recharts
- **数据库**: SQLite + ChromaDB + Parquet
- **调度**: APScheduler（Full + Lightweight + trigger_check 三套 cron）
- **推送**: python-telegram-bot v20+
- **LLM**: 通过 `aegis.llm.client.LLMClient` 调用，禁止直接 import openai SDK
- **CLI**: Typer

### 禁止项
- ✗ requests（用 httpx）
- ✗ logging 标准库（用 loguru）
- ✗ Pydantic v1
- ✗ openai SDK 直接调用
- ✗ Agent 内直接 import httpx 调外部 API（必须通过 Tool Registry）
- ✗ hardcode prompt（必须 Jinja2 模板）
- ✗ Agent 直接挂未声明字段到 PipelineState（走 state.extensions）
- ✗ 前端 hardcode hex/hsl 色值（走 --aegis-* 变量）
- ✗ 前端引入非指定 UI 库（仅 shadcn/ui + Lucide Icons）

### 契约层（冻结，修改需 [CONTRACT] PR）
- `backend/aegis/pipeline/state.py` — PipelineState（新增字段允许，删改禁止）
- `backend/aegis/agents/base.py` — BaseAgent.run() 签名冻结
- `backend/aegis/memory/interface.py` — 5 方法签名冻结
- `backend/aegis/tools/base.py` — ToolResult 字段冻结
- `backend/aegis/llm/client.py` — 所有 LLM 必须走此客户端
- `backend/aegis/registry/agent_registry.py` — AgentManifest schema 冻结

### 编码规范
- 类型注解强制（所有公开函数）
- async/await：IO/LLM 调用 async，纯计算 sync
- 行长 100 列（ruff）
- 命名：模块 snake_case / 类 PascalCase+Agent 后缀 / 函数 snake_case 动词开头
- 新 Agent 必须声明 `manifest: ClassVar[AgentManifest]` + 注册 `agents.yaml` + 单测
- 新 Tool 必须注册 `tools.yaml`（含 tags）+ 单测

### Git 规范
- Conventional Commits: `<type>(<scope>): <subject>`
- 分支: `feat/m{N}-{name}` / `fix/{issue}` / `chore/{topic}`
- Squash merge 到 develop

### 测试要求
- pytest + pytest-asyncio + pytest-mock
- LLM 调用用 MockLLMClient，Tool 调用用 Mock
- 函数名: `test_{behavior}_{scenario}`
- fixture 共享: `tests/fixtures/`

### 目录结构
```
backend/aegis/agents/      — LangGraph Agent
backend/aegis/calculators/ — 纯计算（无 LLM/IO）
backend/aegis/tools/       — Tool Adapters（分类子包）
backend/aegis/pipeline/    — State + Graph + Runner
backend/aegis/registry/    — Tool + Agent Registry
backend/aegis/memory/      — 四层 Memory
backend/aegis/models/      — SQLAlchemy 模型
backend/aegis/api/         — FastAPI 路由
backend/aegis/llm/         — LLM 客户端封装
backend/config/            — YAML 配置 + Jinja2 prompts
frontend/                  — Next.js 前端
```

## 开发原则

### Think Before Coding
- 先理解目标、约束、边界与成功标准
- 发现歧义先提关键问题

### Simplicity First
- 用最少改动解决问题
- 不做投机性抽象
- 优先复用现有模式

### Surgical Changes
- 只改必须改的文件
- 保持现有架构边界
- 不顺手做无关重构

### Goal-Driven Execution
- 先定义完成标准
- 改动后执行验证
- 未验证通过不宣称完成

## 关联文档
- `AGENTS.md` — 全局工程规范（完整版，冲突时以此为准）
- `docs/prd.md` — 产品需求文档 v1.2
- `docs/tech-arch.md` — 技术架构 v1.2
- `docs/design.md` — 前端设计系统 v1.0

<!-- devkit-managed:start version=1 generated_at=2026-06-03T06:38:50.740Z -->
## DevKit Configuration

This section is managed by `devkit-init`. Do not edit manually.

### Installed Skills
- devkit-init: project bootstrap, audit, adopt
- devkit-go: 7-stage development workflow

### Project Meta
- language: python, typescript
- framework: fastapi, langgraph, nextjs
- scale: M

### Workflow Conventions
- 触发 devkit-go 进入 7 阶段流程
- _meta.yaml schema_version: 2
- STATE.md 字段顺序锁定（详见 templates/STATE.md）
<!-- devkit-managed:end -->

<!-- 用户手写区域:devkit 不会修改 -->
