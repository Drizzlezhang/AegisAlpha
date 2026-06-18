# Tasks: m3-sprint-0-foundation

## 任务波次

### Wave 1（无依赖，可并行）— 基础设施铺设

#### T01: M2 遗留 Smart Money 测试修复
- 描述: 修复 `test_smart_money_agent.py` 中 3 个测试断言值，使其与归一化到 0-100 的算法一致。同时更新注释中的计算过程。
- read_files: [`backend/aegis/agents/smart_money_agent.py`, `backend/tests/agents/test_smart_money_agent.py`]
- write_files: [`backend/tests/agents/test_smart_money_agent.py`]
- verify: `cd backend && .venv/bin/python -m pytest tests/agents/test_smart_money_agent.py -v`
- status: done

#### T02: PipelineState v1.4 契约扩展
- 描述: 在 `state.py` 末尾新增 5 个 M3 字段（thesis_cards / kol_signals / universe_candidates / weight_snapshot / thesis_validation_results），所有 default 为空容器。
- read_files: [`backend/aegis/pipeline/state.py`]
- write_files: [`backend/aegis/pipeline/state.py`]
- verify: `cd backend && .venv/bin/python -c "from aegis.pipeline.state import PipelineState; s = PipelineState(); assert s.thesis_cards == {}; assert s.kol_signals == {}; assert s.universe_candidates == []; assert s.weight_snapshot == {}; assert s.thesis_validation_results == {}; print('OK')"`
- status: done

#### T03: DB Models — 4 个新模型文件
- 描述: 创建 `models/thesis.py`（ThesisCard）、`models/kol.py`（KOLSource + KOLCall）、`models/long_term_memory.py`（LongTermMemory）、`models/factor_weight.py`（FactorWeight），字段与 dev plan 一致。
- read_files: [`backend/aegis/models/base.py`, `backend/aegis/models/memory.py`]
- write_files: [`backend/aegis/models/thesis.py`, `backend/aegis/models/kol.py`, `backend/aegis/models/long_term_memory.py`, `backend/aegis/models/factor_weight.py`]
- verify: `cd backend && .venv/bin/python -c "from aegis.models.thesis import ThesisCard; from aegis.models.kol import KOLSource, KOLCall; from aegis.models.long_term_memory import LongTermMemory; from aegis.models.factor_weight import FactorWeight; print('OK')"`
- status: done

#### T04: models/__init__.py 更新
- 描述: 更新 `models/__init__.py`，导出所有 7 个模型（含已有 ShortTermMemory）。
- read_files: [`backend/aegis/models/__init__.py`]
- write_files: [`backend/aegis/models/__init__.py`]
- verify: `cd backend && .venv/bin/python -c "from aegis.models import ThesisCard, KOLSource, KOLCall, LongTermMemory, FactorWeight, ShortTermMemory; print('OK')"`
- status: done

#### T05: MemoryInterface v1.1 签名扩展
- 描述: 更新 `memory/interface.py`，`read` 新增 `limit=10`，`search` 新增 `collection="default"` 和 `filter=None`，`summarize` 的 `ticker` 改为 Optional 并新增 `data_type=""`。文件头注释更新为 "Frozen at M3 v1.1"。
- read_files: [`backend/aegis/memory/interface.py`]
- write_files: [`backend/aegis/memory/interface.py`]
- verify: `cd backend && .venv/bin/python -c "from aegis.memory.interface import MemoryInterface; import inspect; sig = inspect.signature(MemoryInterface.read); assert 'limit' in sig.parameters; print('OK')"`
- status: done

#### T06: agents.yaml 新增 3 个 Agent
- 描述: 在 `agents.yaml` 末尾追加 universe_triage / kol_tracker / thesis_validator，均 enabled=false。
- read_files: [`backend/config/agents.yaml`]
- write_files: [`backend/config/agents.yaml`]
- verify: `cd backend && .venv/bin/python -c "import yaml; d = yaml.safe_load(open('config/agents.yaml')); assert 'universe_triage' in d['agents']; assert d['agents']['universe_triage']['enabled'] == False; print('OK')"`
- status: done

#### T07: 4 个配置文件新增
- 描述: 创建 `config/universe_watchlist.yaml`、`config/kol_sources.yaml`、`config/memory.yaml`、`config/weights.yaml`，内容与 dev plan 一致。
- read_files: [`backend/config/tools.yaml`]
- write_files: [`backend/config/universe_watchlist.yaml`, `backend/config/kol_sources.yaml`, `backend/config/memory.yaml`, `backend/config/weights.yaml`]
- verify: `cd backend && .venv/bin/python -c "import yaml; [yaml.safe_load(open(f'config/{f}')) for f in ['universe_watchlist.yaml','kol_sources.yaml','memory.yaml','weights.yaml']]; print('OK')"`
- status: done

#### T08: settings.py 新增 M3 key
- 描述: 在 `settings.py` 中新增 CHROMA_PERSIST_DIR / EMBEDDING_MODEL / STOCKTWITS_ACCESS_TOKEN / REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / X_BEARER_TOKEN / MEMORY_SHORT_TTL_DAYS / MEMORY_COMPRESSION_ENABLED / OBSERVATION_PERIOD_DAYS / UNIVERSE_SCAN_TOP_N / UNIVERSE_SCAN_ENABLED。
- read_files: [`backend/aegis/utils/settings.py`]
- write_files: [`backend/aegis/utils/settings.py`]
- verify: `cd backend && .venv/bin/python -c "from aegis.utils.settings import settings; assert hasattr(settings, 'CHROMA_PERSIST_DIR'); assert hasattr(settings, 'EMBEDDING_MODEL'); assert hasattr(settings, 'UNIVERSE_SCAN_ENABLED'); print('OK')"`
- status: done

#### T09: .env.example 更新
- 描述: 在 `.env.example` 末尾追加 M3 新 key（ChromaDB / KOL / Memory / Universe），均有注释说明。
- read_files: [`backend/.env.example`]
- write_files: [`backend/.env.example`]
- verify: `grep -q "CHROMA_PERSIST_DIR" backend/.env.example && grep -q "EMBEDDING_MODEL" backend/.env.example && grep -q "UNIVERSE_SCAN_ENABLED" backend/.env.example && echo "OK"`
- status: done

#### T10: AGENTS.md v1.2 → v1.3
- 描述: 更新版本号 v1.2→v1.3，更新 Section 9.1 四层 Memory 表格标注 M3 状态，更新 Section 18.1 M3 行标记「当前」，新增 "M3 新增约束规则" Section（6 条规则）。
- read_files: [`AGENTS.md`]
- write_files: [`AGENTS.md`]
- verify: `grep -q "v1.3" AGENTS.md && grep -q "M3 新增约束规则" AGENTS.md && echo "OK"`
- status: done

### Wave 2（依赖 Wave 1）— 迁移 + 测试

#### T11: Alembic 迁移
- 描述: 运行 `alembic revision --autogenerate` 生成迁移文件，手动检查 upgrade/downgrade 包含 5 张表 + 索引。
- depends_on: [T03, T04]
- read_files: [`backend/alembic/env.py`, `backend/alembic.ini`]
- write_files: [`backend/alembic/versions/m3_001_*.py`]
- verify: `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade -1 && echo "OK"`
- status: done

#### T12: 单元测试
- 描述: 编写测试文件：`test_state_v14.py`（v1.4 字段 + v1.3 兼容）、`test_models_thesis.py`、`test_models_kol.py`、`test_models_ltm.py`、`test_models_weight.py`、`test_memory_interface_v11.py`。
- depends_on: [T02, T03, T04, T05]
- read_files: [`backend/tests/foundation/test_state.py`, `backend/tests/agents/test_smart_money_agent.py`]
- write_files: [`backend/tests/foundation/test_state_v14.py`, `backend/tests/models/test_models_thesis.py`, `backend/tests/models/test_models_kol.py`, `backend/tests/models/test_models_ltm.py`, `backend/tests/models/test_models_weight.py`, `backend/tests/memory/test_memory_interface_v11.py`]
- verify: `cd backend && .venv/bin/python -m pytest tests/foundation/test_state_v14.py tests/models/ tests/memory/ -v`
- status: pending

### Wave 3（依赖 Wave 2）— 全量验证

#### T13: 全量测试 + lint + type check
- 描述: 运行全量测试套件、ruff check、mypy，确保无回归。
- depends_on: [T01, T11, T12]
- read_files: []
- write_files: []
- verify: `cd backend && .venv/bin/python -m pytest tests/ -v && .venv/bin/ruff check aegis/ tests/ && .venv/bin/mypy aegis/models/ aegis/pipeline/state.py aegis/memory/interface.py aegis/utils/settings.py`
- status: done

### Wave 4（依赖 Wave 3）— 交付

#### T14: Commit + Ship
- 描述: 提交所有变更，生成 conventional commit message。
- depends_on: [T13]
- read_files: []
- write_files: []
- verify: `git log --oneline -1`
- status: done

## 风险任务
- **T01 (Smart Money 测试修复)**: 期望值需手动验算，确保与 `_compute_score` 算法一致
- **T02 (PipelineState v1.4)**: 需验证 v1.3 JSON 反序列化到 v1.4 不报错
- **T11 (Alembic 迁移)**: autogenerate 可能遗漏索引，需手动检查
- **T13 (全量测试)**: 新增 ~6 个测试文件，需确保与已有测试无冲突

## 回滚任务
- 如需回滚：删除 5 个 PipelineState 字段、`alembic downgrade -1`、删除 4 个新 YAML、删除 agents.yaml 中 3 个 Agent、revert AGENTS.md
