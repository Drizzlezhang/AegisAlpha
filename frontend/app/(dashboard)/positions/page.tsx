"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Position } from "@/lib/types";
import { formatPrice, formatPercent, dteFromExpiry } from "@/lib/utils";
import SignalBadge from "@/components/charts/signal-badge";
import EntryModeBadge from "@/components/charts/entry-mode-badge";
import LoadingSkeleton from "@/components/ui/loading-skeleton";
import EmptyState from "@/components/ui/empty-state";

type SortField = "ticker" | "unrealized_pnl" | "delta_dollars" | "health_score" | "dte";
type SortDir = "asc" | "desc";

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
  {
    id: 4, account: "LongBridge", ticker: "IWM", pos_type: "call",
    quantity: 2, avg_cost: 1800, current_price: 1650, strike: 210,
    expiry: "2027-01-15", option_type: "call", delta: 0.55, gamma: 0.005,
    theta: -0.12, vega: 0.48, iv: 28.5, delta_dollars: 8500,
    unrealized_pnl: -300, unrealized_pnl_pct: -8.3,
    entry_mode: "active_left", grade: "C", health_score: 55, dte: 220,
  },
];

const COLUMNS: { key: SortField; label: string }[] = [
  { key: "ticker", label: "Ticker" },
  { key: "unrealized_pnl", label: "P&L" },
  { key: "delta_dollars", label: "Delta $" },
  { key: "health_score", label: "Health" },
  { key: "dte", label: "DTE" },
];

export default function PositionsPage() {
  const [sortField, setSortField] = useState<SortField>("ticker");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [filterMode, setFilterMode] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data, error } = useSWR<Position[]>("/positions", fetcher, {
    fallbackData: MOCK_POSITIONS,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    let result = [...data];
    if (filterMode !== "all") {
      result = result.filter((p) => p.entry_mode === filterMode);
    }
    result.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === "asc" ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
    return result;
  }, [data, filterMode, sortField, sortDir]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  return (
    <div className="p-4">
      <h2
        className="text-lg font-semibold mb-4"
        style={{ color: "var(--aegis-text-primary)" }}
      >
        Positions
      </h2>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        {["all", "active_left", "active_right", "passive", "cc"].map((mode) => (
          <button
            key={mode}
            onClick={() => setFilterMode(mode)}
            className="px-3 py-1 text-xs rounded transition-colors duration-150"
            style={{
              color: filterMode === mode ? "var(--aegis-text-primary)" : "var(--aegis-text-secondary)",
              background: filterMode === mode ? "var(--aegis-bg-elevated)" : "var(--aegis-bg-surface)",
              borderColor: "var(--aegis-border-default)",
              borderWidth: 1,
            }}
          >
            {mode === "all" ? "All" : mode.replace("_", " ")}
          </button>
        ))}
      </div>

      {error && (
        <p style={{ color: "var(--aegis-signal-bear)" }}>Failed to load positions</p>
      )}
      {!data && !error && <LoadingSkeleton lines={5} />}
      {data && data.length === 0 && <EmptyState title="No positions" />}

      {filtered.length > 0 && (
        <div
          className="rounded-lg border overflow-hidden"
          style={{
            background: "var(--aegis-bg-surface)",
            borderColor: "var(--aegis-border-default)",
          }}
        >
          <table className="w-full text-sm">
            <thead>
              <tr
                className="text-xs uppercase tracking-wider"
                style={{ background: "var(--aegis-bg-elevated)" }}
              >
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Account</th>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className="py-2 px-3 font-medium cursor-pointer select-none transition-colors duration-150"
                    style={{
                      color: sortField === col.key ? "var(--aegis-brand)" : "var(--aegis-text-tertiary)",
                      textAlign: col.key === "ticker" ? "left" : "right",
                    }}
                  >
                    {col.label} {sortField === col.key ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                ))}
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Entry</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: "var(--aegis-text-tertiary)" }}>Grade</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((pos) => (
                <>
                  <tr
                    key={pos.id}
                    onClick={() => setExpandedId(expandedId === pos.id ? null : pos.id)}
                    className="cursor-pointer transition-colors duration-150"
                    style={{
                      background: expandedId === pos.id ? "var(--aegis-bg-elevated)" : "transparent",
                    }}
                  >
                    <td className="py-2 px-3" style={{ color: "var(--aegis-text-secondary)" }}>{pos.account}</td>
                    <td className="py-2 px-3 font-semibold" style={{ color: "var(--aegis-text-primary)" }}>{pos.ticker}</td>
                    <td
                      className="py-2 px-3 text-right tabular-nums"
                      style={{ color: pos.unrealized_pnl >= 0 ? "var(--aegis-signal-bull)" : "var(--aegis-signal-bear)" }}
                    >
                      {formatPrice(pos.unrealized_pnl, 0)}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-text-primary)" }}>
                      ${pos.delta_dollars.toLocaleString()}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums">
                      <SignalBadge signal={pos.health_score >= 80 ? "bull" : pos.health_score >= 60 ? "neutral" : "bear"} label={pos.health_score.toString()} />
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums" style={{ color: "var(--aegis-text-secondary)" }}>
                      {pos.dte > 0 ? pos.dte : "--"}
                    </td>
                    <td className="py-2 px-3"><EntryModeBadge mode={pos.entry_mode} /></td>
                    <td className="py-2 px-3">
                      <span
                        className="text-xs font-medium"
                        style={{
                          color: pos.grade === "A" ? "var(--aegis-signal-bull)" : pos.grade === "C" ? "var(--aegis-signal-bear)" : "var(--aegis-signal-neutral)",
                        }}
                      >
                        {pos.grade}
                      </span>
                    </td>
                  </tr>
                  {expandedId === pos.id && (
                    <tr key={`${pos.id}-detail`}>
                      <td colSpan={9} className="p-4" style={{ background: "var(--aegis-bg-base)" }}>
                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Type: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.pos_type.toUpperCase()} {pos.option_type?.toUpperCase()}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Qty: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.quantity}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Avg Cost: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>${formatPrice(pos.avg_cost)}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Current: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>${formatPrice(pos.current_price)}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Delta: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.delta.toFixed(3)}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Gamma: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.gamma.toFixed(4)}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Theta: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.theta.toFixed(3)}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>Vega: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.vega.toFixed(3)}</span>
                          </div>
                          {pos.strike && (
                            <div>
                              <span style={{ color: "var(--aegis-text-tertiary)" }}>Strike: </span>
                              <span style={{ color: "var(--aegis-text-primary)" }}>${pos.strike}</span>
                            </div>
                          )}
                          {pos.expiry && (
                            <div>
                              <span style={{ color: "var(--aegis-text-tertiary)" }}>Expiry: </span>
                              <span style={{ color: "var(--aegis-text-primary)" }}>{pos.expiry}</span>
                            </div>
                          )}
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>IV: </span>
                            <span style={{ color: "var(--aegis-text-primary)" }}>{pos.iv > 0 ? `${pos.iv.toFixed(1)}%` : "--"}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--aegis-text-tertiary)" }}>P&L %: </span>
                            <span style={{ color: pos.unrealized_pnl_pct >= 0 ? "var(--aegis-signal-bull)" : "var(--aegis-signal-bear)" }}>
                              {formatPercent(pos.unrealized_pnl_pct)}
                            </span>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
