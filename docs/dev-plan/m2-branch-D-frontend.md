# M2 Branch D — Frontend v1 (Next.js Dashboard)

> **分支**: `feat/m2-frontend`
> **估时**: 8 天
> **优先级**: P0
> **子 Agent**: `m2-frontend`
> **前置**: M2 Sprint-0 完成（API 骨架可用）
> **前置阅读**: `AGENTS.md` v1.2 + `docs/design.md` + `docs/tech-arch.md` 第 8 节 + `docs/prd.md` 第 5 节

---

## 1. 目标

构建 Aegis 2.0 Web 前端 v1，包含 Dashboard / Positions / Recommendation Detail / Triggers / Flows 五个核心页面。严格遵循 `docs/design.md` 设计规范（Dark-first、金融终端风格），通过 REST API + WebSocket 与后端通信。

---

## 2. 技术栈

| 库 | 版本 | 用途 |
|---|---|---|
| Next.js | 15 (App Router) | 框架 |
| React | 19 | UI |
| TypeScript | 5.x | 类型安全 |
| Tailwind CSS | v4 | 样式 |
| shadcn/ui | latest | 基础组件 |
| Recharts | 2.x | 图表 |
| TanStack Table | 8.x | 数据表格 |
| Zustand | 4.x | 全局状态 |
| SWR | 2.x | 数据请求 + 缓存 |
| Lucide Icons | latest | 图标 |

---

## 3. 交付物清单

### 3.1 项目初始化

**目录**: `frontend/`

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout + ThemeProvider + TopBar
│   ├── globals.css             # shadcn theme 覆盖 + aegis CSS variables
│   ├── (dashboard)/
│   │   ├── page.tsx            # Dashboard 首页
│   │   ├── positions/
│   │   │   └── page.tsx        # 持仓页
│   │   ├── recommendations/
│   │   │   ├── page.tsx        # 推荐列表页
│   │   │   └── [id]/
│   │   │       └── page.tsx    # 推荐详情页
│   │   ├── triggers/
│   │   │   └── page.tsx        # Pending Triggers 页
│   │   └── flows/
│   │       └── page.tsx        # Fund Flow + Smart Money 页
│   └── api/                    # Next.js API routes (proxy to backend, if needed)
├── components/
│   ├── ui/                     # shadcn/ui 组件（Button, Card, Badge, Table, etc.）
│   ├── layout/
│   │   ├── top-bar.tsx         # Top Bar (48px): Logo + Nav + Pipeline Status + Time
│   │   ├── left-panel.tsx      # Left Panel (280px): Holdings + Watch + Thesis
│   │   ├── right-panel.tsx     # Right Panel (320px): Signal Log + Agent Runs + Triggers
│   │   └── status-bar.tsx      # Status Bar (28px): Last Run + Errors + Version
│   ├── dashboard/
│   │   ├── portfolio-summary.tsx   # 总 NAV / 日 P&L / Delta $ / 现金比
│   │   ├── recommendation-feed.tsx # 推荐摘要（盘前/盘后 tab）
│   │   ├── position-snapshot.tsx   # 持仓快照（Table ↔ Treemap 切换）
│   │   ├── delta-dollars-chart.tsx # Delta Dollars 柱状图
│   │   ├── greeks-summary.tsx      # Greeks 汇总表
│   │   ├── expiry-calendar.tsx     # 到期日历热力图
│   │   ├── pnl-trend-chart.tsx     # P&L 趋势图
│   │   ├── fund-flow-heatmap.tsx   # Fund Flow Heatmap（v1.2 新增）
│   │   ├── smart-money-card.tsx    # Smart Money 摘要 Card（v1.2 新增）
│   │   └── health-panel.tsx        # 持仓健康度面板（v1.2 新增）
│   ├── recommendations/
│   │   ├── recommendation-card.tsx
│   │   ├── strategy-comparison.tsx # 多策略对比表（v1.2 新增）
│   │   ├── scenario-pnl-chart.tsx  # 场景模拟 P&L 图（v1.2 新增）
│   │   ├── smart-money-block.tsx   # Smart Money 论据块（可折叠）
│   │   └── fund-flow-block.tsx     # Fund Flow 论据块（可折叠）
│   ├── positions/
│   │   ├── position-table.tsx
│   │   └── position-detail.tsx
│   ├── triggers/
│   │   └── trigger-list.tsx
│   ├── flows/
│   │   ├── etf-flow-table.tsx
│   │   ├── sector-heatmap.tsx
│   │   └── smart-money-detail.tsx
│   └── charts/
│       ├── signal-badge.tsx        # Bull/Bear/Neutral/Blocked badge
│       └── entry-mode-badge.tsx    # left/right/both badge
├── lib/
│   ├── api.ts                  # Backend API client（base URL、fetch wrapper）
│   ├── ws.ts                   # WebSocket client
│   ├── design-tokens.ts        # SIGNAL_COLORS / CHART_COLORS / AGENT_STATUS_COLORS
│   ├── types.ts                # TypeScript type definitions（mirror backend schemas）
│   └── utils.ts                # 格式化（价格、百分比、日期、Delta Dollars）
├── stores/
│   ├── pipeline-store.ts       # Pipeline 运行状态（WebSocket 驱动）
│   └── portfolio-store.ts      # Portfolio 数据缓存
├── tailwind.config.ts          # Aegis 定制主题（按 design.md 10.1）
├── next.config.ts
├── tsconfig.json
└── package.json
```

### 3.2 全局布局

按 `docs/design.md` 第 4.1 节三列布局：

```
┌──────────────────────────────────────────────────────────┐
│  Top Bar (48px): Logo + Nav Tabs + Pipeline Status + Time│
├────────┬─────────────────────────────┬───────────────────┤
│        │                             │                   │
│ Left   │     Main Content Area       │    Right Panel    │
│ Panel  │     (flex-1, scrollable)    │    (320px)        │
│ (280px)│                             │                   │
│        │                             │ - Signal Log      │
│ - Holds│  Cards / Charts / Tables    │ - Agent Runs      │
│ - Watch│                             │ - Triggers        │
│        │                             │                   │
├────────┴─────────────────────────────┴───────────────────┤
│  Status Bar (28px): Last Pipeline Run + Errors + Version │
└──────────────────────────────────────────────────────────┘
```

**响应式**:
- `≥ 1440px`: 三列完整展示
- `1024-1439px`: 三列压缩（Left 240 + Main + Right 280）
- `768-1023px`: Left 可折叠 + Main; Right 收纳为抽屉
- `< 768px`: 不支持

### 3.3 Dashboard 页 (`/`)

固定 2×3 + 1×3 grid（M2 v1.2 新增模块）：

**第一行**:
- Portfolio Summary Card（全宽）: 总 NAV / 日 P&L / Delta $ / 现金比

**第二行（2 列）**:
- 推荐摘要（盘前 / 盘后 tab 切换）
- 持仓快照（Table ↔ Treemap 切换）

**第三行（2 列）**:
- Delta Dollars 柱状图
- Greeks 汇总表

**第四行（2 列）**:
- 到期日历（热力图）
- P&L 趋势图（不叠加基准）

**第五行（M2 新增，3 列）**:
- Fund Flow Heatmap（板块 ETF 7 日资金流热力图）
- Smart Money 摘要 Card（近 24h unusual options Top 5）
- 持仓健康度面板（active 持仓健康分 0-100 排序）

### 3.4 Positions 页 (`/positions`)

- TanStack Table 展示所有持仓
- 列: Account / Ticker / Type / Qty / Avg Cost / Current / P&L / Delta / Greeks / DTE / Entry Mode / Grade / Health Score
- 排序 + 筛选（按 account / entry_mode / grade）
- 数字列右对齐 + `tabular-nums`
- 涨跌色: 正数 signal-bull / 负数 signal-bear
- Click 行 → 展开持仓详情（Greeks 图表 + Thesis Card 关联）

### 3.5 Recommendation Detail 页 (`/recommendations/[id]`)

- **顶部**: Ticker + 方向 + entry_mode badge + urgency + score
- **多策略对比表**: LEAPS Call vs Diagonal vs Vertical 等，列出成本 / 最大盈利 / 最大亏损 / Greeks / 适用场景
- **场景模拟 P&L 图**: 三场景（目标价 / 横盘 / 止损）+ 30/60/90 天 Theta 衰减曲线
- **Smart Money 论据块**（可折叠）: direction_bias + top 3 异常单 + narrative
- **Fund Flow 论据块**（可折叠）: macro_liquidity + credit_appetite + 板块轮动 + narrative
- **Debate 摘要**: Bull vs Bear 论点
- **止损方案**: support_based / fixed_pct + 具体价位
- **Risk Gate 状态**: passed / blocked（附原因）

### 3.6 Triggers 页 (`/triggers`)

- 展示 Pending Triggers 列表
- 列: Ticker / Type / Params / Suggested Action / Valid Until / Status
- 操作: 取消触发（DELETE /api/v1/triggers/{id}）
- 状态: pending(neutral) / triggered(bull) / expired(tertiary) / cancelled(bear)

### 3.7 Flows 页 (`/flows`)

- **Tab 1: ETF Flows**
  - SPY / QQQ / GLD / SLV 7 日资金流柱状图
  - 板块 ETF Heatmap（颜色编码资金流入/流出强度）
- **Tab 2: Smart Money**
  - 按 ticker 查看 Smart Money 详情
  - Unusual Options 列表 + OI 变化图表
  - direction_bias + smart_money_score

### 3.8 API Client

**文件**: `frontend/lib/api.ts`

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

// 封装 SWR fetcher
export const fetcher = (url: string) => fetch(`${API_BASE}${url}`).then(r => r.json())

// API endpoints
export const api = {
  pipeline: {
    latest: () => `/pipeline/runs?limit=1`,
    runs: (params?: Record<string, string>) => `/pipeline/runs?${new URLSearchParams(params)}`,
    trigger: (mode: string) => fetch(`${API_BASE}/pipeline/trigger`, { method: 'POST', body: JSON.stringify({ mode }) }),
  },
  portfolio: {
    snapshot: () => `/portfolio/snapshot`,
    greeks: () => `/portfolio/greeks`,
    deltaDollars: () => `/portfolio/delta-dollars`,
    health: () => `/portfolio/health`,
  },
  recommendations: {
    list: () => `/recommendations`,
    detail: (id: number) => `/recommendations/${id}`,
  },
  triggers: {
    list: () => `/triggers`,
    cancel: (id: number) => fetch(`${API_BASE}/triggers/${id}`, { method: 'DELETE' }),
  },
  flows: {
    etf: () => `/flows/etf`,
    sector: () => `/flows/sector`,
    smartMoney: (ticker: string) => `/flows/smart-money/${ticker}`,
  },
}
```

### 3.9 WebSocket Client

**文件**: `frontend/lib/ws.ts`

```typescript
// 连接 ws://localhost:8000/ws/pipeline
// 接收 PipelineEvent:
interface PipelineEvent {
  type: "agent_start" | "agent_complete" | "agent_failed" | "pipeline_complete" | "trigger_fired"
  pipeline_run_id: number
  pipeline_mode: "full" | "lightweight"
  agent_name?: string
  ticker?: string
  timestamp: string
  data?: any
}

// Zustand store 接收事件,驱动 UI 实时更新
```

### 3.10 Design Tokens 实现

严格按 `docs/design.md` 第 10 节实现:
- `tailwind.config.ts`: Aegis 定制主题（所有 `--aegis-*` 变量）
- `globals.css`: shadcn 主题覆盖（`[data-theme="dark"]`）
- `design-tokens.ts`: SIGNAL_COLORS / CHART_COLORS / AGENT_STATUS_COLORS

---

## 4. 开发阶段

### Phase 1（Day 1-3）: 骨架 + Dashboard

1. `npx create-next-app@latest` + Tailwind v4 + shadcn/ui 初始化
2. 全局布局（TopBar + LeftPanel + RightPanel + StatusBar）
3. Design Tokens + globals.css
4. Dashboard 页 6 个核心 Card（用 mock 数据）
5. API client + SWR 基础配置

### Phase 2（Day 4-5）: Positions + Recommendations

1. Positions 页 TanStack Table
2. Recommendation 列表页
3. Recommendation 详情页（含策略对比表 + P&L 图）
4. Signal Badge / Entry Mode Badge 组件

### Phase 3（Day 6-7）: Triggers + Flows + M2 新增模块

1. Triggers 页
2. Flows 页（ETF Flows + Smart Money）
3. Dashboard M2 新增模块（Fund Flow Heatmap + Smart Money Card + Health Panel）
4. WebSocket 集成

### Phase 4（Day 8）: 联调 + 响应式

1. 对接后端 REST API（替换 mock 数据）
2. 响应式适配（1440px / 1024px / 768px）
3. 质量检查（按 design.md 第 11 节清单）

---

## 5. Mock 数据策略

D 分支可从 Sprint-0 开始并行开发（不依赖后端 Agent 完成）：
- `frontend/mocks/` 目录包含所有 API endpoint 的 mock JSON
- 开发期间 `NEXT_PUBLIC_USE_MOCK=true` 使用 mock 数据
- 后端 API 就绪后切换为真实数据

---

## 6. 测试要求

| 文件 | 测试点 |
|---|---|
| `__tests__/components/portfolio-summary.test.tsx` | 数字格式化 + 涨跌色 |
| `__tests__/components/recommendation-card.test.tsx` | Signal badge 颜色映射 + entry_mode badge |
| `__tests__/components/strategy-comparison.test.tsx` | 多策略对比表渲染 |
| `__tests__/components/trigger-list.test.tsx` | 状态色映射 + 取消操作 |
| `__tests__/lib/api.test.ts` | API client URL 构建 |
| `__tests__/lib/utils.test.ts` | 价格 / 百分比 / Delta Dollars 格式化 |

**测试工具**: Vitest + React Testing Library

---

## 7. 验收清单

- [ ] `npm run dev` 启动成功，`http://localhost:3000` 可访问
- [ ] Dashboard 6 + 3 个模块正常渲染（含 mock 数据）
- [ ] Positions 页 TanStack Table 支持排序 + 筛选
- [ ] Recommendation 详情页含策略对比表 + P&L 图
- [ ] Triggers 页展示 + 取消功能
- [ ] Flows 页 ETF 资金流 + Smart Money
- [ ] 所有颜色引用 `--aegis-*` 变量，无 hardcode hex/hsl
- [ ] 涨跌色使用 signal 色系
- [ ] 卡片无 box-shadow
- [ ] 动效时长 ≤ 200ms
- [ ] 1024px 断点可正常显示
- [ ] Lighthouse Performance Score ≥ 90
- [ ] 组件测试全绿

---

## 8. 不允许做的事

- 不实现后端 Agent 逻辑
- 不实现认证（私有部署，无需登录）
- 不实现 Light Mode（M3+）
- 不实现 Pipeline DAG 可视化（M3+，ReactFlow）
- 不实现 Thesis Cards 页（M3+）
- 不实现移动端适配（< 768px）
- 不使用 Font Awesome / Material Icons（仅 Lucide）
- 不使用 box-shadow 做层级区分
- 不使用 Glassmorphism / 多彩渐变
