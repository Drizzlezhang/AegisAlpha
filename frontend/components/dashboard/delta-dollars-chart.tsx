"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { CHART_COLORS } from "@/lib/design-tokens";
import LoadingSkeleton from "@/components/ui/loading-skeleton";

interface DeltaDollarItem {
  ticker: string;
  delta_dollars: number;
  pct_of_nav: number;
}

export default function DeltaDollarsChart() {
  const { data, error } = useSWR<DeltaDollarItem[]>(
    "/portfolio/delta-dollars",
    fetcher
  );

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
        Delta Dollars
      </h3>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <XAxis
              dataKey="ticker"
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
                "Delta $",
              ]}
            />
            <Bar dataKey="delta_dollars" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={index}
                  fill={
                    entry.delta_dollars >= 0
                      ? CHART_COLORS.positive
                      : CHART_COLORS.negative
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
