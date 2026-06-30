"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { fetchTheses, type ThesisCard } from "@/lib/api/thesis";
import { formatDate, formatPercent } from "@/lib/utils";

const columnHelper = createColumnHelper<ThesisCard>();

const columns = [
  columnHelper.accessor("ticker", {
    header: "Ticker",
    cell: (info) => (
      <span style={{ fontFamily: "var(--aegis-font-mono)", fontWeight: 600 }}>
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("direction", {
    header: "Direction",
    cell: (info) => {
      const v = info.getValue();
      const color =
        v === "long"
          ? "var(--aegis-signal-bull)"
          : v === "short_put"
            ? "var(--aegis-signal-bear)"
            : "var(--aegis-text-tertiary)";
      const label =
        v === "long" ? "Long" : v === "short_put" ? "Short Put" : v;
      return (
        <span
          style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: "4px",
            fontSize: "12px",
            fontWeight: 500,
            color,
            background:
              v === "long"
                ? "var(--aegis-signal-bull-bg)"
                : v === "short_put"
                  ? "var(--aegis-signal-bear-bg)"
                  : "var(--aegis-bg-elevated)",
          }}
        >
          {label}
        </span>
      );
    },
  }),
  columnHelper.accessor("entry_mode", {
    header: "Entry Mode",
    cell: (info) => {
      const v = info.getValue();
      const labels: Record<string, string> = {
        active_left: "Left Entry",
        active_right: "Right Follow",
        passive: "Passive",
        cc: "Covered Call",
        sell_put: "Sell Put",
      };
      return labels[v] || v;
    },
  }),
  columnHelper.accessor("thesis_valid_status", {
    header: "Status",
    cell: (info) => {
      const v = info.getValue();
      const color =
        v === "valid"
          ? "var(--aegis-signal-bull)"
          : v === "partial_broken"
            ? "var(--aegis-signal-neutral)"
            : v === "fully_broken"
              ? "var(--aegis-signal-bear)"
              : "var(--aegis-text-tertiary)";
      return (
        <span
          style={{
            color,
            fontSize: "13px",
            fontWeight: 500,
          }}
        >
          {v.replace(/_/g, " ")}
        </span>
      );
    },
  }),
  columnHelper.accessor("entry_date", {
    header: "Entry Date",
    cell: (info) => {
      const v = info.getValue();
      return v ? formatDate(v) : "\u2014";
    },
  }),
  columnHelper.accessor("actual_pnl_pct", {
    header: "P&L",
    cell: (info) => {
      const v = info.getValue();
      if (v == null) return "\u2014";
      const color =
        v >= 0 ? "var(--aegis-signal-bull)" : "var(--aegis-signal-bear)";
      return (
        <span style={{ color, fontWeight: 500 }}>{formatPercent(v * 100)}</span>
      );
    },
  }),
  columnHelper.accessor("judgment_score", {
    header: "Judgment",
    cell: (info) => {
      const v = info.getValue();
      return v != null ? `${v}/5` : "\u2014";
    },
  }),
  columnHelper.accessor("execution_score", {
    header: "Execution",
    cell: (info) => {
      const v = info.getValue();
      return v != null ? `${v}/5` : "\u2014";
    },
  }),
];

interface Props {
  filters: { status: string; direction: string; ticker: string };
}

export function ThesisTable({ filters }: Props) {
  const router = useRouter();
  const [data, setData] = useState<ThesisCard[]>([]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchTheses(filters);
      setData(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load theses");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const commonThStyle: React.CSSProperties = {
    padding: "10px 16px",
    textAlign: "left",
    fontSize: "12px",
    fontWeight: 500,
    color: "var(--aegis-text-tertiary)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    cursor: "pointer",
    userSelect: "none",
    transition: "color 150ms",
  };

  const commonTdStyle: React.CSSProperties = {
    padding: "10px 16px",
    fontSize: "14px",
    color: "var(--aegis-text-primary)",
  };

  if (error) {
    return (
      <div
        style={{
          padding: "32px",
          textAlign: "center",
          color: "var(--aegis-signal-bear)",
          fontSize: "14px",
        }}
      >
        {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div
        style={{
          padding: "32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        Loading...
      </div>
    );
  }

  if (!data.length) {
    return (
      <div
        style={{
          padding: "48px 32px",
          textAlign: "center",
          color: "var(--aegis-text-tertiary)",
          fontSize: "14px",
        }}
      >
        No thesis cards yet
      </div>
    );
  }

  return (
    <div
      style={{
        borderRadius: "8px",
        border: "1px solid var(--aegis-border-default)",
        overflow: "hidden",
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead style={{ background: "var(--aegis-bg-elevated)" }}>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  style={commonThStyle}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              style={{
                borderTop: "1px solid var(--aegis-border-default)",
                cursor: "pointer",
                transition: "background-color 150ms",
              }}
              onClick={() => router.push(`/thesis/${row.original.id}`)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background =
                  "var(--aegis-bg-elevated)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} style={commonTdStyle}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}