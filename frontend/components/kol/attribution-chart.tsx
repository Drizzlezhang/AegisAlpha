"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { CHART_COLORS } from "@/lib/design-tokens";

interface Props {
  report: Record<string, unknown> | null;
}

export function AttributionChart({ report }: Props) {
  if (!report) {
    return (
      <div
        style={{
          padding: "32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No attribution data yet
      </div>
    );
  }

  // Extract data from report
  const sources = (report.sources as Array<Record<string, unknown>>) || [];
  if (!sources.length) {
    return (
      <div
        style={{
          padding: "32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No attribution data yet
      </div>
    );
  }

  const chartData = sources.map((s) => ({
    name: (s.name as string) || "Unknown",
    value: (s.total_calls as number) || 0,
  }));

  const COLORS = [
    CHART_COLORS.price,
    CHART_COLORS.iv,
    CHART_COLORS.positive,
    CHART_COLORS.negative,
    CHART_COLORS.volume,
  ];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          outerRadius={90}
          dataKey="value"
          // Remove label to avoid text overflow issues
          nameKey="name"
        >
          {chartData.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              fill={COLORS[index % COLORS.length]}
            />
          ))}
        </Pie>
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
          wrapperStyle={{ fontSize: "12px", color: "var(--aegis-text-secondary)" }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}