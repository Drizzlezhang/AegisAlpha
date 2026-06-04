"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { CHART_COLORS } from "@/lib/design-tokens";

const MOCK_DATA = [
  { date: "May 1", pnl: 0 },
  { date: "May 8", pnl: 2500 },
  { date: "May 15", pnl: 1800 },
  { date: "May 22", pnl: 4200 },
  { date: "May 29", pnl: 3250 },
  { date: "Jun 4", pnl: 5100 },
];

export default function PnlTrendChart() {
  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      <h3
        className="text-sm font-medium mb-3"
        style={{ color: "var(--aegis-text-primary)" }}
      >
        P&L Trend
      </h3>

      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={MOCK_DATA}>
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_COLORS.positive} stopOpacity={0.2} />
              <stop offset="100%" stopColor={CHART_COLORS.positive} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--aegis-text-tertiary)", fontSize: 11 }}
            axisLine={{ stroke: "var(--aegis-border-subtle)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--aegis-text-tertiary)", fontSize: 11 }}
            axisLine={{ stroke: "var(--aegis-border-subtle)" }}
            tickLine={false}
            tickFormatter={(v: number) =>
              v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v.toString()
            }
          />
          <Tooltip
            contentStyle={{
              background: "var(--aegis-bg-elevated)",
              border: "1px solid var(--aegis-border-default)",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [
              `$${Number(value).toLocaleString()}`,
              "P&L",
            ]}
          />
          <Area
            type="monotone"
            dataKey="pnl"
            stroke={CHART_COLORS.positive}
            strokeWidth={2}
            fill="url(#pnlGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
