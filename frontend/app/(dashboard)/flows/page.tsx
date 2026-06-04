"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { EtfFlow, SectorFlow, SmartMoneyData } from "@/lib/types";
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
import SignalBadge from "@/components/charts/signal-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";

function flowColor(intensity: number): string {
  if (intensity >= 0.6) return "hsl(145, 60%, 40%)";
  if (intensity >= 0.2) return "hsl(145, 40%, 30%)";
  if (intensity >= -0.2) return "var(--aegis-bg-elevated)";
  if (intensity >= -0.6) return "hsl(0, 40%, 30%)";
  return "hsl(0, 60%, 40%)";
}

export default function FlowsPage() {
  const [tab, setTab] = useState<"etf" | "smart">("etf");

  const { data: etfData, error: etfError } = useSWR<EtfFlow[]>(
    "/flows/etf",
    fetcher
  );
  const { data: sectorData } = useSWR<SectorFlow[]>(
    "/flows/sector",
    fetcher
  );
  const { data: smartData, error: smartError } = useSWR<SmartMoneyData>(
    "/flows/smart-money/QQQ",
    fetcher
  );

  return (
    <div className="p-4">
      <h2
        className="text-lg font-semibold mb-4"
        style={{ color: "var(--aegis-text-primary)" }}
      >
        Fund Flows & Smart Money
      </h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {(["etf", "smart"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-3 py-1.5 text-xs rounded transition-colors duration-150"
            style={{
              color:
                tab === t
                  ? "var(--aegis-text-primary)"
                  : "var(--aegis-text-secondary)",
              background:
                tab === t ? "var(--aegis-bg-elevated)" : "transparent",
            }}
          >
            {t === "etf" ? "ETF Flows" : "Smart Money"}
          </button>
        ))}
      </div>

      {/* ETF Flows Tab */}
      {tab === "etf" && (
        <div className="space-y-4">
          {etfError && (
            <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load ETF flows</p>
          )}
          {!etfData && !etfError && <LoadingSkeleton lines={4} />}

          {etfData && (
            <div
              className="rounded-lg border p-4"
              style={{
                background: "var(--aegis-bg-surface)",
                borderColor: "var(--aegis-border-default)",
              }}
            >
              <h3 className="text-sm font-medium mb-3" style={{ color: "var(--aegis-text-primary)" }}>
                ETF 7-Day Flows
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={etfData}>
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
                      v >= 1_000_000_000
                        ? `${(v / 1_000_000_000).toFixed(1)}B`
                        : `${(v / 1_000_000).toFixed(0)}M`
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
                      `$${(Number(value) / 1_000_000).toFixed(0)}M`,
                      "Flow",
                    ]}
                  />
                  <Bar dataKey="flow_7d" radius={[4, 4, 0, 0]}>
                    {etfData.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={
                          entry.flow_7d >= 0
                            ? CHART_COLORS.positive
                            : CHART_COLORS.negative
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {sectorData && (
            <div
              className="rounded-lg border p-4"
              style={{
                background: "var(--aegis-bg-surface)",
                borderColor: "var(--aegis-border-default)",
              }}
            >
              <h3 className="text-sm font-medium mb-3" style={{ color: "var(--aegis-text-primary)" }}>
                Sector Heatmap
              </h3>
              <div className="grid grid-cols-2 gap-1.5">
                {sectorData.map((sector) => (
                  <div
                    key={sector.sector}
                    className="flex items-center justify-between p-2 rounded text-xs"
                    style={{ background: flowColor(sector.intensity) }}
                  >
                    <span
                      style={{
                        color:
                          Math.abs(sector.intensity) >= 0.4
                            ? "var(--aegis-text-primary)"
                            : "var(--aegis-text-secondary)",
                      }}
                    >
                      {sector.sector}
                    </span>
                    <span
                      className="tabular-nums"
                      style={{
                        color:
                          sector.flow_7d >= 0
                            ? "var(--aegis-signal-bull)"
                            : "var(--aegis-signal-bear)",
                      }}
                    >
                      {sector.flow_7d >= 0 ? "+" : ""}
                      {(sector.flow_7d / 1_000_000).toFixed(0)}M
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Smart Money Tab */}
      {tab === "smart" && (
        <div className="space-y-4">
          {smartError && (
            <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load Smart Money data</p>
          )}
          {!smartData && !smartError && <LoadingSkeleton lines={4} />}

          {smartData && (
            <div
              className="rounded-lg border p-4"
              style={{
                background: "var(--aegis-bg-surface)",
                borderColor: "var(--aegis-border-default)",
              }}
            >
              <div className="flex items-center gap-3 mb-3">
                <h3 className="text-sm font-medium" style={{ color: "var(--aegis-text-primary)" }}>
                  {smartData.ticker} Smart Money
                </h3>
                <SignalBadge
                  signal={
                    smartData.direction_bias === "bullish"
                      ? "bull"
                      : smartData.direction_bias === "bearish"
                      ? "bear"
                      : "neutral"
                  }
                />
                <span
                  className="text-xs tabular-nums ml-auto"
                  style={{ color: "var(--aegis-text-secondary)" }}
                >
                  Score: {smartData.smart_money_score}
                </span>
              </div>

              <div className="space-y-1 mb-3">
                {smartData.unusual_options.map((opt, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs py-1.5 px-2 rounded"
                    style={{ background: "var(--aegis-bg-base)" }}
                  >
                    <span
                      style={{
                        color:
                          opt.option_type === "call"
                            ? "var(--aegis-signal-bull)"
                            : "var(--aegis-signal-bear)",
                      }}
                    >
                      {opt.option_type.toUpperCase()}
                    </span>
                    <span style={{ color: "var(--aegis-text-secondary)" }}>
                      ${opt.strike}
                    </span>
                    <span style={{ color: "var(--aegis-text-tertiary)" }}>
                      {opt.expiry.slice(0, 7)}
                    </span>
                    <span className="tabular-nums" style={{ color: "var(--aegis-text-secondary)" }}>
                      Prem: ${(opt.premium / 1_000_000).toFixed(1)}M
                    </span>
                    <span
                      className="tabular-nums ml-auto"
                      style={{
                        color:
                          opt.oi_change >= 0
                            ? "var(--aegis-signal-bull)"
                            : "var(--aegis-signal-bear)",
                      }}
                    >
                      OI {opt.oi_change >= 0 ? "+" : ""}
                      {opt.oi_change.toLocaleString()}
                    </span>
                    <span className="tabular-nums" style={{ color: "var(--aegis-text-tertiary)" }}>
                      Vol: {opt.volume.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>

              <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>
                {smartData.narrative}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
