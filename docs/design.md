# Aegis 2.0 Design System

> **版本**：v1.0（与 PRD v1.2 / tech-arch v1.2 / AGENTS.md v1.2 同步发布）
> **位置**：`docs/aegis-2.0-design-system.md`
> **约束**：前端所有页面、组件、图表必须遵循本文件定义的设计规范。修改需发起独立 PR + owner 评审。

---

## 1. 设计理念

### 1.1 定位

Aegis 2.0 前端是**个人交易决策仪表盘**，用户在以下场景使用：

- 盘前（美东 5:00-9:30 / 北京 17:00-21:30）：浏览推荐、确认建仓计划
- 盘后（美东 16:00-20:00 / 北京 4:00-8:00）：Review 持仓、Thesis Card 打分、查看回顾
- 周末：查看周报摘要、因子权重变化、历史 Debate 记录

### 1.2 设计原则

| 优先级 | 原则 | 说明 |
|---|---|---|
| P0 | **信息密度优先** | 一屏内展示尽可能多的有效信息，不浪费空间在装饰上 |
| P1 | **信号可辨识** | 看多/看空/中性/拦截 一眼区分，不靠文字靠色彩编码 |
| P2 | **视觉疲劳低** | 深色主体 + 低对比度背景 + 高对比度关键数据 |
| P3 | **操作零门槛** | 无复杂交互，hover 看详情，click 进详情页，无 modal 嵌套 |
| P4 | **一致性** | 所有页面同一视觉语言，组件复用率 > 80% |

### 1.3 设计关键词

`Dark-first` · `金融终端` · `数据驱动` · `克制品牌色` · `卡片化模块` · `零装饰`

---

## 2. 色彩系统

### 2.1 基础色板（CSS Variables）

```css
:root {
  /* ─── 背景层级 ─── */
  --aegis-bg-base:       hsl(220, 20%, 8%);    /* 最底层背景 */
  --aegis-bg-surface:    hsl(220, 15%, 12%);   /* 卡片/面板背景 */
  --aegis-bg-elevated:   hsl(220, 12%, 16%);   /* 悬浮/展开面板 */
  --aegis-bg-overlay:    hsl(220, 15%, 10%);   /* Overlay 蒙层 */

  /* ─── 边框 ─── */
  --aegis-border-default: hsl(220, 15%, 20%);  /* 默认分割线 */
  --aegis-border-subtle:  hsl(220, 12%, 16%);  /* 极淡分割 */
  --aegis-border-focus:   hsl(210, 100%, 56%); /* Focus ring */

  /* ─── 文字 ─── */
  --aegis-text-primary:   hsl(0, 0%, 92%);     /* 主文字（不用纯白） */
  --aegis-text-secondary: hsl(0, 0%, 60%);     /* 次要文字 */
  --aegis-text-tertiary:  hsl(0, 0%, 42%);     /* Label / 占位符 */
  --aegis-text-disabled:  hsl(0, 0%, 30%);     /* 禁用态 */

  /* ─── 品牌色 ─── */
  --aegis-brand:          hsl(210, 100%, 56%); /* 科技蓝：Active / 选中 / CTA */
  --aegis-brand-hover:    hsl(210, 100%, 62%);
  --aegis-brand-muted:    hsl(210, 60%, 25%);  /* 品牌色背景态 */

  /* ─── 信号色（核心） ─── */
  --aegis-signal-bull:    hsl(145, 65%, 50%);  /* 看多 / Buy / 健康 */
  --aegis-signal-bull-bg: hsl(145, 40%, 12%);  /* 看多背景 */
  --aegis-signal-bear:    hsl(0, 75%, 60%);    /* 看空 / Risk / 预警 */
  --aegis-signal-bear-bg: hsl(0, 50%, 12%);    /* 看空背景 */
  --aegis-signal-neutral: hsl(45, 80%, 55%);   /* Hold / 等待 / Pending */
  --aegis-signal-neutral-bg: hsl(45, 50%, 12%);
  --aegis-signal-blocked: hsl(280, 50%, 60%);  /* 被 Risk Gate 拦截 */
  --aegis-signal-blocked-bg: hsl(280, 30%, 12%);

  /* ─── 语义色 ─── */
  --aegis-success:        hsl(145, 65%, 50%);
  --aegis-warning:        hsl(45, 80%, 55%);
  --aegis-error:          hsl(0, 75%, 60%);
  --aegis-info:           hsl(210, 100%, 56%);
}
```

### 2.2 信号色使用规则

| 场景 | 前景色 | 背景色 | 用法示例 |
|---|---|---|---|
| Bullish / Buy / Score ≥ 7 | `--aegis-signal-bull` | `--aegis-signal-bull-bg` | 推荐卡片左边框、Score badge |
| Bearish / Sell / Score ≤ 3 | `--aegis-signal-bear` | `--aegis-signal-bear-bg` | 止损预警、Risk 标签 |
| Neutral / Hold / 4 ≤ Score ≤ 6 | `--aegis-signal-neutral` | `--aegis-signal-neutral-bg` | Pending Trigger、等待确认 |
| Blocked by Risk Gate | `--aegis-signal-blocked` | `--aegis-signal-blocked-bg` | 被拦截推荐卡片 |
| Active / Selected / CTA | `--aegis-brand` | `--aegis-brand-muted` | 当前选中 Tab、按钮 |

### 2.3 Light Mode（预留，M3+）

- 当前 M1-M2 **仅实现 Dark Mode**
- Light Mode 色板预留变量命名空间：`--aegis-light-*`
- 切换机制：`<html data-theme="dark|light">`，CSS variables swap
- Light Mode 设计时参考 Linear Light 主题色调

---

## 3. 排版系统

### 3.1 字体

```css
:root {
  --aegis-font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --aegis-font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
}
```

| 用途 | 字体 | 特性 |
|---|---|---|
| 正文 / 标题 / Label | Inter | `font-feature-settings: 'cv01', 'cv02'`（区分 I/l/1） |
| 数字 / 价格 / 百分比 | Inter (tabular-nums) | `font-variant-numeric: tabular-nums` — 对齐列 |
| 代码 / Agent 名 / 技术标识 | JetBrains Mono | 等宽，区分度高 |

### 3.2 字号体系（基于 4px grid）

| Token | Size | Line Height | Weight | 用途 |
|---|---|---|---|---|
| `text-xs` | 11px | 16px | 400 | 时间戳、辅助标注 |
| `text-sm` | 13px | 20px | 400 | 次要信息、表格内容 |
| `text-base` | 14px | 22px | 400 | 正文默认 |
| `text-md` | 15px | 24px | 500 | 卡片标题、重要 Label |
| `text-lg` | 18px | 28px | 600 | 区块标题 |
| `text-xl` | 22px | 30px | 700 | 页面标题 |
| `text-2xl` | 28px | 36px | 700 | 数字大屏（Portfolio 总值） |
| `text-3xl` | 36px | 44px | 800 | Hero 数字（仅 Dashboard 顶部） |

### 3.3 间距体系

基于 **4px** 基线网格（Tailwind 默认 `spacing` 单位）：

| Token | 值 | 典型用途 |
|---|---|---|
| `space-1` | 4px | 图标与文字间距 |
| `space-2` | 8px | 紧凑元素内边距 |
| `space-3` | 12px | 卡片内边距（小） |
| `space-4` | 16px | 卡片内边距（标准） |
| `space-5` | 20px | 卡片间距 |
| `space-6` | 24px | 区块间距 |
| `space-8` | 32px | 大区块分隔 |
| `space-10` | 40px | 页面顶部 / 底部留白 |

---

## 4. 布局系统

### 4.1 整体架构

```
┌──────────────────────────────────────────────────────────┐
│  Top Bar (48px): Logo + Nav Tabs + Pipeline Status + Time│
├────────┬─────────────────────────────────┬───────────────┤
│        │                                 │               │
│ Left   │       Main Content Area         │    Right      │
│ Panel  │       (flex-1, scrollable)      │    Panel      │
│ (280px)│                                 │   (320px)     │
│        │                                 │               │
│ - Holds│  Cards / Charts / Tables        │ - Signal Log  │
│ - Watch│                                 │ - Agent Runs  │
│ - Thesis│                                │ - Triggers    │
│        │                                 │               │
├────────┴─────────────────────────────────┴───────────────┤
│  Status Bar (28px): Last Pipeline Run + Errors + Version │
└──────────────────────────────────────────────────────────┘
```

### 4.2 响应式断点

| 断点 | 宽度 | 布局 | 目标设备 |
|---|---|---|---|
| `desktop` | ≥ 1440px | 三列（Left 280 + Main + Right 320） | Mac 外接屏 |
| `laptop` | 1024–1439px | 三列压缩（Left 240 + Main + Right 280） | MacBook |
| `tablet-landscape` | 768–1023px | 两列（Left 可折叠 + Main；Right 收纳为抽屉） | iPad 横屏 |
| `< 768px` | — | **不支持**（PRD 明确不做移动端） | — |

### 4.3 Grid 约定

- Main Content 内部使用 **CSS Grid**：`grid-template-columns: repeat(auto-fit, minmax(320px, 1fr))`
- 卡片自动填充，保证信息密度
- Dashboard 首页固定 2×3 grid（Portfolio Summary / 推荐摘要 / 持仓快照 / Delta Dollars / Greeks / 到期日历）

---

## 5. 组件规范

### 5.1 卡片（Card）

```
┌─ 2px left-border (signal color) ──────────────────┐
│  [space-4 padding]                                 │
│  Title (text-md, 500)          Timestamp (text-xs) │
│  ─────────────────────────────────────────────     │
│  Content area                                      │
│  ...                                               │
│  Footer: Tags / Score Badge / Action               │
└────────────────────────────────────────────────────┘
```

| 属性 | 值 |
|---|---|
| 背景 | `--aegis-bg-surface` |
| 圆角 | `8px` |
| 边框 | `1px solid var(--aegis-border-default)` |
| 左侧信号条 | `2px solid var(--aegis-signal-*)` |
| 阴影 | **无**（用色差区分层级） |
| Hover | 背景过渡到 `--aegis-bg-elevated`，`transition: 150ms ease` |

### 5.2 Badge / Tag

| 变体 | 前景 | 背景 | 用途 |
|---|---|---|---|
| Bull | `--aegis-signal-bull` | `--aegis-signal-bull-bg` | Buy / Bullish / Score 7+ |
| Bear | `--aegis-signal-bear` | `--aegis-signal-bear-bg` | Sell / Bearish / Score 3- |
| Neutral | `--aegis-signal-neutral` | `--aegis-signal-neutral-bg` | Hold / Pending |
| Blocked | `--aegis-signal-blocked` | `--aegis-signal-blocked-bg` | Risk Gate 拦截 |
| Info | `--aegis-brand` | `--aegis-brand-muted` | Agent 名称 / Tag |

- 圆角：`4px`
- 内边距：`2px 8px`
- 字号：`text-xs`，`font-weight: 500`

### 5.3 表格（TanStack Table）

- 表头：`--aegis-bg-elevated` 背景,`text-xs` 大写标签,`letter-spacing: 0.05em`
- 行高：`36px`（紧凑）/ `44px`（标准）
- 斑马纹：奇数行 `--aegis-bg-surface`，偶数行 `--aegis-bg-base`
- 数字列：右对齐 + `tabular-nums`
- 涨跌色：正数用 `--aegis-signal-bull`，负数用 `--aegis-signal-bear`
- 排序图标：`▲▼` 单色，active 态用 `--aegis-brand`

### 5.4 图表（Recharts）

| 属性 | 规范 |
|---|---|
| 背景 | 透明（继承卡片背景） |
| 网格线 | `stroke: var(--aegis-border-subtle)`，`opacity: 0.3` |
| 轴标签 | `text-xs`，`fill: var(--aegis-text-tertiary)` |
| 线条宽度 | `2px` |
| 面积填充 | 对应线条色 `opacity: 0.1` |
| Tooltip | `--aegis-bg-elevated` 背景，`8px` 圆角，无箭头 |
| 图例 | 卡片底部行内 dot + label，不用外置图例框 |

**配色映射**:

| 数据含义 | 颜色 |
|---|---|
| 价格 / NAV | `--aegis-brand` |
| 涨 / 正 Delta | `--aegis-signal-bull` |
| 跌 / 负 Delta | `--aegis-signal-bear` |
| Volume / Flow | `hsl(200, 60%, 50%)` — 青蓝 |
| IV / Volatility | `hsl(35, 80%, 55%)` — 橙 |
| 基准线 / Threshold | `--aegis-text-tertiary`，`strokeDasharray: "4 4"` |

### 5.5 DAG 可视化（ReactFlow）

- **节点**: 圆角矩形 `8px`,内部 Agent 名 + 状态 icon
  - 背景:`--aegis-bg-surface`
  - 边框:`2px solid` + 状态色(running = brand, done = bull, error = bear, skipped = tertiary)
  - 尺寸:`160×48px`
- **连线**: 贝塞尔曲线,`stroke-width: 1.5px`,`--aegis-border-default`
- **布局方向**: 从左到右（水平泳道式,与 PRD Pipeline 描述一致）
- **分组**: Full Pipeline 和 Lightweight Pipeline 用虚线框分组标注
- **交互**: Hover 节点高亮上下游;Click 展开侧面板显示 Agent 详情 + 耗时 + token

### 5.6 按钮

| 变体 | 背景 | 文字 | 用途 |
|---|---|---|---|
| Primary | `--aegis-brand` | white | 主 CTA（如「提交打分」） |
| Secondary | transparent | `--aegis-brand` | 次要操作 |
| Ghost | transparent | `--aegis-text-secondary` | 辅助操作（如「展开」） |
| Danger | `--aegis-signal-bear` | white | 危险操作（如「清空」） |

- 圆角：`6px`
- 高度：`32px`（sm）/ `36px`（md）/ `40px`（lg）
- 禁用态：`opacity: 0.4`，`cursor: not-allowed`
- 动效：`transition: background 150ms ease`

### 5.7 输入框 / Select

- 背景：`--aegis-bg-base`
- 边框：`1px solid var(--aegis-border-default)`
- Focus：`border-color: var(--aegis-brand)` + `box-shadow: 0 0 0 2px var(--aegis-brand-muted)`
- 高度：`36px`
- 圆角：`6px`
- Placeholder：`--aegis-text-tertiary`

---

## 6. 动效与交互

### 6.1 原则

- **克制**：仅在状态转换时使用动效，不用于装饰
- **快速**：所有 transition ≤ 200ms
- **一致**：统一使用 `ease` timing function

### 6.2 动效清单

| 场景 | 动效 | 时长 |
|---|---|---|
| Hover 色变 | background-color transition | 150ms |
| 面板展开/折叠 | height + opacity | 200ms |
| 卡片入场 | translateY(8px) → 0 + opacity | 200ms, stagger 50ms |
| Tooltip 显示 | opacity 0→1 | 100ms, delay 200ms |
| 骨架屏 | pulse animation (shimmer) | 1.5s infinite |
| 图表数据更新 | Recharts 内置 animationDuration | 300ms |

### 6.3 禁止的动效

- ❌ 弹跳 (bounce)
- ❌ 旋转 (rotate / spin)，loading 除外
- ❌ 缩放 (scale > 1.02)
- ❌ 模糊 (backdrop-filter: blur) — 性能开销大
- ❌ 页面级 transition (page route animation)

---

## 7. 图标系统

- 使用 **Lucide Icons**（shadcn/ui 默认搭配）
- 尺寸：`16px`（inline）/ `20px`（button 内）/ `24px`（导航）
- 颜色：继承文字色 `currentColor`
- **禁止**：Font Awesome / Material Icons / 自绘 SVG icon（保持一致性）

---

## 8. 页面规范

### 8.1 Dashboard（首页）

```
┌─────────────────────────────────────────────────────────┐
│ Portfolio Summary Card (full width)                      │
│ ┌──────────┬──────────┬──────────┬──────────┐          │
│ │ 总 NAV    │ 日 P&L   │ Delta $  │ 现金比    │          │
│ │ $XXX,XXX │ +$X,XXX  │ $XX,XXX  │  XX%     │          │
│ └──────────┴──────────┴──────────┴──────────┘          │
├─────────────────────────┬───────────────────────────────┤
│ 推荐摘要 (盘前/盘后 tab) │ 持仓快照 (Table ↔ Treemap)   │
│                         │                               │
├─────────────────────────┼───────────────────────────────┤
│ Delta Dollars 柱状图     │ Greeks 汇总表                  │
│                         │                               │
├─────────────────────────┼───────────────────────────────┤
│ 到期日历 (热力图)        │ P&L 趋势图 (不叠加基准)        │
│                         │                               │
└─────────────────────────┴───────────────────────────────┘
```

### 8.2 Thesis Cards 页

- 左侧列表 + 右侧详情 (master-detail)
- 列表卡片含：标的、方向、entry_mode badge、Score(双维度)、状态
- 详情页：完整 Thesis 内容 + 打分面板 + 历史记录时间线

### 8.3 Pipeline DAG 页

- 全宽 ReactFlow 画布
- 顶部 Tab 切换 Full / Lightweight
- 右侧抽屉：点击节点后展示 Agent 详情

### 8.4 System Status 页（独立页面）

- Agent 运行状态表
- Tool 健康状态（Circuit Breaker 三态）
- Pipeline 历史 + 耗时
- 错误日志流

---

## 9. 对标参考

| 产品 | 借鉴维度 |
|---|---|
| **Linear** | 极简暗色 UI、键盘优先交互、信息密度、卡片层级 |
| **Bloomberg Terminal** | 色彩编码信号系统、数字对齐、数据第一无装饰 |
| **TradingView (Dark)** | 图表配色、面板分割、悬浮 Tooltip |
| **Raycast** | 卡片圆角克制、品牌色点缀比例、快速响应感 |
| **Vercel Dashboard** | 状态指示器设计、部署时间线 |

### 不采用的风格

| 风格 | 排除原因 |
|---|---|
| Light Mode 为主 | 盘前 5-6 点/盘后深夜使用,深色更护眼 |
| Glassmorphism | 半透明模糊性能开销大,iPad 帧率问题 |
| 多彩渐变 (Vercel Marketing 风) | 装饰性过强,牺牲信息密度 |
| Material Design 3 | 阴影层级过多,偏消费产品风格 |
| Neumorphism | 可读性差,对比度不足,不适合数据密集型 |

---

## 10. 工程落地

### 10.1 Tailwind 配置

```typescript
// tailwind.config.ts
import type { Config } from 'tailwindcss'

export default {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        aegis: {
          bg: {
            base: 'hsl(220, 20%, 8%)',
            surface: 'hsl(220, 15%, 12%)',
            elevated: 'hsl(220, 12%, 16%)',
            overlay: 'hsl(220, 15%, 10%)',
          },
          border: {
            DEFAULT: 'hsl(220, 15%, 20%)',
            subtle: 'hsl(220, 12%, 16%)',
            focus: 'hsl(210, 100%, 56%)',
          },
          text: {
            primary: 'hsl(0, 0%, 92%)',
            secondary: 'hsl(0, 0%, 60%)',
            tertiary: 'hsl(0, 0%, 42%)',
            disabled: 'hsl(0, 0%, 30%)',
          },
          brand: {
            DEFAULT: 'hsl(210, 100%, 56%)',
            hover: 'hsl(210, 100%, 62%)',
            muted: 'hsl(210, 60%, 25%)',
          },
          signal: {
            bull: 'hsl(145, 65%, 50%)',
            'bull-bg': 'hsl(145, 40%, 12%)',
            bear: 'hsl(0, 75%, 60%)',
            'bear-bg': 'hsl(0, 50%, 12%)',
            neutral: 'hsl(45, 80%, 55%)',
            'neutral-bg': 'hsl(45, 50%, 12%)',
            blocked: 'hsl(280, 50%, 60%)',
            'blocked-bg': 'hsl(280, 30%, 12%)',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        card: '8px',
        badge: '4px',
        button: '6px',
      },
    },
  },
} satisfies Config
```

### 10.2 shadcn/ui 主题覆盖

在 `frontend/app/globals.css` 中覆盖 shadcn 默认 CSS variables：

```css
@layer base {
  [data-theme="dark"] {
    --background: 220 20% 8%;
    --foreground: 0 0% 92%;
    --card: 220 15% 12%;
    --card-foreground: 0 0% 92%;
    --popover: 220 12% 16%;
    --popover-foreground: 0 0% 92%;
    --primary: 210 100% 56%;
    --primary-foreground: 0 0% 100%;
    --secondary: 220 15% 20%;
    --secondary-foreground: 0 0% 92%;
    --muted: 220 12% 16%;
    --muted-foreground: 0 0% 55%;
    --accent: 220 12% 16%;
    --accent-foreground: 0 0% 92%;
    --destructive: 0 75% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 220 15% 20%;
    --input: 220 15% 20%;
    --ring: 210 100% 56%;
    --radius: 0.5rem;
  }
}
```

### 10.3 Design Token 文件

```typescript
// frontend/lib/design-tokens.ts
export const SIGNAL_COLORS = {
  bull:    'var(--aegis-signal-bull)',
  bear:    'var(--aegis-signal-bear)',
  neutral: 'var(--aegis-signal-neutral)',
  blocked: 'var(--aegis-signal-blocked)',
} as const

export const CHART_COLORS = {
  price:      'hsl(210, 100%, 56%)',
  volume:     'hsl(200, 60%, 50%)',
  iv:         'hsl(35, 80%, 55%)',
  positive:   'hsl(145, 65%, 50%)',
  negative:   'hsl(0, 75%, 60%)',
  threshold:  'hsl(0, 0%, 42%)',
} as const

export const AGENT_STATUS_COLORS = {
  running: 'var(--aegis-brand)',
  done:    'var(--aegis-signal-bull)',
  error:   'var(--aegis-signal-bear)',
  skipped: 'var(--aegis-text-tertiary)',
} as const
```

### 10.4 文件位置规范

| 文件类型 | 位置 |
|---|---|
| Design Token | `frontend/lib/design-tokens.ts` |
| 全局样式 | `frontend/app/globals.css` |
| Tailwind 配置 | `frontend/tailwind.config.ts` |
| shadcn 组件 | `frontend/components/ui/` |
| 业务组件 | `frontend/components/{domain}/` |
| 图表组件 | `frontend/components/charts/` |
| 页面 | `frontend/app/(dashboard)/{page}/page.tsx` |

---

## 11. 质量检查清单

每个前端 PR 提交前自查：

- [ ] 所有颜色引用 `--aegis-*` 变量或 `aegis-*` Tailwind class，**禁止 hardcode hex/hsl**
- [ ] 数字列使用 `tabular-nums`
- [ ] 涨跌色使用 signal 色系，不自定义绿红
- [ ] 卡片无 box-shadow，用 border + 背景色差做层级
- [ ] 动效时长 ≤ 200ms
- [ ] 信号状态至少有 bull/bear/neutral/blocked 四态覆盖
- [ ] iPad 横屏（1024px）可正常显示所有关键信息
- [ ] 无 `font-size` 硬编码，统一走 Tailwind text-* utility
- [ ] 图表 tooltip / legend 色彩与数据含义一致
- [ ] Lighthouse Performance Score ≥ 90（Dark Mode）

---

## 12. 版本演进计划

| 阶段 | 设计目标 |
|---|---|
| M1-M2 | 落地 Dark Mode + 核心组件库 + Dashboard + Thesis Card 页 |
| M3 | 补充 DAG 可视化 + System Status + 图表完善 |
| M4 | 可选 Light Mode + 微交互打磨 + 组件文档 (Storybook) |

---

**最后约束**：前端开发过程中，视觉风格以本文件为唯一权威。如与第三方库默认样式冲突，以本文件为准覆盖。如需扩展新组件样式，必须先在本文件补充规范再实现代码。
