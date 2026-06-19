# Change: m3-weight-adapter

## 概述
实现 WeightAdapter 自适应因子权重系统：双维度反馈（judgment + execution）→ 加权回归 → 因子权重自适应，含 30 天观察期机制、Weight Store CRUD、Pipeline 权重快照注入、REST API 与 APScheduler 定时任务。

## 动机
M3 Sprint-0 已铺设 factor_weights 表、weights.yaml 初始权重、MemoryInterface v1.1 等基础设施。Branch B 在此基础上实现核心权重自适应逻辑，使系统能根据历史交易的双维度打分自动调整各因子权重，形成反馈闭环。

## 影响范围
- `backend/aegis/memory/weight_adapter.py`（新建）— 核心权重计算
- `backend/aegis/memory/weight_store.py`（新建）— factor_weights 表 CRUD
- `backend/aegis/memory/observation_period.py`（新建）— 观察期管理
- `backend/aegis/pipeline/runner.py`（修改）— 权重快照注入
- `backend/aegis/pipeline/scheduler.py`（修改）— 定时任务注册
- `backend/aegis/api/routes/weights.py`（新建）— REST API
- `backend/tests/memory/`（新建测试）— 7 个测试文件
- `backend/pyproject.toml`（修改）— numpy 依赖声明

## 验收目标
- WeightAdapter 正确计算综合信号 (0.5 pnl + 0.3 judgment + 0.2 execution)
- 时间衰减半衰期 90 天正确
- 观察期 30 天内不改变权重，期满后触发回填
- 权重范围限制在 [0.2, 3.0]
- 样本 < 5 时保持当前权重不变
- Pipeline 启动时 weight_snapshot 正确注入
- 每周日定时更新 job 注册
- REST API 可查询权重/历史/手动覆盖
- 单测全绿，ruff + mypy clean

## Size: M
## 推断依据
- 范围：跨 memory / pipeline / api 三个模块，新建 4 个文件 + 修改 2 个文件 + 7 个测试文件
- 关键词：feature / adapter / regression / feedback loop
- 预估文件数：~13 个
- 依赖变更：新增 numpy 依赖
- 风险：需回归测试确保 Pipeline 不受影响

## 阶段序列
0 → 1 → 2 → 3 → 4 → 5 → 6
