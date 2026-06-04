"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Position } from "@/lib/types";
import { formatPrice, formatPercent } from "@/lib/utils";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
import EmptyState from "@/components/ui/empty-state";

const MOCK_POSITIONS: Position[] = [
  {
    id: 1, account: "IBKR", ticker: "QQQ", pos_type: "call",
    quantity: 5, avg_cost: 2850, current_price: 3200, strike: 500,
    expiry: "2027-06-18", option_type: "call", delta: 0.72, gamma: 0.008,
    theta: -0.15, vega: 0.85, iv: 22.5, delta_dollars: 125000,
    unrealized_pnl: 1750, unrealized_pnl_pct: 12.3,
    entry_mode: "active_left", grade: "A", health_score: 85, dte: 380,
  },
  {
    id: 2, account: "IBKR", ticker: "SPY", pos_type: "stock",
    quantity: 100, avg_cost: 585, current_price: 592, delta: 1.0,
    gamma: 0, theta: 0, vega: 0, iv: 0, delta_dollars: 59200,
    unrealized_pnl: 700, unrealized_pnl_pct: 1.2,
    entry_mode: "passive", grade: "B", health_score: 72, dte: 0,
  },
  {
    id: 3, account: "IBKR", ticker: "GLD", pos_type: "call",
    quantity: 3, avg_cost: 1200, current_price: 1450, strike: 230,
    expiry: "2027-03-19", option_type: "call", delta: 0.65, gamma: 0.006,
    theta: -0.10, vega: 0.55, iv: 18.2, delta_dollars: 17200,
    unrealized_pnl: 750, unrealized_pnl_pct: 20.8,
    entry_mode: "active_right", grade: "A", health_score: 90, dte: 290,
  },
];

export default function PositionSnapshot() {
  const [view, setView] = useState<"table" | "treemap">("table");
  const { data, error } = useSWR<Position[]>("/positions", fetcher, {
    fallbackData: MOCK_POSITIONS,
  });

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        background: "var(--aegis-bg-surface)",
        borderColor: "var(--aegis-border-default)",
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3
          className="text-sm font-medium"
          style={{ color: "var(--aegis-text-primary)" }}
        >
          Positions
        </h3>
        <div className="flex gap-1">
          {(["table", "treemap"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-2 py-0.5 text-xs rounded transition-colors duration-150"
              style={{
                color:
                  view === v
                    ? "var(--aegis-text-primary)"
                    : "var(--aegis-text-secondary)",
                background:
                  view === v
                    ? "var(--aegis-bg-elevated)"
                    : "transparent",
              }}
            >
              {v === "table" ? "Table" : "Treemap"}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load</p>
      )}
      {!data && !error && <LoadingSkeleton lines={3} />}
      {data && data.length === 0 && <EmptyState title="No positions" />}
      {data && data.length > 0 && (
        <div className="space-y-1">
          {data.map((pos) => (
            <div
              key={pos.id}
              className="flex items-center gap-3 py-1.5 px-2 rounded text-sm"
              style={{ background: "var(--aegis-bg-base)" }}
            >
              <span
                className="font-semibold w-12"
                style={{ color: "var(--aegis-text-primary)" }}
              >
                {pos.ticker}
              </span>
              <span
                className="text-xs w-16"
                style={{ color: "var(--aegis-text-secondary)" }}
              >
                {pos.pos_type.toUpperCase()}
              </span>
              <span
                className="tabular-nums w-20 text-right"
                style={{
                  color:
                    pos.unrealized_pnl >= 0
                      ? "var(--aegis-signal-bull)"
                      : "var(--aegis-signal-bear)",
                }}
              >
                {formatPrice(pos.unrealized_pnl, 0)}
              </span>
              <span
                className="tabular-nums w-16 text-right"
                style={{
                  color:
                    pos.unrealized_pnl_pct >= 0
                      ? "var(--aegis-signal-bull)"
                      : "var(--aegis-signal-bear)",
                }}
              >
                {formatPercent(pos.unrealized_pnl_pct)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
