# Sprint-0 Foundation — Plan Prompt (v1.2)

> **分支**: `feat/m1-sprint0-foundation`
> **估时**: 1 天
> **优先级**: P0(阻塞所有其他分支)
> **子 Agent**: `m1-foundation`
> **前置阅读**: `AGENTS.md` v1.2 + `docs/aegis-2.0-tech-arch.md` 第 4、10 节

---

## 1. 目标

搭好 monorepo 骨架 + 冻结 v1.2 契约层 + 跑通最小 LangGraph hello-world,为 A-G 分支并行开发解除阻塞。

---

## 2. 交付物清单

### 2.1 仓库骨架

```
aegis/
├── AGENTS.md                          # v1.2 全局规范
├── README.md                          # 项目入口(quickstart)
├── Makefile                           # 常用命令封装
├── docker-compose.yml                 # 占位(M3 完善)
├── .gitignore                         # 含 .env / data/ / __pycache__/
├── .env.example                       # 含所有 key 占位(含 v1.2 新增数据源预留)
├── docs/
│   ├── aegis-2.0-prd.md              # v1.2
│   ├── aegis-2.0-tech-arch.md        # v1.2
│   ├── aegis-2.0-design-system.md    # v1.0
│   └── sprints/m1/                   # 本次会话产出的 README + branch-*.md
├── backend/
│   ├── pyproject.toml                # uv 管理,依赖见下文
│   ├── ruff.toml                     # line-length 100
│   ├── mypy.ini                      # strict 模式
│   ├── alembic.ini
│   ├── alembic/                      # 空仓 + env.py
│   │   └── versions/.gitkeep
│   ├── aegis/
│   │   ├── __init__.py
│   │   ├── cli.py                    # Typer 入口(只有 `aegis --help` 可用)
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   └── base.py               # 【契约】BaseAgent + manifest 属性 + write_extension/read_extension
│   │   ├── registry/
│   │   │   ├── __init__.py
│   │   │   └── agent_registry.py     # 【契约】AgentManifest Pydantic model
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── state.py              # 【契约】PipelineState v1.2 全字段
│   │   │   ├── graph.py              # 占位:hello-world graph
│   │   │   └── runner.py             # 占位:run_pipeline()
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   └── base.py               # 【契约】BaseTool + ToolResult
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   └── interface.py          # 【契约】MemoryInterface
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   └── client.py             # 【契约】LLMClient(OpenAI 兼容协议)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── base.py               # SQLAlchemy DeclarativeBase
│   │   ├── api/__init__.py           # 占位
│   │   ├── notifier/__init__.py      # 占位
│   │   ├── calculators/__init__.py   # 占位
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── settings.py           # pydantic-settings 加载 .env
│   │       ├── logging.py            # loguru 配置
│   │       ├── retry.py              # tenacity 通用装饰器
│   │       └── circuit_breaker.py    # 三态熔断器骨架(B 分支补全)
│   ├── config/
│   │   ├── tools.yaml                # 空 schema(含 tags 字段示例)
│   │   ├── agents.yaml               # 空 schema(含 manifest 字段示例)
│   │   ├── rules.yaml                # 空 schema
│   │   ├── schedule.yaml             # 空 schema
│   │   └── prompts/.gitkeep
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py               # 全局 fixtures(含 MockLLMClient)
│       ├── foundation/
│       │   ├── test_state_contract.py   # 验证 PipelineState v1.2 全字段
│       │   ├── test_base_agent.py       # 含 manifest 属性校验
│       │   ├── test_agent_manifest.py   # AgentManifest 字段完整性【新增】
│       │   ├── test_memory_interface.py
│       │   ├── test_tool_base.py
│       │   ├── test_llm_client.py
│       │   └── test_hello_graph.py      # 跑通最小 graph
│       └── fixtures/.gitkeep
└── frontend/.gitkeep                  # M2 起填充
```

### 2.2 依赖(`backend/pyproject.toml`)

```toml
[project]
name = "aegis"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    "langgraph>=0.2",
    "langchain-core>=0.3",
    "fastapi>=0.115",
    "pydantic>=2.8",
    "pydantic-settings>=2.5",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "httpx>=0.27",
    "tenacity>=8.3",
    "loguru>=0.7",
    "typer>=0.12",
    "apscheduler>=3.10",
    "python-telegram-bot>=20.7",
    "openai>=1.40",          # 仅在 LLMClient 内部使用
    "pyyaml>=6.0",
    "jinja2>=3.1",
    "pandas>=2.2",
    "pyarrow>=17.0",         # parquet
    "chromadb>=0.5",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
    "ruff",
    "mypy",
    "pip-audit",
]
```

### 2.3 契约层代码(v1.2 冻结)

#### `pipeline/state.py`

```python
"""Frozen at M1 v1.2. Changes require owner review."""
from __future__ import annotations
from datetime import datetime
from typing import Any, ClassVar, Literal, Optional
from pydantic import BaseModel, Field

PipelineMode = Literal["pre-market", "post-market", "manual"]

class FactorScore(BaseModel):
    factor: str
    score: float            # 0-100
    confidence: float       # 0-1
    rationale: str = ""

class OptionContract(BaseModel):
    symbol: str
    type: Literal["call", "put"]
    strike: float
    expiration: str         # YYYY-MM-DD
    dte: int
    bid: float
    ask: float
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float

class Recommendation(BaseModel):
    ticker: str
    action: Literal["buy", "sell", "hold", "close", "add", "reduce"]
    strategy: str           # "leaps_call" / "covered_call" / "stock"
    rationale: str
    factor_scores: list[FactorScore]
    option_contracts: list[OptionContract] = []
    stop_loss: dict[str, Any] = {}
    urgency: Literal["high", "medium", "low"] = "medium"
    score: float = 0.0
    delta_dollars_delta: float = 0.0  # v1.2: 该推荐增加的 Delta 暴露

class BlockedRecommendation(BaseModel):
    recommendation: Recommendation
    block_reason: str
    blocked_at: datetime

class PipelineState(BaseModel):
    # 元数据
    pipeline_id: str
    mode: PipelineMode
    triggered_at: datetime
    tickers: list[str]

    # v1.2: 双 Pipeline 模式
    pipeline_mode: Literal["full", "lightweight"] = "full"
    tickers_holdings_active: list[str] = []
    tickers_holdings_passive: list[str] = []
    entry_mode: dict[str, Literal["passive", "active_left", "active_right", "cc", "sell_put"]] = {}

    # 数据采集
    market_data: dict[str, Any] = {}
    macro_data: dict[str, Any] = {}
    positions: dict[str, Any] = {}

    # 分析结果
    analyst_outputs: dict[str, dict[str, Any]] = {}
    debate_results: dict[str, dict[str, Any]] = {}
    options_step1: dict[str, dict[str, Any]] = {}
    options_step2: dict[str, list[OptionContract]] = {}

    # 决策
    recommendations: list[Recommendation] = []
    blocked_recommendations: list[BlockedRecommendation] = []

    # v1.2: extensions slot(新 Agent 写自定义产出)
    extensions: dict[str, dict[str, Any]] = {}

    # v1.2: Pending Triggers(M1 仅占位)
    pending_triggers: list[dict[str, Any]] = []

    # v1.2: Lightweight Pipeline 输出
    passive_health_alerts: list[dict[str, Any]] = []
    health_scores: dict[str, float] = {}
    delta_dollars_delta: float = 0.0

    # Working Memory
    scratchpad: dict[str, str] = {}   # {agent_name: reasoning_trace}

    # 错误
    error_flags: list[dict[str, Any]] = []

    # 性能
    agent_timings: dict[str, float] = {}
```

#### `registry/agent_registry.py`

```python
"""Frozen at M1 v1.2. Changes require owner review."""
from typing import Literal, Optional
from pydantic import BaseModel

class AgentManifest(BaseModel):
    """每个 Agent 必须导出的注册信息。"""
    name: str
    version: str = "0.1.0"
    requires: list[str] = []          # 依赖的 state 字段或上游 Agent 输出 key
    provides: list[str] = []          # 写入 state 的字段或 extensions key
    tags: list[str] = []              # 能力标签
    llm_dependency: bool = True       # 是否需要 LLM(决定能否进 Lightweight)
    parallel_group: Optional[str] = None  # 同组可并行
    pipeline_mode: Literal["full", "lightweight", "both"] = "full"
    enabled: bool = True
```

#### `agents/base.py`

```python
"""Frozen at M1 v1.2. Changes require owner review."""
from abc import ABC, abstractmethod
from typing import Any, ClassVar
from aegis.pipeline.state import PipelineState
from aegis.memory.interface import MemoryInterface
from aegis.registry.agent_registry import AgentManifest

class BaseAgent(ABC):
    name: str = "base"
    manifest: ClassVar[AgentManifest]   # 子类必须覆盖

    def __init__(self, memory: MemoryInterface, tools: dict[str, Any], config: dict[str, Any]):
        self.memory = memory
        self.tools = tools
        self.config = config

    @abstractmethod
    async def run(self, state: PipelineState) -> PipelineState:
        ...

    def write_extension(self, state: PipelineState, key: str, value: Any) -> None:
        """将自定义产出写入 state.extensions[agent_name][key]。"""
        if self.name not in state.extensions:
            state.extensions[self.name] = {}
        state.extensions[self.name][key] = value

    def read_extension(self, state: PipelineState, agent_name: str, key: str) -> Any:
        """读取其他 Agent 的 extension 产出。"""
        return state.extensions.get(agent_name, {}).get(key)
```

#### `memory/interface.py`

```python
"""Frozen at M1 v1.0. Changes require owner review."""
from abc import ABC, abstractmethod
from typing import Any, Literal

MemoryScope = Literal["working", "short", "long", "episodic"]

class MemoryInterface(ABC):
    @abstractmethod
    async def read(self, scope: MemoryScope, query: dict[str, Any]) -> list[dict[str, Any]]: ...
    @abstractmethod
    async def write(self, scope: MemoryScope, data: dict[str, Any]) -> None: ...
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]: ...
    @abstractmethod
    async def summarize(self, ticker: str, date_range: tuple[str, str]) -> dict[str, Any]: ...
    @abstractmethod
    async def archive_scratchpad(self, pipeline_id: str, scratchpad: dict[str, str]) -> None: ...
```

#### `tools/base.py`

```python
"""Frozen at M1 v1.0. Changes require owner review."""
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel

class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    source: str = ""
    cached: bool = False

class BaseTool(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, **kwargs: Any) -> ToolResult: ...
```

#### `llm/client.py`

```python
"""Frozen at M1 v1.0. Changes require owner review."""
from typing import Any
from openai import AsyncOpenAI
from aegis.utils.settings import settings

class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = await self._client.chat.completions.create(**kwargs)
        return {
            "content": resp.choices[0].message.content,
            "usage": resp.usage.model_dump() if resp.usage else {},
            "model": resp.model,
        }
```

### 2.4 工具骨架

- `utils/settings.py`:pydantic-settings 加载 `.env`,定义所有 key 字段(含 v1.2 新增预留)
- `utils/logging.py`:loguru 全局配置
- `utils/retry.py`:tenacity wrapper(exponential_backoff,最多 3 次)
- `utils/circuit_breaker.py`:三态骨架,B 分支补全

### 2.5 Hello-world Graph

`pipeline/graph.py` 实现最小 graph:`START → echo_node → END`
`tests/foundation/test_hello_graph.py` 调用 runner,验证 state 能流转。

---

## 3. 测试要求

| 文件 | 测试点 |
|---|---|
| `test_state_contract.py` | PipelineState v1.2 全字段存在 + 类型正确(含 extensions / pipeline_mode / entry_mode 等) |
| `test_base_agent.py` | 抽象方法签名正确 + manifest 属性存在 + write_extension/read_extension 工作 |
| `test_agent_manifest.py` | AgentManifest 全字段校验 + pipeline_mode Literal 约束 + enabled 默认值 |
| `test_memory_interface.py` | 5 个抽象方法签名正确 |
| `test_tool_base.py` | ToolResult 字段完整 |
| `test_llm_client.py` | mock httpx,验证 base_url / api_key 注入 |
| `test_hello_graph.py` | LangGraph state 流转正确 |

---

## 4. 验收清单

- [ ] `uv sync` 通过
- [ ] `ruff check .` 通过
- [ ] `mypy backend/aegis` 通过
- [ ] `pytest backend/tests/foundation/` 全绿(含 v1.2 新字段 + manifest 校验)
- [ ] `alembic init` 完成,alembic env.py 指向 settings.DATABASE_URL
- [ ] `.env.example` 字段完整(参考 AGENTS.md v1.2 第 8.1 节,含 M2 预留注释)
- [ ] PR 描述:"v1.2 契约层冻结,A-G 分支可开干"

---

## 5. 不允许做的事

- 不实现具体 Agent(A-G 分支的事)
- 不实现具体 Tool(A 分支的事)
- 不实现 Calculator(B 分支的事)
- 不实现 graph_builder 动态装配逻辑(M4)
- 不写 Memory 的 SQLAlchemy 实现(M3)
- 不引入 frontend 任何代码

---

## 6. 子 Agent 行为约束

- 完成后输出:变更文件树 + 测试结果摘要 + 给 A-G 分支的「契约层签名 + v1.2 新增字段清单」
- 禁止改任何 A-G 分支会用到的具体业务文件
- 完成后通知主 session:「Sprint-0 v1.2 完成,A-G 可启动」
