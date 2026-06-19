# Tasks: m3-weight-adapter

## 任务波次

### Wave 1（无依赖，可并行）

#### T01: 添加 numpy 依赖
- 描述: 在 `pyproject.toml` 的 `dependencies` 中添加 `"numpy>=1.26"`，并执行 `uv sync`
- read_files: [`backend/pyproject.toml`]
- write_files: [`backend/pyproject.toml`]
- verify: `cd backend && uv run python -c "import numpy; print(numpy.__version__)"`
- status: done

#### T02: 创建 ThesisStore
- 描述: 新建 `backend/aegis/memory/thesis_store.py`，实现 `get_closed_cards(session)` 和 `get_closed_cards_by_factor(session, factor_name)` 两个方法，查询已平仓且有双维度打分的 ThesisCard
- read_files: [`backend/aegis/models/thesis.py`]
- write_files: [`backend/aegis/memory/thesis_store.py`]
- verify: `cd backend && uv run python -c "from aegis.memory.thesis_store import ThesisStore; print('OK')"`
- status: done

#### T03: 创建 WeightStore
- 描述: 新建 `backend/aegis/memory/weight_store.py`，实现 `get_weight`、`get_all_weights`、`update_weight`、`get_weight_history`、`initialize_from_config`、`is_observation_period_active` 六个方法，封装 factor_weights 表 CRUD
- read_files: [`backend/aegis/models/factor_weight.py`, `backend/config/weights.yaml`]
- write_files: [`backend/aegis/memory/weight_store.py`]
- verify: `cd backend && uv run python -c "from aegis.memory.weight_store import WeightStore; print('OK')"`
- status: done

### Wave 2（依赖 Wave 1）

#### T04: 创建 WeightAdapter 核心算法
- 描述: 新建 `backend/aegis/memory/weight_adapter.py`，实现 `_pnl_to_signal`、`_score_to_signal`、`_composite_signal`、`_time_decay_weight`、`_collect_samples`、`_weighted_regression`、`update_weights` 七个方法。依赖 numpy 加权最小二乘，依赖 WeightStore 和 ThesisStore（通过构造函数注入）
- depends_on: [T01, T02, T03]
- read_files: [`backend/aegis/memory/weight_store.py`, `backend/aegis/memory/thesis_store.py`, `backend/aegis/models/thesis.py`]
- write_files: [`backend/aegis/memory/weight_adapter.py`]
- verify: `cd backend && uv run python -c "from aegis.memory.weight_adapter import WeightAdapter; print('OK')"`
- status: done

#### T05: 创建 ObservationPeriodManager
- 描述: 新建 `backend/aegis/memory/observation_period.py`，实现 `get_first_card_date`、`is_in_observation_period`、`check_and_transition`、`backfill_after_observation` 四个方法。依赖 WeightStore 和 WeightAdapter
- depends_on: [T03, T04]
- read_files: [`backend/aegis/memory/weight_store.py`, `backend/aegis/memory/weight_adapter.py`, `backend/aegis/models/thesis.py`]
- write_files: [`backend/aegis/memory/observation_period.py`]
- verify: `cd backend && uv run python -c "from aegis.memory.observation_period import ObservationPeriodManager; print('OK')"`
- status: done

### Wave 3（依赖 Wave 2）

#### T06: 创建 Scheduler 常驻进程
- 描述: 新建 `backend/aegis/scheduler.py`，使用 APScheduler + SQLAlchemyJobStore，注册两个 cron job：`observation_check_job`（每日 1:00 ET）和 `weight_update_job`（每周日 4:00 ET），从 `schedule.yaml` 读取 cron 配置
- depends_on: [T05]
- read_files: [`backend/config/schedule.yaml`, `backend/aegis/memory/observation_period.py`, `backend/aegis/memory/weight_adapter.py`, `backend/aegis/utils/settings.py`]
- write_files: [`backend/aegis/scheduler.py`]
- verify: `cd backend && uv run python -c "from aegis.scheduler import create_scheduler; print('OK')"`
- status: done

#### T07: 创建 REST API 路由 + Response Schema
- 描述: 新建 `backend/aegis/api/routes/weights.py`，实现三个端点：`GET /memory/weights`、`GET /memory/weights/history`、`POST /memory/weights/{factor}/override`。同时在 `backend/aegis/api/schemas/responses.py` 中新增 `WeightSnapshotResponse`、`WeightHistoryResponse`、`WeightOverrideRequest`、`WeightOverrideResponse` 四个 Pydantic 模型
- depends_on: [T03]
- read_files: [`backend/aegis/api/routes/agents.py`, `backend/aegis/api/schemas/responses.py`, `backend/aegis/memory/weight_store.py`]
- write_files: [`backend/aegis/api/routes/weights.py`, `backend/aegis/api/schemas/responses.py`]
- verify: `cd backend && uv run python -c "from aegis.api.routes.weights import router; print(len(router.routes))"`
- status: done

#### T08: Pipeline runner 注入 weight_snapshot
- 描述: 修改 `backend/aegis/pipeline/runner.py`，在 `run_full()` 中 `GraphBuilder.build()` 之前调用 `_inject_weight_snapshot()`，从 WeightStore 获取当前权重并写入 `state.weight_snapshot`
- depends_on: [T03]
- read_files: [`backend/aegis/pipeline/runner.py`, `backend/aegis/memory/weight_store.py`]
- write_files: [`backend/aegis/pipeline/runner.py`]
- verify: `cd backend && uv run python -c "from aegis.pipeline.runner import _inject_weight_snapshot; print('OK')"`
- status: done

### Wave 4（依赖 Wave 3）

#### T09: 注册 weights router 到 FastAPI app
- 描述: 修改 `backend/aegis/api/app.py`，import weights router 并 `app.include_router(weights.router, prefix="/api/v1")`
- depends_on: [T07]
- read_files: [`backend/aegis/api/app.py`, `backend/aegis/api/routes/weights.py`]
- write_files: [`backend/aegis/api/app.py`]
- verify: `cd backend && uv run python -c "from aegis.api.app import app; routes = [r.path for r in app.routes]; assert '/api/v1/memory/weights' in routes"`
- status: done

#### T10: 更新 schedule.yaml 添加 weight adapter cron 配置
- 描述: 在 `backend/config/schedule.yaml` 中添加 `weight_adapter` section，包含 `observation_check`（cron: `0 1 * * *`）和 `weight_update`（cron: `0 4 * * 0`）两个 job 配置
- depends_on: [T06]
- read_files: [`backend/config/schedule.yaml`]
- write_files: [`backend/config/schedule.yaml`]
- verify: `cd backend && uv run python -c "import yaml; c=yaml.safe_load(open('config/schedule.yaml')); assert 'weight_adapter' in c['schedules']"`
- status: done

#### T11: 编写单元测试
- 描述: 创建测试文件，覆盖所有 12 个 AC：
  - `tests/memory/test_weight_adapter.py` — AC-1/AC-2/AC-6/AC-7/AC-12（composite_signal、time_decay、insufficient_samples、empty_cards、pnl_signal 边界）
  - `tests/memory/test_weighted_regression.py` — AC-5（weight clamping）
  - `tests/memory/test_observation_period.py` — AC-3/AC-4（in_period_no_update、backfill_on_expiry）
  - `tests/memory/test_weight_store.py` — AC-10/AC-11（get_history、initialize_from_config）
  - `tests/api/test_weight_api.py` — AC-9（manual_override）
  - `tests/pipeline/test_pipeline_weight_inject.py` — AC-8（weight_snapshot 非空）
- depends_on: [T04, T05, T07, T08]
- read_files: [`backend/aegis/memory/weight_adapter.py`, `backend/aegis/memory/weight_store.py`, `backend/aegis/memory/observation_period.py`, `backend/aegis/api/routes/weights.py`, `backend/aegis/pipeline/runner.py`]
- write_files: [`backend/tests/memory/test_weight_adapter.py`, `backend/tests/memory/test_weighted_regression.py`, `backend/tests/memory/test_observation_period.py`, `backend/tests/memory/test_weight_store.py`, `backend/tests/api/test_weight_api.py`, `backend/tests/pipeline/test_pipeline_weight_inject.py`]
- verify: `cd backend && uv run pytest tests/memory/test_weight_adapter.py tests/memory/test_weighted_regression.py tests/memory/test_observation_period.py tests/memory/test_weight_store.py tests/api/test_weight_api.py tests/pipeline/test_pipeline_weight_inject.py -v`
- status: done

## 风险任务
- **T04 (WeightAdapter)**: numpy 加权最小二乘回归可能数值不稳定，需 try/except `LinAlgError` 并 fallback 到默认权重 1.0
- **T06 (Scheduler)**: 从零创建 scheduler 进程，需确保 SQLAlchemyJobStore 与现有 SQLite 数据库兼容，避免表冲突
- **T08 (Pipeline 集成)**: 修改 runner.py 需确保不破坏现有 Full/Lightweight Pipeline 流程，`_inject_weight_snapshot` 失败时不应阻断 Pipeline

## 回滚任务
- 删除新增文件：`weight_adapter.py`, `weight_store.py`, `observation_period.py`, `thesis_store.py`, `scheduler.py`, `weights.py` (routes)
- 从 `runner.py` 移除 `_inject_weight_snapshot` 调用
- 从 `app.py` 移除 weights router 注册
- 从 `pyproject.toml` 移除 numpy 依赖
- 从 `schedule.yaml` 移除 weight_adapter section
- `factor_weights` 表保留不删除（Sprint-0 产物）
