# Change: m3-thesis-cards

## 概述
M3 Branch C — Thesis Cards 完整生命周期：创建→持有→校验→平仓→打分→入 Memory→驱动 WeightAdapter

## 动机
Thesis Cards 是 Aegis 2.0 反馈闭环的核心载体。当前系统缺少：
1. 从推荐到 Thesis 的自动创建机制
2. 每日轻量级校验（key_assumptions 是否仍然成立）
3. 平仓时的双维度打分（judgment_score + execution_score）
4. 打分结果写入 Memory 并驱动 WeightAdapter 权重更新
5. Re-entry 机制（平仓 30 天后同标的重新出现信号）
6. Research Manager 冷却检查（活跃 Thesis 阻止重复推荐）

## 影响范围
- **新建**: `backend/aegis/services/thesis_service.py` — ThesisService 生命周期管理
- **新建**: `backend/aegis/storage/thesis_store.py` — thesis_cards 表 CRUD
- **新建**: `backend/aegis/agents/thesis_validator_agent.py` — 每日轻量级校验 Agent
- **新建**: `backend/config/prompts/thesis_validator.j2` — 校验 prompt 模板
- **新建**: `backend/aegis/api/thesis.py` — REST API 路由
- **新建**: `backend/tests/services/test_thesis_service.py`
- **新建**: `backend/tests/storage/test_thesis_store.py`
- **新建**: `backend/tests/agents/test_thesis_validator_agent.py`
- **新建**: `backend/tests/api/test_thesis_api.py`
- **新建**: `backend/tests/integration/test_thesis_lifecycle.py`
- **新建**: `backend/tests/integration/test_thesis_memory_integration.py`
- **修改**: `backend/aegis/agents/research_manager_agent.py` — 冷却检查集成
- **修改**: `backend/aegis/pipeline/graph_full.py` — 注册 ThesisValidatorAgent
- **修改**: `backend/aegis/pipeline/graph_lightweight.py` — 注册 ThesisValidatorAgent
- **修改**: `backend/config/agents.yaml` — 注册 thesis_validator manifest
- **修改**: `backend/config/schedule.yaml` — 添加 thesis_validation cron job
- **修改**: `backend/aegis/api/__init__.py` — 注册 thesis router
- **修改**: `backend/aegis/models/thesis.py` — 确认 ThesisCard 模型字段完整

## 验收目标
1. ThesisService 完整生命周期：create_from_recommendation → close_thesis → check_re_entry
2. ThesisStore CRUD 通过 SQLAlchemy AsyncSession
3. ThesisValidatorAgent 每日校验 key_assumptions，更新 thesis_valid_status
4. 平仓流程：PnL 计算 + 双维度打分 + Episodic Memory 写入 + WeightAdapter 触发
5. Re-entry 检查：平仓 ≥30 天 + judgment_score ≥3 + 无活跃 thesis
6. Research Manager 冷却检查：has_active_thesis() 阻止重复推荐
7. REST API：GET/POST/PUT thesis + close + validation history
8. APScheduler 集成：thesis_validation cron job
9. 全部 6 个测试文件通过
10. ruff + mypy 通过

## Size: L
## 推断依据
- **范围**: 跨系统 — services + storage + agents + API + scheduler + pipeline + Research Manager
- **预估文件数**: 12 个新建 + 7 个修改 = 19 个文件
- **依赖变更**: 依赖 Branch A (MemoryService) + Branch B (WeightAdapter)，多系统联调
- **风险**: 涉及 Pipeline 图装配变更、调度器变更、Research Manager 行为变更，需回归测试
- **project.yaml base**: M，但实际变更范围远超 M 阈值（10-30 文件、跨系统），上浮至 L

## 阶段序列
0 → 1 → 2 → 3 → 4 → 5 → 6（全部阶段 + post-spec gate + post-plan gate + pre-ship gate + pre-commit gate）
