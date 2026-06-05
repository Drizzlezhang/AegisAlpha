"use client";

import type { StrategyComparison } from "@/lib/types";

interface StrategyComparisonTableProps {
  strategies: StrategyComparison[];
}

export default function StrategyComparisonTable({ strategies }: StrategyComparisonTableProps) {
  return (
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
            {strategies.map((s, i) => (
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
  );
}
