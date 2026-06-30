"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CHART_COLORS } from "@/lib/design-tokens";
import { WeightHistoryItem } from "@/lib/api/memory";
import { formatDate } from "@/lib/utils";

interface Props {
  history: WeightHistoryItem[];
}

export function WeightTrendChart({ history }: Props) {
  if (!history.length) {
    return (
      <div
        style={{
          padding: "48px 32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No weight data yet
      </div>
    );
  }

  // Group by factor_name, each entry has date + weight
  const factorNames = [...new Set(history.map((h) => h.factor_name))];
  const dates = [
    ...new Set(history.map((h) => h.updated_at).filter(Boolean) as string[]),
  ].sort();

  // Build chart data: for each date, collect all factor weights
  const chartData = dates.map((date) => {
    const point: Record<string, string | number | null> = { date: formatDate(date) };
    for (const fn of factorNames) {
      const entry = history.find(
        (h) => h.factor_name === fn && h.updated_at === date
      );
      point[fn] = entry ? entry.weight : null;
    }
    return point;
  });

  const COLORS = [
    CHART_COLORS.price,
    CHART_COLORS.iv,
    CHART_COLORS.positive,
    CHART_COLORS.negative,
    CHART_COLORS.volume,
    "hsl(280, 50%, 60%)",
    "hsl(200, 60%, 55%)",
    "hsl(35, 80%, 55%)",
  ];

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartData}>
        <CartesianGrid
          stroke="var(--aegis-border-default)"
          strokeDasharray="3 3"
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "var(--aegis-text-tertiary)" }}
          axisLine={{ stroke: "var(--aegis-border-default)" }}
          tickLine={false}
        />
        <YAxis
          domain={[0.2, 3.0]}
          tick={{ fontSize: 11, fill: "var(--aegis-text-tertiary)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--aegis-bg-surface)",
            border: "1px solid var(--aegis-border-default)",
            borderRadius: "8px",
            fontSize: "13px",
          }}
          labelStyle={{ color: "var(--aegis-text-primary)" }}
        />
        <Legend
          wrapperStyle={{
            fontSize: "12px",
            color: "var(--aegis-text-secondary)",
          }}
        />
        {factorNames.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
            animationDuration={200}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}