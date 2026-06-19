# Requirements: m3-weight-adapter

## 功能需求

### FR-1: WeightAdapter 双维度综合信号计算
- Given: 已平仓 Thesis Card 含 judgment_score (1-5)、execution_score (1-5)、actual_pnl_pct
- When: WeightAdapter._collect_samples 被调用
- Then: 综合信号 = 0.5 * pnl_signal + 0.3 * judgment_signal + 0.2 * execution_signal，其中 pnl_signal 由 P&L% 线性映射到 [-1,1]，judgment/execution 归一化到 [-1,1]

### FR-2: 加权线性回归计算新权重
- Given: 某 factor 收集到 >= 5 个有效样本（含 factor_score、outcome、time_decay_weight）
- When: WeightAdapter._weighted_regression 被调用
- Then: 使用 numpy 加权最小二乘法计算斜率，新权重 = 1.0 + slope，限制在 [0.2, 3.0]

### FR-3: 时间衰减
- Given: 样本的 close_date 距今 age_days 天
- When: 计算样本权重
- Then: decay = 0.5^(age_days / 90)，即半衰期 90 天

### FR-4: 观察期机制
- Given: 系统首次创建 Thesis Card 之日起 OBSERVATION_PERIOD_DAYS (30) 天内
- When: update_weights 被调用
- Then: 直接返回当前权重，不执行回归计算

### FR-5: 观察期结束后回填
- Given: 观察期刚结束（首次检测到 observation_period_active 从 True → False）
- When: ObservationPeriodManager.check_and_transition 被调用
- Then: 自动调用 backfill_after_observation，使用所有历史打分数据计算权重

### FR-6: Weight Store CRUD
- Given: factor_weights 表已存在
- When: WeightStore 方法被调用
- Then: get_weight 返回当前权重（不存在返回 1.0），update_weight 记录 previous_weight 并写入新行，get_all_weights 返回所有 factor 当前权重，get_weight_history 返回变更历史

### FR-7: 初始权重加载
- Given: factor_weights 表为空
- When: WeightStore.initialize_from_config 被调用
- Then: 从 config/weights.yaml 加载 6 个 factor 的初始权重（均为 1.0），写入 factor_weights 表

### FR-8: Pipeline 权重快照注入
- Given: Pipeline 启动
- When: runner 执行 _inject_weight_snapshot
- Then: state.weight_snapshot 被填充为当前所有 factor 权重 dict

### FR-9: APScheduler 定时任务
- Given: scheduler 进程运行中
- When: 每日凌晨 1:00 ET 和每周日凌晨 4:00 ET
- Then: 观察期检查 job 和权重更新 job 分别触发

### FR-10: REST API
- Given: FastAPI 服务运行中
- When: GET /api/v1/memory/weights、GET /api/v1/memory/weights/history、POST /api/v1/memory/weights/{factor}/override
- Then: 分别返回当前权重+观察期状态、权重变更历史、手动覆盖结果

### FR-11: P&L 信号映射
- Given: actual_pnl_pct 值
- When: _pnl_to_signal 被调用
- Then: >= +20% → 1.0, 0% → 0.0, <= -20% → -1.0，中间线性插值

## 验收标准与验证方式

| AC | 验证方式 |
|----|---------|
| AC-1: 综合信号 = 0.5*pnl + 0.3*judgment + 0.2*execution | `test_weight_adapter.py::test_composite_signal` — 构造已知 pnl/judgment/execution，断言 composite 值 |
| AC-2: 时间衰减半衰期 90 天 | `test_weight_adapter.py::test_time_decay` — 构造 90 天前样本，断言 decay ≈ 0.5 |
| AC-3: 观察期 30 天内不改变权重 | `test_observation_period.py::test_in_period_no_update` — mock 首个 card 在 10 天前，断言 update_weights 返回原权重 |
| AC-4: 观察期结束后触发回填 | `test_observation_period.py::test_backfill_on_expiry` — mock 首个 card 在 31 天前，断言 backfill 被调用 |
| AC-5: 权重范围 [0.2, 3.0] | `test_weighted_regression.py::test_weight_clamping` — 构造极端样本使 slope 超限，断言权重被 clamp |
| AC-6: 样本 < 5 保持当前权重 | `test_weight_adapter_edge.py::test_insufficient_samples` — 仅 3 个样本，断言权重不变 |
| AC-7: 空 cards 返回默认权重 | `test_weight_adapter_edge.py::test_empty_cards` — closed_cards 为空，断言返回当前权重 |
| AC-8: Pipeline 启动后 weight_snapshot 非空 | `test_pipeline_weight_inject.py` — 构造 PipelineState，断言 weight_snapshot 含 6 个 factor |
| AC-9: 手动覆盖 API 正常 | `test_weight_api.py::test_manual_override` — POST /override，断言 changed_by="manual" |
| AC-10: 权重历史可查询 | `test_weight_store.py::test_get_history` — 写入 3 条记录，断言返回 3 条 |
| AC-11: 初始权重从 YAML 加载 | `test_weight_store.py::test_initialize_from_config` — 空表调用 initialize，断言 6 个 factor 权重均为 1.0 |
| AC-12: P&L 信号边界值正确 | `test_pnl_to_signal.py` — 0%→0.0, +20%→1.0, -20%→-1.0, +50%→1.0, -50%→-1.0 |

## 用户故事

- As a 系统，I want 根据历史交易的双维度打分自动调整因子权重，So that 推荐质量随时间持续提升
- As a 开发者，I want 通过 REST API 查看当前权重和历史趋势，So that 能理解系统决策依据
- As a 运维者，I want 观察期内系统不自动调权，So that 有足够数据积累后再启动自适应
- As a 用户，I want 手动覆盖某个 factor 的权重，So that 能注入人工判断

## 非功能需求

### NFR-1: 性能
- update_weights 单次执行 ≤ 5 秒（假设 ≤ 1000 条 closed cards）
- 加权回归使用 numpy，不引入 scikit-learn 等重依赖

### NFR-2: 可靠性
- 回归计算失败时返回默认权重 1.0，不抛异常
- WeightStore 操作失败时记录日志，不阻断 Pipeline

### NFR-3: 可维护性
- 所有 Store 操作通过接口，不直接操作 SQLite
- 权重变更记录完整历史（previous_weight + changed_by + sample_count）

## 边界场景

### Edge-1: 空 cards
- 无任何已平仓 Thesis Card → update_weights 返回当前权重，不报错

### Edge-2: 极端 P&L
- P&L > +100% 或 < -100% → pnl_signal 被 clamp 到 [-1, 1]

### Edge-3: 回归数值不稳定
- numpy.linalg.LinAlgError → 捕获异常，返回默认权重 1.0

### Edge-4: 首次启动无任何 card
- _is_in_observation_period 返回 True（无 card 视为观察期）

### Edge-5: 并发更新
- 多个 scheduler job 同时调用 update_weights → 依赖 SQLite 事务隔离

## 回滚计划
- 删除 `backend/aegis/memory/weight_adapter.py`、`weight_store.py`、`observation_period.py`
- 删除 `backend/aegis/api/routes/weights.py`
- 从 scheduler.py 移除两个 job 注册
- 从 runner.py 移除 _inject_weight_snapshot 调用
- 从 pyproject.toml 移除 numpy 依赖（如无其他用途）
- factor_weights 表保留不删除（Sprint-0 产物）

## 数据/权限影响
- 读取 factor_weights 表（Sprint-0 已创建）
- 读取 thesis_cards 表（需 ThesisStore 接口，若不存在需先定义）
- 不修改 PipelineState schema
- 不修改 MemoryInterface 签名
