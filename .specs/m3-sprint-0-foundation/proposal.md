# Change: m3-sprint-0-foundation

## 概述
M3 Sprint-0 基础建设：PipelineState v1.4 契约扩展 + 5 张新 DB 表 + MemoryInterface v1.1 + 3 个 Agent 注册 + 4 个配置文件 + Alembic 迁移 + AGENTS.md v1.3 + M2 遗留修复。

## 动机
M3 需要 Thesis Cards、KOL 追踪、长期记忆、因子权重等基础设施。Sprint-0 先铺好契约层、DB schema、配置和接口签名，后续分支（A/B/C/D/E）在此基础上实现具体逻辑。

## 影响范围
- **契约层**: `pipeline/state.py`（v1.4 新增 5 字段）
- **DB**: 4 个新 model 文件 + `models/__init__.py` + Alembic 迁移
- **接口**: `memory/interface.py`（v1.1 签名扩展）
- **配置**: `agents.yaml`（3 个新 Agent）+ 4 个新 YAML 文件
- **环境**: `settings.py` + `.env.example`（M3 新 key）
- **文档**: `AGENTS.md`（v1.2 → v1.3）
- **修复**: `test_smart_money_agent.py`（3 个断言更新）

## 验收目标
- M2 遗留 3 个 Smart Money 测试修复，全量测试全绿
- PipelineState v1.4 新字段存在且 default 为空
- 5 张新表可通过 Alembic 创建和回退
- MemoryInterface v1.1 签名向后兼容
- agents.yaml 含 3 个新 Agent（enabled=false）
- 4 个配置文件就位
- settings.py + .env.example 含 M3 新 key
- AGENTS.md v1.3 更新
- ruff + mypy 全绿

## Size: M
## 推断依据
- 范围：跨模块（契约 + DB + 配置 + 接口 + 文档），15+ 文件
- 关键词：feature、migrate、schema
- 预估文件数：15-20
- 依赖变更：无新增外部依赖
- 风险：契约层修改需向后兼容，DB 迁移需可逆
- project.yaml scale=M

## 阶段序列
0 → 1 → 2 → 3 → 4 → 5 → 6
