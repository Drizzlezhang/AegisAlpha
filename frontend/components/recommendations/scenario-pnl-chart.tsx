"use client";

import type { ScenarioPnl } from "@/lib/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { CHART_COLORS } from "@/lib/design-tokens";

const SCENARIO_COLORS: Record<string, string> = {
  target: CHART_COLORS.positive,
  sideways: CHART_COLORS.iv,
  stop_loss: CHART_COLORS.negative,
};

interface ScenarioPnlChartProps {
  scenarios: ScenarioPnl[];
}

export default function ScenarioPnlChart({ scenarios }: ScenarioPnlChartProps) {
  const chartData = scenarios[0]?.days.map((day, i) => {
    const point: Record<string, number | string> = { day: `D${day}` };
    scenarios.forEach((s) => {
      point[s.scenario] = s.pnl_values[i];
    });
    return point;
  }) || [];

  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
    >
      <h3 className="text-sm font-medium mb-3" style={{ color: "var(--aegis-text-primary)" }}>
        Scenario P&L Simulation
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <XAxis
            dataKey="day"
            tick={{ fill: "var(--aegis-text-tertiary)", fontSize: 11 }}
            axisLine={{ stroke: "var(--aegis-border-subtle)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--aegis-text-tertiary)", fontSize: 11 }}
            axisLine={{ stroke: "var(--aegis-border-subtle)" }}
            tickLine={false}
            tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--aegis-bg-elevated)",
              border: "1px solid var(--aegis-border-default)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "var(--aegis-text-secondary)" }}
          />
          {scenarios.map((s) => (
            <Line
              key={s.scenario}
              type="monotone"
              dataKey={s.scenario}
              stroke={SCENARIO_COLORS[s.scenario] || CHART_COLORS.threshold}
              strokeWidth={2}
              dot={false}
              name={s.scenario.replace("_", " ")}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
