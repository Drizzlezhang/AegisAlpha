"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Recommendation, StrategyComparison, ScenarioPnl } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import SignalBadge from "@/components/charts/signal-badge";
import EntryModeBadge from "@/components/charts/entry-mode-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
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

interface DetailData extends Recommendation {
  strategy_comparisons: StrategyComparison[];
  scenario_pnls: ScenarioPnl[];
  smart_money: {
    direction_bias: string;
    top_unusual: { strike: number; expiry: string; option_type: string; premium: number; oi_change: number; volume: number }[];
    narrative: string;
  };
  fund_flow: {
    macro_liquidity: string;
    credit_appetite: string;
    sector_rotation: string;
    narrative: string;
  };
  debate: { bull: string; bear: string };
  stop_loss: { type: string; level: number; description: string };
}

const SCENARIO_COLORS: Record<string, string> = {
  target: CHART_COLORS.positive,
  sideways: CHART_COLORS.iv,
  stop_loss: CHART_COLORS.negative,
};

export default function RecommendationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [smartMoneyOpen, setSmartMoneyOpen] = useState(false);
  const [fundFlowOpen, setFundFlowOpen] = useState(false);

  const { data, error } = useSWR<DetailData>(
    `/recommendations/${id}`,
    fetcher
  );

  if (error) {
    return (
      <div className="p-4" style={{ color: "var(--aegis-signal-bear)" }}>
        Failed to load recommendation
      </div>
    );
  }
  if (!data) return <div className="p-4"><LoadingSkeleton lines={6} /></div>;

  // Transform scenario PnL data for Recharts
  const chartData = data.scenario_pnls[0]?.days.map((day, i) => {
    const point: Record<string, number | string> = { day: `D${day}` };
    data.scenario_pnls.forEach((s) => {
      point[s.scenario] = s.pnl_values[i];
    });
    return point;
  }) || [];

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div
        className="rounded-lg border p-4"
        style={{
          background: "var(--aegis-bg-surface)",
          borderColor: "var(--aegis-border-default)",
          borderLeftWidth: 2,
          borderLeftColor:
            data.direction === "bullish"
              ? "var(--aegis-signal-bull)"
              : data.direction === "bearish"
              ? "var(--aegis-signal-bear)"
              : "var(--aegis-signal-neutral)",
        }}
      >
        <div className="flex items-center gap-3 mb-2">
          <span className="text-xl font-bold" style={{ color: "var(--aegis-text-primary)" }}>
            {data.ticker}
          </span>
          <SignalBadge
            signal={
              data.direction === "bullish" ? "bull" : data.direction === "bearish" ? "bear" : "neutral"
            }
          />
          <EntryModeBadge mode={data.entry_mode} />
          <span
            className="text-xs px-2 py-0.5 rounded"
            style={{ color: "var(--aegis-text-primary)", background: "var(--aegis-bg-elevated)" }}
          >
            {data.strategy}
          </span>
          <div className="flex-1" />
          <span
            className="text-xs"
            style={{
              color:
                data.urgency === "high"
                  ? "var(--aegis-signal-bear)"
                  : data.urgency === "medium"
                  ? "var(--aegis-signal-neutral)"
                  : "var(--aegis-text-tertiary)",
            }}
          >
            {data.urgency.toUpperCase()}
          </span>
          <span
            className="text-sm font-bold tabular-nums"
            style={{
              color:
                data.score >= 7
                  ? "var(--aegis-signal-bull)"
                  : data.score >= 4
                  ? "var(--aegis-signal-neutral)"
                  : "var(--aegis-signal-bear)",
            }}
          >
            {data.score.toFixed(1)}
          </span>
        </div>
        <p className="text-sm" style={{ color: "var(--aegis-text-secondary)" }}>
          {data.rationale}
        </p>
      </div>

      {/* Strategy Comparison Table */}
      <div
        className="rounded-lg border p-4"
        style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
      >
        <h3 className="text-sm font-medium mb-3" style={{ color: "var(--aegis-text-primary)" }}>
          Strategy Comparison
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider" style={{ background: "var(--aegis-bg-elevated)" }}>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Strategy</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Cost</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Max Profit</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Max Loss</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Delta</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Theta</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Scenario</th>
              </tr>
            </thead>
            <tbody>
              {data.strategy_comparisons.map((s, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--aegis-border-subtle)" }}>
                  <td className="py-2 px-3 font-medium" style={{ color: "var(--aegis-text-primary)" }}>{s.strategy_name}</td>
                  <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-text-primary)" }}>${s.cost.toLocaleString()}</td>
                  <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-signal-bull)" }}>${s.max_profit.toLocaleString()}</td>
                  <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-signal-bear)" }}>${s.max_loss.toLocaleString()}</td>
                  <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-text-secondary)" }}>{s.delta.toFixed(2)}</td>
                  <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-text-secondary)" }}>{s.theta.toFixed(2)}</td>
                  <td className="py-2 px-3 text-xs" style={{ color: "var(--aegis-text-secondary)" }}>{s.scenario}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Scenario P&L Chart */}
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
            {data.scenario_pnls.map((s) => (
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

      {/* Smart Money Block (collapsible) */}
      <div
        className="rounded-lg border"
        style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
      >
        <button
          onClick={() => setSmartMoneyOpen(!smartMoneyOpen)}
          className="w-full flex items-center justify-between p-4 text-left"
        >
          <h3 className="text-sm font-medium" style={{ color: "var(--aegis-text-primary)" }}>
            Smart Money Analysis
          </h3>
          <span className="text-xs" style={{ color: "var(--aegis-text-tertiary)" }}>
            {smartMoneyOpen ? "▲" : "▼"}
          </span>
        </button>
        {smartMoneyOpen && (
          <div className="px-4 pb-4 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: "var(--aegis-text-tertiary)" }}>Bias:</span>
              <SignalBadge
                signal={
                  data.smart_money.direction_bias === "bullish" ? "bull" : data.smart_money.direction_bias === "bearish" ? "bear" : "neutral"
                }
              />
            </div>
            <div className="space-y-1">
              {data.smart_money.top_unusual.slice(0, 3).map((opt, i) => (
                <div key={i} className="flex items-center gap-2 text-xs py-1 px-2 rounded" style={{ background: "var(--aegis-bg-base)" }}>
                  <span style={{ color: opt.option_type === "call" ? "var(--aegis-signal-bull)" : "var(--aegis-signal-bear)" }}>
                    {opt.option_type.toUpperCase()} ${opt.strike}
                  </span>
                  <span style={{ color: "var(--aegis-text-tertiary)" }}>{opt.expiry.slice(0, 7)}</span>
                  <span className="tabular-nums ml-auto" style={{ color: "var(--aegis-text-secondary)" }}>
                    Vol: {opt.volume.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>
              {data.smart_money.narrative}
            </p>
          </div>
        )}
      </div>

      {/* Fund Flow Block (collapsible) */}
      <div
        className="rounded-lg border"
        style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
      >
        <button
          onClick={() => setFundFlowOpen(!fundFlowOpen)}
          className="w-full flex items-center justify-between p-4 text-left"
        >
          <h3 className="text-sm font-medium" style={{ color: "var(--aegis-text-primary)" }}>
            Fund Flow Analysis
          </h3>
          <span className="text-xs" style={{ color: "var(--aegis-text-tertiary)" }}>
            {fundFlowOpen ? "▲" : "▼"}
          </span>
        </button>
        {fundFlowOpen && (
          <div className="px-4 pb-4 space-y-2">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span style={{ color: "var(--aegis-text-tertiary)" }}>Macro Liquidity: </span>
                <span style={{ color: "var(--aegis-text-secondary)" }}>{data.fund_flow.macro_liquidity}</span>
              </div>
              <div>
                <span style={{ color: "var(--aegis-text-tertiary)" }}>Credit Appetite: </span>
                <span style={{ color: "var(--aegis-text-secondary)" }}>{data.fund_flow.credit_appetite}</span>
              </div>
              <div className="col-span-2">
                <span style={{ color: "var(--aegis-text-tertiary)" }}>Sector Rotation: </span>
                <span style={{ color: "var(--aegis-text-secondary)" }}>{data.fund_flow.sector_rotation}</span>
              </div>
            </div>
            <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>
              {data.fund_flow.narrative}
            </p>
          </div>
        )}
      </div>

      {/* Debate Summary */}
      <div
        className="rounded-lg border p-4"
        style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
      >
        <h3 className="text-sm font-medium mb-2" style={{ color: "var(--aegis-text-primary)" }}>
          Debate Summary
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 rounded" style={{ background: "var(--aegis-signal-bull-bg)" }}>
            <p className="text-xs font-medium mb-1" style={{ color: "var(--aegis-signal-bull)" }}>BULL CASE</p>
            <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>{data.debate.bull}</p>
          </div>
          <div className="p-3 rounded" style={{ background: "var(--aegis-signal-bear-bg)" }}>
            <p className="text-xs font-medium mb-1" style={{ color: "var(--aegis-signal-bear)" }}>BEAR CASE</p>
            <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>{data.debate.bear}</p>
          </div>
        </div>
      </div>

      {/* Stop Loss + Risk Gate */}
      <div className="grid grid-cols-2 gap-4">
        <div
          className="rounded-lg border p-4"
          style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
        >
          <h3 className="text-sm font-medium mb-2" style={{ color: "var(--aegis-text-primary)" }}>
            Stop Loss Plan
          </h3>
          <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>
            Type: <span style={{ color: "var(--aegis-text-primary)" }}>{data.stop_loss.type}</span>
          </p>
          <p className="text-xs" style={{ color: "var(--aegis-text-secondary)" }}>
            Level: <span className="font-semibold" style={{ color: "var(--aegis-signal-bear)" }}>${data.stop_loss.level}</span>
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--aegis-text-tertiary)" }}>
            {data.stop_loss.description}
          </p>
        </div>

        <div
          className="rounded-lg border p-4"
          style={{ background: "var(--aegis-bg-surface)", borderColor: "var(--aegis-border-default)" }}
        >
          <h3 className="text-sm font-medium mb-2" style={{ color: "var(--aegis-text-primary)" }}>
            Risk Gate
          </h3>
          <SignalBadge
            signal={data.risk_gate_status === "passed" ? "bull" : "blocked"}
            label={data.risk_gate_status.toUpperCase()}
          />
          {data.block_reason && (
            <p className="text-xs mt-2" style={{ color: "var(--aegis-text-secondary)" }}>
              {data.block_reason}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
