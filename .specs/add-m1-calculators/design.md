# Design: add-m1-calculators

## 技术方案概述

在 `backend/aegis/calculators/` 下实现 5 个纯计算模块 + 1 个共享 Pydantic 模型文件。所有函数为 sync、无 IO、无 LLM 依赖，返回值统一为 Pydantic BaseModel。遵循 AGENTS.md 第 5 节编码规范。

## 组件拆分

```
backend/aegis/calculators/
├── __init__.py          # 公开导出所有计算函数与模型
├── models.py            # 共享 Pydantic 结果模型
├── greeks.py            # Black-Scholes + 隐含波动率
├── stop_loss.py         # 固定百分比 + 支撑位动态止损
├── wyckoff.py           # Wyckoff 相位检测
├── gex.py               # Gamma Exposure 聚合
└── volume_profile.py    # 成交量分布 + POC + Value Area
```

## API 设计

### greeks.py

```python
def compute_greeks(
    option_type: Literal["call", "put"],
    S: float,       # 标的价格
    K: float,       # 行权价
    T: float,       # 到期时间（年）
    r: float,       # 无风险利率
    sigma: float,   # 波动率
    q: float = 0.0, # 股息率
) -> GreeksResult:
    """Black-Scholes Greeks + implied volatility via Newton-Raphson."""
    ...

def compute_implied_volatility(
    option_type: Literal["call", "put"],
    market_price: float,
    S: float, K: float, T: float, r: float, q: float = 0.0,
    max_iter: int = 100,
    tolerance: float = 1e-6,
) -> float:
    """Newton-Raphson 反推隐含波动率。"""
    ...
```

### stop_loss.py

```python
def compute_stop_loss(
    entry_price: float,
    mode: Literal["fixed_pct", "support_based"],
    support_level: float | None = None,
) -> StopLossResult:
    """计算止损价与止损百分比。"""
    ...
```

### wyckoff.py

```python
def detect_wyckoff_phase(
    ohlcv_df: "pd.DataFrame",
) -> WyckoffResult:
    """基于量价关系识别 Wyckoff 相位。"""
    ...
```

### gex.py

```python
def compute_gex(
    options_chain_df: "pd.DataFrame",
    spot: float,
) -> GexResult:
    """计算 Gamma Exposure 聚合、Gamma Flip、Max Pain。"""
    ...
```

### volume_profile.py

```python
def compute_volume_profile(
    ohlcv_df: "pd.DataFrame",
    bins: int = 50,
) -> VolumeProfileResult:
    """计算成交量分布、POC、Value Area。"""
    ...
```

## 数据模型

所有模型定义在 `backend/aegis/calculators/models.py`，首行标注 `"""Frozen at M1. Changes require owner review."""`。

```python
from pydantic import BaseModel
from typing import Literal

class GreeksResult(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float

class StopLossResult(BaseModel):
    stop_price: float
    stop_pct: float          # 止损百分比（如 0.08 表示 8%）
    mode: Literal["fixed_pct", "support_based"]

class WyckoffResult(BaseModel):
    phase: Literal["accumulation", "distribution", "markup", "markdown", "unknown"]
    confidence: float        # 0-1
    rationale: str           # 判断依据简述

class GexResult(BaseModel):
    total_gex: float
    gamma_flip: float | None  # Gamma Flip 点位，无则 None
    max_pain: float | None    # Max Pain 点位，无则 None
    gex_by_strike: dict[float, float]  # {strike: GEX}

class VolumeProfileResult(BaseModel):
    poc: float               # Point of Control
    value_area_high: float
    value_area_low: float
    profile: dict[float, float]  # {price_level: volume}
```

## 算法设计

### Greeks (Black-Scholes)

标准 Black-Scholes 公式：
- d1 = (ln(S/K) + (r - q + sigma²/2) × T) / (sigma × √T)
- d2 = d1 - sigma × √T
- Call: delta = e^(-qT) × N(d1), gamma = N'(d1) × e^(-qT) / (S × sigma × √T)
- theta = -(S × N'(d1) × sigma × e^(-qT)) / (2√T) - rK × e^(-rT) × N(d2) + qS × e^(-qT) × N(d1) (call)
- vega = S × e^(-qT) × N'(d1) × √T
- rho = K × T × e^(-rT) × N(d2) (call)

N(x) 用 `math.erf` 实现，N'(x) 为标准正态 PDF。

隐含波动率：Newton-Raphson 迭代，初始猜测 sigma=0.3，vega 为导数。

### Stop Loss

- fixed_pct: stop_price = entry_price × (1 - 0.08)
- support_based: stop_price = support_level × (1 - 0.02)，support_level 为 None 时抛 ValueError

### Wyckoff Phase Detection

启发式算法，基于最近 N 根 K 线的：
1. 价格趋势（线性回归斜率）
2. 成交量趋势（线性回归斜率）
3. 波动率变化（ATR 趋势）
4. 价格-成交量背离度

规则矩阵：
| 价格趋势 | 成交量趋势 | 波动率 | 相位 |
|---------|-----------|--------|------|
| ↓/横盘 | ↓/萎缩 | ↓ | Accumulation |
| ↑ | ↑ | ↑ | Markup |
| ↑/横盘 | ↑/放量 | ↑ | Distribution |
| ↓ | ↑ | ↑ | Markdown |

### GEX Calculator

- 每行期权：GEX_i = gamma_i × open_interest_i × spot × 100
- 按 strike 聚合：gex_by_strike[strike] = sum(GEX_i for all options at that strike)
- total_gex = sum(all GEX_i)
- Gamma Flip：total GEX 从正变负的 strike 点位（线性插值）
- Max Pain：总 OI（call + put）最大的 strike

### Volume Profile

- 将价格范围 [low, high] 等分为 bins 个区间
- 每根 K 线的成交量按价格分布分配到对应区间（简化：分配到 (high+low)/2 所在区间）
- POC = 成交量最大的价格区间中点
- Value Area：从 POC 向两侧扩展，直到累计成交量 ≥ 总成交量 × 70%

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 浮点精度：erf/cdf 在极端参数下精度不足 | Greeks 值偏差 | `pytest.approx(rel=1e-4)` 宽松容差；参考已知解析解验证 |
| Wyckoff 启发式算法边界模糊 | 相位误判 | 返回 confidence 字段；低置信度时标记 unknown |
| GEX 依赖 options_chain 列名 | 列名不匹配崩溃 | 函数内做列名校验，缺失列抛明确 ValueError |
| Volume Profile bins 参数极端 | 内存/性能问题 | bins 限制 10-500，超出范围抛 ValueError |
| T→0 时 Greeks 除零 | 崩溃 | T < 1e-6 时返回边界值（delta→阶跃，gamma/theta/vega→0） |

## 回滚计划
- calculators 模块为纯增量，不修改任何现有文件
- 回滚只需删除 `backend/aegis/calculators/` 下新增文件及 `backend/tests/calculators/` 目录
- 不影响 Pipeline、Agent、Tool 等任何现有模块
